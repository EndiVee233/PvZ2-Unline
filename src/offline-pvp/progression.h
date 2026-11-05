// Wallet, production and building queues share one atomic, per-player record.
static U levelOf(const Economy&s,U kind){return kind==1?s.baseLevel:kind==2?s.sunLevel:s.campLevel;}
static U upgradeCost(const Economy&s,U kind){U n=levelOf(s,kind)-1;return kind==1?BASE_SPECS[n].cost:kind==2?SUN_SPECS[n].cost:CAMP_SPECS[n].cost;}
static U upgradeSeconds(const Economy&s,U kind){U n=levelOf(s,kind)-1;return kind==1?BASE_SPECS[n].seconds:kind==2?SUN_SPECS[n].seconds:CAMP_SPECS[n].seconds;}
static void ownBaseRecord(U b,P m){
 const Economy&s=economyRuntime.state;const BaseSpec&base=BASE_SPECS[s.baseLevel-1];
 // Context kind 4 (own base) reads this dedicated six-word block, not the
 // BigMapInfo neighbor vector used by context kinds 2/3.
 at<U>(m,0x138)=s.medals;at<U>(m,0x13c)=base.medalLimit;at<U>(m,0x140)=s.coins;
 at<U>(m,0x144)=base.coinLimit;at<U>(m,0x148)=base.medals;at<U>(m,0x14c)=base.coins;
#ifdef PVP_RESIDENT_NEIGHBORS
 // The original map has a dedicated own-base house/label and kind-4 panel.
 // A second entry in the business vector overlays a numbered business tag.
 return;
#endif
 P first=at<P>(m,0x110),end=at<P>(m,0x114),record=nullptr;
 if(first&&end>=first&&U(end-first)<=64*256)for(P p=first;p<end;p+=64)if(at<U>(p,48)==1&&at<U>(p,52)==2){record=p;break;}
 if(!record){
  alignas(8) U item[16]={owner(b),0,owner(b),0,0,s.baseLevel,s.medals,base.medalLimit,s.coins,base.coinLimit,base.medals,base.coins,1,2,1,0};
  const U title[]={0x60a8,0x7684,0x57fa,0x5730,0};char alloc=0;
  call<void>(b,0x14eb451,reinterpret_cast<P>(item)+16,title,&alloc);call<void>(b,0x1046a04,m,item);release(b,reinterpret_cast<P>(item[4]),true);return;
 }
 at<U>(record,20)=s.baseLevel;at<U>(record,24)=s.medals;at<U>(record,28)=base.medalLimit;
 at<U>(record,32)=s.coins;at<U>(record,36)=base.coinLimit;at<U>(record,40)=base.medals;at<U>(record,44)=base.coins;
}
static void applyProgression(U b,P m){
 const Economy&s=economyRuntime.state;
 call<void>(b,0x1042aa8,m,s.medals);call<void>(b,0x1042b40,m,s.baseLevel);
 for(U kind=1;kind<=3;++kind)call<void>(b,0x1060f70,m+0x54,kind,levelOf(s,kind));
 U now=realNow(b);at<U>(m,0x6c)=s.upgradeKind;at<U>(m,0x70)=0;
 at<float>(m,0x74)=s.upgradeKind?at<float>(call<P>(b,0x1f7380),0x24)+float(s.upgradeDue>now?s.upgradeDue-now:0):0x1.fffffep127f;
 at<U>(m,0x15c)=s.daveWins;ownBaseRecord(b,m);
}
static bool commitProgression(U b,P m,Economy&next){
 ++next.sequence;if(!saveEconomy(b,next)){economyNotice(b,"[V38_PVP_SAVE_ERROR]");return false;}
 economyRuntime.state=next;
 if(regular(b))applyEconomy(b,m);else {call<void>(b,0x1042a5c,m,next.coins);applyProgression(b,m);}
 return true;
}
static void finishUpgrade(Economy&s){
 U kind=s.upgradeKind;if(kind==1){++s.baseLevel;s.home=s.baseLevel;}else if(kind==2)++s.sunLevel;else if(kind==3)++s.campLevel;
 s.upgradeKind=0;s.upgradeDue=0;
}
static void produce(U&balance,U&fraction,U rate,U cap,U elapsed){
 // Split whole hours to avoid a 32-bit overflow or a 64-bit division helper.
 if(balance>=cap){fraction=0;return;}
 if(elapsed>31536000)elapsed=31536000;
 U partial=fraction+(elapsed%3600)*rate;
 U earned=(elapsed/3600)*rate+partial/3600;fraction=partial%3600;
 if(earned>=cap-balance){balance=cap;fraction=0;}else balance+=earned;
}
static void tickProgression(U b){
 EconomyRuntime&r=economyRuntime;if(!r.loaded||r.blocked||!r.state.initialized||r.user!=owner(b))return;
 U now=realNow(b);Economy next=r.state;if(now<next.producedAt)return;
 U elapsed=now-next.producedAt;if(!elapsed&&(!next.upgradeKind||now<next.upgradeDue))return;
 bool completed=next.upgradeKind&&now>=next.upgradeDue;
 U before=completed&&next.upgradeDue>next.producedAt?next.upgradeDue-next.producedAt:completed?0:elapsed;
 const BaseSpec&base=BASE_SPECS[next.baseLevel-1];
 produce(next.coins,next.coinFraction,base.coins,base.coinLimit,before);
 produce(next.medals,next.medalFraction,base.medals,base.medalLimit,before);
 if(completed){finishUpgrade(next);const BaseSpec&after=BASE_SPECS[next.baseLevel-1];
  produce(next.coins,next.coinFraction,after.coins,after.coinLimit,elapsed-before);
  produce(next.medals,next.medalFraction,after.medals,after.medalLimit,elapsed-before);
 }
 next.producedAt=now;
 // Persist at most once per minute unless a whole currency unit or an upgrade changes.
 if(next.coins==r.state.coins&&next.medals==r.state.medals&&!completed&&elapsed<60)return;
 if(commitProgression(b,manager(b),next)&&completed)log(b,"building-upgrade-completed",next.baseLevel,next.campLevel);
}
extern "C" void offlineProgressionInit(U b){
 P m=manager(b);if(!profile(b)||!ensureEconomy(b,m,true))return;EconomyRuntime&r=economyRuntime;
 if(!r.state.initialized){
  Economy next=r.state;next.initialized=1;next.medals=200;
  // Existing offline wallets retain purchases and spending during migration.
  if(!r.loadedFromDisk)next.coins=1000;
  next.baseLevel=next.home;next.sunLevel=1;next.campLevel=1;next.producedAt=realNow(b);
  if(!commitProgression(b,m,next))return;log(b,"pvp-initial-resources",next.coins,next.medals);
 }else applyProgression(b,m);
 tickProgression(b);
#ifdef PVP_EVOLUTION
 if(regular(b)&&ensureEvolution(b,m)){settleEvolution(b,m);applyEvolution(b,m);}
#endif
#ifdef PVP_SKILL_RESEARCH
 if(regular(b)&&ensureResearch(b,m)){settleResearch(b,m);applyResearch(b,m);}
#endif
}
// Only the three original building categories use this page. Research pages
// have separate per-zombie/per-skill configurations and remain separate.
extern "C" U offlineUpgradeClick(U b,P ui,U button){
 U kind=at<U>(ui,0xac);if(!regular(b)||kind<1||kind>3||(button!=U(-2)&&button!=U(-3)))return 0;
 offlineProgressionInit(b);P m=manager(b);EconomyRuntime&r=economyRuntime;if(r.blocked||!r.state.initialized)return 1;
 tickProgression(b);Economy next=r.state;
 if(button==U(-3)){
  if(next.upgradeKind!=kind)return 1;
  // The original cancel confirmation is reached before this callback.
  next.upgradeKind=0;next.upgradeDue=0;
 }else{
  if(next.upgradeKind==kind){
   U seconds=next.upgradeDue-realNow(b);call<void>(b,0x10747d0,ui,(seconds+59)/60);return 1;
  }
  if(next.upgradeKind
#ifdef PVP_EVOLUTION
    ||next.evolutionIndex
#endif
#ifdef PVP_SKILL_RESEARCH
    ||next.researchIndex
#endif
  ){economyNotice(b,"[V54_UPGRADE_BUSY]");return 1;}
  if(levelOf(next,kind)>=20)return 1;
  if(kind!=1&&levelOf(next,kind)>=next.baseLevel){economyNotice(b,"[V54_BASE_LEVEL_REQUIRED]");return 1;}
  U cost=upgradeCost(next,kind);if(next.coins<cost){economyNotice(b,"[PVP_ERROR_PVPCOIN_NOT_ENOUCH]");return 1;}
  next.coins-=cost;next.upgradeKind=kind;next.upgradeDue=realNow(b)+upgradeSeconds(next,kind);
 }
 if(commitProgression(b,m,next))log(b,"building-upgrade-updated",kind,next.upgradeDue);return 1;
}
static U finishProgressionWithGems(U b,P timer){
 P m=manager(b);if(!ensureEconomy(b,m))return 1;tickProgression(b);Economy next=economyRuntime.state;
 if(!next.initialized||!next.upgradeKind)return 1;
 // Keep the native displayed quote for this confirmation. Completing sooner
 // must never replace it with an obsolete cash product's price.
 U price=call<U>(b,0x1086e0c,timer,at<U>(timer,0x1f4));if(!price||price>15)return 1;
 if(call<I>(b,0x747d00,profile(b),price)<0){economyNotice(b,"[V41_GEMS_REQUIRED]");return 1;}
 U kind=next.upgradeKind;finishUpgrade(next);
 if(!commitProgression(b,m,next)){call<void>(b,0x745220,profile(b),price,1);return 1;}
 log(b,"building-finished-with-gems",kind,price);return 1;
}
extern "C" void offlineUpgradeDisplay(U b,P ui){
 U kind=at<U>(ui,0xac);EconomyRuntime&r=economyRuntime;
 if(!regular(b)||kind<1||kind>3||!r.loaded||r.user!=owner(b)||!r.state.initialized||r.state.upgradeKind!=kind)return;
 P button=at<P>(ui,0xb0),timer=at<P>(ui,0xb4);if(!button||!timer)return;
 U now=realNow(b),seconds=r.state.upgradeDue>now?r.state.upgradeDue-now:0,minutes=(seconds+59)/60;if(!minutes)return;
 U price=call<U>(b,0x1086e0c,timer,minutes);at<U>(timer,0x1f4)=minutes;
 call<void>(0,at<U>(at<P>(timer,0),0x8c),timer,0);
 call<void>(0,at<U>(at<P>(button,0),0x8c),button,1);
 call<void>(0,at<U>(at<P>(button,0),0xa4),button,0);
 call<void>(b,0x7e96a4,button);
 U text[32]{},n=0;if(price>=10)text[n++]=U('0'+price/10);text[n++]=U('0'+price%10);
 text[n++]=0x94bb;text[n++]=0x77f3;text[n++]=0x7acb;text[n++]=0x5373;text[n++]=0x5b8c;text[n++]=0x6210;
 P wide=nullptr;char allocator=0;call<void>(b,0x14eb451,&wide,text,&allocator);
 call<void>(b,0x14eae75,button+0xa4,&wide);release(b,wide,true);
}
