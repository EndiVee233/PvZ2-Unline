// Native map regions are {zone, starcoin price, closed byte + padding} at
// manager+11c. Cloud rendering and the existing kind-0 confirmation use them.
extern "C" U offlineRegionMode(){return 1;}
#ifdef PVP_REGION_BALANCE_ONLY
extern "C" U offlineRegionBalanceOnlyMode(){return 1;}
#endif
static P regionPanel;
static U regionPanelUser;
extern "C" void offlineRegionPanelReady(U b,P panel){
 regionPanel=nullptr;
 if(panel&&regular(b)&&at<U>(panel,0xa4)==0){regionPanel=panel;regionPanelUser=owner(b);}
}
static U regionCost(U zone){
 if(zone<2||zone>6)return 0;U price=10000;
 for(U i=3;i<=zone;++i)price+=5000+i*500;
 return price;
}
static bool regionOpen(U zone){
 return zone>=1&&zone<=6&&economyRuntime.loaded&&!economyRuntime.blocked&&
  economyRuntime.state.regionsInitialized&&(economyRuntime.state.regionsOpen&(1u<<(zone-1)));
}
#ifndef PVP_REGION_BALANCE_ONLY
static U regionBaseLevel(U zone){
 U price=regionCost(zone);for(U i=0;i<20;++i)if(BASE_SPECS[i].coinLimit>=price)return i+1;
 return 21;
}
#endif
static void projectRegions(U b,P m){
 auto&r=economyRuntime;
 if(!regular(b)||!r.loaded||r.blocked||r.user!=owner(b)||!r.state.regionsInitialized)return;
 for(U zone=2;zone<=6;++zone){
  P first=at<P>(m,0x11c),last=at<P>(m,0x120),record=nullptr;
  if(bool(first)!=bool(last)||(first&&last<first)||U(last-first)>12*64||U(last-first)%12)return;
  for(P p=first;p<last;p+=12)if(at<U>(p,0)==zone){record=p;break;}
  U item[3]={zone,regionCost(zone),regionOpen(zone)?0u:1u};
  if(record){at<U>(record,4)=item[1];at<U>(record,8)=item[2];}
  else call<void>(b,0x1046d44,m,item);
 }
}
// Remove only our own locked-area fixtures when changing local players.
// Other native records keep their identity and ownership.
static void removeLockedNeighbors(U b,P m){
 if(!ensureEconomy(b,m))return;
 P first=at<P>(m,0x128),last=at<P>(m,0x12c);
 if(bool(first)!=bool(last)||(first&&last<first)||U(last-first)>64*256||U(last-first)%64)return;
 for(P p=first;p<last;){const NpcPreset*n=npc(at<U>(p,0));
  if(n&&!n->evil&&!regionOpen(n->zone)&&at<U>(p,28)==n->zone&&at<U>(p,32)==n->position){
   release(b,at<P>(p,8),true);bytes(p,p+64,U(last-p-64));last-=64;at<P>(m,0x12c)=last;
  }else p+=64;
 }
 first=at<P>(m,0x110);last=at<P>(m,0x114);
 if(bool(first)!=bool(last)||(first&&last<first)||U(last-first)>64*256||U(last-first)%64)return;
 for(P p=first;p<last;){const BusinessPlot*s=businessId(at<U>(p,0));
  if(s&&!regionOpen(s->zone)&&at<U>(p,48)==s->zone&&at<U>(p,52)==s->position){
   release(b,at<P>(p,16),true);bytes(p,p+64,U(last-p-64));last-=64;at<P>(m,0x114)=last;
  }else p+=64;
 }
}
static U regionAction(U b,P panel,U button){
 if(!panel||!regular(b)||at<U>(panel,0xa4)!=0)return 0;
 if(button!=202)return 0; // Native Cancel/close retains its normal handler.
 U zone=at<U>(panel,0xac);if(zone<2||zone>6||at<U>(panel,0xa8)!=0)return 1;
 if(regionPanel!=panel||regionPanelUser!=owner(b))return 1;
 P m=manager(b);if(!ensureEconomy(b,m))return 1;tickProgression(b);
 auto&r=economyRuntime;
 if(r.blocked||r.user!=owner(b)||!r.state.initialized)return 1;
 P map=at<P>(panel,0xc0);if(!map)return 1;
 if(regionOpen(zone)){call<void>(b,0x100a864,map);return 1;}
 if(!regionOpen(zone-1)){economyNotice(b,"[V93_PREVIOUS_REGION_REQUIRED]");return 1;}
#ifndef PVP_REGION_BALANCE_ONLY
 if(r.state.baseLevel<regionBaseLevel(zone)){
  char requirement[]="[V93_REGION_0_REQUIRED]";requirement[12]=char('0'+zone);
  economyNotice(b,requirement);return 1;
 }
#endif
 U price=regionCost(zone);
 if(at<U>(panel,0x144)!=price){economyNotice(b,"[V38_PVP_SAVE_ERROR]");return 1;}
 if(r.state.coins<price){economyNotice(b,"[V93_REGION_COINS_REQUIRED]");return 1;}
 Economy next=r.state;next.coins-=price;next.regionsOpen|=1u<<(zone-1);
 if(!commitProgression(b,m,next))return 1;
 neighbors(b,m);call<void>(b,0x100a864,map);
 log(b,"region-unlocked",zone,price);return 1;
}
