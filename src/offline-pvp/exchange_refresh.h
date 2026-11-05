// Keep the original 1/2/3 catalogue sampler and the native confirmation UI.
// The wallet is the authority for a refreshed generation; restoring it into
// native shop/profile memory is repeatable after either profile write fails.
static U exchangeQuoteUser,exchangeQuoteDay,exchangeQuoteIndex,exchangeQuoteFee;
static P exchangeQuoteWindow;
#ifdef PVP_EXCHANGE_CLOCK
static bool settleExchangeClock(U b,P shop);
#endif
static U exchangeRefreshPrice(U count){
 U n=sizeof(EXCHANGE_REFRESH_COSTS)/sizeof(EXCHANGE_REFRESH_COSTS[0]);
 return EXCHANGE_REFRESH_COSTS[count<n?count:n-1];
}
static bool stockIdsValid(const U*ids){
 for(U i=0;i<6;++i){if(!exchangeSpec(ids[i]))return false;for(U k=0;k<i;++k)if(ids[k]==ids[i])return false;}
 return true;
}
static bool sampleExchangeStock(U b,P shop,U*ids){
 U rows[6][4]{},chosen[6]{};P first=reinterpret_cast<P>(rows),begin=reinterpret_cast<P>(chosen);
 P offers[3]={first,first,first+sizeof(rows)},names[3]={begin,begin,begin+sizeof(chosen)};
 // The sampler only appends baseCount+randomCount+padCount (1+2+3) rows.
 if(at<U>(shop,4)!=1||at<U>(shop,8)!=2||at<U>(shop,12)!=3)return false;
 call<void>(b,0x106c3cc,shop,offers,names);
 if(offers[1]!=first+sizeof(rows)||names[1]!=begin+sizeof(chosen))return false;
 for(U i=0;i<6;++i){ids[i]=chosen[i];const ExchangeSpec*o=exchangeSpec(ids[i]);if(!o||rows[i][0]!=o->id||rows[i][1]!=o->quantity||rows[i][2]!=o->price)return false;}
 return stockIdsValid(ids);
}
static bool publishExchangeStock(U b,P shop){
 const Economy&s=economyRuntime.state;P p=profile(b);P ids=at<P>(p,0x79c),end=at<P>(p,0x7a0);
 bool sameGeneration=at<U>(p,0x798)==s.stockDay&&at<U>(p,0x794)==s.stockRefresh&&end>=ids&&U(end-ids)==24;
 if(sameGeneration)for(U i=0;i<6;++i)if(at<U>(ids,i*4)!=s.stockIds[i])sameGeneration=false;
 if(!sameGeneration){
  P pm=call<P>(b,0x1df738);unsigned char held=at<unsigned char>(pm,0x81);at<unsigned char>(pm,0x81)=1;
  call<void>(b,0x7153d4,p,s.stockDay);at<U>(p,0x794)=s.stockRefresh;
  P first=reinterpret_cast<P>(const_cast<U*>(s.stockIds));P vector[3]={first,first+24,first+24};
  call<void>(b,0x715430,p,vector);
  at<unsigned char>(pm,0x81)=held;
  // Stock setters do not schedule a profile save themselves. Request the
  // same immediate serialization path used by the native grant methods.
  at<float>(p,4)=-1.0f;call<void>(b,0x7110c4,p);
  log(b,"exchange-stock-applied",s.stockRefresh,s.stockIds[0]);
 }
 U rows[6][4]{};for(U i=0;i<6;++i){const ExchangeSpec*o=exchangeSpec(s.stockIds[i]);if(!o)return false;
  rows[i][0]=o->id;rows[i][1]=o->quantity;rows[i][2]=o->price;rows[i][3]=exchangeBought(b,o->id);}
 P first=reinterpret_cast<P>(rows);P vector[3]={first,first+sizeof(rows),first+sizeof(rows)};
 call<void>(b,0x106ceec,shop,exchangeRefreshPrice(s.stockRefresh),vector);
 return true;
}
static bool ensureExchangeStock(U b,P shop){
 if(economyRuntime.state.stockInitialized)return publishExchangeStock(b,shop);
 Economy next=economyRuntime.state;P p=profile(b),first=at<P>(p,0x79c),end=at<P>(p,0x7a0);
 bool existing=end>=first&&U(end-first)==24;
 if(existing){for(U i=0;i<6;++i)next.stockIds[i]=at<U>(first,4*i);existing=stockIdsValid(next.stockIds);}
 if(!existing&&!sampleExchangeStock(b,shop,next.stockIds))return false;
 next.stockInitialized=1;next.stockDay=at<U>(p,0x798);next.stockRefresh=at<U>(p,0x794);
 if(next.stockRefresh>1000000)return false;
 if(!commitProgression(b,manager(b),next))return false;
 return publishExchangeStock(b,shop);
}
static U prepareExchangeStock(U b,P shop,U refresh){
 if(exchangeBusy||!ensureExchangeStock(b,shop))return 1;
 // A recovered refresh may just have restored the generation needed by a
 // later purchase journal whose native profile write had not reached disk.
 if(!recoverExchange(b,shop))return 1;
#ifdef PVP_EXCHANGE_CLOCK
 if(!settleExchangeClock(b,shop))return 1;
#endif
 if(!refresh)return 1;
 P dialog=at<P>(reinterpret_cast<P>(b),0x18a584c);
 Economy next=economyRuntime.state;U price=exchangeRefreshPrice(next.stockRefresh);
 if(!dialog||dialog!=exchangeQuoteWindow||exchangeQuoteUser!=owner(b)||exchangeQuoteDay!=next.stockDay||exchangeQuoteIndex!=next.stockRefresh||exchangeQuoteFee!=price)return 1;
 exchangeQuoteWindow=nullptr; // Consume this confirmation even when it fails.
 if(next.medals<price){economyNotice(b,"[V71_EXCHANGE_MEDALS_REQUIRED]");return 1;}
 if(next.stockRefresh>=1000000||!sampleExchangeStock(b,shop,next.stockIds)){economyNotice(b,"[V38_PVP_SAVE_ERROR]");return 1;}
 next.medals-=price;++next.stockRefresh;
 if(!commitProgression(b,manager(b),next))return 1;
 publishExchangeStock(b,shop);log(b,"exchange-refreshed",price,next.stockRefresh);return 1;
}
extern "C" void offlineExchangeQuote(U b,P dialog,U mode){
 if(!regular(b)||mode!=0||!ensureEconomy(b,manager(b)))return;
#ifdef PVP_EXCHANGE_CLOCK
 if(!economyRuntime.state.stockInitialized||!settleExchangeClock(b,manager(b)+0x200))return;
#endif
 const Economy&s=economyRuntime.state;if(!s.stockInitialized)return;
 exchangeQuoteWindow=dialog;exchangeQuoteUser=owner(b);exchangeQuoteDay=s.stockDay;exchangeQuoteIndex=s.stockRefresh;exchangeQuoteFee=exchangeRefreshPrice(s.stockRefresh);
 log(b,"exchange-refresh-quote",exchangeQuoteFee,s.stockRefresh);
}
#ifdef PVP_EXCHANGE_CLOCK
#include "exchange_clock.h"
#endif
