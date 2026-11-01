"""Bounded ARM regression of the restored patches, including tutorial cleanup calls."""
from pathlib import Path
import json,struct
from unicorn import *
from unicorn.arm_const import *
root=Path(__file__).resolve().parents[1];out=root/'work/restored-v14'
b=(out/'libSrc.so').read_bytes();h=(out/'libHookPVZ2.so').read_bytes();cases=[]
for widget in [0,0x6000200]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x9f4000,0x1000);u.mem_write(0x9f4000,b[0x9f4000:0x9f5000]);u.mem_map(0x6000000,0x4000);u.mem_map(0x5000000,0x1000)
 this=0x6000000;vt=0x6001000;panel=0x6002000;profile=0x6003000
 def put(a,v):u.mem_write(a,struct.pack('<I',v))
 put(this,vt);put(this+0x1b4,panel);put(vt+0x194,0x5000000);put(panel+0x34,123)
 u.reg_write(UC_ARM_REG_R8,this);u.reg_write(UC_ARM_REG_R10,profile);u.reg_write(UC_ARM_REG_R4,widget);u.reg_write(UC_ARM_REG_SP,0x6003f00);events=[]
 def hook(c,pc,size,data):
  if pc in [0x9e9fec,0x725b38,0x5000000]:
   events.append([hex(pc),c.reg_read(UC_ARM_REG_R0),c.reg_read(UC_ARM_REG_R1)])
   c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
 u.mem_map(0x9e9000,0x1000);u.mem_map(0x725000,0x1000);u.hook_add(UC_HOOK_CODE,hook)
 u.emu_start(0x9f407c,0x9f40a4,count=100)
 assert [e[0] for e in events]==['0x9e9fec','0x725b38','0x5000000'],events
 assert events[1][1:]==[profile,18] and events[2][1:]==[this,4]
 assert u.mem_read(panel+0x34,4)==b'\0'*4
 cases.append(dict(test='tutorial18',widget=hex(widget),events=events,input_panel_flag_cleared=True))
for mode in range(20):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x990000,0x10000);u.mem_write(0x990000,b[0x990000:0x9a0000]);u.mem_map(0x6000000,0x1000);u.reg_write(UC_ARM_REG_R6,0x6000000);u.reg_write(UC_ARM_REG_R4,0xdead0000)
 u.emu_start(0x9970b8,0x9967a0,count=10)
 assert u.reg_read(UC_ARM_REG_R0)==0x6000000
 cases.append(dict(test='restored_v13_gate',mode=mode,continuation='0x9967a0'))
for off in [0x6afc,0x6c02]:
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.mem_map(0x6000,0x1000);u.mem_write(off,h[off:off+4]);u.reg_write(UC_ARM_REG_R0,123)
 u.emu_start(off|1,off+4,count=3);assert u.reg_read(UC_ARM_REG_R0)==123
 cases.append(dict(test='hook_registration_nopped',offset=hex(off)))
record=dict(checks_passed=len(cases),scope='Bounded original tutorial branch and cleanup dispatch with external callees mocked; restored victory branch and removed hook installation calls. Full gameplay not tested.',cases=cases,device_verified=False)
(root/'docs/recovery/restored-v14-validation.json').write_text(json.dumps(record,indent=2),encoding='utf8');print('PASS',len(cases),'bounded ARM/Thumb checks')
