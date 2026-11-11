// SPDX-License-Identifier: GPL-3.0-or-later
#include "aster_zlib.h"
#include "dynarmic_host.h"
#include "thunk_manager.h"

#include <cstring>
#include <elf.h>
#include <memory>
#include <mutex>
#include <unordered_map>
#include <zlib.h>

namespace {
using Jit = Dynarmic::A32::Jit;
using Host = DynarmicHost;

struct Stream32 {
    uint32_t nextIn, availableIn, totalIn;
    uint32_t nextOut, availableOut, totalOut;
    uint32_t message, state, alloc, free, opaque;
    int32_t dataType;
    uint32_t adler, reserved;
};
static_assert(sizeof(Stream32) == 56);

template<class T = Bytef>
T* guest(Host& host, uint32_t address, size_t size) {
    if (!address || size > host.GetGuestMemorySize() - address) return nullptr;
    return reinterpret_cast<T*>(host.GetGuestMemoryBase() + address);
}

struct Stream {
    z_stream native{};
    bool compression;
    uint32_t message = 0;

    explicit Stream(bool isCompression) : compression(isCompression) {}
    ~Stream() {
        if (native.state) {
            if (compression) deflateEnd(&native);
            else inflateEnd(&native);
        }
    }

    void sync(Host& host, Stream32& stream) {
        stream.totalIn = uint32_t(native.total_in);
        stream.totalOut = uint32_t(native.total_out);
        stream.dataType = native.data_type;
        stream.adler = uint32_t(native.adler);
        stream.message = 0;
        if (!native.msg) return;
        const size_t size = std::strlen(native.msg) + 1;
        if (size > 128) return;
        if (!message) message = host.GuestAlloc(128);
        if (message) {
            std::memcpy(guest(host, message, size), native.msg, size);
            stream.message = message;
        }
    }
};

struct Streams {
    std::mutex mutex;
    std::unordered_map<uint32_t, std::unique_ptr<Stream>> items;
};

enum class Init { Deflate, Deflate2, Inflate, Inflate2 };
enum class Op { Run, End, Reset };

int initialize(Host& host, Jit& jit, Streams& streams, Init kind) {
    const auto& args = jit.Regs();
    const uint32_t address = args[0];
    auto* stream = guest<Stream32>(host, address, sizeof(Stream32));
    if (!stream || address % alignof(Stream32) || stream->alloc || stream->free) return Z_STREAM_ERROR;

    uint32_t version, size;
    switch (kind) {
    case Init::Deflate: version = args[2]; size = args[3]; break;
    case Init::Deflate2: version = host.ReadStackWord(jit, 2); size = host.ReadStackWord(jit, 3); break;
    case Init::Inflate: version = args[1]; size = args[2]; break;
    case Init::Inflate2: version = args[2]; size = args[3]; break;
    }
    const auto* major = guest<char>(host, version, 1);
    if (!major || *major != ZLIB_VERSION[0] || size != sizeof(Stream32)) return Z_VERSION_ERROR;

    std::lock_guard lock(streams.mutex);
    if (streams.items.contains(address)) return Z_STREAM_ERROR;
    const bool compressing = kind == Init::Deflate || kind == Init::Deflate2;
    auto state = std::make_unique<Stream>(compressing);
    int status;
    switch (kind) {
    case Init::Deflate:
        status = deflateInit(&state->native, int32_t(args[1])); break;
    case Init::Deflate2:
        status = deflateInit2(&state->native, int32_t(args[1]), int32_t(args[2]), int32_t(args[3]),
                              int32_t(host.ReadStackWord(jit, 0)), int32_t(host.ReadStackWord(jit, 1)));
        break;
    case Init::Inflate:
        status = inflateInit(&state->native); break;
    case Init::Inflate2:
        status = inflateInit2(&state->native, int32_t(args[1])); break;
    }
    state->sync(host, *stream);
    if (status == Z_OK) {
        // The guest treats zlib's internal state as opaque.
        stream->state = address;
        streams.items.emplace(address, std::move(state));
    } else if (state->message) {
        // The failed init has no live state from which to reclaim the message.
        host.GuestFree(state->message);
        stream->message = 0;
    }
    return status;
}

int operate(Host& host, Jit& jit, Streams& streams, bool compression, Op operation) {
    const uint32_t address = jit.Regs()[0];
    auto* stream = guest<Stream32>(host, address, sizeof(Stream32));
    if (!stream || address % alignof(Stream32) || stream->state != address) return Z_STREAM_ERROR;
    std::lock_guard lock(streams.mutex);
    auto it = streams.items.find(address);
    if (it == streams.items.end() || it->second->compression != compression) return Z_STREAM_ERROR;
    auto& state = *it->second;
    z_stream& native = state.native;
    int status;
    if (operation == Op::Run) {
        native.next_in = guest(host, stream->nextIn, stream->availableIn);
        native.next_out = guest(host, stream->nextOut, stream->availableOut);
        if ((!native.next_in && (stream->nextIn || stream->availableIn)) || !native.next_out)
            return Z_STREAM_ERROR;
        native.avail_in = stream->availableIn;
        native.avail_out = stream->availableOut;
        const int flush = int32_t(jit.Regs()[1]);
        status = compression ? deflate(&native, flush) : inflate(&native, flush);
        stream->nextIn += stream->availableIn - native.avail_in;
        stream->nextOut += stream->availableOut - native.avail_out;
        stream->availableIn = native.avail_in;
        stream->availableOut = native.avail_out;
    } else if (operation == Op::Reset) {
        status = compression ? deflateReset(&native) : inflateReset(&native);
    } else {
        status = compression ? deflateEnd(&native) : inflateEnd(&native);
        stream->state = 0;
        stream->message = 0;
        if (state.message) host.GuestFree(state.message);
        streams.items.erase(it);
        return status;
    }
    state.sync(host, *stream);
    return status;
}

int transfer(Host& host, Jit& jit, bool compression, bool explicitLevel) {
    const auto& args = jit.Regs();
    if (args[1] % alignof(uint32_t) || !guest(host, args[1], sizeof(uint32_t))) return Z_STREAM_ERROR;
    uLongf length = host.MemoryRead32(args[1]);
    Bytef* destination = guest(host, args[0], length);
    const Bytef* source = guest(host, args[2], args[3]);
    if (!destination || !source) return Z_STREAM_ERROR;
    const int status = compression
        ? compress2(destination, &length, source, args[3],
                    explicitLevel ? int32_t(host.ReadStackWord(jit, 0)) : Z_DEFAULT_COMPRESSION)
        : uncompress(destination, &length, source, args[3]);
    host.MemoryWrite32(args[1], uint32_t(length));
    return status;
}
}

