"""Exercise research transactions at actual native click/draw trampolines."""
from check_offline_pvp_v64_arm import SkillLabEngine,OUT
from check_offline_pvp_arm import BASE,M,PM,PROFILE
from unicorn.arm_const import *
import json,struct

NAMES=['pvpskill_aid','pvpskill_invisible','pvpskill_rage','pvpskill_zombiefood']
class ResearchEngine(SkillLabEngine):
 def __init__(self):super().__init__();self.research_prompts=0;self.research_timer=0;self.research_builds=0
 def hook(self,em,a,size,d):
  off=a-BASE;x,y,z,w=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  if off in (0x108531c,0x1083d88):return
  if off==0x1083d8c:
   sp=em.reg_read(UC_ARM_REG_SP)
   for i,r in enumerate((UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_PC)):em.reg_write(r,self.get(sp+4*i))
   em.reg_write(UC_ARM_REG_SP,sp+36);return
  if off==0xfb6ef0 and self.txt(self.get(y)) in NAMES:
   self.put(x,0);self.put(x+4,301+NAMES.index(self.txt(self.get(y))));result=x
  elif off==0x1083754:result=77
  elif off==0x108737c and self.get(y+4)==BASE+0x108531c:
   self.put(x+0x1fc,self.get(y+4));self.research_timer=x;self.research_prompts+=1;result=0
  elif off in (0x10849c0,0x1084a38):
   if off==0x1084a38:self.put(x+0xc4,self.skill_nodes[NAMES[y]])
   self.put(x+0xac,self.make_button());self.put(x+0xb0,0);self.research_builds+=1;result=0
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_R0,result);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)
 def research_ui(self,index=0):
  ui=self.alloc(0xe0);self.put(ui+0xc4,self.skill_nodes[NAMES[index]]);self.put(ui+0xc0,index);self.put(ui+0xac,self.make_button());self.run(0x1083d88,ui,0);return ui
 def click_research(self,ui):self.run(0x108531c,ui,0xfffffffe)
 def research_state(self):
  suffix=f'offline-pvp-{self.get(PM+0x74):08x}.eco';raw=next(v for k,v in self.files.items() if k.endswith(suffix));assert len(raw) in (332,344,364,400,412,416)
  return struct.unpack('<83I',raw[:332])
 def research_queue(self):return self.research_state()[81:83]
 def research_grade(self,index=0):return self.get(self.skill_nodes[NAMES[index]]+4)

for index,cost,seconds in [(0,2000,1800),(1,3000,2700),(2,4000,4000),(3,5000,5000)]:
 e=ResearchEngine();e.enter();e.stub(0x9344a4,e.product(),1);before=e.get(M+4);ui=e.research_ui(index);e.click_research(ui)
 assert e.get(M+4)==before-cost and e.research_queue()==(index+1,e.now+seconds) and e.get(M+0x6c)==7 and e.get(M+0x70)==301+index
 assert e.get(ui+0xb0)==0 and '钻石完成' in e.labels[e.get(ui+0xac)+0xa4]

e=ResearchEngine();e.enter();e.stub(0x9344a4,e.product(),1);ui=e.research_ui();e.click_research(ui)
e.stub(0x1084200,ui);assert e.u.reg_read(UC_ARM_REG_R0)==0 and e.get(M+0x6c)==7
gems=e.gems;e.click_research(ui);e.confirm(e.research_timer,0);assert e.gems==gems and e.research_grade()==1
e.click_research(ui);e.gems=0;e.confirm(e.research_timer);assert e.gems==0 and e.research_queue()[0]==1
e.gems=100;e.failwrite=True;e.confirm(e.research_timer);assert e.gems==100 and e.research_grade()==1 and e.refunds==[3]
e.failwrite=False;e.confirm(e.research_timer);assert e.gems==97 and e.research_grade()==2 and e.research_queue()==(0,0)
e.confirm(e.research_timer);assert e.gems==97 and e.research_grade()==2
e.run(0x1083d88,ui,0);assert e.research_builds>=2

