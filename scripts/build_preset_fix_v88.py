"""Retain immutable RSG file indexes across player/resource-pool changes."""
from pathlib import Path
from io import BytesIO
import hashlib,json,struct,subprocess,zipfile,shutil,sys
from elftools.elf.elffile import ELFFile
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/pvp-v88';OUT.mkdir(exist_ok=True)
BASE=ROOT/'work/pvp-v86/PvZ2-v86-pvp-scene-candidate.apk'
assert hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest()=='a4dde5aa68813de5523e07f823082b8f1f8d2eb8ce9f06b2101c8c304de87801'
with zipfile.ZipFile(BASE) as z:b=bytearray(z.read('lib/armeabi/libSrc.so'))
elf=ELFFile(BytesIO(b));loads=[(i,s) for i,s in enumerate(elf.iter_segments()) if s['p_type']=='PT_LOAD'];index,text=loads[-2];_,rw=loads[-1]
assert text['p_flags']==5 and rw['p_flags']==6 and rw['p_vaddr']==0x1b00000
prior=ELFFile((ROOT/'work/pvp-v86/offline.elf').open('rb'));assert prior.get_section_by_name('.runtime')['sh_size']<0xc00
off=text['p_offset']+text['p_filesz'];va=text['p_vaddr']+text['p_filesz']
compiler='Y:/Android/Sdk/ndk/27.0.12077973/toolchains/llvm/prebuilt/windows-x86_64/bin/clang++.exe'
flags=['--target=armv7a-linux-androideabi21','-marm','-Os','-fPIC','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-exceptions','-fno-rtti','-fno-unwind-tables','-fno-asynchronous-unwind-tables']
source=ROOT/'src/resource-index/retained_lookup.cpp'
subprocess.run([compiler,*flags,'-c',str(source),'-o',str(OUT/'index.o')],check=True)
obj=ELFFile((OUT/'index.o').open('rb'))
for s in obj.iter_sections():
 if s['sh_type']=='SHT_REL' and 'exidx' not in s.name:assert all(r['r_info_type']!=2 for r in s.iter_relocations())
(OUT/'flat.ld').write_text(f'ENTRY(retainedResourceLookup)\nSECTIONS {{ . = {va}; .payload : {{ *(.text*) *(.rodata*) }} . = 0x1b00c00; .runtime : {{ *(.data*) *(.bss*) *(COMMON) *(.got*) }} /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }} }}')
subprocess.run([compiler,*flags,'-nostdlib','-static','-no-pie','-Wl,--no-undefined','-Wl,-T,'+str(OUT/'flat.ld'),str(OUT/'index.o'),'-o',str(OUT/'index.elf')],check=True)
payload=ELFFile((OUT/'index.elf').open('rb'));section=payload.get_section_by_name('.payload');runtime=payload.get_section_by_name('.runtime');assert runtime['sh_addr']+runtime['sh_size']<=0x1b01000
symbols={s.name:s['st_value'] for s in payload.get_section_by_name('.symtab').iter_symbols()}
code=bytearray(section.data());stub=va+len(code);stub+=(4-stub%4)%4;code.extend(bytes(stub-va-len(code)))
asm='push {r4,lr}\nmov r2,r1\nmov r1,r0\nadr r0,basepoint\nldr r12,[r0]\nsub r0,r0,r12\n'+f'bl #{symbols["retainedResourceLookup"]}\npop {{r4,pc}}\nbasepoint: .word 0x11223344'
shim=bytearray(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(asm,addr=stub)[0]);at=shim.index(struct.pack('<I',0x11223344));struct.pack_into('<I',shim,at,stub+at);code.extend(shim)
assert off+len(code)<rw['p_offset'] and not any(b[off:off+len(code)])
b[off:off+len(code)]=code
site=0x11c7740
def bl(a,t):return struct.pack('<I',0xeb000000|(((t-a-8)//4)&0xffffff))
assert b[site:site+4]==bl(site,0x1405fd0);b[site:site+4]=bl(site,stub)
ph=elf['e_phoff']+index*32;struct.pack_into('<II',b,ph+16,text['p_filesz']+len(code),text['p_filesz']+len(code))
(OUT/'libSrc.so').write_bytes(b)
subprocess.run([sys.executable,str(ROOT/'scripts/check_resource_index_v88.py')],check=True)
unsigned=OUT/'unsigned.apk';aligned=OUT/'aligned.apk';final=OUT/'PvZ2-v88-retained-resource-index.apk'
with zipfile.ZipFile(BASE) as src,zipfile.ZipFile(unsigned,'w',allowZip64=True) as dst:
 for item in src.infolist():
  if item.filename.startswith('META-INF/'):continue
  if item.filename=='lib/armeabi/libSrc.so':dst.writestr(item,b)
  else:
   with src.open(item) as i,dst.open(item,'w') as o:shutil.copyfileobj(i,o,1048576)
align='K:/pvz2-tools/android-build-tools/android-14/zipalign.exe';sign='K:/pvz2-tools/android-build-tools/android-14/lib/apksigner.jar'
subprocess.run([align,'-f','4',str(unsigned),str(aligned)],check=True)
subprocess.run(['java','-jar',sign,'sign','--ks',str(ROOT/'work/keys/recovered-debug.keystore'),'--ks-pass','pass:android','--key-pass','pass:android','--ks-key-alias','androiddebugkey','--out',str(final),str(aligned)],check=True)
subprocess.run(['java','-jar',sign,'verify',str(final)],check=True);subprocess.run([align,'-c','4',str(final)],check=True)
with zipfile.ZipFile(BASE) as src,zipfile.ZipFile(final) as dst:
 for item in src.infolist():
  if not item.filename.startswith('META-INF/') and item.filename!='lib/armeabi/libSrc.so':assert (item.CRC,item.file_size)==(dst.getinfo(item.filename).CRC,dst.getinfo(item.filename).file_size)
record=dict(apk=str(final.relative_to(ROOT)),sha256=hashlib.file_digest(final.open('rb'),'sha256').hexdigest(),site=hex(site),entry=hex(symbols['retainedResourceLookup']),code_bytes=len(code),runtime_start=hex(runtime['sh_addr']),runtime_bytes=runtime['sh_size'],source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),resources_and_importer_unchanged=True,actual_switch_pending=True)
(OUT/'build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
