"""Run the original native 1/2/3 shop sampler, including its stack vectors."""
from check_offline_pvp_v72_arm import RefreshEngine,SPECS,OUT
from check_offline_pvp_arm import BASE,M
from unicorn.arm_const import *
import struct,json

class NativeSamplerEngine(RefreshEngine):
 def __init__(self):
  super().__init__();self.random=19
  for offset,group in zip((0x10,0x1c,0x28),self.offer_groups):
   first=self.alloc(16*len(group))
   for i,o in enumerate(group):self.u.mem_write(first+16*i,struct.pack('<4I',o['ObjectId'],o['Quantity'],o['Price'],1))
   for k,v in enumerate((first,first+16*len(group),first+16*len(group))):self.put(M+0x200+offset+4*k,v)
 def hook(self,em,a,size,d):
  off=a-BASE
  if 0x106c3cc<=off<0x106c884:return
  if off==0x14786c:
   self.random=(self.random*1103515245+12345)&0x7fffffff;em.reg_write(UC_ARM_REG_R0,self.random)
  elif off==0x15ddfb8:
   x,y=em.reg_read(UC_ARM_REG_R0),em.reg_read(UC_ARM_REG_R1);assert y>0
   em.reg_write(UC_ARM_REG_R0,x//y);em.reg_write(UC_ARM_REG_R1,x%y)
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)

def check():
 e=NativeSamplerEngine();e.enter();e.open();seen=set()
 for _ in range(20):
  e.quote();e.refresh();ids=e.current();assert len(ids)==6 and len(set(ids))==6
  for part,group in zip((ids[:1],ids[1:3],ids[3:]),e.offer_groups):assert all(id in [o['ObjectId'] for o in group] for id in part)
  for p in range(e.get(M+0x24c),e.get(M+0x250),16):
   id=e.get(p);o=next(o for o in SPECS if o['ObjectId']==id);assert (e.get(p+4),e.get(p+8))==(o['Quantity'],o['Price'])
  seen.add(tuple(ids))
 assert len(seen)>1
 report=dict(original_native_sampler_executed=True,six_preallocated_rows_and_ids=True,category_counts=[1,2,3],quantities_and_prices_preserved=True,randomized_multiple_catalogues=True,runtime_game_verified=False)
 (OUT/'v72-native-sampler-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
if __name__=='__main__':check()
