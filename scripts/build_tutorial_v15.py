"""v15: treat retired tutorial 18 as complete before map overlay/input lock creation."""
import struct,zipfile,hashlib,json,shutil
from pathlib import Path
from elftools.elf.elffile import ELFFile
root=Path(__file__).resolve().parents[1];source=root/'work/restored-v14/PvZ2-v14-restored-lottery-tutorial.apk';out=root/'work/tutorial-v15';out.mkdir(exist_ok=True)
def branch(src,dst):
 delta=dst-src-8;assert delta%4==0 and -(1<<25)<=delta<(1<<25)
 return struct.pack('<I',0xea000000|((delta//4)&0xffffff))
with zipfile.ZipFile(source) as z:
 original=z.read('lib/armeabi/libSrc.so');assert hashlib.sha256(original).hexdigest()=='969e4a84d92e7665c5c247ad7fda7f7d042ea1f30336c59e354e8445e3e42d7a'
 b=bytearray(original);(out/'before.so').write_bytes(b)
 with (out/'before.so').open('rb') as f:
  e=ELFFile(f);segments=[(i,s) for i,s in enumerate(e.iter_segments()) if s['p_type']=='PT_LOAD'];idx,seg=segments[-1]
  assert seg['p_offset']+seg['p_filesz']==len(b) and seg['p_flags']==5
  stub_va=seg['p_vaddr']+seg['p_filesz'];stub_off=len(b);assert stub_va%4==0
  ph=e['e_phoff']+idx*e['e_phentsize'];oldsz=seg['p_filesz'];oldmem=seg['p_memsz'];assert oldsz==oldmem
 entry=0x709808;before=bytes(b[entry:entry+4]);assert before==bytes.fromhex('04b02de5')
 # cmp r1,#18; moveq r0,#1; bxeq lr; original str fp,[sp,#-4]!; b entry+4
 code=bytes.fromhex('120051e30100a0031eff2f01')+before+branch(stub_va+16,entry+4)
 b.extend(code);b[entry:entry+4]=branch(entry,stub_va)
 struct.pack_into('<I',b,ph+16,oldsz+len(code));struct.pack_into('<I',b,ph+20,oldmem+len(code))
 (out/'libSrc.so').write_bytes(b)
 with zipfile.ZipFile(out/'unsigned.apk','w',allowZip64=True) as dst:
  for i in z.infolist():
   if i.filename.startswith('META-INF/'):continue
   if i.filename=='lib/armeabi/libSrc.so':dst.writestr(i,b)
   else:
    with z.open(i) as a,dst.open(i,'w') as c:shutil.copyfileobj(a,c,1024*1024)
 record=dict(source_apk=str(source),source_native_sha256=hashlib.sha256(original).hexdigest(),patched_native_sha256=hashlib.sha256(b).hexdigest(),entry=hex(entry),before=before.hex(),after=b[entry:entry+4].hex(),stub_va=hex(stub_va),stub_offset=hex(stub_off),stub_code=code.hex(),program_header_offset=hex(ph),old_segment_size=oldsz,new_segment_size=oldsz+len(code),user_verified_v14_lottery=True,device_verified_v15_tutorial=False)
 (root/'docs/recovery/tutorial-v15-patches.json').write_text(json.dumps(record,indent=2),encoding='utf8');print(json.dumps(record,indent=2))
