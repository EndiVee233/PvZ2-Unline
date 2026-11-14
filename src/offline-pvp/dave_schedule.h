// Persist a single visitor slot. The ordinary roster remains underneath it,
// so refresh/restart cannot create two houses at the same map position.
static bool replaceDaveNeighbor(U b,U id,U cycle){
 auto*old=findEncounter(*neighborRoster,id);if(!old)return false;
 auto*next=call<NeighborRoster*>(b,0x147938,sizeof(NeighborRoster));if(!next)return false;
 *next=*neighborRoster;auto*entry=findEncounter(*next,id);
 U seed=neighborMix(owner(b)^id^cycle^0xd32ac765u);
 generateNeighbor(*entry,id,seed,8,matchedNeighborCups(economyRuntime.state.cups,seed));
 ++next->sequence;bool ok=saveRoster(b,*next);
 if(ok)*neighborRoster=*next;
 call<void>(b,0x147950,next);return ok;
}
static bool daveCandidate(const NpcPreset&n){
 return !n.evil&&regionOpen(n.zone)
#ifdef PVP_VISITOR_MAP_FIX
 &&n.zone==1
#endif
 ;
}
static bool ensureDaveSchedule(U b,P m){
 if(!ensureNeighborRoster(b,m))return false;
 U day;if(!pvpCivilDay(b,day))return false;
 Economy next=economyRuntime.state;
 // A defeated visitor becomes an ordinary (not special/shared) new neighbor.
 if(next.daveReplacement){
  if(!replaceDaveNeighbor(b,next.daveTarget,next.daveRefreshDay))return false;
  next.neighborProtectedUntil[neighborProtectionIndex(npc(next.daveTarget))]=0;
  next.daveTarget=next.daveReplacement=0;
 }
 U cycle=lastDaveRefreshDay(day);
 bool moveHome=false;
#ifdef PVP_VISITOR_MAP_FIX
 const NpcPreset*prior=npc(next.daveTarget);moveHome=next.daveActive&&prior&&prior->zone!=1;
 if(moveHome&&cycle<next.daveRefreshDay)cycle=next.daveRefreshDay;
#endif
 if(cycle>next.daveRefreshDay||moveHome){
  if(next.daveActive){
   if(!replaceDaveNeighbor(b,next.daveTarget,next.daveRefreshDay))return false;
   next.neighborProtectedUntil[neighborProtectionIndex(npc(next.daveTarget))]=0;
  }
  U count=0;for(const auto& n:NPCS)if(daveCandidate(n))++count;
  if(!count)return false;
  U pick=neighborRemainder(neighborMix(owner(b)^cycle^0x85c41d29u),count);
  for(const auto& n:NPCS)if(daveCandidate(n)){
   if(!pick){next.daveTarget=n.id;break;}--pick;
  }
  next.daveRefreshDay=cycle;next.daveActive=1;
 }
 const Economy&old=economyRuntime.state;
 if(next.daveRefreshDay!=old.daveRefreshDay||next.daveTarget!=old.daveTarget||next.daveReplacement!=old.daveReplacement){
  ++next.sequence;if(!saveEconomy(b,next)){economyNotice(b,"[V38_PVP_SAVE_ERROR]");return false;}
  economyRuntime.state=next;log(b,"dave-schedule",next.daveRefreshDay,next.daveTarget);
 }
 U wins=next.daveWins;
 at<U>(m,0x15c)=next.daveActive&&wins>=DAVE_ROUND_COUNT?DAVE_ROUND_COUNT-1:wins;
 return true;
}
static void removeScheduledDaveRecords(U b,P m){
 P first=at<P>(m,0x128),last=at<P>(m,0x12c);
 if(!first||last<first||U(last-first)>64*256||U(last-first)%64)return;
 P out=first;
 for(P p=first;p<last;p+=64){
  const NpcPreset*n=npc(at<U>(p,0));
  bool hidden=n&&(n->evil||economyRuntime.state.daveActive&&n->id==economyRuntime.state.daveTarget);
  if(hidden){release(b,at<P>(p,8),true);continue;}
  if(out!=p)bytes(out,p,64);out+=64;
 }
 at<P>(m,0x12c)=out;
}
static bool scheduledHouseSelected(const NpcPreset&n,P m){
 const NpcPreset*where=&n;
 if(n.evil){
  if(!economyRuntime.state.daveActive)return false;
  where=npc(economyRuntime.state.daveTarget);if(!where)return false;
 }
 return where->zone==at<U>(m,0xfc)&&where->position==at<U>(m,0xf8);
}
