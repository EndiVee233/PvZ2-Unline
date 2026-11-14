// Persist real SkillInfo grades, leaving effect properties with the engine.
#include "research_presets.h"
#include "research_cards.h"
static U researchTimer[0x218/4],researchPromptUser,researchPromptIndex,researchPromptDue;
struct ResearchView {P ui,button;U index,level,mode,second;};
static ResearchView researchView;
static U researchIndex(P name){
 if(!name||!at<P>(name,0))return 4;
 for(U i=0;i<4;++i)if(same(reinterpret_cast<const char*>(at<P>(name,0)),RESEARCH_SPECS[i].name))return i;
 return 4;
}
static bool ensureResearch(U b,P m){
 if(!regular(b)||!ensureEconomy(b,m))return false;
 if(economyRuntime.state.researchInitialized)return true;
 Economy next=economyRuntime.state;next.researchInitialized=1;
 for(U i=0;i<4;++i){
  P key=nullptr;narrow(b,reinterpret_cast<P>(&key),RESEARCH_SPECS[i].name);P info=call<P>(b,0x1046764,m,&key);release(b,key);
  U level=info?at<U>(info,4):1;next.researchLevels[i]=level>=1&&level<=4?level:1;
 }
 ++next.sequence;if(!saveEconomy(b,next)){economyNotice(b,"[V38_PVP_SAVE_ERROR]");return false;}
 economyRuntime.state=next;applyResearch(b,m);log(b,"research-initialized");return true;
}
static void applyResearch(U b,P m){
 const Economy&s=economyRuntime.state;if(!s.researchInitialized||!regular(b))return;
#ifdef PVP_WEEKLY_RULES
 skillAidGrade=s.researchLevels[0];skillFogGrade=s.researchLevels[1];
#endif
 for(U i=0;i<4;++i){
  P key=nullptr;narrow(b,reinterpret_cast<P>(&key),RESEARCH_SPECS[i].name);P info=call<P>(b,0x1046764,m,&key);
  U entry[5]={reinterpret_cast<U>(key),s.researchLevels[i],1,info?at<U>(info,12):0,1};call<P>(b,0x1048dcc,m,entry);release(b,key);
 }
 if(s.researchIndex){
  P key=nullptr;narrow(b,reinterpret_cast<P>(&key),RESEARCH_SPECS[s.researchIndex-1].name);U type[2]{};call<void>(b,0xfb6ef0,type,&key);release(b,key);
  U now=realNow(b);at<U>(m,0x6c)=7;at<U>(m,0x70)=type[1];at<float>(m,0x74)=at<float>(call<P>(b,0x1f7380),0x24)+float(s.researchDue>now?s.researchDue-now:0);
 }
}
static void settleResearch(U b,P m){
 if(!regular(b)||!economyRuntime.loaded||economyRuntime.blocked||economyRuntime.user!=owner(b))return;
 const Economy&s=economyRuntime.state;if(!s.researchInitialized||!s.researchIndex||realNow(b)<s.researchDue)return;
 Economy next=s;U index=next.researchIndex-1;++next.researchLevels[index];next.researchIndex=next.researchDue=0;
 if(commitProgression(b,m,next))log(b,"research-completed",index,next.researchLevels[index]);
}
static U researchMinutes(U b){const Economy&s=economyRuntime.state;U now=realNow(b);return s.researchIndex&&s.researchDue>now?(s.researchDue-now+59)/60:0;}
extern "C" U offlineResearchRemaining(U b,P ui){
 return regular(b)&&researchIndex(at<P>(ui,0xc4))<4?0:call<U>(b,0x1083754,ui);
}
extern "C" void offlineResearchTick(U b,P ui){
 if(!regular(b)||!ensureResearch(b,manager(b)))return;settleResearch(b,manager(b));P info=at<P>(ui,0xc4);U index=researchIndex(info);if(index>=4)return;
 const Economy&s=economyRuntime.state;U level=s.researchLevels[index];
 U mode=s.researchIndex==index+1?1:s.researchIndex||s.evolutionIndex||s.upgradeKind?2:0;
 bool rebuild=researchView.ui==ui&&researchView.index==index&&(researchView.level!=level||researchView.mode!=mode);
 bool selectedCardChanged=syncResearchCardGrades(b,ui,manager(b));
 bool levelChanged=(rebuild&&researchView.level!=level)||selectedCardChanged;
 if(levelChanged)call<void>(b,0x1084a38,ui,at<U>(ui,0xc0));
 else if(rebuild)call<void>(b,0x10849c0,ui);
 P button=at<P>(ui,0xac);U now=realNow(b);
 bool refresh=researchView.ui!=ui||researchView.index!=index||researchView.second!=now||researchView.button!=button||rebuild;
 researchView={ui,button,index,level,mode,now};if(!button||level>=4)return;
 bool disabled=mode==2||(mode==0&&(s.coins<RESEARCH_SPECS[index].cost[level-1]||s.baseLevel<RESEARCH_SPECS[index].base[level-1]));
 call<void>(0,at<U>(at<P>(button,0),0xa4),button,U(disabled));
 if(mode==1&&refresh){call<void>(b,0x7e96a4,button);U minutes=researchMinutes(b);evolutionLabel(b,button,minutes,evolutionPrice(b,minutes));}
}
extern "C" U offlineResearchClick(U b,P ui,U button){
 if(!regular(b)||(button!=U(-2)&&button!=U(-3)))return 0;
 U index=researchIndex(at<P>(ui,0xc4));if(index>=4)return 0;
 P m=manager(b);if(!ensureResearch(b,m))return 1;settleResearch(b,m);
 Economy next=economyRuntime.state;
 if(next.researchIndex==index+1){
  U minutes=researchMinutes(b);if(!minutes)return 1;
  researchPromptUser=owner(b);researchPromptIndex=next.researchIndex;researchPromptDue=next.researchDue;
  P timer=reinterpret_cast<P>(researchTimer);at<U>(timer,0x1f4)=minutes;U callback[6]={0,b+0x108531c,0,0,1,0};
  researchFinishPrompt=true;offlineTrainingFinishPrompt(b,timer,reinterpret_cast<P>(callback));researchFinishPrompt=false;
  log(b,"research-gem-prompt",index,evolutionPrice(b,minutes));return 1;
 }
 if(next.researchIndex||next.evolutionIndex||next.upgradeKind){economyNotice(b,"[V54_UPGRADE_BUSY]");return 1;}
 U level=next.researchLevels[index];if(level>=4)return 1;
 if(next.baseLevel<RESEARCH_SPECS[index].base[level-1]){economyNotice(b,"[V54_BASE_LEVEL_REQUIRED]");return 1;}
 U cost=RESEARCH_SPECS[index].cost[level-1];if(next.coins<cost){economyNotice(b,"[PVP_ERROR_PVPCOIN_NOT_ENOUCH]");return 1;}
 next.coins-=cost;next.researchIndex=index+1;next.researchDue=realNow(b)+RESEARCH_SPECS[index].seconds[level-1];
 if(commitProgression(b,m,next)){log(b,"research-started",index,cost);call<void>(b,0x10849c0,ui);researchView.ui=nullptr;offlineResearchTick(b,ui);}
 return 1;
}
static U finishResearchWithGems(U b,P timer){
 P m=manager(b);if(!ensureResearch(b,m))return 1;settleResearch(b,m);Economy next=economyRuntime.state;
 if(researchPromptUser!=owner(b)||!next.researchIndex||researchPromptIndex!=next.researchIndex||researchPromptDue!=next.researchDue)return 1;
 U price=evolutionPrice(b,at<U>(timer,0x1f4));if(!price||price>15)return 1;
 if(call<I>(b,0x747d00,profile(b),price)<0){economyNotice(b,"[V41_GEMS_REQUIRED]");return 1;}
 U index=next.researchIndex-1;++next.researchLevels[index];next.researchIndex=next.researchDue=0;
 if(!commitProgression(b,m,next)){call<void>(b,0x745220,profile(b),price,1);return 1;}
 researchPromptUser=0;log(b,"research-finished-with-gems",index,price);return 1;
}
