// SPDX-License-Identifier: GPL-3.0-or-later
#include "aster_dl.h"
#include "aster_libc.h"
#include "dynarmic_host.h"
#include "thunk_manager.h"

#include <array>
#include <algorithm>
#include <android/asset_manager.h>
#include <android/log.h>
#include <cstring>
#include <elf.h>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>
#include <unistd.h>

namespace {
using Host = DynarmicHost;
using Jit = Dynarmic::A32::Jit;
constexpr uint32_t defaultScope = 0xffffffff;
constexpr uint32_t nextScope = 0xfffffffe;
constexpr uint32_t processHandle = 0x5e000000;
constexpr std::array systemLibraries{
    "libc.so", "libm.so", "libdl.so", "liblog.so", "libstdc++.so", "libz.so",
    "libandroid.so", "libGLESv1_CM.so", "libGLESv2.so", "libEGL.so", "libOpenSLES.so"
};

struct Error {
    std::string message;
    uint32_t buffer = 0;
};
struct Symbol {
    std::string name;
    uint32_t address;
    uint32_t size;
    uint32_t nameAddress = 0;
};
struct Image {
    std::string name;
    uint32_t base;
    uint32_t nameAddress = 0;
    uint32_t headersAddress = 0;
    uint32_t unwindAddress = 0;
    uint32_t unwindCount = 0;
    std::vector<Elf32_Phdr> headers;
    std::vector<Symbol> symbols;

