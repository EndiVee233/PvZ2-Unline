"""Owned-shop editors: isolated files, lifecycle, ownership and failed saves."""
from check_offline_pvp_v80_arm import CaptureEngine,OUT,fixture,check_capture
from check_offline_pvp_v79_arm import check_scout,check_ownership,check_businesses
from check_offline_pvp_v60_arm import board,result,return_map
from check_offline_pvp_arm import M,PM,GM
from check_offline_pvp_v56_arm import BOARD
from unicorn.arm_const import *
import struct,json

class GarrisonEngine(CaptureEngine):
 def edit(self,index):
  ui,_=self.shop_panel(self.shops()[index]);self.put(ui+0xa4,2);self.put(ui+0xc0,M+0x18000)
  before=self.own_loads;self.stub(0x100b3d8,ui,201)
  if self.own_loads>before:
   self.put(M+0x7000+0x6bc,BOARD);self.string(BOARD+0xc4,'arena_plant_test');self.put(BOARD+0xc0,5)
  return self.own_loads-before
 def arrangement(self,plant,row,col):
  p=self.alloc(12);self.u.mem_write(p,struct.pack('<III',plant,row,col));i=self.alloc(16)
  self.u.mem_write(i,struct.pack('<III',plant,1,0));self.string(i+12,'local-defense-signature')
  for o,v in ((4,p),(8,p+12),(12,p+12),(16,i),(20,i+16),(24,i+16)):self.put(M+0x80+o,v)
 def save(self):self.run('offlineSave',0,0,3,2)

def claim(e,index):
 e.attack_shop(index);board(e);e.run(0x1030a50,M+0x14300,e.held());e.deaths(0)
 result(e,3,0x71000001+index);return_map(e);e.reset_map()

def check_garrisons():
 e=GarrisonEngine();e.enter();e.run('offlineGarden')
 # Ownership is acquired via the real local battle/result, not file editing.
 assert e.edit(0)==0 and not any('-shop-' in k for k in e.files)
 for _ in range(3):e.train()
 e.advance(91);e.run('offlineTrainingTick',e.get(M+0x20));claim(e,0);claim(e,1);assert e.owned()==3
 e.own();e.arrangement(2,0,8);e.save();e.request(3)
 home=next(k for k in e.files if k.endswith('.def'));home_bytes=bytes(e.files[home])
 funds=(e.get(M+4),e.get(M+8),e.gems,e.held())
 assert e.edit(0)==1 and e.get(M+0x84)==e.get(M+0x88),'neutral plants leaked into new garrison'
 assert e.get(M+0xa8)==2 and e.get(M+0xf4)==0x71000001
 e.put(M+0x7000+0x6bc,0);e.put(GM+0xa24,6);e.string(GM+0xa40,'arena_plant_test')
 assert e.edit(0)==0,'pending editor request was loaded twice'
 e.put(GM+0xa24,0xffffffff);e.put(M+0x7000+0x6bc,BOARD)
 for _ in range(15):
  e.advance(3);e.put(M+0x5000+0x18,struct.unpack('<I',struct.pack('<f',float(e.now)))[0]);e.request(1)
  assert e.ack()==e.get(M+0x5000+0x18)
 e.arrangement(2,2,3);before=e.own_loads;assert e.edit(0)==0 and e.own_loads==before
 e.save();assert e.scenes[-1]==25 and e.get(BOARD+0xc0)==9;e.request(3)
 one=next(k for k in e.files if k.endswith('-shop-71000001.def'));first=bytes(e.files[one])
 assert bytes(e.files[home])==home_bytes
 assert e.edit(0)==1 and e.plants()==struct.pack('<III',2,2,3)
 e.put(e.get(M+0x84)+4,4);e.request(3);assert e.edit(0)==1
 assert e.plants()==struct.pack('<III',2,2,3),'discarded edit persisted'
 e.request(3);assert e.edit(1)==1 and e.get(M+0x84)==e.get(M+0x88)
 e.arrangement(6,1,6);e.save();e.request(3)
 two=next(k for k in e.files if k.endswith('-shop-71000002.def'))
 assert bytes(e.files[one])==first and bytes(e.files[home])==home_bytes
 assert (e.get(M+4),e.get(M+8),e.gems,e.held())==funds,'editing changed currency or army'
 e.own();assert e.plants()==struct.pack('<III',2,0,8);e.request(3)
 assert e.edit(0)==1;e.arrangement(3,4,5)
 saved={k:bytes(v) for k,v in e.files.items()};e.failwrite=True;scenes=len(e.scenes);e.save()
 assert len(e.scenes)==scenes and e.get(BOARD+0xc0)==5 and {k:bytes(v) for k,v in e.files.items()}==saved
 e.failwrite=False
 # A wrong target or changed player cannot turn a shop save into a home save.
 e.put(M+0xf4,0x71000002);e.save();assert {k:bytes(v) for k,v in e.files.items()}==saved
 e.put(M+0xf4,0x71000001);e.put(PM+0x74,43);e.save()
 assert {k:bytes(v) for k,v in e.files.items()}==saved
 e.put(PM+0x74,42);e.save();e.request(3)
 assert bytes(e.files[one])!=first and bytes(e.files[home])==home_bytes
 r=GarrisonEngine();r.copy_state(e);r.enter();r.run('offlineGarden')
 assert r.edit(0)==1 and r.plants()==struct.pack('<III',3,4,5);r.request(3)
 assert r.edit(1)==1 and r.plants()==struct.pack('<III',6,1,6);r.request(3)
 r.own();assert r.plants()==struct.pack('<III',2,0,8);r.request(3)
 # A valid envelope belonging to shop 2 still cannot be loaded as shop 1.
 original=bytes(r.files[one]);r.files[one]=bytearray(r.files[two]);before=r.own_loads
 assert r.edit(0)==0 and r.own_loads==before and bytes(r.files[one])==bytes(r.files[two])
 r.files[one]=bytearray(original);r.files[one][100]^=1
 assert r.edit(0)==0 and r.own_loads==before,'corrupt garrison silently replaced'
 # Profile zero has a real active-session flag; teardown cannot authorize a save.
 z=GarrisonEngine();z.put(PM+0x74,0);z.enter();z.run('offlineGarden');z.own();z.arrangement(2,0,0)
 z.save();z.request(3);saved={k:bytes(v) for k,v in z.files.items()};z.save()
 assert {k:bytes(v) for k,v in z.files.items()}==saved
 report=dict(owned_native_button_dispatch=True,unowned_edit_rejected=True,
 home_and_two_garrisons_independent=True,new_garrison_empty_not_neutral_defense=True,
 duplicate_editor_entry_preserves_unsaved_edits=True,editor_keepalive_45_seconds=True,
 save_finishes_board_and_returns_map=True,discard_reload_and_restart=True,
 write_failure_keeps_editor_and_prior_file=True,corrupt_or_wrong_shop_envelope_blocks_loading=True,
 wrong_player_or_target_cannot_write_home=True,zero_profile_active_session_guard=True,
 currency_army_and_ownership_unchanged=True,runtime_game_verified=False)
 (OUT/'v81-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
