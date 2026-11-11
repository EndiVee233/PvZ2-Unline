// SPDX-License-Identifier: GPL-3.0-or-later
#include "aster_libc.h"
#include "dynarmic_host.h"
#include "thunk_manager.h"

#include <algorithm>
#include <array>
#include <android/log.h>
#include <bit>
#include <cerrno>
#include <climits>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <cwchar>
#include <cwctype>
#include <elf.h>
#include <fnmatch.h>
#include <memory>
#include <mutex>
#include <string>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/statvfs.h>
#include <locale.h>
#include <unordered_map>

namespace {
using Host = DynarmicHost;
using Jit = Dynarmic::A32::Jit;
static_assert(sizeof(wchar_t) == 4);
constexpr std::array classes{"alnum", "alpha", "blank", "cntrl", "digit", "graph",
                             "lower", "print", "punct", "space", "upper", "xdigit"};
// Bionic uses four sequence bytes on A32 and adds four reserved bytes on AArch64.
constexpr size_t guestMbStateSize = 4;
static_assert(sizeof(mbstate_t) == 8);
std::mutex temporaryMutex;
std::string temporaryDirectory;

template<class T>
size_t remaining(Host& host, uint32_t address) {
    const size_t size = host.GetGuestMemorySize();
    return address && address < size && address % alignof(T) == 0
        ? (size - address) / sizeof(T) : 0;
}

template<class T>
T* span(Host& host, uint32_t address, size_t count) {
    if (!address || count > remaining<T>(host, address) ||
        address >= host.GetGuestMemorySize() || address % alignof(T)) {
        const auto& r=host.CurrentJit().Regs();
        __android_log_print(ANDROID_LOG_ERROR,"AsterLibc","Rejected buffer address=%08x count=%zu unit=%zu PC=%08x LR=%08x R0=%08x R1=%08x R2=%08x R3=%08x",address,count,sizeof(T),r[15],r[14],r[0],r[1],r[2],r[3]);
        host.Fail("Invalid Aster libc guest buffer");
        return nullptr;
    }
    return reinterpret_cast<T*>(host.GetGuestMemoryBase() + address);
}

template<class T>
const T* string(Host& host, uint32_t address, size_t limit = SIZE_MAX) {
    const auto* data = span<T>(host, address, 0);
    if (!data) return nullptr;
    const size_t length = std::min(remaining<T>(host, address), limit);
    if (std::char_traits<T>::find(data, length, T{}) || length == limit) return data;
    host.Fail("Unterminated Aster libc guest string");
    return nullptr;
}

uint32_t guestPointer(Host& host, const wchar_t* pointer) {
    return pointer ? uint32_t(reinterpret_cast<const uint8_t*>(pointer) - host.GetGuestMemoryBase()) : 0;
}

template<class T>
void return64(Jit& jit, T value) {
    const auto bits = std::bit_cast<uint64_t>(value);
    jit.Regs()[0] = uint32_t(bits);
    jit.Regs()[1] = uint32_t(bits >> 32);
}

void setGuestErrno(Host& host, int error) {
    host.MemoryWrite32(host.GuestErrnoAddress(), error);
}

template<class Convert>
uint32_t convertMultibyte(Host& host, uint32_t stateAddress, Convert convert) {
    mbstate_t hostState{};
    char* guestState = stateAddress ? span<char>(host, stateAddress, guestMbStateSize) : nullptr;
    if (stateAddress && !guestState) return UINT32_MAX;
    if (guestState) std::memcpy(&hostState, guestState, guestMbStateSize);
    const size_t result = convert(guestState ? &hostState : nullptr);
    if (result == size_t(-1)) setGuestErrno(host, errno);
    if (guestState) std::memcpy(guestState, &hostState, guestMbStateSize);
    return uint32_t(result);
}
}

void configureAsterTemporaryFiles(const std::string& directory) {
    std::lock_guard lock(temporaryMutex);
    temporaryDirectory = directory;
}

std::string asterTemporaryPattern() {
    std::lock_guard lock(temporaryMutex);
    return temporaryDirectory.empty() ? std::string() : temporaryDirectory + "/aster-XXXXXX";
}

#include "aster_locale.inc"

