"""Exercise local evolution costs, queue, native grade handoff and gem finish."""
from check_offline_pvp_v60_arm import BattleEngine as DaveEngine,OUT
from check_offline_pvp_arm import BASE,M,PM,END,PROFILE
from unicorn.arm_const import *
import json,struct

class EvolutionEngine(DaveEngine):
 def __init__(self):
  super().__init__();self.nodes={};self.evolution_prompts=0;self.last_timer=0;self.button_builds=0;self.spawn_grades=[]
 def hook(self,em,a,size,d):
  off=a-BASE;x,y,z,w=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  if 0x108c2b4<=off<0x108c3dc:return # native PvP bank spawn reads the real grade
  if off in (0x107eb28,0x1080e28):return # actual installed trampolines
  if off==0x104673c:result=self.nodes.get(self.txt(self.get(y)),0)
  elif off==0x1048f44:
   key=self.txt(self.get(y));node=self.nodes.get(key)
   if node is None:node=self.alloc(20);self.nodes[key]=node
   em.mem_write(node,bytes(em.mem_read(y,20)));result=node
  elif off==0x107eb2c:
   assert bytes(em.mem_read(x+0xbc,1))==b'\0','cash branch remained enabled'
   self.button_builds+=1
   if self.grade(self.txt(self.get(x+0xa8)))<4:
    button=self.make_button();self.put(x+0xc0,button);self.put(x+0xc4,0)
   sp=em.reg_read(UC_ARM_REG_SP)
   for i,r in enumerate((UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_PC)):em.reg_write(r,self.get(sp+4*i))
   em.reg_write(UC_ARM_REG_SP,sp+36);return
  elif off==0x108737c and self.get(y+4)==BASE+0x1080e28:
   self.put(x+0x1fc,self.get(y+4));self.last_timer=x;self.evolution_prompts+=1;result=0
  elif off==0xb8291c:result=x+0x10
  elif off==0x22bfd0:
   self.spawn_grades.append(self.get(em.reg_read(UC_ARM_REG_SP)+4));result=0
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_R0,result);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)
 def make_button(self):
  button=self.alloc(0x240);vt=self.alloc(0x200)
  self.put(vt+0xa4,BASE+0x1314548);self.put(vt+0x8c,END+0x310);self.put(vt+0x4c,END+0x330);self.put(button,vt);return button
 def evo_ui(self,alias='pvp_change'):
  ui=self.alloc(0xd0);self.string(ui+0xa8,alias);self.run(0x107eb28,ui);return ui
 def click(self,ui):self.stub(0x1080e28,ui,0x1e8d)
 def grade(self,alias='pvp_change'):return self.get(self.nodes[alias]+4) if alias in self.nodes else 1
 def state(self):
  suffix=f'offline-pvp-{self.get(PM+0x74):08x}.eco'
  raw=next(v for k,v in self.files.items() if k.endswith(suffix))
  assert (len(raw),struct.unpack_from('<I',raw,4)[0]) in ((304,4),(332,5),(344,6),(364,7),(400,8))
  return struct.unpack('<76I',raw[:304])
 def queue(self):return self.state()[74:76]

