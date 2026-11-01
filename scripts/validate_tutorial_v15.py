from pathlib import Path
import json,struct
from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.arm_const import *
root=Path(__file__).resolve().parents[1];out=root/'work/tutorial-v15';cases=[]
REGS=[UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11]
def machine(path):
 b=path.read_bytes();e=ELFFile(path.open('rb'));u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in e.iter_segments():
  if s['p_type']=='PT_LOAD':
   lo=s['p_vaddr']&~4095;hi=(s['p_vaddr']+s['p_memsz']+4095)&~4095
   u.mem_map(lo,hi-lo);u.mem_write(s['p_vaddr'],b[s['p_offset']:s['p_offset']+s['p_filesz']])
 u.mem_map(0x4000000,0x10000);u.mem_map(0x5000000,4096)
 return u
def put(u,a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
for progress in [0,2,18,30]:
 for completed in [[],[15,17,19,25],[18],[15,16,17,18,19,20,21,22,23,24,25]]:
  for ident in range(-1,31):
   results=[]
   for patched in [False,True]:
    u=machine(out/('libSrc.so' if patched else 'before.so'));profile=0x4000000;vec=profile+0x1000;stack=profile+0xf000
    put(u,profile+0x120,progress);put(u,profile+0x124,vec);put(u,profile+0x128,vec+4*len(completed))
    for j,v in enumerate(completed):put(u,vec+j*4,v)
    u.reg_write(UC_ARM_REG_R0,profile);u.reg_write(UC_ARM_REG_R1,ident&0xffffffff);u.reg_write(UC_ARM_REG_SP,stack);u.reg_write(UC_ARM_REG_LR,0x5000000)
    for j,r in enumerate(REGS):u.reg_write(r,0x111000+j)
    u.emu_start(0x709808,0x5000000,count=1000)
    assert u.reg_read(UC_ARM_REG_SP)==stack
    assert [u.reg_read(r) for r in REGS]==[0x111000+j for j in range(8)]
    results.append(u.reg_read(UC_ARM_REG_R0))
   assert results[1]==(1 if ident==18 else results[0]),(progress,completed,ident,results)
   cases.append(dict(progress=progress,completed=completed,id=ident,before=results[0],after=results[1]))
# Execute the actual overlay-entry query/branch with an incomplete profile.
u=machine(out/'libSrc.so');profile=0x4000000;mapobj=profile+0x1000;stack=profile+0xf000
put(u,profile+0x124,profile+0x2000);put(u,profile+0x128,profile+0x2000);put(u,mapobj+0x29c,0)
u.reg_write(UC_ARM_REG_R0,profile);u.reg_write(UC_ARM_REG_R7,profile);u.reg_write(UC_ARM_REG_R5,18);u.reg_write(UC_ARM_REG_R6,mapobj);u.reg_write(UC_ARM_REG_SP,stack)
u.emu_start(0x9fce24,0x9fce38,count=100)
assert u.mem_read(mapobj+0x29c,4)==b'\0'*4
record=dict(differential_cases_passed=len(cases),overlay_entry_bypassed_before_state_write=True,callee_saved_registers_and_stack_verified=True,device_verified=False,cases=cases)
(root/'docs/recovery/tutorial-v15-validation.json').write_text(json.dumps(record,indent=2),encoding='utf8');print('PASS',len(cases),'differential queries and real overlay-entry bypass')