int32_t asterGuestStringCompare(Host& host,uint32_t a,uint32_t b,bool ignoreCase) {
    const auto readable=[&](uint64_t at) {
        if (!at || at>=host.GetGuestMemorySize()) return false;
        if (at>=ASTER_STACK_BASE && at<uint64_t(ASTER_STACK_BASE)+64*ASTER_STACK_STRIDE) {
            const auto offset=(at-ASTER_STACK_BASE)%ASTER_STACK_STRIDE;
            return offset>=uint64_t(sysconf(_SC_PAGESIZE)) && offset<ASTER_STACK_SIZE;
        }
        return true;
    };
    for (uint64_t offset=0;offset<4*1024*1024;++offset) {
        if (!readable(uint64_t(a)+offset) || !readable(uint64_t(b)+offset)) {
            const auto& r=host.CurrentJit().Regs();
            __android_log_print(ANDROID_LOG_ERROR,"AsterLibc","Invalid comparison a=%08x b=%08x offset=%llu PC=%08x LR=%08x",a,b,(unsigned long long)offset,r[15],r[14]);
            // Diagnose the producer, without dereferencing the rejected pointer.
            for (unsigned first=0;first<16;first+=4)
                __android_log_print(ANDROID_LOG_ERROR,"AsterLibc","Compare regs r%u=%08x r%u=%08x r%u=%08x r%u=%08x",first,r[first],first+1,r[first+1],first+2,r[first+2],first+3,r[first+3]);
            const auto inHeap=[](uint32_t p,size_t n) {return p>=0x50000000u && uint64_t(p)+n<=0x7ffc0000ull;};
            const auto dump=[&](const char* label,uint32_t p,unsigned count) {
                if (!inHeap(p,size_t(count)*4)) return;
                for(unsigned i=0;i<count;i+=4) {
                    uint32_t v[4]{};for(unsigned k=0;k<4 && i+k<count;++k)v[k]=host.MemoryRead32(p+(i+k)*4);
                    __android_log_print(ANDROID_LOG_ERROR,"AsterLibc","Compare %s @%08x: %08x %08x %08x %08x",label,p+i*4,v[0],v[1],v[2],v[3]);
                }
            };
            if(inHeap(b,256)) {
                char name[257]{};for(unsigned i=0;i<256;++i){name[i]=char(host.MemoryRead8(b+i));if(!name[i])break;}
                __android_log_print(ANDROID_LOG_ERROR,"AsterLibc","Compare requested name: %s",name);
            }
            dump("record",r[4],20);dump("owner",r[5],24);
            if(inHeap(r[5]+0x44,4)) {
                const uint32_t header=host.MemoryRead32(r[5]+0x44);dump("header",header,8);
                if(inHeap(header+4,8)) {
                    const uint32_t begin=host.MemoryRead32(header+4),end=host.MemoryRead32(header+8);
                    if(end>=begin && inHeap(begin,end-begin) && end-begin<1024*1024)
                        for(uint32_t at=begin,index=0;at+0x44<=end && index<20;at+=0x44,++index)
                            __android_log_print(ANDROID_LOG_ERROR,"AsterLibc","Compare entry %u @%08x name=%08x",index,at,host.MemoryRead32(at));
                }
            }
            uint32_t fp=r[11];
            for(unsigned depth=0;depth<16 && fp>=ASTER_STACK_BASE+4 && fp<ASTER_STACK_BASE+64*ASTER_STACK_STRIDE && readable(fp-4) && readable(fp+3);++depth) {
                const uint32_t next=host.MemoryRead32(fp-4),lr=host.MemoryRead32(fp);
                __android_log_print(ANDROID_LOG_ERROR,"AsterLibc","Compare frame %u fp=%08x lr=%08x prev=%08x",depth,fp,lr,next);
                if(next<=fp)break;fp=next;
            }
            host.Fail("Invalid guest string comparison range");return 0;
        }
        unsigned left=host.MemoryRead8(a+offset),right=host.MemoryRead8(b+offset);
        if (ignoreCase) {
            if (left>='A' && left<='Z')left+='a'-'A';
            if (right>='A' && right<='Z')right+='a'-'A';
        }
        if (left!=right || !left) return int32_t(left)-int32_t(right);
    }
    host.Fail("Unterminated guest string comparison");return 0;
}

