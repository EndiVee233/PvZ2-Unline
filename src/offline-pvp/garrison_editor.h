static U defenseSessionTarget;
static bool defenseSessionActive;
#ifdef PVP_DEFENSE_DESKTOP_CURSOR
// Board creates ArenaEditPlantCursor with a zero rectangle, so its ordinary
// release handler always drops it. A small logical-coordinate click rectangle
// enables the existing BaseCursor retain/promotion/cancel lifecycle. The
// desktop hover, preview draw and crosshair passes already handle that slot.
extern "C" void offlineDefenseCursorReady(U b,P board,P cursor){
 if(!defenseSessionActive||!cursor||!board||defenseSessionUser!=owner(b)||!regular(b)||
    !sameText(at<P>(board,0xc4),"arena_plant_test")||at<U>(board,0xc0)==9)return;
 I x=at<I>(cursor,4),y=at<I>(cursor,8);
 at<I>(cursor,12)=x-10;at<I>(cursor,16)=y-10;
 at<I>(cursor,20)=20;at<I>(cursor,24)=20;
}
#endif
#ifdef PVP_GARRISON_REPOSITION
extern "C" U offlineGarrisonRepositionMode(){return 1;}
#include "garrison_roster.h"
#endif
static bool ownedGarrison(U b,U target){
 P m=manager(b);if(!regular(b)||!businessId(target)||!ensureEconomy(b,m)||
  !(economyRuntime.state.businessOwnedMask&businessBit(target)))return false;
 const BusinessPlot*s=businessId(target);P begin=at<P>(m,0x110),end=at<P>(m,0x114);
 if(!begin||end<begin||U(end-begin)>64*256||U(end-begin)%64)return false;
 for(P p=begin;p<end;p+=64)if(at<U>(p,0)==target&&at<U>(p,48)==s->zone&&at<U>(p,52)==s->position)
  return at<U64>(p,8)==offlineBusinessIdentity(b);
 return false;
}
static bool openLocalDefense(U b,U target){
 if(target&&!ownedGarrison(b,target))return false;
 P m=manager(b);Store saved{};I found=target?readGarrison(b,target,saved):I(readStore(b,saved));
 if(found<0){economyNotice(b,"[V38_PVP_SAVE_ERROR]");log(b,"garrison-invalid",target);return false;}
#ifdef PVP_GARRISON_REPOSITION
 // v81 incorrectly started shops empty. Restore the full neutral roster on
 // first entry (or a valid v81 empty file), without writing until normal save.
 if(target&&(!found||!saved.positions)){
  initialBusinessFormation(b,*businessId(target),saved);found=1;
  log(b,"garrison-roster-restored",target,saved.positions);
 }
#endif
 // Serialize/read before ending the old editor; bind the new target only
 // after Board::Finish has sent its old module's teardown callback.
 finishArenaBoard(b);
 if(found){apply(b,m+0x80,saved);log(b,target?"garrison-loaded":"defense-loaded",saved.positions,saved.infos);}
 else {clear(b,m+0x80);at<U>(m+0x80,28)=1;log(b,target?"garrison-new":"defense-new",target);}
#ifdef PVP_GARRISON_REPOSITION
 if(target)bindGarrisonRoster(saved);else {garrisonRosterSize=0;garrisonPlantCount=0;}
#endif
 defenseSessionUser=owner(b);defenseSessionTarget=target;defenseSessionActive=true;
 at<U>(m,0xa8)=target?2:1;at<U>(m,0xf4)=target;
 const BusinessPlot*s=businessId(target);
 at<U>(m,0xf8)=s?s->position:0;at<U>(m,0xfc)=s?s->zone:0;at<U>(m,0x104)=target;
 at<unsigned char>(m,0x100)=at<unsigned char>(m,0x101)=at<unsigned char>(m,0x102)=at<unsigned char>(m,0x103)=0;
 call<void>(b,0x85e7d8);log(b,"defense-editor-target",target);return true;
}
static bool defendBusiness(U b,const BusinessPlot&s){
 if(!ownedGarrison(b,s.id))return false;
 P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0),board=at<P>(app,0x6bc);
 P g=at<P>(reinterpret_cast<P>(b),0x1835eec);
 bool live=board&&at<U>(board,0xc0)!=9&&sameText(at<P>(board,0xc4),"arena_plant_test");
 bool pending=at<U>(g,0xa24)==6&&sameText(at<P>(g,0xa40),"arena_plant_test");
 if(defenseSessionActive&&defenseSessionUser==owner(b)&&defenseSessionTarget==s.id&&(live||pending)){
  log(b,"garrison-entry-duplicate",s.id);return true;
 }
 return openLocalDefense(b,s.id);
}
static bool saveLocalDefense(U b){
 P m=manager(b);U target=defenseSessionTarget;
 if(!defenseSessionActive||defenseSessionUser!=owner(b)||(target&&(!ownedGarrison(b,target)||at<U>(m,0xa8)!=2||at<U>(m,0xf4)!=target))||
  (!target&&at<U>(m,0xa8)!=1)){economyNotice(b,"[V38_PVP_SAVE_ERROR]");return false;}
 Store saved{};bool captured=capture(b,m+0x80,saved);
#ifdef PVP_GARRISON_REPOSITION
 if(captured&&target&&!validGarrisonMove(saved)){
  economyNotice(b,"[V82_REPOSITION_ONLY]");log(b,"garrison-roster-change-denied",target,saved.positions);return false;
 }
#endif
 bool ok=captured&&(target?writeGarrison(b,target,saved):writeStore(b,saved));
 if(!ok){economyNotice(b,"[V38_PVP_SAVE_ERROR]");log(b,"defense-save-failed",target);return false;}
 log(b,target?"garrison-saved":"defense-saved",saved.positions,saved.infos);
 log(b,"defense-saved-target",target);
 finishArenaBoard(b);scene(b,25);return true;
}
