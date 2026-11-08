// Custom tracks replace only the Wwise music bus. The original music slider
// remains the source of truth and the native engine still handles sound effects.
static bool customPvpMusic;

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
extern "C" U offlinePvpMusicEffectiveGain(U,U gain){
 return customPvpMusic?0:gain;
}
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