    bool contains(uint32_t address) const {
        return std::any_of(headers.begin(), headers.end(), [&](const auto& header) {
            return header.p_type == PT_LOAD && uint64_t(address) >= uint64_t(base) + header.p_vaddr
                && uint64_t(address) < uint64_t(base) + header.p_vaddr + header.p_memsz;
        });
    }
};
struct LoaderState {
    std::mutex mutex;
    std::unordered_map<uint32_t, size_t> references;
    std::unordered_map<std::thread::id, Error> errors;
    std::vector<Image> images;
};
std::mutex catalogMutex;
std::unordered_map<Host*, std::weak_ptr<LoaderState>> catalogs;

const char* text(Host& host, uint32_t address) {
    if (!address) return nullptr;
    for (uint64_t cursor = address; cursor < host.GetGuestMemorySize(); ++cursor) {
        if (!host.MemoryRead8(uint32_t(cursor)))
            return reinterpret_cast<const char*>(host.GetGuestMemoryBase() + address);
    }
    host.Fail("Unterminated Aster dynamic loader string");
    return nullptr;
}

void error(LoaderState& state, const std::string& message) {
    state.errors[std::this_thread::get_id()].message = message;
}

bool read(AAsset* asset, uint64_t offset, void* output, size_t count) {
    const auto length = uint64_t(AAsset_getLength64(asset));
    if (offset > length || count > length - offset) return false;
    return AAsset_seek64(asset, off64_t(offset), SEEK_SET) == off64_t(offset)
        && AAsset_read(asset, output, count) == int64_t(count);
}

bool catalog(Host& host, AAssetManager* assets, LoaderState& state) {
    struct Input { const char* name; const char* asset; uint32_t base; uint32_t limit; };
    constexpr Input inputs[] = {
#include "aster_images.inc"
    };
    for (const auto& input : inputs) {
        const std::unique_ptr<AAsset, decltype(&AAsset_close)> asset(
            AAssetManager_open(assets, input.asset, AASSET_MODE_RANDOM), &AAsset_close);
        if (!asset) return false;
        Elf32_Ehdr header{};
        if (!read(asset.get(), 0, &header, sizeof(header)) ||
            std::memcmp(header.e_ident, ELFMAG, SELFMAG) ||
            header.e_ident[EI_CLASS] != ELFCLASS32 || header.e_ident[EI_DATA] != ELFDATA2LSB ||
            header.e_machine != EM_ARM || header.e_phentsize != sizeof(Elf32_Phdr) ||
            !header.e_phnum || header.e_phnum > 256) return false;
        Image image{input.name, input.base};
        image.headers.resize(header.e_phnum);
        if (!read(asset.get(), header.e_phoff, image.headers.data(), image.headers.size() * sizeof(Elf32_Phdr))) return false;
        for (const auto& program : image.headers) {
            if (program.p_type == PT_LOAD &&
                uint64_t(input.base) + program.p_vaddr + program.p_memsz > input.limit) return false;
            if (program.p_type == PT_ARM_EXIDX) {
                image.unwindAddress = image.base + program.p_vaddr;
                image.unwindCount = program.p_memsz / 8;
            }
        }
        if (header.e_shnum) {
            if (header.e_shentsize != sizeof(Elf32_Shdr)) return false;
            std::vector<Elf32_Shdr> sections(header.e_shnum);
            if (!read(asset.get(), header.e_shoff, sections.data(), sections.size() * sizeof(Elf32_Shdr))) return false;
            for (const auto& section : sections) {
                if (section.sh_type != SHT_DYNSYM) continue;
                if (section.sh_entsize != sizeof(Elf32_Sym) || section.sh_link >= sections.size() ||
                    section.sh_size % sizeof(Elf32_Sym) || section.sh_size > 16 * 1024 * 1024) return false;
                const auto& strings = sections[section.sh_link];
                if (strings.sh_type != SHT_STRTAB || strings.sh_size > 16 * 1024 * 1024) return false;
                std::vector<char> names(strings.sh_size);
                std::vector<Elf32_Sym> symbols(section.sh_size / sizeof(Elf32_Sym));
                if (!read(asset.get(), strings.sh_offset, names.data(), names.size()) ||
                    !read(asset.get(), section.sh_offset, symbols.data(), section.sh_size)) return false;
                for (const auto& symbol : symbols) {
                    if (symbol.st_shndx == SHN_UNDEF || symbol.st_name >= names.size() ||
                        (ELF32_ST_BIND(symbol.st_info) != STB_GLOBAL && ELF32_ST_BIND(symbol.st_info) != STB_WEAK))
                        continue;
                    const char* name = names.data() + symbol.st_name;
                    if (!std::memchr(name, 0, names.size() - symbol.st_name)) return false;
                    if (*name) image.symbols.push_back({name, image.base + symbol.st_value, symbol.st_size});
                }
            }
        }
        std::sort(image.symbols.begin(), image.symbols.end(), [](const auto& left, const auto& right) {
            return left.address < right.address;
        });
        size_t namesSize = 0;
        for (const auto& symbol : image.symbols) namesSize += symbol.name.size() + 1;
        const uint32_t symbolNames = host.GuestAlloc(namesSize);
        if (!symbolNames) return false;
        uint32_t cursor = symbolNames;
        for (auto& symbol : image.symbols) {
            symbol.nameAddress = cursor;
            std::memcpy(host.GetGuestMemoryBase() + cursor, symbol.name.c_str(), symbol.name.size() + 1);
            cursor += uint32_t(symbol.name.size() + 1);
        }
        image.nameAddress = host.GuestAlloc(image.name.size() + 1);
        image.headersAddress = host.GuestAlloc(image.headers.size() * sizeof(Elf32_Phdr));
        if (!image.nameAddress || !image.headersAddress) return false;
        std::memcpy(host.GetGuestMemoryBase() + image.nameAddress, image.name.c_str(), image.name.size() + 1);
        std::memcpy(host.GetGuestMemoryBase() + image.headersAddress, image.headers.data(), image.headers.size() * sizeof(Elf32_Phdr));
        state.images.push_back(std::move(image));
    }
    return true;
}

bool loaded(Host& host, const Image& image) {
    return !image.symbols.empty() && host.FindLibrarySymbol(image.name, image.symbols.front().name) != 0;
}
}

