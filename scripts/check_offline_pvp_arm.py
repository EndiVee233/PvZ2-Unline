"""Exercise the compiled ARM offline backend without starting or changing a game."""
from pathlib import Path
from io import BytesIO
import struct,json
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/pvp-v37'
BASE=0x10000000;M=0x40000000;PM=M+0x1000;PROFILE=M+0x2000;GM=M+0x3000;END=0x50000000
class Engine:
 def __init__(self):
  self.u=Uc(UC_ARCH_ARM,UC_MODE_ARM);self.u.mem_map(BASE,0x2000000);self.u.mem_map(M,0x100000);self.u.mem_map(END,0x200000)
  e=ELFFile(BytesIO((OUT/'offline.elf').read_bytes()));s=e.get_section_by_name('.payload')
  library=ELFFile(BytesIO((OUT/'libSrc.so').read_bytes()))
  for segment in library.iter_segments():
   if segment['p_type']=='PT_LOAD':self.u.mem_write(BASE+segment['p_vaddr'],segment.data())
  assert bytes(self.u.mem_read(BASE+s['sh_addr'],s['sh_size']))==s.data(),'embedded payload alignment'
  self.exports={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()};self.heap=M+0x10000
  self.records=[];self.loaded=[];self.scenes=[];self.files={};self.fds={};self.counter=3;self.failwrite=False
  self.put(BASE+0x1835eec,GM);self.put(PM+0x74,42);self.put(PROFILE+0x75c,9);self.put(M+0x15c,0xffffffff)
  self.payload_range=(BASE+s['sh_addr'],BASE+s['sh_addr']+s['sh_size'])
  self.u.mem_write(END,b'\x1e\xff\x2f\xe1');self.u.hook_add(UC_HOOK_CODE,self.dispatch)
 def dispatch(self,em,a,size,data):
  # All current native-boundary fixtures leave the compiled payload itself
  # executable. Avoid twenty historical UI hooks/register reads per payload
  # instruction. Older base shims (including 1a0204c) remain outside this range.
  if self.payload_range[0]<=a<self.payload_range[1]:return
  self.hook(em,a,size,data)
 def put(self,p,v):self.u.mem_write(p,struct.pack('<I',v&0xffffffff))
 def get(self,p):return struct.unpack('<I',self.u.mem_read(p,4))[0]
 def alloc(self,n):p=self.heap;self.heap=(p+n+7)&~7;return p
 def txt(self,p):return bytes(self.u.mem_read(p,256)).split(b'\0')[0].decode()
 def string(self,addr,data,wide=False):
  if isinstance(data,str):data=data.encode('utf-32-le' if wide else 'utf8')
  p=self.alloc(len(data)+16);self.put(p,len(data)//(4 if wide else 1));self.put(p+4,len(data));self.put(p+8,0);self.u.mem_write(p+12,data+b'\0'*(4 if wide else 1));self.put(addr,p+12)
 def run(self,name,*args):
  regs=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3];sp=END+0x1f0000
  address=name if isinstance(name,int) else self.exports[name]
  inputs=args if isinstance(name,int) else (BASE,*args)
  for i,a in enumerate(inputs):
   if i<4:self.u.reg_write(regs[i],a)
   else:self.put(sp+(i-4)*4,a)
  self.u.reg_write(UC_ARM_REG_CPSR,0x10);self.u.reg_write(UC_ARM_REG_SP,sp);self.u.reg_write(UC_ARM_REG_LR,END)
  self.u.reg_write(UC_ARM_REG_C1_C0_2, 0xf << 20);self.u.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
  try:self.u.emu_start(BASE+address,END,count=2000000)
  except Exception:print("FAULT PC",hex(self.u.reg_read(UC_ARM_REG_PC)));raise
  assert self.u.reg_read(UC_ARM_REG_PC)==END,'backend did not return'
  assert self.u.reg_read(UC_ARM_REG_SP)==sp,'stack not restored'
 def stub(self,site,*args):
  word=self.get(BASE+site);delta=word&0xffffff
  if delta&0x800000:delta-=1<<24
  self.run(site+8+4*delta,*args)
 def hook(self,em,a,size,_):
  off=a-BASE
  if off>=0x1a00000 or a==END:return
  r=[em.reg_read(x) for x in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];x,y,z,w=r;result=0
  if off==0x7fa754:result=M
  elif off==0x1df738:result=PM
  elif off==0x7a98dc:assert x==PM;result=PROFILE
  elif off==0x352498:assert x==GM;self.scenes.append(y)
  elif off in (0x14ed0e0,0x14eb450):
   if off==0x14ed0e0:
    assert y>=BASE,hex(y)
    data=self.txt(y)
   else:
    data=bytearray();p=y
    while self.get(p):data+=bytes(em.mem_read(p,4));p+=4
    data=bytes(data)
   self.string(x,data,off==0x14eb450);result=x
  elif off in (0x14ebf58,0x14ea238,0x14c2e94):pass
  elif off==0x14c1a7c:result=self.alloc(x)
  elif off==0x1046a04:
   assert x==M;self.records.append(bytes(em.mem_read(y,64)))
   p=self.alloc(len(self.records)*64)
   em.mem_write(p,b''.join(self.records));self.put(M+0x110,p);self.put(M+0x114,p+len(self.records)*64);self.put(M+0x118,p+len(self.records)*64)
  elif off in (0x104673c,0x1046764):result=0
  elif off in (0x1048f44,0x1048dcc):assert x==M
  elif off==0x104b5d8:
   self.put(x+12,0);self.put(x+16,0);self.put(x+20,0);self.put(x+4,100);result=x
  elif off==0x104d6e4:
   assert self.txt(self.get(y))=='tutorial_armor1';p=self.alloc(32);em.mem_write(p,bytes(em.mem_read(y,32)));self.put(x+12,p);self.put(x+16,p+32);self.put(x+20,p+32)
  elif off in (0x85e7d8,0x85e874,0x85e9a8):self.loaded.append(off)
  elif off==0x147adc:pass
  elif off==0x148448:
   path=self.txt(x)
   if y==0 and path not in self.files:result=-1
   else:
    if y:self.files[path]=bytearray()
    result=self.counter;self.counter+=1;self.fds[result]=[path,0]
  elif off in (0x148460,0x1485d4):
   path,pos=self.fds[x];data=self.files[path]
   if off==0x148460:
    part=data[pos:pos+z];em.mem_write(y,bytes(part));result=len(part)
   elif self.failwrite:result=-1
   else:
    part=bytes(em.mem_read(y,min(z,79)));data.extend(part);result=len(part)
   if result>0:self.fds[x][1]+=result
  elif off==0x1485e0:result=0
  elif off==0x147b90:self.fds.pop(x)
  elif off==0x147e6c:self.files[self.txt(y)]=self.files.pop(self.txt(x))
  elif off==0x148424:self.files.pop(self.txt(x),None)
  elif off in (0xf79d74,0xf7a070,0xf87154,0xf87710,0xf87cc4):raise AssertionError('unexpected server call '+hex(off))
  else:raise AssertionError('unhandled native call '+hex(off))
  em.reg_write(UC_ARM_REG_R0,result&0xffffffff);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)

