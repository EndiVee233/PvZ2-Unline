// Ordinary local neighbors only. Dave's challenge rewards are a separate task.
static U paidBattleSerial,paidBattleUser;
static bool paidBattleMatches(U b,const Economy&s){
 return paidBattleUser==owner(b)&&paidBattleSerial&&s.battleOpen==paidBattleSerial&&s.battleNpc==arenaNpc;
}
static void closeBattleJournal(Economy&s){
 s.battleSettled=s.battleOpen;s.battleOpen=s.battleNpc=s.battleStage=s.battleFee=0;
}
static bool beginBattleFee(U b,P m,const NpcPreset&n,bool live){
 if(n.evil)return true;
 if(!ensureEconomy(b,m))return false;
#ifdef PVP_NEIGHBOR_PROTECTION
 if(rejectProtectedNeighbor(b,n))return false;
#endif
 Economy next=economyRuntime.state;
 if(next.battleOpen){log(b,"battle-payment-already-open",next.battleOpen,next.battleNpc);return false;}
 if(!next.coins){economyNotice(b,"[PVP_ERROR_PVPCOIN_NOT_ENOUCH]");return false;}
 if(next.battleSerial==0xffffffffu){economyNotice(b,"[V38_PVP_SAVE_ERROR]");return false;}
#ifdef PVP_SILENT_RAIDS
 if(!markRevengeStarted(b,next,n.id))return false;
#endif
 --next.coins;++next.battleSerial;next.battleOpen=next.battleSerial;
 next.battleNpc=n.id;next.battleStage=live?2:1;next.battleFee=1;++next.sequence;
 if(!saveEconomy(b,next)){economyNotice(b,"[V38_PVP_SAVE_ERROR]");return false;}
 economyRuntime.state=next;paidBattleUser=owner(b);paidBattleSerial=next.battleOpen;
 call<void>(b,0x1042a5c,m,next.coins);log(b,"battle-fee-paid",next.battleOpen,next.coins);return true;
}
static void markPaidBattleStarted(U b){
#ifdef PVP_NPC_RAIDS
 if(raidActive(b))return;
#endif
 if(!paidBattleMatches(b,economyRuntime.state)||economyRuntime.state.battleStage!=1)return;
 Economy next=economyRuntime.state;next.battleStage=2;++next.sequence;
 if(saveEconomy(b,next)){economyRuntime.state=next;log(b,"paid-battle-started",next.battleOpen);}
 else log(b,"paid-battle-start-save-failed",next.battleOpen);
}
static bool closeAbandonedBattle(U b,P m){
 if(!ensureEconomy(b,m))return false;
 if(!economyRuntime.state.battleOpen)return true;
 if(!paidBattleMatches(b,economyRuntime.state))return false;
 Economy next=economyRuntime.state;
 if(next.battleStage==1&&next.coins<=2000000000u-next.battleFee)next.coins+=next.battleFee;
 closeBattleJournal(next);++next.sequence;
 if(!saveEconomy(b,next)){economyNotice(b,"[V38_PVP_SAVE_ERROR]");return false;}
 economyRuntime.state=next;call<void>(b,0x1042a5c,m,next.coins);log(b,"battle-abandoned",paidBattleSerial);return true;
}
static bool settleBattleReward(U b,Economy&next,U stars){
 if(stars>3||!paidBattleMatches(b,next))return false;
 U reward=100*stars/3;
 // The hard storage limit must not trap a completed battle in its result UI.
 if(reward>2000000000u-next.coins)reward=2000000000u-next.coins;
 next.coins+=reward;closeBattleJournal(next);return true;
}
