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
ROOT=Path(__file__).resolve().parents[1];VERSION=86 if '--v86' in sys.argv else 85 if '--v85' in sys.argv else 84 if '--v84' in sys.argv else 83 if '--v83' in sys.argv else 82 if '--v82' in sys.argv else 81 if '--v81' in sys.argv else 80 if '--v80' in sys.argv else 79 if '--v79' in sys.argv else 78 if '--v78' in sys.argv else 77 if '--v77' in sys.argv else 76 if '--v76' in sys.argv else 75 if '--v75' in sys.argv else 74 if '--v74' in sys.argv else 73 if '--v73' in sys.argv else 72 if '--v72' in sys.argv else 71 if '--v71' in sys.argv else 70 if '--v70' in sys.argv else 69 if '--v69' in sys.argv else 68 if '--v68' in sys.argv else 67 if '--v67' in sys.argv else 66 if '--v66' in sys.argv else 65 if '--v65' in sys.argv else 64 if '--v64' in sys.argv else 63 if '--v63' in sys.argv else 62 if '--v62' in sys.argv else 61 if '--v61' in sys.argv else 60 if '--v60' in sys.argv else 59 if '--v59' in sys.argv else 58 if '--v58' in sys.argv else 57 if '--v57' in sys.argv else 56 if '--v56' in sys.argv else 55 if '--v55' in sys.argv else 54 if '--v54' in sys.argv else 53 if '--v53' in sys.argv else 52 if '--v52' in sys.argv else 51 if '--v51' in sys.argv else 50 if '--v50' in sys.argv else 49 if '--v49' in sys.argv else 48 if '--v48' in sys.argv else 47 if '--v47' in sys.argv else 46 if '--v46' in sys.argv else 45 if '--v45' in sys.argv else 44 if '--v44' in sys.argv else 43 if '--v43' in sys.argv else 42 if '--v42' in sys.argv else 41 if '--v41' in sys.argv else 40 if '--v40' in sys.argv else 39
OUT=ROOT/(f'work/pvp-v{VERSION}-test' if '--shop-clock-test' in sys.argv else f'work/pvp-v{VERSION}');OUT.mkdir(exist_ok=True)
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
if VERSION>=59:
 from prepare_offline_pvp_no_rank import prepare as prepare_no_rank
 resource,no_rank_record=prepare_no_rank(resource,OUT/'generated');economy_record['no_rank']=no_rank_record
if VERSION>=68:
 from prepare_offline_dave_dialogue import prepare as prepare_dialogue
 resource,dialogue_record=prepare_dialogue(resource,OUT/'generated');economy_record['dave_dialogue']=dialogue_record
from prepare_offline_progression import prepare as prepare_progression
economy_record['progression']=prepare_progression(resource,OUT/'generated')
if VERSION>=63:
 from prepare_offline_evolution import prepare as prepare_evolution
 economy_record['evolution']=prepare_evolution(resource,OUT/'generated')
if VERSION>=65:
 from prepare_offline_research import prepare as prepare_research
 economy_record['research']=prepare_research(resource,OUT/'generated')
if VERSION>=71:
 from prepare_offline_exchange import prepare as prepare_exchange
 economy_record['exchange']=prepare_exchange(resource,OUT/'generated')
 if VERSION>=73:
  economy_record['exchange']['automatic_refresh_implemented']=True
  economy_record['exchange']['temporary_shop_clock_test']='--shop-clock-test' in sys.argv
  (OUT/'generated/exchange-presets.json').write_text(json.dumps(economy_record['exchange'],ensure_ascii=False,indent=2)+'\n',encoding='utf8')
if VERSION>=83:
 from prepare_offline_pvp_drag import prepare as prepare_drag
 resource,drag_record=prepare_drag(resource,OUT/'generated');economy_record['drag']=drag_record
if VERSION>=66:
 from prepare_offline_dave import prepare as prepare_dave
 economy_record['dave']=prepare_dave(OUT/'generated')
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
 if VERSION>=59:
  previous=economy_record['no_rank']['predecessor_sha256']
  extra+=f'\n\n    const-string v0, "{previous}"\n    invoke-virtual {{v0, p0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n    move-result v0\n    if-eqz v0, :v59_older_versions\n    const/4 v0, 0x1\n    return v0\n    :v59_older_versions'
 if VERSION>=68:
  previous=economy_record['dave_dialogue']['predecessor_sha256']
  extra+=f'\n\n    const-string v0, "{previous}"\n    invoke-virtual {{v0, p0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n    move-result v0\n    if-eqz v0, :v68_older_versions\n    const/4 v0, 0x1\n    return v0\n    :v68_older_versions'
 if VERSION>=83:
  previous=economy_record['drag']['predecessor_sha256']
  extra+=f'\n\n    const-string v0, "{previous}"\n    invoke-virtual {{v0, p0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n    move-result v0\n    if-eqz v0, :v83_older_versions\n    const/4 v0, 0x1\n    return v0\n    :v83_older_versions'
 marker=f'.offline-pvp-v59-{newsha[:12]}' if VERSION>=59 else '.offline-pvp-v47' if VERSION>=47 else '.offline-pvp-v43' if VERSION>=43 else '.offline-economy-v38'
 dex=rebuild_bootstrap(src.read('classes8.dex'),OUT/'bootstrap',{oldsha:newsha,method:method+extra,'.offline-defense-v35':marker,hex(len(old_resource)):hex(len(resource))},ROOT/'tools/apktool.jar')
