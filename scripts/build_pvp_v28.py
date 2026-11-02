"""Offline NPC practice entry using the game's native arena tutorial battle."""
from pathlib import Path
from io import BytesIO,StringIO
import hashlib,json,struct,shutil,zipfile,sys,os
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/pvp-v28';OUT.mkdir(exist_ok=True)
sys.path[:0]=[str(ROOT/'src/tools'),'K:/pvz2-tools/pyvz2/OBBEdit/libraries']
import rsbtool
from pyvz2rton import RTONDecoder,JSONDecoder
from py3rijndael import RijndaelCbc,ZeroPadding
from rebuild_bootstrap_dex import rebuild_bootstrap
BASE=ROOT/'work/treasure-v27/PvZ2-v27-trial-transition-lucky-guide-fix.apk'
assert hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest()=='d84f7ef9bd8aa92c4ff5c34d18de709cdba0b03c9ff91ff29f0272c203e87325'
os.environ['TMP']=os.environ['TEMP']=str(ROOT/'work/tmp')
patches=[]
with zipfile.ZipFile(BASE) as src:
 b=bytearray(src.read('lib/armeabi/libSrc.so'));elf=ELFFile(BytesIO(b))
 idx,tail=[(i,s) for i,s in enumerate(elf.iter_segments()) if s['p_type']=='PT_LOAD'][-1]
 oldlen=len(b);assert tail['p_offset']+tail['p_filesz']==oldlen
 def patch(a,expected,new,role):
  assert b[a:a+len(expected)]==expected,(role,hex(a))
  b[a:a+len(new)]=new;patches.append(dict(va=hex(a),before=expected.hex(),after=new.hex(),role=role))
 def branch(a,t,link=False):return struct.pack('<I',(0xeb000000 if link else 0xea000000)|(((t-a-8)//4)&0xffffff))
 while len(b)%4:b.append(0)
 va=tail['p_vaddr']+len(b)-tail['p_offset']
 # Same mode, level-load functor, and request parameters as 0x10969d4..
 # 0x1096a44, but entered from the map without a Board or server session.
 asm='''push {r4,r5,r6,r7,r8,lr}
 sub sp,sp,#24
 bl #0x7fa754
 mov r3,#1
 str r3,[r0,#4]
 str r3,[r0,#0xa8]
 mov r3,#0
 strb r3,[r0,#0x100]
 adr r4,app_delta
 ldr r3,[r4]
 add r4,r4,r3
 ldr r4,[r4]
 ldr r4,[r4]
 add r4,r4,#0x1200
 mov r3,#3
 str r3,[r4,#0x18]
 add r0,sp,#8
 adr r1,level_name
 add r2,sp,#16
 blx #0x14ed0e0
 adr r0,manager_delta
 ldr r3,[r0]
 add r0,r0,r3
 ldr r0,[r0]
 adr r1,functor_delta
 ldr r3,[r1]
 add r1,r1,r3
 add r2,sp,#8
 mvn r3,#0
 mov r4,#1
 str r4,[sp]
 str r4,[sp,#4]
 bl #0x354360
 ldr r0,[sp,#8]
 sub r0,r0,#12
 add r1,sp,#12
 blx #0x14ebf58
 add sp,sp,#24
 pop {r4,r5,r6,r7,r8,pc}
 app_delta: .word 0x11223344
 manager_delta: .word 0x22334455
 functor_delta: .word 0x33445566
 level_name: .asciz "arena_battle_attack_tutorial"
 '''
 code=bytearray(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(asm,addr=va)[0])
 for marker,target in [(0x11223344,0x1821674),(0x22334455,0x1835eec),(0x33445566,0x18a6708)]:
  at=code.index(struct.pack('<I',marker));struct.pack_into('<I',code,at,(target-va-at)&0xffffffff)
 b.extend(code)
 patch(0x1021f4c,bytes.fromhex('f0482de9'),branch(0x1021f4c,va),'map PvP click enters native offline NPC practice without cloud/login')
 # Pause/abandon paths can request the original online PvP main scene 28.
 # Remap that request only while the native arena tutorial battle mode is 3.
 while len(b)%4:b.append(0)
 exitva=tail['p_vaddr']+len(b)-tail['p_offset']
 exitasm='''cmp r1,#28
 bne original
 push {r4,r5}
 adr r4,exit_app_delta
 ldr r5,[r4]
 add r4,r4,r5
 ldr r4,[r4]
 ldr r4,[r4]
 add r4,r4,#0x1200
 ldr r5,[r4,#0x18]
 cmp r5,#3
 moveq r1,#7
 pop {r4,r5}
 original:
 str fp,[sp,#-4]!
 b #0x352a80
 exit_app_delta: .word 0x44556677'''
 exitcode=bytearray(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(exitasm,addr=exitva)[0])
 at=exitcode.index(struct.pack('<I',0x44556677));struct.pack_into('<I',exitcode,at,(0x1821674-exitva-at)&0xffffffff)
 b.extend(exitcode)
 patch(0x352a7c,bytes.fromhex('04b02de5'),branch(0x352a7c,exitva),'arena tutorial-mode requests for online PvP scene 28 return to map instead')
 # The tutorial battle's two completion exits otherwise lead to online PvP
 # scenes 25/28. Preserve its native result/cleanup, select normal map 7.
 for a,old in [(0x10a9714,25),(0x10a9784,28)]:
  patch(a,struct.pack('<I',0xe3a01000|old),bytes.fromhex('0710a0e3'),'native NPC result returns to map')
 for a in (0x10a96f4,0x10a9ae4):
  old=bytes(b[a:a+4]);patch(a,old,bytes.fromhex('0000a0e1'),'practice does not advance online PvP tutorial progress')
 ph=elf['e_phoff']+idx*elf['e_phentsize'];added=len(b)-oldlen
 for p in (ph+16,ph+20):struct.pack_into('<I',b,p,struct.unpack_from('<I',b,p)[0]+added)
 (OUT/'libSrc.so').write_bytes(b)
 # Keep a fixed native zombie card instead of the online trained-army chooser.
 resource='assets/reconstruction/dynamic-original-speed.rsb.smf'
 dynamic=bytearray(src.read(resource));oldsha=hashlib.sha256(dynamic).hexdigest()
 h=rsbtool.parse_head(dynamic);g=rsbtool.read_rsgp_info(dynamic,h['rsgpInfo_BeginOffset'],h['rsgp_Number'],h['rsgpInfo_EachLength'])
 start=next(x for x in g if x['ID'].lower()=='packages')['fields'][0]
 ln,lo=struct.unpack_from('<II',dynamic,start+0x48)
 entries=rsbtool.read_string_list(dynamic[start+lo:start+lo+ln],0,ln,1)
 name,(_,pos,size)=next(x for x in entries if x[0].endswith('LEVELS\\ARENA_BATTLE_ATTACK_TUTORIAL.RTON'))
 dataoff=struct.unpack_from('<I',dynamic,start+0x18)[0];at=start+dataoff+pos
 key=hashlib.md5(b'com_popcap_pvz2_magento_product_2013_05_05').hexdigest().encode()
 cipher=RijndaelCbc(key,key[4:28],ZeroPadding(24),block_size=24)
 plain=cipher.decrypt(bytes(dynamic[at+2:at+size]));fp=BytesIO(plain[4:]);fp.name=name
 config=json.loads(RTONDecoder(repairFiles=False).parse_root_object(fp))
 bank=next(x['objdata'] for x in config['objects'] if x['objclass']=='PVPSeedBankProperties')
 bank['ZombieList']=[dict(ZombieName='tutorial',NeedZoneLevel=1)]
 enc=JSONDecoder().encode_root_object(StringIO(json.dumps(config,ensure_ascii=False)))
 assert len(enc)<=size-2
 dynamic[at:at+size]=b'\x10\0'+cipher.encrypt(enc+bytes(size-2-len(enc)))
 dex=src.read('classes8.dex');assert oldsha.encode() in dex
 dex=rebuild_bootstrap(dex,OUT/'bootstrap',{oldsha:hashlib.sha256(dynamic).hexdigest(),
                       '.exchange-shop-v16-r10':'.offline-npc-v28'},ROOT/'tools/apktool.jar')
 replacements={'lib/armeabi/libSrc.so':b,resource:dynamic,'classes8.dex':dex}
 with zipfile.ZipFile(OUT/'unsigned.apk','w',allowZip64=True) as dst:
  for item in src.infolist():
   if item.filename.startswith('META-INF/'):continue
   if item.filename in replacements:dst.writestr(item,replacements[item.filename])
   else:
    with src.open(item) as a,dst.open(item,'w') as z:shutil.copyfileobj(a,z,1024*1024)
record=dict(base=str(BASE),patches=patches,entry=hex(va),entry_assembly=asm,native_sha256=hashlib.sha256(b).hexdigest(),
            scope='Native offline NPC practice battle, not the online PvP management system',
            game_verified=False,validation_skipped_per_user=True)
(ROOT/'docs/recovery/pvp-v28-build.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
