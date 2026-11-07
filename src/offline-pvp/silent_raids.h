// v99 replaces the foreground raid experiment. Background outcomes follow the
// user's explicit probability rules and never create/finish a Board.
#include "silent_raid_policy.h"
#include "frozen_encounters.h"
static_assert(sizeof(Economy)==2840,"silent raid save layout");
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
 if(s.raidTestMask&~7u||s.raidTestDone&~s.raidTestMask||(!s.raidTestMask&&(s.raidTestDue||s.raidTestDone))||(s.raidTestMask&&!s.raidTestDue))return false;
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
  if(h.kind<3){
   if(s.historyFlags[i])return false;
   if(s.historyMedals[i]){
#ifdef PVP_DAVE_REFERENCE
    const NpcPreset* opponent=npc(h.target);
    if(h.kind!=1||!opponent||!opponent->evil||!h.stars||s.historyMedals[i]<250||s.historyMedals[i]>500||s.historyMedals[i]%50)return false;
#else
    return false;
#endif
   }
  }
  if(h.kind>=3&&!h.stars&&(h.coins||s.historyMedals[i]||s.historyFlags[i]))return false;
 }
 for(U i=0;i<s.retaliationCount;++i){const auto&j=s.retaliations[i];const NpcPreset*n=npc(j.target);
  if(!n||n->evil||!j.seed||j.kind>7||!j.due||j.stars>3||!(j.frozenLo|j.frozenHi))return false;
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
static U silentPollUser,silentPollAt;
static bool silentRunning;
static U raidRoll(U&rng,U bound){
 if(!bound)return 0;U limit=0xffffffffu-neighborRemainder(0xffffffffu,bound),value;
 do{value=neighborRandom(rng)-1;}while(value>=limit);
 return neighborRemainder(value,bound);
}
static void initializeSilent(U b,Economy&next,U now){
 if(next.raidInitialized)return;
 next.raidInitialized=1;next.raidRng=neighborMix(owner(b)^now^next.sequence^0xa365bc71u);next.raidCheckedAt=now;
 for(U i=0;i<2;++i)if(next.businessOwnedMask&(1u<<i))next.shopRaidAt[i]=now;
 // Old v98 foreground jobs are deliberately not replayed or charged.
}
static bool chooseRaidOpponent(U b,Economy&next,bool fbi,NeighborEncounter&out){
 if(!ensureNeighborRoster(b,manager(b)))return false;
 U count=0;
 for(U i=0;i<NEIGHBOR_SLOT_COUNT;++i){const auto&e=neighborRoster->entries[i];const auto*n=npc(e.id);
  if(e.seed&&n&&regionOpen(n->zone)&&((e.kind==1)==fbi))++count;
 }
 if(count){U pick=raidRoll(next.raidRng,count);
  for(U i=0;i<NEIGHBOR_SLOT_COUNT;++i){const auto&e=neighborRoster->entries[i];const auto*n=npc(e.id);
   if(e.seed&&n&&regionOpen(n->zone)&&((e.kind==1)==fbi)){if(!pick){out=e;return true;}--pick;}
  }
 }
 // FBI can still make its single global daily roll after all visible FBI
 // houses have been refreshed away. Freeze a genuine FBI-specific formation.
 if(fbi)for(U i=0;i<NPC_COUNT;++i)if(!NPCS[i].evil&&regionOpen(NPCS[i].zone)){
  generateNeighbor(out,NPCS[i].id,neighborRandom(next.raidRng),1);return true;
 }
 return false;
}
static bool planSilentRevenge(U b,Economy&next,U target,U stars){
 const NeighborEncounter*e=lastBattleEncounter&&lastBattleEncounter->ready&&lastBattleEncounter->user==owner(b)&&lastBattleEncounter->opponent.id==target?&lastBattleEncounter->opponent:encounter(b,target);
 if(!e||!e->seed)return false;
 if(e->kind==1&&!stars)return true;
 Store home{};if(e->kind!=1&&!readStore(b,home))return true;
 if(next.retaliationCount>=64){log(b,"silent-revenge-queue-full");return false;}
 U now=realNow(b);initializeSilent(b,next,now);U frozen[2]{};
 if(!freezeEncounter(b,*e,frozen)){log(b,"silent-revenge-snapshot-failed");return false;}
 next.retaliations[next.retaliationCount++]={target,e->seed,e->kind,now+30,stars,frozen[0],frozen[1]};
 log(b,"silent-revenge-queued",target,stars);return true;
}
static bool appendSilentDefense(U b,Economy&next,const NeighborEncounter&enemy,U stars,U defended,U when,U lo,U hi){
 if(next.sequence>=0xfffffffeu)return false;
 U coins=stars?raidLoss(next.coins):0,medals=stars?raidLoss(next.medals):0;
 next.coins-=coins;next.medals-=medals;
 U id=activeEncounterId,seed=activeEncounterSeed,kind=activeEncounterKind;
 activeEncounterId=enemy.id;activeEncounterSeed=enemy.seed;activeEncounterKind=enemy.kind;
 appendHistory(b,next,enemy.id,stars,coins);
 activeEncounterId=id;activeEncounterSeed=seed;activeEncounterKind=kind;
 next.history[0].kind=defended?4:3;next.history[0].time=when;
 next.historyMedals[0]=medals;next.historyDefended[0]=defended;
 next.historyFrozen[0][0]=lo;next.historyFrozen[0][1]=hi;++next.sequence;
 if(defended){U index=businessBit(defended)==1?0:1;next.businessOwnedMask&=~(1u<<index);
  next.shopEnemy[index]=enemy.id;next.shopEnemySeed[index]=enemy.seed;next.shopEnemyKind[index]=enemy.kind;
  // Existing inventory is retained but stops producing until recapture.
 }
 return true;
}
static bool resolveSilentJob(U b,Economy&next,U index,U strength,U when){
 auto job=next.retaliations[index];U outcome=revengeOutcome(job.kind,job.stars,strength,raidRoll(next.raidRng,10000));
 if(outcome){NeighborEncounter enemy{};
  if(readFrozen(b,job.frozenLo,job.frozenHi,enemy)!=1||enemy.id!=job.target||enemy.seed!=job.seed||enemy.kind!=job.kind)return false;
  if(!appendSilentDefense(b,next,enemy,outcome==2?3:0,0,when,job.frozenLo,job.frozenHi))return false;
 }
 for(U i=index+1;i<next.retaliationCount;++i)next.retaliations[i-1]=next.retaliations[i];
 next.retaliations[--next.retaliationCount]=Economy::Retaliation{};return true;
}
static void raidTick(U b){
 if(silentRunning||!regular(b)||!ensureEconomy(b,manager(b))||!economyRuntime.state.initialized||economyRuntime.busy)return;
 U now=realNow(b),user=owner(b);if(silentPollUser==user&&silentPollAt==now)return;
 silentPollUser=user;silentPollAt=now;silentRunning=true;economyRuntime.busy=true;
 Economy next=economyRuntime.state;bool changed=!next.raidInitialized,ok=true;initializeSilent(b,next,now);
#ifndef PVP_SILENT_RAID_TEST
 if(next.raidTestMask||next.raidTestDue||next.raidTestDone){next.raidTestMask=next.raidTestDue=next.raidTestDone=0;changed=true;}
#endif
 Store home{};bool hasHome=readStore(b,home);U strength=hasHome?defenseStrength(home):0;
 for(U processed=0;processed<96;++processed){
  U when=0xffffffffu,source=0,index=0;
  if(next.raidCheckedAt<=0xffffffffu-86400&&next.raidCheckedAt+86400<=now){when=next.raidCheckedAt+86400;source=1;}
  for(U i=0;i<2;++i)if(next.businessOwnedMask&(1u<<i)){
   if(!next.shopRaidAt[i]){next.shopRaidAt[i]=now;changed=true;}
   if(next.shopRaidAt[i]<=0xffffffffu-86400&&next.shopRaidAt[i]+86400<=now&&next.shopRaidAt[i]+86400<when){when=next.shopRaidAt[i]+86400;source=2;index=i;}
  }
  for(U i=0;i<next.retaliationCount;++i)if(next.retaliations[i].due<=now&&next.retaliations[i].due<when){when=next.retaliations[i].due;source=3;index=i;}
#ifdef PVP_SILENT_RAID_TEST
  if(next.raidTestMask&&next.raidTestDue<=now&&next.raidTestDue<=when){
   for(U bit=0;bit<3;++bit)if((next.raidTestMask&(1u<<bit))&&!(next.raidTestDone&(1u<<bit))){when=next.raidTestDue;source=4;index=bit;break;}
  }
#endif
  if(!source)break;changed=true;accrueProduction(next,when);
  if(source==3){if(!resolveSilentJob(b,next,index,strength,when)){ok=false;break;}continue;}
  U roll=raidRoll(next.raidRng,10000),outcome=0,defended=0;
#ifdef PVP_SILENT_RAID_TEST
  if(source==4){next.raidTestDone|=1u<<index;if(!index){outcome=3;next.raidCheckedAt=when;}
   else{U shop=index-1;next.shopRaidAt[shop]=when;if(next.businessOwnedMask&(1u<<shop)){outcome=2;defended=BUSINESSES[shop].id;}}
  }else
#endif
  if(source==1){next.raidCheckedAt=when;outcome=naturalOutcome(strength,roll);if(!hasHome&&outcome!=3)outcome=0;}
  else {next.shopRaidAt[index]=when;if(roll<1000){outcome=2;defended=BUSINESSES[index].id;}}
  if(outcome){NeighborEncounter enemy{};U frozen[2]{};
   bool chosen=chooseRaidOpponent(b,next,outcome==3,enemy);
   if(!chosen&&defended)chosen=chooseRaidOpponent(b,next,true,enemy);
   if(!chosen){if(outcome!=3)continue;ok=false;break;}
   if(!freezeEncounter(b,enemy,frozen)||!appendSilentDefense(b,next,enemy,outcome==1?0:3,defended,when,frozen[0],frozen[1])){ok=false;break;}
  }
 }
 if(changed&&ok){if(next.sequence==economyRuntime.state.sequence)++next.sequence;
  if(saveEconomy(b,next)){economyRuntime.state=next;applyEconomy(b,manager(b));projectBusinessOwners(b,manager(b));
   log(b,"silent-raids-committed",next.historyCount,next.retaliationCount);
  }else log(b,"silent-raids-save-failed");
 }else if(!ok)log(b,"silent-raids-snapshot-failed");
 economyRuntime.busy=false;silentRunning=false;
}
static bool silentBacklog(U b){
 const auto&s=economyRuntime.state;if(!s.raidInitialized||economyRuntime.user!=owner(b))return false;
 U now=realNow(b);
 if(s.raidCheckedAt<=now&&now-s.raidCheckedAt>=86400)return true;
 for(U i=0;i<2;++i)if((s.businessOwnedMask&(1u<<i))&&s.shopRaidAt[i]<=now&&now-s.shopRaidAt[i]>=86400)return true;
 for(U i=0;i<s.retaliationCount;++i)if(s.retaliations[i].due<=now)return true;
 return false;
}
static void silentTestArm(U b){
#ifdef PVP_SILENT_RAID_TEST
 if(!regular(b)||!ensureEconomy(b,manager(b)))return;
 Economy next=economyRuntime.state;if(next.raidTestMask){economyNotice(b,"[V99_TEST_ALREADY]");return;}
 U now=realNow(b);initializeSilent(b,next,now);next.raidTestMask=1|(next.businessOwnedMask<<1);next.raidTestDue=now+30;next.raidTestDone=0;++next.sequence;
 if(saveEconomy(b,next)){economyRuntime.state=next;silentPollAt=0;economyNotice(b,"[V99_TEST_ARMED]");log(b,"silent-test-armed",next.raidTestMask,next.raidTestDue);}
 else economyNotice(b,"[V38_PVP_SAVE_ERROR]");
#endif
}
extern "C" void offlineSilentHistogram(U,U strength,U kind,U playerStars,P output){
 for(U i=0;i<4;++i)at<U>(output,i*4)=0;
 for(U roll=0;roll<10000;++roll){U outcome=kind==8?naturalOutcome(strength,roll):revengeOutcome(kind,playerStars,strength,roll);++at<U>(output,outcome*4);}
}
