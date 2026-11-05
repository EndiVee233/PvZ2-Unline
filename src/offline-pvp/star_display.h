// Native ArenaStarWidget already keeps the earned count at +f0. Its original
// draw positions and unearned images stay intact; use the loaded UICommon
// illuminated star for earned slots instead of a retained PopAnim overlay.
static U starImageWeak[2];
static P illuminatedStar(U b){
 P objects=call<P>(b,0x11d74b4);P weak=reinterpret_cast<P>(starImageWeak);
 P image=call<P>(b,0x1da034,objects,weak);if(image)return image;
 P resources=at<P>(reinterpret_cast<P>(b),0x183607c);if(!resources)return nullptr;
 P key=nullptr;narrow(b,reinterpret_cast<P>(&key),"IMAGE_UI_HUD_INGAME_ARENA_STAR_ON");
 U saved=at<U>(resources,0xe8),scope=at<U>(reinterpret_cast<P>(b),0x183606c);if(scope)at<U>(resources,0xe8)=scope;
 // Native offsets, not Ghidra's image-base-adjusted labels. The original
 // draw path at 109eb2c/109eb40 calls these exact two entry points.
 P record=call<P>(b,0x11ba888,resources,call<U>(b,0x11b5b5c),&key);
 if(scope)at<U>(resources,0xe8)=saved;release(b,key);
 if(!record)return nullptr;
 call<void>(b,0x1d9bb4,weak,0,at<U>(record,0x18),at<U>(record,0x1c));
 image=call<P>(b,0x1da034,objects,weak);if(image)log(b,"star-display-image-loaded");return image;
}
extern "C" U offlineStarAnimation(U b,P widget){return regular(b)&&arenaModule(b)?1:0;}
extern "C" void offlineStarDraw(U b,P widget,P graphics,P original,I x,I y,U slot){
 P image=original;
 if(slot<3&&regular(b)&&arenaModule(b)){
  U count=at<U>(widget,0xf0);
  if(count<=3&&slot<count){P lit=illuminatedStar(b);if(lit)image=lit;}
 }
 call<void>(b,0x11694c8,graphics,image,x,y);
}
