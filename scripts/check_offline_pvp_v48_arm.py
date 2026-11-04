"""Exercise real training dispatch/prompt setup and native result response."""
from check_offline_pvp_v46_arm import BattleEngine,OUT
from check_offline_pvp_arm import BASE,M,END,PROFILE,PM
from unicorn.arm_const import *
import json

MODULE=M+0xe000;BOARD=M+0xd000
class SessionEngine(BattleEngine):
 def __init__(self):
  super().__init__();self.gems=100;self.closed=0;self.prompts=0;self.windows=0;self.starts=0;self.visible={};self.labels={};self.put(BASE+0x18300a4,PM)
 def hook(self,em,a,size,d):
  off=a-BASE;x,y,z,w=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  if 0x1086e0c<=off<0x1086e70 or 0x1055474<=off<0x1055518 or 0x108573c<=off<0x1085754 or 0x108d340<=off<0x108d748 or 0x1314548<=off<0x13145f8 or 0x7e96a4<=off<0x7e9738:return
  if a==END+0x300:self.closed+=1;result=0
  elif a==END+0x310:self.visible[x]=y;result=0
  elif a==END+0x330:result=0
  elif off==0x14ea230:result=0 # native wide-string disposal, not UI behavior
  elif 0x895f0c<=off<0x895fc0:return
  elif 0x1030a50<=off<0x1030a6c:return
  elif 0x226770<=off<0x22679c:return
  elif off==0x2262b0:self.ends+=1;self.put(x+0xc0,9);result=0
  elif off==0x9760a8:
   assert y==M+0x14100 and z==0
   self.put(x,M+0x14200);self.put(x+4,0);result=x
  elif off==0x975d78:result=self.get(x)
  elif off==0x1d9bb4:self.put(x,z);self.put(x+4,w);result=x
  elif off==0x1da034 and y not in self.products:result=self.get(y)
  elif off==0x14eae74:
   self.labels[x]=bytes(em.mem_read(self.get(y),160)).decode('utf-32-le').split('\0')[0];result=x
  elif off==0x747d00:
   if self.gems<y:result=0xffffffff
   else:self.gems-=y;result=1
  elif off==0x745220:self.gems+=y;self.refunds.append(y);result=0
  elif off in (0x108a164,0x1094f28):result=M+0xf000 if off==0x108a164 else M+0xf008
  elif off==0x43af38:result=MODULE if y==M+0xf000 else 0
  elif off==0x1090990:self.starts+=1;self.put(MODULE+0xb0,3);result=0
  elif off==0x108737c:
   # Execute the real offer caller. Only the dialog rendering is a boundary.
   assert self.get(y+4)==BASE+0x1055588
   self.put(x+0x1fc,self.get(y+4));self.put(x+0x204,self.get(y+12));self.prompts+=1;result=0
  elif off==0x202010:result=self.get(x+0x7f4)
  elif off==0x4032e0:
   assert x==M+0x7000 and y==0 and z==MODULE+0x60
   self.windows+=1;self.put(x+0x139c,M+0x12000);result=0
  elif off in (0x7291cc,0x1044390,0x3fa970):result=0
  elif off==0x3ffc08:self.put(x+0x139c,0);result=0
  elif off==0x10446d8:result=0
  elif off==0x7b98dc:result=PROFILE
  elif off==0x10485f0:raise AssertionError('premature battle-teardown event')
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_R0,result);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)
 def live(self):
  self.put(M+0x7000+0x6bc,BOARD);self.string(BOARD+0xc4,'arena_battle_test');self.put(BOARD+0x938,M+0xf100);self.put(BOARD+0x7f4,1)
  self.products[M+0x14000+0x50]=M+0x14100;self.put(M+0x14200+8,M+0x14300);self.put(M+0x14200+12,0)
  self.run('offlineBankReady',M+0x14000)
 def training_ui(self):
  ui=self.alloc(0x140);button=self.alloc(0x240);timer=self.alloc(0x240);vtable=self.alloc(0x200)
  self.put(vtable+0x8c,END+0x310);self.put(vtable+0xa4,BASE+0x1314548);self.put(vtable+0x4c,END+0x330)
  self.put(button,vtable);self.put(timer,vtable);self.put(ui+0x108,button);self.put(ui+0x10c,timer)
  return ui,button,timer
 def confirm(self,timer,button=1):
  dialog=self.alloc(0x100);vtable=self.alloc(0x200);self.put(dialog,vtable);self.put(vtable+0x17c,END+0x300)
  self.put(BASE+0x1836300,dialog);self.stub(0x10870e0,timer,0,button)

