"""Real ARM local raid scheduling, saved defense, journal and economy isolation.

Board rendering/spawning is an explicit engine boundary here. The separate
check_pvp_playback_native.py executes original frame dispatch instructions.
Neither check substitutes for the WSA acceptance test.
"""
import importlib,json,struct,sys
from check_offline_pvp_v76_focused import Definitions

def check_raids(c):
 from check_offline_pvp_v81_arm import GarrisonEngine
 from check_offline_pvp_v60_arm import board,result,return_map
 from check_offline_pvp_v56_arm import BOARD
 from check_offline_pvp_arm import BASE,M,PM,GM,END
 from check_offline_pvp_v93_focused import key
 from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_R0
 class Raid(GarrisonEngine):
  def __init__(self):
   super().__init__();self.fail_eco=False;table=self.alloc(0x140);self.put(table+0x12c,END+0x900);self.put(M+0x7000,table)
  def hook(self,em,a,size,d):
   if a==BASE+0x105b774:
    em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR));return
   if a==BASE+0x1485d4 and self.fail_eco and self.fds[em.reg_read(UC_ARM_REG_R0)][0].endswith('.eco.tmp'):
    em.reg_write(UC_ARM_REG_R0,0xffffffff);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR));return
   if a==END+0x900:
    em.reg_write(UC_ARM_REG_R0,0);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR));return
   return super().hook(em,a,size,d)
  def job(self):return next((bytes(v) for k,v in self.files.items() if k.endswith('.raid')),None)
  def history(self):
   raw=self.files[key(self)];n=struct.unpack_from('<I',raw,464)[0]
   return [struct.unpack_from('<6I',raw,468+24*i) for i in range(n)]
  def idle(self):
   self.reset_map();self.put(M+0x7000+0x1218,0);self.put(M+0x7000+0x139c,0);self.put(M+0x7000+0x1378,0)
  def tick(self):self.run('offlineTrainingTick',self.get(M+0x20))
 def fixture(saved_home=True):
  e=Raid();e.enter();e.run('offlineGarden')
  if saved_home:e.own();e.arrangement(2,2,3);e.save();e.request(3)
  e.idle();e.train();e.advance(31);e.tick()
  return e
 def attack(e):
  e.idle();p=e.residents()[0];target=e.get(p);e.selected(p);e.stub(0x1042fe8,M,0,1,0);board(e)
  e.run(0x1030a50,M+0x14300,e.held());e.deaths(0);result(e,0,target);return_map(e);e.idle();return target
 e=fixture();home=next(k for k in e.files if k.endswith('.def'));saved_home=bytes(e.files[home]);target=attack(e)
 assert e.job() and struct.unpack_from('<II',e.job(),32)==(1,0)
 pending={k:bytes(v) for k,v in e.files.items()};before_load=len(e.loads)
 e.tick();assert len(e.loads)==before_load,'retaliation ignored its due time'
 e.advance(31);e.tick();assert len(e.loads)==before_load+1 and e.plants()==struct.pack('<III',2,2,3)
 # Bank setup must use the NPC's own ten units even if the player has one.
 board(e);first,last=e.get(M+0xd4),e.get(M+0xd8);assert last-first==8 and e.get(first+4)==10
 funds=(e.get(M+4),e.get(M+8),e.gems,e.held());before=e.history();result(e,2,target)
 assert e.history()[0][2:]==(target,2,0,3) and e.history()[1:]==before
 assert (e.get(M+4),e.get(M+8),e.gems,e.held())==funds
 assert bytes(e.files[home])==saved_home and e.scenes[-1]==25
 ui=e.alloc(0x100);e.run('offlineHistoryLoad',ui);e.run('offlineHistoryLookup',e.history()[0][0],0x4c4f434c);brief=e.u.reg_read(UC_ARM_REG_R0)
 assert brief and [e.get(brief+o) for o in (0x90,0x94,0xa0,0xa8,0xb4)]==[0,1,target,2,0]
 assert e.get(e.get(M+0xd4)+4)==e.held(),'NPC bank did not restore the player army'
 finished=e.history();result(e,2,target);assert e.history()==finished
 # A process ending after the job's outcome was saved but before its economy
 # marker was cleared cannot append the same defense again on reopening.
 r=Raid();r.copy_state(e);r.enter();r.idle();r.tick();assert r.history()==finished
 r.advance(40);loads=len(r.loads);r.tick();assert len(r.loads)==loads
 # Restart a queued raid, then fail its result write: neither wallet nor
 # journal changes until a successful retry. Retry records one outcome only.
 f=Raid();f.files={k:bytearray(v) for k,v in pending.items()};f.enter();f.run('offlineGarden');f.idle();f.advance(100);f.tick();board(f)
 funds=(f.get(M+4),f.get(M+8),f.gems,f.held());old=f.history();f.failwrite=True;result(f,1,target)
 assert f.history()==old and (f.get(M+4),f.get(M+8),f.gems,f.held())==funds
 f.failwrite=False;result(f,1,target);assert len(f.history())==len(old)+1 and f.history()[0][3:]==(1,0,3)
 crash=Raid();crash.files={k:bytearray(v) for k,v in pending.items()};crash.enter();crash.run('offlineGarden');crash.idle();crash.advance(100);crash.tick();board(crash)
 crash.fail_eco=True;result(crash,3,target);assert crash.history()==before and struct.unpack_from('<I',crash.job(),32)[0]==2
 resumed=Raid();resumed.copy_state(crash);resumed.enter();resumed.idle();resumed.tick()
 assert resumed.history()[0][3:]==(3,0,3) and len(resumed.history())==len(before)+1
 saved=resumed.history();resumed.tick();assert resumed.history()==saved
 # Corrupt job files block only retaliation; never replace them or fabricate
 # results. A player with no saved defense also gets no invented formation.
 bad=Raid();bad.files={k:bytearray(v) for k,v in pending.items()};job=next(k for k in bad.files if k.endswith('.raid'));bad.files[job][20]^=1;raw=bytes(bad.files[job]);bad.enter();bad.idle();bad.advance(50);bad.tick()
 assert bytes(bad.files[job])==raw and bad.history()==before
 empty=fixture(False);attack(empty);assert empty.job() is None
 # New profile cannot inherit the previous player's pending retaliation.
 scoped=Raid();scoped.files={k:bytearray(v) for k,v in pending.items()};scoped.put(PM+0x74,43);scoped.enter();scoped.idle();scoped.advance(50);scoped.tick();assert scoped.history()==[] and not scoped.loads
 report=dict(saved_home_only=True,npc_army_separate=True,delayed_and_restart_queue=True,defense_kind_three=True,no_fee_or_reward_or_army_loss=True,formation_file_unchanged=True,failed_write_retry=True,restart_deduplication=True,corrupt_job_preserved=True,player_scope=True,actual_native_combat_requires_wsa=True,runtime_game_verified=False)
 (c.OUT/'v98-raid-checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':
 sys.meta_path.insert(0,Definitions());c=importlib.import_module('check_offline_pvp_v82_arm')
 check_raids(c)
 importlib.import_module('check_offline_pvp_v97_focused').check_tutorial(c)
 importlib.import_module('check_offline_pvp_v93_focused').accepted_legacy_fixtures()
 importlib.import_module('check_offline_pvp_v94_focused').check_history(c)
 old=importlib.import_module('check_offline_pvp_v76_arm');old.check_lifecycle();old.check_defense();old.check_residences()
 c.check_reposition();c.check_scout()
