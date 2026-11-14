// Native SkillInfo is live, but each card copies its grade when the page is
// constructed (0x10835e4 -> card+0x1f8). Selecting again only rebuilds the
// detail/button, so a completed upgrade must synchronize the card copy too.
static bool sameText(P text,const char* expected);
static bool syncResearchCardGrades(U b,P ui,P m){
 if(!ui||!m)return false;
 U begin=at<U>(ui,0xb4),end=at<U>(ui,0xb8);
 if(!begin||end<begin||(end-begin)%sizeof(P)||(end-begin)/sizeof(P)>4)return false;
 U selected=at<U>(ui,0xc0),count=(end-begin)/sizeof(P);
 bool selectedChanged=false;
 for(U i=0;i<count;++i){
  P card=at<P>(reinterpret_cast<P>(begin),i*sizeof(P));
  if(!card)continue;
  P name=at<P>(card,0x1fc);
  if(!sameText(name,"pvpskill_aid")&&!sameText(name,"pvpskill_invisible")&&
     !sameText(name,"pvpskill_rage")&&!sameText(name,"pvpskill_zombiefood"))continue;
  P info=call<P>(b,0x1046764,m,card+0x1fc);
  U level=info?at<U>(info,4):0;
  if(level<1||level>4||at<U>(card,0x1f8)==level)continue;
  at<U>(card,0x1f8)=level;
  if(i==selected)selectedChanged=true;
 }
 return selectedChanged;
}