FILE* asterOpenGuestProcMaps(Host& host,const char* path,bool& handled) {
    handled=false;
    if(!path)return nullptr;
    const std::string own="/proc/"+std::to_string(getpid())+"/maps";
    if(std::strcmp(path,"/proc/self/maps") && path!=own)return nullptr;
    handled=true;
    std::shared_ptr<LoaderState> state;
    {
        std::lock_guard lock(catalogMutex);
        const auto entry=catalogs.find(&host);
        if(entry!=catalogs.end())state=entry->second.lock();
    }
    if(!state){errno=ENOENT;return nullptr;}
    std::string content;
    const auto pageSize=uint64_t(sysconf(_SC_PAGESIZE));
    for(const auto& image:state->images) {
        if(!loaded(host,image))continue;
        for(const auto& header:image.headers) {
            if(header.p_type!=PT_LOAD || !header.p_memsz)continue;
            const auto begin=(uint64_t(image.base)+header.p_vaddr)&~(pageSize-1);
            const auto end=(uint64_t(image.base)+header.p_vaddr+header.p_memsz+pageSize-1)&~(pageSize-1);
            char row[256];
            const int n=snprintf(row,sizeof(row),"%08x-%08x %c%c%cp %08x 00:00 0 /aster-guest/lib/armeabi/%s\n",
                unsigned(begin),unsigned(end),header.p_flags&PF_R?'r':'-',header.p_flags&PF_W?'w':'-',
                header.p_flags&PF_X?'x':'-',unsigned(uint64_t(header.p_offset)&~(pageSize-1)),image.name.c_str());
            if(n<=0 || size_t(n)>=sizeof(row)){errno=EOVERFLOW;return nullptr;}
            content.append(row,size_t(n));
        }
    }
    auto pattern=asterTemporaryPattern();
    if(pattern.empty()){errno=ENOENT;return nullptr;}
    std::vector<char> temporary(pattern.begin(),pattern.end());temporary.push_back(0);
    const int fd=mkstemp(temporary.data());
    if(fd<0)return nullptr;
    unlink(temporary.data());
    FILE* file=fdopen(fd,"w+b");
    if(!file){const int error=errno;close(fd);errno=error;return nullptr;}
    if(fwrite(content.data(),1,content.size(),file)!=content.size() || fseek(file,0,SEEK_SET)) {
        const int error=errno;fclose(file);errno=error;return nullptr;
    }
    __android_log_print(ANDROID_LOG_INFO,"AsterLoader","Guest module maps opened for %s (%zu bytes)",path,content.size());
    return file;
}

bool asterGuestImageRange(Host& host, uint32_t address, uint64_t end, size_t pageSize) {
    std::shared_ptr<LoaderState> state;
    {
        std::lock_guard lock(catalogMutex);
        auto entry = catalogs.find(&host);
        if (entry != catalogs.end()) state = entry->second.lock();
    }
    if (!state) return false;
    for (const auto& image : state->images) {
        if (!loaded(host, image)) continue;
        uint64_t cursor = address;
        for (const auto& header : image.headers) {
            if (header.p_type != PT_LOAD) continue;
            const uint64_t begin = (uint64_t(image.base) + header.p_vaddr) & ~(uint64_t(pageSize) - 1);
            const uint64_t limit = (uint64_t(image.base) + header.p_vaddr + header.p_memsz + pageSize - 1) & ~(uint64_t(pageSize) - 1);
            if (limit <= cursor) continue;
            if (begin > cursor) break;
            cursor = limit;
            if (cursor >= end) return true;
        }
    }
    return false;
}

