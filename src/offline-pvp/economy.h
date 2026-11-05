// The offline wallet/queue is app-owned state, included by the save snapshot.
#include "training_presets.h"
struct LocalTrain {U held,queued,due;};
struct Economy {U magic,version,user,coins,home,sequence,checksum,reserved;LocalTrain trains[TRAIN_COUNT];
 U initialized,medals,baseLevel,sunLevel,campLevel,upgradeKind,upgradeDue,producedAt,coinFraction,medalFraction,daveWins;
#ifdef PVP_BATTLE_ECONOMY
 U battleSerial,battleOpen,battleSettled,battleNpc,battleStage,battleFee;
#endif
#ifdef PVP_EVOLUTION
 U evolutionInitialized,evolutionLevels[TRAIN_COUNT],evolutionIndex,evolutionDue;
#endif
#ifdef PVP_SKILL_RESEARCH
 U researchInitialized,researchLevels[4],researchIndex,researchDue;
#endif
#ifdef PVP_DAVE_NARRATIVE
 U daveDialogueSerial,daveDialogueSeen,daveDialogueOutcome;
#endif
#ifdef PVP_EXCHANGE
 U shopItem,shopQuantity,shopPrice,shopDay,shopRefresh;
#endif
#ifdef PVP_EXCHANGE_REFRESH
 U stockInitialized,stockDay,stockRefresh,stockIds[6];
#endif
#ifdef PVP_EXCHANGE_CLOCK
 U stockClockInitialized,stockClockDay;I stockTestOffset;
#endif
};
static constexpr U LEGACY_ECONOMY_SIZE=32+12*TRAIN_COUNT;
static constexpr U V2_ECONOMY_SIZE=LEGACY_ECONOMY_SIZE+44;
static constexpr U V3_ECONOMY_SIZE=V2_ECONOMY_SIZE+24;
static constexpr U V4_ECONOMY_SIZE=V3_ECONOMY_SIZE+12+4*TRAIN_COUNT;
static constexpr U V5_ECONOMY_SIZE=V4_ECONOMY_SIZE+28;
static constexpr U V6_ECONOMY_SIZE=V5_ECONOMY_SIZE+12;
static constexpr U V7_ECONOMY_SIZE=V6_ECONOMY_SIZE+20;
static constexpr U V8_ECONOMY_SIZE=V7_ECONOMY_SIZE+36;
#ifdef PVP_DAVE_ROUNDS
static constexpr U DAVE_WINS_LIMIT=6;
#else
static constexpr U DAVE_WINS_LIMIT=1;
#endif
struct EconomyRuntime {U user,lastTick;bool loaded,blocked,busy,loadedFromDisk;P camp;Economy state;};
static EconomyRuntime economyRuntime;
static bool same(const char*a,const char*b){while(*a&&*a==*b){++a;++b;}return *a==*b;}
static U checkEconomy(const Economy&s){const unsigned char*p=reinterpret_cast<const unsigned char*>(&s);U h=2166136261u;for(U i=0;i<(s.version==1?LEGACY_ECONOMY_SIZE:s.version==2?V2_ECONOMY_SIZE:s.version==3?V3_ECONOMY_SIZE:s.version==4?V4_ECONOMY_SIZE:s.version==5?V5_ECONOMY_SIZE:s.version==6?V6_ECONOMY_SIZE:s.version==7?V7_ECONOMY_SIZE:s.version==8?V8_ECONOMY_SIZE:sizeof(s));++i)if(i<24||i>=28)h=(h^p[i])*16777619u;return h;}
static bool validEconomy(const Economy&s,U user){
 bool version=s.version==1||s.version==2;
#ifdef PVP_BATTLE_ECONOMY
 version=version||s.version==3;
 if(s.version>=3){
  if(s.battleSettled>s.battleSerial)return false;
  if(s.battleOpen){const NpcPreset*n=npc(s.battleNpc);if(s.battleOpen!=s.battleSerial||s.battleOpen<=s.battleSettled||!n||n->evil||s.battleStage<1||s.battleStage>2||s.battleFee!=1)return false;}
  else if(s.battleNpc||s.battleStage||s.battleFee||s.battleSettled!=s.battleSerial)return false;
 }
#endif
#ifdef PVP_EVOLUTION
 version=version||s.version==4;
 if(s.evolutionInitialized){
  if(s.evolutionInitialized!=1||s.evolutionIndex>TRAIN_COUNT||bool(s.evolutionIndex)!=bool(s.evolutionDue)||s.evolutionIndex&&s.upgradeKind)return false;
  for(U i=0;i<TRAIN_COUNT;++i)if(s.evolutionLevels[i]<1||s.evolutionLevels[i]>4)return false;
  if(s.evolutionIndex&&s.evolutionLevels[s.evolutionIndex-1]>=4)return false;
 }else if(s.evolutionIndex||s.evolutionDue)return false;
#endif
#ifdef PVP_SKILL_RESEARCH
 version=version||s.version==5;
 if(s.researchInitialized){
  if(s.researchInitialized!=1||s.researchIndex>4||bool(s.researchIndex)!=bool(s.researchDue)||s.researchIndex&&(s.upgradeKind||s.evolutionIndex))return false;
  for(U i=0;i<4;++i)if(s.researchLevels[i]<1||s.researchLevels[i]>4)return false;
  if(s.researchIndex&&s.researchLevels[s.researchIndex-1]>=4)return false;
 }else if(s.researchIndex||s.researchDue)return false;
#endif
#ifdef PVP_DAVE_NARRATIVE
 version=version||s.version==6;
 if(s.daveDialogueSeen>s.daveDialogueSerial||s.daveDialogueOutcome>6||s.daveDialogueOutcome>s.daveWins||!s.daveDialogueSerial&&(s.daveDialogueSeen||s.daveDialogueOutcome))return false;
#endif
#ifdef PVP_EXCHANGE
 version=version||s.version==7;
 if(s.shopItem){const ExchangeSpec*spec=exchangeSpec(s.shopItem);if(!spec||s.shopQuantity!=spec->quantity||s.shopPrice!=spec->price)return false;}
 else if(s.shopQuantity||s.shopPrice)return false;
#endif
#ifdef PVP_EXCHANGE_REFRESH
 version=version||s.version==8;
 if(s.stockInitialized){
  if(s.stockInitialized!=1||s.stockRefresh>1000000)return false;
  for(U i=0;i<6;++i){if(!exchangeSpec(s.stockIds[i]))return false;for(U k=0;k<i;++k)if(s.stockIds[k]==s.stockIds[i])return false;}
 }
#endif
#ifdef PVP_EXCHANGE_CLOCK
 version=version||s.version==9;
 if(s.stockClockInitialized>1||s.stockClockInitialized&&!s.stockInitialized||s.stockTestOffset< -86400||s.stockTestOffset>86400)return false;
#endif
 if(s.magic!=0x45435650||!version||s.user!=user||s.coins>2000000000u||!s.home||s.home>20||s.checksum!=checkEconomy(s))return false;
 if(s.initialized&&(s.initialized!=1||s.medals>2000000000u||!s.baseLevel||s.baseLevel>20||!s.sunLevel||s.sunLevel>20||!s.campLevel||s.campLevel>20||s.upgradeKind>3||bool(s.upgradeKind)!=bool(s.upgradeDue)||s.coinFraction>=3600||s.medalFraction>=3600||s.daveWins>DAVE_WINS_LIMIT))return false;
 U used=0;
 for(U i=0;i<TRAIN_COUNT;++i){const LocalTrain&t=s.trains[i];if(t.held>100||t.queued>100||(t.queued&&!t.due)||(!t.queued&&t.due))return false;used+=(t.held+t.queued)*TRAIN_SPECS[i].space;}
 return used<=(s.initialized?campCapacity(s.campLevel):40);
}
static void economyPath(U id,char*out,bool tmp){
 const char*prefix="/data/data/com.popcap.pvz2cthd.reconstruction/files/userdata/offline-pvp-";U n=0;
 while(prefix[n]){out[n]=prefix[n];++n;}const char*digits="0123456789abcdef";
 for(I i=7;i>=0;--i)out[n++]=digits[(id>>(i*4))&15];const char*s=tmp?".eco.tmp":".eco";while(*s)out[n++]=*s++;out[n]=0;
}
static bool saveEconomy(U b,Economy&s){
 s.version=2;
#ifdef PVP_BATTLE_ECONOMY
 s.version=3;
#endif
#ifdef PVP_EVOLUTION
 s.version=4;
#endif
#ifdef PVP_SKILL_RESEARCH
 s.version=5;
#endif
#ifdef PVP_DAVE_NARRATIVE
 s.version=6;
#endif
#ifdef PVP_EXCHANGE
 s.version=7;
#endif
#ifdef PVP_EXCHANGE_REFRESH
 s.version=8;
#endif
#ifdef PVP_EXCHANGE_CLOCK
 s.version=9;
#endif
 s.checksum=checkEconomy(s);if(!validEconomy(s,s.user))return false;
 char dst[160],tmp[160];economyPath(s.user,dst,false);economyPath(s.user,tmp,true);
 I fd=call<I>(b,0x148448,tmp,0x241,0600);if(fd<0)return false;U done=0;
 while(done<sizeof(s)){I n=call<I>(b,0x1485d4,fd,reinterpret_cast<P>(&s)+done,sizeof(s)-done);if(n<=0)break;done+=U(n);}
 bool ok=done==sizeof(s)&&call<I>(b,0x1485e0,fd)==0;if(call<I>(b,0x147b90,fd))ok=false;
 if(ok)ok=call<I>(b,0x147e6c,tmp,dst)==0;if(!ok)call<I>(b,0x148424,tmp);return ok;
}
static I loadEconomy(U b,Economy&s){
 char path[160];economyPath(owner(b),path,false);I fd=call<I>(b,0x148448,path,0,0);if(fd<0)return 0;U done=0;
 while(done<sizeof(s)){I n=call<I>(b,0x148460,fd,reinterpret_cast<P>(&s)+done,sizeof(s)-done);if(n<=0)break;done+=U(n);}
 char tail;I extra=call<I>(b,0x148460,fd,&tail,1);call<I>(b,0x147b90,fd);
 bool length=(s.version==1&&done==LEGACY_ECONOMY_SIZE)||(s.version==2&&done==V2_ECONOMY_SIZE);
#ifdef PVP_BATTLE_ECONOMY
 length=length||(s.version==3&&done==V3_ECONOMY_SIZE);
#endif
#ifdef PVP_EVOLUTION
 length=length||(s.version==4&&done==V4_ECONOMY_SIZE);
#endif
#ifdef PVP_SKILL_RESEARCH
 length=length||(s.version==5&&done==V5_ECONOMY_SIZE);
#endif
#ifdef PVP_DAVE_NARRATIVE
 length=length||(s.version==6&&done==V6_ECONOMY_SIZE);
#endif
#ifdef PVP_EXCHANGE
 length=length||(s.version==7&&done==V7_ECONOMY_SIZE);
#endif
#ifdef PVP_EXCHANGE_REFRESH
 length=length||(s.version==8&&done==V8_ECONOMY_SIZE);
#endif
#ifdef PVP_EXCHANGE_CLOCK
 length=length||(s.version==9&&done==sizeof(s));
#endif
 return length&&extra==0&&validEconomy(s,owner(b))?1:-1;
}
static void economyNotice(U b,const char*message){
 P title=nullptr,body=nullptr;narrow(b,reinterpret_cast<P>(&title),"[V38_NOTICE_TITLE]");narrow(b,reinterpret_cast<P>(&body),message);
 P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0);call<void>(b,0x4045fc,app,&title,&body);release(b,title);release(b,body);
}
static U realNow(U b){return call<U>(b,0x147824,0);}
static void notifyTraining(U b,P m){U response[5]={0,0,0,0,at<U>(m,4)};call<void>(b,0x104a544,m,response);}
static void applyEconomy(U b,P m){
 EconomyRuntime&r=economyRuntime;P a=at<P>(m,0x20);
 if(!a){a=call<P>(b,0x14c1a7d,0x1c);call<void>(b,0x104b5d8,a);at<P>(m,0x20)=a;}
 call<void>(b,0x104b628,a);at<U>(a,4)=r.state.initialized?campCapacity(r.state.campLevel):40;at<U>(a,8)=6;U now=realNow(b);P clock=call<P>(b,0x1f7380);float gameTime=at<float>(clock,0x24);
 for(U i=0;i<TRAIN_COUNT;++i){const LocalTrain&t=r.state.trains[i];if(!t.held&&!t.queued)continue;
  alignas(8) U entry[8]={0,t.held,t.queued,0xbf800000,0x7f7fffff,0,0,0};narrow(b,reinterpret_cast<P>(entry),TRAIN_SPECS[i].name);
  if(t.queued){at<float>(reinterpret_cast<P>(entry),12)=float(TRAIN_SPECS[i].seconds);at<float>(reinterpret_cast<P>(entry),16)=gameTime+float(t.due>now?t.due-now:0);}
  call<void>(b,0x104d6e4,a,entry);release(b,reinterpret_cast<P>(entry[0]));
 }
 r.camp=a;call<void>(b,0x1042a5c,m,r.state.coins);
 // g is the native garden level, distinct from ag (star coins) at manager+4.
 if(at<U>(m,0x10)<1)at<U>(m,0x10)=r.state.home;
 if(r.state.initialized)applyProgression(b,m);
#ifdef PVP_EVOLUTION
 if(r.state.evolutionInitialized)applyEvolution(b,m);
#endif
#ifdef PVP_SKILL_RESEARCH
 if(r.state.researchInitialized)applyResearch(b,m);
#endif
}
static bool ensureEconomy(U b,P m,bool entering=false){
 if(!regular(b)&&!entering)return false;EconomyRuntime&r=economyRuntime;U user=owner(b);
 if(!r.loaded||r.user!=user){r.loaded=true;r.user=user;r.lastTick=0;r.camp=nullptr;r.blocked=false;r.state=Economy{};
  I found=loadEconomy(b,r.state);
  r.loadedFromDisk=found==1;
  if(found<0){r.blocked=true;log(b,"economy-invalid");return false;}
  if(!found){r.state.magic=0x45435650;r.state.version=2;r.state.user=user;r.state.coins=at<U>(m,4);r.state.home=at<U>(m,0x10);if(!r.state.home||r.state.home>20)r.state.home=1;}
#ifdef PVP_BATTLE_ECONOMY
  // A process restart cannot resume an old Board or replay its result. Refund
  // a load that never created its bank; a battle that started keeps its fee.
  if(found==1&&r.state.battleOpen){Economy next=r.state;
   if(next.battleStage==1&&next.coins<=2000000000u-next.battleFee)next.coins+=next.battleFee;
   next.battleSettled=next.battleOpen;next.battleOpen=next.battleNpc=next.battleStage=next.battleFee=0;++next.sequence;
   if(!saveEconomy(b,next)){r.blocked=true;log(b,"battle-recovery-save-failed");return false;}
   r.state=next;log(b,"battle-recovered",next.battleSettled,next.coins);
  }
#endif
  log(b,"economy-loaded",r.state.coins,found==1);
 }
 if(r.blocked)return false;
 // During the original first-entry tutorial, preserve its temporary army.
 if(!regular(b)){call<void>(b,0x1042a5c,m,r.state.coins);return true;}
 if(r.camp!=at<P>(m,0x20)||!r.camp)applyEconomy(b,m);
 else if(at<U>(m,4)!=r.state.coins)call<void>(b,0x1042a5c,m,r.state.coins);
 return true;
}
static void settleTraining(U b,P m){
 EconomyRuntime&r=economyRuntime;U now=realNow(b);if(now==r.lastTick||r.busy)return;r.lastTick=now;
 Economy next=r.state;bool changed=false;
 for(U i=0;i<TRAIN_COUNT;++i){LocalTrain&t=next.trains[i];while(t.queued&&now>=t.due){--t.queued;++t.held;changed=true;if(t.queued)t.due+=TRAIN_SPECS[i].seconds;else t.due=0;}}
 if(changed){++next.sequence;if(saveEconomy(b,next)){r.state=next;applyEconomy(b,m);notifyTraining(b,m);log(b,"training-completed");}else log(b,"training-save-failed");}
}
extern "C" void offlineEconomyInit(U b){P m=manager(b);if(ensureEconomy(b,m))settleTraining(b,m);}
// The callback receives success after the original gem-payment validation.
// Only pvpCoin products are handled here; all other products fall through.
static U starPrice(U count){return count==5000?110:count==20000?440:count==75000?1650:0;}
static U creditStarcoinCount(U b,U count,U success){
 if(!success)return 1;U price=starPrice(count);
 P m=manager(b);if(!price){log(b,"coin-product-rejected",count);return 1;}
 EconomyRuntime&r=economyRuntime;
 if(!ensureEconomy(b,m)||r.state.coins>2000000000u-count){call<void>(b,0x745220,profile(b),price,1);economyNotice(b,"[V38_PVP_SAVE_ERROR]");return 1;}
 Economy next=r.state;next.coins+=count;++next.sequence;
 if(saveEconomy(b,next)){r.state=next;call<void>(b,0x1042a5c,m,next.coins);if(next.initialized)applyProgression(b,m);log(b,"starcoins-purchased",count,price);}
 else{call<void>(b,0x745220,profile(b),price,1);economyNotice(b,"[V38_PVP_SAVE_ERROR]");log(b,"starcoin-write-refund",price);}
 return 1;
}
static U creditStarcoins(U b,P weak,U success){
 P product=call<P>(b,0x1da034,call<P>(b,0x11d74b4),weak);
 if(!product||!same(reinterpret_cast<const char*>(at<P>(product,0x44)),"pvpCoin"))return 0;
 return creditStarcoinCount(b,at<U>(product,0x50),success);
}
static U buyStarcoins(U b,U count){
 U price=starPrice(count);P m=manager(b);
 if(!price||!ensureEconomy(b,m)||economyRuntime.state.coins>2000000000u-count){economyNotice(b,"[V38_PVP_SAVE_ERROR]");return 1;}
 if(call<I>(b,0x747d00,profile(b),price)<0){economyNotice(b,"[V41_GEMS_REQUIRED]");log(b,"starcoin-insufficient-gems",count,price);return 1;}
 return creditStarcoinCount(b,count,1);
}
extern "C" U offlineCoinComplete(U b,P self,U success){return creditStarcoins(b,self+0xb8,success);}
extern "C" U offlineCoinGrant(U b,P self,P weak){return creditStarcoins(b,weak,1);}
// The dedicated PvP bank (App::ShowPVPCoinBank, 0x40b154) uses a category
// weak reference, not either generic bank's card vector. Its real button ends
// at this request with the zero-based product index; no gem debit precedes it.
extern "C" void offlineCoinRequest(U b,P m,U index){
 if(!regular(b)){call<void>(b,0xf79d74);call<void>(b,0xf8cee4,call<P>(b,0xf7a070),index);return;}
 log(b,"pvp-bank-request",index);
 if(index>=3){log(b,"pvp-bank-index-rejected",index);return;}
 const U amounts[3]={5000,20000,75000};buyStarcoins(b,amounts[index]);
}
// Currency-bank dialogs dispatch purchases by their native bank mode, even
// when Magento displays a gem price. Intercept the actual product click before
// that cash/server branch. The two existing banks use different card vectors.
extern "C" U offlineCoinClick(U b,P ui,U index,U vectorOffset){
 if(!ui||index>=64||(vectorOffset!=0xa8&&vectorOffset!=0xb8))return 0;
 P first=at<P>(ui,vectorOffset),last=at<P>(ui,vectorOffset+4);
 if(!first||last<first||U(last-first)>64*4||U(last-first)%4||index>=U(last-first)/4)return 0;
 P card=at<P>(first,index*4);if(!card)return 0;
 P product=call<P>(b,0x1da034,call<P>(b,0x11d74b4),card+0xa0);
 if(!product||!same(reinterpret_cast<const char*>(at<P>(product,0x44)),"pvpCoin"))return 0;
 // Use the original balance check, encrypted wallet update, UI notifications
 // and persistence. Only a successful debit can reach the local credit path.
 return buyStarcoins(b,at<U>(product,0x50));
}
extern "C" void offlineTraining(U b,P camp,P name,U action){
 P m=manager(b);if(!regular(b)){call<void>(b,0xf79d74);P net=call<P>(b,0xf7a070);call<void>(b,0xf8fb18,net,name,action==1?1:action==2?-1:0);return;}
 if(!ensureEconomy(b,m)){economyNotice(b,"[V38_PVP_SAVE_ERROR]");return;}settleTraining(b,m);
 U index=TRAIN_COUNT;for(U i=0;i<TRAIN_COUNT;++i)if(same(reinterpret_cast<const char*>(at<P>(name,0)),TRAIN_SPECS[i].name)){index=i;break;}
 if(index==TRAIN_COUNT){log(b,"unknown-training",action);return;}
 if(action==3){applyEconomy(b,m);return;}if(action!=1&&action!=2)return;
 EconomyRuntime&r=economyRuntime;Economy next=r.state;LocalTrain&t=next.trains[index];const TrainSpec&s=TRAIN_SPECS[index];
 if(action==1){
  if(s.level>next.home){economyNotice(b,"[V38_PVP_LOCKED]");return;}
  if(next.coins<s.cost){economyNotice(b,"[PVP_ERROR_PVPCOIN_NOT_ENOUCH]");return;}
  U used=0,slots=0;for(U i=0;i<TRAIN_COUNT;++i){used+=(next.trains[i].held+next.trains[i].queued)*TRAIN_SPECS[i].space;if(next.trains[i].queued)++slots;}
  if(used+s.space>(next.initialized?campCapacity(next.campLevel):40)||(!t.queued&&slots>=6)){economyNotice(b,"[V38_PVP_CAPACITY]");return;}
  next.coins-=s.cost;if(!t.queued)t.due=realNow(b)+s.seconds;++t.queued;
 }else{if(!t.queued)return;--t.queued;if(!t.queued)t.due=0;next.coins+=s.cost;}
 ++next.sequence;if(!saveEconomy(b,next)){economyNotice(b,"[V38_PVP_SAVE_ERROR]");return;}
 r.state=next;applyEconomy(b,m);notifyTraining(b,m);log(b,"training-updated",index,action);
}
extern "C" void offlineTrainingTick(U b,P camp){P m=manager(b);if(ensureEconomy(b,m))settleTraining(b,m);tickProgression(b);
#ifdef PVP_EVOLUTION
 settleEvolution(b,m);
#endif
#ifdef PVP_SKILL_RESEARCH
 settleResearch(b,m);
#endif
 call<void>(b,0x104c894,camp);completeLocalBattle(b);inspectArena(b);}