void registerAsterZlib(Host& host) {
    auto& manager = host.GetThunkManager();
    auto streams = std::make_shared<Streams>();
    for (auto [name, kind] : {std::pair{"deflateInit_", Init::Deflate}, {"deflateInit2_", Init::Deflate2},
                              {"inflateInit_", Init::Inflate}, {"inflateInit2_", Init::Inflate2}}) {
        manager.RegisterThunk(name, [streams, kind](Jit& jit, Host& guestHost) {
            jit.Regs()[0] = uint32_t(initialize(guestHost, jit, *streams, kind));
        });
    }
    for (auto [name, compression, operation] : {
             std::tuple{"deflate", true, Op::Run}, {"deflateEnd", true, Op::End}, {"deflateReset", true, Op::Reset},
             {"inflate", false, Op::Run}, {"inflateEnd", false, Op::End}, {"inflateReset", false, Op::Reset}}) {
        manager.RegisterThunk(name, [streams, compression, operation](Jit& jit, Host& guestHost) {
            jit.Regs()[0] = uint32_t(operate(guestHost, jit, *streams, compression, operation));
        });
    }
    for (auto [name, compression, explicitLevel] : {
             std::tuple{"compress", true, false}, {"compress2", true, true}, {"uncompress", false, false}}) {
        manager.RegisterThunk(name, [compression, explicitLevel](Jit& jit, Host& guestHost) {
            jit.Regs()[0] = uint32_t(transfer(guestHost, jit, compression, explicitLevel));
        });
    }
    for (auto [name, checksum] : {std::pair{"crc32", &crc32}, {"adler32", &adler32}}) {
        manager.RegisterThunk(name, [checksum](Jit& jit, Host& guestHost) {
            auto& args = jit.Regs();
            const Bytef* data = guest(guestHost, args[1], args[2]);
            if (!data && args[1]) {
                guestHost.Fail("zlib checksum range is outside guest memory");
                return;
            }
            args[0] = uint32_t(checksum(args[0], data, args[2]));
        });
    }
}

