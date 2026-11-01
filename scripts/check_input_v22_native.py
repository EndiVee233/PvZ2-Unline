from pathlib import Path
from io import BytesIO
import struct,json
from unicorn import *
from unicorn.arm_const import *
from elftools.elf.elffile import ELFFile
r=Path(__file__).resolve().parents[1]
code=(r/'work/input-v22/shortcuts.elf').read_bytes();e=ELFFile(BytesIO(code));payload=e.get_section_by_name('.payload')
for base in [0,0x20000000]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(base+0x1000,0x3000000);u.mem_write(base+payload['sh_addr'],payload.data());u.mem_map(0x6000000,0x200000)
 app,board,driver,bank,packet,evt,table,children,stack=[0x6000000+i*0x2000 for i in range(9)]
 def put(p,v):u.mem_write(p,struct.pack('<I',v&0xffffffff))
 def get(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 def reg(n):return u.reg_read([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3][n])
 def string(p):
  s=b''
  while u.mem_read(p,1)!=b'\0':s+=bytes(u.mem_read(p,1));p+=1
  return s.decode()
 put(driver+0x44,app);put(app+0x6bc,board);put(board+0xc0,4)
 for p in [app,board,bank,packet]:put(p,table)
 funcs={0x12c:0x6100000,0x10:0x6100010,0x1c8:0x6100020,0x1cc:0x6100030,0x58:0x6100040}
 for k,v in funcs.items():put(table+k,v)
 put(bank+0x48,children);put(bank+0x4c,children+8);u.mem_write(bank+0x11d,b'\x01');put(children,packet);put(children+4,1)
 actions=[];blocked=False;disabled=False;overlay=False
 collectible,ctable,rect,dispatcher,listeners=0x6030000,0x6031000,0x6032000,0x6040000,0x6041000
 put(collectible,ctable);put(collectible+8,collectible);put(collectible+12,1)
 put(ctable+0x10,0x6100010);put(ctable+0x90,0x6100060);put(ctable+0xe4,0x6100050)
 for off,value in [(0,100),(4,200),(8,40),(12,40)]:put(rect+off,value)
 put(board+0x93c,dispatcher);put(dispatcher,listeners);put(dispatcher+4,listeners+0x48);put(listeners+12,collectible)
 put(app+0x690,0x3f800000)
 def hook(uc,a,size,data):
  global blocked,disabled,overlay
  a0,a1,a2,a3=[reg(n) for n in range(4)];result=0;handled=True
  off=a-base
  if a==0x6101000:uc.emu_stop();return
  if off==0x14ed0e0:put(a0,a1)
  elif off==0x14ebf58:pass
  elif off==0x97714c:result=bank if string(get(a0))=='UISeedBank' else packet
  elif off==0x976720:result=0 if disabled else 1
  elif off==0x976478:put(a0,150);put(a0+4,250)
  elif off==0x9775d4:result=packet
  elif off in [0x11d74b4,0x8ac6f4,0x27c56c]:result=base+off
  elif off==0x1d9bb4:put(a0,a2);put(a0+4,a3)
  elif off==0x15dec20:result=struct.unpack('<I',struct.pack('<f',a0))[0]
  elif off==0x15deccc:result=struct.unpack('<I',struct.pack('<f',struct.unpack('<f',struct.pack('<I',a0))[0]*struct.unpack('<f',struct.pack('<I',a1))[0]))[0]
  elif off==0x15df0f8:result=int(struct.unpack('<f',struct.pack('<I',a0))[0])
  elif off==0x1da034:result=get(a1)
  elif off==0x20c5e8:actions.append('pause');u.mem_write(board+0x8d5,b'\x01')
  elif off==0x20963c:actions.append('cancel')
  elif off==0x4021b0:actions.append('close');put(app+0x1378,0)
  elif a==0x6100000:result=int(overlay)
  elif a==0x6100010:result=a0 if (a0==collectible)==(a1==base+0x27c56c) else 0
  elif a==0x6100020:actions.append(('down',get(a1+8),get(a1+12)))
  elif a==0x6100030:actions.append('blocked' if blocked else 'up')
  elif a==0x6100040:actions.append('resume');u.mem_write(board+0x8d5,bytes([a1]))
  elif a==0x6100060:result=rect
  elif a==0x6100050:
   x,y,phase=get(a1+8),get(a1+12),get(a1+40)
   assert phase==1
   if 100<=x<140 and 200<=y<240:actions.append('collect');put(collectible+0x94,1)
  else:handled=False
  if handled:uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 def run(key,mode=6):
  actions.clear();put(evt+8,key);put(evt+16,-1);put(evt+20,-1)
  for rr,val in [(UC_ARM_REG_R0,base),(UC_ARM_REG_R1,driver),(UC_ARM_REG_R2,evt),(UC_ARM_REG_R3,mode),(UC_ARM_REG_LR,0x6101000),(UC_ARM_REG_SP,stack+0x1f00)]:u.reg_write(rr,val)
  u.emu_start(base+e['e_entry'],0,count=20000)
  assert u.reg_read(UC_ARM_REG_PC)==0x6101000
  return list(actions)
 assert run(8)==[('down',150,250),'up']
 assert run(9)==[] # nonexistent slot
 put(packet+0x10c,32);assert run(8)==[];put(packet+0x10c,0)
 disabled=True;assert run(50)==[];disabled=False
 overlay=True;assert run(8)==[];overlay=False
 assert run(100)==['cancel']
 assert run(62)==['pause'];assert run(8)==[];assert run(62)==['resume']
 blocked=True;assert run(8)[-1]=='blocked'
 assert run(29)==['collect'];assert run(29)==[]
 put(collectible+0x94,0);put(evt+12,220)
 assert run(90,5)==[];assert run(120,5)==['collect'];assert run(120,5)==[]
 put(collectible+0x94,0);put(collectible+0x8c,0x80);assert run(29)==[];put(collectible+0x8c,0)
 print('Native shortcut checks passed at load base',hex(base))
