"""Add narrowly scoped UTF-32 localization keys for exchange strings."""
import struct
from io import BytesIO
from elftools.elf.elffile import ELFFile
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM

def add_exchange_localization(original, strings):
 b=bytearray(original);e=ELFFile(BytesIO(original));i,s=[(i,s) for i,s in enumerate(e.iter_segments()) if s['p_type']=='PT_LOAD'][-1]
 assert s['p_offset']+s['p_filesz']==len(b) and s['p_flags']==5
 start=s['p_vaddr']+s['p_filesz'];pad=(-start)%4;b.extend(bytes(pad));start+=pad
 off=len(b);ph=e['e_phoff']+i*e['e_phentsize'];entry=0xd07ae8;old=bytes(b[entry:entry+4])
 fallback=None
 if old!=bytes.fromhex('f0482de9'):
  word=struct.unpack('<I',old)[0];assert word>>24==0xea
  delta=word&0xffffff
  if delta&0x800000:delta-=1<<24
  fallback=entry+8+delta*4
 asm=['push {r4,r5,r6,r7,fp,lr}','sub sp,sp,#8','mov r4,r0','mov r5,r1']
 for n,(key,value) in enumerate(strings.items()):
  asm += ['ldr r2,[r5]',f'ldr r3,keydelta{n}',f'keyref{n}:','add r3,pc,r3',f'loop{n}:','ldr r6,[r2],#4','ldr r7,[r3],#4','cmp r6,r7',f'bne next{n}','cmp r6,#0',f'bne loop{n}',f'ldr r1,valuedelta{n}',f'valueref{n}:','add r1,pc,r1','mov r0,r4','mov r2,sp','blx #0x14eb450','mov r0,r4','add sp,sp,#8','pop {r4,r5,r6,r7,fp,pc}',f'next{n}:']
 asm+=['mov r0,r4','mov r1,r5','add sp,sp,#8','pop {r4,r5,r6,r7,fp,lr}']
 if fallback is None:asm+=['push {r4,r5,r6,r7,fp,lr}','b #0xd07aec']
 else:asm+=[f'b #{fallback}']
 for n in range(len(strings)):
  asm += [f'keydelta{n}:',f'.word key{n}-keyref{n}-8',f'valuedelta{n}:',f'.word value{n}-valueref{n}-8']
 for n,(key,value) in enumerate(strings.items()):
  for prefix,text in [('key',key),('value',value)]:
   asm.append(f'{prefix}{n}:');asm.append('.word '+','.join(str(ord(c)) for c in text+'\0'))
 code=bytes(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm('\n'.join(asm),addr=start)[0]);b.extend(code)
 b[entry:entry+4]=struct.pack('<I',0xea000000|(((start-entry-8)//4)&0xffffff))
 for p in [ph+16,ph+20]:struct.pack_into('<I',b,p,struct.unpack_from('<I',b,p)[0]+pad+len(code))
 return b,dict(offset=hex(entry),before=old.hex(),after=b[entry:entry+4].hex(),stub_offset=hex(off),stub_va=hex(start),stub_size=len(code),strings=strings,role='Exchange-only localization keys use UTF-32 strings; unrelated localization falls back to original lookup')
