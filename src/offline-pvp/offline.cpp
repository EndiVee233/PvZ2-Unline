// All engine calls execute on the game's existing event thread. No STL ABI sharing.
using U=unsigned;using P=unsigned char*;using I=int;using U64=unsigned long long;
template<class T>T& at(P p,U o){return *reinterpret_cast<T*>(p+o);}
template<class R,class...A>R call(U b,U o,A...a){return reinterpret_cast<R(*)(A...)>(b+o)(a...);}
#ifdef PVP_RECT_SKILLS
#include "skill_ranges.h"
#endif
#include "npc_presets.h"
#ifdef PVP_EXCHANGE
#include "exchange_presets.h"
#endif
#ifdef PVP_DAVE_ROUNDS
#include "dave_presets.h"
#endif
static P manager(U b){return call<P>(b,0x7fa754);}
static P profile(U b){return call<P>(b,0x7a98dc,call<P>(b,0x1df738));}
static U owner(U b){return at<U>(call<P>(b,0x1df738),0x74);}
static void scene(U b,U s){P g=at<P>(reinterpret_cast<P>(b),0x1835eec);call<void>(b,0x352498,g,s,0,1);}
static bool regular(U b){P p=profile(b);return p&&at<U>(p,0x75c)>=9;}
static const NpcPreset* npc(U id){for(U i=0;i<NPC_COUNT;++i)if(NPCS[i].id==id)return NPCS+i;return nullptr;}
#ifdef PVP_RANDOM_NEIGHBORS
#include "neighbor_generator.h"
static void projectDynamicNeighbor(U b,P m,const NpcPreset&n);
static U neighborAction(U b,P panel,U button);
#endif
static void bytes(P d,const unsigned char*s,U n){for(U i=0;i<n;++i)d[i]=s[i];}
static void narrow(U b,P dst,const char*src){char a=0;call<void>(b,0x14ed0e1,dst,src,&a);}
static void release(U b,P value,bool wide=false){if(value){char a=0;call<void>(b,wide?0x14ea239:0x14ebf59,value-12,&a);}}
static void log(U b,const char*what,U a=0,U c=0){call<I>(b,0x147adc,4,"OfflinePvP","%s a=%u b=%u",what,a,c);}
#ifdef PVP_RESIDENT_NEIGHBORS
#include "residences.h"
#endif
#ifdef PVP_BUSINESS_MAP
#ifdef PVP_REGIONS
static U regionAction(U b,P panel,U button);
static bool regionOpen(U zone);
#endif
#include "businesses.h"
#endif
static void starter(U b,P m,const char*name,U count,bool skill){
 P key=nullptr;narrow(b,reinterpret_cast<P>(&key),name);
 if(!call<P>(b,skill?0x1046764:0x104673c,m,&key)){
  U record[5]={reinterpret_cast<U>(key),1,1,count,1};
  call<P>(b,skill?0x1048dcc:0x1048f44,m,record);
 }
 release(b,key);
}
static void inspectArena(U b);
static void completeLocalBattle(U b);
#ifdef PVP_NPC_RAIDS
static bool raidActive(U b);
static void raidBindArmy(U b,P m);
static void raidQueue(U b,U target);
static void raidTick(U b);
static U raidResult(U b,U stars);
static void raidEnded(U b);
#endif
#ifdef PVP_SILENT_RAIDS
struct Economy;
static bool validSilentRaids(const Economy& s);
static void planSilentRevenge(U b,Economy& next,U target);
static bool startHistoryRevenge(U b,P row,U button);
static bool revengeAllowed(U b,U serial);
static const NeighborEncounter* revengeEncounter(U b,U id);
static void rememberBattleEncounter(U b,const NeighborEncounter& opponent);
static bool markRevengeStarted(U b,Economy& next,U target);
static void clearRevenge();
static bool localRaidOccupier(U b,U64 identity);
#endif
#include "progression_presets.h"
static U campCapacity(U level){return CAMP_SPECS[level>=1&&level<=20?level-1:0].capacity;}
static void applyProgression(U b,P m);
static void tickProgression(U b);
#ifdef PVP_REGIONS
static void projectRegions(U b,P m);
static bool regionOpen(U zone);
static void neighbors(U b,P m);
#endif
static U finishProgressionWithGems(U b,P timer);
#ifdef PVP_EVOLUTION
static void applyEvolution(U b,P m);
static bool ensureEvolution(U b,P m);
static void settleEvolution(U b,P m);
static U finishEvolutionWithGems(U b,P timer);
static bool evolutionFinishPrompt;
#endif
#ifdef PVP_SKILL_RESEARCH
static void applyResearch(U b,P m);
static bool ensureResearch(U b,P m);
static void settleResearch(U b,P m);
static U finishResearchWithGems(U b,P timer);
static bool researchFinishPrompt;
#endif
#include "economy.h"
#ifdef PVP_BUSINESS_PRODUCTION
static bool produceBusinesses(Economy& next,U now);
static void projectBusinessStocks(U b,P m);
#endif
#ifdef PVP_BUSINESS_BATTLE
static U businessProjectionIdentity;
static void projectBusinessOwners(U b,P m){
 if(!regular(b)||!ensureEconomy(b,m))return;
 P begin=at<P>(m,0x110),end=at<P>(m,0x114);U identity=offlineBusinessIdentity(b);
 if(!begin||end<begin||U(end-begin)>64*256||U(end-begin)%64)return;
 for(P p=begin;p<end;p+=64){const BusinessPlot*s=businessId(at<U>(p,0));
  if(!s||at<U>(p,48)!=s->zone||at<U>(p,52)!=s->position)continue;
  U64 previous=at<U64>(p,8);
  if(previous&&previous!=identity&&previous!=businessProjectionIdentity)continue;
  at<U64>(p,8)=economyRuntime.state.businessOwnedMask&businessBit(s->id)?identity:0;
 }
 businessProjectionIdentity=identity;
#ifdef PVP_BUSINESS_PRODUCTION
 projectBusinessStocks(b,m);
#endif
}
#endif
#include "progression.h"
#ifdef PVP_REGIONS
#include "regions.h"
#endif
#ifdef PVP_RANDOM_NEIGHBORS
#include "neighbor_roster.h"
#endif
#ifdef PVP_HISTORY
#include "history.h"
#endif
#ifdef PVP_BUSINESS_PRODUCTION
#include "business_production.h"
#endif
#ifdef PVP_BUSINESS_COLLECTION
#include "business_collection.h"
#endif
#ifdef PVP_EXCHANGE
#include "exchange.h"
#endif
#ifdef PVP_EVOLUTION
#include "evolution.h"
#endif
#ifdef PVP_SKILL_RESEARCH
#include "research.h"
#endif
#ifdef PVP_DAVE_NARRATIVE
#include "dave_narrative.h"
#endif
#include "redeem.h"
// S2C attack replies normally translate owned aliases into the numeric
// ArenaZombieInfoData vector at +d4. The native zombie bank reads this vector,
// not TrainingData. Use the native alias converter and vector assignment.
static U deployedArmy[TRAIN_COUNT],deployedSlot[TRAIN_COUNT],deployedType[TRAIN_COUNT],deployedUser;
static void bindBattleArmy(U b,P m){
#ifdef PVP_NPC_RAIDS
 if(raidActive(b)){raidBindArmy(b,m);return;}
#endif
 alignas(8) U entries[TRAIN_COUNT][2]{};U count=0,total=0;
 deployedUser=owner(b);for(U i=0;i<TRAIN_COUNT;++i)deployedArmy[i]=0;
 for(U i=0;i<TRAIN_COUNT;++i){U held=economyRuntime.state.trains[i].held;if(!held)continue;
  P name=nullptr;narrow(b,reinterpret_cast<P>(&name),TRAIN_SPECS[i].name);
  U type[2]{};call<void>(b,0xfb6ef0,type,&name);release(b,name);
  if(!type[1]){log(b,"army-alias-rejected",i,held);continue;}
  deployedSlot[i]=count;entries[count][0]=type[1];entries[count++][1]=held;total+=held;
  deployedArmy[i]=held;
  deployedType[i]=type[1];
  starter(b,m,TRAIN_SPECS[i].name,held,false);
 }
 P first=reinterpret_cast<P>(entries);P vector[3]={first,first+count*8,first+sizeof(entries)};
 call<void>(b,0x10454b0,m,vector);log(b,"battle-army-bound",count,total);
}
static void neighbors(U b,P m){
 if(!regular(b))return;
#ifdef PVP_RANDOM_NEIGHBORS
 if(!ensureNeighborRoster(b,m))return;
#endif
#ifdef PVP_REGIONS
 removeLockedNeighbors(b,m);
#endif
#ifdef PVP_RESIDENT_NEIGHBORS
 removeLocalBusinessRecords(b,m);
#endif
 for(U i=0;i<NPC_COUNT;++i){const NpcPreset& n=NPCS[i];
#ifdef PVP_REGIONS
  if(!regionOpen(n.zone))continue;
#endif
  bool occupied=false;P begin=at<P>(m,0x110),end=at<P>(m,0x114);
  if(begin&&end>=begin&&U(end-begin)<=64*256){
   for(P p=begin;p<end;p+=64)if(at<U>(p,48)==n.zone&&at<U>(p,52)==n.position){occupied=true;break;}
  }
  if(n.evil){
   // Native BigMapInfo type 4 is the special Evil Dave house. Its name is at
   // +8 and its plot at +1c/+20, unlike player-neighbor records.
   // +30 is dfmt, the challenge total compared with manager+15c by the
   // original map click handler. Zero makes even an untouched house "beaten".
   alignas(8) U special[16]={n.id,0,0,n.level,1000,2000,100,n.zone,n.position,4,0,0,n.level,0,1,0};
#ifdef PVP_DAVE_ROUNDS
   special[11]=economyRuntime.state.daveWins;
   special[12]=DAVE_ROUND_COUNT;
#endif
   char alloc=0;call<void>(b,0x14eb451,reinterpret_cast<P>(special)+8,n.name,&alloc);
   call<void>(b,0x104678c,m,special);release(b,reinterpret_cast<P>(special[2]),true);
   continue;
  }
#ifdef PVP_RESIDENT_NEIGHBORS
  residentialNeighbor(b,m,n);continue;
#endif
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
 // original Evil Dave introduction altogether. Start with zero completed
 // challenges; the house supplies its nonzero challenge total separately.
 if(at<I>(m,0x15c)<0)at<I>(m,0x15c)=0;
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
#ifdef PVP_BUSINESS_DEFENSE
#include "garrison_storage.h"
#endif
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
#ifdef PVP_BUSINESS_SCOUT
static void initialBusinessFormation(U b,const BusinessPlot&s,Store&formation){
 formation=Store{};formation.user=owner(b);formation.positions=5;formation.infos=1;
 U plant=s.id==BUSINESSES[0].id?2:6;
 for(U row=0;row<5;++row)formation.pos[row]={plant,row,0};
 formation.info[0].type=plant;formation.info[0].level=1;
}
#endif
static U arenaDaveRound;
static bool localDaveAllowed(U b,P m,const NpcPreset&n){
#ifdef PVP_REGIONS
 if(!ensureEconomy(b,m))return false;
 if(!regionOpen(n.zone)){economyNotice(b,"[V93_REGION_CLOSED]");return false;}
#endif
#ifdef PVP_DAVE_ROUNDS
 if(n.evil){
  if(!ensureEconomy(b,m))return false;
  if(economyRuntime.state.daveWins>=DAVE_ROUND_COUNT){economyNotice(b,"[V66_DAVE_FINISHED]");return false;}
 }
#endif
 return true;
}
#ifdef PVP_DAVE_LABEL
// Map names format {SON}/{MON} from this house record, not manager+15c.
// The record can outlive a completed battle or be rebuilt by the old map
// notifications. Project the accepted local values at the actual title call.
extern "C" void offlineDaveLabel(U b,P record){
 if(!record||!regular(b))return;const NpcPreset*n=npc(at<U>(record,0));
 if(!n||!n->evil||at<U>(record,0x24)!=4||at<U>(record,0x1c)!=n->zone||at<U>(record,0x20)!=n->position)return;
 if(!ensureEconomy(b,manager(b)))return;
 U wins=economyRuntime.state.daveWins;
 if(at<U>(record,0x2c)!=wins||at<U>(record,0x30)!=DAVE_ROUND_COUNT){
  log(b,"dave-label-previous",at<U>(record,0x2c),at<U>(record,0x30));
  at<U>(record,0x2c)=wins;at<U>(record,0x30)=DAVE_ROUND_COUNT;log(b,"dave-label-local",wins,DAVE_ROUND_COUNT);
 }
}
#endif
static bool preset(U b,P m,const NpcPreset&n){
 const U (*plants)[3]=n.plants;U count=n.count;
#ifdef PVP_DAVE_ROUNDS
 if(n.evil){arenaDaveRound=economyRuntime.state.daveWins;const DaveRound&r=DAVE_ROUNDS[arenaDaveRound<DAVE_ROUND_COUNT?arenaDaveRound:DAVE_ROUND_COUNT-1];plants=r.plants;count=r.count;log(b,"dave-round-prepared",arenaDaveRound+1,count);}
#endif
 Store s{};s.user=owner(b);s.positions=count;
#ifdef PVP_RANDOM_NEIGHBORS
 const NeighborEncounter* rich=nullptr;activeEncounterId=activeEncounterSeed=activeEncounterKind=0;
 if(!n.evil){
#ifdef PVP_SILENT_RAIDS
  rich=revengeEncounter(b,n.id);
#endif
  if(!rich)rich=encounter(b,n.id);if(!rich||!rich->seed)return false;count=s.positions=rich->count;
#ifdef PVP_SILENT_RAIDS
  rememberBattleEncounter(b,*rich);
#endif
  activeEncounterId=n.id;activeEncounterSeed=rich->seed;activeEncounterKind=rich->kind;}
#endif
 for(U k=0;k<count;++k){
#ifdef PVP_RANDOM_NEIGHBORS
  if(rich)s.pos[k]={rich->plants[k].type,rich->plants[k].row,rich->plants[k].col};else
#endif
  s.pos[k]={plants[k][0],plants[k][1],plants[k][2]};
  bool seen=false;for(U j=0;j<s.infos;++j)if(s.info[j].type==s.pos[k].type)seen=true;
  if(!seen){Info&v=s.info[s.infos++];v.type=s.pos[k].type;v.level=1;
#ifdef PVP_RANDOM_NEIGHBORS
   if(rich)v.level=rich->plants[k].level;
#endif
  }
 }
 apply(b,m+0x80,s);return true;
}
static U arenaNpc,arenaUser;
static bool resultAck,exitAck;
static bool resultSaved;
static P armyBankModule,armyBankBoard;
static bool localArenaIdentity(U b){
 if(npc(arenaNpc))return true;
#ifdef PVP_BUSINESS_SCOUT
 return businessId(arenaNpc)
#ifndef PVP_BUSINESS_BATTLE
 &&at<unsigned char>(manager(b),0x100)==1
#endif
 ;
#else
 return false;
#endif
}
#ifdef PVP_BATTLE_ECONOMY
#include "battle_economy.h"
#endif
static P arenaModule(U b){
 P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0);P board=at<P>(app,0x6bc);
 if(!board||!regular(b)||!at<P>(board,0xc4)||!same(reinterpret_cast<const char*>(at<P>(board,0xc4)),"arena_battle_test")||arenaUser!=owner(b)||!localArenaIdentity(b))return nullptr;
 P modules=at<P>(board,0x938);return modules?call<P>(b,0x43af38,modules,call<P>(b,0x108a164)):nullptr;
}
extern "C" void offlineBankReady(U b,P module){
 P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0);
 P board=at<P>(app,0x6bc);
 if(!regular(b)||arenaUser!=owner(b)||!localArenaIdentity(b)||!board||!at<P>(board,0xc4)||!same(reinterpret_cast<const char*>(at<P>(board,0xc4)),"arena_battle_test"))return;
 armyBankModule=module;armyBankBoard=at<P>(app,0x6bc);log(b,"battle-bank-ready");
#ifdef PVP_BATTLE_ECONOMY
 if(!at<unsigned char>(manager(b),0x100))markPaidBattleStarted(b);
#endif
}
extern "C" void offlineMapArmyPrepare(U b,P map){
 P m=manager(b);if(!regular(b)||!ensureEconomy(b,m))return;
 settleTraining(b,m);applyEconomy(b,m);
}
extern "C" void offlineMapArmyReady(U b,P map){
 if(!regular(b)||!at<P>(map,0x2d4))return;
 call<void>(b,0x100918c,map);log(b,"map-army-refreshed");
}
static void finishArenaBoard(U b){
 P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0),board=at<P>(app,0x6bc);
 bool local=board&&at<P>(board,0xc4)&&same(reinterpret_cast<const char*>(at<P>(board,0xc4)),"arena_battle_test");
