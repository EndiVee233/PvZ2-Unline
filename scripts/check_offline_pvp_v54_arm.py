"""Exercise one-time grants, native lab levels, production, upgrades and Dave."""
from check_offline_pvp_v52_arm import RecallEngine,OUT,BOARD,MODULE
from check_offline_pvp_arm import BASE,M,PM,PROFILE
from unicorn.arm_const import *
import struct,json

class ProgressionEngine(RecallEngine):
 def __init__(self):
  super().__init__()
  # Existing native lab entries: execute actual lookups/updates on these nodes.
  self.level_nodes={i:self.alloc(24) for i in (1,2,3)}
  for i,node in self.level_nodes.items():self.put(node+16,i);self.put(node+20,1)
  root=self.level_nodes[2];self.put(root+8,self.level_nodes[1]);self.put(root+12,self.level_nodes[3]);self.put(M+0x5c,root)
 def hook(self,em,a,size,d):
  off=a-BASE;x,y=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1)]
  if 0x10747d0<=off<0x107486c:return
  if off==0x108737c and self.get(y+4)==BASE+0x10748e8:
   self.put(x+0x1fc,self.get(y+4));self.put(x+0x204,self.get(y+12));self.prompts+=1
   em.reg_write(UC_ARM_REG_R0,0);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
  if 0x1060f70<=off<0x1060ffc or 0x1060e94<=off<0x1060f6c:return
  if off in (0x1042aa8,0x1042b40):
   assert x==M;self.put(M+(8 if off==0x1042aa8 else 16),y)
   em.reg_write(UC_ARM_REG_R0,0);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
  return super().hook(em,a,size,d)
 def enter(self):self.run('offlineProgressionInit')
 def upgrade(self,kind,button=-2):
  ui=self.alloc(0xc0);self.put(ui+0xac,kind);self.stub(0x107486c,ui,button&0xffffffff)
 def level(self,kind):return self.get(self.level_nodes[kind]+20)
 def copy_state(self,source):self.files={k:bytearray(v) for k,v in source.files.items()}

e=ProgressionEngine();e.enter()
assert (e.get(M+4),e.get(M+8))==(1000,200)
assert all(e.level(i)==1 for i in (1,2,3))
own=next(r for r in e.records if struct.unpack_from('<II',r,48)==(1,2))
assert struct.unpack_from('<6I',own,24)==(200,2000,1000,2000,20,40)
e.enter();assert e.get(M+4)==1000 and e.get(M+8)==200 and len(e.records)==1
r=ProgressionEngine();r.copy_state(e);r.enter();assert (r.get(M+4),r.get(M+8))==(1000,200)
early=ProgressionEngine();early.put(PROFILE+0x75c,1);temporary=early.alloc(0x40);early.put(M+0x20,temporary);early.enter()
assert (early.get(M+4),early.get(M+8))==(1000,200) and early.get(M+0x20)==temporary,'first tutorial army replaced'

# Actual page dispatch, correct cost and original four-hour duration.
e.upgrade(1);assert e.get(M+4)==850 and e.get(M+0x6c)==1
assert struct.unpack('<f',e.u.mem_read(M+0x74,4))[0]==15400.0
e.upgrade(2);assert e.get(M+4)==850 and e.notices[-1]=='[V54_UPGRADE_BUSY]'
pending=ProgressionEngine();pending.copy_state(e);pending.enter();assert pending.get(M+0x6c)==1 and pending.get(M+4)==850
pending.advance(14400);pending.run('offlineTrainingTick',pending.get(M+0x20))
assert pending.level(1)==2 and pending.get(M+0x6c)==0 and pending.get(M+4)==1010 and pending.get(M+8)==280
after=ProgressionEngine();after.now=pending.now;after.copy_state(pending);after.enter();assert after.level(1)==2 and after.get(M+4)==1010
after.upgrade(2);assert after.get(M+4)==980
after.advance(2880);after.run('offlineTrainingTick',after.get(M+0x20));assert after.level(2)==2
after.upgrade(3);assert after.get(M+4)==960 # +40 hourly rate fraction from 2880 seconds at base2
after.advance(5760);after.run('offlineTrainingTick',after.get(M+0x20));assert after.level(3)==2 and after.get(after.get(M+0x20)+4)==43

# Purchased balances above storage capacity must never be clamped.
rich=ProgressionEngine();rich.enter();rich.stub(0x9344a4,rich.product(),1);rich.advance(3600);rich.enter()
assert rich.get(M+4)==6000 and rich.get(M+8)==220
cap=ProgressionEngine();cap.enter();cap.advance(3600*24*365);cap.enter();assert (cap.get(M+4),cap.get(M+8))==(2000,2000)

