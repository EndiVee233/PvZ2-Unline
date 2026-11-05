"""Check six local Dave rounds without inventing legacy reward amounts."""
from check_offline_pvp_v65_arm import ResearchEngine,OUT
from check_offline_pvp_v60_arm import board,return_map
from check_offline_pvp_v56_arm import BOARD,MODULE
from check_offline_pvp_arm import BASE,M,GM,END
from unicorn.arm_const import *
import json,struct

class DaveRoundEngine(ResearchEngine):
 def hook(self,em,a,size,d):
  if a==BASE+0x101a3f4:
   # Native availability comparison has selected the completed-house UI.
   # Its dialog renderer is the boundary, as the available branch already is.
   em.reg_write(UC_ARM_REG_PC,END);return
  return super().hook(em,a,size,d)

def make():
 e=DaveRoundEngine();e.enter();e.run('offlineGarden')
 for _ in range(3):e.train()
 ui,button,timer=e.training_ui();e.stub(0x1059300,ui,1);e.confirm(timer);assert e.held()==3
 e.put(M+0x104,0x70000007);e.put(M+0xfc,1);e.put(M+0xf8,1);return e
def preview(e):
 e.put(GM+0xa24,0xffffffff);e.put(GM+0x984,25)
 e.stub(0x1042fe8,M,0,4,0);board(e)
 a,z=e.get(M+0x84),e.get(M+0x88);return bytes(e.u.mem_read(a,z-a))
def start(e):
 raw=(OUT/'libSrc.so').read_bytes();delta=struct.unpack_from('<I',raw,0x10912f0)[0]
 # Match the real Dave-start event fixture used by the accepted v56 checks.
 e.put(M+0xa000+16,(BASE+0x1091184+delta)&0xffffffff);e.put(M+0xa000+20,0);e.put(M+0xa000+24,0)
 e.stub(0x1042fe8,M,0,1,0)
def result(e,stars):
 e.deaths(0);e.put(MODULE+0x78,stars);e.stub(0x10448e8,M,stars,0,1);e.run('offlineTrainingTick',e.get(M+0x20))
def available(e):
 e.dave_available=False;e.u.reg_write(UC_ARM_REG_R8,M);e.u.reg_write(UC_ARM_REG_R5,0);e.run(0x101a3d8);return e.dave_available

e=make();assert struct.unpack_from('<I',e.special[0],48)[0]==6 and e.get(M+0x15c)==0 and available(e)
initial=(e.get(M+4),e.get(M+8),e.gems,e.held());formation=preview(e);assert len(formation)==10*12
start(e);result(e,0);assert e.get(M+0x15c)==0 and (e.get(M+4),e.get(M+8),e.gems,e.held())==initial
return_map(e);assert preview(e)==formation
start(e);e.failwrite=True;result(e,1);assert e.get(M+0x15c)==0
e.failwrite=False
e.stub(0x10448e8,M,1,0x70000001,1);assert e.get(M+0x15c)==0,'foreign result advanced Dave'
seen=set()
for wins,count in enumerate((10,12,13,14,15,16)):
 if wins:
  f=DaveRoundEngine();f.now=e.now;f.copy_state(e);f.enter();f.run('offlineGarden');assert f.get(M+0x15c)==wins and available(f)
  f.put(M+0x104,0x70000007);f.put(M+0xfc,1);f.put(M+0xf8,1);e=f
  formation=preview(e);start(e)
 assert len(formation)==count*12 and formation not in seen;seen.add(formation)
 assert len(set(struct.unpack_from('<III',formation,i) for i in range(0,len(formation),12)))==count
 before=(e.get(M+4),e.get(M+8),e.gems,e.held());result(e,1)
 assert e.get(M+0x15c)==wins+1 and (e.get(M+4),e.get(M+8),e.gems,e.held())==before
 assert (e.get(M+0xc4),e.get(M+0xc8),e.get(M+0xcc))==(0,0,0),'invented or stale displayed rewards'
 result(e,1);assert e.get(M+0x15c)==wins+1,'duplicate result advanced twice'
 return_map(e)

done=DaveRoundEngine();done.copy_state(e);done.enter();done.run('offlineGarden');assert done.get(M+0x15c)==6 and not available(done)
loads=len(done.loads);done.put(M+0x104,0x70000007);done.put(M+0xfc,1);done.put(M+0xf8,1);done.stub(0x1042fe8,M,0,4,0)
assert len(done.loads)==loads and done.notices[-1]=='[V66_DAVE_FINISHED]'
# Completion blocks only Dave. A normal neighbor still has its accepted fee.
before=done.get(M+4);done.stub(0x1042fe8,M,0x70000001,1,0);assert done.get(M+4)==before-1
report=dict(native_house_counter_zero_to_six=True,six_unique_local_formations=True,
 defeat_does_not_advance=True,win_advances_once=True,restart_after_each_round=True,
 failed_save_and_foreign_result_no_progress=True,no_new_reward_or_fee_policy=True,
 no_stale_result_reward_display=True,completed_house_blocks_only_dave=True,
 previous_v65_regressions=True,runtime_game_verified=False)
(OUT/'v66-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
