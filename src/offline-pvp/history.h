// The journal commits with army losses and battle rewards, never in a second
// file after payment. Only completed local battles enter this ten-row list.
static constexpr U HISTORY_NAMESPACE=0x4c4f434c;
static P historyBrief,historyUi;
static U historyUiUser;
extern "C" U offlineHistoryMode(){return 1;}
static void appendHistory(U b,Economy&next,U target,U stars,U coins){
 U count=next.historyCount<10?next.historyCount:9;
 for(U i=count;i>0;--i)next.history[i]=next.history[i-1];
 next.history[0]={next.sequence+1,realNow(b),target,stars,coins,businessId(target)?2u:1u};
 if(next.historyCount<10)++next.historyCount;
}
static const Economy::BattleHistory* findHistory(U serial){
 const auto&s=economyRuntime.state;
 for(U i=0;i<s.historyCount;++i)if(s.history[i].serial==serial)return s.history+i;
 return nullptr;
}
extern "C" P offlineHistoryLookup(U b,U serial,U high){
 if(high!=HISTORY_NAMESPACE||!regular(b)||!historyUi||historyUiUser!=owner(b)||!ensureEconomy(b,manager(b)))return nullptr;
 const auto*h=findHistory(serial);if(!h)return nullptr;
 if(!historyBrief){historyBrief=call<P>(b,0x14c1a7d,0xd0);if(!historyBrief)return nullptr;for(U i=0;i<0xd0;i+=4)at<U>(historyBrief,i)=0;}
 release(b,at<P>(historyBrief,0x9c),true);
 for(U i=0;i<0xd0;i+=4)at<U>(historyBrief,i)=0;
 // PlaybackBrief fields registered by the original RTTI serializer:
 // ia/+90, t/+94, v/+98, on/+9c, opi/+a0, r/+a8,
 // cc/+ac, mc/+b0, agc/+b4, rs/+b8, ft/+c8.
 at<U>(historyBrief,0x88)=serial;at<U>(historyBrief,0x8c)=high;
 at<U>(historyBrief,0x90)=1;at<U>(historyBrief,0x94)=h->kind;
 at<U>(historyBrief,0x98)=serial;at<U>(historyBrief,0xa0)=h->target;
 at<U>(historyBrief,0xa8)=h->stars;at<U>(historyBrief,0xb4)=h->coins;
 at<U>(historyBrief,0xc8)=h->time;
 const NpcPreset*n=npc(h->target);const BusinessPlot*s=businessId(h->target);
 const U*name=n?n->name:s?s->name:nullptr;
 if(name){char alloc=0;call<void>(b,0x14eb451,historyBrief+0x9c,name,&alloc);}
 return historyBrief;
}
extern "C" U offlineHistoryLoad(U b,P ui){
 if(!regular(b))return 0;
 if(!ui||!ensureEconomy(b,manager(b)))return 1;
 historyUi=ui;historyUiUser=owner(b);
 alignas(8) U ids[10][2]{};U count=economyRuntime.state.historyCount;
 for(U i=0;i<count;++i){ids[i][0]=economyRuntime.state.history[i].serial;ids[i][1]=HISTORY_NAMESPACE;}
 P begin=reinterpret_cast<P>(ids);P vector[3]={begin,begin+count*8,begin+sizeof(ids)};
 call<void>(b,0x105b774,ui,vector);
 log(b,"history-opened",count);return 1;
}
extern "C" void offlineHistoryRowReady(U b,P row){
 if(!row||at<U>(row,0xac)!=HISTORY_NAMESPACE||historyUiUser!=owner(b)||!regular(b))return;
 const auto*h=findHistory(at<U>(row,0xa8));if(!h)return;
 // The old residential renderer hides starcoins for its obsolete game mode.
 // Local residential rewards are starcoins, so keep the original third icon.
 at<U>(row,0xd0)=h->coins;
 for(U o=0xb0;o<=0xb4;o+=4)if(P button=at<P>(row,o)){
  call<void>(b,at<U>(at<P>(button,0),0x8c)-b,button,0);
  call<void>(b,at<U>(at<P>(button,0),0xa4)-b,button,1);
 }
}
extern "C" U offlineHistoryAction(U b,P row){
 if(!row||at<U>(row,0xac)!=HISTORY_NAMESPACE)return 0;
 // Replay input streams and revenge are separate recovery steps. A local
 // summary must never fall through to the obsolete download/attack requests.
 return 1;
}
