"""Shop fees, rewards, three-star ownership, migration and atomic results."""
from check_offline_pvp_v79_arm import ScoutEngine,OUT,check_scout,check_ownership,check_businesses
from check_offline_pvp_v60_arm import board,result,return_map,wallet
from check_offline_pvp_arm import BASE,M,PM,GM,END
from check_offline_pvp_v56_arm import BOARD,MODULE
from unicorn.arm_const import *
import struct,json

class CaptureEngine(ScoutEngine):
 def hook(self,em,a,size,d):
  off=a-BASE
  if 0x101a780<=off<0x101a7bc:return
  if off==0x101a7bc:em.reg_write(UC_ARM_REG_PC,END);return
  return super().hook(em,a,size,d)
 def owned(self):
  key=f'offline-pvp-{self.get(PM+0x74):08x}.eco'
  data=next(v for k,v in self.files.items() if k.endswith(key))
  return struct.unpack_from('<I',data,412)[0] if len(data)>=416 else 0
 def attack_shop(self,index=0):
  p=self.shops()[index];ui,_=self.shop_panel(p)
  self.u.reg_write(UC_ARM_REG_R4,p);self.u.reg_write(UC_ARM_REG_R6,ui)
  self.run(0x101a780,M)
 def reset_map(self):self.put(GM+0x984,25);self.put(GM+0xa24,0xffffffff)

def fixture():
 e=CaptureEngine();e.enter();e.run('offlineGarden')
 for _ in range(3):e.train()
 e.advance(91);e.run('offlineTrainingTick',e.get(M+0x20));assert e.held()==3
 return e

def check_capture():
 # Read-only scout remains free even without an army; cannot start combat.
 empty=CaptureEngine();empty.enter();empty.run('offlineGarden');before=empty.get(M+4)
 empty.scout_shop(0);board(empty);empty.stub(0x1042fe8,M,0x71000001,2,0)
 assert empty.get(MODULE+0xb0)==2 and empty.get(M+4)==before;empty.cancel()
 foreign=fixture();foreign.put(foreign.shops()[0]+8,777);before=foreign.get(M+4)
 foreign.stub(0x1042fe8,M,0x71000001,2,0)
 assert foreign.get(M+4)==before and not foreign.loads,'foreign ownership charged before validation'
 for stars,reward in enumerate((0,33,66,100)):
  e=fixture();before=e.get(M+4);e.scout_shop(0);board(e);plants=e.plants();loads=len(e.loads)
  e.stub(0x1042fe8,M,0x71000001,2,0)
  assert e.starts==1 and e.get(M+4)==before-1 and e.get(MODULE+0xb0)==3
  assert e.plants()==plants and len(e.loads)==loads,'scout-to-attack replaced plants'
  e.stub(0x1042fe8,M,0x71000001,2,0);assert e.starts==1 and e.get(M+4)==before-1
  e.run(0x1030a50,M+0x14300,2);e.deaths(0)
  result(e,stars,0x71000001)
  assert e.get(M+4)==before-1+reward and e.get(M+0xc4)==reward
  assert e.owned()==int(stars==3) and e.held()==3
  assert e.get(e.shops()[0]+8)==(42 if stars==3 else 0)
  result(e,stars,0x71000001);assert e.get(M+4)==before-1+reward and e.windows==1
  return_map(e);e.reset_map();assert e.scenes[-1]==25
  r=CaptureEngine();r.copy_state(e);r.enter();r.run('offlineGarden')
  assert r.owned()==int(stars==3) and r.get(M+4)==e.get(M+4) and r.held()==3
  if stars==3:
   assert r.click(r.shops()[0])==(2,3,2)
   before=r.get(M+4);r.stub(0x1042fe8,M,0x71000001,2,0);assert r.get(M+4)==before and not r.loads
   ui,_=r.shop_panel(r.shops()[0]);r.put(ui+0xa4,2)
   for button in (200,201,202):r.stub(0x100b3d8,ui,button)
   assert r.get(M+4)==before,'unfinished own-shop buttons reached a transaction'
 # Actual native big-button request tail starts the same direct battle.
 d=fixture();before=d.get(M+4);d.attack_shop(1);assert d.get(M+4)==before-1
 board(d);assert d.get(MODULE+0xb0)==3 and d.plants()==b''.join(struct.pack('<III',6,row,0) for row in range(5))
 d.run(0x1030a50,M+0x14300,3);d.deaths(0);result(d,0,0x71000002);return_map(d);d.reset_map()
 assert d.get(M+4)==before-1 and d.owned()==0 and d.held()==3
 # Fee reservation refunds only when the bank never started; no phantom claim.
 pending=fixture();before=pending.get(M+4);pending.attack_shop(0)
 r=CaptureEngine();r.copy_state(pending);r.enter();r.run('offlineGarden')
 assert r.get(M+4)==before and r.owned()==0
 board(pending);r=CaptureEngine();r.copy_state(pending);r.enter();assert r.get(M+4)==before-1 and r.owned()==0
 # Failed result writes cannot partially change ownership, army or reward.
 f=fixture();f.attack_shop(0);board(f);before=f.get(M+4)
 f.run(0x1030a50,M+0x14300,2);f.deaths(1);saved={k:bytes(v) for k,v in f.files.items()}
 f.failwrite=True;result(f,3,0x71000001)
 assert f.owned()==0 and f.get(M+4)==before and f.held()==3 and f.windows==0
 assert {k:bytes(v) for k,v in f.files.items()}==saved
 f.failwrite=False;result(f,3,0x71000001)
 assert f.owned()==1 and f.get(M+4)==before+100 and f.held()==2 and f.windows==1
 return_map(f);f.reset_map()
 # The second shop can be captured separately without resetting the first.
 f.attack_shop(1);board(f);f.run(0x1030a50,M+0x14300,2);f.deaths(0)
 result(f,3,0x71000002);return_map(f);f.reset_map();assert f.owned()==3
 f.put(PM+0x74,43);f.put(M+0x20,0);f.enter();f.run('offlineGarden')
 assert f.owned()==0 and all(f.get(p+8)==0 for p in f.shops()),'ownership leaked across profiles'
 # Real v9 serialized layout: checksum only its 412 bytes, append zero owner bits.
 legacy=fixture();key=next(k for k in legacy.files if k.endswith('.eco'))
 raw=bytearray(legacy.files[key][:412]);struct.pack_into('<I',raw,4,9);h=2166136261
 for i,c in enumerate(raw):
  if not 24<=i<28:h=((h^c)*16777619)&0xffffffff
 struct.pack_into('<I',raw,24,h);legacy.files[key]=raw
 r=CaptureEngine();r.copy_state(legacy);r.enter();r.run('offlineGarden')
 assert r.get(M+4)==legacy.get(M+4) and r.held()==3 and r.owned()==0
 r.attack_shop(0);board(r);r.run(0x1030a50,M+0x14300,3);r.deaths(0);result(r,0,0x71000001)
 assert len(r.files[key])==416 and struct.unpack_from('<I',r.files[key],4)[0]==10
 report=dict(native_direct_request_tail_and_preview_start=True,
 fee_once_and_free_scout=True,zero_through_three_star_rewards=[0,33,66,100],only_three_stars_occupies=True,
 ownership_reward_army_atomic_and_duplicate_safe=True,live_recall_dead_only_consumption=True,
 zero_deployment_defeat_no_claim=True,pending_refund_started_restart_no_phantom_capture=True,
 independent_shop_ownership_restart_and_profile_isolation=True,legacy_v9_wallet_migration=True,
 owned_shop_unimplemented_actions_guarded=True,runtime_game_verified=False)
 (OUT/'v80-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
