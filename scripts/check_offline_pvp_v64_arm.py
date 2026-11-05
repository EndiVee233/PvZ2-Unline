"""Check lobby-to-skill roster handoff and the actual crashing title call."""
from check_offline_pvp_v63_arm import EvolutionEngine,OUT
from check_offline_pvp_arm import BASE,M,PROFILE
from unicorn.arm_const import *
import json

class SkillLabEngine(EvolutionEngine):
 def __init__(self):
  super().__init__();self.skill_nodes={};self.lab_handoff=[];self.localized_calls=0
 def hook(self,em,a,size,d):
  off=a-BASE;x,y,z,w=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  if off==0x10726e4:return
  if off==0x1046764:result=self.skill_nodes.get(self.txt(self.get(y)),0)
  elif off==0x1048dcc:
   key=self.txt(self.get(y));node=self.skill_nodes.get(key)
   if node is None:node=self.alloc(20);self.skill_nodes[key]=node
   em.mem_write(node,bytes(em.mem_read(y,20)));result=node
  elif off==0x10726e8:
   self.lab_handoff.append((x,y));sp=em.reg_read(UC_ARM_REG_SP)
   for i,r in enumerate((UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R11,UC_ARM_REG_PC)):em.reg_write(r,self.get(sp+4*i))
   em.reg_write(UC_ARM_REG_SP,sp+16);return
  elif off==0xa45450:
   assert self.products.get(y),'null type passed to original title renderer'
   self.localized_calls+=1;self.string(x,'原版技能名称',True);result=x
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_R0,result);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)

e=SkillLabEngine();e.enter();e.skill_nodes.clear();assert not e.skill_nodes
ui=e.alloc(0x100);before=(e.get(M+4),e.get(M+8),e.gems,e.held(),dict(e.files))
e.run(0x10726e4,ui,15)
expected={'pvpskill_zombiefood','pvpskill_aid','pvpskill_invisible','pvpskill_rage'}
assert set(e.skill_nodes)==expected and e.lab_handoff==[(ui,15)]
assert all(e.get(n+4)==1 for n in e.skill_nodes.values())
assert (e.get(M+4),e.get(M+8),e.gems,e.held(),e.files)==before,'opening skill page granted resources or wrote progression'
node=e.skill_nodes['pvpskill_aid'];e.put(node+4,3)
e.run(0x10726e4,ui,15);assert e.get(node+4)==3,'existing research grade reset'
count=len(e.skill_nodes)
for button in (10,11,12,13):e.run(0x10726e4,ui,button)
assert len(e.skill_nodes)==count and e.lab_handoff[-1]==(ui,13)

weak=e.alloc(8);out=e.alloc(4)
# Execute the patched BL at the exact old crash caller. Empty and stale
# references produce an owned empty string; real selections keep localization.
e.products[weak]=0;e.stub(0x1083ab8,out,weak)
assert e.get(e.get(out))==0 and e.localized_calls==0
e.products[weak]=e.alloc(0x80);e.stub(0x1083ab8,out,weak)
assert e.localized_calls==1
early=SkillLabEngine();early.put(PROFILE+0x75c,7);early.run(0x10726e4,ui,15)
assert not early.skill_nodes and early.lab_handoff==[(ui,15)]
report=dict(direct_lobby_entry_populates_four_skill_records=True,existing_research_level_preserved=True,
 no_currency_army_or_progression_awarded=True,original_lab_dispatch_preserved=True,
 actual_crash_caller_empty_weak_guard=True,valid_selection_original_localization=True,
 other_lab_buttons_and_early_tutorial_preserved=True,previous_v63_regressions=True,runtime_game_verified=False)
(OUT/'v64-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
