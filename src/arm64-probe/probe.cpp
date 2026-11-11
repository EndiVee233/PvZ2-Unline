// SPDX-License-Identifier: GPL-3.0-or-later
#include "dynarmic_host.h"
#include "aster_gles.h"
#include "aster_libc.h"
#include "aster_dl.h"
#include "aster_zlib.h"
#include "jni_fake_env.h"

#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <bit>
#include <cstdio>
#include <jni.h>
#include <mutex>
#include <string>

namespace {
constexpr char guestAsset[] = "guest_libs/libSrc_a32.so";
// v163 ARM32 leaf function. It reads the diamond count from a supplied profile.
constexpr uint32_t getterOffset = 0x706a10;
constexpr uint32_t getterSize = 48;

bool checkGameJni(JNIEnv* env, DynarmicHost& host) {
    auto& bridge = FakeJniEnv::Instance();
    JavaVM* vm = nullptr;
    if (env->GetJavaVM(&vm) != JNI_OK) return false;
    bridge.SetJavaVM(vm);
    bridge.AttachHostEnv(env);
    jclass owner = env->FindClass("com/popcap/SexyAppFramework/AndroidGameApp");
    if (!owner || !bridge.CacheClassLoader(env, owner)) return false;
    constexpr const char* initializeSignature =
        "(Lcom/popcap/SexyAppFramework/AndroidSurfaceView;Lcom/popcap/SexyAppFramework/AndroidHttpProxy;Landroid/content/pm/PackageManager;)Z";
    const JNINativeMethod declarations[] = {
        {const_cast<char*>("Native_GameAppInitialize"), const_cast<char*>(initializeSignature), nullptr},
        {const_cast<char*>("Native_GameAppTeardown"), const_cast<char*>("()V"), nullptr}
    };
    if (!bridge.DeclareNatives(env, owner, declarations, std::size(declarations)) ||
        !bridge.Init(host) || !bridge.BeginNativeCall(env)) return false;
    const uint32_t function = host.FindLibrarySymbol("libSrc.so", "JNI_OnLoad");
    const uint32_t version = host.RunFunction(function, {bridge.VmTableGuestAddr(), 0});
    const bool registered = bridge.FindNative(env, owner, "Native_GameAppInitialize", initializeSignature)
        && bridge.FindNative(env, owner, "Native_GameAppTeardown", "()V");
    __android_log_print(ANDROID_LOG_INFO, "AsterArm64Probe",
        "Aster JNI_OnLoad version=0x%x native-methods-registered=%d", version, registered);
    bool companionJni = true;
#ifdef ASTER_INITIALIZE_COMPANIONS
    for (const char* name : {"libczProject.so", "libHookPVZ2.so"}) {
        const auto entry = host.FindLibrarySymbol(name,"JNI_OnLoad");
        const auto result = entry ? host.RunFunction(entry,{bridge.VmTableGuestAddr(),0}) : 0;
        __android_log_print(ANDROID_LOG_INFO,"AsterArm64Probe","Companion JNI_OnLoad: %s version=0x%x",name,result);
        companionJni = companionJni && result == JNI_VERSION_1_6;
    }
#endif
    bridge.EndNativeCall();
    const bool success = version == JNI_VERSION_1_6 && registered && companionJni &&
        !bridge.HasFailed() && !host.HasFailed() && !env->ExceptionCheck();
    bridge.ReleaseCurrentThread();
    env->DeleteLocalRef(owner);
    return success;
}

bool runGetter(AAssetManager* assets) {
    DynarmicHost host;
    if (!host.Initialize()) return false;
    AAsset* asset = AAssetManager_open(assets, guestAsset, AASSET_MODE_RANDOM);
    if (!asset) return false;
    uint32_t words[getterSize / sizeof(uint32_t)];
    const bool read = AAsset_seek64(asset, getterOffset, SEEK_SET) == getterOffset &&
                      AAsset_read(asset, words, sizeof(words)) == sizeof(words);
    AAsset_close(asset);
    if (!read || words[0] != 0xe59030a4 || words[11] != 0xe12fff1e) return false;

    const uint32_t code = host.GuestAlloc(getterSize);
    const uint32_t profile = host.GuestAlloc(0xa8);
    if (!code || !profile) return false;
    for (uint32_t i = 0; i < getterSize / sizeof(uint32_t); ++i) {
        host.MemoryWrite32(code + 4 * i, words[i]);
    }
    host.AddExecutableRange(code, getterSize);
    constexpr uint32_t key = 0x13579bdf;
    host.MemoryWrite32(profile + 0xa4, key);
    for (const uint32_t expected : {0u, 76u, 123456u}) {
        host.MemoryWrite32(profile + 0xa0, std::rotl(expected ^ key, int(key & 31)));
        if (host.RunFunction(code, {profile}) != expected || host.HasFailed()) return false;
    }
    return true;
}
}

