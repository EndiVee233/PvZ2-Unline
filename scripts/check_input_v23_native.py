from pathlib import Path
from io import BytesIO
import struct,json,sys
from unicorn import *
from unicorn.arm_const import *
from elftools.elf.elffile import ELFFile
r=Path(__file__).resolve().parents[1]
candidate=Path(sys.argv[1]) if len(sys.argv)>1 else None
code=((candidate/'offline.elf') if candidate else r/'work/input-v23/shortcuts.elf').read_bytes();e=ELFFile(BytesIO(code));payload=e.get_section_by_name('.payload')
entry=0x1a010a4 if candidate else e['e_entry']
for base in [0,0x20000000]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(base+0x1000,0x3000000);u.mem_write(base+payload['sh_addr'],payload.data());u.mem_map(0x6000000,0x200000)
 if candidate:
  with (candidate/'libSrc.so').open('rb') as lib:
   for seg in ELFFile(lib).iter_segments():
    if seg['p_type']=='PT_LOAD':
     skip=max(0,4096-seg['p_vaddr']);u.mem_write(base+seg['p_vaddr']+skip,seg.data()[skip:])
  exports={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()}
  instruction=struct.unpack('<I',u.mem_read(base+entry,4))[0];assert instruction>>24==0xea
  delta=instruction&0xffffff
  if delta&0x800000:delta-=0x1000000
  assert entry+8+delta*4==exports['desktopInput']
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
 pvp_manager,pvp_module,pvp_bank=0x6050000,0x6052000,0x6054000
 pvp_packets=[0x6058000+i*0x200 for i in range(16)];pvp_bank_type=True;pvp_packet_type=True;pvp_occluded=False
 pvp_slot_reads=[];preview_positions=[]
 belt=0x6070000
 belt_packets=[0x6074000+i*0x200 for i in range(10)]
 belt_y={p:100+(9-i)*27 for i,p in enumerate(belt_packets)}
 active_belt=0
 food_plant=0
 cursor=0x6080000
 put(belt,table)
 for p in belt_packets:put(p,table)
 put(pvp_bank,table)
 for p in pvp_packets:put(p,table)
 put(pvp_manager+0xa8,1);put(board+0x938,pvp_module);put(pvp_module+0x48,pvp_bank);put(pvp_module+0x4c,1)
 u.mem_write(pvp_bank+0x11d,b'\x06');put(pvp_bank+0x148,0);put(pvp_bank+0x14c,6)
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
  elif off==0x976478:
   index=pvp_packets.index(a1) if a1 in pvp_packets else -1
   put(a0,150+index*64 if index>=0 else 150);put(a0+4,550 if index>=0 else belt_y.get(a1,250))
  elif off==0x9775d4:
   index=(a0-150)//64
   if a0>=500 and a1!=550:result=0
   elif active_belt:result=next((p for p,y in belt_y.items() if y==a1),0)
   else:result=(0 if pvp_occluded else pvp_packets[index]) if a1==550 and 0<=index<16 else packet
  elif off in [0x11d74b4,0x8ac6f4,0x27c56c,0x10290ac,0x102dc20,0x1030720,0x29a23c]:result=base+off
  elif off==0x20bb34:result=active_belt
  elif off==0x15dee64:result=0x3f800000
  elif off==0x203990:
   assert (a0,a1,a2)==(board,4,1) and string(get(a3))=='smallChestnut'
   result=food_plant
  elif off==0x4e7f60:
   assert a0==food_plant
   actions.append('plantfood')
  elif off==0x7fa754:result=pvp_manager
  elif off==0x43af38:result=pvp_module if a0==pvp_module and a1==base+0x10290ac else 0
  elif off==0x895f0c:
   assert a1==pvp_bank and 0<=a2<u.mem_read(pvp_bank+0x11d,1)[0]
   pvp_slot_reads.append(a2);put(a0,pvp_packets[a2]);put(a0+4,1)
  elif off==0x147adc:pass
  elif off==0x1327d0c:pass
  elif off==0x1efccc:preview_positions.append((get(a1),get(a1+4)))
  elif off==0x1d9bb4:put(a0,a2);put(a0+4,a3)
  elif off==0x15dec20:result=struct.unpack('<I',struct.pack('<f',a0))[0]
  elif off==0x15deccc:result=struct.unpack('<I',struct.pack('<f',struct.unpack('<f',struct.pack('<I',a0))[0]*struct.unpack('<f',struct.pack('<I',a1))[0]))[0]
  elif off==0x15df0f8:result=int(struct.unpack('<f',struct.pack('<I',a0))[0])
  elif off==0x1da034:result=get(a1)
  elif off==0x20c5e8:actions.append('pause');u.mem_write(board+0x8d5,b'\x01')
  elif off==0x20963c:actions.append('cancel')
  elif off==0x4021b0:actions.append('close');put(app+0x1378,0)
  elif a==0x6100000:result=int(overlay)
  elif a==0x6100010:
   if a1==base+0x27c56c:result=int(a0==collectible)
   elif a1==base+0x102dc20:result=int(a0==pvp_bank and pvp_bank_type)
   elif a1==base+0x1030720:result=int(a0 in pvp_packets and pvp_packet_type)
   elif a1==base+0x8ac6f4:result=int(a0==packet or a0 in belt_packets)
   elif a1==base+0x29a23c:result=int(a0==belt)
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
 def run(key,mode=6,point=(-1,-1)):
  actions.clear();put(evt+8,key);put(evt+16,point[0]);put(evt+20,point[1])
  for rr,val in [(UC_ARM_REG_R0,base),(UC_ARM_REG_R1,driver),(UC_ARM_REG_R2,evt),(UC_ARM_REG_R3,mode),(UC_ARM_REG_LR,0x6101000),(UC_ARM_REG_SP,stack+0x1f00)]:u.reg_write(rr,val)
  u.emu_start(base+entry,0,count=20000)
  assert u.reg_read(UC_ARM_REG_PC)==0x6101000
  return list(actions)
 assert run(8)==[('down',150,250),'up']
 assert run(9)==[] # nonexistent slot
 put(packet+0x10c,32);assert run(8)==[];put(packet+0x10c,0)
 disabled=True;assert run(50)==[];assert run(62)==[];disabled=False
 overlay=True;assert run(8)==[];overlay=False
 assert run(100)==['cancel']
 assert run(62)==[('down',150,250),'up']
 u.mem_write(board+0x8d5,b'\x01');assert run(8)==[];assert run(62)==[]
 put(app+0x1378,1);assert run(62)==['close','resume']
 blocked=True;assert run(8)[-1]=='blocked'
 assert run(29)==['collect'];assert run(29)==[]
 put(collectible+0x94,0);put(evt+12,220)
 assert run(90,5)==[];assert run(120,5)==['collect'];assert run(120,5)==[]
 put(collectible+0x94,0);put(collectible+0x8c,0x80);assert run(29)==[];put(collectible+0x8c,0)
 print('Native shortcut checks passed at load base',hex(base))
 if candidate:
  # Bind the actual home-defense plant bank, not UISeedBank or its skills and
  # zombies. Execute the installed entry branch at both relocation bases.
  level=0x6060000;u.mem_write(level,b'arena_plant_test\0');put(board+0xc4,level);blocked=False
  for key,index in [(8,0),(9,1),(10,2),(11,3),(45,4),(51,5)]:
   assert run(key)==[('down',150+64*index,550),'up'];assert pvp_slot_reads[-1]==index
  assert run(33)==run(46)==[] # visible slots seven/eight do not exist
  put(pvp_bank+0x14c,8);u.mem_write(pvp_bank+0x11d,b'\x10')
  assert run(33)==[('down',150+64*6,550),'up'];assert run(46)==[('down',150+64*7,550),'up']
  put(pvp_bank+0x148,1);assert run(8)==[('down',150+64*8,550),'up']
  u.mem_write(pvp_bank+0x11d,b'\x0a');assert run(10)==[] # incomplete last page
  put(pvp_bank+0x148,0);put(pvp_bank+0x14c,6);u.mem_write(pvp_bank+0x11d,b'\x06')
  put(pvp_manager+0xa8,2);assert run(8)==[];put(pvp_manager+0xa8,1) # merchant: fixed roster
  put(pvp_module+0x48,0);put(pvp_module+0x4c,0);assert run(8)==[]
  put(pvp_module+0x48,pvp_bank);put(pvp_module+0x4c,1)
  pvp_bank_type=False;assert run(8)==[];pvp_bank_type=True
  pvp_packet_type=False;assert run(8)==[];pvp_packet_type=True
  pvp_occluded=True;assert run(8)==[];pvp_occluded=False
  disabled=True;assert run(8)==[];disabled=False
  overlay=True;assert run(8)==[];overlay=False
  u.mem_write(board+0x8d5,b'\x01');assert run(8)==[];u.mem_write(board+0x8d5,b'\0')
  blocked=True;assert run(8)==[('down',150,550),'blocked'];blocked=False
  # The preview is restored using the original coordinate conversion rather
  # than being left on the clicked card. Include a nonzero board origin.
  put(board+0x94c,0x6062000);put(board+0x2c,25);put(board+0x30,15)
  put(evt+8,8);put(evt+16,500);put(evt+20,300);actions.clear()
  for rr,val in [(UC_ARM_REG_R0,base),(UC_ARM_REG_R1,driver),(UC_ARM_REG_R2,evt),(UC_ARM_REG_R3,6),(UC_ARM_REG_LR,0x6101000),(UC_ARM_REG_SP,stack+0x1f00)]:u.reg_write(rr,val)
  u.emu_start(base+entry,0,count=20000);assert preview_positions[-1]==(475,285)
  assert actions==[('down',150,550),'up']
  print('PVP home bank: eight keys, visible pages, merchant exclusion, type/bounds/UI guards and hover restoration passed',hex(base))
  if '--extended-input' in sys.argv:
   put(board+0xc4,0);put(board+0x94c,0);put(board+0x2c,0);put(board+0x30,0)
   active_belt=belt;put(belt+0x48,children);put(belt+0x4c,children+80)
   u.mem_write(belt+0x11d,b'\x0a')
   for i,p in enumerate(belt_packets):
    put(children+i*8,p);put(children+i*8+4,1)
    put(p+0x10c,2)
   for i,key in enumerate((8,9,10,11,45,51,33,46)):
    assert run(key)==[('down',150,100+i*27),'up']
   for key in (52,54):assert run(key)==[('down',150,100),'up']
   put(board+0x94c,cursor);put(cursor,base+0x179b940);put(cursor+0x28,belt_packets[2])
   put(cursor+0x2c,1)
   assert run(52)==[('down',150,316),'up'] # slot 8 to slot 9
   assert run(54)==[('down',150,262),'up'] # slot 8 to slot 7
   put(cursor+0x28,belt_packets[0]);assert run(52)==[]
   put(board+0x94c,0);active_belt=0
   put(board+0xc0,5);food_plant=0x6081000
   assert run(101,point=(500,260))==[]
   put(board+0x11c,1)
   assert run(101,point=(500,260))==['plantfood']
   put(board+0xc4,level);assert run(101,point=(500,260))==[]
   put(board+0xc4,0);put(board+0x895,1);assert run(101,point=(500,260))==[]
   put(board+0x895,0);food_plant=0;assert run(101,point=(500,260))==[]
   print('Conveyor order, relative slots, and native plant food guards passed',hex(base))
