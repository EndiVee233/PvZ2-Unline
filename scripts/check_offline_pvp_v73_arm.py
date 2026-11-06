"""Run daily-boundary, native countdown and restart cases without player saves."""
from check_offline_pvp_v72_arm import RefreshEngine,OUT,check_manual_refresh
from check_offline_pvp_arm import BASE,M,PROFILE
from unicorn.arm_const import *
from datetime import datetime,timezone
from pathlib import Path
from io import BytesIO
from elftools.elf.elffile import ELFFile
import json,struct

class ClockEngine(RefreshEngine):
 def __init__(self):
  super().__init__();self.clock_labels={};self.clock_writes=0
 def hook(self,em,a,size,d):
  off=a-BASE;x,y=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1)]
  if off==0x106e5d4:return
  if off==0x106e5d8:
   sp=em.reg_read(UC_ARM_REG_SP);regs=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R11,UC_ARM_REG_PC)
   for i,r in enumerate(regs):em.reg_write(r,self.get(sp+4*i))
   em.reg_write(UC_ARM_REG_SP,sp+4*len(regs));return
  if off==0x10c2548 and x in self.clock_labels:
   p=self.get(y);n=self.get(p-12);self.clock_labels[x]=bytes(em.mem_read(p,n*4)).decode('utf-32-le');self.clock_writes+=1
   em.reg_write(UC_ARM_REG_R0,0);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
  return super().hook(em,a,size,d)
 def clock_ui(self):
  ui=self.alloc(0xec);label=self.alloc(0x80);self.put(ui+0xe8,label);self.clock_labels[label]='';return ui
 def draw(self,ui):self.run(0x106e5d4,ui);return self.clock_labels[self.get(ui+0xe8)]
 def clock_state(self):
  raw=next(v for k,v in self.files.items() if k.endswith('.eco'));assert len(raw) in (412,416);return struct.unpack('<IIi',raw[400:412])
 def mode(self):self.run('offlineExchangeClockMode');return self.u.reg_read(UC_ARM_REG_R0)
 def restart(self):
  r=ClockEngine();r.now=self.now;r.timezone_offset=self.timezone_offset;r.copy_state(self);r.enter();r.open();return r

DAY=int(datetime(2026,11,5,tzinfo=timezone.utc).timestamp())
def fixture(second=64798,offset=28800):
 e=ClockEngine();e.timezone_offset=offset;e.now=DAY+second-offset-5*86400;e.enter();e.advance(5*86400);e.enter();e.open();return e
def remaining(e):
 ui=e.clock_ui();s=e.draw(ui);a,b,c=map(int,s.split(':'));return 3600*a+60*b+c