void registerAsterLibc(Host& host) {
    auto& manager = host.GetThunkManager();
    registerAsterLocale(host);
    for (auto [name, function] : {std::pair{"sqrtf", &::sqrtf}, {"roundf", &::roundf}}) {
        manager.RegisterThunk(name, [function](Jit& jit, Host&) {
            jit.Regs()[0] = std::bit_cast<uint32_t>(function(std::bit_cast<float>(jit.Regs()[0])));
        });
    }
    manager.RegisterThunk("round", [](Jit& jit, Host&) {
        const uint64_t bits = uint64_t(jit.Regs()[0]) | (uint64_t(jit.Regs()[1]) << 32);
        return64(jit, std::round(std::bit_cast<double>(bits)));
    });
    manager.RegisterThunk("difftime", [](Jit& jit, Host&) {
        return64(jit, double(int32_t(jit.Regs()[0])) - double(int32_t(jit.Regs()[1])));
    });
    manager.RegisterThunk("atoll", [](Jit& jit, Host& guest) {
        if (const auto* value = string<char>(guest, jit.Regs()[0])) return64(jit, std::atoll(value));
    });
    manager.RegisterThunk("strcspn", [](Jit& jit, Host& guest) {
        const auto* value = string<char>(guest, jit.Regs()[0]);
        const auto* reject = string<char>(guest, jit.Regs()[1]);
        if (value && reject) jit.Regs()[0] = uint32_t(std::strcspn(value, reject));
    });
    manager.RegisterThunk("fnmatch", [](Jit& jit, Host& guest) {
        const auto* pattern = string<char>(guest, jit.Regs()[0]);
        const auto* value = string<char>(guest, jit.Regs()[1]);
        if (pattern && value) jit.Regs()[0] = fnmatch(pattern, value, int32_t(jit.Regs()[2]));
    });
    manager.RegisterThunk("__android_log_write", [](Jit& jit, Host& guest) {
        const auto* tag = jit.Regs()[1] ? string<char>(guest, jit.Regs()[1]) : nullptr;
        const auto* message = string<char>(guest, jit.Regs()[2]);
        if (message && !guest.HasFailed()) jit.Regs()[0] = __android_log_write(int32_t(jit.Regs()[0]), tag, message);
    });
    manager.RegisterThunk("getcwd", [](Jit& jit, Host& guest) {
        const uint32_t address = jit.Regs()[0];
        const uint32_t size = jit.Regs()[1];
        jit.Regs()[0] = 0;
        if (address) {
            if (!size) {
                setGuestErrno(guest, EINVAL);
                return;
            }
            auto* buffer = span<char>(guest, address, size);
            if (!buffer) return;
            if (::getcwd(buffer, size)) jit.Regs()[0] = address;
            else setGuestErrno(guest, errno);
            return;
        }
        const std::unique_ptr<char, decltype(&std::free)> path(::getcwd(nullptr, 0), &std::free);
        if (!path) {
            setGuestErrno(guest, errno);
            return;
        }
        const size_t length = std::strlen(path.get()) + 1;
        if (size && size < length) {
            setGuestErrno(guest, ERANGE);
            return;
        }
        const uint32_t result = guest.GuestAlloc(size ? size : length);
        if (result) {
            std::memcpy(span<char>(guest, result, length), path.get(), length);
            jit.Regs()[0] = result;
        } else {
            setGuestErrno(guest, ENOMEM);
        }
    });
    manager.RegisterThunk("memalign", [](Jit& jit, Host& guest) {
        const uint32_t alignment = jit.Regs()[0];
        const uint32_t size = jit.Regs()[1];
        jit.Regs()[0] = std::has_single_bit(alignment) ? guest.GuestAlloc(std::max(size, 1u), alignment) : 0;
    });
    for (auto [name, function] : {std::pair{"iswalnum", &std::iswalnum}, {"iswspace", &std::iswspace},
                                  {"wctob", &std::wctob}}) {
        manager.RegisterThunk(name, [function](Jit& jit, Host&) { jit.Regs()[0] = function(jit.Regs()[0]); });
    }
    for (auto [name, function] : {std::pair{"towlower", &std::towlower}, {"towupper", &std::towupper}}) {
        manager.RegisterThunk(name, [function](Jit& jit, Host&) { jit.Regs()[0] = function(jit.Regs()[0]); });
    }
    manager.RegisterThunk("btowc", [](Jit& jit, Host&) { jit.Regs()[0] = std::btowc(int32_t(jit.Regs()[0])); });
    manager.RegisterThunk("wctype", [](Jit& jit, Host& guest) {
        const auto* name = string<char>(guest, jit.Regs()[0]);
        jit.Regs()[0] = 0;
        if (!name) return;
        for (size_t i = 0; i < classes.size(); ++i) {
            if (std::strcmp(name, classes[i]) == 0) {
                jit.Regs()[0] = uint32_t(i + 1);
                return;
            }
        }
    });
    manager.RegisterThunk("iswctype", [](Jit& jit, Host&) {
        const uint32_t descriptor = jit.Regs()[1];
        jit.Regs()[0] = descriptor && descriptor <= classes.size()
            ? std::iswctype(jit.Regs()[0], std::wctype(classes[descriptor - 1])) : 0;
    });
    for (auto [name, function] : {std::pair{"wcsspn", &std::wcsspn}, {"wcscspn", &std::wcscspn}}) {
        manager.RegisterThunk(name, [function](Jit& jit, Host& guest) {
            const auto* text = string<wchar_t>(guest, jit.Regs()[0]);
            const auto* set = string<wchar_t>(guest, jit.Regs()[1]);
            if (text && set) jit.Regs()[0] = uint32_t(function(text, set));
        });
    }
    manager.RegisterThunk("wcscoll", [](Jit& jit, Host& guest) {
        const auto* first = string<wchar_t>(guest, jit.Regs()[0]);
        const auto* second = string<wchar_t>(guest, jit.Regs()[1]);
        if (first && second) jit.Regs()[0] = std::wcscoll(first, second);
    });
    manager.RegisterThunk("wcsxfrm", [](Jit& jit, Host& guest) {
        const uint32_t count = jit.Regs()[2];
        const auto* source = string<wchar_t>(guest, jit.Regs()[1]);
        auto* destination = count ? span<wchar_t>(guest, jit.Regs()[0], count) : nullptr;
        if (source && !guest.HasFailed()) jit.Regs()[0] = uint32_t(std::wcsxfrm(destination, source, count));
    });
    manager.RegisterThunk("wcstol", [](Jit& jit, Host& guest) {
        const auto* source = string<wchar_t>(guest, jit.Regs()[0]);
        const auto endAddress = jit.Regs()[1];
        auto* output = endAddress ? span<uint32_t>(guest, endAddress, 1) : nullptr;
        if (!source || guest.HasFailed()) return;
        wchar_t* end = const_cast<wchar_t*>(source);
        errno = 0;
        const long value = std::wcstol(source, &end, int32_t(jit.Regs()[2]));
        if (output) *output = guestPointer(guest, end);
        if (errno || value > INT32_MAX || value < INT32_MIN)
            setGuestErrno(guest, errno ? errno : ERANGE);
        jit.Regs()[0] = uint32_t(std::clamp(value, long(INT32_MIN), long(INT32_MAX)));
    });
    manager.RegisterThunk("wcstombs", [](Jit& jit, Host& guest) {
        const uint32_t count = jit.Regs()[2];
        const auto* source = string<wchar_t>(guest, jit.Regs()[1]);
        auto* destination = jit.Regs()[0] ? span<char>(guest, jit.Regs()[0], count) : nullptr;
        if (source && !guest.HasFailed()) {
            const size_t result = std::wcstombs(destination, source, count);
            if (result == size_t(-1)) setGuestErrno(guest, errno);
            jit.Regs()[0] = uint32_t(result);
        }
    });
    manager.RegisterThunk("mbrtowc", [](Jit& jit, Host& guest) {
        const auto& args = jit.Regs();
        auto* output = args[0] ? span<wchar_t>(guest, args[0], 1) : nullptr;
        const size_t count = args[1] ? std::min<size_t>(args[2], MB_CUR_MAX) : 0;
        const char* input = args[1] ? string<char>(guest, args[1], count) : nullptr;
        if (guest.HasFailed()) return;
        jit.Regs()[0] = convertMultibyte(guest, args[3], [&](mbstate_t* state) {
            return std::mbrtowc(output, input, count, state);
        });
    });
    manager.RegisterThunk("wcrtomb", [](Jit& jit, Host& guest) {
        const auto& args = jit.Regs();
        const uint32_t address = args[0];
        char buffer[MB_LEN_MAX]{};
        jit.Regs()[0] = convertMultibyte(guest, args[2], [&](mbstate_t* state) {
            const size_t result = std::wcrtomb(address ? buffer : nullptr, wchar_t(args[1]), state);
            if (address && result != size_t(-1)) {
                if (auto* output = span<char>(guest, address, result)) std::memcpy(output, buffer, result);
            }
            return result;
        });
    });
    manager.RegisterThunk("wcschr", [](Jit& jit, Host& guest) {
        if (const auto* value = string<wchar_t>(guest, jit.Regs()[0]))
            jit.Regs()[0] = guestPointer(guest, std::wcschr(value, wchar_t(jit.Regs()[1])));
    });
    manager.RegisterThunk("wcsncmp", [](Jit& jit, Host& guest) {
        const auto count = jit.Regs()[2];
        const auto* first = string<wchar_t>(guest, jit.Regs()[0], count);
        const auto* second = string<wchar_t>(guest, jit.Regs()[1], count);
        if (first && second) jit.Regs()[0] = std::wcsncmp(first, second, count);
    });
    manager.RegisterThunk("wcsncpy", [](Jit& jit, Host& guest) {
        const auto count = jit.Regs()[2];
        auto* destination = span<wchar_t>(guest, jit.Regs()[0], count);
        const auto* source = string<wchar_t>(guest, jit.Regs()[1], count);
        if (destination && source) std::wcsncpy(destination, source, count);
    });
    // Packed resource strings can start at byte-aligned offsets. Bionic's
    // wide copy is a byte copy; do not impose wchar_t alignment on this path.
    for (auto [name, function] : {std::pair{"wmemcpy", &std::memcpy}, {"wmemmove", &std::memmove}}) {
        manager.RegisterThunk(name, [function](Jit& jit, Host& guest) {
            const auto count = uint64_t(jit.Regs()[2])*4;
            if (!count) return;
            auto* destination = span<char>(guest, jit.Regs()[0], count);
            const auto* source = span<char>(guest, jit.Regs()[1], count);
            if (destination && source) function(destination, source, count);
        });
    }
    manager.RegisterThunk("wmemcmp", [](Jit& jit, Host& guest) {
        const auto count = jit.Regs()[2];
        const auto* first = span<wchar_t>(guest, jit.Regs()[0], count);
        const auto* second = span<wchar_t>(guest, jit.Regs()[1], count);
        if (first && second) jit.Regs()[0] = std::wmemcmp(first, second, count);
    });
    manager.RegisterThunk("wmemchr", [](Jit& jit, Host& guest) {
        const auto count = jit.Regs()[2];
        if (const auto* value = span<wchar_t>(guest, jit.Regs()[0], count))
            jit.Regs()[0] = guestPointer(guest, std::wmemchr(value, wchar_t(jit.Regs()[1]), count));
    });
    manager.RegisterThunk("wmemset", [](Jit& jit, Host& guest) {
        const auto count = jit.Regs()[2];
        if (auto* value = span<wchar_t>(guest, jit.Regs()[0], count))
            std::wmemset(value, wchar_t(jit.Regs()[1]), count);
    });
}

