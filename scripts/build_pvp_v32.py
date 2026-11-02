"""Restore native first PvP combat tutorial and missing original skill animations.

Only the original first NPC/tutorial flow is restored here. This does not supply
an online PvP service or complete the commercial occupation mode/backend.
Requires the locally-owned original 1.7.5 zombie2 resource bundle as input.
"""
from pathlib import Path
from io import BytesIO
import ast,zipfile,struct,subprocess,os,hashlib,json,shutil,argparse,zlib
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--legacy-zombie2',type=Path,default=Path('work/pvp-v32/original175-zombie2.smf'))
parser.add_argument('--thin',action='store_true',help='Diagnostic package only; requires extracted resources')
args=parser.parse_args()
P=Path('work/pvp-v32');P.mkdir(exist_ok=True)
BASE=Path('work/pvp-v31/PvZ2-v31-offline-pvp-map.apk')
assert hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest()=='5c23a50870ddcf3844514424d4ba05cc5f386fc3d71c25359592d66885e6b385'
os.environ['TMP']=os.environ['TEMP']=str(Path('work/tmp').resolve())
with zipfile.ZipFile(BASE) as z:b=bytearray(z.read('lib/armeabi/libSrc.so'))
e=ELFFile(BytesIO(b));idx,t=[(i,x) for i,x in enumerate(e.iter_segments()) if x['p_type']=='PT_LOAD'][-1];old=len(b)
def append(asm,markers):
 while len(b)%4:b.append(0)
 va=t['p_vaddr']+len(b)-t['p_offset'];c=bytearray(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(asm,addr=va)[0])
 for m,target in markers:
  at=c.index(struct.pack('<I',m));struct.pack_into('<I',c,at,(target-va-at)&0xffffffff)
 b.extend(c);return va
