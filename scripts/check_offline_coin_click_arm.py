"""Execute actual native bank click entries and the gem-parent visibility block."""
import check_offline_economy_arm as economy
from check_offline_pvp_arm import BASE,M,PROFILE,END
from unicorn.arm_const import *
import json

class ClickEngine(economy.EconomyEngine):
 def __init__(self):
  super().__init__();self.gems=3000;self.debits=[];self.fallbacks=[];self.visible=False
 def hook(self,em,a,size,d):
  off=a-BASE;x,y,z=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
  if off in (0x931da8,0x9333bc) or 0x10526c0<=off<0x10526dc:return
  if a==END+0x100:
   assert x==M+0xa000;self.visible=bool(y);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
  if off in (0x931dac,0x9333c0):
   sp=em.reg_read(UC_ARM_REG_SP);assert self.get(sp)==em.reg_read(UC_ARM_REG_R4)
   self.fallbacks.append((x,y));em.reg_write(UC_ARM_REG_SP,sp+36);em.reg_write(UC_ARM_REG_PC,self.get(sp+32));return
  if off==0x747d00:
   assert x==PROFILE
   result=-1
   if self.gems>=y:self.gems-=y;self.debits.append(y);result=0
  elif off==0x745220:
   assert x==PROFILE and z==1;self.gems+=y;self.refunds.append(y);result=0
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_R0,result&0xffffffff);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)
 def bank(self,offset,count=5000,kind='pvpCoin'):
  ui=self.alloc(0x140);items=self.alloc(4);card=self.alloc(0x120);props=self.alloc(0x80)
  self.put(ui+offset,items);self.put(ui+offset+4,items+4);self.put(items,card)
  self.string(props+0x44,kind);self.put(props+0x50,count);self.products[card+0xa0]=props
  return ui

def main():
 for site,offset in ((0x931da8,0xa8),(0x9333bc,0xb8)):
  e=ClickEngine();e.run(site,e.bank(offset),0)
  assert e.gems==2890 and e.get(M+4)==5001 and e.debits==[110] and not e.fallbacks
  e.run(site,e.bank(offset,20000),0);e.run(site,e.bank(offset,75000),0)
  assert e.gems==800 and e.get(M+4)==100001 and e.debits==[110,440,1650]
  short=ClickEngine();short.gems=109;short.run(site,short.bank(offset),0)
  assert short.gems==109 and short.get(M+4)==1 and not short.files and not short.debits
  fail=ClickEngine();fail.failwrite=True;fail.run(site,fail.bank(offset),0)
  assert fail.gems==3000 and fail.get(M+4)==1 and fail.refunds==[110] and not fail.files
  capped=ClickEngine();capped.put(M+4,2000000000);capped.run(site,capped.bank(offset),0)
  assert capped.gems==3000 and not capped.debits
  other=ClickEngine();ui=other.bank(offset,5000,'gem');other.run(site,ui,0)
  assert other.fallbacks==[(ui,0)] and other.gems==3000
  other.run(site,ui,2000);assert other.fallbacks[-1]==(ui,2000)
 # Run the real constructor instructions around SetVisible, with only the
 # virtual UI method substituted. Balance updates remain the native CBar path.
 e=ClickEngine();widget=M+0xa000;vtable=M+0xb000;e.put(widget,vtable);e.put(vtable+0x8c,END+0x100)
 e.u.reg_write(UC_ARM_REG_CPSR,0x10);e.u.reg_write(UC_ARM_REG_R4,widget)
 e.u.emu_start(BASE+0x10526c0,BASE+0x10526dc,count=100)
 assert e.visible and e.u.reg_read(UC_ARM_REG_PC)==BASE+0x10526dc
 result=dict(actual_bank_click_entries=True,three_gem_prices=True,insufficient_no_debit_or_credit=True,
  failed_save_full_refund=True,balance_limit_before_debit=True,other_products_and_special_buttons_preserved=True,
  native_gem_parent_visible=True,runtime_game_verified=False)
 (economy.core.OUT/'coin-click-arm-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
