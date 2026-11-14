using U=unsigned;
using P=unsigned char*;
template<class T>static T& at(P p,U n){return *reinterpret_cast<T*>(p+n);}
template<class R,class...A>static R call(U b,U o,A...args){return reinterpret_cast<R(*)(A...)>(b+o)(args...);}
__attribute__((noinline)) static bool sameText(P p,const char* text){
 if(!p)return false;
 U i=0;for(;text[i];++i)if(p[i]!=static_cast<unsigned char>(text[i]))return false;
 return !p[i];
}
#include "../offline-pvp/pvp_music_track.h"
extern "C" U asterPvpMusicTrack(U base){return pvpMusicTrack(base);}
#include "../offline-pvp/research_cards.h"
extern "C" void asterResearchCardRefresh(U b,P ui){
 P holder=call<P>(b,0x1df738);
 P player=holder?call<P>(b,0x7a98dc,holder):nullptr;
 if(!player||at<U>(player,0x75c)<9)return;
 P m=call<P>(b,0x7fa754);
 if(syncResearchCardGrades(b,ui,m))call<void>(b,0x1084a38,ui,at<U>(ui,0xc0));
}