def fixture():
 f=SessionEngine();f.run('offlineGarden');f.stub(0x9344a4,f.product(),1);f.train()
 ui,button,timer=f.training_ui();return f,ui,button,timer

f,ui,button,timer=fixture()
decoration=f.alloc(0x48);f.string(decoration+0x18,'obsolete price decoration',True)
f.put(button+0x1d4,decoration);f.put(button+0x1d8,decoration+0x48);f.put(button+0x1dc,decoration+0x48)
f.run('offlineTrainingDisplay',ui)
assert f.labels[button+0xa4]=='1钻石立即完成' and f.visible[button]==1 and f.visible[timer]==0
assert bytes(f.u.mem_read(button+0x4e,1))==b'\0','SetDisabled blocked a nonempty queue'
assert f.get(button+0x1d8)==decoration,'native decoration cleanup did not remove old icon'
f.stub(0x1059300,ui,1);assert f.prompts==1 and f.gems==100
f.confirm(timer);assert f.gems==99 and f.held()==1 and f.queued()==0 and f.closed==1
f.run('offlineTrainingDisplay',ui);assert bytes(f.u.mem_read(button+0x4e,1))==b'\1'
f.stub(0x1059300,ui,1);assert f.prompts==1 and f.gems==99
poor,ui,button,timer=fixture();poor.gems=0;poor.stub(0x1059300,ui,1);poor.confirm(timer)
assert poor.queued()==1 and poor.gems==0
fail,ui,button,timer=fixture();fail.failwrite=True;fail.stub(0x1059300,ui,1);fail.confirm(timer)
assert fail.queued()==1 and fail.gems==100 and fail.refunds==[1]
cancel,ui,button,timer=fixture();cancel.stub(0x1059300,ui,1);cancel.confirm(timer,0)
assert cancel.queued()==1 and cancel.gems==100

e=SessionEngine();e.run('offlineGarden');e.stub(0x9344a4,e.product(),1);e.train();e.advance(31);e.run('offlineTrainingTick',e.get(M+0x20))
e.stub(0x1042fe8,M,0x70000001,3,0)
name=e.alloc(4);e.string(name,'arena_battle_test');e.run('offlineBoardLoad',BOARD,name,0xffffffff);e.live();e.put(MODULE+0xb0,2)
e.stub(0x1042fe8,M,0x70000001,2,0);assert e.starts==1
e.put(M+0x5000+0x18,0x42c80000);e.stub(0x104305c,M,2);assert e.get(MODULE+0x40)==0x42c80000
# One newly completed unit is not part of this battle's deployed army.
e.train();e.advance(31);e.run('offlineTrainingTick',e.get(M+0x20));assert e.held()==2
e.put(e.get(M+0xd4)+4,1);e.put(MODULE+0x78,1);e.stub(0x10448e8,M,1,0x70000001,2)
assert e.held()==2 and e.windows==0 # apply to engine on the deferred update
e.run('offlineTrainingTick',e.get(M+0x20));assert e.held()==1 and e.windows==1
assert e.get(M+0x12000+0xbc)==1,'native response did not attach earned stars'
e.stub(0x10448e8,M,1,0x70000001,2);e.run('offlineTrainingTick',e.get(M+0x20));assert e.held()==1 and e.windows==1
balance=e.get(M+4);e.put(M+0xac,0)
e.stub(0x104fa50,M+0x12000,0)
assert e.scenes[-1]==25 and e.get(M+4)==balance and e.get(M+0x7000+0x139c)==0
result=dict(actual_training_button_dispatch=True,actual_offer_caller_executed=True,regular_gem_label_and_cash_overlay_hidden=True,native_set_disabled_executed=True,native_extra_icon_cleanup_executed=True,confirm_cancel_insufficient_and_write_failure=True,native_result_response_executed=True,result_window_receives_stars=True,result_continue_closes_window_and_preserves_wallet=True,no_premature_teardown=True,battle_spends_only_deployed_units=True,duplicate_result_ignored=True,in_place_start_and_heartbeat_preserved=True,runtime_game_verified=False)
(OUT/('v49-arm-checks.json' if OUT.name=='pvp-v49' else 'v48-arm-checks.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
