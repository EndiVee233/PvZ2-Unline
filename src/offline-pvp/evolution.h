// The original engine still applies per-level attack/health/skills. Persist
// its per-alias grade and shared lab queue locally, alongside the wallet.
#include "evolution_presets.h"
static U evolutionTimer[0x218/4],evolutionPromptUser,evolutionPromptIndex,evolutionPromptDue;
struct EvolutionView {P ui;U index,level,mode,second;};
static EvolutionView evolutionView;
static U evolutionIndex(P name){
 if(!name||!at<P>(name,0))return TRAIN_COUNT;
 for(U i=0;i<TRAIN_COUNT;++i)if(same(reinterpret_cast<const char*>(at<P>(name,0)),TRAIN_SPECS[i].name))return i;
 return TRAIN_COUNT;
}
static bool ensureEvolution(U b,P m){
 if(!regular(b)||!ensureEconomy(b,m))return false;
 if(economyRuntime.state.evolutionInitialized)return true;
 Economy next=economyRuntime.state;next.evolutionInitialized=1;
 for(U i=0;i<TRAIN_COUNT;++i){
  P key=nullptr;narrow(b,reinterpret_cast<P>(&key),TRAIN_SPECS[i].name);P record=call<P>(b,0x104673c,m,&key);release(b,key);
  U level=record?at<U>(record,4):1;
  // Import legitimate existing grades only. A missing or invalid server grade
  // is not evidence that the zombie has completed every evolution.
  next.evolutionLevels[i]=level>=1&&level<=4?level:1;
 }
 ++next.sequence;if(!saveEconomy(b,next)){economyNotice(b,"[V38_PVP_SAVE_ERROR]");return false;}
 economyRuntime.state=next;applyEvolution(b,m);log(b,"evolution-initialized");return true;
}
static void applyEvolution(U b,P m){
 const Economy&s=economyRuntime.state;if(!s.evolutionInitialized||!regular(b))return;
 for(U i=0;i<TRAIN_COUNT;++i){
  P key=nullptr;narrow(b,reinterpret_cast<P>(&key),TRAIN_SPECS[i].name);P info=call<P>(b,0x104673c,m,&key);
  if(info||TRAIN_SPECS[i].level<=s.home){
   U entry[5]={reinterpret_cast<U>(key),s.evolutionLevels[i],1,info?at<U>(info,12):0,1};
   // Assignment uses the real native tree key and structure rather than
   // overwriting a pointer that another module may have cached.
   call<P>(b,0x1048f44,m,entry);
  }
  release(b,key);
 }
 if(s.evolutionIndex){
  P key=nullptr;narrow(b,reinterpret_cast<P>(&key),TRAIN_SPECS[s.evolutionIndex-1].name);
  U type[2]{};call<void>(b,0xfb6ef0,type,&key);release(b,key);
  at<U>(m,0x6c)=4;at<U>(m,0x70)=type[1];
  U now=realNow(b);at<float>(m,0x74)=at<float>(call<P>(b,0x1f7380),0x24)+float(s.evolutionDue>now?s.evolutionDue-now:0);
 }
}
static void settleEvolution(U b,P m){
 if(!regular(b)||!economyRuntime.loaded||economyRuntime.user!=owner(b)||economyRuntime.blocked)return;
 const Economy&s=economyRuntime.state;if(!s.evolutionInitialized||!s.evolutionIndex||realNow(b)<s.evolutionDue)return;
 Economy next=s;U index=next.evolutionIndex-1;++next.evolutionLevels[index];next.evolutionIndex=next.evolutionDue=0;
 if(commitProgression(b,m,next))log(b,"evolution-completed",index,next.evolutionLevels[index]);
}
static U evolutionMinutes(U b){const Economy&s=economyRuntime.state;U now=realNow(b);return s.evolutionIndex&&s.evolutionDue>now?(s.evolutionDue-now+59)/60:0;}
static U evolutionPrice(U b,U minutes){return call<U>(b,0x1086e0c,reinterpret_cast<P>(evolutionTimer),minutes);}
static U decimal(U*out,U n,U value){U reverse[10],count=0;do{reverse[count++]=U('0')+value%10;value/=10;}while(value);while(count)out[n++]=reverse[--count];return n;}
static void evolutionLabel(U b,P button,U minutes,U price){
 U text[64]{},n=decimal(text,0,price);
 const U tail[]={0x94bb,0x77f3,0x5b8c,0x6210,0x28,0};
 for(U i=0;tail[i];++i)text[n++]=tail[i];n=decimal(text,n,minutes);text[n++]=0x5206;text[n++]=0x29;
 P wide=nullptr;char allocator=0;call<void>(b,0x14eb451,&wide,text,&allocator);call<void>(b,0x14eae75,button+0xa4,&wide);release(b,wide,true);
}
// The cash overlay is intentionally not constructed for this local queue.
// Keep the regular native button and original layout/next-level descriptions.
extern "C" void offlineEvolutionBuild(U b,P ui){
 if(!regular(b)||evolutionIndex(ui+0xa8)==TRAIN_COUNT)return;
 if(ensureEvolution(b,manager(b)))settleEvolution(b,manager(b));
 at<unsigned char>(ui,0xbc)=0;evolutionView.ui=nullptr;
}
extern "C" void offlineEvolutionTick(U b,P ui){
 if(!regular(b))return;U index=evolutionIndex(ui+0xa8);if(index==TRAIN_COUNT||!ensureEvolution(b,manager(b)))return;
 settleEvolution(b,manager(b));const Economy&s=economyRuntime.state;
 U mode=s.evolutionIndex==index+1?1:s.evolutionIndex||s.upgradeKind?2:0,level=s.evolutionLevels[index];
 bool rebuild=evolutionView.ui==ui&&evolutionView.index==index&&evolutionView.level!=level;
 evolutionView.index=index;evolutionView.level=level;evolutionView.mode=mode;
 if(rebuild){evolutionView.ui=nullptr;call<void>(b,0x107eb28,ui);}
 P button=at<P>(ui,0xc0);if(!button)return;
 if(level>=4){call<void>(0,at<U>(at<P>(button,0),0xa4),button,1);call<void>(0,at<U>(at<P>(button,0),0x8c),button,0);return;}
 // A regular button is available for 1->2, 2->3 and 3->4. Its original
 // construction preserves the star-coin icon/price whenever no queue runs.
 U now=realNow(b);bool refresh=evolutionView.ui!=ui||evolutionView.second!=now;
 evolutionView.ui=ui;evolutionView.second=now;
 call<void>(0,at<U>(at<P>(button,0),0xa4),button,mode==2||(mode==0&&s.coins<EVOLUTION_SPECS[index].cost[level-1]));
 if(mode==1&&refresh){call<void>(b,0x7e96a4,button);U minutes=evolutionMinutes(b);evolutionLabel(b,button,minutes,evolutionPrice(b,minutes));}
}
extern "C" U offlineEvolutionClick(U b,P ui,U button){
 if(!regular(b)||(button!=0x1e8d&&button!=0x1938))return 0;
 U index=evolutionIndex(ui+0xa8);if(index==TRAIN_COUNT)return 0;
 P m=manager(b);if(!ensureEvolution(b,m))return 1;settleEvolution(b,m);Economy next=economyRuntime.state;
 if(next.evolutionIndex==index+1){
  U minutes=evolutionMinutes(b);if(!minutes)return 1;
  evolutionPromptUser=owner(b);evolutionPromptIndex=next.evolutionIndex;evolutionPromptDue=next.evolutionDue;
  P timer=reinterpret_cast<P>(evolutionTimer);at<U>(timer,0x1f4)=minutes;
  U callback[6]={0,b+0x1080e28,0,0,1,0};evolutionFinishPrompt=true;offlineTrainingFinishPrompt(b,timer,reinterpret_cast<P>(callback));evolutionFinishPrompt=false;
  log(b,"evolution-gem-prompt",index,evolutionPrice(b,minutes));return 1;
 }
 if(next.evolutionIndex||next.upgradeKind){economyNotice(b,"[V54_UPGRADE_BUSY]");return 1;}
 if(TRAIN_SPECS[index].level>next.home){economyNotice(b,"[V38_PVP_LOCKED]");return 1;}
 U level=next.evolutionLevels[index];if(level>=4)return 1;
 U cost=EVOLUTION_SPECS[index].cost[level-1];if(next.coins<cost){economyNotice(b,"[PVP_ERROR_PVPCOIN_NOT_ENOUCH]");return 1;}
 next.coins-=cost;next.evolutionIndex=index+1;next.evolutionDue=realNow(b)+EVOLUTION_SPECS[index].seconds[level-1];
 if(commitProgression(b,m,next)){log(b,"evolution-started",index,cost);call<void>(b,0x107eb28,ui);}
 return 1;
}
static U finishEvolutionWithGems(U b,P timer){
 P m=manager(b);if(!ensureEvolution(b,m))return 1;settleEvolution(b,m);Economy next=economyRuntime.state;
 if(evolutionPromptUser!=owner(b)||!next.evolutionIndex||next.evolutionIndex!=evolutionPromptIndex||next.evolutionDue!=evolutionPromptDue)return 1;
 U price=evolutionPrice(b,at<U>(timer,0x1f4));if(!price||price>15)return 1;
 if(call<I>(b,0x747d00,profile(b),price)<0){economyNotice(b,"[V41_GEMS_REQUIRED]");return 1;}
 U index=next.evolutionIndex-1;++next.evolutionLevels[index];next.evolutionIndex=next.evolutionDue=0;
 if(!commitProgression(b,m,next)){call<void>(b,0x745220,profile(b),price,1);return 1;}
 evolutionPromptUser=0;log(b,"evolution-finished-with-gems",index,price);return 1;
}
