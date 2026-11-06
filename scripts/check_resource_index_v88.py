"""Actual ARM lookup + retention code; no game, profile or UI acceptance."""
from pathlib import Path
from io import BytesIO
import struct,json,sys
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UcError
from unicorn.arm_const import *
from merge_legacy_pvp_resources import Bundle,u32
ROOT=Path(__file__).resolve().parents[1];OUT=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'work/pvp-v88'
blob=(OUT/'libSrc.so').read_bytes();elf=ELFFile(BytesIO(blob))
bundle=Bundle((ROOT/'work/pvp-v87/future.rsb.smf').read_bytes())
group=next(i for i,g in enumerate(bundle.groups) if g['ID']=='WorldMap_Future_NonPVR_Common')
rsg=bundle.payloads[group];table=bytes(rsg[u32(rsg,0x4c):u32(rsg,0x4c)+u32(rsg,0x48)])
expected=bundle.files(group);assert len(table)//4==139 and len(expected)==3
cases=[]
for base in (0,0x20000000):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(base,0x2000000)
 for s in elf.iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(base+s['p_vaddr'],blob[s['p_offset']:s['p_offset']+s['p_filesz']])
 for address,size in ((0x50000000,0x10000),(0x51000000,0x10000),(0x52000000,0x100000),(0x53000000,0x1000)):u.mem_map(address,size)
 ctype=bytearray(1024)
 for c in range(256):ctype[c*2+2]=c-32 if 97<=c<=122 else c
 u.mem_write(0x50001000,bytes(ctype));u.mem_write(0x53000000,table)
 row=0x50003000;path=0x50004000;groupname=0x50002000
 u.mem_write(groupname,b'WorldMap_Future_NonPVR_Common\0')
 u.mem_write(row,struct.pack('<6I',groupname,3,0x53000000,len(table)//4,0,0x50008000))
 original_row=bytes(u.mem_read(row,24));events=[];allocations=[];held=[False];allocation_ok=[True]
 def hook(u,a,n,_):
  if a==base+0x1405f48:
   u.reg_write(UC_ARM_REG_R0,u.reg_read(UC_ARM_REG_R5));u.reg_write(UC_ARM_REG_R4,0x50001000);u.reg_write(UC_ARM_REG_PC,base+0x1405f58);return
  if a==base+0x1479d4:
   assert not held[0];held[0]=True;events.append('lock');value=0
  elif a==base+0x1479e0:
   assert held[0];held[0]=False;events.append('unlock');value=0
  elif a==base+0x147938:
   assert held[0];size=u.reg_read(UC_ARM_REG_R0);value=0x52000000+len(allocations)*0x10000 if allocation_ok[0] else 0
   if value:allocations.append(size)
  else:return
  assert u.reg_read(UC_ARM_REG_SP)%8==0
  for r in (UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R12):u.reg_write(r,0xabc000+r)
  u.reg_write(UC_ARM_REG_R0,value);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 def lookup(name,original=False):
  u.mem_write(path,name.lower().encode()+b'\0');u.reg_write(UC_ARM_REG_R0,row+8);u.reg_write(UC_ARM_REG_R1,path);u.reg_write(UC_ARM_REG_SP,0x51008000)
  saved=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_FP)
  for r in saved:u.reg_write(r,0xdef000+r)
  stop=base+0x11c7744;u.reg_write(UC_ARM_REG_LR,stop)
  u.emu_start(base+(0x1405fd0 if original else 0x11c7740),stop,count=100000)
  assert u.reg_read(UC_ARM_REG_SP)==0x51008000 and all(u.reg_read(r)==0xdef000+r for r in saved)
  assert bytes(u.mem_read(row,24))==original_row and not held[0]
  result=u.reg_read(UC_ARM_REG_R0)
  return struct.unpack('<3I',u.mem_read(result,12)) if result else None
 for name,info in expected:assert lookup(name)==info
 assert len(allocations)==1
 u.mem_unmap(0x53000000,0x1000)
 try:lookup(expected[0][0],original=True)
 except UcError:pass
 else:raise AssertionError('fixture did not expose native stale dictionary read')
 for name,info in expected:assert lookup(name)==info
 assert lookup('NOT_PRESENT/RESOURCE.PAM') is None and len(allocations)==1
 # Same record storage repurposed for another RSG is not a cached identity hit.
 u.mem_map(0x53000000,0x1000);u.mem_write(0x53000000,table);u.mem_write(groupname,b'WorldMap_Other_NonPVR_Common\0')
 assert lookup(expected[0][0])==expected[0][1] and len(allocations)==2
 # An allocation failure keeps the original native behavior on valid input.
 u.mem_write(groupname,b'WorldMap_Third_NonPVR_Common\0');allocation_ok[0]=False
 assert lookup(expected[1][0])==expected[1][1] and len(allocations)==2
 assert events==['lock','unlock']*(len(events)//2)
 cases.append(dict(base=hex(base),public_native_entries=3,stale_native_read_reproduced=True,retained_after_unmap=True,missing_lookup=True,record_reuse_isolated=True,allocation_failure_falls_back=True,abi_and_lock_balanced=True))
report=dict(cases=cases,scope='Real future RSG dictionary and actual ARM query/retention; allocator/mutex and libc case table bounded substitutes. User switching remains pending.')
(OUT/'index-check.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
