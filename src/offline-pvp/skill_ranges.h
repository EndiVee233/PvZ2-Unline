// Native lawn coordinates are 64 x 76. Use the engine's cell conversion and
// rectangular entity query, rather than approximating a rectangle by a circle.
struct SkillArea {I x,y,w,h;};
static U skillWidth(P props){U cost=props?at<U>(props,0x160):0;return cost==25?4:cost==30?5:3;}
static U skillHeight(P props){U cost=props?at<U>(props,0x160):0;return cost==25||cost==30?4:3;}
static SkillArea skillArea(U b,P point,U w,U h){
 alignas(8) unsigned char entity[24]={};at<float>(entity,0x10)=at<float>(point,0);at<float>(entity,0x14)=at<float>(point,4);
 I col=call<I>(b,0x23bcec,entity),row=call<I>(b,0x23bcd4,entity);
 return {col-I(w/2),row-I(h/2),I(w),I(h)};
}
static bool skillContains(U b,const SkillArea&r,P zombie){
 I col=call<I>(b,0x23bcec,zombie),row=call<I>(b,0x23bcd4,zombie);
 return col>=r.x&&col<r.x+r.w&&row>=r.y&&row<r.y+r.h;
}
static void skillQuery(U b,P out,P point,U w,U h){SkillArea r=skillArea(b,point,w,h);call<void>(b,0xbf518c,out,2,&r);}
extern "C" void offlineFoodTargets(U b,P out,U unused,P point,U radius){skillQuery(b,out,point,3,3);}
extern "C" void offlineRageTargets(U b,P out,U unused,P point,U radius){skillQuery(b,out,point,5,4);}
static U skillZoneContains(U b,P subsystem,P zombie,U offset,U w,U h){
 P first=at<P>(subsystem,offset),end=at<P>(subsystem,offset+4);
 if(end<first||U(end-first)>8*256||U(end-first)%8)return 0;
 P objects=call<P>(b,0x11d74b4);
 for(P p=first;p<end;p+=8){
  P zone=call<P>(b,0x1da034,objects,p);if(!zone)continue;
  float point[2]={at<float>(zone,0x10),at<float>(zone,0x14)-24.0f};
  if(skillContains(b,skillArea(b,reinterpret_cast<P>(point),w,h),zombie))return 1;
 }
 return 0;
}
extern "C" U offlineAidContains(U b,P subsystem,P zombie){return skillZoneContains(b,subsystem,zombie,0x18,4,4);}
extern "C" U offlineFogContains(U b,P subsystem,P zombie){return skillZoneContains(b,subsystem,zombie,0x14,3,3);}
static P cursorSkillProps(U b,P cursor){
 P objects=call<P>(b,0x11d74b4),seed=call<P>(b,0x1da034,objects,cursor+0x30);if(!seed)return nullptr;
 U weak[2]={};call<void>(b,0xb82850,weak,seed);P props=call<P>(b,0x1da034,objects,weak);
 call<void>(b,0x1d9bb4,weak,0,0,0);return props;
}
extern "C" void offlineSkillCursorTargets(U b,P cursor,P out,P point){P props=cursorSkillProps(b,cursor);skillQuery(b,out,point,skillWidth(props),skillHeight(props));}
static U drawingSkillWidth,drawingSkillHeight;
extern "C" void offlineSkillScope(U b,P board,P graphics,I col,I row,P props){
 U priorW=drawingSkillWidth,priorH=drawingSkillHeight;
 drawingSkillWidth=skillWidth(props);drawingSkillHeight=skillHeight(props);
 // Same even-size convention as the original square indicator: two cells
 // before the selected cell and one after it for a width/height of four.
 call<void>(b,0x207088,board,graphics,col,row,drawingSkillWidth);
 drawingSkillWidth=priorW;drawingSkillHeight=priorH;
}
extern "C" void offlineSkillScopeRect(U b,P graphics,P rect){
 if(drawingSkillWidth==5&&drawingSkillHeight==4)at<I>(rect,12)=at<I>(rect,12)*4/5;
 call<void>(b,0x1167128,graphics,rect);
}
