"""Execute the offer bypass and real map action scheduler at two load bases."""
from pathlib import Path
from io import BytesIO
import json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *

ROOT=Path(__file__).resolve().parents[1]
blob=(ROOT/'work/trial-v25/libSrc.so').read_bytes()
MEM,STOP,STACK=0x4000000,0x5000000,0x40f0000
def put(u,a,v):u.mem_write(a,struct.pack('<I',v))
def get(u,a):return struct.unpack('<I',u.mem_read(a,4))[0]
def machine(base):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
    for s in ELFFile(BytesIO(blob)).iter_segments():
        if s['p_type']!='PT_LOAD':continue
        lo=(base+s['p_vaddr'])&~4095;end=(base+s['p_vaddr']+s['p_memsz']+4095)&~4095
        u.mem_map(lo,end-lo);u.mem_write(base+s['p_vaddr'],blob[s['p_offset']:s['p_offset']+s['p_filesz']])
    u.mem_map(MEM,0x100000);u.mem_map(STOP,4096)
    u.reg_write(UC_ARM_REG_SP,STACK);u.reg_write(UC_ARM_REG_LR,STOP)
    return u

cases=[]
for base in (0,0x20000000):
    u=machine(base);action=MEM+0x1000;vt=MEM+0x2000;queue=MEM+0x3000;calls=[]
    u.mem_write(action,b'\x55'*0x40);put(u,action,vt)
    u.reg_write(UC_ARM_REG_R0,action)
    u.emu_start(base+0xa13804,STOP,count=10)
    assert u.reg_read(UC_ARM_REG_PC)==STOP
    assert u.mem_read(action+5,1)==b'\1'
    assert u.mem_read(action+6,0x3a)==b'\x55'*0x3a
    assert u.reg_read(UC_ARM_REG_SP)==STACK
    # The actual scheduler starts, observes completion, runs end/destructor,
    # and erases the action. No close event or purchase dialog is supplied.
    u.mem_write(action+4,b'\0\0')
    put(u,MEM+0x27c,queue);put(u,MEM+0x280,queue+4);put(u,queue,action)
    for off,target in [(4,STOP+0x100),(8,base+0xa13804),(12,base+0x9dc888),(16,base+0x9dc89c)]:put(u,vt+off,target)
    u.mem_write(STOP+0x100,bytes.fromhex('1eff2fe1'))
    def hook(uc,addr,size,_):
        if addr in (STOP+0x100,base+0x1135464):
            if addr==STOP+0x100:calls.append(uc.reg_read(UC_ARM_REG_R0))
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    for reg,value in [(UC_ARM_REG_R4,MEM),(UC_ARM_REG_R3,queue),(UC_ARM_REG_R6,1),
                      (UC_ARM_REG_R5,0),(UC_ARM_REG_R7,0)]:u.reg_write(reg,value)
    u.emu_start(base+0x9e9e50,base+0x9e9e4c,count=200)
    assert u.reg_read(UC_ARM_REG_PC)==base+0x9e9e4c
    assert get(u,MEM+0x280)==queue and calls==[action]
    assert u.mem_read(action+4,2)==b'\1\1'
    assert u.reg_read(UC_ARM_REG_SP)==STACK
    cases.append(dict(base=hex(base),completed_action_removed_by_original_scheduler=True))
    # Even alternate open notifications cannot allocate or install the modal.
    for app in (0,MEM,0xffffffff):
        u.reg_write(UC_ARM_REG_R0,app);u.reg_write(UC_ARM_REG_LR,STOP)
        u.emu_start(base+0x40c9c4,STOP,count=4)
        assert u.reg_read(UC_ARM_REG_PC)==STOP and u.reg_read(UC_ARM_REG_R0)==0
        assert u.reg_read(UC_ARM_REG_SP)==STACK

result=dict(scheduler_cases=cases,alternate_offer_open_cases=6,device_verified=False,
            limitations='Native bounded checks; post-Egypt-4 transition requires in-game acceptance.')
(ROOT/'docs/recovery/trial-v25-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
