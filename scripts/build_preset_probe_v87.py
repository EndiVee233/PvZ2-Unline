"""Temporary resource-lookup probe; preserve v86 save import and game behavior."""
from pathlib import Path
from io import BytesIO
import hashlib,json,struct,subprocess,zipfile,shutil
from elftools.elf.elffile import ELFFile
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/pvp-v87';OUT.mkdir(exist_ok=True)
BASE=ROOT/'work/pvp-v86/PvZ2-v86-pvp-scene-candidate.apk'
assert hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest()=='a4dde5aa68813de5523e07f823082b8f1f8d2eb8ce9f06b2101c8c304de87801'
with zipfile.ZipFile(BASE) as z:b=bytearray(z.read('lib/armeabi/libSrc.so'))
elf=ELFFile(BytesIO(b));loads=[(i,s) for i,s in enumerate(elf.iter_segments()) if s['p_type']=='PT_LOAD']
index,text=loads[-2];_,rw=loads[-1]
assert text['p_flags']==5 and rw['p_flags']==6
off=text['p_offset']+text['p_filesz'];va=text['p_vaddr']+text['p_filesz']
site=0x11c7738
assert b[site:site+4]==bytes.fromhex('0510a0e1') # mov r1,r5
assembly='''push {r0-r3,r12,lr}
 sub sp,sp,#24
 ldr r0,[r6]
 str r0,[sp]
 ldr r0,[r6,#4]
 str r0,[sp,#4]
 str r6,[sp,#8]
 ldr r0,[r6,#8]
 str r0,[sp,#12]
 ldr r0,[r6,#12]
 str r0,[sp,#16]
 ldr r0,[r6,#20]
 str r0,[sp,#20]
 mov r3,r5
 mov r0,#4
 adr r1,probe_tag
 adr r2,probe_format
 bl #0x147adc
 add sp,sp,#24
 pop {r0-r3,r12,lr}
 mov r1,r5
 b #0x11c773c
 probe_tag: .asciz "PresetResource87"
 probe_format: .asciz "%s slot=%u kind=%u info=%p trie=%p words=%u group=%p"
'''
code=bytes(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(assembly,addr=va)[0])
assert off+len(code)<rw['p_offset'] and not any(b[off:off+len(code)])
b[off:off+len(code)]=code
branch=0xea000000|(((va-site-8)//4)&0xffffff)
struct.pack_into('<I',b,site,branch)
ph=elf['e_phoff']+32*index
struct.pack_into('<II',b,ph+16,text['p_filesz']+len(code),text['p_filesz']+len(code))

# Run the actual installed stub at two load addresses. The logger is bounded;
# no resource lookup, save, UI or game state is simulated as accepted here.
for base in (0,0x20000000):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for address in (site&~4095,va&~4095,0x147000):u.mem_map(base+address,4096)
 u.mem_map(0x50000000,0x10000);u.mem_write(base+site,struct.pack('<I',branch));u.mem_write(base+va,code)
 row=0x50000100;name=0x50000200;sp=0x50008000
 u.mem_write(row,struct.pack('<6I',123,3,0x76540000,999,0,0x76550000));u.mem_write(name,b'PUBLIC/RESOURCE.PAM\0')
 regs=(UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R12,UC_ARM_REG_LR)
 values=[0x111,0x222,0x333,0x444,0x555,name,row,0x888,0x999]
 for r,v in zip(regs,values):u.reg_write(r,v)
 u.reg_write(UC_ARM_REG_SP,sp);events=[]
 def hook(u,a,n,_):
  if a==base+0x147adc:
   assert u.reg_read(UC_ARM_REG_R0)==4 and u.reg_read(UC_ARM_REG_R3)==name
   assert u.reg_read(UC_ARM_REG_SP)%8==0
   assert struct.unpack('<6I',u.mem_read(u.reg_read(UC_ARM_REG_SP),24))==(123,3,row,0x76540000,999,0x76550000)
   events.append(a);u.reg_write(UC_ARM_REG_R0,77);u.reg_write(UC_ARM_REG_R1,88);u.reg_write(UC_ARM_REG_R2,99);u.reg_write(UC_ARM_REG_R3,100);u.reg_write(UC_ARM_REG_R12,101)
   u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.emu_start(base+site,base+site+4,count=1000)
 assert len(events)==1 and u.reg_read(UC_ARM_REG_SP)==sp
 assert [u.reg_read(r) for r in regs]==[values[0],name,*values[2:]]
 assert bytes(u.mem_read(row,24))==struct.pack('<6I',123,3,0x76540000,999,0,0x76550000)

(OUT/'libSrc.so').write_bytes(b)
unsigned=OUT/'unsigned.apk';aligned=OUT/'aligned.apk';final=OUT/'PvZ2-v87-preset-resource-diagnostic.apk'
with zipfile.ZipFile(BASE) as src,zipfile.ZipFile(unsigned,'w',allowZip64=True) as dst:
 for item in src.infolist():
  if item.filename.startswith('META-INF/'):continue
  if item.filename=='lib/armeabi/libSrc.so':dst.writestr(item,b)
  else:
   with src.open(item) as i,dst.open(item,'w') as o:shutil.copyfileobj(i,o,1048576)
align='K:/pvz2-tools/android-build-tools/android-14/zipalign.exe'
sign='K:/pvz2-tools/android-build-tools/android-14/lib/apksigner.jar'
subprocess.run([align,'-f','4',str(unsigned),str(aligned)],check=True)
subprocess.run(['java','-jar',sign,'sign','--ks',str(ROOT/'work/keys/recovered-debug.keystore'),'--ks-pass','pass:android','--key-pass','pass:android','--ks-key-alias','androiddebugkey','--out',str(final),str(aligned)],check=True)
subprocess.run(['java','-jar',sign,'verify',str(final)],check=True);subprocess.run([align,'-c','4',str(final)],check=True)
with zipfile.ZipFile(BASE) as src,zipfile.ZipFile(final) as dst:
 assert {i.filename for i in src.infolist() if not i.filename.startswith('META-INF/')}=={i.filename for i in dst.infolist() if not i.filename.startswith('META-INF/')}
 for i in src.infolist():
  if not i.filename.startswith('META-INF/') and i.filename!='lib/armeabi/libSrc.so':assert (i.CRC,i.file_size)==(dst.getinfo(i.filename).CRC,dst.getinfo(i.filename).file_size)
record=dict(diagnostic_only=True,apk=str(final.relative_to(ROOT)),sha256=hashlib.file_digest(final.open('rb'),'sha256').hexdigest(),site=hex(site),stub=hex(va),stub_size=len(code),abi_and_aslr_cases=2,save_import_unchanged=True,resources_unchanged=True)
(OUT/'build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');print(json.dumps(record))