static bool trainingFinishPrompt;
// Read the local queues, rather than the obsolete cash-product availability.
// Different types train in parallel; each type's queue is sequential.
static U trainingMinutes(U b){
 U now=realNow(b),seconds=0;
 for(U i=0;i<TRAIN_COUNT;++i){const LocalTrain&t=economyRuntime.state.trains[i];
  if(t.queued){U n=(t.due>now?t.due-now:0)+(t.queued-1)*TRAIN_SPECS[i].seconds;if(n>seconds)seconds=n;}
 }
 return (seconds+59)/60;
}
extern "C" void offlineTrainingDisplay(U b,P ui){
 if(!regular(b)||!ensureEconomy(b,manager(b)))return;
 P button=at<P>(ui,0x108),timer=at<P>(ui,0x10c);if(!button||!timer)return;
 U minutes=trainingMinutes(b),price=call<U>(b,0x1086e0c,timer,minutes);
 // The old updater writes a cash quote here. Keep the original prompt and
 // confirmation on the same remaining-minute input as the displayed price.
 at<U>(timer,0x1f4)=minutes;
 // The regular button and cash overlay have the same native button ID (1).
 // Display the regular button so neither cash labels nor product lookups run.
 call<void>(0,at<U>(at<P>(timer,0),0x8c),timer,0);
 call<void>(0,at<U>(at<P>(button,0),0x8c),button,1);
 // Widget::SetDisabled takes true to block input (not true to enable it).
 call<void>(0,at<U>(at<P>(button,0),0xa4),button,minutes==0);
 // The original gem button also draws an icon/price decoration at a fixed
 // position. Clear it through its native destructor before using one label.
 call<void>(b,0x7e96a4,button);
 U text[32]{},n=0;if(price>=10)text[n++]=U('0'+price/10);text[n++]=U('0'+price%10);
 text[n++]=0x94bb;text[n++]=0x77f3;text[n++]=0x7acb;text[n++]=0x5373;text[n++]=0x5b8c;text[n++]=0x6210;
 P wide=nullptr;char allocator=0;call<void>(b,0x14eb451,&wide,text,&allocator);
 call<void>(b,0x14eae75,button+0xa4,&wide);release(b,wide,true);
}
extern "C" U offlineTrainingClick(U b,P ui,U button){
 if(!regular(b)||button!=1)return 0;
 P m=manager(b);if(!ensureEconomy(b,m))return 1;settleTraining(b,m);
 U minutes=trainingMinutes(b);if(!minutes||!at<P>(ui,0x10c))return 1;
 // Reuse the original prompt constructor and callback, now intercepted below.
 call<void>(b,0x1055474,ui,minutes);log(b,"training-gem-prompt",minutes);return 1;
}
extern "C" void offlineTrainingFinishPrompt(U b,P timer,P callback){
 trainingFinishPrompt=regular(b);call<void>(b,0x108737c,timer,callback);trainingFinishPrompt=false;
}
extern "C" void offlineFinishCurrencyText(U b,P out,P text,P allocator){
 U key[64]{};
 if(trainingFinishPrompt){const char*s="[PVP_TRAINING_FINISH_TIP]";
#ifdef PVP_EVOLUTION
  if(evolutionFinishPrompt)s="[V63_EVOLUTION_FINISH_TIP]";
#endif
#ifdef PVP_SKILL_RESEARCH
  if(researchFinishPrompt)s="[V65_RESEARCH_FINISH_TIP]";
#endif
  for(U i=0;s[i];++i)key[i]=U(s[i]);text=reinterpret_cast<P>(key);}
 call<void>(b,0x14eb451,out,text,allocator);
}
// Only the training timer's original callback is eligible. Upgrade/research
// dialogs use the same checkout widget but retain their own native path.
extern "C" U offlineTrainingFinish(U b,P timer){
 if(!regular(b))return 0;
#ifdef PVP_SKILL_RESEARCH
 if(at<U>(timer,0x1fc)==b+0x108531c)return finishResearchWithGems(b,timer);
#endif
#ifdef PVP_EVOLUTION
 if(at<U>(timer,0x1fc)==b+0x1080e28)return finishEvolutionWithGems(b,timer);
#endif
 if(at<U>(timer,0x1fc)==b+0x10748e8)return finishProgressionWithGems(b,timer);
 if(at<U>(timer,0x1fc)!=b+0x1055588)return 0;
 P m=manager(b);if(!ensureEconomy(b,m))return 1;settleTraining(b,m);
 Economy next=economyRuntime.state;U total=0;for(U i=0;i<TRAIN_COUNT;++i)total+=next.trains[i].queued;
 if(!total)return 1;
 U price=call<U>(b,0x1086e0c,timer,at<U>(timer,0x1f4));if(!price||price>15)return 1;
 if(call<I>(b,0x747d00,profile(b),price)<0){economyNotice(b,"[V41_GEMS_REQUIRED]");return 1;}
 for(U i=0;i<TRAIN_COUNT;++i){LocalTrain&t=next.trains[i];t.held+=t.queued;t.queued=0;t.due=0;}
 ++next.sequence;
 if(!saveEconomy(b,next)){call<void>(b,0x745220,profile(b),price,1);economyNotice(b,"[V38_PVP_SAVE_ERROR]");return 1;}
 economyRuntime.state=next;applyEconomy(b,m);notifyTraining(b,m);log(b,"training-finished-with-gems",price,total);return 1;
}
extern "C" U offlineTrainingFinishConfirm(U b,P timer,U unused,U button){
 bool known=at<U>(timer,0x1fc)==b+0x1055588||at<U>(timer,0x1fc)==b+0x10748e8;
#ifdef PVP_SKILL_RESEARCH
 known=known||at<U>(timer,0x1fc)==b+0x108531c;
#endif
#ifdef PVP_EVOLUTION
 known=known||at<U>(timer,0x1fc)==b+0x1080e28;
#endif
 if(!regular(b)||!known)return 0;
 // Use the confirm callback's actual receiver. Later checkout code reuses
 // its r6 register for the product object, so it no longer identifies timer.
 P cell=reinterpret_cast<P>(b)+0x1836300;P dialog=at<P>(cell,0);
 if(dialog){call<void>(0,at<U>(at<P>(dialog,0),0x17c),dialog);at<P>(cell,0)=nullptr;}
 if(button==1)offlineTrainingFinish(b,timer);return 1;
}
