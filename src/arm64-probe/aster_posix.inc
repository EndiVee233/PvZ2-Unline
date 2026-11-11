// SPDX-License-Identifier: GPL-3.0-or-later
// Included inside RegisterLibcThunks to share FILE, fd, semaphore and thread registries.
RegisterThunk("getpagesize", [](Jit& jit, Host&) { jit.Regs()[0] = ::getpagesize(); });
RegisterThunk("fileno", [](Jit& jit, Host& host) {
    Result(jit, host, WithFile(jit.Regs()[0], -1, [](FILE* file) { return ::fileno(file); }));
});
RegisterThunk("fseeko", [](Jit& jit, Host& host) {
    const int32_t offset = jit.Regs()[1], whence = jit.Regs()[2];
    auto file = Lookup(g_files, jit.Regs()[0]);
    if (file && file->direct) {
        std::lock_guard lock(file->mutex);
        Result(jit, host, AssetVfs::Seek(file->direct.get(), offset, whence) < 0 ? -1 : 0);
    } else Result(jit, host, WithFile(jit.Regs()[0], -1,
        [&](FILE* stream) { return ::fseeko64(stream, offset, whence); }));
});
RegisterThunk("ftello", [](Jit& jit, Host& host) {
    auto file = Lookup(g_files, jit.Regs()[0]);
    off64_t offset;
    if (file && file->direct) {
        std::lock_guard lock(file->mutex);
        offset = AssetVfs::Tell(file->direct.get());
    } else offset = WithFile(jit.Regs()[0], off64_t(-1), [](FILE* stream) { return ::ftello64(stream); });
    if (offset > INT32_MAX) Failure(jit, host, EOVERFLOW);
    else Result(jit, host, offset);
});
RegisterThunk("vasprintf", [](Jit& jit, Host& host) {
    const uint32_t output = jit.Regs()[0];
    auto* destination = static_cast<uint32_t*>(Span(host, output, 4));
    VarArgs args(jit, host, jit.Regs()[2], true);
    const auto text = Format(host, String(host, jit.Regs()[1]), args);
    *destination = 0;
    if (host.HasFailed()) return;
    const uint32_t allocation = host.GuestAlloc(text.size() + 1);
    if (!allocation) { Failure(jit, host, ENOMEM); return; }
    memcpy(Span(host, allocation, text.size() + 1), text.c_str(), text.size() + 1);
    *destination = allocation;
    jit.Regs()[0] = text.size();
});
RegisterThunk("vsscanf", [](Jit& jit, Host& host) {
    VarArgs args(jit, host, jit.Regs()[2], true);
    jit.Regs()[0] = Scan(host, String(host, jit.Regs()[0]), String(host, jit.Regs()[1]), args);
});
RegisterThunk("android_set_abort_message", [](Jit& jit, Host& host) {
    android_set_abort_message(String(host, jit.Regs()[0]));
});
struct AsterSyslog { std::mutex mutex; std::string tag = "AsterGuest"; int facility = 0; };
const auto syslogState = std::make_shared<AsterSyslog>();
RegisterThunk("openlog", [syslogState](Jit& jit, Host& host) {
    std::lock_guard lock(syslogState->mutex);
    syslogState->tag = jit.Regs()[0] ? String(host, jit.Regs()[0]) : "AsterGuest";
    syslogState->facility = jit.Regs()[2];
});
RegisterThunk("closelog", [syslogState](Jit&, Host&) {
    std::lock_guard lock(syslogState->mutex);
    syslogState->tag = "AsterGuest";
    syslogState->facility = 0;
});
RegisterThunk("syslog", [syslogState](Jit& jit, Host& host) {
    const auto priority = jit.Regs()[0] & 7;
    VarArgs args(jit, host, 2);
    const auto text = Format(host, String(host, jit.Regs()[1]), args);
    std::lock_guard lock(syslogState->mutex);
    const int androidPriority = priority <= 3 ? ANDROID_LOG_ERROR : priority == 4 ? ANDROID_LOG_WARN
        : priority <= 6 ? ANDROID_LOG_INFO : ANDROID_LOG_DEBUG;
    __android_log_write(androidPriority, syslogState->tag.c_str(), text.c_str());
});
RegisterThunk("vswprintf", [](Jit& jit, Host& host) {
    const auto output = jit.Regs()[0], count = jit.Regs()[1];
    VarArgs args(jit, host, jit.Regs()[3], true);
    std::wstring result;
    if (!FormatWide(host, WideText(host, jit.Regs()[2]), args, result)) {
        host.Fail("Aster wide printf format unsupported");
        jit.Regs()[0] = UINT32_MAX;
        return;
    }
    if (!count || result.size() >= count) { Errno(host, EOVERFLOW); jit.Regs()[0] = UINT32_MAX; return; }
    memcpy(Span(host, output, (result.size() + 1) * 4), result.c_str(), (result.size() + 1) * 4);
    jit.Regs()[0] = uint32_t(result.size());
});
RegisterThunk("swscanf", [](Jit& jit, Host& host) {
    VarArgs args(jit, host, 2);
    jit.Regs()[0] = ScanWide(host, WideText(host, jit.Regs()[0]), WideText(host, jit.Regs()[1]), args);
});
RegisterThunk("ferror", [](Jit& jit, Host& host) {
    auto file = Lookup(g_files, jit.Regs()[0]);
    if (!file) { Failure(jit, host, EBADF); return; }
    if (file->direct) { jit.Regs()[0] = 0; return; }
    Result(jit, host, WithFile(jit.Regs()[0], EOF, [](FILE* stream) { return ferror(stream); }));
});
RegisterThunk("__srget", [](Jit& jit, Host& host) {
    const uint32_t handle = jit.Regs()[0];
    auto file = Lookup(g_files, handle);
    if (file && file->direct) {
        std::lock_guard lock(file->mutex);
        unsigned char byte{};
        const auto count = AssetVfs::Read(file->direct.get(), &byte, 1);
        Result(jit, host, count == 1 ? byte : EOF);
        return;
    }
    Result(jit, host, WithFile(handle, EOF, [](FILE* stream) { return fgetc(stream); }));
});
RegisterThunk("__swbuf", [](Jit& jit, Host& host) {
    const int character = jit.Regs()[0];
    Result(jit, host, WithFile(jit.Regs()[1], EOF, [&](FILE* stream) { return fputc(character, stream); }));
});
RegisterThunk("tmpfile", [](Jit& jit, Host& host) {
    auto pattern = asterTemporaryPattern();
    if (pattern.empty()) { Errno(host, ENOENT); jit.Regs()[0] = 0; return; }
    const int fd = ::mkstemp(pattern.data());
    if (fd < 0) { Errno(host, errno); jit.Regs()[0] = 0; return; }
    if (::unlink(pattern.c_str())) {
        const int error = errno;
        ::close(fd);
        Errno(host, error);
        jit.Regs()[0] = 0;
        return;
    }
    FILE* stream = ::fdopen(fd, "w+b");
    if (!stream) {
        const int error = errno;
        ::close(fd);
        Errno(host, error);
        jit.Regs()[0] = 0;
        return;
    }
    jit.Regs()[0] = AddFile(host, stream);
    if (!jit.Regs()[0]) Errno(host, errno);
});
RegisterThunk("freopen", [](Jit& jit, Host& host) {
    const uint32_t handle = jit.Regs()[2];
    const char* path = jit.Regs()[0] ? String(host, jit.Regs()[0]) : nullptr;
    const char* mode = String(host, jit.Regs()[1]);
    auto file = Lookup(g_files, handle);
    if (!file || !mode) { Errno(host, EBADF); jit.Regs()[0] = 0; return; }
    std::lock_guard lock(file->mutex);
    if (!file->stream) { Errno(host, ENOTSUP); jit.Regs()[0] = 0; return; }
    file->stream = ::freopen(path, mode, file->stream);
    if (!file->stream) { Errno(host, errno); jit.Regs()[0] = 0; return; }
    if (path) file->label = path;
    host.MemoryWrite16(handle + 14, uint16_t(fileno(file->stream)));
    jit.Regs()[0] = handle;
});
RegisterThunk("fsetpos", [](Jit& jit, Host& host) {
    int32_t offset{};
    memcpy(&offset, Span(host, jit.Regs()[1], sizeof(offset)), sizeof(offset));
    auto file = Lookup(g_files, jit.Regs()[0]);
    if (file && file->direct) {
        std::lock_guard lock(file->mutex);
        Result(jit, host, AssetVfs::Seek(file->direct.get(), offset, SEEK_SET) < 0 ? -1 : 0);
        return;
    }
    Result(jit, host, WithFile(jit.Regs()[0], -1, [&](FILE* stream) { return fseeko64(stream, offset, SEEK_SET); }));
});
RegisterThunk("ftruncate", [](Jit& jit, Host& host) {
    const int fd = int32_t(jit.Regs()[0]);
    if (LookupVirtualFd(fd)) { Failure(jit, host, EBADF); return; }
    Result(jit, host, ::ftruncate(NativeFd(fd), int32_t(jit.Regs()[1])));
});
RegisterThunk("writev", [](Jit& jit, Host& host) {
    const int count = int32_t(jit.Regs()[2]);
    if (count < 0 || count > IOV_MAX) { Failure(jit, host, EINVAL); return; }
    const uint32_t source = jit.Regs()[1];
    Span(host, source, size_t(count) * 8);
    std::vector<iovec> buffers;
    buffers.reserve(count);
    for (int i = 0; i < count; ++i) {
        const auto address = host.MemoryRead32(source + i * 8);
        const auto size = host.MemoryRead32(source + i * 8 + 4);
        buffers.push_back({Span(host, address, size), size});
    }
    if (LookupVirtualFd(int32_t(jit.Regs()[0]))) { Failure(jit, host, EBADF); return; }
    Result(jit, host, ::writev(NativeFd(int32_t(jit.Regs()[0])), buffers.data(), count));
});
RegisterThunk("fwide", [](Jit& jit, Host& host) {
    Result(jit, host, WithFile(jit.Regs()[0], 0, [&](FILE* stream) { return ::fwide(stream, int32_t(jit.Regs()[1])); }));
});
RegisterThunk("getwc", [](Jit& jit, Host& host) {
    const wint_t value = WithFile(jit.Regs()[0], wint_t(WEOF), [](FILE* stream) { return ::getwc(stream); });
    if (value == WEOF) Errno(host, errno);
    jit.Regs()[0] = value;
});
RegisterThunk("putwc", [](Jit& jit, Host& host) {
    const wint_t value = WithFile(jit.Regs()[1], wint_t(WEOF), [&](FILE* stream) { return ::putwc(wchar_t(jit.Regs()[0]), stream); });
    if (value == WEOF) Errno(host, errno);
    jit.Regs()[0] = value;
});
RegisterThunk("ungetwc", [](Jit& jit, Host& host) {
    const wint_t value = WithFile(jit.Regs()[1], wint_t(WEOF), [&](FILE* stream) { return ::ungetwc(jit.Regs()[0], stream); });
    if (value == WEOF) Errno(host, errno);
    jit.Regs()[0] = value;
});
RegisterThunk("sem_timedwait", [](Jit& jit, Host& host) {
    auto semaphore = GetSemaphore(jit.Regs()[0]);
    if (!semaphore) { Failure(jit, host, EINVAL); return; }
    timespec deadline{};
    if (!ReadTime(host, jit.Regs()[1], deadline)) { Failure(jit, host, EINVAL); return; }
    Result(jit, host, ::sem_timedwait(&semaphore->value, &deadline));
});
RegisterThunk("pthread_condattr_init", [](Jit& jit, Host& host) {
    Span(host, jit.Regs()[0], 4);
    host.MemoryWrite32(jit.Regs()[0], 0);
    jit.Regs()[0] = 0;
});
RegisterThunk("pthread_condattr_destroy", [](Jit& jit, Host& host) {
    Span(host, jit.Regs()[0], 4);
    jit.Regs()[0] = 0;
});
RegisterThunk("pthread_mutexattr_setpshared", [](Jit& jit, Host& host) {
    Span(host, jit.Regs()[0], 4);
    // Address-keyed bridge mutexes support intra-process synchronization.
    jit.Regs()[0] = jit.Regs()[1] == PTHREAD_PROCESS_PRIVATE ? 0 : ENOTSUP;
});
RegisterThunk("pthread_attr_setschedpolicy", [](Jit& jit, Host& host) {
    auto* attr = static_cast<Attr32*>(Span(host, jit.Regs()[0], sizeof(Attr32)));
    const int policy = int32_t(jit.Regs()[1]);
    if (sched_get_priority_min(policy) == -1) { jit.Regs()[0] = EINVAL; return; }
    attr->policy = policy;
    jit.Regs()[0] = 0;
});
RegisterThunk("pthread_attr_getstack", [](Jit& jit, Host& host) {
    const auto* attr = static_cast<const Attr32*>(Span(host, jit.Regs()[0], sizeof(Attr32)));
    Span(host, jit.Regs()[1], 4);
    Span(host, jit.Regs()[2], 4);
    host.MemoryWrite32(jit.Regs()[1], attr->base);
    host.MemoryWrite32(jit.Regs()[2], attr->size);
    jit.Regs()[0] = 0;
});
RegisterThunk("pthread_attr_setstack", [](Jit& jit, Host& host) {
    auto* attr = static_cast<Attr32*>(Span(host, jit.Regs()[0], sizeof(Attr32)));
    const auto base = jit.Regs()[1], size = jit.Regs()[2];
    if (!base || size < PTHREAD_STACK_MIN || uint64_t(base) + size > host.GetGuestMemorySize()) {
        jit.Regs()[0] = EINVAL;
        return;
    }
    attr->base = base;
    attr->size = size;
    jit.Regs()[0] = 0;
});
RegisterThunk("pthread_getschedparam", [](Jit& jit, Host& host) {
    auto thread = GetThread(jit.Regs()[0]);
    if (!thread) { jit.Regs()[0] = ESRCH; return; }
    Span(host, jit.Regs()[1], 4);
    Span(host, jit.Regs()[2], 4);
    std::lock_guard lock(thread->mutex);
    int policy{};
    sched_param parameter{};
    const int result = pthread_getschedparam(thread->native, &policy, &parameter);
    if (!result) {
        host.MemoryWrite32(jit.Regs()[1], policy);
        host.MemoryWrite32(jit.Regs()[2], parameter.sched_priority);
    }
    jit.Regs()[0] = result;
});
RegisterThunk("pthread_getattr_np", [](Jit& jit, Host& host) {
    const auto id = jit.Regs()[0];
    auto* output = static_cast<Attr32*>(Span(host, jit.Regs()[1], sizeof(Attr32)));
    if (!GetThread(id)) { jit.Regs()[0] = ESRCH; return; }
    if (id != Self()) { jit.Regs()[0] = ENOTSUP; return; }
    const uint32_t sp = jit.Regs()[13];
    if (sp < ASTER_STACK_BASE || sp >= uint64_t(ASTER_STACK_BASE) + 64 * ASTER_STACK_STRIDE) {
        jit.Regs()[0] = EINVAL;
        return;
    }
    const uint32_t slot = (sp - ASTER_STACK_BASE) / ASTER_STACK_STRIDE;
    const uint32_t guard = uint32_t(sysconf(_SC_PAGESIZE));
    const uint32_t base = ASTER_STACK_BASE + slot * ASTER_STACK_STRIDE;
    if (sp < base + guard || sp > base + ASTER_STACK_SIZE) { jit.Regs()[0] = EINVAL; return; }
    int policy{};
    sched_param schedule{};
    const int result = pthread_getschedparam(pthread_self(), &policy, &schedule);
    if (!result) *output = Attr32{0, base + guard, ASTER_STACK_SIZE - guard, guard, policy, schedule.sched_priority};
    jit.Regs()[0] = result;
});
RegisterThunk("readdir_r", [](Jit& jit, Host& host) {
    const auto directory = jit.Regs()[0], output = jit.Regs()[1], result = jit.Regs()[2];
    Span(host, output, sizeof(Dirent32));
    Span(host, result, 4);
    const uint32_t saved = host.MemoryRead32(host.GuestErrnoAddress());
    host.MemoryWrite32(host.GuestErrnoAddress(), 0);
    const uint32_t entry = host.CallGuestNested(
        host.GetThunkManager().ResolveSymbol("readdir", STT_FUNC), {directory});
    const auto error = host.MemoryRead32(host.GuestErrnoAddress());
    host.MemoryWrite32(host.GuestErrnoAddress(), saved);
    host.MemoryWrite32(result, entry ? output : 0);
    if (entry) memcpy(Span(host, output, sizeof(Dirent32)), Span(host, entry, sizeof(Dirent32)), sizeof(Dirent32));
    jit.Regs()[0] = entry ? 0 : error;
});
RegisterThunk("system", [](Jit& jit, Host& host) {
    const char* command = jit.Regs()[0] ? String(host, jit.Regs()[0]) : nullptr;
    Result(jit, host, ::system(command));
});
RegisterThunk("tmpnam", [](Jit& jit, Host& host) {
    auto pattern = asterTemporaryPattern();
    const uint32_t output = jit.Regs()[0];
    if (pattern.empty()) { Errno(host, ENOENT); jit.Regs()[0] = 0; return; }
    const int fd = ::mkstemp(pattern.data());
    if (fd < 0) { Errno(host, errno); jit.Regs()[0] = 0; return; }
    ::close(fd);
    if (::unlink(pattern.c_str())) { Errno(host, errno); jit.Regs()[0] = 0; return; }
    if (output) {
        memcpy(Span(host, output, pattern.size() + 1), pattern.c_str(), pattern.size() + 1);
        jit.Regs()[0] = output;
    } else {
        jit.Regs()[0] = CachedString(host, "tmpnam", pattern.c_str());
    }
});
RegisterThunk("ptrace", [](Jit& jit, Host& host) {
    // An emulated CPU has no host process with matching registers.
    Failure(jit, host, ENOSYS);
});
RegisterThunk("prctl", [](Jit& jit, Host& host) {
    const int option = int32_t(jit.Regs()[0]);
    if (option == PR_SET_NAME) {
        Result(jit, host, ::prctl(option, String(host, jit.Regs()[1]), 0UL, 0UL, 0UL));
    } else if (option == PR_GET_NAME) {
        Result(jit, host, ::prctl(option, Span(host, jit.Regs()[1], 16), 0UL, 0UL, 0UL));
    } else if (option == PR_GET_DUMPABLE || option == PR_GET_SECCOMP || option == PR_GET_KEEPCAPS) {
        Result(jit, host, ::prctl(option, 0UL, 0UL, 0UL, 0UL));
    } else if (option == PR_SET_DUMPABLE || option == PR_SET_KEEPCAPS) {
        Result(jit, host, ::prctl(option, static_cast<unsigned long>(jit.Regs()[1]), 0UL, 0UL, 0UL));
    } else {
        Failure(jit, host, EINVAL);
    }
});
RegisterThunk("__android_log_assert", [](Jit& jit, Host& host) {
    const char* condition = jit.Regs()[0] ? String(host, jit.Regs()[0]) : "";
    const char* tag = jit.Regs()[1] ? String(host, jit.Regs()[1]) : "AsterGuest";
    std::string message = condition;
    if (jit.Regs()[2]) {
        VarArgs args(jit, host, 3);
        message = Format(host, String(host, jit.Regs()[2]), args);
    }
    __android_log_write(ANDROID_LOG_FATAL, tag, message.c_str());
    host.Fail(message.c_str());
});
const auto timezoneAddress = m_host.GuestAlloc(4, 4);
const auto namesAddress = m_host.GuestAlloc(8, 4);
if (!timezoneAddress || !namesAddress) Invalid("Aster timezone allocation");
RegisterSymbol("timezone", timezoneAddress);
RegisterSymbol("tzname", namesAddress);
const auto updateTimezone = [timezoneAddress, namesAddress](Host& host) {
    ::tzset();
    host.MemoryWrite32(timezoneAddress, uint32_t(::timezone));
    host.MemoryWrite32(namesAddress, CachedString(host, "aster-tzname-0", ::tzname[0]));
    host.MemoryWrite32(namesAddress + 4, CachedString(host, "aster-tzname-1", ::tzname[1]));
};
updateTimezone(m_host);
RegisterThunk("tzset", [updateTimezone](Jit&, Host& host) { updateTimezone(host); });
RegisterThunk("asctime", [](Jit& jit, Host& host) {
    const auto& source = *static_cast<const Tm32*>(Span(host, jit.Regs()[0], sizeof(Tm32)));
    tm value{};
    value.tm_sec = source.sec; value.tm_min = source.min; value.tm_hour = source.hour;
    value.tm_mday = source.mday; value.tm_mon = source.mon; value.tm_year = source.year;
    value.tm_wday = source.wday; value.tm_yday = source.yday; value.tm_isdst = source.isdst;
    char buffer[26]{};
    if (::asctime_r(&value, buffer)) jit.Regs()[0] = CachedString(host, "asctime", buffer);
    else { Errno(host, errno); jit.Regs()[0] = 0; }
});
RegisterThunk("wcsftime", [](Jit& jit, Host& host) {
    const uint32_t output = jit.Regs()[0], count = jit.Regs()[1], format = jit.Regs()[2];
    if (!count) { jit.Regs()[0] = 0; return; }
    const auto& source = *static_cast<const Tm32*>(Span(host, jit.Regs()[3], sizeof(Tm32)));
    tm value{};
    value.tm_sec = source.sec; value.tm_min = source.min; value.tm_hour = source.hour;
    value.tm_mday = source.mday; value.tm_mon = source.mon; value.tm_year = source.year;
    value.tm_wday = source.wday; value.tm_yday = source.yday; value.tm_isdst = source.isdst;
    value.tm_gmtoff = source.gmtoff;
    value.tm_zone = source.zone ? String(host, source.zone) : nullptr;
    const auto* text = static_cast<const wchar_t*>(Span(host, format, (GuestWideLength(host, format) + 1) * 4));
    auto* buffer = static_cast<wchar_t*>(Span(host, output, uint64_t(count) * 4));
    jit.Regs()[0] = uint32_t(::wcsftime(buffer, count, text, &value));
});
