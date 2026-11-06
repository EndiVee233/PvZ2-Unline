// First restore independent business map records and their native detail panel.
// Ownership, garrisons and rent are deliberately separate from residential raids.
struct BusinessPlot {U id,zone,position;U name[8];};
static const BusinessPlot BUSINESSES[]={
 {0x71000001,3,2,{0x5496,0x5561,0x5e97,0}},
 {0x71000002,3,3,{0x5546,0x5e97,0}}
};
extern "C" U offlineBusinessMapMode(){return 1;}
#ifdef PVP_BUSINESS_OWNER
// The original getter parses the server account id, which is zero offline.
// Zero is also the unoccupied-owner sentinel. Use the selected local profile
// for native ownership comparisons; keep wallet/save keys unchanged. A local
// profile numbered zero receives a nonzero UI identity, never the sentinel.
extern "C" U offlineBusinessIdentity(U b){
 if(!regular(b))return 0;U user=owner(b);return user?user:0x7fffffff;
}
#endif
static const BusinessPlot* businessPlot(U zone,U position){
 for(U i=0;i<sizeof(BUSINESSES)/sizeof(BUSINESSES[0]);++i)
  if(BUSINESSES[i].zone==zone&&BUSINESSES[i].position==position)return BUSINESSES+i;
 return nullptr;
}
#ifdef PVP_BUSINESS_SCOUT
extern "C" U offlineBusinessScoutMode(){return 1;}
static const BusinessPlot* businessId(U id){
 for(U i=0;i<sizeof(BUSINESSES)/sizeof(BUSINESSES[0]);++i)if(BUSINESSES[i].id==id)return BUSINESSES+i;
 return nullptr;
}
static bool scoutBusiness(U b,const BusinessPlot&s,bool attack=false);
#endif
#ifdef PVP_BUSINESS_BATTLE
extern "C" U offlineBusinessBattleMode(){return 1;}
static U businessBit(U id){for(U i=0;i<2;++i)if(BUSINESSES[i].id==id)return 1u<<i;return 0;}
static void projectBusinessOwners(U b,P m);
static bool attackBusiness(U b,const BusinessPlot&s);
#endif
#ifdef PVP_BUSINESS_DEFENSE
extern "C" U offlineBusinessDefenseMode(){return 1;}
static bool defendBusiness(U b,const BusinessPlot&s);
#endif
#ifdef PVP_BUSINESS_COLLECTION
static bool collectBusiness(U b,const BusinessPlot&s);
#endif
static void projectBusinesses(U b,P m){
 if(!regular(b))return;
 for(U i=0;i<sizeof(BUSINESSES)/sizeof(BUSINESSES[0]);++i){
  const BusinessPlot&s=BUSINESSES[i];bool occupied=false;
#ifdef PVP_REGIONS
  if(!regionOpen(s.zone))continue;
#endif
  P begin=at<P>(m,0x110),end=at<P>(m,0x114);
  if((begin&&end<begin)||U(end-begin)>64*256||U(end-begin)%64)return;
  for(P p=begin;p<end;p+=64)if(at<U>(p,48)==s.zone&&at<U>(p,52)==s.position){occupied=true;break;}
  // Never replace a server/foreign record or manufacture player ownership.
  if(occupied)continue;
  P first=at<P>(m,0x128),last=at<P>(m,0x12c);
  if((first&&last<first)||U(last-first)>64*256||U(last-first)%64)return;
  for(P p=first;p<last;p+=64)if(at<U>(p,28)==s.zone&&at<U>(p,32)==s.position){occupied=true;break;}
  if(occupied)continue;
  // Local unoccupied fixtures: no accrued funds or production before capture.
  // Capacity is a provisional local value, not a recovered server economy.
  alignas(8) U record[16]={s.id,0,0,0,0,1,0,2000,0,2000,0,0,s.zone,s.position,1,0};
  char alloc=0;call<void>(b,0x14eb451,reinterpret_cast<P>(record)+16,s.name,&alloc);
  call<void>(b,0x1046a04,m,record);release(b,reinterpret_cast<P>(record[4]),true);
  log(b,"business-map-added",s.zone,s.position);
 }
#ifdef PVP_BUSINESS_BATTLE
 projectBusinessOwners(b,m);
#endif
}
static bool localBusinessPanel(U b,P panel){
 if(!panel||!regular(b))return false;
 U kind=at<U>(panel,0xa4);if(kind!=3
#ifdef PVP_BUSINESS_BATTLE
 &&kind!=2
#endif
 )return false;
 const BusinessPlot*s=businessPlot(at<U>(panel,0xac),at<U>(panel,0xa8));if(!s)return false;
 P m=manager(b),begin=at<P>(m,0x110),end=at<P>(m,0x114);
 if(!begin||end<begin||U(end-begin)>64*256||U(end-begin)%64)return false;
 for(P p=begin;p<end;p+=64)if(at<U>(p,48)==s->zone&&at<U>(p,52)==s->position)
  return at<U>(p,0)==s->id&&(at<U64>(p,8)==0
#ifdef PVP_BUSINESS_BATTLE
  ||at<U64>(p,8)==offlineBusinessIdentity(b)
#endif
  );
 return false;
}
// Scouting is local when enabled; other unfinished shop actions must not fall
// through into old server requests. Closing the panel remains the original
// handler; residence and own-base events pass.
extern "C" U offlineBusinessAction(U b,P panel,U button){
#ifdef PVP_RANDOM_NEIGHBORS
 if(neighborAction(b,panel,button))return 1;
#endif
#ifdef PVP_REGIONS
 if(regionAction(b,panel,button))return 1;
#endif
 if(button==203||!localBusinessPanel(b,panel))return 0;
#ifdef PVP_BUSINESS_COLLECTION
 if(button==200&&at<U>(panel,0xa4)==2){
  const BusinessPlot*s=businessPlot(at<U>(panel,0xac),at<U>(panel,0xa8));
  if(s&&collectBusiness(b,*s))if(P map=at<P>(panel,0xc0))call<void>(b,0x100a864,map);
  return 1;
 }
#endif
#ifdef PVP_BUSINESS_DEFENSE
 if(button==201&&at<U>(panel,0xa4)==2){
  const BusinessPlot*s=businessPlot(at<U>(panel,0xac),at<U>(panel,0xa8));
  if(s&&defendBusiness(b,*s))call<void>(b,0x100a864,at<P>(panel,0xc0));
  return 1;
 }
#endif
#ifdef PVP_BUSINESS_SCOUT
 if(button==205){
  const BusinessPlot*s=businessPlot(at<U>(panel,0xac),at<U>(panel,0xa8));
  if(s&&scoutBusiness(b,*s))call<void>(b,0x100a864,at<P>(panel,0xc0));
  return 1;
 }
#endif
 log(b,"business-action-pending",button);return 1;
}
extern "C" U offlineBusinessRaidInput(U b,P panel){
 if(!localBusinessPanel(b,panel))return 0;
#ifdef PVP_BUSINESS_BATTLE
 // Keep the original big-button hit test and army validation. The request
 // reaches offlineAttack only when the user actually clicks its rectangle.
 if(at<U>(panel,0xa4)==3)return 0;
#endif
 log(b,"business-raid-pending");return 1;
}