def main():
 e=Engine();e.stub(0x107bf08);assert len(e.records)==6 and e.scenes==[25] and e.get(M+0x15c)==0
 e.run('offlineGarden');assert len(e.records)==6,'duplicate neighbors'
 early=Engine();early.put(PROFILE+0x75c,7);early.run('offlineGarden');assert not early.records and early.get(M+0x15c)==0xffffffff,'tutorial modified early'
 # Real ARM functions and binary persistence: roundtrip a nonempty formation and signature.
 p=e.alloc(12);e.u.mem_write(p,struct.pack('<III',2,3,4));i=e.alloc(16);e.u.mem_write(i,struct.pack('<III',2,1,0));e.string(i+12,'plant-signature')
 for off,value in ((4,p),(8,p+12),(12,p+12),(16,i),(20,i+16),(24,i+16)):e.put(M+0x80+off,value)
 e.stub(0x1042f78,0,0,1,1);assert len(e.files)==1 and e.scenes[-1]==25
 e.stub(0x100b4c0);assert e.loaded[-1]==0x85e7d8
 d=M+0x80;assert bytes(e.u.mem_read(e.get(d+4),12))==struct.pack('<III',2,3,4)
 assert e.txt(e.get(e.get(d+16)+12))=='plant-signature'
 # NPC viewing cannot overwrite the saved local defense; reentry reloads own layout.
 e.stub(0x1043028,M,0,0x70000001,2);assert e.loaded[-1]==0x85e874 and (e.get(d+8)-e.get(d+4))//12==5
 e.run('offlineOwn');assert e.get(e.get(d+4)+4)==3
 # Corruption / cross-profile files are rejected; failed writes never leave the editor.
 path=next(iter(e.files));e.files[path][28]^=1;e.run('offlineOwn');assert e.get(d+4)==e.get(d+8)==0
 e.failwrite=True;scenes=len(e.scenes);e.run('offlineSave',0,0,1,1);assert len(e.scenes)==scenes and all(not x.endswith('.tmp') for x in e.files)
 e.stub(0x1042fe8,M,0x70000002,3,0);assert e.loaded[-1]==0x85e9a8
 result=dict(arm_backend_checks=True,embedded_stubs_at_nonzero_base=True,stack_restored=True,neighbor_count=6,tutorial_gating=True,persistence_roundtrip=True,corrupt_store_rejected=True,failed_write_keeps_editor=True,npc_does_not_overwrite_own_defense=True,runtime_game_verified=False)
 (OUT/'arm-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
