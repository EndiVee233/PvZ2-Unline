"""Correct screen-to-board conversion for the pending hover cursor over v19."""
from pathlib import Path
from io import BytesIO
import struct,zipfile,shutil,json,hashlib
from elftools.elf.elffile import ELFFile
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM
root=Path(__file__).resolve().parents[1];out=root/'work/mouse-v20';out.mkdir(exist_ok=True)
base=root/'work/mouse-v19/PvZ2-v19-pointer-hover-diagnostic.apk'
assert hashlib.file_digest(base.open('rb'),'sha256').hexdigest()=='b5332051e63e11691471268b2904a901857352c9c2508d45a78e8c36e18e9b44'
with zipfile.ZipFile(base) as src:
 b=bytearray(src.read('lib/armeabi/libSrc.so'));e=ELFFile(BytesIO(b))
 idx,s=[(i,s) for i,s in enumerate(e.iter_segments()) if s['p_type']=='PT_LOAD'][-1]
 assert s['p_offset']+s['p_filesz']==len(b)
 start=s['p_vaddr']+s['p_filesz'];site=0x132b660
 asm='''cmp r3,#5
 beq hover
 cmp r3,#4
 b #0x132b664
 hover:
 mov r0,r5
 mov r1,r4
 bl #0x1327d0c
 ldr r0,[r5,#0x44]
 ldr r0,[r0,#0x6bc]
 cmp r0,#0
 beq done
 ldr r2,[r0,#0x2c]
 ldr r3,[r4,#8]
 sub r3,r3,r2
 str r3,[r4,#8]
 ldr r2,[r0,#0x30]
 ldr r3,[r4,#0xc]
 sub r3,r3,r2
 str r3,[r4,#0xc]
 ldr r0,[r0,#0x94c]
 cmp r0,#0
 beq done
 ldrb r2,[r0,#0x1d]
 cmp r2,#0
 bne done
 add r1,r4,#8
 bl #0x1efccc
 done:
 b #0x132b688'''
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
(root/'docs/recovery/mouse-v20-build.json').write_text(json.dumps(dict(base=str(base),site=hex(site),stub=hex(start),assembly=asm,device_verified=False),indent=2)+'\n')
print('Packaged board-origin conversion candidate')
