static constexpr U SHARED_LIMIT=1000;
static constexpr U SHARED_WORDS=44+45*4;
struct SharedCandidate {NeighborEncounter encounter;U appearance;};
static SharedCandidate* sharedCatalog;
static U sharedCount;

static U setSharedCatalog(U b,const U* data,U size){
 if(!data||!size||data[0]>SHARED_LIMIT||size!=1+data[0]*SHARED_WORDS)return 0;
 SharedCandidate* next=nullptr;
 if(data[0]){
  next=call<SharedCandidate*>(b,0x147938,data[0]*sizeof(SharedCandidate));
  if(!next)return 0;
 }
 U accepted=0;
 for(U i=0;i<data[0];++i){
  const U* words=data+1+i*SHARED_WORDS;
  NeighborEncounter entry{};
  entry.seed=words[0];entry.cups=words[1];entry.count=words[2];entry.kind=SHARED_NEIGHBOR;
  if(!entry.seed||entry.count>45)continue;
  for(U j=0;j<40;++j)entry.title[j]=words[3+j];
  U appearance=entry.title[0]?words[43]:0;
  if(appearance>10001)appearance=0;
  for(U j=0;j<entry.count;++j){
   const U* plant=words+44+j*4;
   entry.plants[j]={plant[0],plant[3],plant[1],plant[2]};
  }
  if(!validEncounter(entry,0,false,true))continue;
  bool duplicate=false;
  for(U j=0;j<accepted;++j)if(next[j].encounter.seed==entry.seed)duplicate=true;
  if(!duplicate)next[accepted++]={entry,appearance};
 }
 if(sharedCatalog)call<void>(b,0x147950,sharedCatalog);
 sharedCatalog=next;sharedCount=accepted;
 log(b,"github-preset-pool",accepted,data[0]);
 return accepted+1;
}

static U cupDistance(U a,U b){return a>b?a-b:b-a;}
static void pickSharedNeighbor(const NeighborRoster& roster,NeighborEncounter& out,U id,U seed,U sampled,U exclude){
 U player=economyRuntime.state.cups;
 if(player>500)player=500;
 U radius=cupDistance(player,sampled);
 if(radius<10)radius=10;
 const NeighborEncounter* ordinary=nullptr;
 const NeighborEncounter* special=nullptr;
 U ordinaryCount=0,specialCount=0,rng=neighborMix(seed^0x39d34f31u);
 for(U i=0;i<sharedCount;++i){
  const auto& shared=sharedCatalog[i];
  const auto& candidate=shared.encounter;
  if(candidate.seed==exclude)continue;
  if(shared.appearance){
   if(neighborMix(seed^candidate.seed^0xc6d85325u)%10000>=shared.appearance-1)continue;
  }else if(cupDistance(candidate.cups,player)>radius)continue;
  bool used=false;
  if(candidate.title[0])for(const auto& assigned:roster.entries)
   if(assigned.kind==SHARED_NEIGHBOR&&assigned.seed==candidate.seed){used=true;break;}
  if(used)continue;
  if(shared.appearance){
   if(neighborRemainder(neighborRandom(rng),++specialCount)==0)special=&candidate;
  }else if(neighborRemainder(neighborRandom(rng),++ordinaryCount)==0)ordinary=&candidate;
 }
 const NeighborEncounter* selected=special?special:ordinary;
 if(selected){
  out=*selected;out.id=id;
  if(!out.title[0])neighborName(seed,0,out.title);
 }
}
