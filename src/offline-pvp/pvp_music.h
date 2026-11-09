// Custom tracks replace only the Wwise music bus. The original music slider
// remains the source of truth and the native engine still handles sound effects.
static bool customPvpMusic;
#ifdef BRANCH_GATE_AUDIO
static bool branchGatePending;
static bool branchGateDucked;

#ifdef BRANCH_GATE_SPEND
extern "C" void offlineBranchGateSpend(U b,P profile,P world,U cost,P event){
 const bool keyGate=event&&at<U>(event,0x10)==8&&cost>0;
 const U before=keyGate?call<U>(b,0x706da0,profile,world):0;
 call<void>(b,0x748b50,profile,world,cost);
 if(keyGate&&before>=cost&&call<U>(b,0x706da0,profile,world)==before-cost){
  branchGatePending=true;
  log(b,"branch-gate-opened",cost,before-cost);
 }
}
#else
extern "C" void offlineBranchGateOpened(U b,U type,U caller,U state){
 // Key gates open side routes; star gates control entrance/exit of worlds.
 if(type!=8||state!=3)return;
 if(caller!=b+0x809bec&&caller!=b+0x74abb8&&caller!=b+0x9f258c)return;
 branchGatePending=true;
 log(b,"branch-gate-opened");
}
#endif
#endif

static P pvpMusicApp(U b){
 P holder=at<P>(reinterpret_cast<P>(b),0x1821674);
 return holder?at<P>(holder,0):nullptr;
}
static U pvpMusicTrack(U b){
 P game=at<P>(reinterpret_cast<P>(b),0x1835eec);
 if(!game)return 0;
 U current=at<U>(game,0x984);
 if(current==25||current==28||current==29)return 1; // Garden map, PvP lobby, lab.
 if(current!=6)return 0;
 P app=pvpMusicApp(b);
 P board=app?at<P>(app,0x6bc):nullptr;
 if(board&&sameText(at<P>(board,0xc4),"arena_battle_test"))return 2;
 return at<U>(game,0xa24)==6&&sameText(at<P>(game,0xa40),"arena_battle_test")?2:0;
}
static U pvpMusicGain(U b,P app){
 // SexyAppBase stores its configured music volume as an aligned double.
 // The stock mixer setter receives float bits in r1 (soft-float ABI).
 return app?call<U>(b,0x15de9dc,at<U64>(app,0x88)):0;
}
extern "C" U offlinePvpMusicEffectiveGain(U b,U gain){
 if(customPvpMusic)return 0;
#ifdef BRANCH_GATE_AUDIO
 if(branchGateDucked)return call<U>(b,0x15deccc,gain,0x3d4ccccdu); // 0.05f
#endif
 return gain;
}
#ifdef BRANCH_GATE_AUDIO
static void branchGateDuck(U b,bool enabled){
 if(branchGateDucked==enabled)return;
 branchGateDucked=enabled;
 P app=pvpMusicApp(b);
 P mixer=app?at<P>(app,0x460):nullptr;
 if(mixer)call<void>(b,0x1363898,mixer,pvpMusicGain(b,app));
 log(b,"branch-gate-duck",enabled,0);
}
#endif
static void pvpMusicOverride(U b,bool enabled){
 if(customPvpMusic==enabled)return;
 customPvpMusic=enabled;
 P app=pvpMusicApp(b);
 P mixer=app?at<P>(app,0x460):nullptr;
 if(mixer)call<void>(b,0x1363898,mixer,enabled?0:pvpMusicGain(b,app));
}
extern "C" U offlinePvpMusicSample(U b){
 U track=pvpMusicTrack(b);
 if(!track){pvpMusicOverride(b,false);return 0;}
 return (pvpMusicGain(b,pvpMusicApp(b))&~3u)|track;
}
