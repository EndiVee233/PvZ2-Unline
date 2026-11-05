"""Exercise the real native star counter and all three draw-call replacements."""
from check_offline_pvp_v68_arm import NarrativeEngine,OUT
from check_offline_pvp_v66_arm import preview,start,result
from check_offline_pvp_arm import BASE,M,END
from unicorn.arm_const import *
import json,struct,zipfile,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from merge_legacy_pvp_resources import Bundle

class StarEngine(NarrativeEngine):
 def __init__(self):
  super().__init__();self.draws=[];self.star_lookups=0;self.image_available=True;self.resource=self.alloc(0x100);self.lit=self.alloc(0x80);self.original_animations=0
  self.put(BASE+0x183607c,self.resource);self.put(BASE+0x183606c,88);self.put(self.resource+0xe8,12)
 def hook(self,em,a,size,d):
  off=a-BASE;x,y,z,w=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  if off==0x109e438 or 0x109e4a8<=off<0x109e528:return
  if off==0x109e43c:
   self.original_animations+=1;sp=em.reg_read(UC_ARM_REG_SP)
   for i,r in enumerate((UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R11,UC_ARM_REG_PC)):em.reg_write(r,self.get(sp+4*i))
   em.reg_write(UC_ARM_REG_SP,sp+16);return
  if off==0x11c5b5c:ret=41
  elif off==0x11ca888:
   assert x==self.resource and y==41 and self.txt(self.get(z))=='IMAGE_UI_HUD_INGAME_ARENA_STAR_ON'
   assert self.get(self.resource+0xe8)==88;self.star_lookups+=1
   if self.image_available:
    record=self.alloc(0x20);self.put(record+0x18,self.lit);self.put(record+0x1c,0);ret=record
   else:ret=0
   em.reg_write(UC_ARM_REG_R1,0)
  elif off==0x11694c8:self.draws.append((x,y,z,w));ret=0
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_R0,ret);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)
 def draw_slots(self,widget):
  frame=self.alloc(0x100)+0x80;self.put(frame-0x54,widget);self.u.reg_write(UC_ARM_REG_R11,frame);self.draws=[]
  for slot,site in enumerate((0x109e9c0,0x109e9fc,0x109ea30)):
   self.stub(site,0x44440000,0x44441000+slot,50+slot*60,20)
  return [r[1] for r in self.draws]

e=StarEngine();e.setup();preview(e);start(e);widget=e.alloc(0x110)
before=(e.get(M+4),e.get(M+8),e.held(),dict(e.files));old=[0x44441000+i for i in range(3)]
# The native setter takes remaining flags, and has already updated +f0
# before its final animation call. Keep that instruction sequence untouched.
for flags,count in [(5,0),(3,1),(1,2),(0,3)]:
 e.run(0x109e4a8,widget,flags);assert e.get(widget+0xf0)==count and e.get(widget+0xf4)==e.get(widget+0xf8)==0
 assert e.draw_slots(widget)==[e.lit if i<count else old[i] for i in range(3)]
 assert [(r[0],r[2],r[3]) for r in e.draws]==[(0x44440000,50+i*60,20) for i in range(3)]
assert e.star_lookups==1 and e.get(e.resource+0xe8)==12 and e.original_animations==0
assert (e.get(M+4),e.get(M+8),e.held(),e.files)==before,'drawing altered gameplay or persistence'
# A resource not yet available keeps the original image and restores scope.
missing=StarEngine();missing.setup();preview(missing);start(missing);widget=missing.alloc(0x110);missing.put(widget+0xf0,2);missing.image_available=False
assert missing.draw_slots(widget)==old and missing.get(missing.resource+0xe8)==12
missing.image_available=True;assert missing.draw_slots(widget)==[missing.lit,missing.lit,old[2]]
# Outside a local PvP board, retain both the original draw and animation path.
other=StarEngine();other.enter();widget=other.alloc(0x110);other.put(widget+0xf0,2)
assert other.draw_slots(widget)==old
other.run(0x109e438,widget,0);assert other.original_animations==1
# Real result path still reads the same gameplay star count and advances once.
result(e,1);assert e.get(M+0x15c)==1 and e.dialogue()[2]==1

with zipfile.ZipFile('pvz2data.zip') as z:
 bundle=Bundle(z.read('com.popcap.pvz2cthd/files/uicommon.rsb.smf'));manifest=bundle.manifest()[2]
 resources={r['id']:r for g in manifest['groups'] for r in g.get('resources',[])}
 on=resources['IMAGE_UI_HUD_INGAME_ARENA_STAR_ON'];off=resources['IMAGE_UI_HUD_INGAME_ARENA_STAR_OFF']
 assert (on['aw'],on['ah'])==(off['aw'],off['ah'])==(147,141)
 assert on['parent']==off['parent']
report=dict(native_flag_to_star_counter_preserved=True,three_actual_draw_call_stubs=True,
 zero_to_three_lit_slots=True,original_positions_dimensions_and_unearned_images=True,
 retained_broken_animation_not_spawned=True,native_resource_scope_restored_and_image_cached=True,
 missing_resource_falls_back_and_retries=True,other_scenes_keep_original_paths=True,
 no_wallet_army_or_save_changes=True,battle_result_count_unchanged=True,
 original_lit_image_exists_and_matches_dimensions=True,previous_v68_regressions=True,runtime_game_verified=False)
(OUT/'v69-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
