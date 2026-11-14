// Shared by the full payload and the bounded maintenance patch.
static bool pvpMusicGrass(P level){
 return sameText(level,"arena_battle_test")||sameText(level,"arena_plant_test");
}
static U pvpMusicTrack(U b){
 P game=at<P>(reinterpret_cast<P>(b),0x1835eec);
 if(!game)return 0;
 U current=at<U>(game,0x984);
 if(current==25||current==28||current==29)return 1;
 if(current!=6)return 0;
 P holder=at<P>(reinterpret_cast<P>(b),0x1821674);
 P app=holder?at<P>(holder,0):nullptr;
 P board=app?at<P>(app,0x6bc):nullptr;
 if(board&&pvpMusicGrass(at<P>(board,0xc4)))return 2;
 return at<U>(game,0xa24)==6&&pvpMusicGrass(at<P>(game,0xa40))?2:0;
}
