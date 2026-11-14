// Each residential slot keeps its own deadline in the atomic economy record.
static U continueProtectedNeighbor;
static U starCups(U stars){
 return stars>=1&&stars<=3?2*stars-1:0;
}
static U neighborProtectionDeadline(U b){
 U now=realNow(b);
 return now<=0xffffffffu-1800?now+1800:0xffffffffu;
}
static U neighborProtectionUntil(U b,const NpcPreset&n){
 const auto&r=economyRuntime;
 const NpcPreset*local=npc(n.id);
 if(!local||local->evil||!r.loaded||r.blocked||r.user!=owner(b))return 0;
 U until=r.state.neighborProtectedUntil[neighborProtectionIndex(local)];
 return until>realNow(b)?until:0;
}
static bool rejectProtectedNeighbor(U b,const NpcPreset&n){
 if(!neighborProtectionUntil(b,n))return false;
 economyNotice(b,"[PVP_MAP_PVP_STATE]");
 log(b,"neighbor-attack-protected",n.id);
 return true;
}
static void beginProtectionOnReturn(U b){
 U id=continueProtectedNeighbor;
 continueProtectedNeighbor=0;
 const NpcPreset*n=npc(id);
 if(!n||!economyRuntime.loaded||economyRuntime.user!=owner(b)||!economyRuntime.state.neighborProtectedUntil[neighborProtectionIndex(n)])return;
 Economy next=economyRuntime.state;
 U&until=next.neighborProtectedUntil[neighborProtectionIndex(n)];
 U deadline=neighborProtectionDeadline(b);
 if(until!=deadline){
  until=deadline;
  ++next.sequence;
  if(saveEconomy(b,next))economyRuntime.state=next;
  else log(b,"neighbor-protection-return-save-failed",id);
 }
 U savedDeadline=economyRuntime.state.neighborProtectedUntil[neighborProtectionIndex(n)];
 P m=manager(b),first=at<P>(m,0x128),end=at<P>(m,0x12c);
 if(first&&end>=first&&U(end-first)<=64*256&&U(end-first)%64==0){
  for(P row=first;row<end;row+=64){
   if(at<U>(row,0)!=id||at<U>(row,0x1c)!=n->zone||at<U>(row,0x20)!=n->position)continue;
   at<U>(row,0x24)=2;
   at<U>(row,0x28)=savedDeadline;
   break;
  }
 }
 log(b,"neighbor-protection-started",id,savedDeadline);
}
static void expireNeighborLabels(U b,P m){
 if(!economyRuntime.loaded||economyRuntime.user!=owner(b))return;
 P first=at<P>(m,0x128),end=at<P>(m,0x12c);
 if(!first||end<first||U(end-first)>64*256||U(end-first)%64)return;
 U now=realNow(b);
 for(P row=first;row<end;row+=64){
  if(at<U>(row,0x24)!=2||at<U>(row,0x28)>now)continue;
  const NpcPreset*n=npc(at<U>(row,0));
  if(n&&!n->evil&&at<U>(row,0x1c)==n->zone&&at<U>(row,0x20)==n->position){
   at<U>(row,0x24)=1;
   at<U>(row,0x28)=0;
  }
 }
}
// Native map drawing expects a synchronized clock for its protection label.
extern "C" U offlineNeighborMapClock(U b,P row){
 const NpcPreset*n=npc(at<U>(row,0));
 if(regular(b)&&n&&!n->evil&&at<U>(row,0x1c)==n->zone&&at<U>(row,0x20)==n->position)return realNow(b);
 call<void>(b,0xf754ac);
 return call<U>(b,0xf7530c);
}
