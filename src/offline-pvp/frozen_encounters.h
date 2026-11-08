// Immutable encounter snapshots: write and fsync before referencing their ID
// in the atomic wallet journal. Failed wallet commits leave harmless orphans;
// existing snapshots are never replaced with different contents.
struct FrozenEncounter {U magic,version,user,lo,hi;NeighborEncounter opponent;};
static U encounterBytes(const NeighborEncounter&e){
#ifdef PVP_GITHUB_PRESETS
 if(e.kind!=SHARED_NEIGHBOR)return LEGACY_ENCOUNTER_BYTES;
#endif
 return sizeof(e);
}
static void encounterId(const NeighborEncounter&e,U&lo,U&hi){
 lo=2166136261u;hi=0x9e3779b9;const auto*p=reinterpret_cast<const unsigned char*>(&e);
 for(U i=0;i<encounterBytes(e);++i){lo=(lo^p[i])*16777619u;hi=(hi<<5)|(hi>>27);hi=(hi^p[i])*0x85ebca6bu;}
 if(!lo&&!hi)hi=1;
}
static void frozenPath(U user,U lo,U hi,char*out,bool temporary){
 economyPath(user,out,false);U n=0;while(out[n])++n;n-=4;const char*prefix="-enc-";
 while(*prefix)out[n++]=*prefix++;const char*digits="0123456789abcdef";
 for(U part=0;part<2;++part)for(I bit=7;bit>=0;--bit)out[n++]=digits[((part?lo:hi)>>(4*bit))&15];
 const char*s=temporary?".npc.tmp":".npc";while(*s)out[n++]=*s++;out[n]=0;
}
static I readFrozen(U b,U lo,U hi,NeighborEncounter&out){
 if(!lo&&!hi)return 0;char file[160];frozenPath(owner(b),lo,hi,file,false);
 I fd=call<I>(b,0x148448,file,0,0);if(fd<0)return 0;FrozenEncounter value{};U done=0;
 while(done<sizeof(value)){I n=call<I>(b,0x148460,fd,reinterpret_cast<P>(&value)+done,sizeof(value)-done);if(n<=0)break;done+=U(n);}
 char tail;I extra=call<I>(b,0x148460,fd,&tail,1);call<I>(b,0x147b90,fd);U a=0,c=0;encounterId(value.opponent,a,c);
 if(done!=20+encounterBytes(value.opponent)||extra||value.magic!=0x46455650||value.version!=1||value.user!=owner(b)||value.lo!=lo||value.hi!=hi||a!=lo||c!=hi||!validEncounter(value.opponent,value.opponent.id))return -1;
 out=value.opponent;return 1;
}
static bool freezeEncounter(U b,const NeighborEncounter&e,U*id){
 const NpcPreset*n=npc(e.id);if(!n||n->evil||!validEncounter(e,e.id))return false;U lo=0,hi=0;encounterId(e,lo,hi);NeighborEncounter existing{};
 I found=readFrozen(b,lo,hi,existing);if(found<0)return false;
 if(found){const auto*a=reinterpret_cast<const unsigned char*>(&e);const auto*c=reinterpret_cast<const unsigned char*>(&existing);for(U i=0;i<encounterBytes(e);++i)if(a[i]!=c[i])return false;id[0]=lo;id[1]=hi;return true;}
 FrozenEncounter value{0x46455650,1,owner(b),lo,hi,e};char dst[160],tmp[160];frozenPath(owner(b),lo,hi,dst,false);frozenPath(owner(b),lo,hi,tmp,true);
 I fd=call<I>(b,0x148448,tmp,0x241,0600);if(fd<0)return false;U done=0;
 U size=20+encounterBytes(e);
 while(done<size){I n=call<I>(b,0x1485d4,fd,reinterpret_cast<P>(&value)+done,size-done);if(n<=0)break;done+=U(n);}
 bool ok=done==size&&call<I>(b,0x1485e0,fd)==0;if(call<I>(b,0x147b90,fd))ok=false;
 if(ok)ok=call<I>(b,0x147e6c,tmp,dst)==0;if(!ok){call<I>(b,0x148424,tmp);return false;}
 id[0]=lo;id[1]=hi;return true;
}
extern "C" U offlineFreezeEncounter(U b,P opponent,P output){return freezeEncounter(b,*reinterpret_cast<NeighborEncounter*>(opponent),reinterpret_cast<U*>(output));}
