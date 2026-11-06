// BigMapInfo (+110) describes businesses. BigMapPVPInfo (+128) describes
// residential opponents; the native map gives those cup/name labels and the
// kind-5 scouting/raid panel. Keep their ABI layouts separate.
extern "C" U offlineResidentialMode(){return 1;}
static void removeLocalBusinessRecords(U b,P m){
 P begin=at<P>(m,0x110),end=at<P>(m,0x114);
 if(!begin||end<begin||U(end-begin)>64*256||U(end-begin)%64)return;
 P out=begin;
 for(P p=begin;p<end;p+=64){
  const NpcPreset*n=npc(at<U>(p,0));
  bool local=n&&at<U>(p,48)==n->zone&&at<U>(p,52)==n->position;
  bool own=at<U>(p,0)==owner(b)&&at<U>(p,48)==1&&at<U>(p,52)==2;
  if(local||own){release(b,at<P>(p,16),true);continue;}
  // Move ownership of the native string along with its record. Do not add
  // references or destroy moved-from slots beyond the new vector end.
  if(out!=p)bytes(out,p,64);out+=64;
 }
 at<P>(m,0x114)=out;
}
static void residentialNeighbor(U b,P m,const NpcPreset&n){
#ifdef PVP_RANDOM_NEIGHBORS
 projectDynamicNeighbor(b,m,n);return;
#endif
 // +10 cups shown on the map; +14 cups obtainable; +18 obtainable coins.
 // Ranking was removed and medal/gem/cup rewards were not authorized.
 alignas(8) U record[16]={n.id,0,0,n.level,0,0,100,n.zone,n.position,1,0,0,0,0,1,0};
 char allocator=0;
 call<void>(b,0x14eb451,reinterpret_cast<P>(record)+8,n.name,&allocator);
 call<void>(b,0x104678c,m,record);
 release(b,reinterpret_cast<P>(record[2]),true);
}
