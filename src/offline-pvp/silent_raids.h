// v99 replaces the foreground raid experiment. Background outcomes follow the
// user's explicit probability rules and never create/finish a Board.
#include "silent_raid_policy.h"
#include "frozen_encounters.h"
static_assert(sizeof(Economy)==2828,"silent raid save layout");
extern "C" void offlineSilentOdds(U,U strength,P out){RaidOdds odds=defenseOdds(strength);at<U>(out,0)=odds.attack;at<U>(out,4)=odds.win;}
extern "C" U offlineSilentHomePower(U b){Store saved{};return readStore(b,saved)?defenseStrength(saved):0xffffffffu;}
struct RevengeContext {U user,serial;bool ready;NeighborEncounter opponent;};
static RevengeContext* revengeContext;
static RevengeContext* lastBattleEncounter;
static void rememberBattleEncounter(U b,const NeighborEncounter&e){
 if(!lastBattleEncounter){lastBattleEncounter=call<RevengeContext*>(b,0x147938,sizeof(RevengeContext));if(!lastBattleEncounter)return;}
 lastBattleEncounter->user=owner(b);lastBattleEncounter->ready=true;lastBattleEncounter->opponent=e;
}
extern "C" U offlineSilentRaidsMode(){return 1;}
extern "C" U offlineRaidsMode(){return 1;}
static bool raidActive(U){return false;}
static void raidBindArmy(U,P){}
static void raidQueue(U,U){}
static U raidResult(U,U){return 0;}
static void raidEnded(U){}
static void clearRevenge(){if(revengeContext)revengeContext->ready=false;}
static const NeighborEncounter* revengeEncounter(U b,U id){
 return revengeContext&&revengeContext->ready&&revengeContext->user==owner(b)&&revengeContext->opponent.id==id?&revengeContext->opponent:nullptr;
}
static bool validSilentRaids(const Economy&s){
 if(s.raidInitialized>1||s.retaliationCount>64)return false;
 if(s.raidInitialized&&(!s.raidRng||!s.raidCheckedAt))return false;
 for(U i=0;i<2;++i){const NpcPreset*n=npc(s.shopEnemy[i]);
  if(s.shopEnemyKind[i]>7)return false;
  if(s.shopEnemy[i]){if(!n||n->evil||!s.shopEnemySeed[i]||(s.businessOwnedMask&(1u<<i)))return false;}
  else if(s.shopEnemySeed[i]||s.shopEnemyKind[i])return false;
 }
 for(U i=0;i<10;++i){
  if(s.historyMedals[i]>100000000||s.historyFlags[i]&~1u)return false;
  if(i>=s.historyCount){if(s.historyMedals[i]||s.historyDefended[i]||s.historyFlags[i]||s.historyFrozen[i][0]||s.historyFrozen[i][1])return false;continue;}
  const auto&h=s.history[i];
  if(h.kind==4){if(!businessId(s.historyDefended[i]))return false;}
  else if(s.historyDefended[i])return false;
  if(h.kind<3&&(s.historyMedals[i]||s.historyFlags[i]))return false;
  if(h.kind>=3&&!h.stars&&(h.coins||s.historyMedals[i]||s.historyFlags[i]))return false;
 }
 for(U i=0;i<s.retaliationCount;++i){const auto&j=s.retaliations[i];const NpcPreset*n=npc(j.target);
  if(!n||n->evil||!j.seed||j.kind>7||!j.due||j.stars>3)return false;
 }
 return true;
}
static bool localRaidOccupier(U b,U64 identity){
 if(!identity||identity>0xffffffffu||!economyRuntime.loaded||economyRuntime.user!=owner(b))return false;
 for(U i=0;i<2;++i)if(economyRuntime.state.shopEnemy[i]==U(identity))return true;
 return false;
}
static bool revengeAllowed(U b,U serial){
 if(!regular(b)||!ensureEconomy(b,manager(b)))return false;
 const auto*h=findHistory(serial);if(!h||h->kind<3||!h->stars)return false;
 U index=U(h-economyRuntime.state.history);
 if(economyRuntime.state.historyFlags[index]&1)return false;
 NeighborEncounter saved{};
 if(economyRuntime.state.historyFrozen[index][0]||economyRuntime.state.historyFrozen[index][1])return readFrozen(b,economyRuntime.state.historyFrozen[index][0],economyRuntime.state.historyFrozen[index][1],saved)==1&&saved.id==h->target&&saved.seed==economyRuntime.state.historySeeds[index]&&saved.kind==economyRuntime.state.historyKinds[index];
 // v98 summaries did not store a snapshot. Only allow the legacy entry if
 // its exact identity is still present, rather than regenerating a guess.
 const auto*current=encounter(b,h->target);
 return current&&current->seed==economyRuntime.state.historySeeds[index]&&current->kind==economyRuntime.state.historyKinds[index];
}
static bool startHistoryRevenge(U b,P row,U button){
 if(button!=101||historyUiUser!=owner(b)||!revengeAllowed(b,at<U>(row,0xa8)))return false;
 const auto*h=findHistory(at<U>(row,0xa8));if(!h)return false;U index=U(h-economyRuntime.state.history);
 const NpcPreset*n=npc(h->target);if(!n||n->evil)return false;
 if(!revengeContext){revengeContext=call<RevengeContext*>(b,0x147938,sizeof(RevengeContext));if(!revengeContext)return false;*revengeContext=RevengeContext{};}
 auto&r=*revengeContext;r.user=owner(b);r.serial=h->serial;r.ready=true;
 U lo=economyRuntime.state.historyFrozen[index][0],hi=economyRuntime.state.historyFrozen[index][1];
 if(lo||hi){if(readFrozen(b,lo,hi,r.opponent)!=1){clearRevenge();return false;}}
 else {const auto*current=encounter(b,n->id);if(!current){clearRevenge();return false;}r.opponent=*current;}
 P window=historyUi;P m=manager(b);finishArenaBoard(b);
 arenaNpc=n->id;arenaUser=owner(b);at<U>(m,0xa8)=2;at<U>(m,0xf4)=at<U>(m,0x104)=n->id;
 at<U>(m,0xf8)=n->position;at<U>(m,0xfc)=n->zone;at<U>(m,0x108)=at<U>(m,0x10c)=0;
 at<unsigned char>(m,0x100)=1;at<unsigned char>(m,0x101)=at<unsigned char>(m,0x102)=at<unsigned char>(m,0x103)=0;
 if(!preset(b,m,*n)){clearRevenge();return false;}
 loadArena(b,m,"arena_battle_test",0);
 // The native row handler closes this exact PlaybackUI global after queuing
 // its scene request. Do not invoke a destructor on an unrelated/stale UI.
 P*slot=reinterpret_cast<P*>(b+0x18a54c0);
 if(*slot==window){historyUi=nullptr;historyUiUser=0;call<void>(b,at<U>(at<P>(window,0),0x17c)-b,window);if(*slot==window)*slot=nullptr;}
 log(b,"revenge-preview-loaded",n->id,r.serial);return true;
}
static bool markRevengeStarted(U b,Economy&next,U target){
 if(!revengeEncounter(b,target))return true;
 for(U i=0;i<next.historyCount;++i)if(next.history[i].serial==revengeContext->serial){
  if(next.historyFlags[i]&1){economyNotice(b,"[V99_REVENGE_USED]");return false;}
  next.historyFlags[i]|=1;return true;
 }
 economyNotice(b,"[V99_REVENGE_EXPIRED]");return false;
}
// Filled after the user's trigger-period and asset-scope choices are known.
static void planSilentRevenge(U,Economy&,U){}
static void raidTick(U){}