bool checkAsterLibc(Host& host) {
    auto call = [&](const char* name, std::vector<uint32_t> args) {
        return host.RunFunction(host.GetThunkManager().ResolveSymbol(name, STT_FUNC), args);
    };
    const auto first=host.GuestAlloc(128),second=host.GuestAlloc(128);
    if (!first || !second) return false;
    const auto sign=[](int32_t value){return (value>0)-(value<0);};
    for (const auto pair : {std::pair{"PeaShooter","peashooter"},{"a","aa"},{"z","A"},{"植物A","植物a"},{"",""}}) {
        memcpy(host.GetGuestMemoryBase()+first,pair.first,strlen(pair.first)+1);
        memcpy(host.GetGuestMemoryBase()+second,pair.second,strlen(pair.second)+1);
        if (sign(call("strcmp",{first,second}))!=sign(::strcmp(pair.first,pair.second))
            || sign(call("strcasecmp",{first,second}))!=sign(::strcasecmp(pair.first,pair.second))) return false;
    }
    host.GuestFree(first);host.GuestFree(second);
    constexpr wchar_t sample[] = L"植物大战";
    const auto source = host.GuestAlloc(sizeof(sample)+1);
    const auto destination = host.GuestAlloc(sizeof(sample));
    const auto className = host.GuestAlloc(sizeof("space"));
    const auto state = host.GuestAlloc(guestMbStateSize + 4);
    const auto bytes = host.GuestAlloc(MB_LEN_MAX);
    constexpr std::array returnHighWord{0xe92d4010u, 0xe12fff32u, 0xe1a00001u, 0xe8bd8010u};
    // push {r4,lr}; blx r2; mov r0,r1; pop {r4,pc}
    const auto trampoline = host.GuestAlloc(sizeof(returnHighWord));
    if (!source || !destination || !className || !trampoline || !state || !bytes) return false;
    std::memcpy(span<wchar_t>(host, source, std::size(sample)), sample, sizeof(sample));
    std::memcpy(span<char>(host, className, sizeof("space")), "space", sizeof("space"));
    std::memcpy(span<uint32_t>(host, trampoline, returnHighWord.size()), returnHighWord.data(), sizeof(returnHighWord));
    host.AddExecutableRange(trampoline, sizeof(returnHighWord));
    host.MemoryWrite32(state, 0);
    host.MemoryWrite32(state + guestMbStateSize, 0xfeed1234);
    const uint32_t descriptor = call("wctype", {className});
    const uint32_t roundAddress = host.GetThunkManager().ResolveSymbol("round", STT_FUNC);
    const auto input = std::bit_cast<uint64_t>(-2.5);
    const auto expected = std::bit_cast<uint64_t>(-3.0);
    const auto aligned = call("memalign", {128, 31});
    const auto unaligned=host.GuestAlloc(sizeof(sample)+1);
    if (!unaligned) return false;
    memcpy(host.GetGuestMemoryBase()+unaligned+1,sample,sizeof(sample));
    return call("wmemcpy", {destination, unaligned+1, std::size(sample)}) == destination
        && memcmp(host.GetGuestMemoryBase()+destination,sample,sizeof(sample))==0
        && call("wmemmove", {unaligned+1,destination,std::size(sample)})==unaligned+1
        && memcmp(host.GetGuestMemoryBase()+unaligned+1,sample,sizeof(sample))==0
        && call("wmemcpy", {destination, source, std::size(sample)}) == destination
        && call("wmemcmp", {destination, source, std::size(sample)}) == 0
        && call("wcschr", {destination, L'大'}) == destination + 8
        && descriptor && call("iswctype", {' ', descriptor}) && !call("iswctype", {'x', descriptor})
        && call("sqrtf", {std::bit_cast<uint32_t>(81.f)}) == std::bit_cast<uint32_t>(9.f)
        && call("roundf", {std::bit_cast<uint32_t>(-2.5f)}) == std::bit_cast<uint32_t>(-3.f)
        && call("round", {uint32_t(input), uint32_t(input >> 32)}) == uint32_t(expected)
        && host.RunFunction(trampoline, {uint32_t(input), uint32_t(input >> 32), roundAddress}) == uint32_t(expected >> 32)
        && aligned && aligned % 128 == 0
        && call("wcrtomb", {bytes, L'A', state}) == 1
        && call("mbrtowc", {destination, bytes, 1, state}) == 1
        && host.MemoryRead32(destination) == 'A'
        && host.MemoryRead32(state + guestMbStateSize) == 0xfeed1234
        && !host.HasFailed();
}

