#include "neighbor_catalog.h"
struct NeighborPlant {U type,level,row,col;};
struct NeighborEncounter {U id,seed,kind,cups,count;NeighborPlant plants[45];};
static U neighborRandom(U&state){state^=state<<13;state^=state>>17;state^=state<<5;return state;}
static U neighborMix(U value){value^=value>>16;value*=0x7feb352d;value^=value>>15;value*=0x846ca68b;value^=value>>16;return value?value:1;}
static U neighborRemainder(U value,U divisor){
 U remainder=0;for(U bit=32;bit>0;--bit){remainder=(remainder<<1)|((value>>(bit-1))&1);if(remainder>=divisor)remainder-=divisor;}return remainder;
}
static const NeighborPlantSpec* neighborPlant(U id){
 for(U i=0;i<NEIGHBOR_PLANT_COUNT;++i)if(NEIGHBOR_PLANTS[i].id==id)return NEIGHBOR_PLANTS+i;
 return nullptr;
}
static U specialNeighborRoll(U roll){
 roll%=100;if(roll<2)return 1;if(roll<5)return 2;if(roll<8)return 3;if(roll<11)return 4;
 if(roll<13)return 5;if(roll<15)return 6;if(roll<17)return 7;return 0;
}
extern "C" U offlineNeighborRoll(U,U roll){return specialNeighborRoll(roll);}
static void neighborName(U seed,U kind,U*out){
 for(U i=0;i<40;++i)out[i]=0;U used=0;
 if(kind&&kind!=4){for(U i=0;i<39&&NEIGHBOR_SPECIAL_NAMES[kind][i];++i)out[used++]=NEIGHBOR_SPECIAL_NAMES[kind][i];return;}
 const U*first=NEIGHBOR_PREFIXES[neighborMix(seed)%NEIGHBOR_PREFIXES_COUNT];
 for(U i=0;i<39&&first[i];++i)out[used++]=first[i];
 const U*last=kind==4?NEIGHBOR_BOWL_SUFFIX[0]:NEIGHBOR_SUFFIXES[neighborMix(seed^0x62428ab3)%NEIGHBOR_SUFFIXES_COUNT];
 if(kind==4&&used&&out[used-1]==0x7684)out[--used]=0;
 for(U i=0;used<39&&last[i];++i)out[used++]=last[i];
}
static U neighborBudget(U cups){U budget=1000+cups*30;return budget<NEIGHBOR_MAX_SUN?budget:NEIGHBOR_MAX_SUN;}
static U neighborFamily(U kind){return kind==2?2:kind==3?4:kind==4?1:kind==5?8:kind==6?32:kind==7?16:0;}
static U neighborCopies(const NeighborEncounter&e,U type){U count=0;for(U i=0;i<e.count;++i)if(e.plants[i].type==type)++count;return count;}
static U neighborGrade(const NeighborEncounter&e,const NeighborPlantSpec&p,U&rng){
 for(U i=0;i<e.count;++i)if(e.plants[i].type==p.id)return e.plants[i].level;
 U top=1+(e.cups+10)/40;if(top>4)top=4;if(e.kind==2)top=4;
 if(top>p.maxLevel)top=p.maxLevel;
 return top>1&&neighborRandom(rng)%100<30?top-1:top;
}
static const NeighborPlantSpec* neighborChoose(const NeighborEncounter&e,U& rng,U remaining,U role,U maxCost){
 U family=neighborFamily(e.kind);bool prefer=family&&(!e.count||neighborRandom(rng)%100<85);
 for(U pass=0;pass<3;++pass){U sum=0;
  for(U i=0;i<NEIGHBOR_PLANT_COUNT;++i){const auto&p=NEIGHBOR_PLANTS[i];
   if(p.cost>remaining||p.cost>maxCost||neighborCopies(e,p.id)>=10||(pass<2&&p.role!=role)||(pass==0&&prefer&&!(p.flags&family)))continue;
   sum+=p.cost+50;
  }
  if(!sum)continue;U pick=neighborRemainder(neighborRandom(rng),sum);
  for(U i=0;i<NEIGHBOR_PLANT_COUNT;++i){const auto&p=NEIGHBOR_PLANTS[i];
   if(p.cost>remaining||p.cost>maxCost||neighborCopies(e,p.id)>=10||(pass<2&&p.role!=role)||(pass==0&&prefer&&!(p.flags&family)))continue;
   U weight=p.cost+50;if(pick<weight)return &p;pick-=weight;
  }
 }
 return nullptr;
}
static U neighborSpent(const NeighborEncounter&e){U total=0;for(U i=0;i<e.count;++i){const auto*p=neighborPlant(e.plants[i].type);if(p)total+=p->cost;}return total;}
static void generateNeighbor(NeighborEncounter&e,U id,U seed,U forcedKind=0){
 e=NeighborEncounter{};e.id=id;e.seed=seed?seed:1;U rng=neighborMix(e.seed);
 e.kind=forcedKind==8?0:forcedKind?forcedKind:specialNeighborRoll(neighborRandom(rng)%100);
 const NpcPreset*n=npc(id);U zone=n?n->zone:1;
 e.cups=e.kind==1?999:e.kind==2?60+neighborRandom(rng)%121:e.kind==3?40+neighborRandom(rng)%111:e.kind==4?30+neighborRandom(rng)%121:e.kind==5?45+neighborRandom(rng)%106:e.kind==6?35+neighborRandom(rng)%116:e.kind==7?30+neighborRandom(rng)%121:neighborRandom(rng)%121+(zone-1)*10;
 if(e.kind==1){
  const U strong[]={34,314,316,313,7,63};U type=strong[neighborRandom(rng)%6];
  const auto*p=neighborPlant(type);
  for(U row=0;row<5;++row)for(U col=0;col<9;++col)e.plants[e.count++]={type,p->maxLevel,row,col};
  return;
 }
 U budget=neighborBudget(e.cups),spent=0,limit=10+e.cups/5;if(limit>45)limit=45;
 U rotation=neighborRandom(rng)%5,maxCost=100+e.cups*3;if(maxCost>5500)maxCost=5500;
 for(U col=0;col<9&&e.count<limit;++col)for(U r=0;r<5&&e.count<limit;++r){
  U role=0;if(col){U roll=neighborRandom(rng)%100;role=roll<(e.kind==6?60u:20u)?1:roll<40?2:0;}
  const auto*p=neighborChoose(e,rng,budget-spent,role,maxCost);if(!p)continue;
  U grade=neighborGrade(e,*p,rng);e.plants[e.count++]={p->id,grade,(r+rotation)%5,col};spent+=p->cost;
 }
 // A mixed roster must not give every type the same tier. Maintain one tier
 // per species, as required by the native PlayerPlantData representation.
 U first=e.count?e.plants[0].type:0;bool variedType=false,variedTier=false;
 for(U i=0;i<e.count;++i){variedType|=e.plants[i].type!=first;variedTier|=e.plants[i].level!=e.plants[0].level;}
 if(!variedType&&e.count){
  for(U k=0;k<NEIGHBOR_PLANT_COUNT;++k){const auto&p=NEIGHBOR_PLANTS[k];
   if(p.role==0&&p.id!=first&&p.cost<=budget-spent+neighborPlant(first)->cost){
    e.plants[e.count-1].type=p.id;e.plants[e.count-1].level=p.maxLevel>=2?2:1;variedType=true;break;
   }
  }
 }
 if(!variedTier&&variedType)for(U i=e.count;i>0;--i){U type=e.plants[i-1].type;
  if(type==first)continue;const auto*p=neighborPlant(type);if(!p||p->maxLevel<2)continue;
  U grade=e.plants[0].level==1?2:1;
  if(e.kind==2&&e.plants[0].level==4)grade=3;
  for(U k=0;k<e.count;++k)if(e.plants[k].type==type)e.plants[k].level=grade;
  break;
 }
 bool mixed=false;for(U i=1;i<e.count;++i)mixed|=e.plants[i].level!=e.plants[0].level;
 if(!mixed&&variedType){const auto*p=neighborPlant(first);if(p&&p->maxLevel>=2){U grade=e.plants[0].level==1?2:1;for(U i=0;i<e.count;++i)if(e.plants[i].type==first)e.plants[i].level=grade;}}
}
extern "C" void offlineNeighborGenerate(U,P output,U id,U seed,U kind){generateNeighbor(*reinterpret_cast<NeighborEncounter*>(output),id,seed,kind);}