#ifdef PVP_DEFENSE_FINISH
 if(board&&regular(b)&&at<P>(board,0xc4)&&same(reinterpret_cast<const char*>(at<P>(board,0xc4)),"arena_plant_test"))local=true;
#endif
 if(local&&at<U>(board,0xc0)!=9){
  // The original PvP return handlers finish the board before changing scenes.
  // Removing only its widget leaves plant objects and module listeners alive.
  call<void>(b,0x226770,board);log(b,"battle-board-finished");
 }
 armyBankModule=nullptr;armyBankBoard=nullptr;
}
// Use the successful server-response paths. In particular the attack callback
// preserves the native pre-load notifications. The debug menu helper skips
// them. A live scouting board must also be ended before loading a new level.
static bool sameText(P text,const char* expected){
 if(!text)return false;U i=0;while(expected[i]){if(text[i]!=U(expected[i]))return false;++i;}return text[i]==0;
}
static U requestedArenaView;
static bool arenaPending(U b,const char*level,U mode){
 P g=at<P>(reinterpret_cast<P>(b),0x1835eec);
 P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0);
 if(at<U>(app,0x1218)!=mode||requestedArenaView!=U(at<unsigned char>(manager(b),0x100)))return false;
 P board=at<P>(app,0x6bc);
 return (at<U>(g,0xa24)==6&&sameText(at<P>(g,0xa40),level))||
        (at<U>(g,0x984)==6&&board&&sameText(at<P>(board,0xc4),level));
}
static void loadArena(U b,P m,const char*level,U mode){
 resultSaved=false;resultAck=false;exitAck=false;
 armyBankModule=nullptr;armyBankBoard=nullptr;
 requestedArenaView=at<unsigned char>(m,0x100);
 P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0);
 finishArenaBoard(b);
 const U offset=mode==1?0xa0:0xa4;
 P name=nullptr;narrow(b,reinterpret_cast<P>(&name),level);
 P previous=at<P>(m,offset);at<P>(m,offset)=name;release(b,previous);
 // Keep the previous mode until the native attack callback runs its notifications.
 if(mode==1){at<U>(app,0x1218)=1;call<void>(b,0x1046360);}
 else {
  P board=at<P>(app,0x6bc);
  // Same board-finish sequence used by the native scout response when it
  // replaces a running board; otherwise Scene 6 can reuse the scout modules.
  if(at<U>(app,0x1218)==1&&board&&at<U>(board,0xc0)==5){
   call<void>(b,0x226770,board);P current=at<P>(app,0x6bc);if(current)at<U>(current,0x7f4)=8;
  }
  call<void>(b,0x104810c,m,1,0);
 }
 log(b,"arena-load",mode,at<unsigned char>(m,0x17d));
}
#ifdef PVP_BUSINESS_SCOUT
static bool scoutBusiness(U b,const BusinessPlot&s,bool attack){
 P m=manager(b);if(!regular(b))return false;
#ifdef PVP_REGIONS
 if(!ensureEconomy(b,m))return false;
 if(!regionOpen(s.zone)){economyNotice(b,"[V93_REGION_CLOSED]");return false;}
#endif
 // Check the actual map record: do not route another owner's/server shop
 // through a local fixture just because it happens to occupy the same plot.
 P begin=at<P>(m,0x110),end=at<P>(m,0x114);bool found=false;
 if(!begin||end<begin||U(end-begin)>64*256||U(end-begin)%64)return false;
 for(P p=begin;p<end;p+=64)if(at<U>(p,0)==s.id&&at<U>(p,48)==s.zone&&at<U>(p,52)==s.position&&at<U64>(p,8)==0){found=true;break;}
 if(!found)return false;
 if(arenaNpc==s.id&&arenaUser==owner(b)&&arenaPending(b,"arena_battle_test",0)&&requestedArenaView==U(!attack)){
  log(b,"business-scout-duplicate",s.id);return true;
 }
 // Dispose the previous board before replacing its formation vectors.
 finishArenaBoard(b);
 at<U>(m,0xa8)=2;at<U>(m,0xf4)=s.id;at<U>(m,0xf8)=s.position;at<U>(m,0xfc)=s.zone;at<U>(m,0x104)=s.id;
 at<unsigned char>(m,0x100)=attack?0:1;
 at<unsigned char>(m,0x101)=at<unsigned char>(m,0x102)=at<unsigned char>(m,0x103)=0;
 // Independent local neutral defenses, not recovered server formations.
 // The two shops deliberately differ to expose stale-board/stacking bugs.
 Store formation{};initialBusinessFormation(b,s,formation);U plant=formation.info[0].type;
 apply(b,m+0x80,formation);arenaNpc=s.id;arenaUser=owner(b);
 loadArena(b,m,"arena_battle_test",0);log(b,"business-scout",s.id,plant);return true;
}
#endif
#ifdef PVP_BUSINESS_BATTLE
static bool attackBusiness(U b,const BusinessPlot&s){
 P m=manager(b);if(!regular(b)||!ensureEconomy(b,m))return false;
#ifdef PVP_REGIONS
 if(!regionOpen(s.zone)){economyNotice(b,"[V93_REGION_CLOSED]");return false;}
#endif
 if(economyRuntime.state.businessOwnedMask&businessBit(s.id)){economyNotice(b,"[V80_BUSINESS_OWNED]");return false;}
 P first=at<P>(m,0x110),last=at<P>(m,0x114);bool available=false;
 if(!first||last<first||U(last-first)>64*256||U(last-first)%64)return false;
 for(P p=first;p<last;p+=64)if(at<U>(p,0)==s.id&&at<U>(p,48)==s.zone&&at<U>(p,52)==s.position&&at<U64>(p,8)==0){available=true;break;}
 if(!available)return false;
 U army=0;for(U i=0;i<TRAIN_COUNT;++i)army+=economyRuntime.state.trains[i].held;
 if(!army){at<unsigned char>(m,0x100)=1;economyNotice(b,"[V80_ARMY_REQUIRED]");return false;}
 P live=arenaModule(b);
 if(arenaNpc==s.id&&live&&at<U>(live,0xb0)==3){log(b,"business-battle-duplicate",s.id);return true;}
 if(arenaNpc==s.id&&arenaUser==owner(b)&&requestedArenaView==0&&arenaPending(b,"arena_battle_test",0))return true;
 NpcPreset fee{};fee.id=s.id;
 if(arenaNpc==s.id&&live&&at<U>(live,0xb0)==2){
  if(!beginBattleFee(b,m,fee,true)){at<unsigned char>(m,0x100)=1;return false;}
  at<unsigned char>(m,0x100)=0;at<unsigned char>(m,0x102)=at<unsigned char>(m,0x103)=0;
  requestedArenaView=0;call<void>(b,0x1090990,live);log(b,"business-preview-started",s.id);return true;
 }
 if(!beginBattleFee(b,m,fee,false))return false;
 if(!scoutBusiness(b,s,true)){closeAbandonedBattle(b,m);return false;}
 log(b,"business-battle-loaded",s.id);return true;
}
#endif
extern "C" __attribute__((section(".text.entry"))) void offlineGarden(U b){neighbors(b,manager(b));
#ifdef PVP_SILENT_RAIDS
 clearRevenge();
#endif
#ifdef PVP_BUSINESS_MAP
 projectBusinesses(b,manager(b));
#endif
#ifdef PVP_REGIONS
 projectRegions(b,manager(b));
#endif
 scene(b,25);}
