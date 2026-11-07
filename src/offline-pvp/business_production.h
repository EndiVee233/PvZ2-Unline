// Explicit user-approved temporary offline rates, not recovered server values.
extern "C" U offlineBusinessProductionMode(){return 1;}
static bool produceBusinesses(Economy& next,U now){
 bool changed=false;
 for(U i=0;i<2;++i){
  if(!(next.businessOwnedMask&(1u<<i)))continue;
  auto& stock=next.businessStocks[i];
  // Old v10 ownership has no acquisition time: begin empty now, never award
  // guessed rent for the period before this feature was installed.
  if(!stock.producedAt){stock.producedAt=now;changed=true;continue;}
  if(now<stock.producedAt)continue;
  U elapsed=now-stock.producedAt,coins=stock.coins,medals=stock.medals;
  produce(stock.coins,stock.coinFraction,40,2000,elapsed);
  produce(stock.medals,stock.medalFraction,20,2000,elapsed);
  stock.producedAt=now;
  changed=changed||coins!=stock.coins||medals!=stock.medals;
 }
 return changed;
}
static void projectBusinessStocks(U b,P m){
 const EconomyRuntime&r=economyRuntime;
 if(!r.loaded||r.blocked||r.user!=owner(b))return;
 P begin=at<P>(m,0x110),end=at<P>(m,0x114);U identity=offlineBusinessIdentity(b);
 if(!begin||end<begin||U(end-begin)>64*256||U(end-begin)%64)return;
 for(P p=begin;p<end;p+=64){const BusinessPlot* plot=businessId(at<U>(p,0));
  if(!plot||at<U>(p,48)!=plot->zone||at<U>(p,52)!=plot->position)continue;
  U index=businessBit(plot->id)==1?0:1;bool owned=r.state.businessOwnedMask&(1u<<index);
  U64 expected=owned?U64(identity):0;
#ifdef PVP_SILENT_RAIDS
  if(!owned)expected=r.state.shopEnemy[index];
#endif
  if(at<U64>(p,8)!=expected)continue;
  const auto& stock=r.state.businessStocks[index];
  at<U>(p,24)=owned?stock.medals:0;at<U>(p,28)=2000;
  at<U>(p,32)=owned?stock.coins:0;at<U>(p,36)=2000;
  at<U>(p,40)=expected?20:0;at<U>(p,44)=expected?40:0;
 }
}
