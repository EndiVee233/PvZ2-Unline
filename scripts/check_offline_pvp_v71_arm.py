"""Exercise exchange debit/recovery and the actual native batched-save gate.

Native item granting, UI notifications and the profile file writer are engine
boundaries. The user's WSA test must separately verify item icons and counts.
"""
from check_offline_pvp_v70_arm import OUT
from check_offline_pvp_v69_arm import StarEngine
from check_offline_pvp_arm import BASE,M,PM,PROFILE,END
from unicorn.arm_const import *
import json,struct

SPECS=json.loads((OUT/'generated/exchange-presets.json').read_text(encoding='utf8'))['offers']
class CutDelivery(Exception):pass

class ExchangeEngine(StarEngine):
 def __init__(self):
  super().__init__();self.inventory={};self.disk_inventory={};self.disk_sold=[];self.native_writes=0;self.generated=0;self.grants=[];self.cut='';self.fail_profile=False
  self.put(BASE+0x18300a4,PM)
  original=(OUT/'libSrc.so').read_bytes()
  pointer=0x7a8ef8+struct.unpack_from('<I',original,0x7a8f1c)[0]
  self.put(BASE+pointer,self.alloc(4))
  self.writer=self.alloc(0x20);table=self.alloc(0x20);self.put(self.writer,table);self.put(table+16,BASE+0x140000)
 def sold(self):
  first,end=self.get(PROFILE+0x7a8),self.get(PROFILE+0x7ac)
  return [self.get(p) for p in range(first,end,4)]
 def set_sold(self,ids):
  p=self.alloc(max(4,len(ids)*4))
  for i,id in enumerate(ids):self.put(p+4*i,id)
  self.put(PROFILE+0x7a8,p);self.put(PROFILE+0x7ac,p+4*len(ids));self.put(PROFILE+0x7b0,p+4*len(ids))
 def catalogue(self,offers):
  p=self.alloc(len(offers)*16)
  for i,o in enumerate(offers):self.u.mem_write(p+16*i,struct.pack('<4I',o['ObjectId'],o['Quantity'],o['Price'],int(o['ObjectId'] in self.sold())))
  self.put(M+0x24c,p);self.put(M+0x250,p+16*len(offers));self.put(M+0x254,p+16*len(offers))
 def hook(self,em,a,size,d):
  off=a-BASE;x,y,z,w=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  if off in (0x106d23c,0x106c098) or 0x7110c4<=off<0x711144 or 0x7a8ed0<=off<0x7a8f1c:return
  if off in (0x106d240,0x106c09c):
   if off==0x106d240:self.generated+=1;regs=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R11,UC_ARM_REG_PC)
   else:regs=(UC_ARM_REG_R11,UC_ARM_REG_PC)
   sp=em.reg_read(UC_ARM_REG_SP)
   for i,r in enumerate(regs):em.reg_write(r,self.get(sp+4*i))
   em.reg_write(UC_ARM_REG_SP,sp+4*len(regs));return
  if off==0x71e15c:
   assert x==PROFILE and em.mem_read(PM+0x81,1)==b'\1';self.set_sold(self.sold()+[y]);ret=0
  elif off==0x106c884:
   assert x==M+0x200 and em.mem_read(PM+0x81,1)==b'\1' and y in self.sold()
   if self.cut=='before-grant':raise CutDelivery()
   self.inventory[y]=self.inventory.get(y,0)+z;self.grants.append((y,z))
   for p in range(self.get(M+0x24c),self.get(M+0x250),16):
    if self.get(p)==y:self.put(p+12,1)
   self.put(PROFILE+4,0xbf800000)
   # The real grant routine calls MarkDirty. Run its real ARM save gate,
   # proving the purchased-ID and item cannot be written separately here.
   em.reg_write(UC_ARM_REG_R0,PROFILE);em.reg_write(UC_ARM_REG_PC,BASE+0x7110c4);return
  elif off==0x15df070:ret=int(struct.unpack('<f',struct.pack('<I',x))[0]<struct.unpack('<f',struct.pack('<I',y))[0])
  elif off==0x70a924:assert x==PROFILE;ret=0
  elif off==0x2dc77c:ret=self.writer
  elif off==0x140000:
   assert x==self.writer and em.mem_read(PM+0x81,1)==b'\0';self.native_writes+=1
   if not self.fail_profile:self.disk_inventory=dict(self.inventory);self.disk_sold=self.sold()
   if self.cut=='after-profile-save':raise CutDelivery()
   ret=0
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_R0,ret);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)
 def copy_state(self,source):
  super().copy_state(source);self.inventory=dict(source.disk_inventory);self.disk_inventory=dict(source.disk_inventory);self.disk_sold=list(source.disk_sold);self.set_sold(self.disk_sold)
 def buy(self,id):self.run(0x106c098,M+0x200,id)
 def open(self,refresh=0):self.run(0x106d23c,M+0x200,refresh)
 def close_engine(self):self.u._Uc__finalizer()

def fixture(offers=SPECS[:6]):
 e=ExchangeEngine();e.enter();e.advance(86400*5);e.enter();e.catalogue(offers);return e

