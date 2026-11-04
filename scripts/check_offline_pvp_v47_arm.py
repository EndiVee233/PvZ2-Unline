"""Check in-place preview start, heartbeat and deferred native result completion."""
from check_offline_pvp_v46_arm import BattleEngine,OUT
from check_offline_pvp_arm import BASE,M,GM,END
from unicorn.arm_const import *
import json

MODULE=M+0xe000;BOARD=M+0xd000
class SessionEngine(BattleEngine):
 def __init__(self):super().__init__();self.starts=0;self.acks=0;self.gems=100;self.closed=0
 def hook(self,em,a,size,d):
  off=a-BASE;x,y=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1)]
  if a==END+0x300:
   self.closed+=1;em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
  if 0x1086e0c<=off<0x1086e70:return
  if off==0x747d00:
   if self.gems<y:result=0xffffffff
   else:self.gems-=y;result=1
  elif off==0x745220:self.gems+=y;self.refunds.append(y);result=0
  elif off==0x108a164:result=M+0xf000
  elif off==0x1094f28:result=M+0xf008
  elif off==0x43af38:result=MODULE if y==M+0xf000 else 0
  elif off==0x1090990:
   assert x==MODULE;self.starts+=1;self.put(MODULE+0xb0,3);result=0
  elif off==0x10485f0:
   assert x==M;self.acks+=1;em.mem_write(M+0x17c,b'\0');result=0
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_R0,result);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)
 def live(self):
  self.put(M+0x7000+0x6bc,BOARD);self.string(BOARD+0xc4,'arena_battle_test')
  self.put(BOARD+0x938,M+0xf100);self.put(GM+0x984,6);self.put(GM+0xa24,0xffffffff)
  self.string(GM+0xa40,'')

e=SessionEngine();e.run('offlineGarden');e.stub(0x9344a4,e.product(),1)
e.train();e.advance(31);e.run('offlineTrainingTick',e.get(M+0x20))
e.stub(0x1042fe8,M,0x70000001,3,0);e.live();e.put(MODULE+0xb0,2)
positions=e.get(M+0x84);loads=len(e.loads)
e.stub(0x1042fe8,M,0x70000001,2,0)
assert e.starts==1 and len(e.loads)==loads and e.get(M+0x84)==positions
e.stub(0x1042fe8,M,0x70000001,2,0);assert e.starts==1 and len(e.loads)==loads
# Native timeout compares the same clock value copied to +40 by local ping.
e.put(M+0x5000+0x18,0x42c80000);e.stub(0x104305c,M,2)
assert e.get(MODULE+0x40)==0x42c80000
# Simulate a fully spent army after the original module updates +d4/+d8.
e.put(M+0xd8,e.get(M+0xd4));e.stub(0x10448e8,M,0,0x70000001,2)
assert e.acks==0,'result ack fired before the native result UI was built'
e.u.mem_write(M+0x17c,b'\1');e.run('offlineTrainingTick',e.get(M+0x20))
assert e.acks==1 and e.held()==0 and bytes(e.u.mem_read(M+0x17c,1))==b'\0'
e.run('offlineTrainingTick',e.get(M+0x20));assert e.acks==1
e.stub(0x104305c,M,4);assert e.scenes[-1]!=25 or len(e.scenes)==1
before=len(e.scenes);e.run('offlineTrainingTick',e.get(M+0x20))
assert len(e.scenes)==before+1 and e.scenes[-1]==25
# Exercise the actual native confirm callback receiver, including cancel.
def finish_fixture():
 f=SessionEngine();f.run('offlineGarden');f.stub(0x9344a4,f.product(),1);f.train()
 timer=f.alloc(0x240);f.put(timer+0x1fc,BASE+0x1055588);f.put(timer+0x1f4,1)
 dialog=f.alloc(0x100);vtable=f.alloc(0x200);f.put(dialog,vtable)
 f.put(vtable+0x17c,END+0x300);f.put(BASE+0x1836300,dialog)
 return f,timer
f,timer=finish_fixture();f.stub(0x10870e0,timer,0,1)
assert f.gems==99 and f.held()==1 and f.queued()==0 and f.closed==1 and f.get(BASE+0x1836300)==0
f.stub(0x10870e0,timer,0,1);assert f.gems==99,'empty queue charged twice'
poor,timer=finish_fixture();poor.gems=0;poor.stub(0x10870e0,timer,0,1)
assert poor.held()==0 and poor.queued()==1 and poor.gems==0
fail,timer=finish_fixture();fail.failwrite=True;fail.stub(0x10870e0,timer,0,1)
assert fail.held()==0 and fail.queued()==1 and fail.gems==100 and fail.refunds==[1]
cancel,timer=finish_fixture();cancel.stub(0x10870e0,timer,0,0)
assert cancel.queued()==1 and cancel.gems==100 and cancel.closed==1
other=SessionEngine();timer=other.alloc(0x240);other.put(timer+0x1fc,BASE+0x10748e8)
other.run('offlineTrainingFinish',timer);assert other.u.reg_read(UC_ARM_REG_R0)==0 and other.gems==100
rig=json.loads((OUT/'generated/rig-resource-build.json').read_text());assert rig['changes'][0]['zombie_class_preserved']
result=dict(preview_starts_native_battle_in_place=True,no_second_level_load_or_formation_apply=True,local_heartbeat_uses_native_clock=True,result_ack_deferred_exactly_once=True,spent_army_persisted=True,exit_ack_returns_to_map=True,training_finish_native_confirm_uses_gems=True,training_finish_empty_insufficient_and_write_failure_guards=True,upgrade_checkout_unchanged=True,shared_mummy_rig_selected=True,runtime_game_verified=False)
(OUT/'v47-arm-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
