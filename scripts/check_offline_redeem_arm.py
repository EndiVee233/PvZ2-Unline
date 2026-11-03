"""Execute the compiled code-entry hooks with native award/UI boundaries."""
from pathlib import Path
from io import BytesIO
import json,struct,sys
import check_offline_economy_arm as economy
from check_offline_pvp_arm import BASE,M,PROFILE
from unicorn.arm_const import *
from elftools.elf.elffile import ELFFile

class RedeemEngine(economy.EconomyEngine):
 def __init__(self):
  super().__init__();self.awards=[];self.card_calls=[];self.fallbacks=[];self.dismissals=0
  self.put(PROFILE+0x9c,0xa37a1035);self.put(PROFILE+0xa4,0x4598432b)
  self.balance(0x98,1234);self.balance(0xa0,23)
 def balance(self,offset,value=None):
  key=self.get(PROFILE+offset+4);shift=key&31
  if value is None:
   raw=self.get(PROFILE+offset)
   return ((raw>>shift)|(raw<<((32-shift)&31)))&0xffffffff ^ key
  raw=value^key;self.put(PROFILE+offset,((raw<<shift)|(raw>>((32-shift)&31)))&0xffffffff)
 def dialog(self,code):
  ui=self.alloc(0x100);input=self.alloc(0x110);self.put(ui+0xac,input);self.string(input+0xa4,code,True);return ui
 def hook(self,em,a,size,d):
  off=a-BASE;x,y,z=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
  if off in (0x852424,0x84adbc):
   # Stop immediately after the real displaced function prologue, before
   # executing its old server request. Check the original UI argument/frame.
   sp=em.reg_read(UC_ARM_REG_SP);count=9
   assert self.get(sp)==em.reg_read(UC_ARM_REG_R4)
   self.fallbacks.append(x);em.reg_write(UC_ARM_REG_SP,sp+count*4)
   em.reg_write(UC_ARM_REG_PC,self.get(sp+(count-1)*4));return
  if off==0x3feb40:
   assert x==M+0x7000;self.dismissals+=1
  elif off in (0x745220,0x746164):
   assert x==PROFILE
   assert self.dismissals>len(self.awards)//2,'reward preceded request-dialog cleanup'
   if off==0x745220:assert z==1
   offset=0xa0 if off==0x745220 else 0x98
   self.balance(offset,self.balance(offset)+y);self.awards.append((off,y))
  elif off==0x7f90fc:
   self.card_calls.append((x,y,z));self.put(x+0xec,0x12345678)
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_R0,x);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)

def main():
 e=RedeemEngine();ui=e.dialog('admin')
 for site in (0x852420,0x84adb8):e.stub(site,ui)
 assert e.balance(0xa0)==223 and e.balance(0x98)==21234
 assert e.awards==[(0x745220,100),(0x746164,10000)]*2
 assert e.notices==['[V39_ADMIN_GRANTED]']*2 and not e.files and e.dismissals==2
 for code in ('','Admin','admin1','adm','admin '):
  e.run('offlineRedeem',e.dialog(code));assert e.u.reg_read(UC_ARM_REG_R0)==0
 for site in (0x852420,0x84adb8):
  invalid=e.dialog('other-code');e.stub(site,invalid);assert e.fallbacks[-1]==invalid
 assert len(e.awards)==4
 e.balance(0x98,2147483647-9999);e.run('offlineRedeem',ui)
 assert len(e.awards)==4 and e.notices[-1]=='[V39_ADMIN_LIMIT]'
 e.balance(0x98,0);e.balance(0xa0,2147483647-99);e.run('offlineRedeem',ui)
 assert len(e.awards)==4 and e.balance(0x98)==0
 card=e.alloc(0x130);e.run('offlineCodeCard',card,2000,M+0xa0);assert e.get(card+0xec)==0
 e.run('offlineCodeCard',card,1000,M+0xa0);assert e.get(card+0xec)==0x12345678
 library=ELFFile(BytesIO((economy.core.OUT/'libSrc.so').read_bytes()))
 assert library['e_phoff']==52 and library['e_phnum']==8
 loads=[s for s in library.iter_segments() if s['p_type']=='PT_LOAD']
 assert [s['p_vaddr'] for s in loads]==sorted(s['p_vaddr'] for s in loads)
 assert loads[-1]['p_flags']==6 and loads[-1]['p_vaddr']==0x1b00000
 assert not any(s['p_type']=='PT_INTERP' for s in library.iter_segments())
 result=dict(repeat_admin_exact_awards=True,request_dialog_closed_before_award=True,encoded_currency_guard=True,non_admin_unchanged=True,
  no_used_code_flag=True,lost_items_picture_removed=True,phdr_location_and_count_preserved=True,
  runtime_game_verified=False)
 (economy.core.OUT/'redeem-arm-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
