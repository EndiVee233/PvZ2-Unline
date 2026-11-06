"""Run compiled region transactions, legacy migration and accepted map flows."""
import sys,importlib,struct,json
from check_offline_pvp_v76_focused import Definitions

def crc(raw):
 h=2166136261
 for i,v in enumerate(raw):
  if not 24<=i<28:h=((h^v)*16777619)&0xffffffff
 struct.pack_into('<I',raw,24,h);return raw

def key(e):
 from check_offline_pvp_arm import PM
 return next(k for k in e.files if k.endswith(f'offline-pvp-{e.get(PM+0x74):08x}.eco'))

def old_record(e,level=7,coins=50000):
 raw=bytearray(e.files[key(e)][:456]);struct.pack_into('<I',raw,4,11)
 for at,n in [(12,coins),(16,level),(184,level)]:struct.pack_into('<I',raw,at,n)
 return crc(raw)

def check_regions(c):
 from check_offline_pvp_v81_arm import GarrisonEngine
 from check_offline_pvp_arm import BASE,M,PM
 from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_PC,UC_ARM_REG_LR
 class Regions(GarrisonEngine):
  def hook(self,em,a,size,d):
   if a==BASE+0x1013a3c:
    ui,map_,kind,zone=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
    position=self.get(em.reg_read(UC_ARM_REG_SP));assert map_==M+0x18000 and kind==0 and position==0
    for o,v in [(0xa4,kind),(0xa8,position),(0xac,zone),(0xc0,map_)]:self.put(ui+o,v)
    em.reg_write(UC_ARM_REG_R0,ui);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
   return super().hook(em,a,size,d)
  def mask(self):return struct.unpack_from('<I',self.files[key(self)],460)[0]
  def regions(self):return {self.get(p):tuple(self.get(p+i) for i in (4,8)) for p in range(self.get(M+0x11c),self.get(M+0x120),12)}
  def panel_region(self,zone,price=None):
   p=self.alloc(0x150)
   for o,v in [(0xa4,0),(0xa8,0),(0xac,zone),(0xc0,M+0x18000),(0x144,price if price is not None else [0,0,10000,16500,23500,31000,39000][zone])]:self.put(p+o,v)
   self.stub(0x10196d0,p,M+0x18000,0,zone,0);assert self.u.reg_read(UC_ARM_REG_R0)==p;return p
  def unlock(self,zone):
   p=self.panel_region(zone);self.stub(0x100b3d8,p,202);return p
 def legacy(level=7,coins=50000):
  e=Regions();e.enter();r=Regions();r.files={key(e):old_record(e,level,coins)};r.enter();r.run('offlineGarden');return r
 e=Regions();e.enter();e.run('offlineGarden')
 assert e.mask()==1 and e.get(M+4)==1000 and len(e.residents())==4 and not e.shops()
 assert e.regions()=={2:(10000,1),3:(16500,1),4:(23500,1),5:(31000,1),6:(39000,1)}
 saved=bytes(e.files[key(e)]);p=e.panel_region(2)
 e.run('offlineBusinessAction',p,203);assert e.u.reg_read(UC_ARM_REG_R0)==0 and bytes(e.files[key(e)])==saved
 e.unlock(2);assert e.mask()==1 and '[V93_REGION_2_REQUIRED]' in e.notices[-1]
 # Legacy v11 is read at its historical length/checksum and keeps areas 1-3.
 old=legacy();assert old.mask()==7 and old.get(M+4)==50000 and len(old.residents())==7 and len(old.shops())==2
 assert old.regions()[2]==(10000,0) and old.regions()[3]==(16500,0)
 old.unlock(4);assert old.mask()==7 and old.get(M+4)==50000 and '[V93_REGION_4_REQUIRED]' in old.notices[-1]
 # New-player paid area 2, sufficient capacity but insufficient actual funds.
 def fresh_at(level,coins):
  f=Regions();f.enter();raw=bytearray(f.files[key(f)])
  for o,v in [(12,coins),(16,level),(184,level)]:struct.pack_into('<I',raw,o,v)
  r=Regions();r.files={key(f):crc(raw)};r.enter();r.run('offlineGarden');return r
 f=fresh_at(6,9999);f.unlock(2);assert f.mask()==1 and f.get(M+4)==9999 and '[V93_REGION_COINS_REQUIRED]' in f.notices[-1]
 f=fresh_at(6,10000);p=f.unlock(2);assert f.mask()==3 and f.get(M+4)==0 and len(f.residents())==7
 first=bytes(f.files[key(f)]);f.stub(0x100b3d8,p,202)
 assert bytes(f.files[key(f)])==first and f.get(M+4)==0,'repeated callback charged again'
 order=fresh_at(9,100000);order.unlock(4);assert order.mask()==1 and order.get(M+4)==100000
 assert '[V93_PREVIOUS_REGION_REQUIRED]' in order.notices[-1]
 # Unlock area 4 is atomic; a failed write cannot clear clouds/debit funds.
 f=legacy(8,23500);saved=bytes(f.files[key(f)]);f.failwrite=True;f.unlock(4)
 assert f.mask()==7 and f.get(M+4)==23500 and f.regions()[4][1]==1 and bytes(f.files[key(f)])==saved
 f.failwrite=False;p=f.unlock(4)
 assert f.mask()==15 and f.get(M+4)==0 and f.regions()[4]==(23500,0) and len(f.residents())==10
 r=Regions();r.copy_state(f);r.enter();r.run('offlineGarden')
 assert r.mask()==15 and r.get(M+4)==0 and len(r.residents())==10
 r.unlock(5);assert r.mask()==15 and '[V93_REGION_5_REQUIRED]' in r.notices[-1]
 # Finish remaining areas with a capacity-appropriate synthetic wallet.
 raw=bytearray(r.files[key(r)])
 for o,v in [(12,70000),(16,9),(184,9)]:struct.pack_into('<I',raw,o,v)
 all_=Regions();all_.files={key(r):crc(raw)};all_.enter();all_.run('offlineGarden')
 all_.unlock(5);assert all_.mask()==31 and all_.get(M+4)==39000 and len(all_.residents())==13
 all_.unlock(6);assert all_.mask()==63 and all_.get(M+4)==0 and len(all_.residents())==16
 assert len({(all_.get(p+28),all_.get(p+32)) for p in all_.residents()})==16
 # Stale confirmation from another player must neither debit nor close it.
 p=all_.panel_region(4);all_.put(PM+0x74,43);all_.put(M+0x20,0);all_.enter();all_.run('offlineGarden')
 assert all_.mask()==1 and len(all_.residents())==4 and not all_.shops(),(all_.mask(),[(all_.get(p),all_.get(p+28),all_.get(p+32)) for p in all_.residents()],all_.shops())
 before=all_.get(M+4),len(all_.dismissed);all_.stub(0x100b3d8,p,202)
 assert (all_.get(M+4),len(all_.dismissed))==before
 all_.put(PM+0x74,42);all_.put(M+0x20,0);all_.enter();all_.run('offlineGarden')
 assert all_.mask()==63 and len(all_.residents())==16 and all_.get(M+4)==0
 # Reject a malformed, noncontiguous unlock mask, without replacing its file.
 corrupt=bytearray(f.files[key(f)]);struct.pack_into('<I',corrupt,460,9);crc(corrupt)
 bad=Regions();bad.files={key(f):corrupt};bad.enter();assert bytes(bad.files[key(f)])==bytes(corrupt)
 runtime=next(v for k,v in bad.exports.items() if k.endswith('economyRuntime'))
 assert bytes(bad.u.mem_read(BASE+runtime+9,1))==b'\1'
 report=dict(new_free_first_area=True,legacy_v11_first_three_free=True,prices=[10000,16500,23500,31000,39000],base_levels=[6,7,8,9,9],capacity_and_balance_and_order_enforced=True,cancel_and_duplicate_safe=True,atomic_failure_retry=True,restart_and_profile_isolation=True,local_neighbors_per_new_area=3,corrupt_state_rejected=True,runtime_game_verified=False)
 (c.OUT/'v93-region-checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

def accepted_legacy_fixtures():
 # Historical merchant/lifecycle tests model pre-v93 players with three open
 # regions. Construct a public synthetic v11 baseline, then exercise the real
 # migration instead of bypassing the product's new-player unlock conditions.
 from check_offline_pvp_v54_arm import ProgressionEngine
 from check_offline_pvp_arm import BASE,PM
 original=ProgressionEngine.enter
 def enter(e):
  original(e)
  marker=getattr(e,'legacy_region_users',set());user=e.get(PM+0x74)
  if user in marker:return
  marker.add(user);e.legacy_region_users=marker
  raw=e.files.get(key(e))
  if not raw or len(raw)!=464 or struct.unpack_from('<I',raw,460)[0]!=1:return
  e.files[key(e)]=old_record(e,struct.unpack_from('<I',raw,184)[0],struct.unpack_from('<I',raw,12)[0])
  symbol=next(v for k,v in e.exports.items() if k.endswith('economyRuntime'))
  e.u.mem_write(BASE+symbol+8,b'\0');original(e)
 ProgressionEngine.enter=enter

if __name__=='__main__':
 sys.meta_path.insert(0,Definitions());c=importlib.import_module('check_offline_pvp_v82_arm')
 check_regions(c);accepted_legacy_fixtures()
 importlib.import_module('check_offline_pvp_v91_focused').check_collection(c)
 importlib.import_module('check_offline_pvp_v90_focused').check_production(c)
 c.check_reposition();c.check_capture();c.check_scout();c.check_ownership();c.check_businesses()
 old=importlib.import_module('check_offline_pvp_v76_arm');old.check_lifecycle();old.check_defense();old.check_residences()
