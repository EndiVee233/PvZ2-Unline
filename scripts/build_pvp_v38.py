"""Build the offline star-coin purchase and training candidate."""
from pathlib import Path
from io import BytesIO
import struct,zipfile,subprocess,shutil,hashlib,json,sys
from prepare_offline_economy import prepare
from exchange_localization import add_exchange_localization
from rebuild_bootstrap_dex import rebuild_bootstrap
from elftools.elf.elffile import ELFFile
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM
from prepare_offline_neighbors import generate
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/pvp-v38';OUT.mkdir(exist_ok=True)
BASE=ROOT/'work/pvp-v36/PvZ2-v36-defense-return-flash-fix.apk'
assert hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest()=='a142d8e1aaeb702e704ac407e915928c4e0e3491b2885fa645ff13a1e561ccac'
generate(OUT/'generated')
resource,strings,economy_record=prepare(BASE,OUT/'generated')
with zipfile.ZipFile(BASE) as src:
 b=bytearray(src.read('lib/armeabi/libSrc.so'))
 old_resource=src.read('assets/reconstruction/dynamic-original-speed.rsb.smf')
 oldsha=hashlib.sha256(old_resource).hexdigest();newsha=hashlib.sha256(resource).hexdigest()
 method='.method private static isSupportedResourcePredecessor(Ljava/lang/String;)Z\n    .registers 2'
 extra=f'\n\n    const-string v0, "{oldsha}"\n    invoke-virtual {{v0, p0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n    move-result v0\n    if-eqz v0, :v38_older_versions\n    const/4 v0, 0x1\n    return v0\n    :v38_older_versions'
 dex=rebuild_bootstrap(src.read('classes8.dex'),OUT/'bootstrap',{oldsha:newsha,method:method+extra,'.offline-defense-v35':'.offline-economy-v38',hex(len(old_resource)):hex(len(resource))},ROOT/'tools/apktool.jar')
