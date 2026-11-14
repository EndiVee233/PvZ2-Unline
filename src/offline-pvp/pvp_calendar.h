// Android local civil time, shared by the weekly visitor and attack counter.
// A backward clock change must not create an extra refresh or cheap attacks.
static bool pvpCivilDay(U b,U&day){
 U now=realNow(b);if(now<86400||now>0x7fffffff)return false;
 P tm=call<P>(b,0x147854,&now);if(!tm)return false;
 I offset=at<I>(tm,0x24);if(offset< -86400||offset>86400)return false;
 day=(now+offset)/86400;return true;
}
static U lastDaveRefreshDay(U day){
 U weekday=(day+4)%7; // Unix epoch was Thursday; Sunday is zero.
 U ago=weekday==1?2:weekday==0||weekday==3||weekday==5?1:0;
 return day>=ago?day-ago:0;
}
static void prepareNeighborAttackDay(U b,Economy&s){
 U day;if(pvpCivilDay(b,day)&&day>s.neighborAttackDay){s.neighborAttackDay=day;s.neighborAttacks=0;}
}
static U neighborAttackFee(U attacks){return attacks<5?10:attacks<10?20:attacks<15?50:100;}
static bool isNeighborAttack(U id){const NpcPreset*n=npc(id);return n&&!n->evil;}
static void countNeighborAttack(U b,Economy&s){
 if(!isNeighborAttack(s.battleNpc))return;
 prepareNeighborAttackDay(b,s);if(s.neighborAttacks<15)++s.neighborAttacks;
}
