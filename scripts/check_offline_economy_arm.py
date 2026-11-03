"""Run compiled ARM wallet and training transactions against explicit engine boundaries."""
import check_offline_pvp_arm as core
from check_offline_pvp_arm import BASE,M,PM,PROFILE,END,Engine
from pathlib import Path
import struct,json
from unicorn.arm_const import *
core.OUT=Path(__file__).resolve().parents[1]/'work/pvp-v38'
class EconomyEngine(Engine):
 def __init__(self):
  self.now=10000;self.notices=[];self.refunds=[];self.notified=0;self.products={}
  super().__init__();self.put(M+4,1);self.put(M+0x10,1);self.u.mem_write(M+0x5000+0x24,struct.pack('<f',1000.0))
  self.put(BASE+0x1821674,M+0x6000);self.put(M+0x6000,M+0x7000)
 def advance(self,seconds):
  self.now+=seconds;self.u.mem_write(M+0x5000+0x24,struct.pack('<f',float(1000+self.now-10000)))
 def hook(self,em,a,size,d):
  off=a-BASE;r=[em.reg_read(x) for x in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];x,y,z,w=r;result=0
  if off==0x1a0204c:
   self.put(M+4,max(1,self.get(M+4)));em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
  if off==0xd07ae8:return
  if off==0x147824:result=self.now
  elif off==0x1f7380:result=M+0x5000
  elif off==0x1042a5c:assert x==M;self.put(M+4,y)
  elif off==0x104b628:self.put(x+16,self.get(x+12))
  elif off==0x104d6e4:
   assert self.txt(self.get(y)).startswith('pvp_'),'non-training alias rejected'
   start=self.get(x+12);end=self.get(x+16);old=bytes(em.mem_read(start,end-start)) if start else b''
   p=self.alloc(len(old)+32);em.mem_write(p,old+bytes(em.mem_read(y,32)));self.put(x+12,p);self.put(x+16,p+len(old)+32);self.put(x+20,p+len(old)+32)
  elif off==0x104a544:assert x==M and self.get(y+16)==self.get(M+4);self.notified+=1
  elif off==0x104c894:pass
  elif off==0x11d74b4:result=M+0x8000
  elif off==0x1da034:result=self.products[y]
  elif off==0x745220:assert x==PROFILE and z==1;self.refunds.append(y)
  elif off==0x4045fc:self.notices.append(self.txt(self.get(z)))
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_R0,result&0xffffffff);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)
 def product(self,count=5000,kind='pvpCoin'):
  card=self.alloc(0x140);props=self.alloc(0x80);self.string(props+0x44,kind);self.put(props+0x50,count);self.products[card+0xb8]=props;return card
 def train(self,action=1,name='pvp_change'):
  key=self.alloc(4);self.string(key,name);self.stub(0x104b8a8,self.get(M+0x20),key,action)
 def held(self):
  a=self.get(M+0x20);p=self.get(a+12);e=self.get(a+16)
  return sum(self.get(i+4) for i in range(p,e,32))
 def queued(self):
  a=self.get(M+0x20);p=self.get(a+12);e=self.get(a+16)
  return sum(self.get(i+8) for i in range(p,e,32))

def main():
 zero=EconomyEngine();zero.put(M+4,0);zero.run('offlineEconomyInit');zero.stub(0x1021f4c);assert zero.get(M+4)==0,'legacy lobby clamp restored a spent coin'
 e=EconomyEngine()
 out=e.alloc(4);key=e.alloc(4);e.string(key,'V38_PVP_5000',True);e.run(0xd07ae8,out,key)
 raw=bytes(e.u.mem_read(e.get(out),64)).decode('utf-32-le').split('\0')[0];assert raw=='获得5000星币'
 e.run('offlineEconomyInit');assert e.get(M+4)==1 and e.held()==0
 e.train();assert e.get(M+4)==1 and e.queued()==0 and e.notices[-1]=='[PVP_ERROR_PVPCOIN_NOT_ENOUCH]'
 card=e.product();e.stub(0x9344a4,card,0);assert e.get(M+4)==1,'failed purchase awarded currency'
 e.stub(0x9344a4,card,1);assert e.get(M+4)==5001 and len(e.files)==1
 generic=EconomyEngine();card2=generic.product(20000);generic.run('offlineCoinGrant',card2,card2+0xb8);assert generic.get(M+4)==20001
 e.train();assert e.get(M+4)==4996 and e.queued()==1 and e.held()==0
 e.advance(29);e.run('offlineTrainingTick',e.get(M+0x20));assert e.held()==0
 e.advance(1);e.run('offlineTrainingTick',e.get(M+0x20));assert e.held()==1 and e.queued()==0
 # Process restart imports the saved wallet/army rather than minting new units.
 restart=EconomyEngine();restart.files={k:bytearray(v) for k,v in e.files.items()};restart.run('offlineEconomyInit');assert restart.get(M+4)==4996 and restart.held()==1
 e.train();e.train(2);assert e.get(M+4)==4996 and e.queued()==0
 for _ in range(39):e.train()
 balance=e.get(M+4);e.train();assert e.held()+e.queued()==40 and e.get(M+4)==balance
 # Atomic write failure keeps prior funds and refunds the already validated gem debit.
 fail=EconomyEngine();fail.run('offlineEconomyInit');fail.failwrite=True;fail.stub(0x9344a4,fail.product(),1);assert fail.get(M+4)==1 and fail.refunds==[110] and not fail.files
 corrupt=EconomyEngine();corrupt.files={k:bytearray(v) for k,v in restart.files.items()};next(iter(corrupt.files.values()))[40]^=1;corrupt.stub(0x9344a4,corrupt.product(),1);assert corrupt.refunds==[110] and corrupt.get(M+4)==1
 # Profile switch isolates balances; early tutorial stages never initialize this backend.
 e.put(PM+0x74,43);e.put(M+4,1);e.put(M+0x20,0);e.run('offlineEconomyInit');assert e.get(M+4)==1 and e.held()==0
 early=EconomyEngine();early.put(PROFILE+0x75c,7);early.run('offlineGarden');assert not early.records and not early.files
 result=dict(arm_checked=True,localization_chain_aligned=True,relocated_stubs=True,failed_purchase_no_award=True,wallet_restart=True,training_spend_wait_completion_restart=True,cancel_refund=True,capacity_guard=True,write_failure_gem_refund=True,corrupt_file_blocks_spending=True,profile_isolation=True,early_tutorial_unchanged=True,runtime_game_verified=False)
 (core.OUT/'economy-arm-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
