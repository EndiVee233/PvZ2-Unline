"""Execute original map ownership comparisons, not just the label string."""
from check_offline_pvp_v77_arm import BusinessEngine,OUT,check_businesses
from check_offline_pvp_arm import BASE,M,PM,PROFILE,END
from unicorn.arm_const import *
import json

class OwnershipEngine(BusinessEngine):
 def __init__(self):super().__init__();self.title_branch=None
 def hook(self,em,a,size,d):
  off=a-BASE
  if 0x10445e8<=off<0x1044668 or 0x1012a84<=off<0x1012a9c or 0x101a398<=off<0x101a3c8:return
  if off in (0x1012a9c,0x1011ab4):
   self.title_branch='own' if off==0x1012a9c else 'other'
   em.reg_write(UC_ARM_REG_PC,END);return
  return super().hook(em,a,size,d)
 def title(self,owner):
  self.u.reg_write(UC_ARM_REG_R4,owner);self.u.reg_write(UC_ARM_REG_R5,0)
  self.title_branch=None;self.run(0x1012a84);return self.title_branch
 def click(self,record):
  self.u.reg_write(UC_ARM_REG_R7,record);self.u.reg_write(UC_ARM_REG_R6,self.alloc(0x300))
  self.run(0x101a398);return self.opened[-1]

def check_ownership():
 e=OwnershipEngine();e.enter();e.run('offlineGarden');p=e.shops()[0]
 e.run(0x10445e8,M);identity=e.u.reg_read(UC_ARM_REG_R0);assert identity==42
 assert e.title(0)=='other','unoccupied zero-owner shop labelled as own'
 assert e.click(p)==(3,3,2),'unoccupied shop opened owned-asset panel'
 assert e.get(p+8)==e.get(p+12)==0,'ownership was fabricated to change title'
 assert e.title(identity)=='own' and e.title(777)=='other'
 e.put(p+8,identity);assert e.click(p)==(2,3,2),'future owned shop classification lost'
 # Local profile zero still must not collide with the unoccupied sentinel.
 e.put(PM+0x74,0);e.run(0x10445e8,M);assert e.u.reg_read(UC_ARM_REG_R0)==0x7fffffff
 assert e.title(0)=='other' and e.title(0x7fffffff)=='own'
 e.put(PM+0x74,43);e.run(0x10445e8,M);assert e.u.reg_read(UC_ARM_REG_R0)==43
 assert e.title(42)=='other' and e.title(43)=='own'
 early=OwnershipEngine();early.put(PROFILE+0x75c,1)
 early.run('offlineBusinessIdentity');assert early.u.reg_read(UC_ARM_REG_R0)==0,'tutorial identity overridden'
 report=dict(native_ownership_getter_hook_executed=True,
 native_map_own_vs_other_title_branch_executed=True,
 native_map_kind_three_unoccupied_vs_kind_two_owned_panel_executed=True,
 unoccupied_record_owner_remains_zero=True,profile_zero_and_profile_switch_safe=True,
 early_tutorial_identity_preserved=True,runtime_game_verified=False)
 (OUT/'v78-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