#ifdef PVP_LOCAL_DEFENSE_SESSION
static U defenseSessionUser;
#endif
#ifdef PVP_BUSINESS_DEFENSE
#include "garrison_editor.h"
#endif
#ifdef PVP_TUTORIAL_DEFENSE
#include "tutorial_defense.h"
#endif
extern "C" void offlineOwn(U b){
#ifdef PVP_SILENT_RAIDS
 clearRevenge();
#endif
#ifdef PVP_BUSINESS_DEFENSE
 if(regular(b)){openLocalDefense(b,0);return;}
#endif
#ifdef PVP_DEFENSE_FINISH
 if(regular(b))finishArenaBoard(b);
#endif
 P m=manager(b);Store s{};if(readStore(b,s)){apply(b,m+0x80,s);log(b,"defense-loaded",s.positions,s.infos);}else{clear(b,m+0x80);log(b,"defense-new");}
#ifdef PVP_LOCAL_DEFENSE_SESSION
 if(regular(b)){
  defenseSessionUser=owner(b);at<U>(m,0xa8)=1;
  at<unsigned char>(m,0x100)=at<unsigned char>(m,0x102)=at<unsigned char>(m,0x103)=0;
 }
#endif
 call<void>(b,0x85e7d8);}
extern "C" void offlineSave(U b,P network,P json,U zone,U type){
 if(!regular(b)){call<void>(b,0xf87cc4,network,json,zone,type);return;}
#ifdef PVP_BUSINESS_DEFENSE
 saveLocalDefense(b);return;
#endif
 Store s{};if(capture(b,manager(b)+0x80,s)&&writeStore(b,s)){log(b,"defense-saved",s.positions,s.infos);
#ifdef PVP_DEFENSE_FINISH
  // Removing only the editor widget keeps the live board/module listeners
  // and music active. Serialize first, then use native Board::Finish before
  // the map transition, just as the original editor exit path does.
  finishArenaBoard(b);
#endif
  scene(b,25);}else log(b,"defense-save-failed");
}
extern "C" void offlineInfo(U b,P m,U a,U id,U kind){
#ifdef PVP_SILENT_RAIDS
 clearRevenge();
#endif
#ifdef PVP_BUSINESS_DEFENSE
 if(regular(b)&&kind==2){const BusinessPlot*s=businessId(id);if(s&&ownedGarrison(b,id)){defendBusiness(b,*s);return;}}
#endif
#ifdef PVP_BUSINESS_SCOUT
 if(regular(b)&&kind==2){const BusinessPlot*s=businessId(id);if(s){scoutBusiness(b,*s);return;}}
#endif
 const NpcPreset*n=npc(id);if(n&&kind==2&&regular(b)){
  if(!localDaveAllowed(b,m,*n))return;
#ifdef PVP_BATTLE_ECONOMY
  at<unsigned char>(m,0x100)=1;
#endif
  if(n->evil){at<unsigned char>(m,0x100)=1;at<unsigned char>(m,0x102)=0;at<unsigned char>(m,0x103)=0;at<U>(m,0xa8)=1;}
  if(arenaPending(b,"arena_battle_test",0)){log(b,"view-duplicate",id);return;}log(b,"view-neighbor",id,n->count);arenaNpc=n->id;arenaUser=owner(b);if(!preset(b,m,*n))return;loadArena(b,m,"arena_battle_test",0);return;}
 call<void>(b,0xf79d74);P net=call<P>(b,0xf7a070);call<void>(b,0xf87154,net,a,id,kind);
}
extern "C" void offlineAttack(U b,P m,U id,U reason,U unused){
#ifdef PVP_BUSINESS_SCOUT
 if(regular(b)){
  const BusinessPlot*s=businessId(id);
  if(!s&&id==0&&arenaUser==owner(b)){
   const BusinessPlot*selected=businessId(at<U>(m,0x104));
   if(selected&&selected->zone==at<U>(m,0xfc)&&selected->position==at<U>(m,0xf8))s=selected;
  }
  if(s){if(reason==3)scoutBusiness(b,*s);
#ifdef PVP_BUSINESS_BATTLE
   else if(reason==1||reason==2)attackBusiness(b,*s);
#endif
   else log(b,"business-attack-pending",s->id,reason);return;}
 }
#endif
 const NpcPreset*n=npc(id);
 // Native special houses send a zero player id and put the house id in +104.
 if(!n&&id==0&&reason>=1&&reason<=4){const NpcPreset* selected=npc(at<U>(m,0x104));if(selected&&
#ifndef PVP_RESIDENT_NEIGHBORS
 selected->evil&&
#endif
 selected->zone==at<U>(m,0xfc)&&selected->position==at<U>(m,0xf8))n=selected;}
 if(n&&regular(b)){
#ifdef PVP_SILENT_RAIDS
  P revengeLive=arenaModule(b);
  if(n->id!=arenaNpc||!revengeLive||at<U>(revengeLive,0xb0)!=2||reason==3||reason==4)clearRevenge();
#endif
#ifdef PVP_RESIDENT_NEIGHBORS
  // Residential buttons use zero-id reasons 4 (scout) and 1 (raid).
  // Route ordinary opponents through the already accepted local battle kind,
  // including in-place preview starts, fees and survivor/death settlement.
  if(!n->evil&&id==0){
   if(reason!=1&&reason!=4){log(b,"residence-reason-rejected",reason);return;}
   reason=reason==4?3:2;id=n->id;at<U>(m,0xa8)=2;at<U>(m,0xf4)=n->id;
   at<unsigned char>(m,0x102)=at<unsigned char>(m,0x103)=0;
   log(b,"residence-request",id,reason);
  }
#endif
  if(!localDaveAllowed(b,m,*n))return;
  log(b,"attack-request-reason",id,reason);
  // The special-house handler sets this server-driven preparation flag.
  // ArenaBattle then stays in state 1, hiding banks until an online start
  // response. A local session starts itself, exactly as neighbor battles do.
  if(n->evil){at<unsigned char>(m,0x102)=0;at<unsigned char>(m,0x103)=0;at<U>(m,0xa8)=1;}
  // Some native preview buttons leave +100 set when sending reason 2.
  // Normalize from the actual request before evaluating the duplicate guard.
  if(reason==3||(n->evil&&reason==4))at<unsigned char>(m,0x100)=1;
  else if(reason==1||reason==2||reason==4)at<unsigned char>(m,0x100)=0;
  // The live preview already owns its plants and seed bank. The native
  // ArenaBattle start method reveals the banks and enables combat in place.
  // Reloading the same level fires another plant-placement notification.
  P live=arenaModule(b);
#ifdef PVP_BATTLE_ECONOMY
  P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0),board=at<P>(app,0x6bc);
  if(board&&at<U>(board,0xc0)==9)live=nullptr;
  if(live&&arenaNpc==n->id&&at<U>(live,0xb0)==3){log(b,"active-battle-duplicate",n->id);return;}
#endif
  if((reason==2||(n->evil&&reason==1))&&arenaNpc==n->id&&live&&at<U>(live,0xb0)==2){
   // Dave's real preview button (1088aa0) sends zero-id reason 1, while
   // neighbors use reason 2. The native starts also clear different flags.
#ifdef PVP_BATTLE_ECONOMY
   if(!beginBattleFee(b,m,*n,true)){at<unsigned char>(m,0x100)=1;return;}
#endif
   requestedArenaView=0;call<void>(b,n->evil&&reason==1?0x1090dec:0x1090990,live);log(b,"preview-battle-started",id);return;
  }
  // The ArenaBattle level handles both preview (+100 set) and attack.
  // ArenaPlant is the editor even when the App mode is changed.
  if(reason==3||(n->evil&&reason==4)){
   if(arenaPending(b,"arena_battle_test",0)){log(b,"view-duplicate",id);return;}
   arenaNpc=n->id;arenaUser=owner(b);if(!preset(b,m,*n))return;loadArena(b,m,"arena_battle_test",0);return;
  }
  if(arenaPending(b,"arena_battle_test",0)){log(b,"attack-duplicate",id);return;}
#ifdef PVP_BATTLE_ECONOMY
  if(reason!=1&&reason!=2&&reason!=4){log(b,"unknown-battle-reason",reason);return;}
  if(!beginBattleFee(b,m,*n,false))return;
#endif
  log(b,"attack-neighbor",id,n->count);arenaNpc=n->id;arenaUser=owner(b);if(!preset(b,m,*n))return;loadArena(b,m,"arena_battle_test",0);return;}
 call<void>(b,0xf79d74);P net=call<P>(b,0xf7a070);call<void>(b,0xf87710,net,id,reason,at<U>(m,0x104),at<U64>(m,0x108));
}
// The offline session acknowledges the original three-second heartbeat using
// the same monotonic clock as ArenaBattleModule's native timeout check.
extern "C" void offlineBattleRequest(U b,P m,U action){
#ifdef PVP_TUTORIAL_DEFENSE
 if(tutorialDefenseRequest(b,action))return;
#endif
#ifdef PVP_LOCAL_DEFENSE_SESSION
 if(regular(b)&&defenseSessionUser==owner(b)
#ifdef PVP_BUSINESS_DEFENSE
 &&defenseSessionActive
#endif
 ){
  P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0),board=at<P>(app,0x6bc);
  bool editor=board&&sameText(at<P>(board,0xc4),"arena_plant_test");
  if(action==1&&editor){
   // ArenaPlant's native update compares the clock's +18 time with the
   // app's last server acknowledgement (+185c). A local edit needs no socket.
   at<U>(app,0x185c)=at<U>(call<P>(b,0x1f7380),0x18);
   return;
  }
  if(action==3){
   // Only ArenaPlant's native destructor sends action 3. Keep this scoped
   // token through scene teardown, when the app may already detach its board.
   defenseSessionUser=0;
#ifdef PVP_BUSINESS_DEFENSE
   defenseSessionTarget=0;
   defenseSessionActive=false;
#ifdef PVP_GARRISON_REPOSITION
   garrisonRosterSize=0;garrisonPlantCount=0;
#endif
#endif
   log(b,"defense-session-closed");return;
  }
 }
