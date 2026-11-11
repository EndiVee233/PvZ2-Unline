// Shared ARM32 engine patch, also carried unchanged by the ARM64 bridge.
// Persist only the native player ID; never rewrite or reorder player saves.
using U = unsigned;
using P = void*;
template<class T, class... A> static T engine(U b, U offset, A... args) {
    return reinterpret_cast<T(*)(A...)>(b + offset)(args...);
}
template<class T, class... A> static T imported(U b, U got, A... args) {
    return reinterpret_cast<T(*)(A...)>(*reinterpret_cast<U*>(b + got))(args...);
}
static const char path[] = "/data/data/com.pvz2unline.aster/files/userdataNo_Backup/last-player.bin";
static const char temporary[] = "/data/data/com.pvz2unline.aster/files/userdataNo_Backup/last-player.tmp";
static constexpr U magic = 0x314c5055; // UPL1, fixed 12-byte record.
static void notice(U b, const char* message) {
    imported<int>(b, 0x1822b98, 4, "AsterPlayerMemory", "%s", message);
}
extern "C" void rememberPlayer(U b, P manager) {
    const U id = *reinterpret_cast<U*>(reinterpret_cast<U>(manager) + 0x74);
    const U data[3] = {magic, id, ~id};
    int fd = imported<int>(b, 0x1822ebc, temporary, 0x241, 0600); // WRONLY|CREAT|TRUNC
    if (fd < 0) { notice(b, "Selection write deferred"); return; }
    bool ok = imported<int>(b, 0x1822f40, fd, data, 12u) == 12;
    if (ok) ok = imported<int>(b, 0x1822f44, fd) == 0;
    if (imported<int>(b, 0x1822bd4, fd) != 0) ok = false;
    if (ok) ok = imported<int>(b, 0x1822cc8, temporary, path) == 0;
    if (!ok) imported<int>(b, 0x1822ccc, temporary);
    notice(b, ok ? "Selection remembered" : "Selection write deferred");
}
extern "C" U restorePlayer(U b, P manager) {
    int fd = imported<int>(b, 0x1822ebc, path, 0, 0);
    if (fd < 0) return 0;
    U data[3] = {};
    int size = imported<int>(b, 0x1822ec4, fd, data, 12u);
    char extra;
    int tail = size == 12 ? imported<int>(b, 0x1822ec4, fd, &extra, 1u) : -1;
    imported<int>(b, 0x1822bd4, fd);
    if (size != 12 || tail != 0 || data[0] != magic || data[2] != ~data[1]) return 0;
    U weak[2] = {};
    // Original FindById returns a native weak reference in its first argument.
    engine<P>(b, 0x7aab68, weak, manager, data[1]);
    P player = nullptr;
    if (weak[0] || weak[1]) {
        P registry = engine<P>(b, 0x11d74b4);
        player = engine<P>(b, 0x1da034, registry, weak);
    }
    bool valid = player && *reinterpret_cast<U*>(reinterpret_cast<U>(player) + 0x1ec) == data[1];
    engine<void>(b, 0x1d9bb4, weak, 0u, 0u, 0u);
    if (!valid) { notice(b, "Remembered player unavailable; using original fallback"); return 0; }
    *reinterpret_cast<U*>(reinterpret_cast<U>(manager) + 0x74) = data[1];
    notice(b, "Last player restored");
    return 1;
}
