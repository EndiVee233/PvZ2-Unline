extern "C" U offlineBusinessCollectionMode(){return 1;}
static bool collectBusiness(U b,const BusinessPlot& plot){
 P m=manager(b);if(!regular(b)||!ensureEconomy(b,m))return false;
 tickProgression(b);EconomyRuntime&r=economyRuntime;
 U bit=businessBit(plot.id);if(r.blocked||!r.state.initialized||!(r.state.businessOwnedMask&bit))return false;
 Economy next=r.state;auto& stock=next.businessStocks[bit==1?0:1];
 U coins=stock.coins,medals=stock.medals;
 if(coins>2000000000u-next.coins)coins=2000000000u-next.coins;
 if(medals>2000000000u-next.medals)medals=2000000000u-next.medals;
 if(!coins&&!medals)return true;
 next.coins+=coins;next.medals+=medals;stock.coins-=coins;stock.medals-=medals;
 // Preserve the fractional second remainder. A capped wallet leaves any
 // unclaimed whole units in the shop, never deletes earned stock.
 if(!commitProgression(b,m,next))return false;
 log(b,"business-rent-collected",coins,medals);return true;
}
