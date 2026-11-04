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
ROOT=Path(__file__).resolve().parents[1];VERSION=52 if '--v52' in sys.argv else 51 if '--v51' in sys.argv else 50 if '--v50' in sys.argv else 49 if '--v49' in sys.argv else 48 if '--v48' in sys.argv else 47 if '--v47' in sys.argv else 46 if '--v46' in sys.argv else 45 if '--v45' in sys.argv else 44 if '--v44' in sys.argv else 43 if '--v43' in sys.argv else 42 if '--v42' in sys.argv else 41 if '--v41' in sys.argv else 40 if '--v40' in sys.argv else 39
OUT=ROOT/f'work/pvp-v{VERSION}';OUT.mkdir(exist_ok=True)
BASE=ROOT/'work/pvp-v36/PvZ2-v36-defense-return-flash-fix.apk'
assert hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest()=='a142d8e1aaeb702e704ac407e915928c4e0e3491b2885fa645ff13a1e561ccac'
generate(OUT/'generated')
resource,strings,economy_record=prepare(BASE,OUT/'generated')
if VERSION>=43:
 from prepare_offline_pvp_scenes import prepare as prepare_scenes
 resource,scene_record=prepare_scenes(resource,OUT/'generated')
 economy_record['scenes']=scene_record
if VERSION>=47:
 from prepare_offline_pvp_zombie_rig import prepare as prepare_rig
 resource,rig_record=prepare_rig(resource,OUT/'generated')
 economy_record['rig']=rig_record
with zipfile.ZipFile(BASE) as src:
 b=bytearray(src.read('lib/armeabi/libSrc.so'))
 old_resource=src.read('assets/reconstruction/dynamic-original-speed.rsb.smf')
 oldsha=hashlib.sha256(old_resource).hexdigest();newsha=hashlib.sha256(resource).hexdigest()
 method='.method private static isSupportedResourcePredecessor(Ljava/lang/String;)Z\n    .registers 2'
 extra=f'\n\n    const-string v0, "{oldsha}"\n    invoke-virtual {{v0, p0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n    move-result v0\n    if-eqz v0, :v38_older_versions\n    const/4 v0, 0x1\n    return v0\n    :v38_older_versions'
 if VERSION>=43:
  previous=economy_record['scenes']['predecessor_sha256']
  extra=extra.replace('    :v38_older_versions', f'    :v38_older_versions\n\n    const-string v0, \"{previous}\"\n    invoke-virtual {{v0, p0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n    move-result v0\n    if-eqz v0, :v43_older_versions\n    const/4 v0, 0x1\n    return v0\n    :v43_older_versions')
 if VERSION>=47:
  previous=economy_record['rig']['predecessor_sha256']
  extra=extra.replace('    :v43_older_versions', f'    :v43_older_versions\n\n    const-string v0, "{previous}"\n    invoke-virtual {{v0, p0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n    move-result v0\n    if-eqz v0, :v47_older_versions\n    const/4 v0, 0x1\n    return v0\n    :v47_older_versions')
 marker='.offline-pvp-v47' if VERSION>=47 else '.offline-pvp-v43' if VERSION>=43 else '.offline-economy-v38'
 dex=rebuild_bootstrap(src.read('classes8.dex'),OUT/'bootstrap',{oldsha:newsha,method:method+extra,'.offline-defense-v35':marker,hex(len(old_resource)):hex(len(resource))},ROOT/'tools/apktool.jar')
