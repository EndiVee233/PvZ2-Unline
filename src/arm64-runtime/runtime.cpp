// SPDX-License-Identifier: GPL-3.0-or-later
#include "dynarmic_host.h"
#include "jni_fake_env.h"
#include "thunk_manager.h"
#include "thunks_opensles.h"
#include "thunks_gl.h"
#include "aster_libc.h"
#include "aster_dl.h"
#include "aster_gles.h"
#include "aster_zlib.h"
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <jni.h>
#include <atomic>
#include <bit>
#include <condition_variable>
#include <chrono>
#include <cstring>
#include <exception>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include <array>
#include <astc-codec/astc-codec.h>

extern JavaVM* g_jvm;
namespace {
constexpr const char* libraries[]={"libSrc.so","libczProject.so","libHookPVZ2.so",
    "libRestart.so","libPresetEditor.so","libAsterRgbaPilot.so"};
#ifdef ASTER_RUNTIME_DIAGNOSTICS
class AsterRuntimeHost final : public DynarmicHost {
public:
    uint64_t GetTicksRemaining() override {return 1000000;}
    void AddTicks(uint64_t) override {
        using Clock=std::chrono::steady_clock;
        static thread_local auto last=Clock::now();
        const auto now=Clock::now();
        if (now-last<std::chrono::seconds(2)) return;
        last=now;
        const auto& r=CurrentJit().Regs();
        __android_log_print(ANDROID_LOG_INFO,"AsterArm64PC",
            "Guest PC=%08x LR=%08x R0=%08x R1=%08x R2=%08x R3=%08x SP=%08x",r[15],r[14],r[0],r[1],r[2],r[3],r[13]);

    }
};
#else
using AsterRuntimeHost=DynarmicHost;
#endif
DynarmicHost* runtime=nullptr; // Same lifetime as detached decoder/audio workers.
std::mutex loadMutex;
std::condition_variable loadChanged;
enum class State { Empty,Loading,Ready,Failed };
State loadState=State::Empty;
std::thread::id loadThread;
jobject assetsOwner=nullptr;
std::atomic<bool> audioStarted=false;

void fail(JNIEnv* env,const char* message) {
    __android_log_print(ANDROID_LOG_ERROR,"AsterArm64","%s",message);
    if (env->ExceptionCheck()) return;
    const auto type=env->FindClass("java/lang/IllegalStateException");
    if (type) { env->ThrowNew(type,message);env->DeleteLocalRef(type); }
}
struct Frame {
    bool active;
    explicit Frame(JNIEnv* env) : active(false) {
        if (runtime) { runtime->CurrentJit();active=FakeJniEnv::Instance().BeginNativeCall(env); }
    }
    ~Frame() { if (active) FakeJniEnv::Instance().EndNativeCall(); }
};
uint64_t resourceHash(const uint8_t* bytes,uint32_t size,int32_t width,int32_t height,int32_t format,int32_t packed) {
    uint64_t hash=1469598103934665603ULL;
    for (uint32_t i=0;i<size;++i) {hash^=bytes[i];hash*=1099511628211ULL;}
    hash^=uint64_t(width)*73856093ULL;hash^=uint64_t(height)*19349663ULL;
    hash^=uint64_t(format)*83492791ULL;hash^=uint64_t(packed)*2654435761ULL;
    return hash;
}
uint32_t registerResourceHash(DynarmicHost& host) {
    return host.GetThunkManager().RegisterThunk("aster_resource_hash_native",[](Dynarmic::A32::Jit& jit,DynarmicHost& guest) {
        const auto args=jit.Regs();
        if (uint64_t(args[0])+args[1]>guest.GetGuestMemorySize() || (!args[0] && args[1])) {
            guest.Fail("Invalid resource hash input");return;
        }
        const auto value=resourceHash(guest.GetGuestMemoryBase()+args[0],args[1],int32_t(args[2]),int32_t(args[3]),
            int32_t(guest.ReadStackWord(jit,0)),int32_t(guest.ReadStackWord(jit,1)));
        jit.Regs()[0]=uint32_t(value);jit.Regs()[1]=uint32_t(value>>32);
    });
}
bool installResourceHash(DynarmicHost& host,uint32_t replacement) {
    // Static v163 GLShim helper; reject another binary rather than guessing.
    constexpr uint32_t function=0x4504e98c;
    constexpr uint8_t expected[]={0xf0,0xb5,0x03,0xaf,0x2d,0xe9,0x00,0x07,0xd7,0xe9,0x02,0xa8,0x40,0xf6,0xb0,0x7c};
    if (!replacement || memcmp(host.GetGuestMemoryBase()+function,expected,sizeof(expected))) return false;
    const auto input=host.GuestAlloc(4096);
    if (!input) return false;
    for (unsigned i=0;i<4096;++i) host.MemoryWrite8(input+i,uint8_t(i*37));
    bool passed=true;
    for (uint32_t size : {0u,4u,4096u}) {
        const std::vector<uint32_t> args{input,size,512,128,0x93b0,size};
        const uint32_t low=host.RunFunction(function|1,args),high=host.CurrentJit().Regs()[1];
        const auto value=resourceHash(host.GetGuestMemoryBase()+input,size,512,128,0x93b0,size);
        passed=passed && (uint64_t(low)|(uint64_t(high)<<32))==value && !host.HasFailed();
    }
    host.GuestFree(input);
    if (!passed) return false;
    host.MemoryWrite32(function,0xf000f8df); // Thumb ldr.w pc,[pc,#0]
    host.MemoryWrite32(function+4,replacement);
    host.InvalidateGuestCode(function,8);
    __android_log_print(ANDROID_LOG_INFO,"AsterArm64","Native resource hash verified against A32 (3 cases) and installed");
    return true;
}
uint32_t registerResourceCodec(DynarmicHost& host) {
    return host.GetThunkManager().RegisterThunk("aster_astc_native",[](Dynarmic::A32::Jit& jit,DynarmicHost& guest) {
        const auto args=jit.Regs();
        const auto footprint=guest.ReadStackWord(jit,0),target=guest.ReadStackWord(jit,1);
        const auto size=guest.ReadStackWord(jit,2),stride=guest.ReadStackWord(jit,3);
        jit.Regs()[0]=0;
        if (!args[0] || !target || uint64_t(args[0])+args[1]>guest.GetGuestMemorySize()
            || uint64_t(target)+size>guest.GetGuestMemorySize()
            || footprint>=unsigned(astc_codec::FootprintType::kCount)) return;
        jit.Regs()[0]=astc_codec::ASTCDecompressToRGBA(guest.GetGuestMemoryBase()+args[0],args[1],args[2],args[3],
            static_cast<astc_codec::FootprintType>(footprint),guest.GetGuestMemoryBase()+target,size,stride);
    });
}
bool installResourceCodec(DynarmicHost& host,uint32_t replacement) {
    constexpr uint32_t functions[]={0x45051eb0,0x47047108};
    constexpr uint8_t expected[]={0xf0,0xb5,0x03,0xaf,0x4d,0xf8,0x04,0x8d,0x8a,0xb0,0x0e,0x46,0xb9,0x68,0x04,0x46};
    for (auto fn : functions) if (memcmp(host.GetGuestMemoryBase()+fn,expected,sizeof(expected))) return false;
    const auto data=host.GuestAlloc(16),output=host.GuestAlloc(6*6*4);
    if (!data || !output) return false;
    // ASTC LDR void-extent block with opaque red UNORM16 channels.
    constexpr uint8_t block[]={0xfc,0xfd,0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff,0,0,0,0,0xff,0xff};
    memcpy(host.GetGuestMemoryBase()+data,block,16);
    bool passed=true;
    for (auto fn : functions) for (const auto fp : {astc_codec::FootprintType::k4x4,astc_codec::FootprintType::k5x5,astc_codec::FootprintType::k6x6}) {
        const uint32_t dimension=fp==astc_codec::FootprintType::k4x4 ? 4 : fp==astc_codec::FootprintType::k5x5 ? 5 : 6;
        const uint32_t size=dimension*dimension*4;
        memset(host.GetGuestMemoryBase()+output,0,size);
        const auto decoded=host.RunFunction(fn|1,{data,16,dimension,dimension,uint32_t(fp),output,size,dimension*4});
        std::array<uint8_t,6*6*4> reference{};
        const bool native=astc_codec::ASTCDecompressToRGBA(block,16,dimension,dimension,fp,reference.data(),size,dimension*4);
        passed=passed && decoded==1 && native && !host.HasFailed()
            && memcmp(reference.data(),host.GetGuestMemoryBase()+output,size)==0
            && reference[0]==255 && reference[1]==0 && reference[2]==0 && reference[3]==255;
    }
    host.GuestFree(data);host.GuestFree(output);
    if (!passed) return false;
    for (auto fn : functions) {
        host.MemoryWrite32(fn,0xf000f8df);host.MemoryWrite32(fn+4,replacement);host.InvalidateGuestCode(fn,8);
    }
    __android_log_print(ANDROID_LOG_INFO,"AsterArm64","Native ASTC verified against both A32 codecs (4x4/5x5/6x6) and installed");
    return true;
}
#ifdef ASTER_RUNTIME_DIAGNOSTICS
uint32_t animationTraceTrampoline=0;
uint32_t registerAnimationTrace(DynarmicHost& host) {
    return host.GetThunkManager().RegisterThunk("aster_animation_copy_trace",[](Dynarmic::A32::Jit& jit,DynarmicHost& guest) {
        const auto args=jit.Regs();
        const auto source=args[1];
        static std::atomic<unsigned> copies{0};
        const bool trace=copies.fetch_add(1)<32 || !source;
        if(trace)__android_log_print(ANDROID_LOG_INFO,"AsterAnim","Copy entry source=%08x target=%08x caller=%08x",source,args[0],args[14]);
        if (trace && source>=0x50000000 && source<0x7ffbff00) {
            char name[257]{};
            const auto text=guest.MemoryRead32(source+0x3c);
            if(text>=0x50000000 && text<0x7ffbff00)
                for(unsigned i=0;i<256;++i) {name[i]=char(guest.MemoryRead8(text+i));if(!name[i])break;}
            __android_log_print(ANDROID_LOG_INFO,"AsterAnim","Copy source=%08x target=%08x file='%s' instance=%08x def=%08x caller=%08x",source,args[0],name,guest.MemoryRead32(source+0x40),guest.MemoryRead32(source+0x44),args[14]);
        }
        jit.Regs()[0]=guest.RunFunction(animationTraceTrampoline,{args[0],args[1],args[2],args[3]});
    });
}
bool installAnimationTrace(DynarmicHost& host,uint32_t replacement) {
    constexpr uint32_t function=0x4118d744;
    if(host.MemoryRead32(function)!=0xe92d4ff0 || host.MemoryRead32(function+4)!=0xe28db020) return false;
    animationTraceTrampoline=host.GuestAlloc(16,4);
    if(!animationTraceTrampoline)return false;
    host.AddExecutableRange(animationTraceTrampoline,16);
    host.MemoryWrite32(animationTraceTrampoline,host.MemoryRead32(function));
    host.MemoryWrite32(animationTraceTrampoline+4,host.MemoryRead32(function+4));
    host.MemoryWrite32(animationTraceTrampoline+8,0xe51ff004);
    host.MemoryWrite32(animationTraceTrampoline+12,function+8);
    host.MemoryWrite32(function,0xe51ff004);host.MemoryWrite32(function+4,replacement);
    host.InvalidateGuestCode(function,8);
    __android_log_print(ANDROID_LOG_INFO,"AsterAnim","Copy trace installed at %08x -> %08x via %08x",function,replacement,animationTraceTrampoline);
    return true;
}
#endif
bool bootstrap(JNIEnv* env) {
    if (env->PushLocalFrame(32)!=JNI_OK) return false;
    struct Pop { JNIEnv* env;~Pop(){env->PopLocalFrame(nullptr);} } pop{env};
    const auto thread=env->FindClass("android/app/ActivityThread");
    if (!thread) return false;
    const auto current=env->GetStaticMethodID(thread,"currentApplication","()Landroid/app/Application;");
    if (!current) return false;
    const auto app=env->CallStaticObjectMethod(thread,current);
    if (!app || env->ExceptionCheck()) return false;
    const auto context=env->FindClass("android/content/Context");
    const auto getAssets=env->GetMethodID(context,"getAssets","()Landroid/content/res/AssetManager;");
    const auto getCache=env->GetMethodID(context,"getCacheDir","()Ljava/io/File;");
    const auto file=env->FindClass("java/io/File");
    const auto absolute=env->GetMethodID(file,"getAbsolutePath","()Ljava/lang/String;");
    if (!getAssets || !getCache || !absolute || env->ExceptionCheck()) return false;
    const auto assets=env->CallObjectMethod(app,getAssets);
    const auto cache=env->CallObjectMethod(app,getCache);
    if (!assets || !cache || env->ExceptionCheck()) return false;
    const auto path=static_cast<jstring>(env->CallObjectMethod(cache,absolute));
    if (!path || env->ExceptionCheck()) return false;
    const char* utf=env->GetStringUTFChars(path,nullptr);
    if (!utf) return false;
    configureAsterTemporaryFiles(utf);
    env->ReleaseStringUTFChars(path,utf);
    assetsOwner=env->NewGlobalRef(assets);
    auto* manager=AAssetManager_fromJava(env,assets);
    if (!assetsOwner || !manager) return false;
    runtime=new AsterRuntimeHost;
    if (!runtime->Initialize()) return false;
    registerAsterZlib(*runtime);registerAsterGles(*runtime);registerAsterLibc(*runtime);
    const auto hashThunk=registerResourceHash(*runtime);
    const auto codecThunk=registerResourceCodec(*runtime);
#ifdef ASTER_RUNTIME_DIAGNOSTICS
    const auto animationTrace=registerAnimationTrace(*runtime);
#endif
    if (!registerAsterDynamicLoader(*runtime,manager)) return false;
    auto& jni=FakeJniEnv::Instance();
    if (!jni.Init(*runtime) || !runtime->LoadGuestLibraries(manager)) return false;
    if (!installResourceHash(*runtime,hashThunk)) return false;
    if (!installResourceCodec(*runtime,codecThunk)) return false;
#ifdef ASTER_RUNTIME_DIAGNOSTICS
    if (!installAnimationTrace(*runtime,animationTrace)) return false;
#endif
    Frame frame(env);
    if (!frame.active) return false;
    for (const char* library : libraries) {
        if (!runtime->RunLibraryConstructors(library)) return false;
        const auto entry=runtime->FindLibrarySymbol(library,"JNI_OnLoad");
        if (entry) {
            const auto version=runtime->RunFunction(entry,{jni.VmTableGuestAddr(),0});
            __android_log_print(ANDROID_LOG_INFO,"AsterArm64","Guest JNI_OnLoad %s: 0x%x",library,version);
            if (version!=JNI_VERSION_1_6 || env->ExceptionCheck() || jni.HasFailed() || runtime->HasFailed()) return false;
        }
    }
    __android_log_print(ANDROID_LOG_INFO,"AsterArm64","Runtime loaded; real game initialization pending");
    return true;
}
bool ensureLoaded(JNIEnv* env) {
    {
        std::unique_lock lock(loadMutex);
        while (loadState==State::Loading) {
            if (loadThread==std::this_thread::get_id()) { fail(env,"Recursive Aster ARM64 bootstrap");return false; }
            loadChanged.wait(lock);
        }
        if (loadState==State::Ready) return true;
        if (loadState==State::Failed) { fail(env,"Aster ARM64 bootstrap previously failed");return false; }
        loadState=State::Loading;loadThread=std::this_thread::get_id();
    }
    bool ok=false;
    try { ok=bootstrap(env); }
    catch (const std::exception& error) { fail(env,error.what()); }
    catch (...) { fail(env,"Unknown Aster ARM64 bootstrap exception"); }
    { std::lock_guard lock(loadMutex);loadState=ok?State::Ready:State::Failed;loadThread={}; }
    loadChanged.notify_all();
    if (!ok) fail(env,"Aster ARM64 bootstrap failed; see native log");
    return ok;
}
struct Argument {
    bool wide=false;
    uint64_t bits=0;
    jobject object=nullptr;
    bool reference=false;
    static Argument scalar(uint32_t value) { return {false,value,nullptr,false}; }
    static Argument large(uint64_t value) { return {true,value,nullptr,false}; }
    static Argument ref(jobject value) { return {false,0,value,true}; }
};
struct NativeResult { uint64_t bits=0;jobject object=nullptr; };
struct Contract { const char* owner;const JNINativeMethod* methods;size_t count;jclass cls=nullptr; };
extern Contract contracts[];
extern const size_t contractCount;
std::string mangle(const char* text) {
    std::string result;
    for (;*text;++text) {
        const auto c=static_cast<unsigned char>(*text);
        if (c=='/') result+='_';else if(c=='_') result+="_1";
        else if(c==';') result+="_2";else if(c=='[') result+="_3";
        else if((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')) result+=char(c);
        else { char escaped[8];snprintf(escaped,sizeof(escaped),"_0%04x",unsigned(c));result+=escaped; }
    }
    return result;
}
NativeResult invoke(JNIEnv* env,jobject receiver,size_t classIndex,const char* method,const char* signature,
                    std::initializer_list<Argument> arguments,bool objectReturn) {
    NativeResult result;
    try {
        if (!ensureLoaded(env)) return result;
        if (runtime->HasFailed() || FakeJniEnv::Instance().HasFailed()) { fail(env,"Aster guest runtime has failed");return result; }
        Frame frame(env);
        if (!frame.active) { fail(env,"Cannot enter Aster JNI frame");return result; }
        auto& jni=FakeJniEnv::Instance();
        const auto& contract=contracts[classIndex];
        if (!strcmp(method,"Native_onSurfaceChanged") && arguments.size()==2) {
            const auto width=uint32_t(arguments.begin()[0].bits),height=uint32_t(arguments.begin()[1].bits);
            ThunkManager::s_screenWidth=width;ThunkManager::s_screenHeight=height;
            PublishHostDefaultFramebufferSurfaceSize(width,height);
        }
        auto entry=jni.FindNative(env,contract.cls,method,signature);
        if (!entry) {
            const std::string shortName="Java_"+mangle(contract.owner)+"_"+mangle(method);
            const std::string parameters(signature+1,strchr(signature,')'));
            const auto longName=shortName+"__"+mangle(parameters.c_str());
            for (const char* library : libraries) {
                entry=runtime->FindLibrarySymbol(library,longName);
                if (!entry) entry=runtime->FindLibrarySymbol(library,shortName);
                if (entry) break;
            }
        }
        if (!entry) { fail(env,(std::string("Aster guest JNI missing: ")+contract.owner+"."+method+signature).c_str());return result; }
        // The asynchronous Java resource converter owns a host direct buffer.
        // Its synchronous decoder call may use guest-addressed staging memory;
        // never expose or truncate an arbitrary ARM64 host pointer to A32.
        struct Staging {
            uint32_t address=0;jobject buffer=nullptr;void* output=nullptr;size_t size=0;JNIEnv* env;
            ~Staging(){if(buffer)env->DeleteLocalRef(buffer);if(address)runtime->GuestFree(address);}
        } staging{0,nullptr,nullptr,0,env};
        if (!strcmp(contract.owner,"com/popcap/pvz2cthd/AsterRgbaPilot") && !strcmp(method,"decodeAstc") && arguments.size()==4) {
            const auto target=arguments.begin()[3].object;
            const int32_t width=arguments.begin()[1].bits,height=arguments.begin()[2].bits;
            if (!target || width<=0 || width>4096 || height<=0 || height>128 || width%4 || height%4) return result;
            staging.size=size_t(width)*height*4;
            const auto capacity=env->GetDirectBufferCapacity(target);
            staging.output=env->GetDirectBufferAddress(target);
            if (!staging.output || capacity<jlong(staging.size)) return result;
            staging.address=runtime->GuestAlloc(staging.size);
            if (!staging.address) {fail(env,"Aster decoder staging allocation failed");return result;}
            staging.buffer=env->NewDirectByteBuffer(runtime->GetGuestMemoryBase()+staging.address,staging.size);
            if (!staging.buffer) return result;
        }
        std::vector<uint32_t> words{jni.EnvTableGuestAddr(),jni.AddObjectRef(receiver)};
        size_t argumentIndex=0;
        for (const auto& argument : arguments) {
            if (argument.reference) words.push_back(jni.AddObjectRef(staging.buffer && argumentIndex==3 ? staging.buffer : argument.object));
            else if (argument.wide) {
                if (words.size()%2) words.push_back(0);
                words.push_back(uint32_t(argument.bits));words.push_back(uint32_t(argument.bits>>32));
            } else words.push_back(uint32_t(argument.bits));
            ++argumentIndex;
        }
        if (env->ExceptionCheck() || jni.HasFailed()) return result;
        const bool draw=strcmp(method,"Native_onDrawFrame")==0;
#ifdef ASTER_RUNTIME_DIAGNOSTICS
        if (!draw) __android_log_print(ANDROID_LOG_INFO,"AsterArm64","Calling %s.%s%s",contract.owner,method,signature);
#endif
        const auto low=runtime->RunFunction(entry,words);
        const auto high=runtime->CurrentJit().Regs()[1];
        if (runtime->HasFailed() || jni.HasFailed()) { fail(env,"Aster guest JNI execution failed");return result; }
        result.bits=uint64_t(low)|(uint64_t(high)<<32);
        if (low && staging.address && !env->ExceptionCheck())
            memcpy(staging.output,runtime->GetGuestMemoryBase()+staging.address,staging.size);
        if (objectReturn && low && !env->ExceptionCheck()) result.object=jni.ResolveObject(low);
#ifdef ASTER_RUNTIME_DIAGNOSTICS
        if (!draw) __android_log_print(ANDROID_LOG_INFO,"AsterArm64","Returned %s: 0x%x",method,low);
#endif
        if (!strcmp(method,"Native_GameAppInitialize") && low && !audioStarted.exchange(true)) StartAudioThread(runtime);
        if (draw) { static std::atomic<bool> first=false;if (!first.exchange(true)) __android_log_print(ANDROID_LOG_INFO,"AsterArm64","First real game frame returned"); }
        if (env->ExceptionCheck()) __android_log_print(ANDROID_LOG_ERROR,"AsterArm64","Java exception after %s",method);
    } catch (const std::exception& error) { fail(env,error.what()); }
    catch (...) { fail(env,"Unknown Aster JNI adapter exception"); }
    return result;
}

#include "aster_jni_contract.inc"
}

extern "C" JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM* vm,void*) {
    g_jvm=vm;
    JNIEnv* env=nullptr;
    if (vm->GetEnv(reinterpret_cast<void**>(&env),JNI_VERSION_1_6)!=JNI_OK) return JNI_ERR;
    auto& jni=FakeJniEnv::Instance();jni.SetJavaVM(vm);jni.AttachHostEnv(env);
    for (size_t i=0;i<contractCount;++i) {
        auto& contract=contracts[i];
        const auto cls=env->FindClass(contract.owner);
        if (!cls || env->ExceptionCheck()) return JNI_ERR;
        contract.cls=static_cast<jclass>(env->NewGlobalRef(cls));
        if (!i && !jni.CacheClassLoader(env,cls)) return JNI_ERR;
        if (!contract.cls || env->RegisterNatives(cls,contract.methods,contract.count)!=JNI_OK
            || !jni.DeclareNatives(env,cls,contract.methods,contract.count)) return JNI_ERR;
        env->DeleteLocalRef(cls);
    }
#ifdef ASTER_RUNTIME_DIAGNOSTICS
    constexpr const char* profile="diagnostic";
#else
    constexpr const char* profile="lean";
#endif
    __android_log_print(ANDROID_LOG_INFO,"AsterArm64","Runtime maps-jni-r4 (%s): registered real-game JNI wrappers for %zu classes",profile,contractCount);
    return JNI_VERSION_1_6;
}
