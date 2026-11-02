"""Restore offline PvP lobby (scene 28) and garden-war map (scene 25).
This stage supplies only safe initial state and navigation; opponent management,
training, labs, currencies and match simulation remain future work.
"""
from pathlib import Path
import struct,zipfile,os,subprocess,shutil,hashlib,json
from io import BytesIO
from keystone import *
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];p=ROOT/'work/pvp-v31';p.mkdir(exist_ok=True)
BASE=ROOT/'work/pvp-v30/PvZ2-v30-offline-npc-entry-crash-fix.apk'
assert hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest()=='c27e2ac0ee5781a0a45000153ff6614ee64e8a011a0c01c5867c3a862788a355'
with zipfile.ZipFile(BASE) as z:b=bytearray(z.read('lib/armeabi/libSrc.so'))
e=ELFFile(BytesIO(b));idx,t=[(i,s) for i,s in enumerate(e.iter_segments()) if s['p_type']=='PT_LOAD'][-1];old=len(b)
while len(b)%4:b.append(0)
va=t['p_vaddr']+len(b)-t['p_offset']
asm='''push {r4,lr}
 bl #0x7fa754
 ldr r1,[r0,#4]
 cmp r1,#1
 movlt r1,#1
 strlt r1,[r0,#4]
 ldr r1,[r0,#0xa8]
 cmp r1,#1
 movlt r1,#1
 strlt r1,[r0,#0xa8]
 mov r1,#2
 str r1,[r0,#0x18]
 adr r4,app
 ldr r0,[r4]
 add r4,r4,r0
 ldr r4,[r4]
 ldr r4,[r4]
 add r4,r4,#0x1200
 mov r1,#0
 str r1,[r4,#0x18]
 adr r4,mgr
 ldr r0,[r4]
 add r4,r4,r0
 ldr r0,[r4]
 mov r1,#28
 mov r2,#0
 mov r3,#1
 bl #0x352498
 pop {r4,pc}
 app: .word 0x11223344
 mgr: .word 0x22334455'''
c=bytearray(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(asm,addr=va)[0])
for marker,target in [(0x11223344,0x1821674),(0x22334455,0x1835eec)]:
 a=c.index(struct.pack('<I',marker));struct.pack_into('<I',c,a,(target-va-a)&0xffffffff)
assert struct.unpack_from('<I',b,0x1021f4c)[0]&0xff000000==0xea000000
b.extend(c);struct.pack_into('<I',b,0x1021f4c,0xea000000|(((va-0x1021f4c-8)//4)&0xffffff))
# Garden war button requests native map scene 25 without login.
while len(b)%4:b.append(0)
mapva=t['p_vaddr']+len(b)-t['p_offset']
masm="""push {r4,lr}
 adr r4,manager
 ldr r0,[r4]
 add r4,r4,r0
 ldr r0,[r4]
 mov r1,#25
 mov r2,#0
 mov r3,#1
 bl #0x352498
 pop {r4,lr}
 b #0x107bd70
 manager: .word 0x55667788"""
mc=bytearray(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(masm,addr=mapva)[0]);ma=mc.index(struct.pack('<I',0x55667788));struct.pack_into('<I',mc,ma,(0x1835eec-mapva-ma)&0xffffffff);b.extend(mc)
assert b[0x107becc:0x107bed0].hex()=='198ec5eb'
struct.pack_into('<I',b,0x107becc,0xea000000|(((mapva-0x107becc-8)//4)&0xffffff))
for a,target in [(0x107b70c,0xf86bec),(0x100c8b0,0xf8a480),(0x353f1c,0xf86bec),(0x353f80,0xf8b6c4),(0x1049fcc,0xf8b350),(0x1042934,0xf8a480)]:
 assert struct.unpack_from('<I',b,a)[0]==0xeb000000|(((target-a-8)//4)&0xffffff)
 struct.pack_into('<I',b,a,0xe1a00000)
assert struct.unpack_from('<I',b,0x1042960)[0]==0xea000000|(((0xf8eec8-0x1042960-8)//4)&0xffffff)
struct.pack_into('<I',b,0x1042960,0xe12fff1e)
ph=e['e_phoff']+idx*32
for a in (ph+16,ph+20):struct.pack_into('<I',b,a,struct.unpack_from('<I',b,a)[0]+len(b)-old)
(p/'libSrc.so').write_bytes(b)
with zipfile.ZipFile(BASE) as src,zipfile.ZipFile(p/'probe-unsigned.apk','w') as dst:
 for x in src.infolist():
  if x.filename.startswith('META-INF/'):continue
  if x.filename=='lib/armeabi/libSrc.so':dst.writestr(x,b)
  else:
   with src.open(x) as a,dst.open(x,'w') as z:shutil.copyfileobj(a,z,1024*1024)
os.environ['TMP']=os.environ['TEMP']=str(Path('work/tmp').resolve())
subprocess.run(['K:/pvz2-tools/android-build-tools/android-14/zipalign.exe','-f','4',str(p/'probe-unsigned.apk'),str(p/'probe-aligned.apk')],check=True)
subprocess.run(['java','-jar','K:/pvz2-tools/android-build-tools/android-14/lib/apksigner.jar','sign','--ks','work/keys/recovered-debug.keystore','--ks-pass','pass:android','--key-pass','pass:android','--ks-key-alias','androiddebugkey','--out',str(p/'PvZ2-v31-offline-pvp-map.apk'),str(p/'probe-aligned.apk')],check=True)
print(hex(va))