#endif
 P module=arenaModule(b);
 if(module){
  if(action==2){P clock=call<P>(b,0x1f7380);at<U>(module,0x40)=at<U>(clock,0x18);return;}
  if(action==4){
#ifdef PVP_SILENT_RAIDS
   clearRevenge();
#endif
#ifdef PVP_NPC_RAIDS
   if(raidActive(b)){raidResult(b,at<U>(module,0x78));return;}
#endif
#ifdef PVP_BATTLE_ECONOMY
   if(
#ifdef PVP_BUSINESS_SCOUT
      (!businessId(arenaNpc)
#ifdef PVP_BUSINESS_BATTLE
       ||!at<unsigned char>(m,0x100)
#endif
      )&&
#endif
      !closeAbandonedBattle(b,m))return;
#endif
   exitAck=true;log(b,"battle-exit-requested");return;}
 }
 call<void>(b,0xf79d74);P net=call<P>(b,0xf7a070);call<void>(b,0xf8c860,net,at<U>(m,0xe4),at<U>(m,0xf4),at<U>(m,0xa8),action);
}
static bool persistBattleArmy(U b,P m,bool daveVictory=false,U stars=0){
 if(!ensureEconomy(b,m)||deployedUser!=owner(b))return false;
 P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0);
 if(!armyBankModule||armyBankBoard!=at<P>(app,0x6bc))return false;
 P objects=call<P>(b,0x11d74b4),bank=call<P>(b,0x1da034,objects,armyBankModule+0x50);if(!bank)return false;
 P losses=at<P>(m,0xd4),end=at<P>(m,0xd8);
 if(end<losses||U(end-losses)>40*8||U(end-losses)%8)return false;
 Economy next=economyRuntime.state;
 for(U i=0;i<TRAIN_COUNT;++i){
  if(!deployedArmy[i])continue;
  if(deployedSlot[i]>=6)return false;
  alignas(8) U weak[2]{};call<void>(b,0x895f0c,weak,bank,deployedSlot[i]);
  P card=call<P>(b,0x1da034,objects,weak);call<void>(b,0x1d9bb4,weak,0,0,0);
  if(!card)return false;U remaining=at<U>(card,0x154);log(b,"battle-card-remaining",i,remaining);
  if(remaining>deployedArmy[i])return false;U placed=deployedArmy[i]-remaining,dead=0;
  // ArenaBattle records deaths before Board removes surviving zombies.
  // Unplayed and surviving deployed units both return to the local army.
  for(P p=losses;p<end;p+=8)if(at<U>(p,0)==deployedType[i]){U n=at<U>(p,4);if(n>100||dead>100-n)return false;dead+=n;}
  if(dead>placed||dead>next.trains[i].held)return false;
  next.trains[i].held-=dead;log(b,"battle-army-deaths",i,dead);
  if(placed>dead)log(b,"battle-army-recalled",i,placed-dead);
 }
 if(daveVictory){
#ifdef PVP_DAVE_ROUNDS
  if(arenaDaveRound>=DAVE_ROUND_COUNT||next.daveWins!=arenaDaveRound){log(b,"dave-result-stale",arenaDaveRound,next.daveWins);return false;}
  ++next.daveWins;
#else
  next.daveWins=1;
#endif
 }
