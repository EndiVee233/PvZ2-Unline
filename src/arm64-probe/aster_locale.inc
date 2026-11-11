// SPDX-License-Identifier: GPL-3.0-or-later
// A32 Bionic locale handles and pointer-bearing structures cannot cross the
// bridge unchanged. Keep the native locale alive while a host thread uses it.
namespace {
struct NativeLocale {
    locale_t value;
    explicit NativeLocale(locale_t locale) : value(locale) {}
    ~NativeLocale() { ::freelocale(value); }
};
struct GuestLocales {
    std::mutex mutex;
    uint32_t next = 0x5d000000;
    std::unordered_map<uint32_t, std::shared_ptr<NativeLocale>> handles;
    uint32_t add(locale_t locale) {
        std::lock_guard lock(mutex);
        const auto handle = next += 4;
        handles.emplace(handle, std::make_shared<NativeLocale>(locale));
        return handle;
    }
    std::shared_ptr<NativeLocale> find(uint32_t handle) {
        std::lock_guard lock(mutex);
        const auto found = handles.find(handle);
        return found == handles.end() ? nullptr : found->second;
    }
    void erase(uint32_t handle) { std::lock_guard lock(mutex); handles.erase(handle); }
};
struct ThreadLocale {
    std::shared_ptr<GuestLocales> owner;
    std::shared_ptr<NativeLocale> selected;
    uint32_t handle = UINT32_MAX;
    ~ThreadLocale() { if (selected) ::uselocale(LC_GLOBAL_LOCALE); }
};
thread_local ThreadLocale asterThreadLocale;
uint32_t pointer32(Host& host, const void* pointer) {
    return pointer ? uint32_t(static_cast<const uint8_t*>(pointer) - host.GetGuestMemoryBase()) : 0;
}
}

