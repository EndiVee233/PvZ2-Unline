// Rich neighbors have their own bounded, per-player atomic file. The full
// roster lives on the heap rather than overflowing the reserved native BSS.
static constexpr U NEIGHBOR_SLOT_COUNT=NPC_COUNT-1;
struct NeighborRoster {U magic,version,user,sequence,rng,checksum;NeighborEncounter entries[NEIGHBOR_SLOT_COUNT];};
static NeighborRoster* neighborRoster;
static U neighborRosterUser;
static bool neighborRosterBlocked;
static P neighborPanel;
static U neighborPanelUser;
static U activeEncounterId,activeEncounterSeed,activeEncounterKind;
extern "C" U offlineRandomNeighborsMode(){return 1;}
#ifdef PVP_UNIQUE_NEIGHBORS
extern "C" U offlineUniqueNeighborsMode(){return 1;}
static const NeighborPlantSpec* legacyNeighborPlant(U id){
 for(U i=0;i<NEIGHBOR_LEGACY_PLANT_COUNT;++i)if(NEIGHBOR_LEGACY_PLANTS[i].id==id)return NEIGHBOR_LEGACY_PLANTS+i;
 return nullptr;
}
#endif
static U neighborChecksum(const NeighborRoster&r){
 const auto*p=reinterpret_cast<const unsigned char*>(&r);U hash=2166136261;
 for(U i=0;i<sizeof(r);++i)if(i<20||i>=24)hash=(hash^p[i])*16777619u;
 return hash;
}
static bool validEncounter(const NeighborEncounter&e,U expected,bool legacy=false){
 if(e.id!=expected)return false;
 if(!e.seed){if(e.kind||e.cups||e.count)return false;return true;}
 if(e.kind>7||e.count<5||e.count>45||e.kind==1&&e.cups!=999||e.kind!=1&&e.cups>230||e.kind==2&&e.cups<60||e.kind==3&&e.cups<40)return false;
 U spent=0;bool varied=false;
 for(U i=0;i<e.count;++i){const auto&q=e.plants[i];const auto*p=neighborPlant(q.type);
#ifdef PVP_UNIQUE_NEIGHBORS
  if(legacy)p=legacyNeighborPlant(q.type);
#endif
  if(!p||!q.level||q.level>p->maxLevel||q.row>=5||q.col>=9)return false;
  spent+=p->cost;varied|=q.level!=e.plants[0].level;U copies=1;
  for(U j=0;j<i;++j){const auto&other=e.plants[j];
   if(other.row==q.row&&other.col==q.col)return false;
   if(other.type==q.type){if(other.level!=q.level)return false;++copies;}
  }
  if(e.kind!=1&&copies>10)return false;
  if(e.kind==1&&(q.type!=e.plants[0].type||q.level!=p->maxLevel))return false;
 }
 return e.kind==1?e.count==45:spent<=NEIGHBOR_MAX_SUN&&varied;
}
static bool validRoster(const NeighborRoster&r,U user){
 bool version=r.version==1;
#ifdef PVP_UNIQUE_NEIGHBORS
 version=version||r.version==2;U seen=0;
 if(r.version==2)for(U i=0;i<NEIGHBOR_SLOT_COUNT;++i){U kind=r.entries[i].kind;if(kind<2||kind>7)continue;
  if(seen&(1u<<kind))return false;seen|=1u<<kind;
 }
#endif
 if(r.magic!=0x4e425650||!version||r.user!=user||!r.rng||r.checksum!=neighborChecksum(r))return false;
 U slot=0;for(U i=0;i<NPC_COUNT;++i)if(!NPCS[i].evil){if(slot>=NEIGHBOR_SLOT_COUNT||!validEncounter(r.entries[slot++],NPCS[i].id,r.version==1))return false;}
 return slot==NEIGHBOR_SLOT_COUNT;
}
static void neighborPath(U user,char*out,bool tmp){
 economyPath(user,out,false);U length=0;while(out[length])++length;
 const char*suffix=tmp?".neighbors.tmp":".neighbors";length-=4;
 while(*suffix)out[length++]=*suffix++;out[length]=0;
}
static bool saveRoster(U b,NeighborRoster&r){
 r.checksum=neighborChecksum(r);if(!validRoster(r,r.user))return false;
 char file[160],tmp[160];neighborPath(r.user,file,false);neighborPath(r.user,tmp,true);
 I fd=call<I>(b,0x148448,tmp,0x241,0600);if(fd<0)return false;U done=0;
 while(done<sizeof(r)){I n=call<I>(b,0x1485d4,fd,reinterpret_cast<P>(&r)+done,sizeof(r)-done);if(n<=0)break;done+=U(n);}
 bool ok=done==sizeof(r)&&call<I>(b,0x1485e0,fd)==0;if(call<I>(b,0x147b90,fd))ok=false;
 if(ok)ok=call<I>(b,0x147e6c,tmp,file)==0;if(!ok)call<I>(b,0x148424,tmp);return ok;
}
static I readRoster(U b,NeighborRoster&r,U user){
 char file[160];neighborPath(user,file,false);I fd=call<I>(b,0x148448,file,0,0);if(fd<0)return 0;
 U done=0;while(done<sizeof(r)){I n=call<I>(b,0x148460,fd,reinterpret_cast<P>(&r)+done,sizeof(r)-done);if(n<=0)break;done+=U(n);}
 char tail;I extra=call<I>(b,0x148460,fd,&tail,1);call<I>(b,0x147b90,fd);
 return done==sizeof(r)&&!extra&&validRoster(r,user)?1:-1;
}
static NeighborEncounter* findEncounter(NeighborRoster&r,U id){
 for(U i=0;i<NEIGHBOR_SLOT_COUNT;++i)if(r.entries[i].id==id)return r.entries+i;return nullptr;
}
#ifdef PVP_UNIQUE_NEIGHBORS
static U presentSpecials(const NeighborRoster&r,U exceptId=0){
 U used=0;for(U i=0;i<NEIGHBOR_SLOT_COUNT;++i){const auto&e=r.entries[i];if(e.id!=exceptId&&e.seed&&e.kind>=2&&e.kind<=7)used|=1u<<e.kind;}return used;
}
static U newAreaSpecial(NeighborRoster&r){
 U used=presentSpecials(r),total=0;for(U kind=2;kind<=7;++kind)if(!(used&(1u<<kind)))total+=kind<=4?3:2;
 if(!total)return 1;U pick=neighborRemainder(neighborRandom(r.rng),total);
 for(U kind=2;kind<=7;++kind)if(!(used&(1u<<kind))){U weight=kind<=4?3:2;if(pick<weight)return kind;pick-=weight;}
 return 1;
}
static void migrateNeighborRoster(NeighborRoster&r){
 U seen=0;
 for(U i=0;i<NEIGHBOR_SLOT_COUNT;++i){auto&e=r.entries[i];if(!e.seed)continue;bool banned=false;
  for(U k=0;k<e.count;++k)if(!neighborPlant(e.plants[k].type))banned=true;
  bool duplicate=e.kind>=2&&e.kind<=7&&(seen&(1u<<e.kind));
  if(banned||duplicate){U id=e.id,kind=duplicate?8:e.kind?e.kind:8;generateNeighbor(e,id,neighborRandom(r.rng),kind);}
  if(e.kind>=2&&e.kind<=7)seen|=1u<<e.kind;
 }
 r.version=2;
}
#endif
static void generateRosterNeighbor(NeighborRoster&r,NeighborEncounter&e,U id,U seed,U kind=0){
 generateNeighbor(e,id,seed,kind);
#ifdef PVP_UNIQUE_NEIGHBORS
 if(e.kind>=2&&e.kind<=7&&(presentSpecials(r,id)&(1u<<e.kind)))generateNeighbor(e,id,seed,8);
#endif
}
static bool ensureNeighborRoster(U b,P m){
 if(!regular(b)||!ensureEconomy(b,m))return false;U user=owner(b);
 if(!neighborRoster||neighborRosterUser!=user){
  if(neighborRoster)call<void>(b,0x147950,neighborRoster);
  neighborRoster=reinterpret_cast<NeighborRoster*>(call<P>(b,0x147938,sizeof(NeighborRoster)));
  neighborRosterUser=user;neighborRosterBlocked=false;if(!neighborRoster)return false;
  *neighborRoster=NeighborRoster{};I found=readRoster(b,*neighborRoster,user);
  if(found<0){neighborRosterBlocked=true;economyNotice(b,"[V38_PVP_SAVE_ERROR]");return false;}
  if(!found){auto&r=*neighborRoster;r.magic=0x4e425650;r.version=1;r.user=user;r.rng=neighborMix(user^realNow(b)^0x952a1837);
   U slot=0;for(U i=0;i<NPC_COUNT;++i)if(!NPCS[i].evil)r.entries[slot++].id=NPCS[i].id;
  }
 }
 if(neighborRosterBlocked)return false;
 bool needed=false;
#ifdef PVP_UNIQUE_NEIGHBORS
 needed=neighborRoster->version<2;
#endif
 for(U i=0;i<NEIGHBOR_SLOT_COUNT;++i){const auto&e=neighborRoster->entries[i];const NpcPreset*n=npc(e.id);if(n&&regionOpen(n->zone)&&!e.seed)needed=true;}
 if(!needed)return true;
 auto*next=reinterpret_cast<NeighborRoster*>(call<P>(b,0x147938,sizeof(NeighborRoster)));if(!next)return false;*next=*neighborRoster;
#ifdef PVP_UNIQUE_NEIGHBORS
 if(next->version<2)migrateNeighborRoster(*next);
#endif
 for(U zone=1;zone<=6;++zone){if(!regionOpen(zone))continue;bool newArea=true;
  for(U i=0;i<NEIGHBOR_SLOT_COUNT;++i){const auto&e=next->entries[i];const NpcPreset*n=npc(e.id);if(n&&n->zone==zone&&e.seed)newArea=false;}
  for(U i=0;i<NEIGHBOR_SLOT_COUNT;++i){auto&e=next->entries[i];const NpcPreset*n=npc(e.id);if(!n||n->zone!=zone||e.seed)continue;
   U kind=0;if(zone==1&&n->position==5)kind=1;
   else if(zone>1&&newArea&&n->position==1){
#ifdef PVP_UNIQUE_NEIGHBORS
    kind=newAreaSpecial(*next);
#else
    kind=specialNeighborRoll(neighborRandom(next->rng)%17);
#endif
   }
   U id=e.id;generateRosterNeighbor(*next,e,id,neighborRandom(next->rng),kind);
   if(zone==1&&n->position==5)for(U k=0;k<45;++k){e.plants[k].type=34;e.plants[k].level=neighborPlant(34)->maxLevel;}
  }
 }
 ++next->sequence;bool ok=saveRoster(b,*next);
 if(ok){*neighborRoster=*next;log(b,"neighbors-generated",next->sequence,NEIGHBOR_SLOT_COUNT);}else economyNotice(b,"[V38_PVP_SAVE_ERROR]");
 call<void>(b,0x147950,next);return ok;
}
static const NeighborEncounter* encounter(U b,U id){
 if(!ensureNeighborRoster(b,manager(b)))return nullptr;
 return findEncounter(*neighborRoster,id);
}
static void projectDynamicNeighbor(U b,P m,const NpcPreset&n){
 const auto*e=encounter(b,n.id);if(!e||!e->seed)return;
 U title[40]{};neighborName(e->seed,e->kind,title);
 alignas(8) U record[16]={n.id,0,0,n.level,e->cups,0,100,n.zone,n.position,1,0,0,0,0,1,0};
 char alloc=0;call<void>(b,0x14eb451,reinterpret_cast<P>(record)+8,title,&alloc);
 call<void>(b,0x104678c,m,record);release(b,reinterpret_cast<P>(record[2]),true);
}
extern "C" void offlinePvpPanelReady(U b,P panel){
 offlineRegionPanelReady(b,panel);neighborPanel=nullptr;
 if(panel&&regular(b)&&at<U>(panel,0xa4)==5){neighborPanel=panel;neighborPanelUser=owner(b);}
}
static U neighborAction(U b,P panel,U button){
 if(button!=204||!panel||!regular(b)||at<U>(panel,0xa4)!=5)return 0;
 if(panel!=neighborPanel||neighborPanelUser!=owner(b))return 1;
 const NpcPreset*n=nullptr;
 for(U i=0;i<NPC_COUNT;++i)if(!NPCS[i].evil&&NPCS[i].zone==at<U>(panel,0xac)&&NPCS[i].position==at<U>(panel,0xa8)){n=NPCS+i;break;}
 if(!n||!ensureNeighborRoster(b,manager(b))||!regionOpen(n->zone))return 1;
 P map=at<P>(panel,0xc0);if(!map)return 1;
 auto*next=reinterpret_cast<NeighborRoster*>(call<P>(b,0x147938,sizeof(NeighborRoster)));if(!next)return 1;*next=*neighborRoster;
 auto*entry=findEncounter(*next,n->id);const auto*old=findEncounter(*neighborRoster,n->id);
 generateRosterNeighbor(*next,*entry,n->id,neighborRandom(next->rng));
 U kind=entry->kind;
 for(U attempt=0;attempt<16;++attempt){
  bool sameName=false;if(kind==old->kind&&(kind==0||kind==4)){U a[40]{},c[40]{};neighborName(entry->seed,kind,a);neighborName(old->seed,kind,c);sameName=true;for(U i=0;i<40;++i)if(a[i]!=c[i])sameName=false;}
  if(!sameName&&(kind==1||entry->cups!=old->cups))break;
  generateNeighbor(*entry,n->id,neighborRandom(next->rng),kind?kind:8);
 }
 if(entry->kind==1&&old->kind==1&&entry->plants[0].type==old->plants[0].type){
  U type=old->plants[0].type==34?314:34;
  for(U k=0;k<45;++k){entry->plants[k].type=type;entry->plants[k].level=neighborPlant(type)->maxLevel;}
 }
 ++next->sequence;bool ok=saveRoster(b,*next);
 if(ok){*neighborRoster=*next;projectDynamicNeighbor(b,manager(b),*n);log(b,"neighbor-replaced",n->id,entry->cups);
  U zone=n->zone,pos=n->position;neighborPanel=nullptr;call<void>(b,0x100a864,map);call<void>(b,0x1019668,map,5,zone,pos);
 }else economyNotice(b,"[V38_PVP_SAVE_ERROR]");
 call<void>(b,0x147950,next);return 1;
}
