"""Execute the title formatter through its original map call and local projection."""
from check_offline_pvp_v66_arm import DaveRoundEngine,make,preview,start,result,return_map,OUT
from check_offline_pvp_arm import BASE,M,END
from unicorn.arm_const import *
import json

class LabelEngine(DaveRoundEngine):
 def __init__(self):super().__init__();self.formatted=[]
 def hook(self,em,a,size,d):
  off=a-BASE;x,y,z,w=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  if off==0x100cd40:
   # Both real loads and both formatting calls have executed. Rendering and
   # font measurement after this point are outside this numeric-field check.
   em.reg_write(UC_ARM_REG_SP,em.reg_read(UC_ARM_REG_R11)+4);em.reg_write(UC_ARM_REG_PC,END);return
  if 0x100cc74<=off<0x100d734:return
  if off==0x4edb04:self.put(x,0);self.put(x+4,0);ret=x
  elif off==0xd080f0:self.string(x,'邪恶戴夫 {SON}/{MON}',True);ret=x
  elif off==0xd06a04:self.formatted.append(w);self.string(x,str(w),True);ret=x
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_R0,ret);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)
 def draw_title(self,record):
  self.formatted=[];point=self.alloc(8);self.stub(0x10129f0,0,1,record,point);return self.formatted

e=LabelEngine();e.enter();e.run('offlineGarden');record=e.get(M+0x128)
assert e.draw_title(record)==[0,6]
e.put(record+0x2c,0);e.put(record+0x30,0);assert e.draw_title(record)==[0,6]
# Use an actual successful battle's saved wallet, not an edited player file.
won=make();preview(won);start(won);result(won,1);return_map(won)
r=LabelEngine();r.copy_state(won);r.enter();r.run('offlineGarden');record=r.get(M+0x128)
r.put(record+0x2c,0);r.put(record+0x30,0);assert r.draw_title(record)==[1,6]
before=(r.get(M+4),r.get(M+8),r.gems,r.held(),dict(r.files));assert r.draw_title(record)==[1,6]
assert (r.get(M+4),r.get(M+8),r.gems,r.held(),r.files)==before,'drawing saved or awarded game state'
normal=r.alloc(64);r.put(normal,0x70000001);r.put(normal+0x24,2);r.put(normal+0x2c,12);r.put(normal+0x30,99)
r.run('offlineDaveLabel',normal);assert (r.get(normal+0x2c),r.get(normal+0x30))==(12,99)
report=dict(actual_map_call_and_native_formatter_loads=True,stale_zero_zero_becomes_zero_six=True,
 actual_saved_victory_formats_one_six_after_restart=True,repeated_draw_no_award_or_save=True,
 other_house_records_unchanged=True,previous_v66_regressions=True,runtime_game_verified=False)
(OUT/'v67-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