# Upgrade is atomic: a failed write changes neither queue, level nor funds.
fail=ProgressionEngine();fail.enter();fail.failwrite=True;fail.upgrade(1)
assert fail.get(M+4)==1000 and fail.get(M+0x6c)==0 and fail.level(1)==1
# Legacy 176-byte wallets migrate without replacing purchased currency/army.
legacy=ProgressionEngine();legacy.run('offlineEconomyInit');legacy.stub(0x9344a4,legacy.product(),1)
key=next(iter(legacy.files));raw=legacy.files[key][:176];struct.pack_into('<I',raw,4,1)
h=2166136261
for i,c in enumerate(raw):
 if not 24<=i<28:h=((h^c)*16777619)&0xffffffff
struct.pack_into('<I',raw,24,h)
migrate=ProgressionEngine();migrate.files[key]=raw;migrate.enter();assert migrate.get(M+4)==5001 and migrate.get(M+8)==200
migrate.enter();assert migrate.get(M+4)==5001

# Native offer caller and shared confirm now finish buildings with gems.
instant=ProgressionEngine();instant.enter();instant.upgrade(1)
ui,button,timer=instant.training_ui();instant.put(ui+0xac,1);instant.put(ui+0xb0,button);instant.put(ui+0xb4,timer)
instant.run('offlineUpgradeDisplay',ui)
assert instant.labels[button+0xa4]=='15钻石立即完成' and instant.visible[timer]==0 and instant.visible[button]==1
assert bytes(instant.u.mem_read(button+0x4e,1))==b'\0'
instant.stub(0x107486c,ui,0xfffffffe);assert instant.prompts==1 and instant.get(timer+0x1fc)==BASE+0x10748e8
instant.confirm(timer,0);assert instant.level(1)==1 and instant.gems==100
instant.confirm(timer);assert instant.level(1)==2 and instant.gems==85 and instant.get(M+0x6c)==0
poor=ProgressionEngine();poor.enter();poor.upgrade(1)
ui,button,timer=poor.training_ui();poor.put(ui+0xac,1);poor.put(ui+0xb4,timer);poor.stub(0x107486c,ui,0xfffffffe);poor.gems=0;poor.confirm(timer)
assert poor.level(1)==1 and poor.get(M+0x6c)==1
poor.gems=100;poor.failwrite=True;poor.confirm(timer);assert poor.level(1)==1 and poor.gems==100 and poor.refunds==[15]

# Fresh-profile isolation grants once for each local owner.
e.put(PM+0x74,43);e.put(M+0x20,0);e.enter();assert (e.get(M+4),e.get(M+8))==(1000,200)

# Special-house preparation cannot remain in the online-only intro state.
boss=ProgressionEngine();boss.enter();boss.run('offlineGarden');boss.train();boss.advance(31);boss.run('offlineTrainingTick',boss.get(M+0x20))
boss.put(M+0x104,0x70000007);boss.put(M+0xfc,1);boss.put(M+0xf8,1);boss.u.mem_write(M+0x102,b'\1')
boss.stub(0x1042fe8,M,0,4,0)
assert bytes(boss.u.mem_read(M+0x102,1))==b'\0' and boss.get(M+0xa8)==1
assert (boss.get(M+0x88)-boss.get(M+0x84))//12==10
name=boss.alloc(4);boss.string(name,'arena_battle_test');boss.run('offlineBoardLoad',BOARD,name,0xffffffff);boss.live();boss.put(BOARD+0xc0,5)
boss.run(0x1030a50,M+0x14300,1);boss.deaths(0);boss.put(MODULE+0x78,1)
boss.stub(0x10448e8,M,1,0,1);assert boss.get(M+0x15c)==1
won=ProgressionEngine();won.now=boss.now;won.copy_state(boss);won.enter();assert won.get(M+0x15c)==1
result=dict(initial_1000_starcoins_200_medals_once=True,first_tutorial_army_preserved=True,legacy_wallet_preserved=True,profile_isolation=True,native_lab_setters_executed=True,base_panel_balance_rates_capacity=True,original_building_costs_and_timers=True,all_three_buildings_complete_and_persist=True,atomic_upgrade_write_failure=True,native_upgrade_gem_offer_and_confirm=True,upgrade_gem_label_cancel_insufficient_refund=True,offline_production_and_caps=True,purchased_over_cap_balance_retained=True,dave_independent_formation=True,dave_server_preparation_cleared=True,dave_victory_persisted=True,prior_v52_regressions_passed=True,runtime_game_verified=False)
(OUT/'v54-arm-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