bool registerAsterDynamicLoader(Host& host, AAssetManager* assets) {
    const auto state = std::make_shared<LoaderState>();
    if (!catalog(host, assets, *state)) {
        host.Fail("Cannot catalog Aster guest libraries");
        return false;
    }
    {
        std::lock_guard lock(catalogMutex);
        for (auto it = catalogs.begin(); it != catalogs.end();) {
            if (it->second.expired()) it = catalogs.erase(it);
            else ++it;
        }
        catalogs[&host] = state;
    }
    auto& manager = host.GetThunkManager();
    manager.RegisterThunk("dlopen", [state](Jit& jit, Host& guest) {
        const char* path = text(guest, jit.Regs()[0]);
        std::lock_guard lock(state->mutex);
        uint32_t handle = processHandle;
        if (path) {
            const char* leaf = std::strrchr(path, '/');
            const std::string name = leaf ? leaf + 1 : path;
            handle = 0;
            for (size_t i = 0; i < systemLibraries.size(); ++i)
                if (name == systemLibraries[i]) handle = processHandle + uint32_t((i + 1) * 4);
            for (size_t i = 0; i < state->images.size(); ++i)
                if (name == state->images[i].name && loaded(guest, state->images[i]))
                    handle = processHandle + 0x100 + uint32_t(i * 4);
            if (!handle) error(*state, "Aster guest library is unavailable: " + name);
        }
        if (handle) ++state->references[handle];
        jit.Regs()[0] = handle;
    });
    manager.RegisterThunk("dlsym", [state](Jit& jit, Host& guest) {
        const uint32_t handle = jit.Regs()[0];
        const char* name = text(guest, jit.Regs()[1]);
        std::lock_guard lock(state->mutex);
        jit.Regs()[0] = 0;
        if (!name) { error(*state, "Aster dlsym requires a symbol name"); return; }
        if (handle == nextScope) {
            error(*state, "Aster RTLD_NEXT scope is unavailable");
            return;
        }
        if (handle != defaultScope && !state->references.count(handle)) {
            error(*state, "Invalid or closed Aster library handle");
            return;
        }
        uint32_t address = 0;
        if (handle == defaultScope || handle == processHandle) address = guest.FindSymbol(name);
        else if (handle < processHandle + 0x100) address = guest.GetThunkManager().FindRegisteredSymbol(name);
        else {
            const size_t index = (handle - processHandle - 0x100) / 4;
            if (index < state->images.size()) address = guest.FindLibrarySymbol(state->images[index].name, name);
        }
        jit.Regs()[0] = address;
        if (!address) error(*state, "Aster guest symbol is unavailable: " + std::string(name));
    });
    manager.RegisterThunk("dlclose", [state](Jit& jit, Host&) {
        std::lock_guard lock(state->mutex);
        const auto found = state->references.find(jit.Regs()[0]);
        if (found == state->references.end()) {
            error(*state, "Invalid or closed Aster library handle");
            jit.Regs()[0] = UINT32_MAX;
            return;
        }
        if (--found->second == 0) state->references.erase(found);
        // Already relocated system libraries and the main executable remain resident.
        jit.Regs()[0] = 0;
    });
    manager.RegisterThunk("dlerror", [state](Jit& jit, Host& guest) {
        std::lock_guard lock(state->mutex);
        auto& current = state->errors[std::this_thread::get_id()];
        jit.Regs()[0] = 0;
        if (current.message.empty()) return;
        const uint32_t buffer = guest.GuestAlloc(current.message.size() + 1);
        if (!buffer) return;
        std::memcpy(guest.GetGuestMemoryBase() + buffer, current.message.c_str(), current.message.size() + 1);
        guest.GuestFree(current.buffer);
        current.buffer = buffer;
        current.message.clear();
        jit.Regs()[0] = buffer;
    });
    manager.RegisterThunk("dladdr", [state](Jit& jit, Host& guest) {
        const uint32_t address = jit.Regs()[0] & ~1u, output = jit.Regs()[1];
        jit.Regs()[0] = 0;
        if (!output || uint64_t(output) + 16 > guest.GetGuestMemorySize()) { guest.Fail("Invalid Dl_info output"); return; }
        for (const auto& image : state->images) {
            if (!image.contains(address) || !loaded(guest, image)) continue;
            uint32_t symbolName = 0, symbolAddress = 0;
            for (const auto& symbol : image.symbols) {
                if ((symbol.address & ~1u) > address) break;
                if (symbol.size && uint64_t(address) >= uint64_t(symbol.address & ~1u) + symbol.size) continue;
                symbolAddress = symbol.address;
                symbolName = symbol.nameAddress;
            }
            const std::array<uint32_t, 4> info{image.nameAddress, image.base, symbolName, symbolAddress};
            std::memcpy(guest.GetGuestMemoryBase() + output, info.data(), sizeof(info));
            jit.Regs()[0] = 1;
            return;
        }
    });
    manager.RegisterThunk("dl_iterate_phdr", [state](Jit& jit, Host& guest) {
        const uint32_t callback = jit.Regs()[0], data = jit.Regs()[1];
        jit.Regs()[0] = 0;
        const uint32_t info = guest.GuestAlloc(16);
        if (!info) { guest.Fail("dl_phdr_info allocation failed"); return; }
        for (const auto& image : state->images) {
            if (!loaded(guest, image)) continue;
            const std::array<uint32_t, 4> words{
                image.base, image.nameAddress, image.headersAddress, uint32_t(image.headers.size())};
            std::memcpy(guest.GetGuestMemoryBase() + info, words.data(), sizeof(words));
            const auto result = guest.CallGuestNested(callback, {info, 16, data});
            if (result || guest.HasFailed()) { jit.Regs()[0] = result; break; }
        }
        guest.GuestFree(info);
    });
    manager.RegisterThunk("dl_unwind_find_exidx", [state](Jit& jit, Host& guest) {
        const uint32_t pc = jit.Regs()[0] & ~1u, count = jit.Regs()[1];
        jit.Regs()[0] = 0;
        if (!count || uint64_t(count) + 4 > guest.GetGuestMemorySize()) { guest.Fail("Invalid unwind count output"); return; }
        guest.MemoryWrite32(count, 0);
        for (const auto& image : state->images)
            if (image.contains(pc) && loaded(guest, image)) {
                guest.MemoryWrite32(count, image.unwindCount);
                jit.Regs()[0] = image.unwindAddress;
                return;
            }
    });
    return true;
}