def branch(a,target,link=False):struct.pack_into('<I',b,a,(0xeb000000 if link else 0xea000000)|(((target-a-8)//4)&0xffffff))
prior28=ast.parse(Path('scripts/build_pvp_v28.py').read_text(encoding='utf8'))
practice=next(ast.literal_eval(n.value) for n in ast.walk(prior28) if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='asm' for x in n.targets))
pva=append(practice,[(0x11223344,0x1821674),(0x22334455,0x1835eec),(0x33445566,0x18a6708)])
prior=ast.parse(Path('scripts/build_pvp_v31.py').read_text(encoding='utf8'))
asm=next(ast.literal_eval(n.value) for n in prior.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='asm' for x in n.targets))
asm=asm.replace('push {r4,lr}',"""push {r4,lr}
 bl #0x1df738
 bl #0x7a98dc
 cmp r0,#0
 beq initialized
 ldr r1,[r0,#0x75c]
 cmp r1,#0
 bne initialized
 mov r1,#1
 str r1,[r0,#0x75c]
 adr r4,app
 ldr r0,[r4]
 add r4,r4,r0
 ldr r4,[r4]
 ldr r4,[r4]
 add r0,r4,#0x1400
 add r0,r0,#0x28
 mov r1,#1
 bl #0x47ff94
 mov r0,r4
 bl #0x3ff4b0
 initialized:
""",1)
asm=asm.replace(' bl #0x7fa754\n ldr r1,[r0,#4]', """ bl #0x7fa754
 mov r4,r0
 bl #0x1043e68
 cmp r0,#1
 bge zone_ready
 add r0,r4,#0x54
 mov r1,#1
 mov r2,#1
 bl #0x1060f70
 zone_ready:
 mov r0,r4
 ldr r1,[r0,#4]""",1)
asm=asm.replace(' adr r4,mgr', f""" bl #0x1df738
 bl #0x7a98dc
 ldr r1,[r0,#0x75c]
 cmp r1,#3
 bne normal_lobby
 bl #{hex(pva)}
 pop {{r4,pc}}
 normal_lobby:
 adr r4,mgr""")
va=append(asm,[(0x11223344,0x1821674),(0x22334455,0x1835eec)]);branch(0x1021f4c,va)
# Restore original tutorial handler and its native completion transitions.
with zipfile.ZipFile('work/treasure-v27/PvZ2-v27-trial-transition-lucky-guide-fix.apk') as z:orig=z.read('lib/armeabi/libSrc.so')
for a in (0x107becc,0x352a7c,0x10a9714,0x10a9784,0x10a96f4,0x10a9ae4):b[a:a+4]=orig[a:a+4]
# Preserve native case-1 tutorial flags, replace only its server map request.
ma="""push {r4,lr}
 adr r4,manager
 ldr r0,[r4]
 add r4,r4,r0
 ldr r0,[r4]
 mov r1,#25
 mov r2,#0
 mov r3,#1
 bl #0x352498
 pop {r4,pc}
 manager: .word 0x55667788"""
mva=append(ma,[(0x55667788,0x1835eec)]);branch(0x107bf08,mva,True)
assert b[0xf7b700:0xf7b704].hex()=='bd23d2eb'
struct.pack_into('<I',b,0xf7b700,0xe1a00000)
assert struct.unpack_from('<I',b,0x1041acc)[0]==0xeb000000|(((0x403988-0x1041acc-8)//4)&0xffffff)
struct.pack_into('<I',b,0x1041acc,0xe3a00000)
# Tutorial-only default skill level when the offline lab has no server record.
skill="""push {r4,r5,r6,r7,r8,lr}
 sub sp,sp,#32
 mov r4,r0
 mov r5,r1
 add r0,r0,#0x3c
 bl #0x1046698
 add r6,r4,#0x40
 cmp r0,r6
 addne r6,r0,#0x14
 bne skill_done
 ldr r0,[r5]
 adr r1,skill_name
 bl #0x147998
 cmp r0,#0
 bne no_skill
 bl #0x1df738
 bl #0x7a98dc
 cmp r0,#0
 beq no_skill
 ldr r0,[r0,#0x75c]
 cmp r0,#7
 bne no_skill
 mov r0,sp
 ldr r1,[r5]
 add r2,sp,#24
 blx #0x14ed0e0
 mov r0,#1
 str r0,[sp,#4]
 str r0,[sp,#8]
 str r0,[sp,#16]
 mov r0,#0
 str r0,[sp,#12]
 mov r0,r4
 mov r1,sp
 bl #0x1048dcc
 mov r6,r0
 ldr r0,[sp]
 sub r0,r0,#12
 add r1,sp,#24
 blx #0x14ebf58
 b skill_done
 no_skill:
 mov r6,#0
 skill_done:
 mov r0,r6
 add sp,sp,#32
 pop {r4,r5,r6,r7,r8,pc}
 skill_name: .asciz "pvpskill_zombiefood"
 """
branch(0x1046764,append(skill,[]))
# Retain the small raw PVP animation group across the plant/battle transition.
pin="""push {r0,r1,r2,r3,r12,lr}
 ldr r0,[r1]
 adr r1,pin_name
 bl #0x147980
 cmp r0,#0
 pop {r0,r1,r2,r3,r12,lr}
 bxne lr
 push {r4,r5,r6,r7,r8,r9,r10,fp,lr}
 b #0x11c70e4
 pin_name: .asciz "PVP_INBATTLEANIM"
 """
branch(0x11c70e0,append(pin,[]))
ph=e['e_phoff']+idx*32
for a in (ph+16,ph+20):struct.pack_into('<I',b,a,struct.unpack_from('<I',b,a)[0]+len(b)-old)
(P/'libSrc.so').write_bytes(b)

from merge_legacy_pvp_resources import merge
from pvp_resource_bootstrap import rebuild_pvp_bootstrap
legacy=args.legacy_zombie2.read_bytes()
legacy_source_sha=hashlib.sha256(legacy).hexdigest()
if legacy[:4]==bytes.fromhex('d4feadde'):
 expected_size=struct.unpack_from('<I',legacy,4)[0]
 legacy=zlib.decompress(legacy[8:])
 assert len(legacy)==expected_size
with zipfile.ZipFile('pvz2data.zip') as resources:
 current=resources.read('com.popcap.pvz2cthd/files/zombie2.rsb.smf')
merged,groups=merge(current,legacy)
resource_sha=hashlib.sha256(merged).hexdigest()
(P/'zombie2-pvp.rsb.smf').write_bytes(merged)
with zipfile.ZipFile(BASE) as src:
 dex=rebuild_pvp_bootstrap(src.read('classes8.dex'),P/'bootstrap-final',
      hashlib.sha256(current).hexdigest(),resource_sha,len(merged),ROOT)
 name='PvZ2-v32-first-pvp-tutorial-skills'+('-diagnostic' if args.thin else '')
 unsigned=P/(name+'-unsigned.apk');aligned=P/(name+'-aligned.apk');final=P/(name+'.apk')
 with zipfile.ZipFile(unsigned,'w',allowZip64=True) as dst:
  for item in src.infolist():
   if item.filename.startswith('META-INF/') or (args.thin and item.filename.startswith('assets/pvz2data.zip.')):continue
   if item.filename=='lib/armeabi/libSrc.so':dst.writestr(item,b)
   elif item.filename=='classes8.dex':dst.writestr(item,dex)
   else:
    with src.open(item) as a,dst.open(item,'w') as c:shutil.copyfileobj(a,c,1048576)
  dst.writestr('assets/reconstruction/zombie2-pvp.rsb.smf',merged,compress_type=zipfile.ZIP_DEFLATED)
subprocess.run(['K:/pvz2-tools/android-build-tools/android-14/zipalign.exe','-f','4',str(unsigned),str(aligned)],check=True)
subprocess.run(['java','-jar','K:/pvz2-tools/android-build-tools/android-14/lib/apksigner.jar','sign','--ks','work/keys/recovered-debug.keystore','--ks-pass','pass:android','--key-pass','pass:android','--ks-key-alias','androiddebugkey','--out',str(final),str(aligned)],check=True)
record=dict(base=str(BASE),base_sha256=hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest(),
 apk=str(final),apk_sha256=hashlib.file_digest(final.open('rb'),'sha256').hexdigest(),
 native_sha256=hashlib.sha256(b).hexdigest(),resource_sha256=resource_sha,
 legacy_input_sha256=legacy_source_sha,imported_groups=groups,thin=args.thin,
 patches=['native tutorial entry and completion transitions','initial plant lab level',
 'native owned tutorial skill record','local map navigation','PVP network-fault dialog suppression',
 'retain PVP animation group'],diagnostics_included=False,
 changed_payloads=['lib/armeabi/libSrc.so','classes8.dex','assets/reconstruction/zombie2-pvp.rsb.smf'])
(P/'build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
print(json.dumps(record,indent=2))