bool checkAsterThreads(Host& host) {
    auto call=[&](const char* name,std::vector<uint32_t> args){return host.RunFunction(host.GetThunkManager().ResolveSymbol(name,STT_FUNC),args);};
    const auto entry=host.GuestAlloc(8),attribute=host.GuestAlloc(24),thread=host.GuestAlloc(4),result=host.GuestAlloc(4);
    if (!entry || !attribute || !thread || !result) return false;
    host.MemoryWrite32(entry,0xe3a0002a);host.MemoryWrite32(entry+4,0xe12fff1e);
    host.AddExecutableRange(entry,8);
    if (call("pthread_attr_init",{attribute})) return false;
    const auto launch=[&](){return call("pthread_create",{thread,attribute,entry,0})==0
        && call("pthread_join",{host.MemoryRead32(thread),result})==0 && host.MemoryRead32(result)==42;};
    const bool small=call("pthread_attr_setstacksize",{attribute,65536})==0 && launch();
    const bool realtime=call("pthread_attr_setstacksize",{attribute,32768})==0
        && call("pthread_attr_setschedpolicy",{attribute,SCHED_FIFO})==0
        && (host.MemoryWrite32(result,99),call("pthread_attr_setschedparam",{attribute,result})==0) && launch();
    const bool oversized=call("pthread_attr_setstacksize",{attribute,2*1024*1024})==0
        && call("pthread_create",{thread,attribute,entry,0})==ENOTSUP;
    call("pthread_attr_destroy",{attribute});
    for(auto pointer:{entry,attribute,thread,result})host.GuestFree(pointer);
    __android_log_print(ANDROID_LOG_INFO,"AsterArm64Probe","Thread stack/scheduling check small=%d realtime=%d oversized_rejected=%d",small,realtime,oversized);
    return small && realtime && oversized && !host.HasFailed();
}