bool checkAsterLibraryQueries(Host& host) {
    auto call = [&](const char* name, std::vector<uint32_t> args) {
        return host.RunFunction(host.GetThunkManager().ResolveSymbol(name, STT_FUNC), args);
    };
    const auto address = host.FindLibrarySymbol("libSrc.so", "JNI_OnLoad");
    const auto output = host.GuestAlloc(16);
    const auto count = host.GuestAlloc(4);
    constexpr std::array code{0xe5923000u, 0xe2833001u, 0xe5823000u, 0xe3a00000u, 0xe12fff1eu};
    const auto callback = host.GuestAlloc(sizeof(code));
    if (!address || !output || !count || !callback) return false;
    std::memcpy(host.GetGuestMemoryBase() + callback, code.data(), sizeof(code));
    host.AddExecutableRange(callback, sizeof(code));
    host.MemoryWrite32(count, 0);
    const bool found = call("dladdr", {address, output}) == 1
        && host.MemoryRead32(output + 4) == 0x40000000
        && host.MemoryRead32(output + 12) == address;
    const auto path=host.GuestAlloc(64),mode=host.GuestAlloc(4),line=host.GuestAlloc(256),format=host.GuestAlloc(16),range=host.GuestAlloc(8);
    if(!path || !mode || !line || !format || !range)return false;
    strcpy(reinterpret_cast<char*>(host.GetGuestMemoryBase()+path),"/proc/self/maps");
    strcpy(reinterpret_cast<char*>(host.GetGuestMemoryBase()+mode),"rt");
    strcpy(reinterpret_cast<char*>(host.GetGuestMemoryBase()+format),"%lx-%lx");
    const auto file=call("fopen",{path,mode});
    if(!file)return false;
    bool engine=false;
    while(call("fgets",{line,256,file})) {
        if(!strstr(reinterpret_cast<char*>(host.GetGuestMemoryBase()+line),"/libSrc.so"))continue;
        if(call("sscanf",{line,format,range,range+4})==2
            && host.MemoryRead32(range)==0x40000000 && host.MemoryRead32(range+4)>0x40000000)engine=true;
    }
    const bool closed=call("fclose",{file})==0;
    bool handled=false;FILE* maps=asterOpenGuestProcMaps(host,"/proc/1/maps",handled);
    const bool isolated=!handled && !maps;
    return found && engine && closed && isolated && call("dl_iterate_phdr", {callback, count}) == 0
        && host.MemoryRead32(count) >= 1 && !host.HasFailed();
}

bool checkAsterDynamicLoader(Host& host) {
    auto call = [&](const char* name, std::vector<uint32_t> args) {
        return host.RunFunction(host.GetThunkManager().ResolveSymbol(name, STT_FUNC), args);
    };
    const uint32_t library = host.GuestAlloc(sizeof("libc.so"));
    const uint32_t symbol = host.GuestAlloc(sizeof("malloc"));
    if (!library || !symbol) return false;
    std::memcpy(host.GetGuestMemoryBase() + library, "libc.so", sizeof("libc.so"));
    std::memcpy(host.GetGuestMemoryBase() + symbol, "malloc", sizeof("malloc"));
    const uint32_t handle = call("dlopen", {library, 0});
    const auto address = host.GetThunkManager().ResolveSymbol("malloc", STT_FUNC);
    return handle && call("dlsym", {handle, symbol}) == address
        && call("dlsym", {defaultScope, symbol}) == address
        && call("dlclose", {handle}) == 0
        && call("dlsym", {handle, symbol}) == 0
        && call("dlerror", {}) != 0 && call("dlerror", {}) == 0
        && !host.HasFailed();
}
