// First restore independent business map records and their native detail panel.
// Ownership, garrisons and rent are deliberately separate from residential raids.
struct BusinessPlot {U id,zone,position;U name[8];};
static const BusinessPlot BUSINESSES[]={
 {0x71000001,3,2,{0x5496,0x5561,0x5e97,0}},
 {0x71000002,3,3,{0x5546,0x5e97,0}}
};
extern "C" U offlineBusinessMapMode(){return 1;}
static const BusinessPlot* businessPlot(U zone,U position){
 for(U i=0;i<sizeof(BUSINESSES)/sizeof(BUSINESSES[0]);++i)
  if(BUSINESSES[i].zone==zone&&BUSINESSES[i].position==position)return BUSINESSES+i;
 return nullptr;
}
static void projectBusinesses(U b,P m){
 if(!regular(b))return;
 for(U i=0;i<sizeof(BUSINESSES)/sizeof(BUSINESSES[0]);++i){
  const BusinessPlot&s=BUSINESSES[i];bool occupied=false;
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
}
static bool localBusinessPanel(U b,P panel){
 if(!panel||!regular(b)||at<U>(panel,0xa4)!=3)return false;
 const BusinessPlot*s=businessPlot(at<U>(panel,0xac),at<U>(panel,0xa8));if(!s)return false;
 P m=manager(b),begin=at<P>(m,0x110),end=at<P>(m,0x114);
 if(!begin||end<begin||U(end-begin)>64*256||U(end-begin)%64)return false;
 for(P p=begin;p<end;p+=64)if(at<U>(p,48)==s->zone&&at<U>(p,52)==s->position)
  return at<U>(p,0)==s->id&&at<U64>(p,8)==0;
 return false;
}
// During the entrance-only milestone, never fall through into old server
// requests if an unimplemented shop action is clicked accidentally. Closing
// the panel remains the original handler; residence and own-base events pass.
extern "C" U offlineBusinessAction(U b,P panel,U button){
 if(button==203||!localBusinessPanel(b,panel))return 0;
 log(b,"business-action-pending",button);return 1;
}
extern "C" U offlineBusinessRaidInput(U b,P panel){
 if(!localBusinessPanel(b,panel))return 0;
 log(b,"business-raid-pending");return 1;
}