#ifdef PVP_BATTLE_ECONOMY
 const NpcPreset*n=npc(arenaNpc);
 bool rewarded=n&&!n->evil;
#ifdef PVP_BUSINESS_BATTLE
 if(businessId(arenaNpc)){
  if(stars==3){
#ifdef PVP_BUSINESS_PRODUCTION
   U bit=businessBit(arenaNpc);
   if(!(next.businessOwnedMask&bit))next.businessStocks[bit==1?0:1].producedAt=realNow(b);
#endif
   next.businessOwnedMask|=businessBit(arenaNpc);
  }
  rewarded=true;
 }
#endif
#ifdef PVP_HISTORY
 U beforeReward=next.coins;
#endif
 if(rewarded&&!settleBattleReward(b,next,stars))return false;
#ifdef PVP_HISTORY
 appendHistory(b,next,arenaNpc,stars,next.coins-beforeReward);
#endif
#ifdef PVP_SILENT_RAIDS
 if(n&&!n->evil)planSilentRevenge(b,next,n->id);
#endif
#endif
#ifdef PVP_DAVE_NARRATIVE
 if(n&&n->evil){
  if(next.daveDialogueSerial==0xffffffffu)return false;
  ++next.daveDialogueSerial;next.daveDialogueOutcome=daveVictory?next.daveWins:0;
 }
