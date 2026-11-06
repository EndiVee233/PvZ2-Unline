// Keep the accepted home .def layout untouched. Each shop uses a validated,
// per-player envelope so neither another shop nor another player can load it.
struct GarrisonStore {U magic,version,user,target,checksum;Store formation;};
static U garrisonHash(const GarrisonStore&s){
 const unsigned char*p=reinterpret_cast<const unsigned char*>(&s);U h=2166136261u;
 for(U i=0;i<sizeof(s);++i)if(i<16||i>=20)h=(h^p[i])*16777619u;return h;
}
static void garrisonPath(U user,U target,char*out,bool tmp){
 char home[160];path(user,home);U n=0;while(home[n]){out[n]=home[n];++n;}
 // Replace only the fixed .def extension, retaining the player's full key.
 n-=4;const char*prefix="-shop-";while(*prefix)out[n++]=*prefix++;
 const char*digits="0123456789abcdef";
 for(I i=7;i>=0;--i)out[n++]=digits[(target>>(i*4))&15];
 const char*s=tmp?".def.tmp":".def";while(*s)out[n++]=*s++;out[n]=0;
}
static bool validGarrison(const GarrisonStore&s,U user,U target){
 return s.magic==0x47445650&&s.version==1&&s.user==user&&s.target==target&&businessId(target)&&
  s.checksum==garrisonHash(s)&&valid(s.formation,user);
}
static I readGarrison(U b,U target,Store&formation){
 char file[160];garrisonPath(owner(b),target,file,false);
 I fd=call<I>(b,0x148448,file,0,0);if(fd<0)return 0;
 GarrisonStore saved{};U done=0;
 while(done<sizeof(saved)){I n=call<I>(b,0x148460,fd,reinterpret_cast<P>(&saved)+done,sizeof(saved)-done);if(n<=0)break;done+=U(n);}
 char tail;I extra=call<I>(b,0x148460,fd,&tail,1);call<I>(b,0x147b90,fd);
 if(done!=sizeof(saved)||extra!=0||!validGarrison(saved,owner(b),target))return -1;
 formation=saved.formation;return 1;
}
static bool writeGarrison(U b,U target,const Store&formation){
 GarrisonStore saved{};saved.magic=0x47445650;saved.version=1;saved.user=owner(b);saved.target=target;
 saved.formation=formation;saved.checksum=garrisonHash(saved);
 if(!validGarrison(saved,owner(b),target))return false;
 char tmp[160],dst[160];garrisonPath(saved.user,target,tmp,true);garrisonPath(saved.user,target,dst,false);
 I fd=call<I>(b,0x148448,tmp,0x241,0600);if(fd<0)return false;
 U done=0;while(done<sizeof(saved)){I n=call<I>(b,0x1485d4,fd,reinterpret_cast<P>(&saved)+done,sizeof(saved)-done);if(n<=0)break;done+=U(n);}
 bool ok=done==sizeof(saved)&&call<I>(b,0x1485e0,fd)==0;
 if(call<I>(b,0x147b90,fd)!=0)ok=false;
 if(ok)ok=call<I>(b,0x147e6c,tmp,dst)==0;
 if(!ok)call<I>(b,0x148424,tmp);return ok;
}
