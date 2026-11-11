// SPDX-License-Identifier: GPL-3.0-or-later
// Included after the shared guest VarArgs and StoreCount definitions.
namespace {
constexpr size_t wideLimit = 1024 * 1024;

const wchar_t* WideText(Host& host, uint32_t address) {
    const auto length = GuestWideLength(host, address);
    return static_cast<const wchar_t*>(Span(host, address, (length + 1) * sizeof(wchar_t)));
}

template<class T>
bool AppendWide(Host& host, std::wstring& result, const std::wstring& spec, T value) {
    for (size_t capacity = 128; capacity <= wideLimit; capacity *= 2) {
        std::vector<wchar_t> buffer(capacity);
        errno = 0;
        const int count = ::swprintf(buffer.data(), capacity, spec.c_str(), value);
        if (count >= 0) {
            if (result.size() + size_t(count) >= wideLimit) break;
            result.append(buffer.data(), count);
            return true;
        }
        if (errno == EILSEQ || errno == EINVAL) break;
    }
    host.Fail("Aster wide printf conversion failed or exceeded buffer limit");
    return false;
}

bool FormatWide(Host& host, const wchar_t* format, VarArgs& args, std::wstring& result) {
    const wchar_t* cursor = format;
    while (*cursor) {
        if (result.size() >= wideLimit) { host.Fail("Aster wide printf output too large"); return false; }
        if (*cursor != L'%') { result.push_back(*cursor++); continue; }
        ++cursor;
        if (*cursor == L'%') { result.push_back(*cursor++); continue; }
        std::wstring spec = L"%";
        while (*cursor && wcschr(L"-+ #0", *cursor)) spec += *cursor++;
        auto field = [&]() {
            uint32_t value = 0;
            while (*cursor >= L'0' && *cursor <= L'9') {
                value = value * 10 + (*cursor - L'0');
                if (value >= wideLimit) return false;
                spec += *cursor++;
            }
            return true;
        };
        if (*cursor == L'*') {
            ++cursor;
            const int64_t width = int32_t(args.U32());
            if (width <= -int64_t(wideLimit) || width >= int64_t(wideLimit)) return false;
            spec += std::to_wstring(width);
        } else if (!field()) return false;
        if (*cursor == L'.') {
            ++cursor;
            if (*cursor == L'*') {
                ++cursor;
                const int32_t precision = args.U32();
                if (precision >= int32_t(wideLimit)) return false;
                if (precision >= 0) spec += L"." + std::to_wstring(precision);
            } else {
                spec += L'.';
                if (!field()) return false;
            }
        }
        std::string length;
        if (*cursor == L'h' || *cursor == L'l') {
            length += char(*cursor++);
            if (*cursor == wchar_t(length[0])) length += char(*cursor++);
        } else if (*cursor && wcschr(L"jztL", *cursor)) length += char(*cursor++);
        const wchar_t conversion = *cursor;
        if (!conversion) return false;
        ++cursor;
        spec.append(length.begin(), length.end());
        spec += conversion;
        if (conversion == L'n') { StoreCount(host, args.U32(), result.size(), length); continue; }
        bool success = false;
        if (conversion == L's') {
            const uint32_t pointer = args.U32();
            if (length == "l")
                success = AppendWide(host, result, spec, pointer ? WideText(host, pointer) : L"(null)");
            else if (length.empty())
                success = AppendWide(host, result, spec, pointer ? String(host, pointer) : "(null)");
        } else if (conversion == L'c') {
            success = AppendWide(host, result, spec, args.U32());
        } else if (conversion == L'p') {
            success = AppendWide(host, result, spec, reinterpret_cast<void*>(uintptr_t(args.U32())));
        } else if (wcschr(L"di", conversion)) {
            const int64_t value = length == "ll" || length == "j" ? int64_t(args.U64()) : int32_t(args.U32());
            if (length == "ll") success = AppendWide(host, result, spec, static_cast<long long>(value));
            else if (length == "j") success = AppendWide(host, result, spec, static_cast<intmax_t>(value));
            else if (length == "l" || length == "z" || length == "t")
                success = AppendWide(host, result, spec, static_cast<long>(value));
            else success = AppendWide(host, result, spec, int(value));
        } else if (wcschr(L"uoxX", conversion)) {
            const uint64_t value = length == "ll" || length == "j" ? args.U64() : args.U32();
            if (length == "ll") success = AppendWide(host, result, spec, static_cast<unsigned long long>(value));
            else if (length == "j") success = AppendWide(host, result, spec, static_cast<uintmax_t>(value));
            else if (length == "l" || length == "z" || length == "t")
                success = AppendWide(host, result, spec, static_cast<unsigned long>(value));
            else success = AppendWide(host, result, spec, unsigned(value));
        } else if (wcschr(L"aAeEfFgG", conversion)) {
            const double value = args.F64();
            success = length == "L" ? AppendWide(host, result, spec, static_cast<long double>(value))
                                    : AppendWide(host, result, spec, value);
        }
        if (!success) return false;
    }
    return true;
}

int ScanWide(Host& host, const wchar_t* input, const wchar_t* format, VarArgs& args) {
    const auto* start = input;
    int assigned = 0;
    while (*format) {
        if (iswspace(*format)) {
            while (iswspace(*format)) ++format;
            while (iswspace(*input)) ++input;
            continue;
        }
        if (*format != L'%' || format[1] == L'%') {
            if (*format == L'%') ++format;
            if (*format++ != *input) return assigned ? assigned : (*input ? 0 : EOF);
            ++input;
            continue;
        }
        ++format;
        const bool suppress = *format == L'*';
        if (suppress) ++format;
        std::wstring width;
        size_t count = 0;
        while (*format >= L'0' && *format <= L'9') {
            count = count * 10 + (*format - L'0');
            if (count >= wideLimit) { host.Fail("Aster wide scanf field too large"); return EOF; }
            width += *format++;
        }
        std::string length;
        if (*format == L'l' || *format == L'h') {
            length += char(*format++);
            if (*format == wchar_t(length[0])) length += char(*format++);
        } else if (*format && wcschr(L"jztL", *format)) length += char(*format++);
        const wchar_t conversion = *format;
        if (!conversion) { host.Fail("Incomplete Aster wide scanf format"); return EOF; }
        ++format;
        std::wstring suffix(1, conversion);
        if (conversion == L'[') {
            if (*format == L'^') suffix += *format++;
            if (*format == L']') suffix += *format++;
            while (*format && *format != L']') suffix += *format++;
            if (!*format) { host.Fail("Unterminated Aster wide scanf scanset"); return EOF; }
            suffix += *format++;
        }
        if (conversion == L'n') {
            if (!suppress) StoreCount(host, args.U32(), input - start, length);
            continue;
        }
        const auto destination = suppress ? 0 : args.U32();
        int consumed = -1;
        const std::wstring wideLength(length.begin(), length.end());
        if (suppress) {
            const auto spec = L"%*" + width + wideLength + suffix + L"%n";
            ::swscanf(input, spec.c_str(), &consumed);
        } else if (conversion == L's' || conversion == L'c' || conversion == L'[') {
            const size_t available = wcslen(input);
            size_t maximum = count ? count : (conversion == L'c' ? 1 : available);
            if (maximum >= wideLimit) { host.Fail("Aster wide scanf text too large"); return EOF; }
            maximum = std::max<size_t>(maximum, 1);
            const auto spec = L"%" + std::to_wstring(maximum) + wideLength + suffix + L"%n";
            if (length == "l") {
                std::vector<wchar_t> buffer(maximum + 1);
                ::swscanf(input, spec.c_str(), buffer.data(), &consumed);
                if (consumed >= 0) {
                    const size_t size = (conversion == L'c' ? maximum : wcslen(buffer.data()) + 1) * 4;
                    memcpy(Span(host, destination, size), buffer.data(), size);
                }
            } else if (length.empty()) {
                std::vector<char> buffer(maximum * MB_LEN_MAX + 1);
                ::swscanf(input, spec.c_str(), buffer.data(), &consumed);
                if (consumed >= 0) {
                    size_t size = strlen(buffer.data()) + (conversion == L'c' ? 0 : 1);
                    memcpy(Span(host, destination, size), buffer.data(), size);
                }
            } else { host.Fail("Unsupported Aster wide scanf text length"); return EOF; }
        } else if (wcschr(L"di", conversion)) {
            long long value{};
            const auto spec = L"%" + width + L"ll" + suffix + L"%n";
            ::swscanf(input, spec.c_str(), &value, &consumed);
            if (consumed >= 0) StoreCount(host, destination, value, length);
        } else if (wcschr(L"uoxX", conversion)) {
            unsigned long long value{};
            const auto spec = L"%" + width + L"ll" + suffix + L"%n";
            ::swscanf(input, spec.c_str(), &value, &consumed);
            if (consumed >= 0) StoreCount(host, destination, int64_t(value), length);
        } else if (wcschr(L"aAeEfFgG", conversion)) {
            const auto spec = L"%" + width + L"L" + suffix + L"%n";
            long double value{};
            ::swscanf(input, spec.c_str(), &value, &consumed);
            if (consumed >= 0) {
                if (length == "l" || length == "L") {
                    const double result = value;
                    memcpy(Span(host, destination, sizeof(result)), &result, sizeof(result));
                } else {
                    const float result = value;
                    memcpy(Span(host, destination, sizeof(result)), &result, sizeof(result));
                }
            }
        } else if (conversion == L'p') {
            void* value{};
            const auto spec = L"%" + width + L"p%n";
            ::swscanf(input, spec.c_str(), &value, &consumed);
            if (consumed >= 0) { Span(host, destination, 4); host.MemoryWrite32(destination, uint32_t(uintptr_t(value))); }
        } else { host.Fail("Unsupported Aster wide scanf conversion"); return EOF; }
        if (consumed < 0) return assigned ? assigned : (*input ? 0 : EOF);
        input += consumed;
        if (!suppress) ++assigned;
    }
    return assigned;
}
}
