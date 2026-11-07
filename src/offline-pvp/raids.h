// First local retaliation stage: real Board combat against a saved home line.
// No wallet loss, army consumption, shop ownership change or simulated score.
struct RaidJob {U magic,version,user,token,attacker,seed,kind,due,state,stars,finishedAt,checksum;};
struct RaidRuntime {RaidJob job;U user;bool loaded,blocked,active,settled;P ai,board;Store formation;};
static RaidRuntime* raidRuntime;
extern "C" U offlineRaidsMode(){return 1;}
static U raidHash(const RaidJob&s){const auto*p=reinterpret_cast<const unsigned char*>(&s);U h=2166136261u;for(U i=0;i<44;++i)h=(h^p[i])*16777619u;return h;}
static void raidPath(U user,char*out,bool tmp){
 economyPath(user,out,false);U n=0;while(out[n])++n;n-=4;
 const char*s=tmp?".raid.tmp":".raid";while(*s)out[n++]=*s++;out[n]=0;
}
static bool validRaid(const RaidJob&s,U user){
 const NpcPreset*n=npc(s.attacker);
 return s.magic==0x52445650&&s.version==1&&s.user==user&&s.token&&n&&!n->evil&&s.seed&&s.kind<=7&&s.due&&s.state>=1&&s.state<=2&&s.stars<=3&&(s.state==2?bool(s.finishedAt):!s.stars&&!s.finishedAt)&&s.checksum==raidHash(s);
}
static bool saveRaid(U b,RaidJob&s){
 s.checksum=raidHash(s);if(!validRaid(s,owner(b)))return false;
 char dst[160],tmp[160];raidPath(s.user,dst,false);raidPath(s.user,tmp,true);
 I fd=call<I>(b,0x148448,tmp,0x241,0600);if(fd<0)return false;U done=0;
 while(done<sizeof(s)){I n=call<I>(b,0x1485d4,fd,reinterpret_cast<P>(&s)+done,sizeof(s)-done);if(n<=0)break;done+=U(n);}
 bool ok=done==sizeof(s)&&call<I>(b,0x1485e0,fd)==0;if(call<I>(b,0x147b90,fd))ok=false;
 if(ok)ok=call<I>(b,0x147e6c,tmp,dst)==0;if(!ok)call<I>(b,0x148424,tmp);return ok;
}
static void destroyRaidAi(U b){
 if(!raidRuntime||!raidRuntime->ai)return;P p=raidRuntime->ai;raidRuntime->ai=nullptr;
 call<void>(b,at<U>(at<P>(p,0),0xc)-b,p);
}
static bool ensureRaid(U b){
 if(!regular(b))return false;
 if(!raidRuntime){raidRuntime=call<RaidRuntime*>(b,0x147938,sizeof(RaidRuntime));if(!raidRuntime)return false;*raidRuntime=RaidRuntime{};}
 auto&r=*raidRuntime;U user=owner(b);if(r.loaded&&r.user==user)return !r.blocked;
 destroyRaidAi(b);r=RaidRuntime{};r.user=user;r.loaded=true;
 char file[160];raidPath(user,file,false);I fd=call<I>(b,0x148448,file,0,0);if(fd<0)return true;U done=0;
 while(done<sizeof(r.job)){I n=call<I>(b,0x148460,fd,reinterpret_cast<P>(&r.job)+done,sizeof(r.job)-done);if(n<=0)break;done+=U(n);}
 char tail;I extra=call<I>(b,0x148460,fd,&tail,1);call<I>(b,0x147b90,fd);
 r.blocked=done!=sizeof(r.job)||extra||!validRaid(r.job,user);if(r.blocked)log(b,"raid-file-invalid");return !r.blocked;
}
static bool raidActive(U b){return raidRuntime&&raidRuntime->active&&raidRuntime->user==owner(b);}
static void raidQueue(U b,U target){
 if(!ensureRaid(b)||!ensureEconomy(b,manager(b)))return;auto&r=*raidRuntime;
 if(r.active||(r.job.token&&r.job.token>economyRuntime.state.reserved))return;
 // A genuinely saved, nonempty home is required. Never defend a previous
 // opponent's singleton data or manufacture an unowned line for an empty save.
 if(!readStore(b,r.formation)||!r.formation.positions)return;
 RaidJob next{0x52445650,1,owner(b),economyRuntime.state.sequence,target,activeEncounterSeed,activeEncounterKind,realNow(b)+30,1,0,0,0};
 if(!saveRaid(b,next)){log(b,"raid-queue-write-failed");return;}r.job=next;log(b,"raid-queued",target,next.token);
}
static void raidBindArmy(U b,P m){
 P name=nullptr;narrow(b,reinterpret_cast<P>(&name),"pvp_change");U type[2]{};call<void>(b,0xfb6ef0,type,&name);release(b,name);
 if(!type[1])return;U entries[2]={type[1],10};P first=reinterpret_cast<P>(entries);P vector[3]={first,first+8,first+8};
 starter(b,m,"pvp_change",10,false);call<void>(b,0x10454b0,m,vector);
 deployedUser=0;log(b,"raid-npc-army-bound",type[1],10);
}
static bool settleRaid(U b){
 auto&r=*raidRuntime;if(r.job.state!=2||!ensureEconomy(b,manager(b)))return false;
 if(economyRuntime.state.reserved>=r.job.token){r.settled=true;return true;}
 Economy next=economyRuntime.state;if(next.sequence==0xffffffffu)return false;
 U id=activeEncounterId,seed=activeEncounterSeed,kind=activeEncounterKind;
 activeEncounterId=r.job.attacker;activeEncounterSeed=r.job.seed;activeEncounterKind=r.job.kind;
 appendHistory(b,next,r.job.attacker,r.job.stars,0);next.history[0].kind=3;next.history[0].time=r.job.finishedAt;
 activeEncounterId=id;activeEncounterSeed=seed;activeEncounterKind=kind;
 next.reserved=r.job.token;++next.sequence;
 if(!saveEconomy(b,next)){log(b,"raid-history-write-failed");return false;}
 economyRuntime.state=next;r.settled=true;log(b,"raid-defense-recorded",r.job.stars,next.sequence);return true;
}
static U raidResult(U b,U stars){
 if(!raidActive(b))return 0;auto&r=*raidRuntime;if(stars>3)return 1;
 if(r.job.state==1){RaidJob next=r.job;next.state=2;next.stars=stars;next.finishedAt=realNow(b);
  if(!saveRaid(b,next)){log(b,"raid-result-write-failed");return 1;}r.job=next;}
 settleRaid(b);return 1;
}
static void raidEnded(U b){
 auto&r=*raidRuntime;destroyRaidAi(b);r.active=false;r.board=nullptr;
 P m=manager(b);applyEconomy(b,m);bindBattleArmy(b,m);
 at<unsigned char>(m,0x17c)=0;resultSaved=resultAck=exitAck=false;
}
static void raidTick(U b){
 if(!ensureRaid(b)||!ensureEconomy(b,manager(b)))return;auto&r=*raidRuntime;
 if(r.job.state==2&&!r.settled)settleRaid(b);
 if(r.active){
  if(r.settled){finishArenaBoard(b);raidEnded(b);scene(b,25);log(b,"raid-returned-to-map");}
  return;
 }
 if(!r.job.token||r.job.token<=economyRuntime.state.reserved||r.job.state!=1||realNow(b)<r.job.due)return;
 P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0),g=at<P>(reinterpret_cast<P>(b),0x1835eec);
 if(at<U>(g,0x984)!=25||resultSaved||at<P>(app,0x139c)||at<U>(app,0x1218)!=0)return;
 if(call<I>(b,at<U>(at<P>(app,0),0x12c)-b,app,1))return;
 if(!readStore(b,r.formation)||!r.formation.positions)return;
 r.active=true;r.settled=false;r.board=nullptr;P m=manager(b);
 arenaNpc=r.job.attacker;arenaUser=owner(b);at<U>(m,0xa8)=1;at<U>(m,0xf4)=at<U>(m,0x104)=arenaNpc;
 at<U>(m,0x108)=at<U>(m,0x10c)=0;at<unsigned char>(m,0x100)=at<unsigned char>(m,0x102)=at<unsigned char>(m,0x103)=0;
 apply(b,m+0x80,r.formation);loadArena(b,m,"arena_battle_test",0);log(b,"raid-started",arenaNpc,r.formation.positions);
}
extern "C" void offlineRaidFrame(U b,P recorder){
 if(!raidActive(b))return;auto&r=*raidRuntime;if(recorder==r.ai||r.job.state!=1)return;
 P app=at<P>(at<P>(reinterpret_cast<P>(b),0x1821674),0),board=at<P>(app,0x6bc);
 if(!board||!armyBankModule||armyBankBoard!=board||!arenaModule(b)||at<U>(board,0xc0)!=5||at<unsigned char>(board,0x8d5))return;
 if(!r.ai){
  r.board=board;r.ai=call<P>(b,0x10347d8);if(!r.ai)return;
  // Use the original record append code to construct owned PFrames/triggers.
  at<U>(r.ai,0x1c)=1;
  for(U i=0;i<10;++i){P event=call<P>(b,0x14c1a7d,0x18);call<void>(b,0x10338e4,event);
   P old=at<P>(event,8);P name=nullptr;narrow(b,reinterpret_cast<P>(&name),"pvp_change");at<P>(event,8)=name;release(b,old);
   at<U>(event,12)=8;at<U>(event,16)=i%5;at<unsigned char>(event,20)=0;
   at<U>(r.ai,0x14)=1000+i*1500;at<U>(r.ai,0x18)=0xffffffffu;call<void>(b,0x103585c,r.ai,event);
  }
  at<U>(r.ai,0x10)=360000;call<void>(b,0x1034980,r.ai);
  P objects=call<P>(b,0x11d74b4);
  for(U o=0x40;o<=0x50;o+=0x10){P bank=call<P>(b,0x1da034,objects,armyBankModule+o);if(bank)call<void>(b,0x103d178,nullptr,bank,0);}
  log(b,"raid-native-timeline-ready",10,r.formation.positions);
 }
 if(r.board!=board)return;
 call<void>(b,0x10347f8,r.ai);
 if(call<U>(b,0x1034a10,r.ai)){P module=arenaModule(b);if(module)raidResult(b,at<U>(module,0x78));}
}
