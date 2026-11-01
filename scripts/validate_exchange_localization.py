from pathlib import Path
import json,struct
from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.arm_const import *
p=Path('work/exchange-v16/libSrc.so');b=p.read_bytes();e=ELFFile(p.open('rb'));j=json.loads(Path('docs/recovery/exchange-v16-patches.json').read_text(encoding='utf8'));strings=j['native_patches'][-1]['strings'];cases=[]
for key,value in strings.items():
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in e.iter_segments():
  if s['p_type']=='PT_LOAD':
   lo=s['p_vaddr']&~4095;hi=(s['p_vaddr']+s['p_memsz']+4095)&~4095;u.mem_map(lo,hi-lo);u.mem_write(s['p_vaddr'],b[s['p_offset']:s['p_offset']+s['p_filesz']])
 u.mem_map(0x4000000,0x10000);u.mem_map(0x5000000,4096);u.mem_write(0x4000100,struct.pack('<I',0x4000200));u.mem_write(0x4000200,(key+'\0').encode('utf-32le'))
 u.reg_write(UC_ARM_REG_R0,0x4000000);u.reg_write(UC_ARM_REG_R1,0x4000100);u.reg_write(UC_ARM_REG_SP,0x400f000);u.reg_write(UC_ARM_REG_LR,0x5000000);result=[]
 def hook(c,pc,size,data):
  if pc==0x14eb450:
   ptr=c.reg_read(UC_ARM_REG_R1);raw=bytearray()
   while bytes(c.mem_read(ptr,4))!=b'\0'*4:raw+=c.mem_read(ptr,4);ptr+=4
   result.append(raw.decode('utf-32le'));c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.emu_start(0xd07ae8,0x5000000,count=5000);assert result==[value],(key,result,value);assert u.reg_read(UC_ARM_REG_SP)==0x400f000;cases.append(key)
print('PASS',len(cases),'Unicode localized strings')
Path('docs/recovery/exchange-localization-validation.json').write_text(json.dumps(dict(keys=cases,passed=len(cases)),indent=2))
