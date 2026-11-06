"""Check scoped local-defense keepalive, teardown and formation persistence."""
from check_offline_pvp_v74_arm import ResidenceEngine,OUT,check_residences
from check_offline_pvp_v56_arm import BOARD
from check_offline_pvp_arm import BASE,M,PM,PROFILE
from unicorn.arm_const import *
import struct,json

class DefenseEngine(ResidenceEngine):
 def __init__(self):super().__init__();self.own_loads=0
 def hook(self,em,a,size,d):
  if a==BASE+0x85e7d8:
   self.own_loads+=1
   em.reg_write(UC_ARM_REG_R0,0);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
  if 0x40b134<=a-BASE<=0x40b150:return
  return super().hook(em,a,size,d)
 def own(self):
  self.run('offlineOwn');self.put(M+0x7000+0x6bc,BOARD)
  self.string(BOARD+0xc4,'arena_plant_test');self.put(BOARD+0xc0,5)
 def request(self,action):self.stub(0x104305c,M,action)
 def ack(self):
  self.run(0x40b134,M+0x7000);return self.u.reg_read(UC_ARM_REG_R0)

def check_defense():
 e=DefenseEngine();e.enter();e.run('offlineGarden')
 # Reproduce entry with the previous resident's selected-house/preview state.
 e.put(M+0x104,0x70000002);e.put(M+0xf4,0x70000002)
 e.u.mem_write(M+0x100,b'\1\0\1\1');e.own()
 assert e.own_loads==1 and e.get(M+0xa8)==1
 assert bytes(e.u.mem_read(M+0x100,4))==bytes(4)
 before=(e.get(M+4),e.get(M+8),e.gems,e.held(),dict(e.files))
 # Execute the installed request stub and the original app time getter.
 # Repeated edit keepalives must neither enter the network nor change money.
 for _ in range(15):
  e.advance(3);e.put(M+0x5000+0x18,struct.unpack('<I',struct.pack('<f',float(e.now)))[0]);e.request(1)
  assert e.ack()==e.get(M+0x5000+0x18)
 assert (e.get(M+4),e.get(M+8),e.gems,e.held(),e.files)==before
 # Save an actual native-layout formation using the existing offline serializer.
 p=e.alloc(12);e.u.mem_write(p,struct.pack('<III',2,2,3));i=e.alloc(16)
 e.u.mem_write(i,struct.pack('<III',2,1,0));e.string(i+12,'')
 for o,v in ((4,p),(8,p+12),(12,p+12),(16,i),(20,i+16),(24,i+16)):e.put(M+0x80+o,v)
 e.run('offlineSave',0,0,1,1);assert e.scenes[-1]==25
 saved={k:bytes(v) for k,v in e.files.items()};assert any(k.endswith('.def') for k in saved)
 # Native editor teardown sends action 3 even after the board is detached.
 e.put(M+0x7000+0x6bc,0);e.request(3)
 assert {k:bytes(v) for k,v in e.files.items()}==saved
 e.own();assert e.own_loads==2
 assert bytes(e.u.mem_read(e.get(M+0x84),12))==struct.pack('<III',2,2,3)
 # Unsaved in-memory edits disappear on reentry; teardown must not save them.
 e.put(e.get(M+0x84)+8,5);e.request(3);e.own()
 assert e.get(e.get(M+0x84)+8)==3
 e.request(1);e.request(3)
 r=DefenseEngine();r.copy_state(e);r.enter();r.own()
 assert bytes(r.u.mem_read(r.get(M+0x84),12))==struct.pack('<III',2,2,3)
 # Never acknowledge a previous player's editor session for a different user.
 r.put(PM+0x74,43)
 try:r.request(1)
 except AssertionError as ex:assert 'unexpected server call' in str(ex)
 else:raise AssertionError('foreign owner incorrectly acknowledged')
 report=dict(local_defense_keepalive_45_seconds_no_server=True,native_app_ack_getter_executed=True,
 stale_resident_preview_flags_cleared=True,detached_editor_teardown_no_server=True,
 saved_formation_reload_and_restart=True,unsaved_editor_changes_discarded=True,
 owner_scope_preserved=True,runtime_game_verified=False)
 (OUT/'v75-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))

if __name__=='__main__':
 check_residences();check_defense()
 from check_offline_pvp_v73_arm import check_clock,check_manual_refresh
 check_manual_refresh();check_clock()
 from check_offline_exchange_sampler_arm import check
 check()