#endif
 ++next.sequence;if(!saveEconomy(b,next))return false;economyRuntime.state=next;
 if(daveVictory){at<U>(m,0x15c)=next.daveWins;log(b,"evil-dave-defeated",next.daveWins);}
 log(b,"battle-army-saved");return true;
}
extern "C" U offlineBattleResult(U b,P m,U stars,U id,U kind){
#ifdef PVP_NPC_RAIDS
 if(raidActive(b))return raidResult(b,stars);
#endif
 if(!arenaModule(b))return 0;
#ifdef PVP_BUSINESS_SCOUT
 if(businessId(arenaNpc)
#ifdef PVP_BUSINESS_BATTLE
 &&at<unsigned char>(m,0x100)
#endif
 ){log(b,"business-preview-result-ignored",stars);return 1;}
#endif
 if(resultSaved)return 1;
 const NpcPreset*n=npc(arenaNpc);
#ifdef PVP_DAVE_ROUNDS
 if(n&&n->evil&&(kind!=1||(id&&id!=n->id))){log(b,"dave-result-foreign",id,kind);return 1;}
#endif
#ifdef PVP_BATTLE_ECONOMY
 bool shop=false;
#ifdef PVP_BUSINESS_BATTLE
 shop=businessId(arenaNpc)!=nullptr;
#endif
 if((!n&&!shop)||stars>3||((shop||n&&!n->evil)&&(id!=arenaNpc||kind!=2||!ensureEconomy(b,m)||!paidBattleMatches(b,economyRuntime.state)))){log(b,"battle-result-unpaid-or-stale",stars,id);return 1;}
 U previousCoins=economyRuntime.state.coins;
#endif
 if(!persistBattleArmy(b,m,n&&n->evil&&stars>0,stars)){economyNotice(b,"[V38_PVP_SAVE_ERROR]");return 1;}
#ifdef PVP_BATTLE_ECONOMY
 if(shop||n&&(!n->evil
#ifdef PVP_DAVE_ROUNDS
 ||n->evil
#endif
 )){
  // Original result drawing reads +c4/+c8 currency deltas; the continuation
  // reads +ac/+b0 totals. Keep both views of the successful local transaction
  // in sync, with no leftover server medal/cup or bonus reward fields.
  at<U>(m,0xac)=economyRuntime.state.coins;at<U>(m,0xb0)=economyRuntime.state.medals;at<U>(m,0xb4)=at<U>(m,12);
  at<U>(m,0xb8)=at<U>(m,0xbc)=at<U>(m,0xc0)=0;
  at<U>(m,0xc4)=economyRuntime.state.coins-previousCoins;at<U>(m,0xc8)=at<U>(m,0xcc)=0;
  log(b,"battle-reward-saved",stars,at<U>(m,0xc4));
 }
#ifdef PVP_BUSINESS_BATTLE
 if(shop){projectBusinessOwners(b,m);log(b,"business-result",stars,economyRuntime.state.businessOwnedMask);}
#endif
#endif
 // The response callback opens the original result window. The unrelated
 // 10485f0 notification tears down the battle and skips that window.
 resultSaved=true;resultAck=true;log(b,"battle-result-local",stars,kind);
#ifdef PVP_NPC_RAIDS
 if(n&&!n->evil)raidQueue(b,n->id);
#endif
 return 1;
}
static void completeLocalBattle(U b){
 if(resultAck){resultAck=false;P module=arenaModule(b);if(module){P m=manager(b);applyEconomy(b,m);
  P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0);
  at<unsigned char>(m,0x17c)=0;call<void>(b,0x3fa970,app);
  call<void>(b,0x108d340,module,1,0);log(b,"battle-result-window-opened");}}
 if(exitAck){exitAck=false;P m=manager(b);at<unsigned char>(m,0x17c)=0;finishArenaBoard(b);scene(b,25);log(b,"battle-exited");}
}
extern "C" U offlineResultContinue(U b,P window,U button){
 P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0);
 if(!resultSaved||arenaUser!=owner(b)||!arenaModule(b)||at<P>(app,0x139c)!=window)return 0;
 if(button!=0)return 1;
