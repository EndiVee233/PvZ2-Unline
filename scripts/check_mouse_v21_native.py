from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.arm_const import *
import struct
b=Path('work/mouse-v21/libSrc.so').read_bytes();u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x1000,0x5000000)
from io import BytesIO
for s in ELFFile(BytesIO(b)).iter_segments():
 if s['p_type']=='PT_LOAD':
  lo=max(4096,s['p_vaddr']);u.mem_write(lo,s.data()[lo-s['p_vaddr']:])
def put(p,v):u.mem_write(p,struct.pack('<I',v))
board,cursor,frame=0x4000000,0x4002000,0x4004000
put(frame-0x44,board);u.reg_write(UC_ARM_REG_FP,frame)
def hook(uc,a,size,data):
 if a in [0x2096c4,0x209898]:uc.emu_stop()
u.hook_add(UC_HOOK_CODE,hook)
for pending,finished,already,wanted in [(0,0,False,False),(cursor,0,False,True),(cursor,1,False,False),(cursor,0,True,False)]:
 put(board+0x94c,pending);u.mem_write(cursor+0x1d,bytes([finished]));u.reg_write(UC_ARM_REG_R4,board+0x950 if already else 0x4010000)
 u.emu_start(0x209894,0,count=80)
 assert u.reg_read(UC_ARM_REG_PC)==(0x2096c4 if wanted else 0x209898)
 if wanted:
  assert u.reg_read(UC_ARM_REG_R4)==board+0x94c
  assert u.reg_read(UC_ARM_REG_R6)==board+0x950
 else:assert u.reg_read(UC_ARM_REG_SP)==frame-0x20
print('Pending hint pass: null, finished, exactly once and epilogue checks passed')