bool checkAsterPosix(Host& host) {
    auto call = [&](const char* name, std::vector<uint32_t> args) {
        return host.RunFunction(host.GetThunkManager().ResolveSymbol(name, STT_FUNC), args);
    };
    const auto position = host.GuestAlloc(8);
    const auto semaphore = host.GuestAlloc(4);
    const auto deadline = host.GuestAlloc(8);
    if (!position || !semaphore || !deadline) return false;
    host.MemoryWrite32(position, 0);
    // A32 fpos_t is four bytes. The following word must not become part of the offset.
    host.MemoryWrite32(position + 4, 0x12345678);
    const uint32_t file = call("tmpfile", {});
    if (!file) {
        __android_log_print(ANDROID_LOG_ERROR, "AsterArm64Probe", "tmpfile failed errno=%u", host.MemoryRead32(host.GuestErrnoAddress()));
        return false;
    }
    const bool filePassed = call("__swbuf", {'A', file}) == 'A'
        && call("ftello", {file}) == 1 && call("fileno", {file}) != UINT32_MAX
        && call("fseeko", {file,0,SEEK_SET}) == 0
        && call("fsetpos", {file, position}) == 0
        && call("__srget", {file}) == 'A'
        && call("ferror", {file}) == 0;
    const bool closed = call("fclose", {file}) == 0;
    if (call("sem_init", {semaphore, 0, 1}) != 0) return false;
    host.MemoryWrite32(deadline, 0);
    host.MemoryWrite32(deadline + 4, 0);
    const bool waited = call("sem_timedwait", {semaphore, deadline}) == 0
        && call("sem_timedwait", {semaphore, deadline}) == UINT32_MAX
        && host.MemoryRead32(host.GuestErrnoAddress()) == ETIMEDOUT;
    const bool destroyed = call("sem_destroy", {semaphore}) == 0;
    constexpr wchar_t wideFormat[] = L"%ls:%08x:%.1f";
    constexpr wchar_t wideSource[] = L"植物大战";
    constexpr wchar_t expected[] = L"植物大战:0000002a:1.5";
    const auto format = host.GuestAlloc(sizeof(wideFormat));
    const auto source = host.GuestAlloc(128);
    const auto arguments = host.GuestAlloc(16);
    const auto output = host.GuestAlloc(1024);
    if (!format || !source || !arguments || !output) return false;
    memcpy(span<wchar_t>(host, format, std::size(wideFormat)), wideFormat, sizeof(wideFormat));
    memcpy(span<wchar_t>(host, source, std::size(wideSource)), wideSource, sizeof(wideSource));
    host.MemoryWrite32(arguments, source);
    host.MemoryWrite32(arguments + 4, 0x2a);
    host.MemoryWrite64(arguments + 8, std::bit_cast<uint64_t>(1.5));
    const bool widePassed = call("vswprintf", {output, 256, format, arguments}) == std::size(expected) - 1
        && std::memcmp(span<wchar_t>(host, output, std::size(expected)), expected, sizeof(expected)) == 0;
    constexpr wchar_t scanSource[] = L"123 -7";
    constexpr wchar_t scanFormat[] = L"%ld %d";
    memcpy(span<wchar_t>(host, source, std::size(scanSource)), scanSource, sizeof(scanSource));
    memcpy(span<wchar_t>(host, format, std::size(scanFormat)), scanFormat, sizeof(scanFormat));
    host.MemoryWrite32(output + 4, 0x11223344);
    const bool scanPassed = call("swscanf", {source, format, output, output + 8}) == 2
        && host.MemoryRead32(output) == 123 && host.MemoryRead32(output + 8) == uint32_t(-7)
        && host.MemoryRead32(output + 4) == 0x11223344;
    constexpr char narrowFormat[]="%s:%08x:%.1f", narrowSource[]="植物", narrowExpected[]="植物:0000002a:1.5";
    memcpy(span<char>(host,format,sizeof(narrowFormat)),narrowFormat,sizeof(narrowFormat));
    memcpy(span<char>(host,source,sizeof(narrowSource)),narrowSource,sizeof(narrowSource));
    host.MemoryWrite32(arguments,source);host.MemoryWrite32(arguments+4,0x2a);
    host.MemoryWrite64(arguments+8,std::bit_cast<uint64_t>(1.5));
    host.MemoryWrite32(output+4,0x11223344);
    const bool narrowPassed=call("vasprintf",{output,format,arguments})==sizeof(narrowExpected)-1
        && host.MemoryRead32(output+4)==0x11223344
        && strcmp(string<char>(host,host.MemoryRead32(output)),narrowExpected)==0;
    call("free",{host.MemoryRead32(output)});
    memcpy(span<char>(host,source,7),"123 -7",7);
    memcpy(span<char>(host,format,7),"%ld %d",7);
    host.MemoryWrite32(arguments,output);host.MemoryWrite32(arguments+4,output+8);
    const bool narrowScan=call("vsscanf",{source,format,arguments})==2
        && host.MemoryRead32(output)==123 && host.MemoryRead32(output+8)==uint32_t(-7)
        && host.MemoryRead32(output+4)==0x11223344;
    __android_log_print(ANDROID_LOG_INFO, "AsterArm64Probe",
        "POSIX file=%d close=%d sem-timeout=%d destroy=%d wide-format=%d wide-scan=%d varargs-format=%d varargs-scan=%d",
        filePassed, closed, waited, destroyed, widePassed, scanPassed,narrowPassed,narrowScan);
    return filePassed && closed && waited && destroyed && widePassed && scanPassed && narrowPassed && narrowScan && !host.HasFailed();
}

