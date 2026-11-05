"""Check roster population and preservation at the original lab dispatcher."""
from check_offline_pvp_v56_arm import DaveEngine,OUT
from check_offline_pvp_arm import BASE,M,PROFILE,END
from unicorn.arm_const import *
import json

class LabEngine(DaveEngine):
 def __init__(self):super().__init__();self.lab_nodes={};self.lab_handoff=[];self.prop_result=0;self.lab_logs=[]
 def hook(self,em,a,size,d):
  off=a-BASE;x,y,z,w=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  if off==0xb82878:return # Execute the installed property-resolver branch.
  if off==0x104673c:result=self.lab_nodes.get(self.txt(self.get(y)),0)
  elif off==0x1048f44:
   key=self.txt(self.get(y));node=self.alloc(20);em.mem_write(node,bytes(em.mem_read(y,20)));self.lab_nodes[key]=node;result=node
  elif off==0x10726e8:
   self.lab_handoff.append((x,y))
   sp=em.reg_read(UC_ARM_REG_SP)
   for i,r in enumerate((UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R11,UC_ARM_REG_PC)):em.reg_write(r,self.get(sp+4*i))
   em.reg_write(UC_ARM_REG_SP,sp+16);return
  elif off==0xb8287c:
   sp=em.reg_read(UC_ARM_REG_SP)
   for i,r in enumerate((UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R11,UC_ARM_REG_PC)):em.reg_write(r,self.get(sp+4*i))
   em.reg_write(UC_ARM_REG_R0,self.prop_result);em.reg_write(UC_ARM_REG_SP,sp+20);return
  elif off==0x147adc:
   fmt=self.txt(z)
   if fmt.startswith('lab-'):self.lab_logs.append((fmt,w))
   result=0
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_R0,result);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)

e=LabEngine();e.enter();balance=e.get(M+4);army=e.held();ui=e.alloc(0x100)
e.stub(0x10726e4,ui,13)
assert e.lab_handoff==[(ui,13)] and set(e.lab_nodes)=={'pvp_change'}
node=e.lab_nodes['pvp_change'];e.put(node+4,3)
e.stub(0x10726e4,ui,13);assert e.get(node+4)==3,'existing native grade was overwritten'
e.stub(0x10726e4,ui,15);assert e.lab_handoff[-1]==(ui,15) and len(e.lab_nodes)==1
assert e.get(M+4)==balance and e.held()==army,'roster granted currency or units'
type_=e.alloc(0x80);props=e.alloc(0x200);e.string(type_+0x1c,'POPANIM_ZOMBIE_TEST')
e.put(props+0x108,0x40050000);e.put(props+0x10c,0x40050024)
e.run('offlineLabProperties',type_,props,BASE+0x107df34)
assert any('rows=%u' in fmt for fmt,_ in e.lab_logs)
e.prop_result=props;e.run(0xb82878,type_)
assert e.u.reg_read(UC_ARM_REG_R0)==props,'property resolver return changed'
e.prop_result=0;e.run(0xb82878,type_);assert e.u.reg_read(UC_ARM_REG_R0)==0
early=LabEngine();early.put(PROFILE+0x75c,7);early.run('offlineLabRoster',ui,13);assert not early.lab_nodes
report=dict(original_dispatch_handoff_and_arguments_preserved=True,unlocked_roster_without_free_units=True,
 existing_native_level_preserved=True,other_lab_buttons_unchanged=True,property_resolver_return_and_null_preserved=True,
 private_diagnostics_only=True,early_tutorial_unchanged=True,runtime_game_verified=False)
(OUT/'v62-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
