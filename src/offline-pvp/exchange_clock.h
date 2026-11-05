// Match the original local-civil-day boundary without requiring server time.
struct ExchangeCalendar {U cycle,localNow;I offset;};
#ifdef PVP_EXCHANGE_CLOCK_TEST
static bool exchangeTestClockArmed;
#endif
static bool exchangeCalendar(U b,U timestamp,ExchangeCalendar&out){
 P tm=call<P>(b,0x147854,&timestamp);if(!tm)return false;I offset=at<I>(tm,0x24);
 if(offset< -86400||offset>86400||timestamp<86400||timestamp>0x7fffffff)return false;
 U local=timestamp+offset,day=local/86400,second=local%86400;
 out={day-(second<EXCHANGE_AUTO_AT?1u:0u),local,offset};return true;
}
static U exchangeShopNow(U b){
 U now=realNow(b);
#ifdef PVP_EXCHANGE_CLOCK_TEST
 now+=economyRuntime.state.stockTestOffset;
#endif
 return now;
}
static bool settleExchangeClock(U b,P shop){
 Economy next=economyRuntime.state;if(!next.stockInitialized||exchangeBusy)return false;
#ifdef PVP_EXCHANGE_CLOCK_TEST
 // Start the temporary countdown on the first visible shop frame, rather
 // than during manager construction while the player is still on menus.
 if(!next.stockClockInitialized&&!exchangeTestClockArmed)return true;
#endif
 ExchangeCalendar c;if(!exchangeCalendar(b,exchangeShopNow(b),c))return false;
 bool initialize=!next.stockClockInitialized;
#ifndef PVP_EXCHANGE_CLOCK_TEST
 // A normal package can safely replace the temporary accelerated test build.
 if(next.stockTestOffset){next.stockTestOffset=0;initialize=true;}
#endif
 if(initialize){
#ifdef PVP_EXCHANGE_CLOCK_TEST
  // Only shop time is shifted. The persisted offset survives a test restart;
  // currency production and every training/research timer keep real time.
  U target=(c.cycle+1)*86400+EXCHANGE_AUTO_AT;
  next.stockTestOffset=I(target-c.localNow)-45;
  if(!exchangeCalendar(b,realNow(b)+next.stockTestOffset,c))return false;
#endif
  next.stockClockInitialized=1;next.stockClockDay=c.cycle;
  if(!commitProgression(b,manager(b),next))return false;
  log(b,"exchange-clock-initialized",c.cycle,U(next.stockTestOffset));return true;
 }
 // Backward clock changes never grant another stock generation. Forward
 // jumps across several missed days produce one current catalogue.
 if(c.cycle<=next.stockClockDay)return true;
 if(!recoverExchange(b,shop)||!sampleExchangeStock(b,shop,next.stockIds))return false;
 next.stockClockDay=c.cycle;next.stockRefresh=0;
 // stockDay remains the opaque generation tag used by existing purchase
 // receipts. Rebasing the civil clock during migration must not erase sales.
 ++next.stockDay;exchangeQuoteWindow=nullptr;
 if(!commitProgression(b,manager(b),next))return false;
 publishExchangeStock(b,shop);log(b,"exchange-auto-refreshed",c.cycle,next.stockIds[0]);return true;
}
extern "C" U offlineExchangeClockMode(U b){
#ifdef PVP_EXCHANGE_CLOCK_TEST
 return 1;
#else
 return 0;
#endif
}
struct ExchangeClockView {P ui;U user,second;};
static ExchangeClockView exchangeClockView;
extern "C" void offlineExchangeClockDraw(U b,P ui){
 if(!regular(b)||!ui||!ensureEconomy(b,manager(b)))return;
 U now=exchangeShopNow(b),user=owner(b);ExchangeClockView&v=exchangeClockView;
 if(v.ui==ui&&v.user==user&&v.second==now)return;v={ui,user,now};
 P shop=manager(b)+0x200;
 if(!economyRuntime.state.stockInitialized&&!ensureExchangeStock(b,shop))return;
#ifdef PVP_EXCHANGE_CLOCK_TEST
 exchangeTestClockArmed=true;
#endif
 if(!settleExchangeClock(b,shop))return;
 ExchangeCalendar c;if(!exchangeCalendar(b,exchangeShopNow(b),c))return;
 U day=economyRuntime.state.stockClockDay,target=(day+1)*86400+EXCHANGE_AUTO_AT;
 U left=target>c.localNow?target-c.localNow:0;if(left>359999)left=359999;
 P label=at<P>(ui,0xe8);if(!label)return;
 U text[9]={U('0')+(left/3600)/10,U('0')+(left/3600)%10,':',U('0')+(left/60%60)/10,U('0')+(left/60)%10,':',U('0')+(left%60)/10,U('0')+left%10,0};
 P wide=nullptr;char allocator=0;call<void>(b,0x14eb451,&wide,text,&allocator);
 call<void>(b,0x10c2548,label,&wide);release(b,wide,true);
}
