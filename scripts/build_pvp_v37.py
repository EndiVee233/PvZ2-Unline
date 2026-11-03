"""Build the first native offline-neighbor and defense-persistence candidate."""
from pathlib import Path
from io import BytesIO
import struct,zipfile,subprocess,shutil,hashlib,json,sys
from elftools.elf.elffile import ELFFile
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM
from prepare_offline_neighbors import generate
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/pvp-v37';OUT.mkdir(exist_ok=True)
BASE=ROOT/'work/pvp-v36/PvZ2-v36-defense-return-flash-fix.apk'
assert hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest()=='a142d8e1aaeb702e704ac407e915928c4e0e3491b2885fa645ff13a1e561ccac'
generate(OUT/'generated')
with zipfile.ZipFile(BASE) as src:b=bytearray(src.read('lib/armeabi/libSrc.so'))
e=ELFFile(BytesIO(b));index,tail=[(i,s) for i,s in enumerate(e.iter_segments()) if s['p_type']=='PT_LOAD'][-1]
old=len(b);assert tail['p_offset']+tail['p_filesz']==old
while len(b)%4:b.append(0)
entry=tail['p_vaddr']+len(b)-tail['p_offset']
compiler='Y:/Android/Sdk/ndk/27.0.12077973/toolchains/llvm/prebuilt/windows-x86_64/bin/clang++.exe'
flags=['--target=armv7a-linux-androideabi21','-marm','-Os','-fPIC','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-exceptions','-fno-rtti','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-I'+str(OUT/'generated')]
subprocess.run([compiler,*flags,'-c',str(ROOT/'src/offline-pvp/offline.cpp'),'-o',str(OUT/'offline.o')],check=True)
# A flat payload has no dynamic relocation table. Absolute pointer constants
# would work at base zero in analysis and crash after Android relocates the SO.
obj=ELFFile(BytesIO((OUT/'offline.o').read_bytes()))
for sec in obj.iter_sections():
 if sec['sh_type']=='SHT_REL' and 'exidx' not in sec.name:
  assert all(r['r_info_type']!=2 for r in sec.iter_relocations()),'payload contains R_ARM_ABS32'
(OUT/'flat.ld').write_text(f'ENTRY(offlineGarden)\nSECTIONS {{ . = {entry}; .payload : {{ *(.text.entry) *(.text*) *(.rodata*) *(.data*) *(.got*) }} /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }} }}')
subprocess.run([compiler,*flags,'-nostdlib','-static','-no-pie','-Wl,--no-undefined','-Wl,-T,'+str(OUT/'flat.ld'),str(OUT/'offline.o'),'-o',str(OUT/'offline.elf')],check=True)
payload=ELFFile(BytesIO((OUT/'offline.elf').read_bytes()))
assert payload.get_section_by_name('.bss') is None
symbols={s.name:s['st_value'] for s in payload.get_section_by_name('.symtab').iter_symbols()}
section=payload.get_section_by_name('.payload')
# Clang may require 8-byte alignment for native double-word constants.
gap=section['sh_addr']-entry;assert 0<=gap<16
b.extend(bytes(gap));b.extend(section.data());patches=[]
payload_file=tail['p_offset']+section['sh_addr']-tail['p_vaddr']
assert bytes(b[payload_file:payload_file+section['sh_size']])==section.data()
def bl(a,t):return struct.pack('<I',0xeb000000|(((t-a-8)//4)&0xffffff))
def append_stub(symbol,shift=False):
 while len(b)%4:b.append(0)
 va=tail['p_vaddr']+len(b)-tail['p_offset']
 asm='push {r4,lr}\n'
 if shift:asm+='mov r4,r3\nsub sp,sp,#8\nstr r4,[sp]\nmov r3,r2\nmov r2,r1\nmov r1,r0\n'
 asm+=f'adr r0,basepoint\nldr r12,[r0]\nsub r0,r0,r12\nbl #{symbols[symbol]}\n'
 if shift:asm+='add sp,sp,#8\n'
 asm+='pop {r4,pc}\nbasepoint: .word 0x11223344'
 code=bytearray(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(asm,addr=va)[0]);at=code.index(struct.pack('<I',0x11223344));struct.pack_into('<I',code,at,va+at)
 b.extend(code);return va
def patch(site,symbol,expected=None,shift=False):
 before=bytes(b[site:site+4])
 if expected is not None:assert before==expected,(hex(site),before.hex())
 target=append_stub(symbol,shift);b[site:site+4]=bl(site,target) if symbol in ('offlineGarden','offlineOwn','offlineSave') else struct.pack('<I',0xea000000|(((target-site-8)//4)&0xffffff))
 patches.append(dict(site=hex(site),symbol=symbol,before=before.hex(),after=bytes(b[site:site+4]).hex()))
assert struct.unpack_from('<I',b,0x107bf08)[0]>>24==0xeb
patch(0x107bf08,'offlineGarden')
patch(0x100b4c0,'offlineOwn',bl(0x100b4c0,0x85e7d8))
patch(0x1042f78,'offlineSave',bl(0x1042f78,0xf87cc4),True)
patch(0x1043028,'offlineInfo',bytes.fromhex('f0482de9'),True)
patch(0x1042fe8,'offlineAttack',bytes.fromhex('f0482de9'),True)
ph=e['e_phoff']+index*e['e_phentsize']
for p in (ph+16,ph+20):struct.pack_into('<I',b,p,struct.unpack_from('<I',b,p)[0]+len(b)-old)
(OUT/'libSrc.so').write_bytes(b)
subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_arm.py')],cwd=ROOT,check=True)
if '--native-only' in sys.argv:raise SystemExit(0)
unsigned=OUT/'unsigned.apk';aligned=OUT/'aligned.apk';final=OUT/'PvZ2-v37-offline-neighbor-candidate.apk'
with zipfile.ZipFile(BASE) as src,zipfile.ZipFile(unsigned,'w',allowZip64=True) as dst:
 for item in src.infolist():
  if item.filename.startswith('META-INF/'):continue
  if item.filename=='lib/armeabi/libSrc.so':dst.writestr(item,b)
  else:
   with src.open(item) as a,dst.open(item,'w') as z:shutil.copyfileobj(a,z,1048576)
subprocess.run(['K:/pvz2-tools/android-build-tools/android-14/zipalign.exe','-f','4',str(unsigned),str(aligned)],check=True)
subprocess.run(['java','-jar','K:/pvz2-tools/android-build-tools/android-14/lib/apksigner.jar','sign','--ks',str(ROOT/'work/keys/recovered-debug.keystore'),'--ks-pass','pass:android','--key-pass','pass:android','--ks-key-alias','androiddebugkey','--out',str(final),str(aligned)],check=True)
subprocess.run(['java','-jar','K:/pvz2-tools/android-build-tools/android-14/lib/apksigner.jar','verify',str(final)],check=True)
subprocess.run(['K:/pvz2-tools/android-build-tools/android-14/zipalign.exe','-c','4',str(final)],check=True)
with zipfile.ZipFile(BASE) as src,zipfile.ZipFile(final) as dst:
 for item in src.infolist():
  if item.filename.startswith('META-INF/') or item.filename=='lib/armeabi/libSrc.so':continue
  assert dst.getinfo(item.filename).CRC==item.CRC and dst.getinfo(item.filename).file_size==item.file_size,item.filename
record=dict(apk=str(final.relative_to(ROOT)),sha256=hashlib.file_digest(final.open('rb'),'sha256').hexdigest(),patches=patches,entry=hex(entry),symbols={k:hex(v) for k,v in symbols.items() if k.startswith('offline')},runtime_verified=False)
(OUT/'build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
