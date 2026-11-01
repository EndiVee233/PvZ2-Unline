"""Bounded original ARM wallet/dispatch checks for the v16 exchange candidate."""
from pathlib import Path
import struct,json,zipfile,hashlib,zlib
from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.arm_const import *
root=Path(__file__).resolve().parents[1];out=root/'work/exchange-v16';record=json.loads((root/'docs/recovery/exchange-v16-patches.json').read_text(encoding='utf8'));blob=(out/'libSrc.so').read_bytes();segments=[dict(s.header) for s in ELFFile((out/'libSrc.so').open('rb')).iter_segments() if s['p_type']=='PT_LOAD'];cases=[]
def machine():
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in segments:
  lo=s['p_vaddr']&~4095;hi=(s['p_vaddr']+s['p_memsz']+4095)&~4095;u.mem_map(lo,hi-lo);u.mem_write(s['p_vaddr'],blob[s['p_offset']:s['p_offset']+s['p_filesz']])
 u.mem_map(0x4000000,0x10000);u.mem_map(0x5000000,4096);return u
P=0x4000000;F=P+0xe000;S=P+0xf000
reg=lambda u,r:u.reg_read(r)
def put(u,a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
def read(u,a):return struct.unpack('<I',u.mem_read(a,4))[0]
def setbalance(u,kind,n,salt):
 off=0x98 if kind=='coin' else 0xa0;x=(n^salt)&0xffffffff;k=salt&31;x=((x<<k)|(x>>(32-k if k else 32)))&0xffffffff;put(u,P+off,x);put(u,P+off+4,salt)
def balance(u,kind):
 off=0x98 if kind=='coin' else 0xa0;x=read(u,P+off);s=read(u,P+off+4);k=s&31;return (((x>>k)|(x<<(32-k if k else 32)))^s)&0xffffffff
def reset(u):
 u.reg_write(UC_ARM_REG_SP,S);u.reg_write(UC_ARM_REG_R11,F);u.reg_write(UC_ARM_REG_LR,0x5000000)
for spec in record['exchanges']:
 for salt in [0,1,0x159d,0x8172315f]:
  for delta in [-1,0,1234]:
   u=machine();pay=spec['spend_currency'];gain=spec['receive_currency'];cost=spec['spend'];amount=spec['receive'];initial=cost+delta
   setbalance(u,pay,initial,salt);setbalance(u,gain,12345,salt^0x12341)
   reset(u);put(u,F-0x74,P);put(u,F-0x6c,cost);trace=[]
   insufficient=0x932c6c if pay=='gem' else 0x932c9c;stop=0x747d74 if pay=='gem' else 0x745bc0
   def hook(c,pc,size,data):
    if pc==0x713ce4:c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
    elif pc in [insufficient,stop]:trace.append(hex(pc));c.emu_stop()
   h=u.hook_add(UC_HOOK_CODE,hook);u.emu_start(0x932694 if pay=='gem' else 0x9323bc,0,count=2000);u.hook_del(h)
   assert trace==[hex(insufficient if delta<0 else stop)],(spec,delta,trace)
   assert balance(u,pay)==(initial if delta<0 else delta)
   assert balance(u,gain)==12345
   if delta>=0:
    # Real generic grant path chooses currency from product metadata.
    reset(u);u.reg_write(UC_ARM_REG_R1,P+0x2000);put(u,P+0x3050,amount)
    product=P+0x3000;calls=[]
    def grant(c,pc,size,data):
     if pc==0x7b0328:c.reg_write(UC_ARM_REG_R0,P);c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
     elif pc==0x11d74b4:c.reg_write(UC_ARM_REG_R0,P+0x1000);c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
     elif pc==0x1da034:c.reg_write(UC_ARM_REG_R0,product);c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
     elif pc==0x14ebd4c:
      addr=c.reg_read(UC_ARM_REG_R1);s=bytes(c.mem_read(addr,30)).split(b'\0')[0].decode();c.reg_write(UC_ARM_REG_R0,0 if s==gain else 1);c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
     elif pc==0x713ce4:c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
     elif pc in [0x7461b4,0x74527c]:calls.append(hex(pc));c.emu_stop()
    h=u.hook_add(UC_HOOK_CODE,grant);u.emu_start(0x930648,0,count=2000);u.hook_del(h)
    assert calls==[hex(0x7461b4 if gain=='coin' else 0x74527c)]
    assert balance(u,gain)==12345+amount and balance(u,pay)==delta
   cases.append(dict(alias=spec['alias'],salt=salt,available=initial,spend=cost,receive=amount,success=delta>=0))
# Correct the Gems page's former IAP-only completion to the generic local grant.
u=machine();reset(u);u.reg_write(UC_ARM_REG_R8,P);u.reg_write(UC_ARM_REG_R5,P+0x2000)
u.emu_start(0x9312b8,0x930648,count=4);assert reg(u,UC_ARM_REG_R0)==P and reg(u,UC_ARM_REG_R1)==P+0x2000
# Every native byte change is in the listed ranges; previous fixes retained.
with zipfile.ZipFile(root/'work/tutorial-v15/PvZ2-v15-skip-return-guide.apk') as z:
 old=z.read('lib/armeabi/libSrc.so');allowed={int(p['offset'],16)+i for p in record['native_patches'] for i in range(len(bytes.fromhex(p['after'])))}
 assert len(blob)==len(old) and all(x==y or i in allowed for i,(x,y) in enumerate(zip(blob,old)))
result=dict(arm_wallet_cases_passed=len(cases),gems_page_local_grant_routing_verified=True,only_listed_native_bytes_changed=True,scope='Original input balance guards, encrypted deduction and payout arithmetic executed. Profile lookup, product handle/string resolution and dirty prelude are controlled boundaries. Real UI, event listeners, disk persistence and full store click sequence require device testing.',device_verified=False,cases=cases)
(root/'docs/recovery/exchange-v16-validation.json').write_text(json.dumps(result,indent=2),encoding='utf8');print('PASS',len(cases),'ARM wallet cases and local-grant routing')