if VERSION>=58:
 from prepare_offline_pvp_skill_art import prepare as prepare_art
 with zipfile.ZipFile(BASE) as art_src:old_art=art_src.read('assets/reconstruction/zombie2-pvp.rsb.smf')
 skill_art,art_record=prepare_art(old_art,OUT/'generated');economy_record['skill_art']=art_record
 old_art_sha=art_record['predecessor_sha256'];art_predecessor=art_record['sha256']
 if VERSION>=61:
  from prepare_offline_pvp_seagull import prepare as prepare_seagull
  legacy=Path(sys.argv[sys.argv.index('--legacy-zombie1')+1]) if '--legacy-zombie1' in sys.argv else ROOT/'work/pvp-v61/original175-zombie1.smf'
  skill_art,seagull_record=prepare_seagull(skill_art,legacy.read_bytes(),OUT/'generated');economy_record['seagull']=seagull_record
 new_art_sha=hashlib.sha256(skill_art).hexdigest()
 art_method='.method private static isPvpResourcePredecessor(Ljava/lang/String;)Z\n    .registers 2'
 art_extra=f'\n\n    const-string v0, "{old_art_sha}"\n    invoke-virtual {{v0, p0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n    move-result v0\n    if-eqz v0, :v58_art_predecessors\n    const/4 v0, 0x1\n    return v0\n    :v58_art_predecessors'
 if VERSION>=61:
  art_extra+=f'\n\n    const-string v0, "{art_predecessor}"\n    invoke-virtual {{v0, p0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n    move-result v0\n    if-eqz v0, :v61_art_predecessors\n    const/4 v0, 0x1\n    return v0\n    :v61_art_predecessors'
 art_marker=('.pvp-seagull-v61-' if VERSION>=61 else '.pvp-art-v58-')+new_art_sha[:12]
 dex=rebuild_bootstrap(dex,OUT/'bootstrap-art',{old_art_sha:new_art_sha,art_method:art_method+art_extra,'.pvp-skills-v32-'+old_art_sha[:12]:art_marker,hex(len(old_art)):hex(len(skill_art))},ROOT/'tools/apktool.jar')
if VERSION>=86:
 from build_preset_importer import build as build_profile_importer
 importer_dex=build_profile_importer(OUT/'profile-importer')
 call_import='    invoke-direct {p0}, Lcom/popcap/pvz2cthd/BootActivity;->applyPvpSkillResource()V'
 dex=rebuild_bootstrap(dex,OUT/'bootstrap-profile-import',{call_import:call_import+'\n\n    invoke-static {p0}, Lcom/popcap/pvz2cthd/PresetProfileImporter;->apply(Landroid/content/Context;)V'},ROOT/'tools/apktool.jar')
 with zipfile.ZipFile(BASE) as preset_src:
  assert 'classes9.dex' not in preset_src.namelist()
  assert hashlib.sha256(preset_src.read('assets/pvz2tool/saves/save_1/pp.dat')).hexdigest()=='ee08d895f7fb56670f8cb834896e6c90d8f67ab37a28f7404dd35425ae73b0c6'

strings.update(V39_ADMIN_GRANTED='获得100钻石和10000金币，可再次输入 admin 领取',
 V39_ADMIN_LIMIT='金币或钻石已接近上限，暂时无法领取',
 GEMS_RESTORE_TITLE='兑换码',GEMS_RESTORE_TIP='请输入兑换码',
 GEMS_RESTORE_DES='输入兑换码领取奖励',GEMS_RESTORE_BUTTON_TITLE='兑换',
 V41_GEMS_REQUIRED='钻石不足，请先兑换钻石',V54_UPGRADE_BUSY='已有升级进行中，请先完成当前升级',V54_BASE_LEVEL_REQUIRED='请先升级基地，再升级此设施')
