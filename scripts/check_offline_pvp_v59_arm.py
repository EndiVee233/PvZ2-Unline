"""Execute the native menu's rank-button dispatch and disabled factory."""
from pathlib import Path
import struct,sys,json
import check_offline_pvp_arm as core
from unicorn.arm_const import *
core.OUT=Path(sys.argv[1]);BASE=core.BASE;END=core.END
class MenuEngine(core.Engine):
 def __init__(self):
  super().__init__();self.rank_calls=0;self.other_calls=[]
  # Real native stack guard access through the relocated GOT.
  got=(0x107bc3c+self.get(BASE+0x107bfc8))&0xffffffff
  slot=(got+self.get(BASE+0x107bfcc))&0xffffffff
  self.put(BASE+slot,core.M+0x9000);self.put(core.M+0x9000,0x13579bdf)
  scene_slot=(got+self.get(BASE+0x107bfe4))&0xffffffff
  self.put(BASE+scene_slot,core.M+0x9004);self.put(core.M+0x9004,core.GM)
 def hook(self,em,a,size,d):
  off=a-BASE
  if off==0x107bb98:self.rank_calls+=1;return
  if off==0x107bb9c or 0x107bc20<=off<0x107bfec:return
  if off in (0x352b38,0x107ba00):
   self.other_calls.append(off);em.reg_write(UC_ARM_REG_R0,0);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
  return super().hook(em,a,size,d)
e=MenuEngine();ui=e.alloc(0x120)
for _ in range(3):
 e.run(0x107bc20,ui,6)
 assert e.get(ui+0xdc)==6 and e.u.reg_read(UC_ARM_REG_R0)==0
assert e.rank_calls==3 and not e.other_calls
e.run(0x107bb98);assert e.u.reg_read(UC_ARM_REG_R0)==0
for button,expected in [(0,0x352b38),(2,0x107ba00)]:
 e.run(0x107bc20,ui,button);assert e.other_calls[-1]==expected
# Ensure the remainder of the implementation is the v58 native library.
before=(core.ROOT/'work/pvp-v58/libSrc.so').read_bytes();after=(core.OUT/'libSrc.so').read_bytes()
assert len(before)==len(after) and before[:0x107bb98]==after[:0x107bb98] and before[0x107bba0:]==after[0x107bba0:]
result=dict(native_rank_button_dispatch=True,repeated_rank_click_no_window_or_request=True,direct_factory_disabled=True,other_menu_dispatch_preserved=True,only_eight_native_bytes_changed=True,runtime_game_verified=False)
(core.OUT/'v59-arm-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