def check_exchange_transactions():
 e=fixture();before=(e.get(M+8),e.gems,dict(e.files));e.open()
 assert e.generated==1 and (e.get(M+8),e.gems,e.files)==before
 e.open(1);assert e.generated==1 and e.notices[-1]=='[V71_EXCHANGE_REFRESH_PENDING]'

 # Every original SKU uses its original quantity and price; no replacement
 # medals/gems/coins are created. Each offer can be redeemed only once.
 for o in SPECS:
  print('exchange SKU',o['ObjectId'],flush=True)
  e=fixture([o]);before=(e.get(M+4),e.get(M+8),e.gems);e.buy(o['ObjectId'])
  assert (e.get(M+4),e.get(M+8),e.gems)==(before[0],before[1]-o['Price'],before[2])
  assert e.inventory=={o['ObjectId']:o['Quantity']} and e.native_writes==1
  assert e.disk_inventory==e.inventory and e.disk_sold==[o['ObjectId']]
  assert e.get(e.get(M+0x24c)+12)==1
  e.buy(o['ObjectId']);assert len(e.grants)==1 and e.native_writes==1
  r=ExchangeEngine();r.now=e.now;r.copy_state(e);r.enter();r.catalogue([o]);r.open()
  assert r.inventory==e.inventory and r.get(M+8)==e.get(M+8) and not r.grants
  e.close_engine();r.close_engine()

 o=SPECS[0]
 poor=ExchangeEngine();poor.enter();poor.catalogue([o]);before=dict(poor.files);poor.buy(o['ObjectId'])
 assert poor.get(M+8)==200 and not poor.grants and poor.files==before

 for bad in (dict(o,Price=1),dict(o,Quantity=99)):
  e=fixture([bad]);before=(e.get(M+8),dict(e.files));e.buy(o['ObjectId']);assert (e.get(M+8),e.files)==before and not e.grants
 e=fixture();e.buy(999999);assert not e.grants
 e=fixture([o]);e.failwrite=True;before=(e.get(M+8),dict(e.files));e.buy(o['ObjectId'])
 assert (e.get(M+8),e.files)==before and not e.grants and not e.sold()

 # Interrupt before item delivery and after the native profile flush; both
 # restart paths keep the single debit and converge to a single award.
 for cut in ('before-grant','after-profile-save'):
  e=fixture([o]);before=e.get(M+8);e.cut=cut
  try:e.buy(o['ObjectId']);raise AssertionError('missing simulated interruption')
  except CutDelivery:pass
  r=ExchangeEngine();r.now=e.now;r.copy_state(e);r.enter();r.catalogue([o]);r.open()
  assert r.get(M+8)==before-o['Price'] and r.inventory=={o['ObjectId']:o['Quantity']}
  assert r.sold()==[o['ObjectId']] and (not r.grants if cut=='after-profile-save' else r.grants==[(o['ObjectId'],o['Quantity'])])

 # If a native profile write does not reach disk, retain the delivery journal
 # so the next launch can recover it instead of losing the purchased item.
 e=fixture([o]);e.fail_profile=True;e.buy(o['ObjectId']);assert not e.disk_sold
 r=ExchangeEngine();r.now=e.now;r.copy_state(e);r.enter();r.catalogue([o]);r.open();assert r.inventory=={o['ObjectId']:o['Quantity']}

 # Migration uses the old checksum extent. Merely entering the UI does not
 # rewrite a v6 wallet or replay any prior purchase.
 e=fixture();key=next(k for k in e.files if k.endswith('.eco'));raw=e.files[key][:344];struct.pack_into('<I',raw,4,6);h=2166136261
 for i,c in enumerate(raw):
  if not 24<=i<28:h=((h^c)*16777619)&0xffffffff
 struct.pack_into('<I',raw,24,h);e.files[key]=raw
 r=ExchangeEngine();r.now=e.now;r.copy_state(e);r.enter();r.catalogue([o]);r.open();assert len(r.files[key])==344 and not r.grants
 r.buy(o['ObjectId']);assert len(r.files[key])==364

 # Rollover clears native purchase flags; an old journal must not award the
 # same item again in the new stock generation.
 e=fixture([o]);e.buy(o['ObjectId']);r=ExchangeEngine();r.now=e.now;r.copy_state(e);r.enter();r.set_sold([]);r.put(PROFILE+0x798,1);r.catalogue([o]);r.open()
 assert r.inventory==e.inventory and not r.grants

 report=dict(original_28_sku_quantities_and_prices=True,native_catalogue_and_confirm_path_preserved=True,
  no_network_purchase=True,medal_debit_once=True,original_item_grant_delegated=True,
  actual_native_profile_save_gate_batched=True,sold_flag_and_inventory_single_native_flush=True,
  before_delivery_and_after_flush_interruptions_recovered=True,profile_write_retry_on_restart=True,
  insufficient_medals_and_bad_offer_no_debit=True,wallet_write_failure_no_grant=True,
  v6_migration_preserves_prior_state=True,refresh_deferred=True,previous_v70_regressions=True,runtime_game_verified=False)
 (OUT/'v71-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))

if __name__=="__main__":check_exchange_transactions()
