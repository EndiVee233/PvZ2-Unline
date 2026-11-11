// SPDX-License-Identifier: GPL-3.0-or-later
// Included inside RegisterLibcThunks so file mappings share the fd registry.
for (const char* name : {"__aeabi_memcpy", "__aeabi_memcpy4", "__aeabi_memcpy8"}) {
    RegisterThunk(name, [](Jit& jit, Host& host) {
        const auto size = jit.Regs()[2];
        memcpy(Span(host, jit.Regs()[0], size), Span(host, jit.Regs()[1], size), size);
    });
}
for (const char* name : {"__aeabi_memmove", "__aeabi_memmove4", "__aeabi_memmove8"}) {
    RegisterThunk(name, [](Jit& jit, Host& host) {
        const auto size = jit.Regs()[2];
        memmove(Span(host, jit.Regs()[0], size), Span(host, jit.Regs()[1], size), size);
    });
}
for (const char* name : {"__aeabi_memset", "__aeabi_memset4", "__aeabi_memset8"}) {
    RegisterThunk(name, [](Jit& jit, Host& host) {
        // AAPCS memset helpers take destination, size, value.
        memset(Span(host, jit.Regs()[0], jit.Regs()[1]), int(jit.Regs()[2]), jit.Regs()[1]);
    });
}
for (const char* name : {"__aeabi_memclr", "__aeabi_memclr4", "__aeabi_memclr8"}) {
    RegisterThunk(name, [](Jit& jit, Host& host) {
        memset(Span(host, jit.Regs()[0], jit.Regs()[1]), 0, jit.Regs()[1]);
    });
}
RegisterThunk("sigemptyset", [](Jit& jit, Host& host) {
    Span(host, jit.Regs()[0], 4);
    host.MemoryWrite32(jit.Regs()[0], 0);
    jit.Regs()[0] = 0;
});
struct Mappings {
    std::mutex mutex;
    std::map<uint32_t, uint64_t> ranges;

    bool covers(uint32_t address, uint64_t end) const {
        auto entry = ranges.upper_bound(address);
        if (entry == ranges.begin()) return false;
        --entry;
        uint64_t cursor = address;
        for (; entry != ranges.end() && entry->first <= cursor; ++entry) {
            cursor = std::max(cursor, entry->second);
            if (cursor >= end) return true;
        }
        return false;
    }

