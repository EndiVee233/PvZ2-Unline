cmake_minimum_required(VERSION 3.22)
project(aster_arm64_probe LANGUAGES C CXX)
option(ASTER_RUNTIME_DIAGNOSTICS "Enable costly real-game cycle sampling, call logs and animation tracing" OFF)

if(NOT ANDROID OR NOT ANDROID_ABI STREQUAL "arm64-v8a")
    message(FATAL_ERROR "The Aster probe requires Android arm64-v8a")
endif()
if(NOT EXISTS "${A7_BRIDGE_SOURCE}/src/dynarmic_host.h")
    message(FATAL_ERROR "Set A7_BRIDGE_SOURCE to the arm64-bridge-a7 arm64_bridge directory")
endif()

add_subdirectory("${A7_BRIDGE_SOURCE}" a7)
# Keep A7's bridge helpers without running its game-specific Java bootstrap.
set_source_files_properties("${A7_BRIDGE_SOURCE}/src/jni_bridge.cpp"
    TARGET_DIRECTORY Android PROPERTIES COMPILE_DEFINITIONS "JNI_OnLoad=A7_JNI_OnLoad")

# Let the ELF audit reach symbol resolution for the two additional libraries
# declared by Aster. The resolver still rejects every unimplemented import.
set(host "${A7_BRIDGE_SOURCE}/src/dynarmic_host.cpp")
file(READ "${host}" host_source)
set(svc_guard [=[        else Fail("Unexpected guest SVC 0");]=])
string(FIND "${host_source}" "${svc_guard}" svc_marker)
if(svc_marker EQUAL -1)
    message(FATAL_ERROR "Unsupported A7 SVC dispatch layout")
endif()
string(REPLACE "${svc_guard}" [=[        else if (jit.Regs()[7] == 0x000f0002) {
            // ARM Linux __ARM_NR_cacheflush from compiler-rt clear_cache.
            // The guest runs through JIT code; invalidate translations rather
            // than passing ARM syscall numbers to the AArch64 host kernel.
            const uint32_t begin = jit.Regs()[0], end = jit.Regs()[1];
            if (jit.Regs()[2] || begin > end || uint64_t(end) > m_memory_size)
                jit.Regs()[0] = uint32_t(-22); // raw syscall -EINVAL
            else {
                if (end > begin) InvalidateGuestCode(begin, uint64_t(end) - begin);
                jit.Regs()[0] = 0;
            }
        } else {
            LOGE("Unsupported Aster SVC 0: PC=0x%08x R7=0x%08x", pc, jit.Regs()[7]);
            Fail("Unexpected guest SVC 0");
        }]=] host_source "${host_source}")