bool checkAsterLocale(Host& host) {
    auto call = [&](const char* name, std::vector<uint32_t> args) {
        return host.RunFunction(host.GetThunkManager().ResolveSymbol(name, STT_FUNC), args);
    };
    const auto buffer = host.GuestAlloc(2048);
    if (!buffer) return false;
    const auto name = buffer, input = buffer+64, output=buffer+256, end=buffer+768;
    const auto state=buffer+800, sourcePointer=buffer+816, allocated=buffer+832;
    memcpy(span<char>(host,name,8), "C.UTF-8", 8);
    const uint32_t locale = call("newlocale",{LC_ALL_MASK,name,0});
    if (!locale) return false;
    const auto previous = call("uselocale",{locale});
    const bool selected = previous == UINT32_MAX && call("uselocale",{0}) == locale
        && call("iswalpha_l",{L'植',locale}) && call("towlower_l",{L'A',locale}) == L'a';
    constexpr char utf8[] = "植物";
    memcpy(span<char>(host,input,sizeof(utf8)),utf8,sizeof(utf8));
    host.MemoryWrite32(sourcePointer,input);
    host.MemoryWrite32(state,0);
    host.MemoryWrite32(state+4,0xfeedcafe);
    const bool decoded = call("mbsnrtowcs",{output,sourcePointer,3,8,state}) == 1
        && host.MemoryRead32(output) == L'植' && host.MemoryRead32(sourcePointer) == input+3
        && call("mbsrtowcs",{output+4,sourcePointer,8,state}) == 1
        && host.MemoryRead32(output+4) == L'物' && host.MemoryRead32(sourcePointer) == 0;
    host.MemoryWrite32(sourcePointer,output);
    const bool encoded = call("wcsnrtombs",{input+32,sourcePointer,3,32,state}) == 6
        && host.MemoryRead32(sourcePointer) == 0
        && memcmp(span<char>(host,input+32,sizeof(utf8)),utf8,sizeof(utf8)) == 0
        && host.MemoryRead32(state+4) == 0xfeedcafe;
    constexpr wchar_t number[] = L"4294967295!";
    memcpy(span<wchar_t>(host,input,std::size(number)),number,sizeof(number));
    host.MemoryWrite32(end+4,0x12345678);
    const bool wideNumber = call("wcstoul",{input,end,10}) == UINT32_MAX
        && host.MemoryRead32(end) == input+40 && host.MemoryRead32(end+4)==0x12345678;
    constexpr char large[] = "18446744073709551615!";
    memcpy(span<char>(host,input,sizeof(large)),large,sizeof(large));
    constexpr std::array highCode{0xe92d4010u,0xe12fff33u,0xe1a00001u,0xe8bd8010u};
    const auto trampoline=host.GuestAlloc(sizeof(highCode));
    memcpy(span<uint32_t>(host,trampoline,highCode.size()),highCode.data(),sizeof(highCode));
    host.AddExecutableRange(trampoline,sizeof(highCode));
    const auto convert=host.GetThunkManager().ResolveSymbol("strtoull",STT_FUNC);
    const bool integer = call("strtoull",{input,end,10})==UINT32_MAX
        && host.RunFunction(trampoline,{input,end,10,convert})==UINT32_MAX
        && host.MemoryRead32(end)==input+20 && host.MemoryRead32(end+4)==0x12345678;
    memcpy(span<char>(host,input,5),"1.5!",5);
    const auto doubleConvert=host.GetThunkManager().ResolveSymbol("strtold",STT_FUNC);
    const bool floating = call("strtold",{input,end})==0
        && host.RunFunction(trampoline,{input,end,0,doubleConvert})==0x3ff80000
        && host.MemoryRead32(end)==input+3;
    host.MemoryWrite32(allocated,0x11223344);
    const bool alignment = call("posix_memalign",{allocated,3,13})==EINVAL
        && host.MemoryRead32(allocated)==0x11223344
        && call("posix_memalign",{allocated,128,13})==0
        && host.MemoryRead32(allocated)%128==0;
    const auto conventions=call("localeconv",{});
    const bool convention = conventions && call("localeconv",{})==conventions
        && strcmp(string<char>(host,host.MemoryRead32(conventions)),".")==0;
    const auto old=call("uselocale",{UINT32_MAX});
    call("freelocale",{locale});
    const bool restored=old==locale && call("uselocale",{0})==UINT32_MAX;
    __android_log_print(ANDROID_LOG_INFO,"AsterArm64Probe",
        "Locale select=%d utf8-decode=%d encode=%d wide32=%d integer64=%d float64=%d align=%d lconv=%d restore=%d",
        selected,decoded,encoded,wideNumber,integer,floating,alignment,convention,restored);
    return selected && decoded && encoded && wideNumber && integer && floating && alignment && convention && restored && !host.HasFailed();
}

