"""First-defense tutorial isolation and scoped offline heartbeat/teardown."""
import sys,importlib,json,struct
from check_offline_pvp_v76_focused import Definitions

def check_tutorial(c):
 from check_offline_pvp_v81_arm import GarrisonEngine
 from check_offline_pvp_arm import BASE,M,PM,PROFILE
 from check_offline_pvp_v56_arm import BOARD
 from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_PC,UC_ARM_REG_LR
 class Tutorial(GarrisonEngine):
  def __init__(self):super().__init__();self.before_load=[]
  def hook(self,em,a,size,d):
   if a==BASE+0x2258d8:
    self.before_load.append((self.get(M+0x88)-self.get(M+0x84),self.get(M+0xa8),self.get(M+0x7000+0x1218)))
    self.put(M+0x7000+0x6bc,BOARD);self.string(BOARD+0xc4,'arena_plant_tutorial');self.put(BOARD+0xc0,5)
    em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
   return super().hook(em,a,size,d)
  def load(self,name='arena_plant_tutorial'):
   n=self.alloc(4);self.string(n,name);self.stub(0x350570,BOARD,n,0xffffffff)
 e=Tutorial();e.enter();e.run('offlineGarden')
 # Leave a real generated NPC roster in the singleton, then change to an
 # early-stage player without resetting the native manager (the reported path).
 row=e.residents()[0];e.selected(row);e.stub(0x1042fe8,M,0,4,0)
 assert e.get(M+0x88)>e.get(M+0x84)
 e.put(PM+0x74,43);e.put(PROFILE+0x75c,2);e.put(M+0x7000+0x1218,3)
 temporary=e.alloc(0x40);e.put(M+0x20,temporary);e.enter()
 saved={k:bytes(v) for k,v in e.files.items()};e.load()
 assert e.before_load[-1]==(0,1,3),'tutorial inherited scout plants, target or wrong mode'
 assert e.get(M+0x20)==temporary and e.get(PROFILE+0x75c)==2
 assert e.get(M+0xf4)==e.get(M+0x104)==0 and bytes(e.u.mem_read(M+0x100,4))==bytes(4)
 info=e.get(M+0x90);assert e.get(M+0x94)-info==16 and e.get(info)==2 and e.get(info+4)==1
 # Ten periodic pings execute the installed request hook, without a socket.
 for n in range(10):
  e.advance(3);e.put(M+0x5000+0x18,n+1200);e.stub(0x104305c,M,1)
  assert e.get(M+0x7000+0x185c)==n+1200
 # Placing the lesson's five peas is retained; pings never clear the board.
 pos=e.alloc(60);e.u.mem_write(pos,b''.join(struct.pack('<III',2,row,0) for row in range(5)))
 e.put(M+0x84,pos);e.put(M+0x88,pos+60);e.put(M+0x8c,pos+60)
 e.stub(0x104305c,M,1);assert e.get(M+0x88)-e.get(M+0x84)==60
 # Teardown can arrive after Board has detached; acknowledge once without
 # manually advancing the original tutorial or fabricating a saved defense.
 e.put(M+0x7000+0x6bc,0);e.stub(0x104305c,M,3)
 assert e.get(PROFILE+0x75c)==2 and {k:bytes(v) for k,v in e.files.items()}==saved
 # The special treatment is level+stage scoped, not a generic board clear.
 for step,name in [(9,'arena_plant_tutorial'),(2,'egypt1')]:
  f=Tutorial();f.enter();f.arrangement(34,2,2);before=bytes(f.u.mem_read(f.get(M+0x84),12))
  f.put(PROFILE+0x75c,step);f.put(M+0x7000+0x1218,3);f.load(name)
  assert f.get(M+0x88)-f.get(M+0x84)==12 and bytes(f.u.mem_read(f.get(M+0x84),12))==before
 # Old-player teardown is consumed without touching the newly selected player.
 x=Tutorial();x.enter();x.put(PROFILE+0x75c,2);x.load();x.put(PM+0x74,99);x.stub(0x104305c,M,3)
 report=dict(actual_board_load_hook=True,previous_scout_formation_cleared=True,pea_tier_one_info_only=True,original_mode3_and_stage_preserved=True,temporary_tutorial_army_preserved=True,ten_heartbeats_no_server=True,five_new_peas_not_cleared=True,detached_and_old_player_teardown_safe=True,other_stage_and_levels_unchanged=True,no_wallet_or_defense_file_written=True,native_tutorial_progression_requires_runtime_test=True,runtime_game_verified=False)
 (c.OUT/'v97-tutorial-checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':
 sys.meta_path.insert(0,Definitions());c=importlib.import_module('check_offline_pvp_v82_arm');check_tutorial(c)
 p=importlib.import_module('check_offline_pvp_v93_focused');p.accepted_legacy_fixtures()
 old=importlib.import_module('check_offline_pvp_v76_arm');old.check_lifecycle();old.check_defense();old.check_residences()
 importlib.import_module('check_offline_pvp_v94_focused').check_history(c)
 c.check_reposition();c.check_scout()
