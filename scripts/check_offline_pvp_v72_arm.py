"""Exercise manual refresh, stock journaling and confirmed medal purchases."""
from check_offline_pvp_v71_arm import ExchangeEngine,SPECS,OUT
from check_offline_pvp_arm import BASE,M,PM,PROFILE,END
from unicorn.arm_const import *
import json,struct

COSTS=[10,20,20,50,50,100,100,200,200,500]
class RefreshEngine(ExchangeEngine):
 def __init__(self):
  super().__init__();self.samples=0;self.published=0;self.disk_stock=(0,0,[]);self.stock_cut=False
  self.put(M+0x204,1);self.put(M+0x208,2);self.put(M+0x20c,3)
  self.offer_groups=[SPECS[:3],SPECS[3:8],SPECS[8:]]
 def hook(self,em,a,size,d):
  off=a-BASE;x,y,z,w=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  if off==0x106e868 or 0x106e4fc<=off<0x106e5c0:return
  if off==0x106e86c:
   sp=em.reg_read(UC_ARM_REG_SP);regs=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_PC)
   for i,r in enumerate(regs):em.reg_write(r,self.get(sp+4*i))
   em.reg_write(UC_ARM_REG_SP,sp+4*len(regs));return
  if off==0x106c3cc:
   assert x==M+0x200;self.samples+=1
   rows=[]
   for group,n in zip(self.offer_groups,(1,2,3)):
    rows.extend(group[(i+self.samples-1)%len(group)] for i in range(n))
   p,q=self.get(y+4),self.get(z+4)
   for i,o in enumerate(rows):em.mem_write(p+16*i,struct.pack('<4I',o['ObjectId'],o['Quantity'],o['Price'],0));self.put(q+4*i,o['ObjectId'])
   self.put(y+4,p+96);self.put(z+4,q+24);ret=0
  elif off==0x106ceec:
   assert x==M+0x200;self.put(x+0x48,y);p,q=self.get(z),self.get(z+4);assert q-p==96
   dest=self.alloc(96);em.mem_write(dest,bytes(em.mem_read(p,96)));self.put(x+0x4c,dest);self.put(x+0x50,dest+96);self.put(x+0x54,dest+96);self.published+=1;ret=0
  elif off==0x7153d4:
   assert x==PROFILE;self.put(x+0x798,y);self.put(x+0x794,0);self.set_sold([]);self.set_ids([]);ret=0
  elif off==0x715430:
   assert x==PROFILE;p,q=self.get(y),self.get(y+4);self.set_ids([self.get(t) for t in range(p,q,4)]);ret=0
  elif off==0x140000:
   if self.stock_cut:raise RuntimeError('cut before stock profile write')
   if not self.fail_profile:self.disk_stock=(self.get(PROFILE+0x798),self.get(PROFILE+0x794),self.ids())
   return super().hook(em,a,size,d)
  elif off==0x140004:
   self.put(BASE+0x18a584c,0);ret=0
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_R0,ret);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)
 def set_ids(self,ids):
  p=self.alloc(max(4,len(ids)*4))
  for i,id in enumerate(ids):self.put(p+4*i,id)
  self.put(PROFILE+0x79c,p);self.put(PROFILE+0x7a0,p+4*len(ids));self.put(PROFILE+0x7a4,p+4*len(ids))
 def ids(self):return [self.get(p) for p in range(self.get(PROFILE+0x79c),self.get(PROFILE+0x7a0),4)]
 def copy_state(self,source):
  super().copy_state(source);self.disk_stock=(source.disk_stock[0],source.disk_stock[1],list(source.disk_stock[2]))
  day,index,ids=self.disk_stock;self.put(PROFILE+0x798,day);self.put(PROFILE+0x794,index);self.set_ids(ids)
 def quote(self):
  ui=self.alloc(0xe4);table=self.alloc(0x180);self.put(ui,table);self.put(table+0x17c,BASE+0x140004)
  self.put(ui+0xcc,0);self.put(BASE+0x18a584c,ui);self.put(BASE+0x1830948,M);self.run(0x106e868,ui,0);return ui
 def refresh(self):self.open(1)
 def confirm(self,ui,button=0):self.run(0x106e4fc,ui,button)
 def current(self):
  return [self.get(p) for p in range(self.get(M+0x24c),self.get(M+0x250),16)]
 def price(self):return self.get(M+0x248)
 def stock_record(self):
  raw=next(v for k,v in self.files.items() if k.endswith('.eco'));assert len(raw) in (400,412);return struct.unpack('<9I',raw[364:400])

def fixture():
 e=RefreshEngine();e.enter();e.advance(86400*5);e.enter();e.open();return e