    void remove(uint32_t address, uint64_t end) {
        auto entry = ranges.lower_bound(address);
        if (entry != ranges.begin()) --entry;
        while (entry != ranges.end() && entry->first < end) {
            const uint32_t start = entry->first;
            const uint64_t limit = entry->second;
            if (limit <= address) { ++entry; continue; }
            entry = ranges.erase(entry);
            if (start < address) ranges.emplace(start, address);
            if (limit > end) { ranges.emplace(uint32_t(end), limit); break; }
        }
    }
};
const auto mappings = std::make_shared<Mappings>();
const uint64_t pageSize = uint64_t(sysconf(_SC_PAGESIZE));
RegisterThunk("mmap", [mappings, pageSize](Jit& jit, Host& host) {
    const auto requested = jit.Regs()[0];
    const auto length = jit.Regs()[1];
    const int protection = jit.Regs()[2], flags = jit.Regs()[3];
    const int fd = int32_t(host.ReadStackWord(jit, 0));
    const int64_t offset = int32_t(host.ReadStackWord(jit, 1));
    const uint64_t size = (uint64_t(length) + pageSize - 1) & ~(pageSize - 1);
    if (!length || size > UINT32_MAX || offset < 0 || uint64_t(offset) % pageSize ||
        (protection & ~(PROT_READ | PROT_WRITE | PROT_EXEC)) ||
        ((flags & MAP_TYPE) != MAP_PRIVATE && (flags & MAP_TYPE) != MAP_SHARED)) {
        Failure(jit, host, EINVAL);
        return;
    }
    std::lock_guard lock(mappings->mutex);
    uint32_t address = 0;
    if (flags & MAP_FIXED) {
        if (!requested || requested % pageSize ||
            !mappings->covers(requested, uint64_t(requested) + size)) {
            Failure(jit, host, ENOTSUP);
            return;
        }
        address = requested;
    } else {
        address = host.GuestAllocMapping(size, pageSize);
    }
    if (!address) { Failure(jit, host, ENOMEM); return; }
    const int hostProtection = (protection & ~PROT_EXEC) | ((protection & PROT_EXEC) ? PROT_READ : 0);
    auto virtualFd = (flags & MAP_ANONYMOUS) ? nullptr : LookupVirtualFd(fd);
    if (virtualFd && (flags & MAP_TYPE) == MAP_SHARED && (protection & PROT_WRITE)) {
        Failure(jit, host, ENOTSUP);
        return;
    }
    void* location = host.GetGuestMemoryBase() + address;
    void* result = nullptr;
    if (virtualFd) {
        result = ::mmap(location, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);
        if (result != MAP_FAILED) {
            // MAP_FIXED has already replaced these pages, even if reading the
            // virtual file fails below. Do not retain the old mapping record.
            mappings->remove(address, uint64_t(address) + size);
            std::lock_guard fileLock(virtualFd->mutex);
            size_t copied = 0;
            bool failed = false;
            while (copied < length) {
                const ssize_t count = AssetVfs::PRead(virtualFd->handle.get(),
                    static_cast<char*>(location) + copied, length - copied, offset + copied);
                if (count < 0) { failed = true; break; }
                if (!count) break;
                copied += count;
            }
            if (failed || ::mprotect(location, size, hostProtection)) {
                const int error = errno;
                ::mmap(location, size, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);
                Failure(jit, host, error);
                return;
            }
        }
    } else {
        result = ::mmap(location, size, hostProtection, flags | MAP_FIXED,
            (flags & MAP_ANONYMOUS) ? -1 : NativeFd(fd), offset);
    }
    if (result == MAP_FAILED) { Failure(jit, host, errno); return; }
    mappings->remove(address, uint64_t(address) + size);
    mappings->ranges.emplace(address, uint64_t(address) + size);
    if (protection & PROT_EXEC) host.AddExecutableRange(address, uint32_t(size));
    host.InvalidateGuestCode(address, size);
    jit.Regs()[0] = address;
});
RegisterThunk("mprotect", [mappings, pageSize](Jit& jit, Host& host) {
    const auto address = jit.Regs()[0], length = jit.Regs()[1];
    const int protection = jit.Regs()[2];
    const uint64_t size = (uint64_t(length) + pageSize - 1) & ~(pageSize - 1);
    if (!length || address % pageSize || uint64_t(address) + size > host.GetGuestMemorySize() ||
        (protection & ~(PROT_READ | PROT_WRITE | PROT_EXEC))) {
        Failure(jit, host, EINVAL);
        return;
    }
    std::lock_guard lock(mappings->mutex);
    if (!mappings->covers(address, uint64_t(address) + size) &&
        !asterGuestImageRange(host, address, uint64_t(address) + size, pageSize)) {
        Failure(jit, host, ENOMEM);
        return;
    }
    const int hostProtection = (protection & ~PROT_EXEC) | ((protection & PROT_EXEC) ? PROT_READ : 0);
    if (::mprotect(host.GetGuestMemoryBase() + address, size, hostProtection)) {
        Failure(jit, host, errno);
        return;
    }
    if (protection & PROT_EXEC) host.AddExecutableRange(address, uint32_t(size));
    host.InvalidateGuestCode(address, size);
    jit.Regs()[0] = 0;
});
RegisterThunk("munmap", [mappings, pageSize](Jit& jit, Host& host) {
    const auto address = jit.Regs()[0], length = jit.Regs()[1];
    const uint64_t size = (uint64_t(length) + pageSize - 1) & ~(pageSize - 1);
    if (!length || address % pageSize || uint64_t(address) + size > host.GetGuestMemorySize()) {
        Failure(jit, host, EINVAL);
        return;
    }
    std::lock_guard lock(mappings->mutex);
    if (!mappings->covers(address, uint64_t(address) + size)) {
        Failure(jit, host, EINVAL);
        return;
    }
    // Keep the containing guest address reservation, while discarding its pages.
    void* result = ::mmap(host.GetGuestMemoryBase() + address, size, PROT_NONE,
        MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);
    if (result == MAP_FAILED) { Failure(jit, host, errno); return; }
    mappings->remove(address, uint64_t(address) + size);
    host.InvalidateGuestCode(address, size);
    jit.Regs()[0] = 0;
});