strings.update(V39_ADMIN_GRANTED='获得100钻石和10000金币，可再次输入 admin 领取',
 V39_ADMIN_LIMIT='金币或钻石已接近上限，暂时无法领取',
 GEMS_RESTORE_TITLE='兑换码',GEMS_RESTORE_TIP='请输入兑换码',
 GEMS_RESTORE_DES='输入兑换码领取奖励',GEMS_RESTORE_BUTTON_TITLE='兑换',
 V41_GEMS_REQUIRED='钻石不足，请先兑换钻石')
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
 target=append_stub(symbol,shift);b[site:site+4]=bl(site,target) if symbol in ('offlineGarden','offlineOwn','offlineSave','offlineBoardLoad','offlineTrainingFinishPrompt','offlineFinishCurrencyText') else struct.pack('<I',0xea000000|(((target-site-8)//4)&0xffffff))
 patches.append(dict(site=hex(site),symbol=symbol,before=before.hex(),after=bytes(b[site:site+4]).hex()))
assert struct.unpack_from('<I',b,0x107bf08)[0]>>24==0xeb
patch(0x107bf08,'offlineGarden')
patch(0x100b4c0,'offlineOwn',bl(0x100b4c0,0x85e7d8))
patch(0x1042f78,'offlineSave',bl(0x1042f78,0xf87cc4),True)
patch(0x1043028,'offlineInfo',bytes.fromhex('f0482de9'),True)
patch(0x1042fe8,'offlineAttack',bytes.fromhex('f0482de9'),True)
if VERSION>=44:patch(0x350570,'offlineBoardLoad',bl(0x350570,0x2258d8),True)
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

# Intercept the original submit methods before throttling or server requests.
for site in (0x852420,0x84adb8):
 first=struct.unpack_from('<I',b,site)[0];assert first>>16==0xe92d
 target=custom_stub('push {r0-r4,lr}\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineRedeem"]}\ncmp r0,#0\npop {{r0-r4,lr}}\nbne handled\n.word {first}\nb #{site+4}\nhandled: bx lr')
 redirect(site,target)
# A plain code card gives the existing input dialog a reachable shop entry.
# Keep both the old lost-items picture and its decorative title banner absent.
site=0x93619c
assert bytes(b[site:site+4])==struct.pack('<I',0xea000000|(((0x935ebc-site-8)//4)&0xffffff))
b[site:site+4]=original[site:site+4]
target=append_stub('offlineCodeCard',True);b[0x9361b4:0x9361b8]=bl(0x9361b4,target)
redirect(0x936234,0x9362dc)

if VERSION>=41:
 for site,vector_offset in ((0x931da8,0xa8),(0x9333bc,0xb8)):
  first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4ff0
  target=custom_stub('push {r0-r4,lr}\nmov r2,r1\nmov r1,r0\n'+f'mov r3,#{vector_offset}\n'+baseasm()+f'bl #{symbols["offlineCoinClick"]}\ncmp r0,#0\npop {{r0-r4,lr}}\nbne handled\n.word {first}\nb #{site+4}\nhandled: bx lr')
  redirect(site,target)
 # The native currency bar already binds and refreshes the player's gem
 # balance. Its constructor explicitly hides only the gem background parent.
 site=0x10526d0;before=bytes(b[site:site+4]);assert before==bytes.fromhex('0010a0e3')
 b[site:site+4]=bytes.fromhex('0110a0e3');patches.append(dict(site=hex(site),before=before.hex(),after=bytes(b[site:site+4]).hex(),role='Show native live PvP diamond balance'))
if VERSION>=42:
 patch(0x104309c,'offlineCoinRequest',original[0x104309c:0x10430a0],True)

if VERSION>=47:
 patch(0x10554e8,'offlineTrainingFinishPrompt',bl(0x10554e8,0x108737c),True)
 # This shared prompt chooses the gem text only during the training offer.
 patch(0x10873d4,'offlineFinishCurrencyText',original[0x10873d4:0x10873d8],True)
 site=0x10870e0;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d48f0
 target=custom_stub('push {r0-r4,lr}\nmov r3,r2\nmov r2,r1\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineTrainingFinishConfirm"]}\ncmp r0,#0\npop {{r0-r4,lr}}\nbne finish_handled\n.word {first}\nb #{site+4}\nfinish_handled: bx lr')
 redirect(site,target)
 patch(0x104305c,'offlineBattleRequest',original[0x104305c:0x1043060],True)
 site=0x10448e8;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4bf0
 target=custom_stub('push {r0-r4,lr}\nsub sp,sp,#8\nstr r3,[sp]\nmov r3,r2\nmov r2,r1\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineBattleResult"]}\nadd sp,sp,#8\ncmp r0,#0\npop {{r0-r4,lr}}\nbne handled\n.word {first}\nb #{site+4}\nhandled: bx lr')
 redirect(site,target)

if VERSION>=48:
 # Wrap the actual training-page refresh, then intercept button ID 1.
 site=0x1056354;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4ff0
 target=custom_stub('push {r4,lr}\nmov r4,r0\nbl training_original\nmov r1,r4\n'+baseasm()+f'bl #{symbols["offlineTrainingDisplay"]}\npop {{r4,pc}}\ntraining_original: .word {first}\nb #{site+4}')
 redirect(site,target)
 site=0x1059300;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4ff0
 target=custom_stub('push {r0-r4,lr}\nmov r2,r1\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineTrainingClick"]}\ncmp r0,#0\npop {{r0-r4,lr}}\nbne training_handled\n.word {first}\nb #{site+4}\ntraining_handled: bx lr')
 redirect(site,target)

 site=0x104fa50;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4830
 target=custom_stub('push {r0-r4,lr}\nmov r2,r1\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineResultContinue"]}\ncmp r0,#0\npop {{r0-r4,lr}}\nbne result_handled\n.word {first}\nb #{site+4}\nresult_handled: bx lr')
 redirect(site,target)

if VERSION>=50:
 site=0x10283e4;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4ff0
 target=custom_stub('push {r4,lr}\nmov r4,r0\nbl bank_original\nmov r1,r4\n'+baseasm()+f'bl #{symbols["offlineBankReady"]}\npop {{r4,pc}}\nbank_original: .word {first}\nb #{site+4}')
 redirect(site,target)

if VERSION>=52:
 site=0x100c6ec;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4ff0
 target=custom_stub('push {r4,lr}\nmov r4,r0\nmov r1,r4\n'+baseasm()+f'bl #{symbols["offlineMapArmyPrepare"]}\nmov r0,r4\nbl map_original\nmov r1,r4\n'+baseasm()+f'bl #{symbols["offlineMapArmyReady"]}\npop {{r4,pc}}\nmap_original: .word {first}\nb #{site+4}')
 redirect(site,target)

site=0x1021f4c;word=struct.unpack_from('<I',b,site)[0];assert word>>24==0xea
delta=word&0xffffff
if delta&0x800000:delta-=1<<24
prior=site+8+4*delta
lobby_stub=custom_stub(f'push {{r0-r4,lr}}\nbl #{prior}\n'+baseasm()+f'bl #{symbols["offlineEconomyInit"]}\npop {{r0-r4,pc}}')
redirect(site,lobby_stub)
# Houdini cannot load the v38 relocated PHDR table. A dlopen-only shared
# library does not use PT_INTERP; reuse that slot for the writable cache.
# Preserve the table location/count and every LOAD, DYNAMIC, EXIDX and RELRO.
headers=[list(struct.unpack_from('<8I',b,e['e_phoff']+i*32)) for i in range(e['e_phnum'])]
assert e['e_phoff']==52 and len(headers)==8 and headers[1][0]==3
headers[index][4]=headers[index][5]=len(b)-tail['p_offset']
rw_offset=(len(b)+4095)&~4095
headers.pop(1)
headers.append([1,rw_offset,0x1b00000,0x1b00000,4096,4096,6,4096])
for i,h in enumerate(headers):struct.pack_into('<8I',b,e['e_phoff']+i*32,*h)
b.extend(bytes(rw_offset-len(b)));b.extend(bytes(4096))
assert struct.unpack_from('<I',b,28)[0]==52 and struct.unpack_from('<H',b,44)[0]==8
(OUT/'libSrc.so').write_bytes(b)
subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_economy_arm.py'),str(OUT)],cwd=ROOT,check=True)
subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_redeem_arm.py'),str(OUT)],cwd=ROOT,check=True)
if VERSION>=41:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_coin_click_arm.py'),str(OUT)],cwd=ROOT,check=True)
if VERSION>=43:subprocess.run([sys.executable,str(ROOT/('scripts/check_offline_pvp_v52_arm.py' if VERSION>=52 else 'scripts/check_offline_pvp_v51_arm.py' if VERSION>=51 else 'scripts/check_offline_pvp_v50_arm.py' if VERSION>=50 else 'scripts/check_offline_pvp_v48_arm.py' if VERSION>=48 else 'scripts/check_offline_pvp_v47_arm.py' if VERSION>=47 else 'scripts/check_offline_pvp_v46_arm.py' if VERSION>=46 else 'scripts/check_offline_pvp_v45_arm.py' if VERSION>=45 else 'scripts/check_offline_pvp_scenes_arm.py')),str(OUT)],cwd=ROOT,check=True)
if '--native-only' in sys.argv:raise SystemExit(0)
scratch=Path(sys.argv[sys.argv.index('--intermediate-dir')+1]).resolve() if '--intermediate-dir' in sys.argv else OUT
scratch.mkdir(parents=True,exist_ok=True)
unsigned=scratch/'unsigned.apk';aligned=scratch/'aligned.apk';final=OUT/(f'PvZ2-v{VERSION}-pvp-scene-candidate.apk' if VERSION>=43 else f'PvZ2-v{VERSION}-startup-admin-candidate.apk')
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