set(known_libraries [=[const std::array<std::string, 9> system_libraries = {]=])
string(FIND "${host_source}" "${known_libraries}" marker)
if(marker EQUAL -1)
    message(FATAL_ERROR "Unsupported A7 bridge version for the Aster import audit")
endif()
string(REPLACE "${known_libraries}" [=[const std::array<std::string, 11> system_libraries = {
        "libOpenSLES.so", "libGLESv1_CM.so",]=] host_source "${host_source}")
set(a7_engine [=["libAndroid.so", "guest_libs/libAndroid.so"]=])
string(FIND "${host_source}" "${a7_engine}" marker)
if(marker EQUAL -1)
    message(FATAL_ERROR "Unsupported A7 bridge guest library list")
endif()
string(REPLACE "${a7_engine}" [=["libSrc.so", "guest_libs/libSrc_a32.so"]=] host_source "${host_source}")
option(ASTER_INCLUDE_COMPANIONS "Audit Aster's additional native libraries" OFF)
option(ASTER_INITIALIZE_COMPANIONS "Run companion constructors in a process-lifetime guest" OFF)
if(ASTER_INITIALIZE_COMPANIONS)
    if(NOT ASTER_INCLUDE_COMPANIONS)
        message(FATAL_ERROR "Companion initialization requires the companion assets")
    endif()
    target_compile_definitions(Android PRIVATE ASTER_INITIALIZE_COMPANIONS=1)
endif()
set(engine_input [=[{"libSrc.so", "guest_libs/libSrc_a32.so", 0x40000000, 0x42000000},]=])
set(all_inputs "${engine_input}")
if(ASTER_INCLUDE_COMPANIONS)
    set(engine_input [=[{"libSrc.so", "guest_libs/libSrc_a32.so", 0x40000000, 0x42000000},]=])
    set(all_inputs [=[{"libSrc.so", "guest_libs/libSrc_a32.so", 0x40000000, 0x42000000},
        {"libczProject.so", "guest_libs/libczProject_a32.so", 0x43000000, 0x43800000},
        {"libHookPVZ2.so", "guest_libs/libHookPVZ2_a32.so", 0x44000000, 0x44800000},
        {"libRestart.so", "guest_libs/libRestart_a32.so", 0x45000000, 0x45800000},
        {"libPresetEditor.so", "guest_libs/libPresetEditor_a32.so", 0x46000000, 0x46800000},
        {"libAsterRgbaPilot.so", "guest_libs/libAsterRgbaPilot_a32.so", 0x47000000, 0x47800000},]=])
    string(FIND "${host_source}" "${engine_input}" marker)
    if(marker EQUAL -1)
        message(FATAL_ERROR "Unsupported A7 library input layout")
    endif()
    string(REPLACE "${engine_input}" "${all_inputs}" host_source "${host_source}")
endif()
file(CONFIGURE OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/aster_images.inc" CONTENT "${all_inputs}" @ONLY)
option(ASTER_GAME_RUNTIME "Build the real game's JNI adapter instead of the isolated probe" OFF)
if(ASTER_GAME_RUNTIME AND ASTER_RUNTIME_DIAGNOSTICS)
    # Bounded runs make stalled real-game initialization observable. A normal
    # cycle-budget exhaustion resumes at the current guest PC, without changing
    # its registers, return value, stack or gameplay state.
    string(REPLACE "m_config.enable_cycle_counting = false;" "m_config.enable_cycle_counting = true;" host_source "${host_source}")
    string(REPLACE "const uint32_t bits = static_cast<uint32_t>(reason);"
        [=[const uint32_t bits = static_cast<uint32_t>(reason);
        if (!bits) {
            using Clock=std::chrono::steady_clock;
            static thread_local auto last=Clock::now();
            const auto now=Clock::now();
            if (now-last>std::chrono::seconds(2)) {
                last=now;
                LOGI("Aster budget PC=%08x LR=%08x R0=%08x R1=%08x",jit.Regs()[15],jit.Regs()[14],jit.Regs()[0],jit.Regs()[1]);
            }
            continue;
        }]=] host_source "${host_source}")
endif()
set(audit_host "${CMAKE_CURRENT_BINARY_DIR}/aster_audit_host.cpp")
file(CONFIGURE OUTPUT "${audit_host}" CONTENT "#include <chrono>\n${host_source}" @ONLY)
set_source_files_properties("${host}" TARGET_DIRECTORY Android PROPERTIES HEADER_FILE_ONLY TRUE)
set(libc "${A7_BRIDGE_SOURCE}/src/thunks_libc.cpp")
file(READ "${libc}" libc_source)
set(guest_open "GuestOpenFile opened=OpenGuestFile(path,mode);")
string(FIND "${libc_source}" "${guest_open}" guest_open_marker)
if(guest_open_marker EQUAL -1)
    message(FATAL_ERROR "Unsupported A7 guest file-open layout")
endif()
string(REPLACE "${guest_open}" [=[
        GuestOpenFile opened;bool guestMaps=false;
        if(ReadOnlyMode(mode))opened.stream=asterOpenGuestProcMaps(h,path,guestMaps);
        if(!guestMaps)opened=OpenGuestFile(path,mode);
]=] libc_source "${libc_source}")
foreach(compare IN ITEMS strcmp strcasecmp)
    if(compare STREQUAL "strcasecmp")
        set(ignore_case "true")
    else()
        set(ignore_case "false")
    endif()
    set(old_compare "j.Regs()[0]=${compare}(String(h,j.Regs()[0]),String(h,j.Regs()[1]));")
    string(FIND "${libc_source}" "${old_compare}" compare_marker)
    if(compare_marker EQUAL -1)
        message(FATAL_ERROR "Unsupported A7 ${compare} thunk")
    endif()
    string(REPLACE "${old_compare}" "const auto a=j.Regs();j.Regs()[0]=asterGuestStringCompare(h,a[0],a[1],${ignore_case});"
        libc_source "${libc_source}")
endforeach()
set(stack_gate "if(guest.base || guest.size!=1024*1024 || (guest.flags&~1u))return ENOTSUP;")
string(FIND "${libc_source}" "${stack_gate}" stack_marker)
if(stack_marker EQUAL -1)
    message(FATAL_ERROR "Unsupported A7 thread-stack acceptance gate")
endif()
# Aster's resource IO threads request 64 KiB. The bridge owns a 1-MiB
# guest arena per thread, so smaller minimum requests fit safely too.
# Reject caller-owned stacks and requests beyond the actual arena limit.
string(REPLACE "${stack_gate}"
    "if(guest.base || guest.size<PTHREAD_STACK_MIN || guest.size>1024*1024 || (guest.flags&~1u))return ENOTSUP;"
    libc_source "${libc_source}")
set(create_thread "if(!rc)rc=pthread_create(&native,&attr,ThreadEntry,start.get());")
string(FIND "${libc_source}" "${create_thread}" create_marker)
if(create_marker EQUAL -1)
    message(FATAL_ERROR "Unsupported A7 thread creation layout")
endif()
string(REPLACE "${create_thread}" [=[
    if(!rc)rc=pthread_create(&native,&attr,ThreadEntry,start.get());
    if(rc==EPERM && guest.policy!=SCHED_OTHER) {
        // Android apps cannot generally create realtime FIFO audio threads.
        // Retry with ordinary scheduling, retaining the real worker and its
        // join/detach behavior rather than reporting a fictitious success.
        sched_param ordinary{};
        int fallback=pthread_attr_setschedpolicy(&attr,SCHED_OTHER);
        if(!fallback)fallback=pthread_attr_setschedparam(&attr,&ordinary);
        if(!fallback)fallback=pthread_create(&native,&attr,ThreadEntry,start.get());
        LOGI("Aster realtime worker fallback policy=%d result=%d",guest.policy,fallback);
        rc=fallback;
    }
]=] libc_source "${libc_source}")
if(ASTER_GAME_RUNTIME AND ASTER_RUNTIME_DIAGNOSTICS)
    string(REPLACE "if (!label.empty() && IsMetadataLabel(label)) {" [=[
    static std::atomic<unsigned> asterFileLogs{0};
    if (!label.empty() && asterFileLogs.fetch_add(1)<160) {
        __android_log_print(ANDROID_LOG_INFO,"AsterIO","op=%s file='%s' requested=%zu result=%zu",operation,label.c_str(),requested,result);
]=] libc_source "${libc_source}")
    string(REPLACE "if(!result)Errno(h,errno);j.Regs()[0]=result;\n    });\n    RegisterThunk(\"fclose\"" [=[
        static std::atomic<unsigned> asterOpenLogs{0};
        if(asterOpenLogs.fetch_add(1)<100) LOGI("Aster fopen '%s' mode='%s' result=%08x errno=%d",path,mode,result,result?0:errno);
        if(!result)Errno(h,errno);j.Regs()[0]=result;
    });
    RegisterThunk("fclose"]=] libc_source "${libc_source}")
    string(REPLACE "j.Regs()[0]=CreateThread(h,j.Regs()[0],j.Regs()[1],j.Regs()[2],j.Regs()[3]);" [=[
        const auto a=j.Regs();
        if (a[1]) {const auto* attr=static_cast<const Attr32*>(Span(h,a[1],sizeof(Attr32)));LOGI("Aster thread request entry=%08x arg=%08x flags=%u base=%08x size=%u policy=%d priority=%d",a[2],a[3],attr->flags,attr->base,attr->size,attr->policy,attr->priority);}
        j.Regs()[0]=CreateThread(h,a[0],a[1],a[2],a[3]);
        LOGI("Aster thread create entry=%08x result=%u",a[2],j.Regs()[0]);
]=] libc_source "${libc_source}")
endif()
set(libc_end "    SelfCheck();\n}")
string(FIND "${libc_source}" "${libc_end}" marker)
if(marker EQUAL -1)
    message(FATAL_ERROR "Unsupported A7 libc registration function")
endif()
string(REPLACE "${libc_end}" "#include \"aster_posix.inc\"\n    SelfCheck();\n}" libc_source "${libc_source}")
string(REPLACE "#include \"aster_posix.inc\"" "#include \"aster_memory.inc\"\n#include \"aster_posix.inc\"" libc_source "${libc_source}")
string(REPLACE "void ThunkManager::RegisterLibcThunks(){" "#include \"aster_wide.inc\"\nvoid ThunkManager::RegisterLibcThunks(){" libc_source "${libc_source}")
set(audit_libc "${CMAKE_CURRENT_BINARY_DIR}/aster_audit_libc.cpp")
file(CONFIGURE OUTPUT "${audit_libc}" CONTENT "#include <sys/uio.h>\n#include <sys/prctl.h>\n#include <sys/mman.h>\n#include <elf.h>\n#include <cwctype>\n#include <map>\n#include \"aster_libc.h\"\n#include \"aster_dl.h\"\n${libc_source}" @ONLY)
set_source_files_properties("${libc}" TARGET_DIRECTORY Android PROPERTIES HEADER_FILE_ONLY TRUE)
set(audio "${A7_BRIDGE_SOURCE}/src/thunks_opensles.cpp")
file(READ "${audio}" audio_source)
foreach(object IN ITEMS OutputMix Player)
    set(realize "host.MemoryWrite32(g_guest${object}VtblAddr + 0 * 4, host.GetThunkManager().GetOrCreateThunkAddress(\"SLObject_Realize\"));")
    string(FIND "${audio_source}" "${realize}" audio_marker)
    if(audio_marker EQUAL -1)
        message(FATAL_ERROR "Unsupported OpenSL ${object} object layout")
    endif()
    set(extra "${realize}")
    foreach(method IN ITEMS "1|Resume" "2|GetState" "4|RegisterCallback" "5|AbortAsyncOperation")
        string(REPLACE "|" ";" pair "${method}")
        list(GET pair 0 slot)
        list(GET pair 1 name)
        string(APPEND extra "\n            host.MemoryWrite32(g_guest${object}VtblAddr + ${slot} * 4, host.GetThunkManager().GetOrCreateThunkAddress(\"SLObject_${name}\"));")
    endforeach()
    string(REPLACE "${realize}" "${extra}" audio_source "${audio_source}")
endforeach()
set(audit_audio "${CMAKE_CURRENT_BINARY_DIR}/aster_audit_audio.cpp")
file(CONFIGURE OUTPUT "${audit_audio}" CONTENT "${audio_source}" @ONLY)
set_source_files_properties("${audio}" TARGET_DIRECTORY Android PROPERTIES HEADER_FILE_ONLY TRUE)
file(READ "${A7_BRIDGE_SOURCE}/src/dynarmic_host.h" host_header)
foreach(name IN ITEMS Base Stride Size)
    string(REGEX MATCH "kStack${name} = (0x[0-9a-fA-F]+)" match "${host_header}")
    if(NOT match)
        message(FATAL_ERROR "Cannot read guest stack ${name}")
    endif()
    string(TOUPPER "${name}" upper)
    target_compile_definitions(Android PRIVATE "ASTER_STACK_${upper}=${CMAKE_MATCH_1}")
endforeach()
target_include_directories(Android PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}" "${CMAKE_CURRENT_BINARY_DIR}")
target_sources(Android PRIVATE "${audit_host}" "${audit_libc}" "${audit_audio}" aster_zlib.cpp aster_gles.cpp aster_libc.cpp aster_dl.cpp)
if(ASTER_GAME_RUNTIME)
    if(ASTER_RUNTIME_DIAGNOSTICS)
        target_compile_definitions(Android PRIVATE ASTER_RUNTIME_DIAGNOSTICS=1)
    endif()
    if(NOT ASTER_INCLUDE_COMPANIONS OR NOT EXISTS "${ASTER_CONTRACT_DIR}/aster_jni_contract.inc")
        message(FATAL_ERROR "Game runtime requires companion assets and generated JNI contracts")
    endif()
    target_include_directories(Android PRIVATE "${ASTER_CONTRACT_DIR}")
    if(NOT EXISTS "${ASTER_ASTC_SOURCE}/include/astc-codec/astc-codec.h")
        message(FATAL_ERROR "Game runtime requires ASTER_ASTC_SOURCE (google/astc-codec)")
    endif()
    target_include_directories(Android PRIVATE "${ASTER_ASTC_SOURCE}" "${ASTER_ASTC_SOURCE}/include")
    foreach(unit IN ITEMS astc_file codec endpoint_codec footprint integer_sequence_codec
        intermediate_astc_block logical_astc_block partition physical_astc_block quantization weight_infill)
        target_sources(Android PRIVATE "${ASTER_ASTC_SOURCE}/src/decoder/${unit}.cc")
    endforeach()
    target_sources(Android PRIVATE ../arm64-runtime/runtime.cpp)
    set_target_properties(Android PROPERTIES OUTPUT_NAME Src)
else()
    target_sources(Android PRIVATE probe.cpp)
endif()
target_link_libraries(Android PRIVATE GLESv1_CM)