e=EvolutionEngine();e.enter();assert e.grade()==1 and e.queue()==(0,0)
ui=e.evo_ui();before=e.get(M+4);e.click(ui)
assert e.get(M+4)==before-100 and e.queue()==(1,e.now+1800)
assert e.grade()==1 and e.get(M+0x6c)==4 and e.get(M+0x70)==201
button=e.get(ui+0xc0);assert e.labels[button+0xa4]=='3钻石完成(30分)'
e.click(ui);assert e.evolution_prompts==1 and e.get(M+4)==before-100
e.confirm(e.last_timer,0);assert e.grade()==1 and e.queue()[0]==1
e.click(ui);gems=e.gems;e.confirm(e.last_timer)
assert e.grade()==2 and e.gems==gems-3 and e.queue()==(0,0)
e.confirm(e.last_timer);assert e.grade()==2 and e.gems==gems-3,'duplicate confirm charged twice'
e.run('offlineEvolutionTick',ui);assert e.get(M+0x6c)==0
# Execute native bank placement as well: grade2 is forwarded to Board::AddZombie
# rather than displaying a new number only in the evolution window.
seed=e.alloc(0x80);weak=e.alloc(8);type_=e.alloc(0x80);pos=e.alloc(8)
e.string(type_+4,'pvp_change');e.products[weak]=type_;e.put(seed+0x58,999)
e.run(0x108c2b4,seed,weak,pos);assert e.spawn_grades==[2]
e.click(ui);assert e.get(M+4)==before-400 and e.queue()==(1,e.now+3600)
r=EvolutionEngine();r.copy_state(e);r.enter();assert r.grade()==2 and r.queue()==(1,e.now+3600)
r.advance(3600);r.run('offlineTrainingTick',r.get(M+0x20));assert r.grade()==3 and r.queue()==(0,0)
# Clock completion applies once and is saved through a new process.
after=EvolutionEngine();after.now=r.now;after.copy_state(r);after.enter();assert after.grade()==3
after.stub(0x9344a4,after.product(),1) # legitimate already-validated bank completion
ui=after.evo_ui();before=after.get(M+4);after.click(ui)
assert after.get(M+4)==before-900 and after.queue()==(1,after.now+7200)
after.advance(7200);after.run('offlineEvolutionTick',ui);assert after.grade()==4
button=after.get(ui+0xc0);assert after.visible[button]==0 and bytes(after.u.mem_read(button+0x4e,1))==b'\1'
before=after.get(M+4);after.click(ui);assert after.get(M+4)==before and after.grade()==4

# A queued building and evolution cannot overwrite each other's manager timer.
busy=EvolutionEngine();busy.enter();busy.upgrade(1);ui=busy.evo_ui();before=busy.get(M+4);busy.click(ui)
assert busy.queue()==(0,0) and busy.get(M+4)==before and busy.get(M+0x6c)==1
busy2=EvolutionEngine();busy2.enter();ui=busy2.evo_ui();busy2.click(ui);before=busy2.get(M+4);busy2.upgrade(1)
assert busy2.get(M+4)==before and busy2.get(M+0x6c)==4

# Failed transaction and gem debit failures leave the existing queue intact.
failed=EvolutionEngine();failed.enter();ui=failed.evo_ui();before=failed.get(M+4);failed.failwrite=True;failed.click(ui)
assert failed.get(M+4)==before and failed.queue()==(0,0)
failed.failwrite=False;failed.click(ui);failed.click(ui);failed.gems=0;failed.confirm(failed.last_timer)
assert failed.grade()==1 and failed.queue()[0]==1 and failed.gems==0
failed.gems=100;failed.failwrite=True;failed.confirm(failed.last_timer)
assert failed.gems==100 and failed.grade()==1 and failed.queue()[0]==1 and failed.refunds==[3]

# Initialize from the accepted v3 wallet, retaining its army, progression and
# legitimate native grade rather than blindly treating every zombie as level1.
legacy=EvolutionEngine();legacy.enter();key=next(k for k in legacy.files if k.endswith('.eco'));raw=legacy.files[key][:244]
struct.pack_into('<I',raw,4,3);h=2166136261
for i,c in enumerate(raw):
 if not 24<=i<28:h=((h^c)*16777619)&0xffffffff
struct.pack_into('<I',raw,24,h)
migrate=EvolutionEngine();node=migrate.alloc(20);migrate.nodes['pvp_change']=node;migrate.put(node+4,2);migrate.files[key]=raw;migrate.enter()
assert migrate.grade()==2 and migrate.get(M+4)==1000 and migrate.state()[62]==2
# Stale confirmations cannot apply a different queue or owner.
e=EvolutionEngine();e.enter();ui=e.evo_ui();e.click(ui);e.click(ui);timer=e.last_timer
e.put(PM+0x74,43);e.put(M+0x20,0);e.enter();gems=e.gems;e.confirm(timer)
assert e.gems==gems and e.queue()==(0,0)

report=dict(original_costs_and_waits_100_300_900_and_30_60_120_minutes=True,
 grade1_to4_native_records_and_restart=True,natural_completion_once=True,
 shared_building_queue_exclusion=True,gem_button_readable_and_real_confirmation=True,
 gem_cancel_insufficient_write_refund_duplicate_and_stale_owner=True,
 failed_start_no_debit=True,v3_migration_retains_existing_grade=True,
 max_grade_has_no_purchase=True,old_currency_and_army_regressions=True,runtime_game_verified=False)
(OUT/'v63-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