static jstring runProbe(JNIEnv* env, jobject manager, jstring cacheDirectory) {
    static_assert(sizeof(void*) == 8);
    if (!cacheDirectory) return env->NewStringUTF("Aster ARM64 probe: cache directory missing");
    const char* directory = env->GetStringUTFChars(cacheDirectory, nullptr);
    if (!directory) return nullptr;
    configureAsterTemporaryFiles(directory);
    env->ReleaseStringUTFChars(cacheDirectory, directory);
    AAssetManager* assets = AAssetManager_fromJava(env, manager);
    if (!assets) return env->NewStringUTF("Aster ARM64 probe: asset manager unavailable");
    const bool getter = runGetter(assets);
    if (!getter) return env->NewStringUTF("Aster ARM64 probe: ARM32 getter failed");
    auto owner = std::make_unique<DynarmicHost>();
    auto& loader = *owner;
    if (!loader.Initialize()) return env->NewStringUTF("Aster ARM64 probe: host initialization failed");
    registerAsterZlib(loader);
    if (!checkAsterZlib(loader)) return env->NewStringUTF("Aster ARM64 probe: zlib ABI check failed");
    registerAsterGles(loader);
    const bool graphics = checkAsterGles(loader);
    registerAsterLibc(loader);
    const bool libc = checkAsterLibc(loader);
    if (!checkAsterThreads(loader)) return env->NewStringUTF("Aster ARM64 probe: thread ABI check failed");
    if (!checkAsterPosix(loader)) return env->NewStringUTF("Aster ARM64 probe: POSIX ABI check failed");
    if (!checkAsterLocale(loader)) return env->NewStringUTF("Aster ARM64 probe: locale and conversion ABI check failed");
    if (!registerAsterDynamicLoader(loader, assets)) return env->NewStringUTF("Aster ARM64 probe: library catalog failed");
    if (!checkAsterDynamicLoader(loader)) return env->NewStringUTF("Aster ARM64 probe: dynamic loader ABI check failed");
    if (!checkAsterMemory(loader)) return env->NewStringUTF("Aster ARM64 probe: memory mapping ABI check failed");
    const bool relocated = loader.LoadGuestLibraries(assets);
    if (!graphics) return env->NewStringUTF("Aster ARM64 probe: ARM32 getter and zlib passed, GLES offscreen check failed");
    if (!libc) return env->NewStringUTF("Aster ARM64 probe: libc ABI check failed");
    if (relocated) {
        if (!checkAsterLibraryQueries(loader)) return env->NewStringUTF("Aster ARM64 probe: library queries failed");
        const bool initialized = loader.RunLibraryConstructors("libSrc.so");
        if (!initialized) return env->NewStringUTF("Aster ARM64 probe: guest constructor initialization failed");
#ifdef ASTER_INITIALIZE_COMPANIONS
        // GLShim creates detached, process-lifetime decoding workers. Retain
        // their guest address space, matching Android's shared-library lifetime.
        // Instrumentation results are cached, so this occurs once per process.
        (void)owner.release();
        for (const char* name : {"libczProject.so", "libHookPVZ2.so", "libRestart.so", "libPresetEditor.so", "libAsterRgbaPilot.so"}) {
            __android_log_print(ANDROID_LOG_INFO,"AsterArm64Probe","Starting companion constructors: %s",name);
            if (!loader.RunLibraryConstructors(name))
                return env->NewStringUTF("Aster ARM64 probe: companion constructor initialization failed");
        }
        if (!checkAsterGlesShim(loader)) return env->NewStringUTF("Aster ARM64 probe: companion texture upload failed");
#endif
        return env->NewStringUTF(checkGameJni(env, loader)
#ifdef ASTER_INITIALIZE_COMPANIONS
            ? "Aster ARM64 probe: all six libraries relocated/initialized, texture upload and game/companion JNI_OnLoad passed"
#else
            ? "Aster ARM64 probe: ABI, relocation, constructors and game JNI_OnLoad passed"
#endif
            : "Aster ARM64 probe: ELF and constructors passed, game JNI_OnLoad failed");
    }
    return env->NewStringUTF(relocated
        ? "Aster ARM64 probe: ARM32 getter, zlib, GLES and libc passed, guest ELF imports resolved"
        : "Aster ARM64 probe: ARM32 getter, zlib, GLES and libc passed, guest ELF relocation incomplete");
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_pvz2unline_arm64probe_ProbeActivity_probe(JNIEnv* env, jclass, jobject manager, jstring cacheDirectory) {
    // FakeJniEnv binds to one guest runtime per process. Cache the diagnostic
    // outcome so reopening the Activity cannot reuse a destroyed guest address space.
    static std::mutex mutex;
    static bool attempted = false;
    static std::string result;
    std::lock_guard lock(mutex);
    if (!attempted) {
        attempted = true;
        jstring message = runProbe(env, manager, cacheDirectory);
        if (env->ExceptionCheck()) {
            env->ExceptionDescribe();
            env->ExceptionClear();
            result = "Aster ARM64 probe: Java exception during guest initialization";
        } else if (message) {
            const char* text = env->GetStringUTFChars(message, nullptr);
            if (!text) return nullptr;
            result = text;
            env->ReleaseStringUTFChars(message, text);
            env->DeleteLocalRef(message);
        } else {
            result = "Aster ARM64 probe: initialization returned no result";
        }
    }
    return env->NewStringUTF(result.c_str());
}
