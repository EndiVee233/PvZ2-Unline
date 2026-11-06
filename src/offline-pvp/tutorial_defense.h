// The original first-defense lesson uses its own level and app mode 3. It
// does not enter offlineOwn/openLocalDefense, so their session setup cannot
// protect it from the preceding player's scout formation or server pings.
static U tutorialDefenseUser;
static bool tutorialDefenseActive;
static bool tutorialDefenseLevel(P text){return sameText(text,"arena_plant_tutorial");}
static void prepareTutorialDefense(U b,P name){
 P p=profile(b);if(!p||at<U>(p,0x75c)<1||at<U>(p,0x75c)>3||!tutorialDefenseLevel(at<P>(name,0)))return;
 P m=manager(b);U prior=0;P first=at<P>(m,0x84),last=at<P>(m,0x88);
 if(first&&last>=first&&U(last-first)<=128*12)prior=U(last-first)/12;
 Store clean{};clean.user=owner(b);clean.infos=1;clean.info[0].type=2;clean.info[0].level=1;
 apply(b,m+0x80,clean);
 at<U>(m,0xa8)=1;at<U>(m,0xf4)=at<U>(m,0x104)=0;
 for(U i=0x100;i<=0x103;++i)m[i]=0;
 tutorialDefenseUser=owner(b);tutorialDefenseActive=true;
 log(b,"tutorial-defense-clean",prior,at<U>(p,0x75c));
}
static bool tutorialDefenseRequest(U b,U action){
 if(!tutorialDefenseActive)return false;
 if(tutorialDefenseUser!=owner(b)){
  // A prior tutorial can finish its native teardown after a player switch.
  if(action==3){tutorialDefenseActive=false;log(b,"tutorial-defense-old-close");return true;}
  return false;
 }
 P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0),board=at<P>(app,0x6bc);
 bool live=board&&tutorialDefenseLevel(at<P>(board,0xc4));
 if(action==1&&live){
  at<U>(app,0x185c)=at<U>(call<P>(b,0x1f7380),0x18);
  log(b,"tutorial-defense-heartbeat");return true;
 }
 if(action==3){tutorialDefenseActive=false;log(b,"tutorial-defense-closed");return true;}
 if(live)log(b,"tutorial-defense-other-request",action);
 return false;
}