r=ResearchEngine();r.copy_state(e);r.enter();assert r.research_grade()==2
ui=r.research_ui();before=r.get(M+4);r.click_research(ui);assert r.get(M+4)==before and r.notices[-1]=='[V54_BASE_LEVEL_REQUIRED]'
# Reach base5 by the actual accepted building upgrade transactions/timers.
r.stub(0x9344a4,r.product(75000),1)
for _ in range(4):r.upgrade(1);r.advance(604800);r.enter()
assert r.level(1)==5
ui=r.research_ui();before=r.get(M+4);r.click_research(ui);assert r.get(M+4)==before-6000 and r.research_queue()==(1,r.now+7200)
pending=ResearchEngine();pending.now=r.now;pending.copy_state(r);pending.enter();assert pending.research_queue()==r.research_queue() and pending.research_grade()==2
pending.advance(7200);pending.run('offlineTrainingTick',pending.get(M+0x20));assert pending.research_grade()==3 and pending.research_queue()==(0,0)
before=pending.get(M+4);pending.run('offlineTrainingTick',pending.get(M+0x20));assert pending.get(M+4)==before and pending.research_grade()==3
for _ in range(5):pending.upgrade(1);pending.advance(604800);pending.enter()
assert pending.level(1)==10
ui=pending.research_ui();before=pending.get(M+4);pending.click_research(ui);assert pending.get(M+4)==before-18000 and pending.research_queue()==(1,pending.now+28800)
pending.advance(28800);pending.run(0x1083d88,ui,0);assert pending.research_grade()==4
before=pending.get(M+4);pending.click_research(ui);assert pending.get(M+4)==before

busy=ResearchEngine();busy.enter();busy.stub(0x9344a4,busy.product(),1);busy.upgrade(1);ui=busy.research_ui();before=busy.get(M+4);busy.click_research(ui);assert busy.get(M+4)==before and busy.research_queue()==(0,0)
busy2=ResearchEngine();busy2.enter();busy2.stub(0x9344a4,busy2.product(),1);ui=busy2.evo_ui();busy2.click(ui);before=busy2.get(M+4);busy2.click_research(busy2.research_ui());assert busy2.get(M+4)==before and busy2.research_queue()==(0,0)
busy3=ResearchEngine();busy3.enter();busy3.stub(0x9344a4,busy3.product(),1);busy3.click_research(busy3.research_ui());before=busy3.get(M+4);busy3.upgrade(1);busy3.click(busy3.evo_ui());assert busy3.get(M+4)==before and busy3.get(M+0x6c)==7

fail=ResearchEngine();fail.enter();fail.stub(0x9344a4,fail.product(),1);ui=fail.research_ui();before=fail.get(M+4);fail.failwrite=True;fail.click_research(ui);assert fail.get(M+4)==before and fail.research_queue()==(0,0)
# Migrate the accepted v4 prefix without discarding existing native skill levels.
old=ResearchEngine();old.enter();key=next(k for k in old.files if k.endswith('.eco'));raw=old.files[key][:304];struct.pack_into('<I',raw,4,4);h=2166136261
for i,c in enumerate(raw):
 if not 24<=i<28:h=((h^c)*16777619)&0xffffffff
struct.pack_into('<I',raw,24,h)
migrate=ResearchEngine();node=migrate.alloc(20);migrate.string(node,NAMES[0]);migrate.put(node+4,2);migrate.skill_nodes[NAMES[0]]=node;migrate.files[key]=raw;migrate.enter();assert migrate.research_grade()==2 and migrate.get(M+4)==1000
e=ResearchEngine();e.enter();e.stub(0x9344a4,e.product(),1);ui=e.research_ui();e.click_research(ui);e.click_research(ui);timer=e.research_timer;e.put(PM+0x74,43);e.put(M+0x20,0);e.enter();gems=e.gems;e.confirm(timer);assert e.gems==gems and e.research_queue()==(0,0)
other=ResearchEngine();other.enter();ui=other.research_ui();node=other.alloc(20);other.string(node,'pvpskill_bomb');other.put(ui+0xc4,node)
other.stub(0x1084200,ui);assert other.u.reg_read(UC_ARM_REG_R0)==77
other.run('offlineResearchClick',ui,0xfffffffe);assert other.u.reg_read(UC_ARM_REG_R0)==0
other.put(PROFILE+0x75c,7);other.stub(0x1084200,ui);assert other.u.reg_read(UC_ARM_REG_R0)==77

report=dict(four_original_costs_waits_and_base_requirements=True,grade_one_to_four_and_restart=True,
 queue_cold_start_and_natural_completion_once=True,building_evolution_research_mutual_exclusion=True,
 gem_label_cancel_insufficient_save_refund_duplicate_stale_owner=True,failed_start_no_debit=True,
 v4_migration_retains_native_skill_grade=True,max_grade_no_purchase=True,
 actual_click_and_draw_trampolines=True,tutorial_and_other_skill_overlay_preserved=True,previous_v64_regressions=True,runtime_game_verified=False)
(OUT/'v65-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
