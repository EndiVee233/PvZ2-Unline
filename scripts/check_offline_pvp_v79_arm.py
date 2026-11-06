"""Exercise the installed business button, preview, keepalive and free exit."""
from check_offline_pvp_v78_arm import OwnershipEngine,OUT,check_ownership,check_businesses
from check_offline_pvp_v60_arm import board
from check_offline_pvp_arm import BASE,M,PM,GM
from check_offline_pvp_v56_arm import BOARD,MODULE
from unicorn.arm_const import *
import json,struct

class ScoutEngine(OwnershipEngine):
 def __init__(self):super().__init__();self.dismissed=[]
 def hook(self,em,a,size,d):
  if a==BASE+0x100a864:
   self.dismissed.append(em.reg_read(UC_ARM_REG_R0))
   em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
  return super().hook(em,a,size,d)
 def scout_shop(self,index):
  ui,_=self.shop_panel(self.shops()[index]);self.put(ui+0xc0,M+0x18000)
  self.stub(0x100b3d8,ui,205);return ui
 def plants(self):return bytes(self.u.mem_read(self.get(M+0x84),self.get(M+0x88)-self.get(M+0x84)))
 def cancel(self):
  self.stub(0x104305c,M,4);self.run('offlineTrainingTick',self.get(M+0x20))
  assert self.scenes[-1]==25 and self.get(BOARD+0xc0)==9
  self.put(GM+0x984,25);self.put(GM+0xa24,0xffffffff)

def check_scout():
 e=ScoutEngine();e.enter();e.run('offlineGarden');assert e.held()==0
 funds=(e.get(M+4),e.get(M+8),e.gems);saved={k:bytes(v) for k,v in e.files.items()}
 e.scout_shop(0);assert e.dismissed==[M+0x18000] and len(e.loads)==1
 assert bytes(e.u.mem_read(M+0x100,4))==b'\1\0\0\0'
 assert e.get(M+0xa8)==2 and e.get(M+0xf4)==0x71000001
 assert e.plants()==b''.join(struct.pack('<III',2,row,0) for row in range(5))
 # Repeated requests while the native scene is pending must not replace it.
 e.put(GM+0xa24,6);e.string(GM+0xa40,'arena_battle_test')
 e.stub(0x1042fe8,M,0x71000001,3,0);assert len(e.loads)==1
 board(e);positions=e.plants();loads=len(e.loads)
 # Both nonzero-id merchant and zero-id preview attack requests are guarded.
 for id,reason in ((0x71000001,2),(0,1),(0x71000001,4)):
  e.stub(0x1042fe8,M,id,reason,0)
 assert e.starts==e.dave_starts==0 and e.get(MODULE+0xb0)==2 and len(e.loads)==loads and e.plants()==positions
 for _ in range(15):
  e.advance(3);e.put(M+0x5000+0x18,struct.unpack('<I',struct.pack('<f',float(e.now)))[0]);e.stub(0x104305c,M,2)
  assert e.get(MODULE+0x40)==e.get(M+0x5000+0x18)
 e.stub(0x10448e8,M,3,0x71000001,2)
 assert e.windows==0 and (e.get(M+4),e.get(M+8),e.gems)==funds
 e.cancel();assert e.held()==0
 assert {k:bytes(v) for k,v in e.files.items()}==saved,'preview changed wallet/ownership files'
 # Switch shop: terminate old board and install exactly the new five plants.
 e.scout_shop(1);board(e)
 assert e.plants()==b''.join(struct.pack('<III',6,row,0) for row in range(5))
 assert e.get(MODULE+0xb0)==2;e.cancel()
 e.scout_shop(0);board(e);assert e.plants()==positions;e.cancel()
 # Returning from a shop must not intercept a later zero-id residential scout.
 e.train();e.advance(31);e.run('offlineTrainingTick',e.get(M+0x20))
 e.selected(e.residents()[0]);before=len(e.loads);e.stub(0x1042fe8,M,0,4,0);board(e)
 assert len(e.loads)==before+1 and e.get(M+0xf4)==0x70000001
 e.cancel()
 e.own();assert e.get(M+0x84)==e.get(M+0x88),'shop formation leaked into own editor'
 assert bytes(e.u.mem_read(M+0x100,4))==bytes(4)
 e.request(3)
 r=ScoutEngine();r.copy_state(e);r.enter();r.run('offlineGarden');r.scout_shop(1);board(r);r.cancel()
 assert len(r.shops())==2 and all(r.get(p+8)==0 for p in r.shops())
 # A stale callback after switching player may not close the old board.
 r.scout_shop(0);board(r);r.put(PM+0x74,43)
 try:r.stub(0x104305c,M,4)
 except AssertionError as ex:assert 'unexpected server call' in str(ex)
 else:raise AssertionError('foreign profile accepted a stale preview')
 report=dict(installed_business_scout_button_executed=True,no_army_required_for_readonly_scout=True,
 independent_local_formations_no_repeated_scene_or_stacking=True,preview_heartbeat_45_seconds=True,
 no_fee_reward_or_ownership_save=True,attack_paths_rejected_without_army=True,
 cancel_finishes_board_and_returns_map=True,shop_to_residence_routing_preserved=True,
 restart_and_player_scope=True,native_render_and_actual_dialog_close_are_runtime_boundaries=True,
 runtime_game_verified=False)
 (OUT/'v79-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