bool checkAsterMemory(Host& host) {
    auto call = [&](const char* name, std::vector<uint32_t> args) {
        return host.RunFunction(host.GetThunkManager().ResolveSymbol(name, STT_FUNC), args);
    };
    const uint32_t page = uint32_t(sysconf(_SC_PAGESIZE));
    const uint32_t address = call("mmap", {0, page * 2, PROT_READ | PROT_WRITE | PROT_EXEC,
                                         MAP_PRIVATE | MAP_ANONYMOUS, UINT32_MAX, 0});
    if (address == UINT32_MAX) return false;
    host.MemoryWrite32(address, 0xe3a00007); // mov r0,#7
    host.MemoryWrite32(address + 4, 0xe12fff1e); // bx lr
    constexpr std::array clearCache{0xe92d4080u,0xe3007002u,0xe340700fu,0xef000000u,0xe8bd8080u};
    // push {r7,lr}; movw r7,#2; movt r7,#15; svc #0; pop {r7,pc}
    const auto flush = host.GuestAlloc(sizeof(clearCache));
    memcpy(span<uint32_t>(host,flush,clearCache.size()),clearCache.data(),sizeof(clearCache));
    host.AddExecutableRange(flush,sizeof(clearCache));
    bool syscall = host.RunFunction(address,{}) == 7;
    host.MemoryWrite32(address,0xe3a00008);
    syscall = host.RunFunction(flush,{address,address+8,0})==0 && host.RunFunction(address,{})==8 && syscall;
    syscall = host.RunFunction(flush,{address,address+8,1})==uint32_t(-EINVAL) && syscall;
    host.MemoryWrite32(address,0xe3a00007);
    bool result = call("mprotect", {address, page, PROT_READ | PROT_EXEC}) == 0
        && host.RunFunction(address, {}) == 7;
    result = call("mprotect", {address, page, PROT_READ | PROT_WRITE}) == 0 && result;
    host.MemoryWrite32(address, 0xe3a00009);
    result = call("mprotect", {address, page, PROT_READ | PROT_EXEC}) == 0
        && host.RunFunction(address, {}) == 9 && result;
    result = call("munmap", {address, page}) == 0 && result;
    result = call("mprotect", {address, page, PROT_READ}) == UINT32_MAX
        && host.MemoryRead32(host.GuestErrnoAddress()) == ENOMEM && result;
    result = call("munmap", {address + page, page}) == 0 && result;
    __android_log_print(ANDROID_LOG_INFO, "AsterArm64Probe", "Mapping execution/cache/partial-unmap=%d ARM-cacheflush=%d", result,syscall);
    return result && syscall && !host.HasFailed();
}
