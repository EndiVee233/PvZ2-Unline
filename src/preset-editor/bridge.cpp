#include <jni.h>
#include <link.h>
#include <cstring>
#include <cstdint>
#include "preset_bridge_addresses.h"
static uintptr_t base;
static int findLibrary(dl_phdr_info* info,size_t,void*){
 const char*n=info->dlpi_name;if(!n)return 0;const char*leaf=strrchr(n,'/');leaf=leaf?leaf+1:n;
 if(strcmp(leaf,"libSrc.so"))return 0;base=info->dlpi_addr;return 1;
}
static bool ready(){if(!base)dl_iterate_phdr(findLibrary,nullptr);return base!=0;}
extern "C" JNIEXPORT jint JNICALL Java_com_popcap_pvz2cthd_PresetEditor_command(JNIEnv*e,jclass,jint cmd,jintArray data){
 if(!ready()||!data)return 0;
 const int size=e->GetArrayLength(data);
 if(size>(cmd==8?1+1000*224:182))return 0;
 jint* input=e->GetIntArrayElements(data,nullptr);
 if(!input)return 0;
 auto run=reinterpret_cast<unsigned(*)(unsigned,unsigned,const unsigned*,unsigned)>(base+EDITOR_COMMAND);
 unsigned result=run(base,cmd,reinterpret_cast<const unsigned*>(input),size);
 e->ReleaseIntArrayElements(data,input,JNI_ABORT);
 return result;
}
extern "C" JNIEXPORT jintArray JNICALL Java_com_popcap_pvz2cthd_PresetEditor_poll(JNIEnv*e,jclass){
 if(!ready())return nullptr;unsigned output[256]{};
 unsigned n=reinterpret_cast<unsigned(*)(unsigned,unsigned*,unsigned)>(base+EDITOR_POLL)(base,output,256);
 if(!n||n>256)return nullptr;jintArray result=e->NewIntArray(n);if(result)e->SetIntArrayRegion(result,0,n,reinterpret_cast<jint*>(output));return result;
}
#ifdef EDITOR_MUSIC_SAMPLE
extern "C" JNIEXPORT jint JNICALL Java_com_popcap_pvz2cthd_PresetEditor_musicSample(JNIEnv*,jclass){
 if(!ready())return 0;
 return reinterpret_cast<unsigned(*)(unsigned)>(base+EDITOR_MUSIC_SAMPLE)(base);
}
#endif