def check_clock():
 e=fixture();mode=e.mode();left=remaining(e);assert left==(45 if mode else 2),(mode,left)
 ui=e.clock_ui();before=e.clock_writes;e.draw(ui);e.draw(ui);assert e.clock_writes==before+1
 e.advance(1);assert e.draw(ui)==('00:00:44' if mode else '00:00:01')
 # Manual refresh changes its price/stock, never the daily deadline.
 deadline=e.now+remaining(e);confirm=e.quote();e.confirm(confirm);assert e.price()==20 and e.now+remaining(e)==deadline
 id=e.current()[0];e.buy(id);assert e.sold()==[id];inventory=dict(e.inventory)
 stale=e.quote();medals=e.get(M+8);samples=e.samples;old=e.stock_record()
 e.advance(deadline-e.now);assert e.draw(ui)=='24:00:00'
 assert e.get(M+8)==medals and e.price()==10 and not e.sold() and e.inventory==inventory
 assert e.samples==samples+1 and e.stock_record()[1]!=old[1] and e.stock_record()[2]==0
 e.draw(ui);e.open();assert e.samples==samples+1
 e.confirm(stale);assert e.get(M+8)==medals,'stale pre-reset quote charged'
 r=e.restart();assert r.current()==e.current() and r.price()==10 and r.inventory==inventory and r.samples==0 and remaining(r)==86400
 # Several missed dates roll into one fresh current catalogue for free.
 r.advance(3*86400+9);before=r.get(M+8);r.open();assert r.samples==1 and r.price()==10 and r.get(M+8)==before
 generation=r.stock_record();r.now-=86400;r.open();assert r.samples==1 and r.stock_record()==generation
 e.close_engine();r.close_engine()

 # Boundary failures retain old goods/price; retry can commit once later.
 e=fixture();left=remaining(e);e.quote();e.refresh();before=(e.get(M+8),e.current(),e.price(),e.clock_state()[1])
 e.failwrite=True;e.advance(left);e.draw(e.clock_ui());assert (e.get(M+8),e.current(),e.price(),e.clock_state()[1])==before
 e.failwrite=False;e.advance(1);e.draw(e.clock_ui());assert e.price()==10 and e.get(M+8)==before[0] and e.clock_state()[1]>before[3]
 e.close_engine()

 for offset in (0,-18000,19800,50400):
  e=fixture(64799,offset);left=remaining(e);assert left==(45 if mode else 1)
  e.advance(left);e.open();assert e.clock_state()[1]>0 and remaining(e)==86400 and e.price()==10;e.close_engine()

 # Existing sold stock is not cleared merely by adding a clock to v8.
 e=fixture(30000);id=e.current()[0];e.buy(id);key=next(k for k in e.files if k.endswith('.eco'));raw=e.files[key][:400];struct.pack_into('<I',raw,4,8);h=2166136261
 for i,c in enumerate(raw):
  if not 24<=i<28:h=((h^c)*16777619)&0xffffffff
 struct.pack_into('<I',raw,24,h);e.files[key]=raw;r=e.restart()
 assert r.current()==e.current() and r.sold()==e.sold() and r.inventory==e.inventory and r.price()==e.price()
 remaining(r);assert r.clock_state()[0]==1 and not r.grants;r.close_engine();e.close_engine()

 # A release package gracefully leaves the accelerated test clock behind.
 if not mode:
  e=fixture(30000);item=e.current()[0];e.buy(item);key=next(k for k in e.files if k.endswith('.eco'));raw=bytearray(e.files[key]);struct.pack_into('<i',raw,408,12000);h=2166136261
  for i,c in enumerate(raw):
   if not 24<=i<28:h=((h^c)*16777619)&0xffffffff
  struct.pack_into('<I',raw,24,h);e.files[key]=raw;r=e.restart()
  assert r.clock_state()[2]==0 and r.current()==e.current() and r.sold()==e.sold() and r.inventory==e.inventory and r.get(M+8)==e.get(M+8)
  r.close_engine();e.close_engine()

 original=Path('work/libSrc_orig.so').read_bytes();elf=ELFFile(BytesIO(original));syms=elf.get_section_by_name('.dynsym');rels=elf.get_section_by_name('.rel.plt')
 assert syms.get_symbol(list(rels.iter_relocations())[19]['r_info_sym']).name=='localtime'
 assert elf.get_section_by_name('.plt')['sh_addr']+20+19*12==0x147854
 word=struct.unpack_from('<I',original,0x10707b0)[0];address=(0x10706e0+word)&0xffffffff
 assert original[address:address+12]==b'UIText_Time\0'
 report=dict(daily_local_refresh_seconds=64800,diagnostic_shop_clock_only=bool(mode),countdown_decrements_and_native_ui_update=True,
 actual_original_localtime_plt_and_time_label_verified=True,manual_refresh_keeps_deadline=True,automatic_refresh_free_once=True,
 sold_flags_and_price_reset_without_repeat_awards=True,stale_manual_confirmation_rejected=True,restart_keeps_deadline_and_stock=True,
 missed_days_coalesced_and_backward_clock_no_replay=True,failed_save_retries_without_fee=True,timezones_and_boundary_second=True,
 v8_migration_preserves_stock_sales_and_inventory=True,runtime_game_verified=False)
 (OUT/'v73-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))

if __name__=='__main__':
 check_manual_refresh()
 check_clock()
 from check_offline_exchange_sampler_arm import check
 check()
