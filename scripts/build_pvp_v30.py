"""Cache immutable arena animation bytes before the RSB drops their backing block.

The native resource index can return a low offset (0x1000) after unloading its
buffer. Match both file name and size and reuse a successful prior read. Only
pvp\\inbattleanim files are cached. RX code and RW cache head stay separate.
"""
from pathlib import Path
from io import BytesIO
from elftools.elf.elffile import ELFFile
from keystone import *
import struct,zipfile,subprocess,os,shutil,hashlib
ROOT=Path(__file__).resolve().parents[1];p=ROOT/'work/pvp-v30';p.mkdir(exist_ok=True)
BASE=ROOT/'work/bootstrap-v29/PvZ2-v29-resource-upgrade-fix.apk'
assert hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest()=='9eff94ac5c90f04c1201cae480bab281179aff23c957ad9d3d95b5a152894a2d'
with zipfile.ZipFile(BASE) as z:b=bytearray(z.read('lib/armeabi/libSrc.so'))
e=ELFFile(BytesIO(b));idx,s=[(i,s) for i,s in enumerate(e.iter_segments()) if s['p_type']=='PT_LOAD'][-1];old=len(b)
while len(b)%4:b.append(0)
va=s['p_vaddr']+len(b)-s['p_offset']
def branch(a,t):return struct.pack('<I',0xea000000|(((t-a-8)//4)&0xffffff))
asm='''push {r0,r1,r2,r3,r4,r5,r6,r7,r8,r9,r10,lr}
 ldr r6,[r9]
 mov r0,r6
 adr r1,needle
 bl #0x1479b0
 cmp r0,#0
 beq done
 ldr r4,[fp,#-0x2c]
 ldr r5,[fp,#-0x28]
 adr r7,head
 ldr r0,[r7]
 add r7,r7,r0
 ldr r8,[r7]
 find:
 cmp r8,#0
 beq add
 ldr r0,[r8,#8]
 cmp r0,r5
 bne next
 add r0,r8,#12
 mov r1,r6
 bl #0x147998
 cmp r0,#0
 beq found
 next:
 ldr r8,[r8]
 b find
 found:
 cmp r4,#0x10000
 bhs done
 ldr r0,[r8,#4]
 add r0,r0,#13
 add r0,r8,r0
 str r0,[fp,#-0x2c]
 b done
 add:
 cmp r4,#0x10000
 blo done
 mov r0,r6
 bl #0x147908
 mov r10,r0
 add r0,r0,#13
 adds r0,r0,r5
 bcs done
 bl #0x147938
 cmp r0,#0
 beq done
 mov r8,r0
 ldr r1,[r7]
 str r1,[r8]
 str r10,[r8,#4]
 str r5,[r8,#8]
 add r0,r8,#12
 mov r1,r6
 add r2,r10,#1
 bl #0x1477f4
 add r0,r8,#13
 add r0,r0,r10
 mov r1,r4
 mov r2,r5
 bl #0x1477f4
 str r8,[r7]
 done:
 pop {r0,r1,r2,r3,r4,r5,r6,r7,r8,r9,r10,lr}
 ldr r0,[fp,#-0x38]
 b #0x11fc134
 head: .word 0
 needle: .asciz "pvp\\\\inbattleanim"
'''
# Resolve strstr PLT from relocation order.
sy=e.get_section_by_name('.dynsym'); rel=e.get_section_by_name('.rel.plt')
strstr=next(e.get_section_by_name('.plt')['sh_addr']+20+i*12 for i,r in enumerate(rel.iter_relocations()) if sy.get_symbol(r['r_info_sym']).name=='strstr')
asm=asm.replace('0x1479b0',hex(strstr))
code=bytearray(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(asm,addr=va)[0])
rw=e.get_segment(3);headva=(rw['p_vaddr']+rw['p_memsz']+3)&~3
assert headva+4 < s['p_vaddr']
headat=code.index(b'pvp\\inbattleanim')-4
struct.pack_into('<I',code,headat,(headva-va-headat)&0xffffffff)
b.extend(code)
struct.pack_into('<I',b,e['e_phoff']+3*32+20,headva+4-rw['p_vaddr'])
assert b[0x11fc130:0x11fc134]==bytes.fromhex('38001be5')
b[0x11fc130:0x11fc134]=branch(0x11fc130,va)
ph=e['e_phoff']+idx*e['e_phentsize'];added=len(b)-old
for x in (ph+16,ph+20):struct.pack_into('<I',b,x,struct.unpack_from('<I',b,x)[0]+added)
struct.pack_into('<I',b,ph+24,5)
(p/'libSrc.so').write_bytes(b);(p/'cache.s').write_text(asm)
with zipfile.ZipFile(BASE) as src,zipfile.ZipFile(p/'cache-unsigned.apk','w') as dst:
 for x in src.infolist():
  if x.filename.startswith('META-INF/'):continue
  if x.filename=='lib/armeabi/libSrc.so':dst.writestr(x,b)
  else:
   with src.open(x) as a,dst.open(x,'w') as d:shutil.copyfileobj(a,d,1024*1024)
os.environ['TMP']=os.environ['TEMP']=str(Path('work/tmp').resolve())
subprocess.run(['K:/pvz2-tools/android-build-tools/android-14/zipalign.exe','-f','4',str(p/'cache-unsigned.apk'),str(p/'cache-aligned.apk')],check=True)
subprocess.run(['java','-jar','K:/pvz2-tools/android-build-tools/android-14/lib/apksigner.jar','sign','--ks','work/keys/recovered-debug.keystore','--ks-key-alias','androiddebugkey','--ks-pass','pass:android','--key-pass','pass:android','--out',str(p/'PvZ2-v30-offline-npc-entry-crash-fix.apk'),str(p/'cache-aligned.apk')],check=True)
print(hex(va),hex(strstr),code[-32:])
