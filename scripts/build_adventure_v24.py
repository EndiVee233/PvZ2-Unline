"""Retire only Lucky Treasure and make original local plant adventures clock-independent of servers."""
from pathlib import Path
from io import BytesIO
import struct,hashlib,json,zipfile,shutil
from elftools.elf.elffile import ELFFile
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/adventure-v24';OUT.mkdir(exist_ok=True)
BASE=ROOT/'work/input-v23/PvZ2-v23-shortcut-crash-pause-fix.apk'
assert hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest()=='ba8bf7aa978b83b6a0b9ec5959da9fb9c0bcdc5fdba4564a9698e43c71604bfc'
patches=[]
with zipfile.ZipFile(BASE) as src:
 b=bytearray(src.read('lib/armeabi/libSrc.so'));e=ELFFile(BytesIO(b))
 idx,seg=[(i,s) for i,s in enumerate(e.iter_segments()) if s['p_type']=='PT_LOAD'][-1]
 assert seg['p_offset']+seg['p_filesz']==len(b) and seg['p_flags']==5
 oldlen=len(b)
 def append(asm):
  while len(b)%4:b.append(0)
  va=seg['p_vaddr']+len(b)-seg['p_offset'];code=bytes(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(asm,addr=va)[0]);b.extend(code)
  return va,code
 def branch(site,target,link=False):
  d=target-site-8;assert d%4==0 and -(1<<25)<=d<(1<<25)
  return struct.pack('<I',(0xeb000000 if link else 0xea000000)|((d//4)&0xffffff))
 def patch(site,data,role,expected=None):
  before=bytes(b[site:site+len(data)])
  if expected is not None:assert before==expected,(hex(site),before.hex())
  b[site:site+len(data)]=data;patches.append(dict(site=hex(site),before=before.hex(),after=data.hex(),role=role))
 def target(site):
  w=struct.unpack_from('<I',b,site)[0];assert w>>24 in [0xea,0xeb]
  d=w&0xffffff;d=d-0x1000000 if d&0x800000 else d
  return site+8+d*4
 # Keep the established tutorial-18 hook. Short-circuit tutorial 15 before
 # the map creates an arrow or writes its input-lock state.
 prior=target(0x709808)
 tutorial,_=append(f'''cmp r1,#15
 moveq r0,#1
 bxeq lr
 b #{prior}''')
 patch(0x709808,branch(0x709808,tutorial),'Lucky Treasure tutorial 15 completed query')
 # This call adds the second button in treasure drawer kind 4: id 12 (Lucky).
 # The first button id 11 (Penny) and the outer Treasure entry remain intact.
 hide_asm='''blx r3
 ldr r0,[r4,#0xa8]
 cmp r0,#0
 beq done
 mov r1,#0
 ldr r3,[r0]
 ldr r3,[r3,#0x8c]
 blx r3
 ldr r0,[r4,#0xa8]
 mov r1,#1
 ldr r3,[r0]
 ldr r3,[r3,#0xa4]
 blx r3
 done:
 ldr r3,[r4,#0xbc]
 cmp r3,#4
 moveq r3,#0
 streq r3,[r4,#0xbc]
 b #0xa36004'''
 hide,_=append(hide_asm)
 patch(0xa36000,branch(0xa36000,hide),'hide and disable Lucky sub-button; retire its drawer guide',bytes.fromhex('33ff2fe1'))
 # gettimeofday is already imported by the original game at this ARM PLT.
 # Use its UTC epoch seconds only at plant-adventure call sites; leave the
 # global ServerTime object and other network features unchanged.
 clock_asm='''push {r4,lr}
 sub sp,sp,#8
 mov r0,sp
 mov r1,#0
 bl #0x147974
 cmp r0,#0
 ldreq r0,[sp]
 movne r0,#0
 add sp,sp,#8
 pop {r4,pc}'''
 clock,_=append(clock_asm)
 clock_sites=[0x6d9818,0x6dcffc,0x6e81c0,0x6ed390,0x6f3d38,
  0xf93d98,0xf93e30,0xf93e84,0xf93f70,0xf94408,0xf944f4,
  0xf94be8,0xf95808,0xf95a34,0xf95f68,0xf96588,0x71f3f8]
 for site in clock_sites:
  assert target(site)==0xf7530c
  patch(site,branch(site,clock,True),'adventure local clock')
 availability_sites=[0x6f3960,0x6f4234,0x6f4290,0x6f4a0c,0x6f6468]
 for site in availability_sites:
  assert target(site)==0x4054e8
  patch(site,bytes.fromhex('0100a0e3'),'adventure local backend is available')
 ph=e['e_phoff']+idx*e['e_phentsize'];added=len(b)-oldlen
 for p in [ph+16,ph+20]:struct.pack_into('<I',b,p,struct.unpack_from('<I',b,p)[0]+added)
 (OUT/'libSrc.so').write_bytes(b)
 with zipfile.ZipFile(OUT/'unsigned.apk','w',allowZip64=True) as dst:
  for item in src.infolist():
   if item.filename.startswith('META-INF/'):continue
   if item.filename=='lib/armeabi/libSrc.so':dst.writestr(item,b)
   else:
    with src.open(item) as a,dst.open(item,'w') as z:shutil.copyfileobj(a,z,1024*1024)
 record=dict(base=str(BASE),patches=patches,tutorial_stub=hex(tutorial),prior_tutorial_stub=hex(prior),
  hide_stub=hex(hide),clock_stub=hex(clock),clock_assembly=clock_asm,hide_assembly=hide_asm,
  clock_sites=[hex(x) for x in clock_sites],device_verified=False,
  reused_native_backend=dict(list='0xf93d8c',dispatch='0xf94bcc',start_ack='0xf957f4',skip='0xf95a1c',claim='0xf95f54',surprise='0xf96574'),
  native_sha256=hashlib.sha256(b).hexdigest())
 (ROOT/'docs/recovery/adventure-v24-build.json').write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps(dict(patches=len(patches),native_sha256=record['native_sha256'],unsigned=str(OUT/'unsigned.apk'))))
