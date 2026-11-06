"""Exercise the installed map-copy hook with public animation bytes on ARM."""
from pathlib import Path
from io import BytesIO
import json,struct,sys
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
from merge_legacy_pvp_resources import Bundle,u32
ROOT=Path(__file__).resolve().parents[1];OUT=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'work/pvp-v89'
blob=(OUT/'libSrc.so').read_bytes();elf=ELFFile(BytesIO(blob));bundle=Bundle((ROOT/'work/pvp-v87/future.rsb.smf').read_bytes())
group=next(i for i,g in enumerate(bundle.groups) if g['ID']=='WorldMap_Future_NonPVR_Common')
path,info=next((n,v) for n,v in bundle.files(group) if n.endswith('GATE_FUTURE.PAM'));rsg=bundle.payloads[group]
raw=bytes(rsg[u32(rsg,0x18)+info[1]:u32(rsg,0x18)+info[1]+info[2]])
assert len(raw)==27822
cases=[]
for base in (0,0x20000000):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(base,0x2000000)
 for s in elf.iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(base+s['p_vaddr'],blob[s['p_offset']:s['p_offset']+s['p_filesz']])
 for address,size in ((0x50000000,0x10000),(0x51000000,0x10000),(0x52000000,0x100000),(0x53000000,0x10000)):u.mem_map(address,size)
 u.mem_write(0x53000000,raw);u.mem_write(0x50005000,struct.pack('<I',0x50004000))
 held=[False];allocations=[];outputs=[];fail=[False]
 def hook(u,a,n,_):
  if a==base+0x1479d4:assert not held[0];held[0]=True;v=0
  elif a==base+0x1479e0:assert held[0];held[0]=False;v=0
  elif a==base+0x147938:
   assert held[0];v=0 if fail[0] else 0x52000000+0x10000*len(allocations)
   if v:allocations.append(u.reg_read(UC_ARM_REG_R0))
  elif a==base+0x112d864:
   assert not held[0] and u.reg_read(UC_ARM_REG_R0)==0x50006000
   src=u.reg_read(UC_ARM_REG_R1);size=u.reg_read(UC_ARM_REG_R2)
   outputs.append(bytes(u.mem_read(src,size)) if size else b'');v=0
  else:return
  assert u.reg_read(UC_ARM_REG_SP)%8==0
  for r in (UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R12):u.reg_write(r,0xabc000+r)
  u.reg_write(UC_ARM_REG_R0,v);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 def copy(name,src=0x53000000,size=len(raw)):
  u.mem_write(0x50004000,name.encode()+b'\0')
  saved=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_FP)
  for r in saved:u.reg_write(r,0xdef000+r)
  u.reg_write(UC_ARM_REG_R9,0x50005000)
  u.reg_write(UC_ARM_REG_R0,0x50006000);u.reg_write(UC_ARM_REG_R1,src);u.reg_write(UC_ARM_REG_R2,size);u.reg_write(UC_ARM_REG_SP,0x51008000);u.reg_write(UC_ARM_REG_LR,base+0x11fc148)
  u.emu_start(base+0x11fc144,base+0x11fc148,count=1000000)
  assert u.reg_read(UC_ARM_REG_SP)==0x51008000 and not held[0]
  for r in saved:assert u.reg_read(r)==(0x50005000 if r==UC_ARM_REG_R9 else 0xdef000+r)
 copy(path);assert outputs[-1]==raw and len(allocations)==1
 u.mem_unmap(0x53000000,0x10000)
 copy(path.lower().replace('\\','/'));assert outputs[-1]==raw and len(allocations)==1
 # Repeated switches neither read the unmapped pool nor allocate more copies.
 for _ in range(4):copy(path,0xdead0000)
 assert all(v==raw for v in outputs) and len(allocations)==1
 u.mem_map(0x53000000,0x10000);u.mem_write(0x53000000,raw)
 copy('images/1536/future/worldmap/other.pam');assert outputs[-1]==raw and len(allocations)==2
 copy('images/1536/plants/pea.pam');assert outputs[-1]==raw and len(allocations)==2
 copy(path,0xdead0000,0);assert outputs[-1]==b''
 fail[0]=True;copy('images/1536/future/worldmap/third.pam');assert outputs[-1]==raw and len(allocations)==2
 cases.append(dict(base=hex(base),bytes=27822,retained_after_unmap=True,repeated_reads_allocate_once=True,case_and_slash_equivalent=True,different_files_isolated=True,non_map_unmodified=True,zero_size_and_allocation_failure_passthrough=True,abi_and_mutex=True))
report=dict(cases=cases,scope='Installed ARM hook and retention code; original vector-copy boundary, allocator and mutex are bounded substitutes. No actual player-switch acceptance.')
(OUT/'map-buffer-check.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