b,localization=add_exchange_localization(b,strings)
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
(OUT/'flat.ld').write_text(f'ENTRY(offlineGarden)\nSECTIONS {{ . = {entry}; .payload : {{ *(.text.entry) *(.text*) *(.rodata*) }} . = 0x1b00000; .runtime : {{ *(.data*) *(.bss*) *(COMMON) *(.got*) }} /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }} }}')
subprocess.run([compiler,*flags,'-nostdlib','-static','-no-pie','-Wl,--no-undefined','-Wl,-T,'+str(OUT/'flat.ld'),str(OUT/'offline.o'),'-o',str(OUT/'offline.elf')],check=True)
payload=ELFFile(BytesIO((OUT/'offline.elf').read_bytes()))
runtime=payload.get_section_by_name('.runtime');assert runtime['sh_addr']==0x1b00000 and 0<runtime['sh_size']<4096
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
# Replace only the server queue request and its native update tail call.
original=(ROOT/'work/libSrc_orig.so').read_bytes()
patch(0x104b8a8,'offlineTraining',original[0x104b8a8:0x104b8ac],True)
patch(0x1046490,'offlineTrainingTick',struct.pack('<I',0xea000000|(((0x104c894-0x1046490-8)//4)&0xffffff)),True)
# Complete only pvpCoin purchases; preserve the original callback for other products.
def baseasm():return 'adr r0,basepoint\nldr r12,[r0]\nsub r0,r0,r12\n'
def custom_stub(asm):
 while len(b)%4:b.append(0)
 va=tail['p_vaddr']+len(b)-tail['p_offset'];asm+='\nbasepoint: .word 0x11223344'
 c=bytearray(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(asm,addr=va)[0]);p=c.index(struct.pack('<I',0x11223344));struct.pack_into('<I',c,p,va+p);b.extend(c);return va
def redirect(site,target):
 before=bytes(b[site:site+4]);struct.pack_into('<I',b,site,0xea000000|(((target-site-8)//4)&0xffffff));patches.append(dict(site=hex(site),before=before.hex(),after=bytes(b[site:site+4]).hex()))
site=0x9344a4;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4bf0
coin_stub=custom_stub('push {r0-r4,lr}\nmov r2,r1\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineCoinComplete"]}\ncmp r0,#0\npop {{r0-r4,lr}}\nbne handled\n.word {first}\nb #{site+4}\nhandled: bx lr')
redirect(site,coin_stub)
site=0x930648;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4ff0
grant_stub=custom_stub('push {r0-r4,lr}\nmov r2,r1\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineCoinGrant"]}\ncmp r0,#0\npop {{r0-r4,lr}}\nbne handled\n.word {first}\nb #{site+4}\nhandled: bx lr')
redirect(site,grant_stub)

site=0x1021f4c;word=struct.unpack_from('<I',b,site)[0];assert word>>24==0xea
delta=word&0xffffff
if delta&0x800000:delta-=1<<24
prior=site+8+4*delta
lobby_stub=custom_stub(f'push {{r0-r4,lr}}\nbl #{prior}\n'+baseasm()+f'bl #{symbols["offlineEconomyInit"]}\npop {{r0-r4,pc}}')
redirect(site,lobby_stub)
# A separate writable mapping owns the cache. Keep code read/execute and retain
# all old load/unwind headers. Relocate the PHDR table rather than the interpreter.
header_offset=len(b);header_va=tail['p_vaddr']+header_offset-tail['p_offset'];count=e['e_phnum']+1
headers=[list(struct.unpack_from('<8I',b,e['e_phoff']+i*32)) for i in range(e['e_phnum'])]
rx_end=header_offset+count*32
headers[index][4]=headers[index][5]=rx_end-tail['p_offset']
headers[0]=[6,header_offset,header_va,header_va,count*32,count*32,4,4]
rw_offset=(rx_end+4095)&~4095
headers.append([1,rw_offset,0x1b00000,0x1b00000,4096,4096,6,4096])
for h in headers:b.extend(struct.pack('<8I',*h))
b.extend(bytes(rw_offset-len(b)));b.extend(bytes(4096))
struct.pack_into('<I',b,28,header_offset);struct.pack_into('<H',b,44,count)
(OUT/'libSrc.so').write_bytes(b)
subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_economy_arm.py')],cwd=ROOT,check=True)
if '--native-only' in sys.argv:raise SystemExit(0)
unsigned=OUT/'unsigned.apk';aligned=OUT/'aligned.apk';final=OUT/'PvZ2-v38-starcoins-training-candidate.apk'
with zipfile.ZipFile(BASE) as src,zipfile.ZipFile(unsigned,'w',allowZip64=True) as dst:
 for item in src.infolist():
  if item.filename.startswith('META-INF/'):continue
  if item.filename=='lib/armeabi/libSrc.so':dst.writestr(item,b)
  elif item.filename=='classes8.dex':dst.writestr(item,dex)
  elif item.filename=='assets/reconstruction/dynamic-original-speed.rsb.smf':dst.writestr(item,resource)
  else:
   with src.open(item) as a,dst.open(item,'w') as z:shutil.copyfileobj(a,z,1048576)
subprocess.run(['K:/pvz2-tools/android-build-tools/android-14/zipalign.exe','-f','4',str(unsigned),str(aligned)],check=True)
subprocess.run(['java','-jar','K:/pvz2-tools/android-build-tools/android-14/lib/apksigner.jar','sign','--ks',str(ROOT/'work/keys/recovered-debug.keystore'),'--ks-pass','pass:android','--key-pass','pass:android','--ks-key-alias','androiddebugkey','--out',str(final),str(aligned)],check=True)
subprocess.run(['java','-jar','K:/pvz2-tools/android-build-tools/android-14/lib/apksigner.jar','verify',str(final)],check=True)
subprocess.run(['K:/pvz2-tools/android-build-tools/android-14/zipalign.exe','-c','4',str(final)],check=True)
with zipfile.ZipFile(BASE) as src,zipfile.ZipFile(final) as dst:
 for item in src.infolist():
  if item.filename.startswith('META-INF/') or item.filename in ('lib/armeabi/libSrc.so','classes8.dex','assets/reconstruction/dynamic-original-speed.rsb.smf'):continue
  assert dst.getinfo(item.filename).CRC==item.CRC and dst.getinfo(item.filename).file_size==item.file_size,item.filename
record=dict(apk=str(final.relative_to(ROOT)),sha256=hashlib.file_digest(final.open('rb'),'sha256').hexdigest(),patches=patches,economy=economy_record,localization=localization,entry=hex(entry),symbols={k:hex(v) for k,v in symbols.items() if k.startswith('offline')},runtime_verified=False)
(OUT/'build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
