// All engine calls execute on the game's existing event thread. No STL ABI sharing.
using U=unsigned;using P=unsigned char*;using I=int;using U64=unsigned long long;
template<class T>T& at(P p,U o){return *reinterpret_cast<T*>(p+o);}
template<class R,class...A>R call(U b,U o,A...a){return reinterpret_cast<R(*)(A...)>(b+o)(a...);}
#include "npc_presets.h"
static P manager(U b){return call<P>(b,0x7fa754);}
static P profile(U b){return call<P>(b,0x7a98dc,call<P>(b,0x1df738));}
static U owner(U b){return at<U>(call<P>(b,0x1df738),0x74);}
static void scene(U b,U s){P g=at<P>(reinterpret_cast<P>(b),0x1835eec);call<void>(b,0x352498,g,s,0,1);}
static bool regular(U b){P p=profile(b);return p&&at<U>(p,0x75c)>=9;}
static const NpcPreset* npc(U id){for(U i=0;i<NPC_COUNT;++i)if(NPCS[i].id==id)return NPCS+i;return nullptr;}
static void bytes(P d,const unsigned char*s,U n){for(U i=0;i<n;++i)d[i]=s[i];}
static void narrow(U b,P dst,const char*src){char a=0;call<void>(b,0x14ed0e1,dst,src,&a);}
static void release(U b,P value,bool wide=false){if(value){char a=0;call<void>(b,wide?0x14ea239:0x14ebf59,value-12,&a);}}
static void log(U b,const char*what,U a=0,U c=0){call<I>(b,0x147adc,4,"OfflinePvP","%s a=%u b=%u",what,a,c);}
static void starter(U b,P m,const char*name,U count,bool skill){
 P key=nullptr;narrow(b,reinterpret_cast<P>(&key),name);
 if(!call<P>(b,skill?0x1046764:0x104673c,m,&key)){
  U record[5]={reinterpret_cast<U>(key),1,1,count,1};
  call<P>(b,skill?0x1048dcc:0x1048f44,m,record);
 }
 release(b,key);
}
#include "economy.h"
static void neighbors(U b,P m){
 if(!regular(b))return;
 for(U i=0;i<NPC_COUNT;++i){const NpcPreset& n=NPCS[i];
  bool occupied=false;P begin=at<P>(m,0x110),end=at<P>(m,0x114);
  if(begin&&end>=begin&&U(end-begin)<=64*256){
   for(P p=begin;p<end;p+=64)if(at<U>(p,48)==n.zone&&at<U>(p,52)==n.position){occupied=true;break;}
  }
  if(occupied)continue;
  alignas(8) U record[16]={n.id,0,n.id,0,0,n.level,1000,2000,100,2000,40,20,n.zone,n.position,1,0};
  char alloc=0;call<void>(b,0x14eb451,reinterpret_cast<P>(record)+16,n.name,&alloc);
  call<void>(b,0x1046a04,m,record);
  release(b,reinterpret_cast<P>(record[4]),true);
 }
 starter(b,m,"pvp_change",0,false);
 starter(b,m,"pvpskill_zombiefood",0,true);
 starter(b,m,"pvpskill_aid",0,true);
 starter(b,m,"pvpskill_invisible",0,true);
 starter(b,m,"pvpskill_rage",0,true);
 offlineEconomyInit(b);
 // Server map replies normally supply this result field. -1 suppresses the
 // original Evil Dave introduction altogether. 0 makes the original pending
 // introduction eligible; its callback still records completion itself.
 if(!at<unsigned char>(profile(b),0x780)&&at<I>(m,0x15c)<0)at<I>(m,0x15c)=0;
 log(b,"neighbors-ready",at<U>(profile(b),0x75c),U(at<P>(m,0x114)-at<P>(m,0x110))/64);
}
struct Pos{U type,row,col;};
struct Info{U type,level,avatar,length;char signature[128];};
struct Store{U magic,version,user,positions,infos,hash;Pos pos[128];Info info[128];};
static U hash(const Store& s){const unsigned char*p=reinterpret_cast<const unsigned char*>(&s);U h=2166136261u;for(U i=0;i<sizeof(s);++i)if(i<20||i>=24)h=(h^p[i])*16777619u;return h;}
static bool valid(const Store&s,U id){
 if(s.magic!=0x4f505650||s.version!=1||s.user!=id||s.positions>128||s.infos>128||s.hash!=hash(s))return false;
 for(U i=0;i<s.positions;++i)if(s.pos[i].row>=5||s.pos[i].col>=9||s.pos[i].type>4096)return false;
 for(U i=0;i<s.infos;++i)if(s.info[i].length>=128||s.info[i].signature[s.info[i].length]||s.info[i].type>4096||s.info[i].level>20)return false;
 return true;
}
static void path(U id,char*out,bool temp=false){
 const char*prefix="/data/data/com.popcap.pvz2cthd.reconstruction/files/userdata/offline-pvp-";
 U n=0;while(prefix[n]){out[n]=prefix[n];++n;}const char*digits="0123456789abcdef";
 for(I i=7;i>=0;--i)out[n++]=digits[(id>>(i*4))&15];
 const char*s=temp?".def.tmp":".def";while(*s)out[n++]=*s++;out[n]=0;
}
static bool capture(U b,P data,Store& s){
 s.magic=0x4f505650;s.version=1;s.user=owner(b);
 P p=at<P>(data,4),e=at<P>(data,8),i=at<P>(data,16),ie=at<P>(data,20);
 if((p&&e<p)||(i&&ie<i)||U(e-p)%12||U(ie-i)%16||U(e-p)>128*12||U(ie-i)>128*16)return false;
 s.positions=U(e-p)/12;s.infos=U(ie-i)/16;
 for(U k=0;k<s.positions;++k)s.pos[k]=*reinterpret_cast<Pos*>(p+k*12);
 for(U k=0;k<s.infos;++k){P r=i+k*16;P text=at<P>(r,12);if(!text)return false;U len=at<U>(text-12,0);if(len>=128)return false;
  s.info[k].type=at<U>(r,0);s.info[k].level=at<U>(r,4);s.info[k].avatar=at<U>(r,8);s.info[k].length=len;
  bytes(reinterpret_cast<P>(s.info[k].signature),text,len);s.info[k].signature[len]=0;
 }
 s.hash=hash(s);return valid(s,s.user);
}
static bool writeStore(U b,Store&s){
 char tmp[160],dst[160];path(s.user,tmp,true);path(s.user,dst);
 I fd=call<I>(b,0x148448,tmp,0x241,0600);if(fd<0)return false;
 U done=0;while(done<sizeof(s)){I n=call<I>(b,0x1485d4,fd,reinterpret_cast<P>(&s)+done,sizeof(s)-done);if(n<=0)break;done+=U(n);}
 bool ok=done==sizeof(s)&&call<I>(b,0x1485e0,fd)==0;
 if(call<I>(b,0x147b90,fd)!=0)ok=false;
 if(ok)ok=call<I>(b,0x147e6c,tmp,dst)==0;
 if(!ok)call<I>(b,0x148424,tmp);return ok;
}
static bool readStore(U b,Store&s){
 char file[160];path(owner(b),file);I fd=call<I>(b,0x148448,file,0,0);if(fd<0)return false;
 U done=0;while(done<sizeof(s)){I n=call<I>(b,0x148460,fd,reinterpret_cast<P>(&s)+done,sizeof(s)-done);if(n<=0)break;done+=U(n);}
 char tail;I extra=call<I>(b,0x148460,fd,&tail,1);call<I>(b,0x147b90,fd);
 return done==sizeof(s)&&extra==0&&valid(s,owner(b));
}
static void clear(U b,P d){
 P p=at<P>(d,4),i=at<P>(d,16),ie=at<P>(d,20);
 if(i&&ie>=i&&U(ie-i)<=128*16)for(P q=i;q<ie;q+=16)release(b,at<P>(q,12));
 if(p)call<void>(b,0x14c2e95,p);if(i)call<void>(b,0x14c2e95,i);
 for(U o=4;o<28;o+=4)at<U>(d,o)=0;
}
static void apply(U b,P d,const Store&s){
 clear(b,d);
 if(s.positions){P p=call<P>(b,0x14c1a7d,s.positions*12);bytes(p,reinterpret_cast<const unsigned char*>(s.pos),s.positions*12);at<P>(d,4)=p;at<P>(d,8)=at<P>(d,12)=p+s.positions*12;}
 if(s.infos){P p=call<P>(b,0x14c1a7d,s.infos*16);for(U k=0;k<s.infos;++k){P r=p+16*k;at<U>(r,0)=s.info[k].type;at<U>(r,4)=s.info[k].level;at<U>(r,8)=s.info[k].avatar;narrow(b,r+12,s.info[k].signature);}
  at<P>(d,16)=p;at<P>(d,20)=at<P>(d,24)=p+s.infos*16;
 }
 at<U>(d,28)=1;
}
static void preset(U b,P m,const NpcPreset&n){
 Store s{};s.user=owner(b);s.positions=n.count;
 for(U k=0;k<n.count;++k){s.pos[k]={n.plants[k][0],n.plants[k][1],n.plants[k][2]};bool seen=false;for(U j=0;j<s.infos;++j)if(s.info[j].type==s.pos[k].type)seen=true;
  if(!seen){Info&v=s.info[s.infos++];v.type=s.pos[k].type;v.level=1;}
 }
 apply(b,m+0x80,s);
}
extern "C" __attribute__((section(".text.entry"))) void offlineGarden(U b){neighbors(b,manager(b));scene(b,25);}
extern "C" void offlineOwn(U b){P m=manager(b);Store s{};if(readStore(b,s)){apply(b,m+0x80,s);log(b,"defense-loaded",s.positions,s.infos);}else{clear(b,m+0x80);log(b,"defense-new");}call<void>(b,0x85e7d8);}
extern "C" void offlineSave(U b,P network,P json,U zone,U type){
 if(!regular(b)){call<void>(b,0xf87cc4,network,json,zone,type);return;}
 Store s{};if(capture(b,manager(b)+0x80,s)&&writeStore(b,s)){log(b,"defense-saved",s.positions,s.infos);scene(b,25);}else log(b,"defense-save-failed");
}
extern "C" void offlineInfo(U b,P m,U a,U id,U kind){
 const NpcPreset*n=npc(id);if(n&&kind==2&&regular(b)){log(b,"view-neighbor",id,n->count);preset(b,m,*n);call<void>(b,0x85e874);return;}
 call<void>(b,0xf79d74);P net=call<P>(b,0xf7a070);call<void>(b,0xf87154,net,a,id,kind);
}
extern "C" void offlineAttack(U b,P m,U id,U reason,U unused){
 const NpcPreset*n=npc(id);if(n&&regular(b)){log(b,"attack-neighbor",id,n->count);preset(b,m,*n);call<void>(b,0x85e9a8);return;}
 call<void>(b,0xf79d74);P net=call<P>(b,0xf7a070);call<void>(b,0xf87710,net,id,reason,at<U>(m,0x104),at<U64>(m,0x108));
}
extern "C" void __aeabi_memclr4(void* p,U n){volatile unsigned char*d=static_cast<volatile unsigned char*>(p);while(n--)*d++=0;}
extern "C" void __aeabi_memclr8(void* p,U n){__aeabi_memclr4(p,n);}
extern "C" void __aeabi_memclr(void* p,U n){__aeabi_memclr4(p,n);}
extern "C" void __aeabi_memcpy8(void* dst,const void* src,U n){volatile unsigned char*d=static_cast<volatile unsigned char*>(dst);const volatile unsigned char*s=static_cast<const volatile unsigned char*>(src);while(n--)*d++=*s++;}
