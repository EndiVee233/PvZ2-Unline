// ARENA_PVP_OCCUPY_BTN formats CURRENCY_COST both when constructed and when
// the live scout module updates its label. ARENA_PVP_BTN is a different button.
static U attackPreviewFee(U b,U original){
 U fee=original;const NpcPreset*n=npc(arenaNpc);
 if(n&&!n->evil&&regular(b)&&ensureEconomy(b,manager(b))){
  const Economy&s=economyRuntime.state;U day,attacks=s.neighborAttacks;
  if(pvpCivilDay(b,day)&&day>s.neighborAttackDay)attacks=0;
  fee=neighborAttackFee(attacks);
  static U lastUser,lastTarget,lastFee;
  if(lastUser!=owner(b)||lastTarget!=arenaNpc||lastFee!=fee){
   lastUser=owner(b);lastTarget=arenaNpc;lastFee=fee;
   log(b,"attack-preview-fee",fee,arenaNpc);
  }
 }
 return fee;
}
extern "C" P offlineAttackPreviewFormat(U b,P out,P text,P key,U original){
 return call<P>(b,0xd06a04,out,text,key,attackPreviewFee(b,original));
}
extern "C" U offlineAttackPreviewCost(U b,P m){
 return attackPreviewFee(b,call<U>(b,0x10449b8,m));
}