bool checkAsterZlib(Host& host) {
    constexpr char sample[] = "Aster resource stream";
    const uint32_t source = host.GuestAlloc(sizeof(sample));
    const uint32_t packed = host.GuestAlloc(128);
    const uint32_t result = host.GuestAlloc(128);
    const uint32_t version = host.GuestAlloc(1);
    const uint32_t streamAddress = host.GuestAlloc(sizeof(Stream32));
    const uint32_t length = host.GuestAlloc(sizeof(uint32_t));
    if (!source || !packed || !result || !version || !streamAddress || !length) return false;
    std::memcpy(guest(host, source, sizeof(sample)), sample, sizeof(sample));
    host.MemoryWrite8(version, ZLIB_VERSION[0]);
    auto* stream = guest<Stream32>(host, streamAddress, sizeof(Stream32));
    *stream = {};
    auto call = [&](const char* name, std::vector<uint32_t> args) {
        return int32_t(host.RunFunction(host.GetThunkManager().ResolveSymbol(name, STT_FUNC), args));
    };

    if (call("deflateInit2_", {streamAddress, 6, Z_DEFLATED, MAX_WBITS, 8, Z_DEFAULT_STRATEGY,
                               version, sizeof(Stream32)}) != Z_OK) return false;
    stream->nextIn = source;
    stream->availableIn = sizeof(sample);
    stream->nextOut = packed;
    stream->availableOut = 128;
    if (call("deflate", {streamAddress, Z_FINISH}) != Z_STREAM_END || stream->availableIn != 0
        || stream->nextIn != source + sizeof(sample) || !stream->totalOut) return false;
    const uint32_t packedSize = stream->totalOut;
    if (call("deflateReset", {streamAddress}) != Z_OK || stream->totalOut != 0
        || call("deflateEnd", {streamAddress}) != Z_OK || stream->state) return false;

    if (call("inflateInit_", {streamAddress, version, sizeof(Stream32)}) != Z_OK) return false;
    stream->nextIn = packed;
    stream->availableIn = packedSize;
    stream->nextOut = result;
    stream->availableOut = 128;
    if (call("inflate", {streamAddress, Z_FINISH}) != Z_STREAM_END || stream->totalOut != sizeof(sample)
        || std::memcmp(guest(host, result, sizeof(sample)), sample, sizeof(sample))
        || call("inflateEnd", {streamAddress}) != Z_OK) return false;

    host.MemoryWrite32(length, 128);
    if (call("compress2", {packed, length, source, sizeof(sample), 6}) != Z_OK) return false;
    const uint32_t compressed = host.MemoryRead32(length);
    host.MemoryWrite32(length, 128);
    return call("uncompress", {result, length, packed, compressed}) == Z_OK
        && host.MemoryRead32(length) == sizeof(sample)
        && std::memcmp(guest(host, result, sizeof(sample)), sample, sizeof(sample)) == 0
        && uint32_t(call("crc32", {0, source, sizeof(sample)})) == crc32(0, guest(host, source, sizeof(sample)), sizeof(sample))
        && !host.HasFailed();
}
