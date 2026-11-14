// Fill Dave's old fixed plot without changing the accepted roster/save layout.
// v16+ retired raids.h; its opaque reserved word is otherwise unused. Keep
// a tagged refresh serial and sampled cups there, stable across restarts.
static NeighborEncounter* vacantEncounter;
static U vacantUser,vacantState;
static U vacantWord(U serial,U cups){return 0x80000000u|((serial&0x1fffffu)<<10)|(cups&1023);}
static const NeighborEncounter* vacantNeighbor(U b){
 if(!ensureEconomy(b,manager(b)))return nullptr;
 U word=economyRuntime.state.reserved;
 if(!(word&0x80000000u)||(word&1023)>550){
  Economy next=economyRuntime.state;U seed=neighborMix(owner(b)^0xa851f239u);
  next.reserved=vacantWord(0,matchedNeighborCups(next.cups,seed));++next.sequence;
  if(!saveEconomy(b,next))return nullptr;economyRuntime.state=next;word=next.reserved;
 }
 if(!vacantEncounter)vacantEncounter=call<NeighborEncounter*>(b,0x147938,sizeof(NeighborEncounter));
 if(!vacantEncounter)return nullptr;
 if(vacantUser!=owner(b)||vacantState!=word){
  U serial=(word>>10)&0x1fffff,seed=neighborMix(owner(b)^serial^0xa851f239u);
  generateNeighbor(*vacantEncounter,VACANT_HOME.id,seed,8,word&1023);
  vacantUser=owner(b);vacantState=word;
 }
 return vacantEncounter;
}
static bool replaceVacantNeighbor(U b){
 if(!vacantNeighbor(b))return false;
 Economy next=economyRuntime.state;U serial=(next.reserved>>10)&0x1fffff;
 if(serial==0x1fffff)return false;++serial;
 U seed=neighborMix(owner(b)^serial^0xa851f239u);
 next.reserved=vacantWord(serial,matchedNeighborCups(next.cups,seed));++next.sequence;
 if(!saveEconomy(b,next))return false;economyRuntime.state=next;return true;
}