#ifdef PVP_SILENT_RAIDS
 clearRevenge();
#endif
 // Native continuation assigns server response balances (+ac/+b0) to the
 // wallet. Those fields are not offline rewards; retain the local economy.
 resultSaved=false;call<void>(b,0x3ffc08,app);call<void>(b,0x3fa970,app);
 finishArenaBoard(b);
 P m=manager(b);at<unsigned char>(m,0x17c)=0;applyEconomy(b,m);call<void>(b,0x10446d8,m);
 scene(b,25);log(b,"battle-result-continued");return 1;
}
extern "C" void __aeabi_memclr4(void* p,U n){volatile unsigned char*d=static_cast<volatile unsigned char*>(p);while(n--)*d++=0;}
extern "C" void __aeabi_memclr8(void* p,U n){__aeabi_memclr4(p,n);}
extern "C" void __aeabi_memclr(void* p,U n){__aeabi_memclr4(p,n);}
extern "C" void __aeabi_memcpy8(void* dst,const void* src,U n){volatile unsigned char*d=static_cast<volatile unsigned char*>(dst);const volatile unsigned char*s=static_cast<const volatile unsigned char*>(src);while(n--)*d++=*s++;}
extern "C" void __aeabi_memcpy4(void* dst,const void* src,U n){__aeabi_memcpy8(dst,src,n);}