if VERSION>=63:strings['V63_EVOLUTION_FINISH_TIP']='花费{NUMBER}钻石立即完成本次僵尸进阶？'
if VERSION>=65:strings['V65_RESEARCH_FINISH_TIP']='花费{NUMBER}钻石立即完成本次技能研究？'
if VERSION>=71:strings.update(V71_EXCHANGE_REFRESH_PENDING='商品刷新将在下一步恢复，本轮请先验证兑换。',V71_EXCHANGE_MEDALS_REQUIRED='奖章不足，暂时无法兑换。')
if VERSION>=82:strings['V82_REPOSITION_ONLY']='商铺只能调整现有植物的位置，不能增减或替换植物。'
if VERSION>=80:strings.update(V80_ARMY_REQUIRED='没有可出战的僵尸，请先在训练场训练。',V80_BUSINESS_OWNED='这处商铺已属于您。')
if VERSION>=66:strings['V66_DAVE_FINISHED']='已完成邪恶戴夫的六轮挑战。'
b,localization=add_exchange_localization(b,strings)
e=ELFFile(BytesIO(b));index,tail=[(i,s) for i,s in enumerate(e.iter_segments()) if s['p_type']=='PT_LOAD'][-1]
old=len(b);assert tail['p_offset']+tail['p_filesz']==old
while len(b)%4:b.append(0)
entry=tail['p_vaddr']+len(b)-tail['p_offset']
compiler='Y:/Android/Sdk/ndk/27.0.12077973/toolchains/llvm/prebuilt/windows-x86_64/bin/clang++.exe'
flags=['--target=armv7a-linux-androideabi21','-marm','-Os','-fPIC','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-exceptions','-fno-rtti','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-I'+str(OUT/'generated')]
if VERSION>=57:flags.append('-DPVP_RECT_SKILLS')
if VERSION>=60:flags.append('-DPVP_BATTLE_ECONOMY')
if VERSION>=62:flags.append('-DPVP_LAB_ROSTER')
if VERSION>=63:flags.append('-DPVP_EVOLUTION')
if VERSION>=64:flags.append('-DPVP_SKILL_LAB')
if VERSION>=65:flags.append('-DPVP_SKILL_RESEARCH')
if VERSION>=66:flags.append('-DPVP_DAVE_ROUNDS')
if VERSION>=67:flags.append('-DPVP_DAVE_LABEL')
if VERSION>=68:flags.append('-DPVP_DAVE_NARRATIVE')
if VERSION>=69:flags.append('-DPVP_STAR_DISPLAY')
if VERSION>=71:flags.append('-DPVP_EXCHANGE')
if VERSION>=72:flags.append('-DPVP_EXCHANGE_REFRESH')
if VERSION>=73:flags.append('-DPVP_EXCHANGE_CLOCK')
if VERSION>=74:flags.append('-DPVP_RESIDENT_NEIGHBORS')
if VERSION>=75:flags.append('-DPVP_LOCAL_DEFENSE_SESSION')
if VERSION>=76:flags.append('-DPVP_DEFENSE_FINISH')
if VERSION>=77:flags.append('-DPVP_BUSINESS_MAP')
if VERSION>=78:flags.append('-DPVP_BUSINESS_OWNER')
if VERSION>=79:flags.append('-DPVP_BUSINESS_SCOUT')
if VERSION>=80:flags.append('-DPVP_BUSINESS_BATTLE')
if VERSION>=81:flags.append('-DPVP_BUSINESS_DEFENSE')
if VERSION>=82:flags.append('-DPVP_GARRISON_REPOSITION')
if VERSION>=84:flags.append('-DPVP_DEFENSE_DESKTOP_CURSOR')
if '--shop-clock-test' in sys.argv:flags.append('-DPVP_EXCHANGE_CLOCK_TEST')
subprocess.run([compiler,*flags,'-c',str(ROOT/'src/offline-pvp/offline.cpp'),'-o',str(OUT/'offline.o')],check=True)
# A flat payload has no dynamic relocation table. Absolute pointer constants
# would work at base zero in analysis and crash after Android relocates the SO.
objects=[OUT/'offline.o']
if VERSION>=85:
 subprocess.run([compiler,*flags,'-DDESKTOP_PVP_SEEDS','-c',str(ROOT/'src/desktop-input/shortcuts.cpp'),'-o',str(OUT/'desktop-input.o')],check=True)
 objects.append(OUT/'desktop-input.o')
for object_path in objects:
 obj=ELFFile(BytesIO(object_path.read_bytes()))
 for sec in obj.iter_sections():
  if sec['sh_type']=='SHT_REL' and 'exidx' not in sec.name:
   assert all(r['r_info_type']!=2 for r in sec.iter_relocations()),'payload contains R_ARM_ABS32'

(OUT/'flat.ld').write_text(f'ENTRY(offlineGarden)\nSECTIONS {{ . = {entry}; .payload : {{ *(.text.entry) *(.text*) *(.rodata*) }} . = 0x1b00000; .runtime : {{ *(.data*) *(.bss*) *(COMMON) *(.got*) }} /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }} }}')
subprocess.run([compiler,*flags,'-nostdlib','-static','-no-pie','-Wl,--no-undefined','-Wl,-T,'+str(OUT/'flat.ld'),*[str(p) for p in objects],'-o',str(OUT/'offline.elf')],check=True)
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

