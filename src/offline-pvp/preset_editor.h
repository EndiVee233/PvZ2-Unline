// Standalone formation documents. No player wallet, plant inventory or .def file writes.
// All entry points run on the existing GL/event thread via the small JNI bridge.
#include "preset_editor_catalog.h"
struct EditorPlacement {U type,row,col,grade;};
struct EditorSession {
 Store prior;
 U priorScene,priorMode,priorKind,priorFormationFlag,priorTarget[7],priorDefenseUser,priorDefenseTarget;
 unsigned char priorTutorial;bool priorDefenseActive,seenBoard,ending;
 U mask,grade,forcedGrade,count;EditorPlacement plants[45];
};
static EditorSession* editorSession;
static P editorSettings;
static U editorEvent,editorOutputSize,editorOutput[184];
#ifdef PVP_PRESET_NATIVE_PAGES
static U editorPage;
static bool editorNetworkEnabled;
static const U editorTitles[3][20]={
 {0x8054,0x7f51,0x83b7,0x53d6,'P','V','P',0x5173,0x5361},
 {'P','V','P',0x6a21,0x5f0f,0x9884,0x8bbe,0x9635,0x5bb9},
 {0x4fee,0x6539,'P','V','P',0x6a21,0x5f0f,0x9884,0x8bbe,0x9635,0x5bb9}};

extern "C" void offlinePresetPageTitle(U b,P holder,P token){
 if(!editorPage){call<void>(b,0x8e4560,holder,token);return;}
 P title=nullptr;char allocator=0;
 call<void>(b,0x14eb451,&title,editorTitles[editorPage==4?2:editorPage-1],&allocator);
 call<void>(b,0x14e9b0d,holder+0xa0,&title);
 release(b,title,true);
}

