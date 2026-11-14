// Native lawn coordinates are 64 x 76. Use the engine's cell conversion and
// rectangular entity query, rather than approximating a rectangle by a circle.
struct SkillArea {I x,y,w,h;};
#ifdef PVP_WEEKLY_RULES
static U skillAidGrade=1,skillFogGrade=1;
// Dimensions are rows x columns: 3x3, 4x3, 4x4, 5x4.
static U growingSkillWidth(U grade){return grade>=3?4:3;}
static U growingSkillHeight(U grade){return grade>=4?5:grade>=2?4:3;}
static U skillWidth(P props){
 U cost=props?at<U>(props,0x160):0;
 return cost==25?growingSkillWidth(skillAidGrade):cost==20?growingSkillWidth(skillFogGrade):cost==30?5:3;
}
static U skillHeight(P props){
 U cost=props?at<U>(props,0x160):0;
 return cost==25?growingSkillHeight(skillAidGrade):cost==20?growingSkillHeight(skillFogGrade):cost==30?4:3;
}
#else
static U skillWidth(P props){U cost=props?at<U>(props,0x160):0;return cost==25?4:cost==30?5:3;}
static U skillHeight(P props){U cost=props?at<U>(props,0x160):0;return cost==25||cost==30?4:3;}
#endif
static SkillArea skillArea(U b,P point,U w,U h){
 alignas(8) unsigned char entity[24]={};at<float>(entity,0x10)=at<float>(point,0);at<float>(entity,0x14)=at<float>(point,4);
 I col=call<I>(b,0x23bcec,entity),row=call<I>(b,0x23bcd4,entity);
 return {col-I(w/2),row-I(h/2),I(w),I(h)};
}
static bool skillContains(U b,const SkillArea&r,P zombie){
 I col=call<I>(b,0x23bcec,zombie),row=call<I>(b,0x23bcd4,zombie);
#ifdef PVP_WEEKLY_RULES
 // Treat the adjacent off-lawn birth band as an extension of column nine.
 // This is not an extra playable/planting column; left and row bounds stay.
 if(col>=9&&col<=10&&r.x<=8&&r.x+r.w>8)col=8;
#endif
 return col>=r.x&&col<r.x+r.w&&row>=r.y&&row<r.y+r.h;
}
static void skillQuery(U b,P out,P point,U w,U h){
 SkillArea r=skillArea(b,point,w,h);
#ifdef PVP_WEEKLY_RULES
 // The native rectangular query uses entity grid bounds. Spawned zombies
 // outside the nine plant columns can be excluded by those bounds.
 // Query the board's same zombie collection, retaining its dead filter, and
 // use world-to-cell coordinates just as the persistent skill zones do.
 P board=call<P>(b,0x20ec10);if(!board)return;
 P list=call<P>(b,0x20a1c0,board);if(!list)return;
 P first=at<P>(list,0),end=at<P>(list,4);
 if(!first||end<first||U(end-first)%4||U(end-first)>4096*4)return;
 for(P p=first;p<end;p+=4){
  P zombie=at<P>(p,0);
  if(!zombie||call<U>(b,0x348944,zombie)||!skillContains(b,r,zombie))continue;
  call<void>(b,0x44a310,out,&zombie);
 }
#else
 call<void>(b,0xbf518c,out,2,&r);
#endif
}
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
extern "C" U offlineAidContains(U b,P subsystem,P zombie){
#ifdef PVP_WEEKLY_RULES
 return skillZoneContains(b,subsystem,zombie,0x18,growingSkillWidth(skillAidGrade),growingSkillHeight(skillAidGrade));
#else
 return skillZoneContains(b,subsystem,zombie,0x18,4,4);
#endif
}
extern "C" U offlineFogContains(U b,P subsystem,P zombie){
#ifdef PVP_WEEKLY_RULES
 return skillZoneContains(b,subsystem,zombie,0x14,growingSkillWidth(skillFogGrade),growingSkillHeight(skillFogGrade));
#else
 return skillZoneContains(b,subsystem,zombie,0x14,3,3);
#endif
}
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
#ifdef PVP_WEEKLY_RULES
 U w=drawingSkillWidth,h=drawingSkillHeight;
 if(w==4&&h==3){I cell=at<I>(rect,12)/4;at<I>(rect,4)+=cell;at<I>(rect,12)=cell*3;}
 if(w==5&&h==4)at<I>(rect,12)=at<I>(rect,12)*4/5;
 if(w==3&&h==4){I cell=at<I>(rect,12)/3;at<I>(rect,4)-=cell;at<I>(rect,12)=cell*4;}
 if(w==4&&h==5)at<I>(rect,12)=at<I>(rect,12)*5/4;
#else
 if(drawingSkillWidth==5&&drawingSkillHeight==4)at<I>(rect,12)=at<I>(rect,12)*4/5;
#endif
 call<void>(b,0x1167128,graphics,rect);
}