void registerAsterLocale(Host& host) {
    auto& manager = host.GetThunkManager();
    const auto locales = std::make_shared<GuestLocales>();
    manager.RegisterThunk("newlocale", [locales](Jit& jit, Host& guest) {
        const int mask = jit.Regs()[0];
        const auto* name = string<char>(guest, jit.Regs()[1]);
        const auto baseHandle = jit.Regs()[2];
        jit.Regs()[0] = 0;
        if (!name) return;
        std::shared_ptr<NativeLocale> base;
        locale_t copy = nullptr;
        if (baseHandle) {
            base = locales->find(baseHandle);
            if (!base) { setGuestErrno(guest, EINVAL); return; }
            copy = ::duplocale(base->value);
            if (!copy) { setGuestErrno(guest, errno); return; }
        }
        locale_t result = ::newlocale(mask, name, copy);
        if (!result) {
            const int error = errno;
            if (copy) ::freelocale(copy);
            setGuestErrno(guest, error);
            return;
        }
        if (baseHandle) locales->erase(baseHandle);
        jit.Regs()[0] = locales->add(result);
    });
    manager.RegisterThunk("freelocale", [locales](Jit& jit, Host& guest) {
        if (!locales->find(jit.Regs()[0])) { setGuestErrno(guest, EINVAL); return; }
        locales->erase(jit.Regs()[0]);
    });
    manager.RegisterThunk("uselocale", [locales](Jit& jit, Host& guest) {
        const auto requested = jit.Regs()[0];
        auto& current = asterThreadLocale;
        const uint32_t previous = current.owner == locales ? current.handle : UINT32_MAX;
        if (!requested) { jit.Regs()[0] = previous; return; }
        auto value = requested == UINT32_MAX ? nullptr : locales->find(requested);
        if (requested != UINT32_MAX && !value) {
            setGuestErrno(guest, EINVAL); jit.Regs()[0] = 0; return;
        }
        if (!::uselocale(value ? value->value : LC_GLOBAL_LOCALE)) {
            setGuestErrno(guest, errno); jit.Regs()[0] = 0; return;
        }
        current.owner = locales;
        current.selected = std::move(value);
        current.handle = requested;
        jit.Regs()[0] = previous;
    });
    for (auto [name, function] : {std::pair{"iswlower_l", &::iswlower_l}, {"iswspace_l", &::iswspace_l},
        {"iswprint_l", &::iswprint_l}, {"iswcntrl_l", &::iswcntrl_l}, {"iswupper_l", &::iswupper_l},
        {"iswalpha_l", &::iswalpha_l}, {"iswdigit_l", &::iswdigit_l}, {"iswpunct_l", &::iswpunct_l},
        {"iswxdigit_l", &::iswxdigit_l}, {"iswblank_l", &::iswblank_l}}) {
        manager.RegisterThunk(name, [locales, function](Jit& jit, Host& guest) {
            const auto locale = locales->find(jit.Regs()[1]);
            if (!locale) { setGuestErrno(guest, EINVAL); jit.Regs()[0] = 0; return; }
            jit.Regs()[0] = function(jit.Regs()[0], locale->value);
        });
    }
    for (auto [name, function] : {std::pair{"towupper_l", &::towupper_l}, {"towlower_l", &::towlower_l}}) {
        manager.RegisterThunk(name, [locales, function](Jit& jit, Host& guest) {
            const auto locale = locales->find(jit.Regs()[1]);
            if (!locale) { setGuestErrno(guest, EINVAL); return; }
            jit.Regs()[0] = function(jit.Regs()[0], locale->value);
        });
    }
    manager.RegisterThunk("strcoll_l", [locales](Jit& jit, Host& guest) {
        const auto* a = string<char>(guest, jit.Regs()[0]);
        const auto* b = string<char>(guest, jit.Regs()[1]);
        const auto locale = locales->find(jit.Regs()[2]);
        if (!locale) { setGuestErrno(guest, EINVAL); jit.Regs()[0] = 0; return; }
        if (a && b) jit.Regs()[0] = ::strcoll_l(a, b, locale->value);
    });
    manager.RegisterThunk("wcscoll_l", [locales](Jit& jit, Host& guest) {
        const auto* a = string<wchar_t>(guest, jit.Regs()[0]);
        const auto* b = string<wchar_t>(guest, jit.Regs()[1]);
        const auto locale = locales->find(jit.Regs()[2]);
        if (!locale) { setGuestErrno(guest, EINVAL); jit.Regs()[0] = 0; return; }
        if (a && b) jit.Regs()[0] = ::wcscoll_l(a, b, locale->value);
    });
    manager.RegisterThunk("strxfrm_l", [locales](Jit& jit, Host& guest) {
        const auto count = jit.Regs()[2];
        const auto* source = string<char>(guest, jit.Regs()[1]);
        auto* target = count ? span<char>(guest, jit.Regs()[0], count) : nullptr;
        const auto locale = locales->find(jit.Regs()[3]);
        if (!locale) { setGuestErrno(guest, EINVAL); jit.Regs()[0] = 0; return; }
        if (source && !guest.HasFailed()) jit.Regs()[0] = ::strxfrm_l(target, source, count, locale->value);
    });
    manager.RegisterThunk("wcsxfrm_l", [locales](Jit& jit, Host& guest) {
        const auto count = jit.Regs()[2];
        const auto* source = string<wchar_t>(guest, jit.Regs()[1]);
        auto* target = count ? span<wchar_t>(guest, jit.Regs()[0], count) : nullptr;
        const auto locale = locales->find(jit.Regs()[3]);
        if (!locale) { setGuestErrno(guest, EINVAL); jit.Regs()[0] = 0; return; }
        if (source && !guest.HasFailed()) jit.Regs()[0] = ::wcsxfrm_l(target, source, count, locale->value);
    });
    manager.RegisterThunk("strftime_l", [locales](Jit& jit, Host& guest) {
        // struct tm: nine signed 32-bit fields, gmtoff32 and zone pointer32.
        const auto* fields = span<int32_t>(guest, jit.Regs()[3], 11);
        const auto count = jit.Regs()[1];
        auto* output = count ? span<char>(guest, jit.Regs()[0], count) : nullptr;
        const auto* format = string<char>(guest, jit.Regs()[2]);
        const auto locale = locales->find(guest.MemoryRead32(jit.Regs()[13]));
        if (!locale) { setGuestErrno(guest, EINVAL); jit.Regs()[0] = 0; return; }
        if (!fields || !format || guest.HasFailed()) return;
        tm time{};
        time.tm_sec=fields[0]; time.tm_min=fields[1]; time.tm_hour=fields[2];
        time.tm_mday=fields[3]; time.tm_mon=fields[4]; time.tm_year=fields[5];
        time.tm_wday=fields[6]; time.tm_yday=fields[7]; time.tm_isdst=fields[8];
        time.tm_gmtoff=fields[9];
        time.tm_zone=fields[10] ? string<char>(guest, uint32_t(fields[10])) : nullptr;
        if (!guest.HasFailed()) jit.Regs()[0] = ::strftime_l(output, count, format, &time, locale->value);
    });
    struct LocaleBuffer { std::mutex mutex; uint32_t address = 0; size_t size = 0; };
    const auto localeBuffer = std::make_shared<LocaleBuffer>();
    manager.RegisterThunk("localeconv", [localeBuffer](Jit& jit, Host& guest) {
        std::lock_guard lock(localeBuffer->mutex);
        const lconv* value = ::localeconv();
        const char* strings[] = {value->decimal_point, value->thousands_sep, value->grouping,
            value->int_curr_symbol, value->currency_symbol, value->mon_decimal_point,
            value->mon_thousands_sep, value->mon_grouping, value->positive_sign, value->negative_sign};
        size_t length = 56;
        for (const char* text : strings) length += strlen(text) + 1;
        if (length > localeBuffer->size) {
            localeBuffer->address = guest.GuestAlloc(std::max<size_t>(length, 4096));
            localeBuffer->size = localeBuffer->address ? std::max<size_t>(length,4096) : 0;
        }
        const uint32_t allocation = localeBuffer->address;
        if (!allocation) { setGuestErrno(guest, ENOMEM); jit.Regs()[0] = 0; return; }
        auto* bytes = span<uint8_t>(guest, allocation, length);
        memset(bytes, 0, length);
        size_t cursor = 56;
        for (unsigned i=0; i<10; ++i) {
            guest.MemoryWrite32(allocation + i*4, allocation + cursor);
            const size_t size = strlen(strings[i]) + 1;
            memcpy(bytes + cursor, strings[i], size); cursor += size;
        }
        const char flags[] = {value->int_frac_digits, value->frac_digits, value->p_cs_precedes,
            value->p_sep_by_space, value->n_cs_precedes, value->n_sep_by_space, value->p_sign_posn,
            value->n_sign_posn, value->int_p_cs_precedes, value->int_p_sep_by_space,
            value->int_n_cs_precedes, value->int_n_sep_by_space, value->int_p_sign_posn, value->int_n_sign_posn};
        memcpy(bytes + 40, flags, sizeof(flags));
        jit.Regs()[0] = allocation;
    });
    manager.RegisterThunk("posix_memalign", [](Jit& jit, Host& guest) {
        auto* output = span<uint32_t>(guest, jit.Regs()[0], 1);
        const uint32_t alignment = jit.Regs()[1], size = jit.Regs()[2];
        if (!output) return;
        if (alignment < 4 || !std::has_single_bit(alignment)) { jit.Regs()[0] = EINVAL; return; }
        const auto allocation = guest.GuestAlloc(std::max(size, 1u), alignment);
        if (allocation) *output = allocation;
        jit.Regs()[0] = allocation ? 0 : ENOMEM;
    });
    manager.RegisterThunk("statvfs", [](Jit& jit, Host& guest) {
        const char* path = string<char>(guest, jit.Regs()[0]);
        auto* target = span<uint32_t>(guest, jit.Regs()[1], 11);
        if (!path || !target) return;
        struct statvfs value{};
        if (::statvfs(path, &value)) { setGuestErrno(guest, errno); jit.Regs()[0] = UINT32_MAX; return; }
        const uint64_t fields[] = {value.f_bsize,value.f_frsize,value.f_blocks,value.f_bfree,value.f_bavail,
            value.f_files,value.f_ffree,value.f_favail,value.f_fsid,value.f_flag,value.f_namemax};
        // fsblkcnt_t and fsfilcnt_t are unsigned long (32-bit) in A32 Bionic.
        for (auto field : fields) if (field > UINT32_MAX) {
            setGuestErrno(guest, EOVERFLOW); jit.Regs()[0] = UINT32_MAX; return;
        }
        for (unsigned i=0; i<11; ++i) target[i] = fields[i];
        jit.Regs()[0] = 0;
    });

    // ARM EABI long double is double64; AArch64 long double is IEEE128.
    // Parse through double for the A32 strtold/wcstold entry points.
    for (const bool wide : {false, true}) for (const int kind : {0, 1, 2, 3, 4, 5}) {
        const char* names[2][6] = {{"strtoll","strtoull","strtof","strtod","strtold","strtoul"},
            {"wcstoll","wcstoull","wcstof","wcstod","wcstold","wcstoul"}};
        const char* name = names[wide][kind];
        for (bool localized : {false, true}) {
            // Only implement the locale forms used by Aster here.
            if (localized && (wide || (kind != 0 && kind != 1 && kind != 4))) continue;
            const auto entry = std::string(name) + (localized ? "_l" : "");
            if (manager.FindRegisteredSymbol(entry)) continue;
            manager.RegisterThunk(entry,
                [locales,wide,kind,localized](Jit& jit, Host& guest) {
                const uint32_t input = jit.Regs()[0], endAddress = jit.Regs()[1];
                auto* output = endAddress ? span<uint32_t>(guest, endAddress, 1) : nullptr;
                const bool integer = kind < 2 || kind == 5;
                const int base = integer ? int32_t(jit.Regs()[2]) : 0;
                auto locale = localized ? locales->find(jit.Regs()[integer ? 3 : 2]) : nullptr;
                if (localized && !locale) { setGuestErrno(guest, EINVAL); return64(jit,uint64_t(0)); return; }
                const char* narrow = wide ? nullptr : string<char>(guest,input);
                const wchar_t* source = wide ? string<wchar_t>(guest,input) : nullptr;
                if (guest.HasFailed()) return;
                errno = 0;
                char* narrowEnd = nullptr; wchar_t* wideEnd = nullptr;
                if (kind == 0) {
                    const int64_t value = wide ? ::wcstoll(source,&wideEnd,base)
                        : localized ? ::strtoll_l(narrow,&narrowEnd,base,locale->value) : ::strtoll(narrow,&narrowEnd,base);
                    return64(jit,value);
                } else if (kind == 1 || kind == 5) {
                    uint64_t value = wide ? ::wcstoull(source,&wideEnd,base)
                        : localized ? ::strtoull_l(narrow,&narrowEnd,base,locale->value) : ::strtoull(narrow,&narrowEnd,base);
                    if (kind == 5) {
                        // A negative representable unsigned-long input wraps in 32 bits.
                        const auto negative = [&]() { if (wide) { auto p=source; while(iswspace(*p)) ++p; return *p==L'-'; }
                            auto p=narrow; while(isspace(static_cast<unsigned char>(*p))) ++p; return *p=='-'; }();
                        if (negative && !errno && value >= UINT64_MAX-UINT32_MAX+1) jit.Regs()[0] = uint32_t(value);
                        else if (errno || value > UINT32_MAX) { errno=ERANGE; jit.Regs()[0]=UINT32_MAX; }
                        else jit.Regs()[0]=uint32_t(value);
                    } else return64(jit,value);
                } else if (kind == 2) {
                    const float value = wide ? ::wcstof(source,&wideEnd) : ::strtof(narrow,&narrowEnd);
                    jit.Regs()[0] = std::bit_cast<uint32_t>(value);
                } else {
                    const double value = wide ? ::wcstod(source,&wideEnd)
                        : localized ? ::strtod_l(narrow,&narrowEnd,locale->value) : ::strtod(narrow,&narrowEnd);
                    return64(jit,value);
                }
                if (output) *output = pointer32(guest,wide ? static_cast<const void*>(wideEnd) : narrowEnd);
                if (errno) setGuestErrno(guest,errno);
            });
        }
    }
    manager.RegisterThunk("__ctype_get_mb_cur_max", [](Jit& jit, Host&) { jit.Regs()[0] = MB_CUR_MAX; });
    manager.RegisterThunk("mbrlen", [](Jit& jit, Host& guest) {
        const auto args = jit.Regs();
        const auto count = args[0] ? std::min<size_t>(args[1], MB_CUR_MAX) : 0;
        const char* source = args[0] ? string<char>(guest,args[0],count) : nullptr;
        if (!guest.HasFailed()) jit.Regs()[0] = convertMultibyte(guest,args[2],
            [&](mbstate_t* state) { return ::mbrlen(source,count,state); });
    });
    manager.RegisterThunk("mbtowc", [](Jit& jit, Host& guest) {
        auto* output = jit.Regs()[0] ? span<wchar_t>(guest,jit.Regs()[0],1) : nullptr;
        const auto count = jit.Regs()[1] ? std::min<size_t>(jit.Regs()[2],MB_CUR_MAX) : 0;
        const char* source = jit.Regs()[1] ? string<char>(guest,jit.Regs()[1],count) : nullptr;
        if (guest.HasFailed()) return;
        const int result = ::mbtowc(output,source,count);
        if (result < 0) setGuestErrno(guest,errno);
        jit.Regs()[0] = result;
    });
    for (bool wide : {false,true}) for (bool bounded : {false,true}) {
        const char* entry = wide ? bounded ? "wcsnrtombs" : "wcsrtombs" : bounded ? "mbsnrtowcs" : "mbsrtowcs";
        if (manager.FindRegisteredSymbol(entry)) continue;
        manager.RegisterThunk(entry,
            [wide,bounded](Jit& jit, Host& guest) {
            const auto args = jit.Regs();
            auto* sourcePointer = span<uint32_t>(guest,args[1],1);
            if (!sourcePointer) return;
            const uint32_t sourceAddress = *sourcePointer;
            const size_t count = args[bounded ? 3 : 2];
            const size_t inputLimit = bounded ? args[2] : SIZE_MAX;
            const auto stateAddress = bounded ? guest.MemoryRead32(args[13]) : args[3];
            if (wide) {
                const wchar_t* source = string<wchar_t>(guest,sourceAddress,inputLimit);
                auto* target = args[0] ? span<char>(guest,args[0],count) : nullptr;
                if (guest.HasFailed()) return;
                jit.Regs()[0] = convertMultibyte(guest,stateAddress,
                    [&](mbstate_t* state) { return bounded ? ::wcsnrtombs(target,&source,inputLimit,count,state)
                        : ::wcsrtombs(target,&source,count,state); });
                if (target) *sourcePointer = pointer32(guest,source);
            } else {
                const char* source = string<char>(guest,sourceAddress,inputLimit);
                auto* target = args[0] ? span<wchar_t>(guest,args[0],count) : nullptr;
                if (guest.HasFailed()) return;
                jit.Regs()[0] = convertMultibyte(guest,stateAddress,[&](mbstate_t* state) {
                    return bounded ? ::mbsnrtowcs(target,&source,inputLimit,count,state) : ::mbsrtowcs(target,&source,count,state);
                });
                if (target) *sourcePointer = pointer32(guest,source);
            }
        });
    }
}