extern "C" U offlinePresetPageRows(U b,P scroll,P description){
 if(!editorPage||!editorSettings)return 0;
 // The template created the original explanatory label, but has not attached it.
 call<void>(b,at<U>(at<P>(description,0),4)-b,description);
 static const U toggles[2][12]={{0x5f00,0x542f,0x8054,0x7f51,0x83b7,0x53d6},{0x5173,0x95ed,0x8054,0x7f51,0x83b7,0x53d6}};
 static const U tiers[4][3]={{0x4e00,0x9636},{0x4e8c,0x9636},{0x4e09,0x9636},{0x56db,0x9636}};
 static const U details[]={0x5173,0x5361,0x8d44,0x6599,0};
 static const U files[2][12]={{0x6253,0x5f00,0x9884,0x8bbe,0x6587,0x4ef6},{0x672c,0x673a,0x5173,0x5361}};
 U count=editorPage==2||editorPage==4?5:2;
 P arrow=editorPage==1?nullptr:call<P>(b,0x1dd8f0,reinterpret_cast<P>(b+0x1848a98));
 for(U i=0;i<count;++i){
  const U*label=editorPage==1?toggles[i]:editorPage==3?files[i]:i?tiers[i-1]:details;
  P title=nullptr;char allocator=0;
  call<void>(b,0x14eb451,&title,label,&allocator);
  P row=editorPage==1?call<P>(b,0x8e4edc,editorSettings,1021+i,&title,U(editorNetworkEnabled==(i==0)))
       :call<P>(b,0x8e4898,editorSettings,(editorPage==3?1031:1010)+i,&title,arrow);
  call<void>(b,0x8e5924,scroll,row);
  release(b,title,true);
 }
 return 1;
}
#endif
static const EditorPlantSpec* editorSpec(U type){
 for(U i=0;i<EDITOR_PLANT_COUNT;++i)if(EDITOR_PLANTS[i].id==type)return EDITOR_PLANTS+i;
 return nullptr;
}
static P editorApp(U b){return at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0);}
static P editorBoard(U b){P a=editorApp(b);return a?at<P>(a,0x6bc):nullptr;}
static bool editorLevel(P board){return board&&sameText(at<P>(board,0xc4),PRESET_BOARD_NAME);}
#ifdef PVP_PRESET_STOCK_BOARD
extern "C" P offlinePresetLevelDefinition(U b,P out,P registry,P name){
 if(!presetEditing||!sameText(at<P>(name,0),PRESET_BOARD_NAME))
  return call<P>(b,0x440dc4,out,registry,name);
 // Keep the stock board identity for lifecycle, UI and input. Swap only the data read.
 P dataName=nullptr;
 narrow(b,reinterpret_cast<P>(&dataName),"arena_preset_editor");
 P result=call<P>(b,0x440dc4,out,registry,&dataName);
 release(b,dataName);
 log(b,"preset-definition-loaded");
 return result;
}
#ifdef PVP_PRESET_EDIT_TOOLS
extern "C" void offlinePresetAdvanceDefensePhase(U b,P module,U phase){
 if(!presetEditing){call<void>(b,0x1097d00,module,phase);return;}
 // Phase 3 checks the tutorial flag. Outside this transition, the same flag
 // would hide the seed bank, shovel and sun HUD in the stock edit scene.
 P managerState=manager(b);
 auto& tutorial=at<unsigned char>(managerState,0x17d);
 unsigned char previous=tutorial;
 tutorial=1;
 call<void>(b,0x1097d00,module,phase);
 tutorial=previous;
 log(b,"preset-edit-tools-ready",phase);
}
#else
extern "C" void offlinePresetHideTutorialSave(U b,P button,U visible){
 // The tutorial suppression flag also hides Save at the end of phase 2.
 // Preset editing keeps the ordinary Save button while skipping the lesson.
 if(presetEditing){log(b,"preset-save-button-ready");return;}
 call<void>(b,0x9766f4,button,visible);
}
#endif
#endif
static void editorRefillSun(P board){
 // Board stores sun as rotate-left(sun XOR key, key & 31).
 // Stock board initialization writes the pair at +0x12c/+0x130;
 // ArenaPlant reads it in the defense editor at 0x1097b4c.
 U key=at<U>(board,0x130);
 U shift=key&31;
 U encoded=100000U^key;
 at<U>(board,0x12c)=(encoded<<shift)|(encoded>>((32-shift)&31));
}
extern "C" U offlinePresetValidate(const U* data,U size){
 if(!data||size<2||!data[0]||(data[0]&~15U)||data[1]>45||size!=2+4*data[1])return 0;
 for(U i=0;i<data[1];++i){const U*p=data+2+i*4;const EditorPlantSpec*s=editorSpec(p[0]);
  if(!s||p[1]>=5||p[2]>=9||p[3]<1||p[3]>s->maxLevel)return 0;
  for(U j=0;j<i;++j){const U*q=data+2+j*4;if(q[1]==p[1]&&q[2]==p[2])return 0;}
 }
 return 1;
}
extern "C" void offlinePresetSettingsReady(U b,P ui){
 static const U labels[][20]={
  {0x8054,0x7f51,0x83b7,0x53d6,'P','V','P',0x5173,0x5361,0},
  {'P','V','P',0x6a21,0x5f0f,0x9884,0x8bbe,0x9635,0x5bb9,0},
  {0x4fee,0x6539,'P','V','P',0x6a21,0x5f0f,0x9884,0x8bbe,0x9635,0x5bb9,0},
  {0x68c0,0x67e5,0x66f4,0x65b0,0}};
 P scroll=at<P>(ui,0xbc);if(!scroll)return;
 P arrow=call<P>(b,0x1dd8f0,reinterpret_cast<P>(b+0x1848a98));if(!arrow)return;
 for(U i=0;i<sizeof(labels)/sizeof(labels[0]);++i){P title=nullptr;char allocator=0;
  call<void>(b,0x14eb451,&title,labels[i],&allocator);
  P row=call<P>(b,0x8e4898,ui,1001+i,&title,arrow);
  call<void>(b,0x8e5924,scroll,row);release(b,title,true);
 }
}
extern "C" U offlinePresetSettingsClick(U b,P ui,U id){
#ifdef PVP_PRESET_NATIVE_PAGES
 if(id<=1){if(editorSettings==ui){editorSettings=nullptr;editorPage=0;}return 0;}
 if(id==1004){if(!presetEditing)editorEvent=19;return 1;}
 if(id>=1001&&id<=1003){
  if(presetEditing||at<P>(ui,0xc0)||at<U>(ui,0xd4))return 1;
  editorSettings=ui;editorPage=id-1000;
  if(editorPage==2)editorEvent=20;
  return 2; // Use the original submenu transition (ID 9).
 }
 if(ui!=editorSettings||!editorPage)return 0;
 if((editorPage==2||editorPage==4)&&id==1010){editorEvent=editorPage==2?14:15;return 1;}
 if((editorPage==2||editorPage==4)&&id>=1011&&id<=1014){editorEvent=id-(editorPage==2?990:970);return 1;}
 if(editorPage==1&&(id==1021||id==1022)){
  editorNetworkEnabled=id==1021;editorEvent=editorNetworkEnabled?31:32;
  return 1;
 }
 if(editorPage==3&&(id==1031||id==1032)){editorEvent=id==1031?3:4;return 1;}
 return 0;
#else
 if(id<1001||id>1003){if(id==0&&editorSettings==ui)editorSettings=nullptr;return 0;}
 if(!editorEvent&&!presetEditing){editorSettings=ui;editorEvent=id-1000;}
 return 1;
#endif
}
extern "C" U offlinePresetUnlock(U b,P player,P key){
 if(!presetEditing||!key)return 0;
 for(U i=0;i<EDITOR_PLANT_COUNT;++i)if(sameText(at<P>(key,0),EDITOR_PLANTS[i].alias))return 1;
 return 0;
}
extern "C" U offlinePresetGrade(U b,P m,P weak){
#ifdef PVP_GITHUB_PRESETS
 if(sharedSpawnGrade)return sharedSpawnGrade;
#endif
 if(!presetEditing||!editorSession)return 0;
 U grade=editorSession->forcedGrade?editorSession->forcedGrade:editorSession->grade;
 P type=weak?call<P>(b,0x1da034,call<P>(b,0x11d74b4),weak):nullptr;
 if(type)for(U i=0;i<EDITOR_PLANT_COUNT;++i)if(sameText(at<P>(type,4),EDITOR_PLANTS[i].alias)){
  if(grade>EDITOR_PLANTS[i].maxLevel)grade=EDITOR_PLANTS[i].maxLevel;break;}
 return grade;
}
extern "C" U offlinePresetUsePlacementGrade(U b){
 return presetEditing&&editorSession&&editorLevel(editorBoard(b));
}
extern "C" void offlinePresetSpawnGrade(U b,U col,U row){
 if(!presetEditing||!editorSession)return;
 editorSession->forcedGrade=0;
 for(U i=0;i<editorSession->count;++i){const EditorPlacement&p=editorSession->plants[i];
  if(p.row==row&&p.col==col){editorSession->forcedGrade=p.grade;break;}}
}
extern "C" void offlinePresetSpawnDone(U b){if(editorSession)editorSession->forcedGrade=0;}
static void editorRefreshBank(U b,P module){
 if(!presetEditing||!module)return;
 P registry=call<P>(b,0x11d74b4);P bank=call<P>(b,0x1da034,registry,module+0x48);if(!bank)return;
 U count=at<unsigned char>(bank,0x11d);if(count>127)return;
 for(U i=0;i<count;++i){U weak[2]={0,0};call<void>(b,0x895f0c,weak,bank,i);
  P packet=call<P>(b,0x1da034,registry,weak);if(packet){
   U grade=editorSession->grade;if(i<EDITOR_PLANT_COUNT&&grade>EDITOR_PLANTS[i].maxLevel)grade=EDITOR_PLANTS[i].maxLevel;
   call<void>(b,0x1030a9c,packet,grade);
  }
  call<void>(b,0x1d9bb4,weak,0,0,0);
 }
}
extern "C" void offlinePresetBankReady(U b,P module){
 if(!presetEditing)return;
 editorRefreshBank(b,module);
 log(b,"preset-bank-ready");
}
static void editorRestore(U b){
 if(!editorSession)return;EditorSession*s=editorSession;P m=manager(b);
 apply(b,m+0x80,s->prior);at<U>(m,0x9c)=s->priorFormationFlag;at<U>(m,0xa8)=s->priorKind;
 bytes(m+0xf4,reinterpret_cast<P>(s->priorTarget),28);at<unsigned char>(m,0x17d)=s->priorTutorial;
 at<U>(editorApp(b),0x1218)=s->priorMode;
 defenseSessionUser=s->priorDefenseUser;defenseSessionTarget=s->priorDefenseTarget;defenseSessionActive=s->priorDefenseActive;
 U previous=s->priorScene;editorSession=nullptr;presetEditing=false;
 call<void>(b,0x14c2e95,s);scene(b,previous);log(b,"preset-editor-restored",previous);
}
static bool presetRequest(U b,U action){
 if(!presetEditing)return false;
 if(action==1)at<U>(editorApp(b),0x185c)=at<U>(call<P>(b,0x1f7380),0x18);
 if(action==3&&editorSession)editorSession->ending=true;
 return true;
}
static bool presetSave(U b){
 if(!presetEditing||!editorSession||editorSession->ending)return false;
 P board=editorBoard(b);if(!editorLevel(board))return false;
 // Native serializers are used only to enumerate live type/position records.
 // Per-instance grade is read from the live plant, not the lossy per-type map.
 call<void>(b,0x10989a4);call<void>(b,0x1098e38);
 Store* current=reinterpret_cast<Store*>(call<P>(b,0x14c1a7d,sizeof(Store)));
 if(!current||!capture(b,manager(b)+0x80,*current)){if(current)call<void>(b,0x14c2e95,current);editorEvent=13;return false;}
 if(current->positions>45){call<void>(b,0x14c2e95,current);editorEvent=13;return false;}
 P layer=nullptr;narrow(b,reinterpret_cast<P>(&layer),"");
 editorOutput[0]=editorSession->mask;editorOutput[1]=current->positions;bool valid=true;
 for(U i=0;i<current->positions;++i){Pos p=current->pos[i];P plant=call<P>(b,0x203990,board,p.col,p.row,&layer);
  if(!plant){valid=false;break;}U*o=editorOutput+2+i*4;o[0]=p.type;o[1]=p.row;o[2]=p.col;o[3]=at<U>(plant,0x38);
 }
 release(b,layer);editorOutputSize=2+4*current->positions;call<void>(b,0x14c2e95,current);
 if(!valid||!offlinePresetValidate(editorOutput,editorOutputSize)){editorEvent=13;return false;}
 // Export first to Java's durable draft, then leave the level on its ack.
 editorEvent=11;return true;
}
extern "C" U offlinePresetSaveClick(U b){if(!presetEditing)return 0;presetSave(b);return 1;}
extern "C" U offlinePresetCommand(U b,U command,const U*data,U size){
#ifdef PVP_GITHUB_PRESETS
 if(command==8)return setSharedCatalog(b,data,size);
#endif
#ifdef PVP_MUSIC
 if(command==9&&size==1){
  pvpMusicOverride(b,data[0]&&data[0]==pvpMusicTrack(b));
  return 1;
 }
#endif
#ifdef BRANCH_GATE_AUDIO
 if(command==10&&size==1){branchGateDuck(b,data[0]!=0);return 1;}
#endif
 if(command==1){
  if(presetEditing||!editorSettings||!offlinePresetValidate(data,size))return 0;
  P g=at<P>(reinterpret_cast<P>(b),0x1835eec),m=manager(b),app=editorApp(b);
  if(!g||!m||!app||at<U>(g,0x984)==6)return 0;
  EditorSession*s=reinterpret_cast<EditorSession*>(call<P>(b,0x14c1a7d,sizeof(EditorSession)));if(!s)return 0;
  for(U i=0;i<sizeof(*s);++i)reinterpret_cast<P>(s)[i]=0;
  if(!capture(b,m+0x80,s->prior)){call<void>(b,0x14c2e95,s);return 0;}
  s->priorScene=at<U>(g,0x984);s->priorMode=at<U>(app,0x1218);s->priorKind=at<U>(m,0xa8);
  s->priorFormationFlag=at<U>(m,0x9c);bytes(reinterpret_cast<P>(s->priorTarget),m+0xf4,28);s->priorTutorial=at<unsigned char>(m,0x17d);
  s->priorDefenseUser=defenseSessionUser;s->priorDefenseTarget=defenseSessionTarget;s->priorDefenseActive=defenseSessionActive;
  s->mask=data[0];s->count=data[1];for(U i=1;i<=4;++i)if(s->mask&(1U<<(i-1))){s->grade=i;break;}
  bytes(reinterpret_cast<P>(s->plants),reinterpret_cast<const unsigned char*>(data+2),s->count*sizeof(EditorPlacement));
  P settings=editorSettings;editorSettings=nullptr;call<void>(b,0x8e8884,settings,0);
#ifdef PVP_PRESET_NATIVE_PAGES
  editorPage=0;
#endif
  editorSession=s;presetEditing=true;editorEvent=0;
  clear(b,m+0x80);Store* initial=reinterpret_cast<Store*>(call<P>(b,0x14c1a7d,sizeof(Store)));
  if(!initial){editorRestore(b);return 0;}for(U i=0;i<sizeof(Store);++i)reinterpret_cast<P>(initial)[i]=0;
  initial->positions=s->count;initial->user=owner(b);
  for(U i=0;i<s->count;++i){const EditorPlacement&p=s->plants[i];initial->pos[i]={p.type,p.row,p.col};
   bool seen=false;for(U j=0;j<initial->infos;++j)if(initial->info[j].type==p.type)seen=true;
   if(!seen){Info&v=initial->info[initial->infos++];v.type=p.type;v.level=p.grade;}}
  apply(b,m+0x80,*initial);call<void>(b,0x14c2e95,initial);
 at<U>(m,0xa8)=1;
#ifdef PVP_PRESET_EDIT_TOOLS
  at<unsigned char>(m,0x17d)=0;
#else
  at<unsigned char>(m,0x17d)=1;
#endif
  for(U i=0xf4;i<0x110;++i)m[i]=0;
#ifdef PVP_PRESET_STOCK_BOARD
  call<void>(b,0x85e7d8);
#else
  at<U>(app,0x1218)=0;
  P level=nullptr;narrow(b,reinterpret_cast<P>(&level),"arena_preset_editor");
  // Match the package string passed by the game's own defense launcher (0x85e848).
  call<void>(b,0x354360,g,reinterpret_cast<P>(b+0x184700c),&level,-1,1,1);release(b,level);
#endif
  log(b,"preset-editor-open",s->count,s->mask);return 1;
 }
 if(command==2&&presetEditing&&size==1&&data[0]>=1&&data[0]<=4&&(editorSession->mask&(1U<<(data[0]-1)))){
  editorSession->grade=data[0];P board=editorBoard(b);if(editorLevel(board)){
   P modules=at<P>(board,0x938);P module=modules?call<P>(b,0x43af38,modules,call<P>(b,0x10290ac)):nullptr;
   editorRefreshBank(b,module);
  }return 1;
 }
 if(command==3&&presetEditing){finishArenaBoard(b);editorRestore(b);editorEvent=16;return 1;}
 if(command==4){editorSettings=nullptr;return 1;}
#ifdef PVP_PRESET_NATIVE_PAGES
 if(command==5&&size==1){editorNetworkEnabled=data[0]!=0;return 1;}
 if(command==6&&editorSettings&&editorPage==3){editorPage=4;call<void>(b,0x8e7820,editorSettings);return 1;}
 if(command==7){if(editorSettings&&editorPage==1)call<void>(b,0x8e7820,editorSettings);return 1;}
#endif
 return 0;
}
extern "C" U offlinePresetPoll(U b,U*out,U capacity){
 if(presetEditing&&editorSession){
  P board=editorBoard(b);
  if(editorLevel(board)&&at<U>(board,0xc0)!=9){
   if(!editorSession->seenBoard){editorSession->seenBoard=true;if(!editorEvent)editorEvent=10;}
   editorRefillSun(board);
   at<U>(editorApp(b),0x185c)=at<U>(call<P>(b,0x1f7380),0x18);
  }
  if(editorSession->seenBoard&&editorLevel(board)&&at<U>(board,0xc0)==9&&editorEvent!=11)
   editorSession->ending=true;
  if(editorSession->ending){editorRestore(b);if(editorEvent!=11)editorEvent=12;}
 }
 if(!out||capacity<185)return 0;
#ifdef BRANCH_GATE_AUDIO
 if(!editorEvent&&branchGatePending){
  branchGatePending=false;
  P app=pvpMusicApp(b);
  out[0]=17;
  out[1]=app?call<U>(b,0x15de9dc,at<U64>(app,0x90)):0;
  return 2;
 }
#endif
#ifdef SPEED_FEEDBACK
 if(!editorEvent&&pendingSpeedFeedback){
  P app=pvpMusicApp(b);
  out[0]=18;
  out[1]=pendingSpeedFeedback;
  out[2]=app?call<U>(b,0x15de9dc,at<U64>(app,0x90)):0;
  pendingSpeedFeedback=0;
  return 3;
 }
#endif
 if(!editorEvent)return 0;
 U event=editorEvent;editorEvent=0;out[0]=event;
 if(event==11){for(U i=0;i<editorOutputSize;++i)out[i+1]=editorOutput[i];return editorOutputSize+1;}
 return 1;
}
