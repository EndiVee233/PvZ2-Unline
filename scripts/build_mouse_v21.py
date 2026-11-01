"""Include the pending cursor in the native planting-hint rendering pass."""
from pathlib import Path
from io import BytesIO
import hashlib,struct,json,zipfile,shutil
from elftools.elf.elffile import ELFFile
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM
root=Path(__file__).resolve().parents[1];out=root/'work/mouse-v21';out.mkdir(exist_ok=True)
base=root/'work/mouse-v20/PvZ2-v20-hover-board-coordinates.apk'
assert hashlib.file_digest(base.open('rb'),'sha256').hexdigest()=='4a79b287641b2a2d46c91ef382225f8494b6009faad04f669ff41dd7ec6ba822'
with zipfile.ZipFile(base) as src:
 b=bytearray(src.read('lib/armeabi/libSrc.so'));e=ELFFile(BytesIO(b))
 idx,s=[(i,s) for i,s in enumerate(e.iter_segments()) if s['p_type']=='PT_LOAD'][-1]
 assert s['p_offset']+s['p_filesz']==len(b)
 site=0x209894;assert b[site:site+4].hex()=='20d04be2'
 start=s['p_vaddr']+s['p_filesz']
 # Board is already preserved at fp-0x44 before any early exit. The cursor
 # traversal increments r4 past the element; slot+4 marks the added iteration.
 asm='''ldr r3,[fp,#-0x44]
 add r3,r3,#0x940
 add r3,r3,#0xc
 add r2,r3,#4
 cmp r4,r2
 beq finish
 ldr r2,[r3]
 cmp r2,#0
 beq finish
 ldrb r1,[r2,#0x1d]
 cmp r1,#0
 bne finish
 mov r4,r3
 add r6,r4,#4
 b #0x2096c4
 finish:
 sub sp,fp,#0x20
 b #0x209898'''
 code=bytes(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(asm,addr=start)[0]);b.extend(code)
 struct.pack_into('<I',b,site,0xea000000|(((start-site-8)//4)&0xffffff))
 ph=e['e_phoff']+idx*e['e_phentsize']
 for p in [ph+16,ph+20]:struct.pack_into('<I',b,p,struct.unpack_from('<I',b,p)[0]+len(code))
 (out/'libSrc.so').write_bytes(b)
 with zipfile.ZipFile(out/'unsigned.apk','w',allowZip64=True) as dst:
  for item in src.infolist():
   if item.filename.startswith('META-INF/'):continue
   if item.filename=='lib/armeabi/libSrc.so':dst.writestr(item,b)
   else:
    with src.open(item) as a,dst.open(item,'w') as z:shutil.copyfileobj(a,z,1024*1024)
(root/'docs/recovery/mouse-v21-build.json').write_text(json.dumps(dict(base=str(base),site=hex(site),stub_va=hex(start),assembly=asm,device_verified=False),indent=2)+'\n')
print('v21 pending planting-hint pass packaged')