if VERSION>=53:
 # PVPSeedPacket's ready transition has already updated its state and restored
 # registers at this tail branch. Omit only the standalone card-effect entity.
 site=0x102e664;before=bytes(b[site:site+4]);assert before==struct.pack('<I',0xea000000|(((0x8ab100-site-8)//4)&0xffffff))
 b[site:site+4]=struct.pack('<I',0xe12fff1e)
 patches.append(dict(site=hex(site),before=before.hex(),after=bytes(b[site:site+4]).hex(),role='Omit decorative PvP ready-card flash after state update'))
 # The skill/counter notification still runs. Its final word-effect spawn is
 # decorative, like the already omitted defense-return flash from v36.
 site=0x102f858;before=bytes(b[site:site+4]);assert before==bl(site,0x8ab228)
 b[site:site+4]=struct.pack('<I',0xe1a00000)
 patches.append(dict(site=hex(site),before=before.hex(),after=bytes(b[site:site+4]).hex(),role='Omit persistent decorative PvP skill/counter word flash'))
 for a,z in ((0x102e5c0,0x102e664),(0x102f43c,0x102f858)):
  assert b[a:z]==original[a:z],'gameplay changed before cosmetic flash'

if VERSION>=54:
 patch(0x107483c,'offlineTrainingFinishPrompt',bl(0x107483c,0x108737c),True)
 site=0x1078334;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4ff0
 target=custom_stub('push {r4,lr}\nmov r4,r0\nbl upgrade_draw_original\nmov r1,r4\n'+baseasm()+f'bl #{symbols["offlineUpgradeDisplay"]}\npop {{r4,pc}}\nupgrade_draw_original: .word {first}\nb #{site+4}')
 redirect(site,target)
 site=0x107486c;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4818
 target=custom_stub('push {r0-r4,lr}\nmov r2,r1\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineUpgradeClick"]}\ncmp r0,#0\npop {{r0-r4,lr}}\nbne upgrade_handled\n.word {first}\nb #{site+4}\nupgrade_handled: bx lr')
 redirect(site,target)

if VERSION>=55:
 # PVZ zombie-card return already increments the packet before spawning WORD_EFFECT.
 site=0x290f24;before=bytes(b[site:site+4]);assert before==bl(site,0x8ab228)
 b[site:site+4]=struct.pack('<I',0xe1a00000)
 patches.append(dict(site=hex(site),before=before.hex(),after=bytes(b[site:site+4]).hex(),role='Omit zombie-return decoration after native card refund'))
 # AddEnergyEffect state 3 spawns a detached landing flash, then state 4
 # performs its timed gameplay callback. Skip only the detached flash block.
 site=0x10402cc;before=bytes(b[site:site+4]);assert before==original[site:site+4]
 redirect(site,0x10404b4)

if VERSION>=59:
 site=0x107bb98;before=bytes(b[site:site+8]);assert before==original[site:site+8]
 b[site:site+8]=bytes.fromhex('0000a0e31eff2fe1') # mov r0,#0; bx lr: no rank window/request.
 patches.append(dict(site=hex(site),role='Remove PvP league/rank window factory',before=before.hex(),after=bytes(b[site:site+8]).hex()))

if VERSION>=62:
 # Observe the real lab button receiver before its original dispatcher runs.
 site=0x10726e4;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4818
 target=custom_stub('push {r0-r4,lr}\nmov r2,r1\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineLabRoster"]}\npop {{r0-r4,lr}}\n.word {first}\nb #{site+4}')
 redirect(site,target)
 # Retain the actual property lookup and its result. Only caller-local lab
 # observations are logged; no null fallback changes gameplay or hides errors.
 if VERSION==62:
  site=0xb82878;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4870
  target=custom_stub('push {r4-r8,lr}\nmov r4,r0\nmov r6,lr\nbl lab_props_original\nmov r5,r0\nmov r1,r4\nmov r2,r5\nmov r3,r6\n'+baseasm()+f'bl #{symbols["offlineLabProperties"]}\nmov r0,r5\npop {{r4-r8,pc}}\nlab_props_original: .word {first}\nb #{site+4}')
  redirect(site,target)

if VERSION>=63:
 site=0x107eb28;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4ff0
 target=custom_stub('push {r4,lr}\nmov r4,r0\nmov r1,r4\n'+baseasm()+f'bl #{symbols["offlineEvolutionBuild"]}\nmov r0,r4\nbl evolution_build_original\nmov r1,r4\n'+baseasm()+f'bl #{symbols["offlineEvolutionTick"]}\npop {{r4,pc}}\nevolution_build_original: .word {first}\nb #{site+4}')
 redirect(site,target)
 site=0x107cd10;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d48f0
 target=custom_stub('push {r4,lr}\nmov r4,r0\nbl evolution_tick_original\nmov r1,r4\n'+baseasm()+f'bl #{symbols["offlineEvolutionTick"]}\npop {{r4,pc}}\nevolution_tick_original: .word {first}\nb #{site+4}')
 redirect(site,target)
 site=0x1080e28;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d48f0
 target=custom_stub('push {r0-r4,lr}\nmov r2,r1\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineEvolutionClick"]}\ncmp r0,#0\npop {{r0-r4,lr}}\nbne evolution_handled\n.word {first}\nb #{site+4}\nevolution_handled: bx lr')
 redirect(site,target)

if VERSION>=64:
 site=0x1083ab8;assert bytes(b[site:site+4])==bl(site,0xa45450)
 target=custom_stub('push {r4,lr}\nmov r2,r1\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineSkillName"]}\npop {{r4,pc}}')
 b[site:site+4]=bl(site,target);patches.append(dict(site=hex(site),symbol='offlineSkillName',role='Guard only empty skill-page title selection'))

if VERSION>=65:
 site=0x108531c;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4810
 target=custom_stub('push {r0-r4,lr}\nmov r2,r1\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineResearchClick"]}\ncmp r0,#0\npop {{r0-r4,lr}}\nbne research_handled\n.word {first}\nb #{site+4}\nresearch_handled: bx lr')
 redirect(site,target)
 site=0x1083d88;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4ff0
 target=custom_stub('push {r0-r4,lr}\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineResearchTick"]}\npop {{r0-r4,lr}}\n.word {first}\nb #{site+4}')
 redirect(site,target)
 # Only the skill purchase renderer uses a regular, locally labelled button.
 # Its real timer stays in manager+6c/70/74 and is not reset for this layout.
 site=0x1084200;assert bytes(b[site:site+4])==bl(site,0x1083754)
 target=custom_stub('push {r4,lr}\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineResearchRemaining"]}\npop {{r4,pc}}')
 b[site:site+4]=bl(site,target);patches.append(dict(site=hex(site),symbol='offlineResearchRemaining',role='Use normal local skill button; preserve tutorial and other skill paths'))

if VERSION>=67:
 site=0x10129f0;assert bytes(b[site:site+4])==bl(site,0x100cc74)
 target=custom_stub('push {r0-r4,lr}\nmov r1,r2\n'+baseasm()+f'bl #{symbols["offlineDaveLabel"]}\npop {{r0-r4,lr}}\nb #0x100cc74')
 b[site:site+4]=bl(site,target);patches.append(dict(site=hex(site),symbol='offlineDaveLabel',role='Project saved Dave counter immediately before native map title formatting'))

if VERSION>=68:
 site=0x100ad18;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4ff0
 target=custom_stub('push {r0-r4,lr}\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineDaveNarrative"]}\ncmp r0,#0\npop {{r0-r4,lr}}\nbne narrative_handled\n.word {first}\nb #{site+4}\nnarrative_handled: bx lr')
 redirect(site,target)
 for site in (0x100906c,0x10090c4):
  first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4818
  target=custom_stub('push {r0-r4,lr}\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineDaveNarrativeAck"]}\ncmp r0,#0\npop {{r0-r4,lr}}\nbne narrative_ack_handled\n.word {first}\nb #{site+4}\nnarrative_ack_handled: bx lr')
  redirect(site,target)

if VERSION>=71:
 for site,name in ((0x106d23c,'offlineExchangePrepare'),(0x106c098,'offlineExchangeBuy')):
  first=struct.unpack_from('<I',b,site)[0];assert first&0xffff0000==0xe92d0000 and bytes(b[site:site+4])==original[site:site+4]
  target=custom_stub('push {r0-r4,lr}\nmov r2,r1\nmov r1,r0\n'+baseasm()+f'bl #{symbols[name]}\ncmp r0,#0\npop {{r0-r4,lr}}\nbne exchange_handled\n.word {first}\nb #{site+4}\nexchange_handled: bx lr')
  redirect(site,target)

if VERSION>=72:
 site=0x106e868;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4ff0
 target=custom_stub('push {r0-r4,lr}\nmov r2,r1\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineExchangeQuote"]}\npop {{r0-r4,lr}}\n.word {first}\nb #{site+4}')
 redirect(site,target)

if VERSION>=73:
 site=0x106e5d4;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4870
 target=custom_stub('push {r4,lr}\nmov r4,r0\nbl exchange_clock_original\nmov r1,r4\n'+baseasm()+f'bl #{symbols["offlineExchangeClockDraw"]}\npop {{r4,pc}}\nexchange_clock_original: .word {first}\nb #{site+4}')
 redirect(site,target)

if VERSION>=85:
 # Existing Java key/hover/right-button queue is unchanged. Only replace the
 # old native command entry with the rebuilt bridge; ordinary keys keep its
 # established UI routing and hover path.
 site=0x1a010a4;file_at=tail['p_offset']+site-tail['p_vaddr']
 before=bytes(b[file_at:file_at+4]);assert struct.unpack('<I',before)[0]==0xe92d4ff0
 b[file_at:file_at+4]=struct.pack('<I',0xea000000|(((symbols['desktopInput']-site-8)//4)&0xffffff))
 patches.append(dict(site=hex(site),file_offset=hex(file_at),symbol='desktopInput',before=before.hex(),after=bytes(b[file_at:file_at+4]).hex()))

if VERSION>=84:
 # After the native existing-plant cursor constructor, before AddCursor.
 # Keep the constructor's stack arguments and all original drag callbacks.
 site=0x22a48c;assert b[site:site+4]==bytes.fromhex('0500a0e1')
 target=custom_stub('push {r0-r4,lr}\nmov r1,r5\nmov r2,sl\n'+baseasm()+f'bl #{symbols["offlineDefenseCursorReady"]}\npop {{r0-r4,lr}}\nmov r0,r5\nb #{site+4}')
 redirect(site,target)

if VERSION>=78:
 # The server user-id parser returns zero offline, colliding with the
 # unoccupied-owner sentinel. Native map labels and panel selection share it.
 site=0x10445e8;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4830
 target=custom_stub('push {r0-r4,lr}\n'+baseasm()+f'bl #{symbols["offlineBusinessIdentity"]}\ncmp r0,#0\nbeq business_identity_original\nstr r0,[sp]\npop {{r0-r4,pc}}\nbusiness_identity_original: pop {{r0-r4,lr}}\n.word {first}\nb #{site+4}')
 redirect(site,target)

if VERSION>=77:
 # The native panel button and large attack hit-test both lead to legacy
 # network requests. Scope the entrance-only guard to our unoccupied plots.
 for site,name in ((0x100b3d8,'offlineBusinessAction'),(0x101a564,'offlineBusinessRaidInput')):
  first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4ff0
  target=custom_stub('push {r0-r4,lr}\nmov r2,r1\nmov r1,r0\n'+baseasm()+f'bl #{symbols[name]}\ncmp r0,#0\npop {{r0-r4,lr}}\nbne business_handled\n.word {first}\nb #{site+4}\nbusiness_handled: bx lr')
  redirect(site,target)

if VERSION>=69:
 site=0x109e438;first=struct.unpack_from('<I',b,site)[0];assert first==0xe92d4830
 target=custom_stub('push {r0-r4,lr}\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineStarAnimation"]}\ncmp r0,#0\npop {{r0-r4,lr}}\nbne star_animation_handled\n.word {first}\nb #{site+4}\nstar_animation_handled: bx lr')
 redirect(site,target)
 for slot,site in enumerate((0x109e9c0,0x109e9fc,0x109ea30)):
  assert bytes(b[site:site+4])==bl(site,0x11694c8)
  target=custom_stub('push {r4,lr}\nsub sp,sp,#16\nstr r2,[sp]\nstr r3,[sp,#4]\n'+f'mov r4,#{slot}\nstr r4,[sp,#8]\nmov r3,r1\nmov r2,r0\nldr r1,[fp,#-0x54]\n'+baseasm()+f'bl #{symbols["offlineStarDraw"]}\nadd sp,sp,#16\npop {{r4,pc}}')
  b[site:site+4]=bl(site,target);patches.append(dict(site=hex(site),symbol='offlineStarDraw',slot=slot,role='Draw earned star using original lit image and native coordinates'))

if VERSION>=57:
 def range_call(site,target,expected,name):
  assert bytes(b[site:site+4])==bl(site,expected),hex(site)
  b[site:site+4]=bl(site,target);patches.append(dict(site=hex(site),symbol=name))
 for site,name in [(0x10067f0,'offlineFoodTargets'),(0x1007924,'offlineRageTargets')]:
  target=custom_stub('push {r4,lr}\nsub sp,sp,#8\nstr r3,[sp]\nmov r3,r2\nmov r2,r1\nmov r1,r0\n'+baseasm()+f'bl #{symbols[name]}\nadd sp,sp,#8\npop {{r4,pc}}')
  range_call(site,target,0xbf52c0,name)
 for site,name in [(0x1001a60,'offlineAidContains'),(0x10060cc,'offlineFogContains')]:patch(site,name,original[site:site+4],True)
 target=custom_stub('push {r4,lr}\nmov r3,r2\nmov r2,r0\nmov r1,r6\n'+baseasm()+f'bl #{symbols["offlineSkillCursorTargets"]}\npop {{r4,pc}}')
 range_call(0x105a220,target,0xbf52c0,'offlineSkillCursorTargets')
 target=custom_stub('push {r4,lr}\nsub sp,sp,#8\nstr r3,[sp]\nstr r5,[sp,#4]\nmov r3,r2\nmov r2,r1\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineSkillScope"]}\nadd sp,sp,#8\npop {{r4,pc}}')
 range_call(0x209a90,target,0x207088,'offlineSkillScope')
 # Three arguments including base; do not use the five-argument shift stub.
 target=custom_stub('push {r4,lr}\nmov r2,r1\nmov r1,r0\n'+baseasm()+f'bl #{symbols["offlineSkillScopeRect"]}\npop {{r4,pc}}')
 range_call(0x207298,target,0x1167128,'offlineSkillScopeRect')

site=0x1021f4c;word=struct.unpack_from('<I',b,site)[0];assert word>>24==0xea
delta=word&0xffffff
if delta&0x800000:delta-=1<<24
prior=site+8+4*delta
lobby_init='offlineProgressionInit' if VERSION>=54 else 'offlineEconomyInit'
lobby_stub=custom_stub(f'push {{r0-r4,lr}}\nbl #{prior}\n'+baseasm()+f'bl #{symbols[lobby_init]}\npop {{r0-r4,pc}}')
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
if '--compile-only' in sys.argv:raise SystemExit(0)
subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_economy_arm.py'),str(OUT)],cwd=ROOT,check=True)
subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_redeem_arm.py'),str(OUT)],cwd=ROOT,check=True)
if VERSION>=41:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_coin_click_arm.py'),str(OUT)],cwd=ROOT,check=True)
if 43<=VERSION<63:subprocess.run([sys.executable,str(ROOT/('scripts/check_offline_pvp_v56_arm.py' if VERSION>=56 else 'scripts/check_offline_pvp_v55_arm.py' if VERSION>=55 else 'scripts/check_offline_pvp_v54_arm.py' if VERSION>=54 else 'scripts/check_offline_pvp_v52_arm.py' if VERSION>=52 else 'scripts/check_offline_pvp_v51_arm.py' if VERSION>=51 else 'scripts/check_offline_pvp_v50_arm.py' if VERSION>=50 else 'scripts/check_offline_pvp_v48_arm.py' if VERSION>=48 else 'scripts/check_offline_pvp_v47_arm.py' if VERSION>=47 else 'scripts/check_offline_pvp_v46_arm.py' if VERSION>=46 else 'scripts/check_offline_pvp_v45_arm.py' if VERSION>=45 else 'scripts/check_offline_pvp_scenes_arm.py')),str(OUT)],cwd=ROOT,check=True)
if VERSION>=57:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v57_arm.py'),str(OUT)],cwd=ROOT,check=True)
if VERSION==59:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v59_arm.py'),str(OUT)],cwd=ROOT,check=True)
if 60<=VERSION<63:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v60_arm.py'),str(OUT)],cwd=ROOT,check=True)
if VERSION==62:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v62_arm.py'),str(OUT)],cwd=ROOT,check=True)
if VERSION==63:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v63_arm.py'),str(OUT)],cwd=ROOT,check=True)
if VERSION==64:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v64_arm.py'),str(OUT)],cwd=ROOT,check=True)
if VERSION==65:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v65_arm.py'),str(OUT)],cwd=ROOT,check=True)
if VERSION==66:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v66_arm.py'),str(OUT)],cwd=ROOT,check=True)
if VERSION==67:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v67_arm.py'),str(OUT)],cwd=ROOT,check=True)
if VERSION==68:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v68_arm.py'),str(OUT)],cwd=ROOT,check=True)
if VERSION==69:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v69_arm.py'),str(OUT)],cwd=ROOT,check=True)
if VERSION==70:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v70_arm.py'),str(OUT)],cwd=ROOT,check=True)
if VERSION==71:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v71_arm.py'),str(OUT)],cwd=ROOT,check=True)
if VERSION==72:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v72_arm.py'),str(OUT)],cwd=ROOT,check=True)
if VERSION>=73:subprocess.run([sys.executable,str(ROOT/('scripts/check_offline_pvp_v82_focused.py' if VERSION>=82 else 'scripts/check_offline_pvp_v81_focused.py' if VERSION>=81 else 'scripts/check_offline_pvp_v80_focused.py' if VERSION>=80 else 'scripts/check_offline_pvp_v79_focused.py' if VERSION>=79 else 'scripts/check_offline_pvp_v78_focused.py' if VERSION>=78 else 'scripts/check_offline_pvp_v77_focused.py' if VERSION>=77 else 'scripts/check_offline_pvp_v76_focused.py' if VERSION==76 else 'scripts/check_offline_pvp_v75_arm.py' if VERSION>=75 else 'scripts/check_offline_pvp_v74_arm.py' if VERSION>=74 else 'scripts/check_offline_pvp_v73_arm.py')),str(OUT)],cwd=ROOT,check=True)
if VERSION>=83:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v83_drag.py'),str(OUT)],cwd=ROOT,check=True)
if VERSION>=84:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v84_cursor.py'),str(OUT)],cwd=ROOT,check=True)
if VERSION>=85:subprocess.run([sys.executable,str(ROOT/'scripts/check_input_v23_native.py'),str(OUT)],cwd=ROOT,check=True)
if '--native-only' in sys.argv:raise SystemExit(0)
scratch=Path(sys.argv[sys.argv.index('--intermediate-dir')+1]).resolve() if '--intermediate-dir' in sys.argv else OUT
scratch.mkdir(parents=True,exist_ok=True)
unsigned=scratch/'unsigned.apk';aligned=scratch/'aligned.apk';final=OUT/(f'PvZ2-v{VERSION}-shop-clock-test.apk' if '--shop-clock-test' in sys.argv else f'PvZ2-v{VERSION}-pvp-scene-candidate.apk' if VERSION>=43 else f'PvZ2-v{VERSION}-startup-admin-candidate.apk')
with zipfile.ZipFile(BASE) as src,zipfile.ZipFile(unsigned,'w',allowZip64=True) as dst:
 for item in src.infolist():
  if item.filename.startswith('META-INF/'):continue
  if item.filename=='lib/armeabi/libSrc.so':dst.writestr(item,b)
  elif VERSION>=58 and item.filename=='assets/reconstruction/zombie2-pvp.rsb.smf':dst.writestr(item,skill_art)
  elif item.filename=='classes8.dex':dst.writestr(item,dex)
  elif item.filename=='assets/reconstruction/dynamic-original-speed.rsb.smf':dst.writestr(item,resource)
  else:
   with src.open(item) as a,dst.open(item,'w') as z:shutil.copyfileobj(a,z,1048576)
if VERSION>=86:
 with zipfile.ZipFile(unsigned,'a') as dst:dst.writestr('classes9.dex',importer_dex)
subprocess.run(['K:/pvz2-tools/android-build-tools/android-14/zipalign.exe','-f','4',str(unsigned),str(aligned)],check=True)
subprocess.run(['java','-jar','K:/pvz2-tools/android-build-tools/android-14/lib/apksigner.jar','sign','--ks',str(ROOT/'work/keys/recovered-debug.keystore'),'--ks-pass','pass:android','--key-pass','pass:android','--ks-key-alias','androiddebugkey','--out',str(final),str(aligned)],check=True)
subprocess.run(['java','-jar','K:/pvz2-tools/android-build-tools/android-14/lib/apksigner.jar','verify',str(final)],check=True)
subprocess.run(['K:/pvz2-tools/android-build-tools/android-14/zipalign.exe','-c','4',str(final)],check=True)
with zipfile.ZipFile(BASE) as src,zipfile.ZipFile(final) as dst:
 for item in src.infolist():
  if item.filename.startswith('META-INF/') or item.filename in ('lib/armeabi/libSrc.so','classes8.dex','assets/reconstruction/dynamic-original-speed.rsb.smf') or (VERSION>=58 and item.filename=='assets/reconstruction/zombie2-pvp.rsb.smf'):continue
  assert dst.getinfo(item.filename).CRC==item.CRC and dst.getinfo(item.filename).file_size==item.file_size,item.filename
record=dict(apk=str(final.relative_to(ROOT)),sha256=hashlib.file_digest(final.open('rb'),'sha256').hexdigest(),patches=patches,economy=economy_record,localization=localization,entry=hex(entry),symbols={k:hex(v) for k,v in symbols.items() if k.startswith('offline')},runtime_verified=False)
if VERSION>=85:record['desktop_input']=dict(previous_entry='0x1a010a4',entry=hex(symbols['desktopInput']),source='src/desktop-input/shortcuts.cpp',source_sha256=hashlib.sha256((ROOT/'src/desktop-input/shortcuts.cpp').read_bytes()).hexdigest(),scope='home defense visible plant bank; original UI click routing')
if VERSION>=86:record['preset_import']=dict(source_asset='assets/pvz2tool/saves/save_1/pp.dat',source_sha256='ee08d895f7fb56670f8cb834896e6c90d8f67ab37a28f7404dd35425ae73b0c6',plant_count=109,tier=1,independent_profile=True,source_sha256_java=hashlib.sha256((ROOT/'src/bootstrap-extra/com/popcap/pvz2cthd/PresetProfileImporter.java').read_bytes()).hexdigest())
(OUT/'build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
if VERSION==61:subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_seagull.py'),str(OUT)],cwd=ROOT,check=True)