// Record the actual level passed to Board::Load, beyond the request boundary.
extern "C" void offlineBoardLoad(U b,P board,P name,U seed){
#ifdef PVP_TUTORIAL_DEFENSE
 prepareTutorialDefense(b,name);
#endif
 if(regular(b)){
  P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0);P m=manager(b);
  call<I>(b,0x147adc,4,"OfflinePvP","board-load name=%s mode=%u view=%u kind=%u",at<P>(name,0),at<U>(app,0x1218),U(at<unsigned char>(m,0x100)),at<U>(m,0xa8));
 }
 if(regular(b)&&sameText(at<P>(name,0),"arena_battle_test")){
  P m=manager(b);if(ensureEconomy(b,m)){
   P camp=at<P>(m,0x20);U held=0;if(camp){P a=at<P>(camp,12),e=at<P>(camp,16);if(a&&e>=a&&U(e-a)<=40*32)for(;a<e;a+=32)held+=at<U>(a,4);}
   log(b,"army-before-board-load",held,economyRuntime.state.trains[0].held);
   // A level transition may reset native TrainingData without changing its
   // camp pointer. Rebind the accepted local queue before seed-bank creation.
   applyEconomy(b,m);
   bindBattleArmy(b,m);
  }
 }
 call<void>(b,0x2258d8,board,name,seed);
}
#ifdef PVP_LAB_ROSTER
// The old server populated the lab roster separately from TrainingData. The
// local training wallet must not be interpreted as zombie evolution levels.
extern "C" void offlineLabRoster(U b,P ui,U button){
#ifdef PVP_SKILL_LAB
 if(button==15&&regular(b)){
  P m=manager(b);if(!ensureEconomy(b,m))return;
  // SkillInfo is a separate server-populated tree. Opening the laboratory
  // directly from the lobby must not depend on visiting Garden Wars first.
  const char names[4][32]={"pvpskill_zombiefood","pvpskill_aid","pvpskill_invisible","pvpskill_rage"};
  for(U i=0;i<4;++i){
   starter(b,m,names[i],0,true);
   P key=nullptr;narrow(b,reinterpret_cast<P>(&key),names[i]);
   P info=call<P>(b,0x1046764,m,&key);release(b,key);
   log(b,"skill-lab-record",i,info?at<U>(info,4):0);
  }
  return;
 }
#endif
 if(button!=13||!regular(b))return;
 P m=manager(b);if(!ensureEconomy(b,m))return;
#ifdef PVP_EVOLUTION
 if(!ensureEvolution(b,m))return;
 applyEvolution(b,m);return;
#endif
 for(U i=0;i<TRAIN_COUNT;++i){
  P key=nullptr;narrow(b,reinterpret_cast<P>(&key),TRAIN_SPECS[i].name);
  P info=call<P>(b,0x104673c,m,&key);
  if(!info&&TRAIN_SPECS[i].level<=economyRuntime.state.home){
   U entry[5]={reinterpret_cast<U>(key),1,1,0,1};info=call<P>(b,0x1048f44,m,entry);
   log(b,"lab-roster-added",i,1);
  }
  if(info){log(b,"lab-record-level",i,at<U>(info,4));log(b,"lab-record-allow",U(at<unsigned char>(info,8)),at<U>(info,12));log(b,"lab-record-advance",i,U(at<unsigned char>(info,16)));}
  else log(b,"lab-record-missing",i,TRAIN_SPECS[i].level);
  release(b,key);
 }
}
#ifdef PVP_SKILL_LAB
// Only the skill-page title call is guarded. The generic name helper
// dereferences a null resolved weak reference; keep its localization for
// valid selections and leave an empty title while selection is stale.
extern "C" P offlineSkillName(U b,P destination,P weak){
 if(!regular(b)||call<P>(b,0x1da034,call<P>(b,0x11d74b4),weak))
  return call<P>(b,0xa45450,destination,weak);
 const U empty[1]={0};char allocator=0;
 call<void>(b,0x14eb451,destination,empty,&allocator);return destination;
}
#endif
extern "C" void offlineLabProperties(U b,P type,P props,U caller){
#ifdef PVP_EVOLUTION
 return; // v62 identified the roster issue; stop per-frame diagnostic logging.
#endif
 U site=caller-b;if(site<0x107c000||site>=0x1085000)return;
 const char*name=at<P>(type,0x1c)?reinterpret_cast<const char*>(at<P>(type,0x1c)):"(empty)";
 if(!props){call<I>(b,0x147adc,4,"OfflinePvP","lab-properties-missing popanim=%s caller=%x",name,site);return;}
 U first=at<U>(props,0x108),last=at<U>(props,0x10c);
 U count=last>=first&&(last-first)%12==0&&(last-first)<=12*20?(last-first)/12:0xffffffffu;
 call<I>(b,0x147adc,4,"OfflinePvP","lab-properties popanim=%s rows=%u caller=%x",name,count,site);
}
#endif
static P loggedArenaBoard;
#ifdef PVP_STAR_DISPLAY
#include "star_display.h"
#endif
static void inspectArena(U b){
 P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0);P board=at<P>(app,0x6bc);
 if(!board){loggedArenaBoard=nullptr;return;}if(board==loggedArenaBoard||!regular(b))return;
 P modules=at<P>(board,0x938);if(!modules)return;
 P plant=call<P>(b,0x43af38,modules,call<P>(b,0x1094f28));
 P m=manager(b);call<I>(b,0x147adc,4,"OfflinePvP","board-active level=%s mode=%u state=%u plant_module=%u view=%u",at<P>(board,0xc4),at<U>(app,0x1218),at<U>(board,0xc0),U(plant!=nullptr),U(at<unsigned char>(m,0x100)));
 loggedArenaBoard=board;
}
#ifdef PVP_NPC_RAIDS
#ifdef PVP_SILENT_RAIDS
#include "silent_raids.h"
#else
#include "raids.h"
#endif
#endif
