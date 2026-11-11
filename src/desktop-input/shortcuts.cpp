// Native desktop input bridge. All game calls execute on its existing event thread.
using U=unsigned; using P=unsigned char*;
template<class T> T &at(P p,U off){return *reinterpret_cast<T*>(p+off);}
template<class R,class... A> R call(U base,U off,A... a){return reinterpret_cast<R(*)(A...)>(base+off)(a...);}
template<class R,class... A> R virt(P p,U off,A... a){return reinterpret_cast<R(*)(P,A...)>(at<U>(reinterpret_cast<P>(at<U>(p,0)),off))(p,a...);}
struct Touch {U id,pad;int x,y,px,py,taps,pad2;U time[2];U phase;};
struct Weak {U a,b;};
static P resolve(U b,Weak *w){if(!(w->a|w->b))return nullptr;return call<P>(b,0x1da034,call<P>(b,0x11d74b4),w);}
static void weak(U b,Weak *w,U a=0,U c=0){call<void>(b,0x1d9bb4,w,0,a,c);}
// RtObject::IsType returns bool, not an adjusted object pointer.
static P cast(U b,P p,U type){return p&&virt<int>(p,0x10,call<P>(b,type))?p:nullptr;}
static P widget(U b,const char *name){
 P s=nullptr;char alloc=0;
 call<void>(b,0x14ed0e1,&s,name,&alloc);
 P p=call<P>(b,0x97714c,&s);
 call<void>(b,0x14ebf59,s-12,&alloc);return p;
}
static bool enabled(U b,P p){return p&&call<int>(b,0x976720,p);}
static bool equal(const char *a,const char *z){if(!a)return false;while(*a&&*a==*z){++a;++z;}return *a==*z;}
static int scaled(U b,int n,U scale){return call<int>(b,0x15df0f8,call<U>(b,0x15deccc,call<U>(b,0x15dec20,n),scale));}
static bool playable(P board){U s=at<U>(board,0xc0);return (s==4||s==5)&&!at<unsigned char>(board,0x8d5);}
static bool modal(P app){return virt<int>(app,0x12c,1)!=0;}
#ifdef DESKTOP_PVP_SEEDS
static P defensePacket(U b,P board,U slot){
 // The home editor has three separate bank weak refs in PVPSeedBankModule.
 // Never select the zombie/skill bank, a merchant's fixed roster, or a trial
 // card through the ordinary SeedBank assumptions.
 P m=call<P>(b,0x7fa754);
 if(!m||at<U>(m,0xa8)!=1)return nullptr;
 P modules=at<P>(board,0x938);if(!modules)return nullptr;
 P module=call<P>(b,0x43af38,modules,call<P>(b,0x10290ac));if(!module)return nullptr;
 P bank=cast(b,resolve(b,reinterpret_cast<Weak*>(module+0x48)),0x102dc20);
 if(!enabled(b,bank))return nullptr;
 U count=at<unsigned char>(bank,0x11d),page=at<U>(bank,0x148),perPage=at<U>(bank,0x14c);
 call<int>(b,0x147adc,4,"DesktopInput","pvp-slot slot=%u count=%u page=%u size=%u",slot,count,page,perPage);
 if(!count||!perPage||perPage>128||page>128||slot>=perPage)return nullptr;
 U index=page*perPage+slot;if(index>=count)return nullptr;
 Weak packet{0,0};call<void>(b,0x895f0c,&packet,bank,index);
 P target=cast(b,resolve(b,&packet),0x1030720);weak(b,&packet);
 // The normal click path, below, owns stock/sun/disable checks. PVP packets
 // have different availability fields from ordinary SeedPacket packets.
 return target;
}
#endif
static bool click(U b,P app,P board,P p,Touch *source){
 if(!enabled(b,p))return false;
 int pos[2];call<void>(b,0x976478,pos,p);
 // Respect occlusion and the same hit-test used by ordinary UI touches.
 P hit=call<P>(b,0x9775d4,pos[0],pos[1],200);
 if(hit!=p)return false;
 Touch t;for(U i=0;i<sizeof(t)/4;++i)reinterpret_cast<U*>(&t)[i]=reinterpret_cast<U*>(source)[i];
 t.id=0x7ffffffe;t.x=pos[0];t.y=pos[1];
 t.px=t.x;t.py=t.y;t.taps=1;t.phase=0;
 // Feed the normal application touch entry, including widget routing, tutorial
 // locks, cooldown/resource checks and Board-local coordinate conversion.
 virt<void>(app,0x1c8,&t);
 t.x=pos[0];t.y=pos[1];t.px=t.x;t.py=t.y;t.phase=3;
 if(at<P>(app,0x6bc)==board)virt<void>(app,0x1cc,&t);
 return true;
}
#ifdef DESKTOP_EXTENDED_INPUT
static P selectedPacket(U b,P board){
 P cursor=at<P>(board,0x94c);
 // PlantCursor retains the originating packet, even as the belt moves.
 if(!cursor||at<U>(cursor,0)!=b+0x179b940||at<unsigned char>(cursor,0x1d))return nullptr;
 return resolve(b,reinterpret_cast<Weak*>(cursor+0x28));
}
static P seedShortcut(U b,P board,int slot,int step,bool useBoardBank=false){
 P boardBank=call<P>(b,0x20bb34,board);
 P belt=cast(b,boardBank,0x29a23c);
 P bank=belt||useBoardBank?boardBank:widget(b,"UISeedBank");
 if(!enabled(b,bank))return nullptr;
 U begin=at<U>(bank,0x48),end=at<U>(bank,0x4c);
 int limit=at<signed char>(bank,0x11d);
 if(!begin||end<begin||end-begin>32*8||limit<=0)return nullptr;
 U count=0;
 struct Card { P packet; int y; };
 Card cards[32];
 for(U entry=begin;entry<end&&int((entry-begin)/8)<limit;entry+=8){
  P p=cast(b,resolve(b,reinterpret_cast<Weak*>(entry)),0x8ac6f4);
  if(p&&(at<U>(p,0x10c)&(belt?16|32:2|16|32)))p=nullptr;
  if(!belt){cards[count++]={p,0};continue;}
  if(!enabled(b,p))continue;
  int center[2];call<void>(b,0x976478,center,p);
  if(call<P>(b,0x9775d4,center[0],center[1],200)!=p)continue;
  U index=count++;
  while(index&&cards[index-1].y>center[1]){
   cards[index]=cards[index-1];--index;
  }
  cards[index]={p,center[1]};
 }
 if(step){
  slot=0;
  P current=selectedPacket(b,board);
  for(U index=0;current&&index<count;++index)
   if(cards[index].packet==current){slot=int(index)+step;break;}
 }
 return U(slot)<count?cards[slot].packet:nullptr;
}
static void plantfoodShortcut(U b,P driver,P app,P board,Touch *source){
 if(at<U>(board,0xc0)!=5||at<unsigned char>(board,0x895))return;
 const char *level=at<const char*>(board,0xc4);
 if(level&&level[0]=='a'&&level[1]=='r'&&level[2]=='e'&&level[3]=='n'&&level[4]=='a'&&level[5]=='_')return;
 U key=at<U>(board,0x120);
 if(!((__builtin_rotateright32(at<U>(board,0x11c),key&31)^key)&255))return;
 if(!enabled(b,widget(b,"UIPlantfood"))||source->px<0||source->py<0)return;

 Touch t=*source;
 t.x=source->px;t.y=source->py;
 call<void>(b,0x1327d0c,driver,&t);
 if(call<P>(b,0x9775d4,t.x,t.y,200))return;
 U scale=at<U>(app,0x690);
 if(!(scale&0x7fffffff))return;
 // Match the native cursor's screen-to-lawn conversion and plant priority.
 U inverse=call<U>(b,0x15dee64,0x3f800000u,scale);
 int col=call<int>(b,0x24105c,scaled(b,t.x-at<int>(board,0x2c),inverse));
 int row=call<int>(b,0x2410b8,scaled(b,t.y-at<int>(board,0x30),inverse));
 if(U(col)>=9||U(row)>=5)return;
 P name=nullptr;char alloc=0;
 call<void>(b,0x14ed0e1,&name,"smallChestnut",&alloc);
 P plant=call<P>(b,0x203990,board,col,row,&name);
 call<void>(b,0x14ebf59,name-12,&alloc);
 if(plant)call<bool>(b,0x4e7f60,plant);
}
#endif
static void collect(U b,P app,P board,Touch *source,bool all){
 if(!playable(board)||modal(app))return;
 P dispatcher=at<P>(board,0x93c);if(!dispatcher)return;
 P begin=at<P>(dispatcher,0),end=at<P>(dispatcher,4);
 if(!begin||end<begin||U(end-begin)>0x48000)return;
 // Snapshot weak handles: a collection callback may change the listener vector.
 Weak refs[256];U count=0;
 for(P entry=begin;entry<end&&count<256;entry+=0x48){
  P obj=at<P>(entry,12);if(!obj||!cast(b,obj,0x27c56c))continue;
  bool duplicate=false;for(U j=0;j<count;++j)if(refs[j].a==at<U>(obj,8)&&refs[j].b==at<U>(obj,12))duplicate=true;
  if(duplicate)continue;
  refs[count].a=refs[count].b=0;weak(b,&refs[count],at<U>(obj,8),at<U>(obj,12));++count;
 }
 for(U j=0;j<count;++j){
  P obj=resolve(b,&refs[j]);
  if(obj&&at<P>(app,0x6bc)==board&&playable(board)&&!(at<U>(obj,0x8c)&0x80)&&at<U>(obj,0x94)!=1){
   Touch t;for(U i=0;i<sizeof(t)/4;++i)reinterpret_cast<U*>(&t)[i]=reinterpret_cast<U*>(source)[i];
   t.phase=1;
   if(all){P rect=virt<P>(obj,0x90);U scale=at<U>(app,0x690);
    t.x=scaled(b,at<int>(rect,0)+at<int>(rect,8)/2,scale);
    t.y=scaled(b,at<int>(rect,4)+at<int>(rect,12)/2,scale);
   }
   virt<int>(obj,0xe4,&t);
  }
  weak(b,&refs[j]);
 }
}
extern "C" __attribute__((section(".text.entry"))) void desktopInput(U b,P driver,Touch *event,U mode){
 P app=at<P>(driver,0x44);if(!app)return;P board=at<P>(app,0x6bc);if(!board)return;
 if(mode==5){collect(b,app,board,event,false);return;}
 int key=event->x;
 bool canPlay=playable(board);
 bool useBoardBank=false;
#ifdef DESKTOP_ENDLESS_INPUT
 const char *level=at<const char*>(board,0xc4);
 useBoardBank=equal(level,"festival_dangerroom_level_endless")
             ||equal(level,"FESTIVAL_DANGERROOM_LEVEL_ENDLESS");
 if(useBoardBank&&!canPlay&&!at<unsigned char>(board,0x8d5)){
  P modules=at<P>(board,0x938);
  P lastStand=modules?call<P>(b,0x43af38,modules,call<P>(b,0x3f8538)):nullptr;
  // Native Last Stand state 4 enables lawn editing and Start Battle.
  canPlay=lastStand&&at<U>(lastStand,0x34)==4;
 }
#endif
 // Pause must pass through ordinary input routing, including tutorial locks.
 if(key==62){
  if(at<unsigned char>(board,0x8d5)){
   if(at<U>(app,0x1378)&&!modal(app)){
    call<void>(b,0x4021b0,app);virt<void>(board,0x58,0);
   }
  }else if(canPlay&&!modal(app))click(b,app,board,widget(b,"UIPauseButton"),event);
  return;
 }
 if(!canPlay||modal(app))return;
#ifdef DESKTOP_EXTENDED_INPUT
 if(key==101){plantfoodShortcut(b,driver,app,board,event);return;}
#endif
 if(key==100){call<void>(b,0x20963c,board);return;}
 if(key==29){collect(b,app,board,event,true);return;}
 P target=nullptr;
 int slot=-1;
 if(key>=8&&key<=11)slot=key-8;
 if(key==45)slot=4;if(key==51)slot=5;if(key==33)slot=6;if(key==46)slot=7;
#ifdef DESKTOP_EXTENDED_INPUT
 if(key==54||key==52)target=seedShortcut(b,board,-1,key==54?-1:1,useBoardBank);
 else
#endif
 if(slot>=0){
#ifdef DESKTOP_PVP_SEEDS
  if(equal(at<const char*>(board,0xc4),"arena_plant_test")||equal(at<const char*>(board,0xc4),"arena_preset_editor"))target=defensePacket(b,board,U(slot));
  else {
#endif
#ifdef DESKTOP_EXTENDED_INPUT
  target=seedShortcut(b,board,slot,0,useBoardBank);
#else
  P bank=widget(b,"UISeedBank");if(!enabled(b,bank))return;
  U n=(at<U>(bank,0x4c)-at<U>(bank,0x48))/8;
  if(n>32||U(slot)>=n||slot>=at<signed char>(bank,0x11d))return;
  Weak *w=reinterpret_cast<Weak*>(at<P>(bank,0x48)+slot*8);target=resolve(b,w);
  // Normal packets only: do not bind trial/free gift cards.
  target=cast(b,target,0x8ac6f4);if(!target)return;
  if(at<U>(target,0x10c)&(2|16|32))return;
#endif
#ifdef DESKTOP_PVP_SEEDS
  }
#endif
 }else if(key==34)target=widget(b,"UIPlantfood");
 else if(key==32)target=widget(b,"UIShovel");
 else if(key==50)target=widget(b,"UIChangeSpeedButton");
 else if(key==41){
  P holder=widget(b,"UIPowerupHolder");if(!enabled(b,holder))return;
  P a=at<P>(holder,0x48),z=at<P>(holder,0x4c);if(!a||z<a||U(z-a)>256)return;
  for(;a<z;a+=8){P ui=cast(b,resolve(b,reinterpret_cast<Weak*>(a)),0x796b58);if(!ui)continue;
   P type=resolve(b,reinterpret_cast<Weak*>(ui+0xf0));
   if(type&&equal(at<const char*>(type,8),"PowerupTacticalCuke")){target=ui;break;}
  }
 }
 if(!target||!click(b,app,board,target,event))return;
 // Restore the selected preview to the last hover position, not the hotkey's UI card.
 P cursor=at<P>(board,0x94c);
 if(cursor&&event->px>=0&&event->py>=0){
  Touch t;for(U i=0;i<sizeof(t)/4;++i)reinterpret_cast<U*>(&t)[i]=reinterpret_cast<U*>(event)[i];
  t.x=event->px;t.y=event->py;call<void>(b,0x1327d0c,driver,&t);
  int pos[2]={t.x-at<int>(board,0x2c),t.y-at<int>(board,0x30)};
  call<void>(b,0x1efccc,cursor,pos);
 }
}