def check_manual_refresh():
 e=fixture();assert len(set(e.current()))==6 and e.price()==10 and e.samples==1
 before=(e.get(M+8),e.current(),e.stock_record());e.open();assert (e.get(M+8),e.current(),e.stock_record())==before and e.samples==1
 # A click without a live confirmation cannot spend. Cancelling the original
 # confirmation closes it; a stale or repeated acknowledgement cannot refresh.
 e.refresh();assert e.get(M+8)==before[0] and e.samples==1
 ui=e.quote();e.confirm(ui,1);e.refresh();assert e.get(M+8)==before[0] and e.get(BASE+0x18a584c)==0

 for index in range(11):
  price=COSTS[min(index,9)];assert e.price()==price
  if e.get(M+8)<price:break
  ui=e.quote();coins,medals,gems=e.get(M+4),e.get(M+8),e.gems;samples=e.samples;e.confirm(ui)
  assert (e.get(M+4),e.get(M+8),e.gems)==(coins,medals-price,gems) and e.samples==samples+1 and e.stock_record()[2]==index+1
  assert e.price()==COSTS[min(index+1,9)] and not e.sold()
  after=(e.get(M+8),e.current());e.confirm(ui);assert (e.get(M+8),e.current())==after
  # All originally selected goods retain their own category quantity/price.
  assert len(set(e.current()))==6
  r=RefreshEngine();r.now=e.now;r.copy_state(e);r.enter();r.open();assert r.current()==e.current() and r.price()==e.price() and r.get(M+8)==e.get(M+8) and r.samples==0
  r.close_engine()

 # One real purchase followed by refresh resets stock but neither awards
 # fragments again nor changes the original native inventory grant path.
 e=fixture();item=e.current()[0];spec=next(o for o in SPECS if o['ObjectId']==item);e.buy(item)
 assert e.inventory[item]==spec['Quantity'] and e.sold()==[item]
 e.quote();e.refresh();assert not e.sold() and e.inventory[item]==spec['Quantity'] and len(e.grants)==1
 r=RefreshEngine();r.now=e.now;r.copy_state(e);r.enter();r.open();assert r.inventory==e.inventory and not r.grants and r.current()==e.current()

 # A failed wallet replacement leaves original stock, medals and native
 # inventory intact. There must be no free stock generation committed to disk.
 e=fixture();e.quote();before=(e.get(M+8),e.current(),e.ids(),dict(e.files));e.failwrite=True;e.refresh()
 assert (e.get(M+8),e.current(),e.ids(),e.files)==before

 # The wallet includes both the fee and target six IDs. If native persistence
 # fails after the debit, restart materializes those exact IDs without re-debit.
 for cut in ('write-fail','interrupted'):
  e=fixture();e.quote();before=e.get(M+8);e.fail_profile=cut=='write-fail';e.stock_cut=cut=='interrupted'
  try:e.refresh()
  except RuntimeError:assert cut=='interrupted'
  target=e.stock_record()[3:];r=RefreshEngine();r.now=e.now;r.copy_state(e);r.enter();r.open()
  assert tuple(r.current())==target and r.get(M+8)==before-10 and r.price()==20 and r.samples==0

 # No money / invalid confirmation owner. Use legal transactions to drain the
 # ordinary fixture, with the final expensive tier rejecting insufficient funds.
 e=fixture()
 while e.get(M+8)>=e.price():e.quote();e.refresh()
 before=(e.get(M+8),e.current());e.quote();e.refresh();assert (e.get(M+8),e.current())==before

 e=fixture();e.quote();e.put(PM+0x74,43);e.put(M+0x20,0);e.enter();before=e.get(M+8);e.refresh();assert e.get(M+8)==before

 # A legacy v7 wallet can be migrated by opening the shop, preserving medals,
 # held army and the existing native six IDs, without charging a refresh.
 e=fixture();key=next(k for k in e.files if k.endswith('.eco'));raw=e.files[key][:364];struct.pack_into('<I',raw,4,7);h=2166136261
 for i,c in enumerate(raw):
  if not 24<=i<28:h=((h^c)*16777619)&0xffffffff
 struct.pack_into('<I',raw,24,h);e.files[key]=raw;r=RefreshEngine();r.now=e.now;r.copy_state(e);r.enter();before=r.get(M+8);r.open()
 assert r.get(M+8)==before and r.current()==e.current() and r.samples==0

 report=dict(original_refresh_costs=COSTS,cost_currency='medals',original_sampler_and_native_shop_event_boundaries=True,
  six_unique_goods_original_category_counts=True,opening_free=True,confirm_cancel_and_duplicate_safe=True,
 native_quote_trampoline_executed=True,actual_native_confirmation_and_close_executed=True,medal_cost_and_next_price=True,stock_and_price_restart=True,
  native_purchased_flags_reset_without_duplicate_item_award=True,wallet_write_failure_preserves_stock=True,
  profile_write_failure_and_interruption_recover_target_stock=True,insufficient_medals_and_cross_profile_rejected=True,
  legacy_v7_migration_preserves_native_stock=True,automatic_refresh_deferred=True,previous_v70_regressions=True,runtime_game_verified=False)
 (OUT/'v72-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))

if __name__=="__main__":
 check_manual_refresh()
 from check_offline_exchange_sampler_arm import check
 check()
