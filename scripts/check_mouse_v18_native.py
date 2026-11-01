"""Execute the appended ARM control flow with isolated cursor/driver fixtures."""
from pathlib import Path
from io import BytesIO
import json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import *

root=Path(__file__).resolve().parents[1]
b=(root/'work/mouse-v18/libSrc-v18.so').read_bytes()
record=json.loads((root/'docs/recovery/mouse-v18-build.json').read_text())
u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
u.mem_map(0x1000,0x5000000)
for s in ELFFile(BytesIO(b)).iter_segments():
    if s['p_type']=='PT_LOAD':
        # ELF starts at zero, which is deliberately outside fixture mapping.
        start=max(0x1000,s['p_vaddr']);skip=start-s['p_vaddr']
        u.mem_write(start,s.data()[skip:])
def put(p,v):u.mem_write(p,struct.pack('<I',v))
event,driver,app,board,cursor,frame=range(0x4000000,0x4006000,0x1000)
calls=[]
stops=set()
def intercept(uc,addr,size,data):
    if addr in stops:uc.emu_stop()
    elif addr in (0x1327d0c,0x1efccc,0x1ef90c):
        calls.append((addr,uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1)))
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,intercept)
def run(entry,targets):
    stops.clear();stops.update(targets);calls.clear()
    u.reg_write(UC_ARM_REG_SP,0x4010000)
    u.emu_start(entry,0,count=200)
    assert u.reg_read(UC_ARM_REG_PC) in targets
put(driver+0x44,app);put(app+0x6bc,board)
u.reg_write(UC_ARM_REG_R4,event);u.reg_write(UC_ARM_REG_R5,driver)
for pending,finished,expected in [(0,0,False),(cursor,0,True),(cursor,1,False)]:
    put(board+0x94c,pending);u.mem_write(cursor+0x1d,bytes([finished]))
    u.reg_write(UC_ARM_REG_R3,5)
    run(0x132b660,{0x132b688})
    assert [x[0] for x in calls]==([0x1327d0c,0x1efccc] if expected else [0x1327d0c])
    if expected:assert calls[-1][1:]==(cursor,event+8)
for phase in range(5):
    u.reg_write(UC_ARM_REG_R3,phase)
    run(0x132b660,{0x132b664});assert not calls
# The pending item is drawn once, then the normal epilogue is reached.
u.reg_write(UC_ARM_REG_FP,frame);put(frame-0x38,board+0x94c)
put(board+0x94c,cursor);u.reg_write(UC_ARM_REG_R7,0x4020000)
run(0x2077d8,{0x207698,0x2077dc})
assert u.reg_read(UC_ARM_REG_PC)==0x207698
assert u.reg_read(UC_ARM_REG_R7)==board+0x94c
u.reg_write(UC_ARM_REG_R7,board+0x950)
run(0x2077d8,{0x207698,0x2077dc})
assert u.reg_read(UC_ARM_REG_PC)==0x2077dc
assert u.reg_read(UC_ARM_REG_SP)==frame-0x20
print('ARM fixtures passed: hover routing, null/finished guards, touch phases 0-4, one pending draw iteration.')
