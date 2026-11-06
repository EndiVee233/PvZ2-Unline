"""Owned shop production, migration and prior capture/edit lifecycle boundaries."""
import sys,importlib,struct,json
from check_offline_pvp_v76_focused import Definitions

def check_production(c):
 from check_offline_pvp_arm import M,PM
 from check_offline_pvp_v81_arm import GarrisonEngine,claim
 def key(e):return next(k for k in e.files if k.endswith(f'offline-pvp-{e.get(PM+0x74):08x}.eco'))
 def stock(e,i):return struct.unpack_from('<5I',e.files[key(e)],416+20*i)
 def ready():
  e=GarrisonEngine();e.enter();e.run('offlineGarden')
  for _ in range(3):e.train()
  e.advance(91);e.run('offlineTrainingTick',e.get(M+0x20));return e
 def tick(e):e.enter();e.run('offlineGarden')
 def projected(e,i):return tuple(e.get(e.shops()[i]+o) for o in (24,28,32,36,40,44))
 e=ready();assert stock(e,0)==stock(e,1)==(0,0,0,0,0)
 claim(e,0);assert stock(e,0)==(e.now,0,0,0,0) and stock(e,1)==(0,0,0,0,0)
 assert projected(e,0)==(0,2000,0,2000,20,40) and projected(e,1)==(0,2000,0,2000,0,0)
 e.advance(90);tick(e);assert stock(e,0)[1:]==(1,0,0,1800)
 claim(e,1);assert stock(e,1)==(e.now,0,0,0,0)
 e.advance(90);tick(e);assert stock(e,0)[1:]==(2,1,0,0) and stock(e,1)[1:]==(1,0,0,1800)
 assert projected(e,0)==(1,2000,2,2000,20,40)
 # Restart/offline hour is credited only to the two stockpiles, not as rent.
 r=GarrisonEngine();r.copy_state(e);r.now=e.now+3600;r.enter();r.run('offlineGarden')
 assert stock(r,0)[1:3]==(42,21) and stock(r,1)[1:3]==(41,20)
 assert r.get(M+4)==min(2000,e.get(M+4)+40) and r.get(M+8)==min(2000,e.get(M+8)+20)
 before=bytes(r.files[key(r)]);tick(r);assert bytes(r.files[key(r)])==before,'same time paid twice'
 # Moving the clock backward neither drains funds nor invents stock.
 r.now-=200;tick(r);assert bytes(r.files[key(r)])==before
 r.now+=200+3600*24*365;tick(r);assert stock(r,0)[1:]==stock(r,1)[1:]==(2000,2000,0,0)
 assert projected(r,0)==(2000,2000,2000,2000,20,40)
 # A failed atomic write keeps prior stock and can be retried once.
 f=ready();claim(f,0);saved={k:bytes(v) for k,v in f.files.items()};f.advance(180);f.failwrite=True;tick(f)
 assert {k:bytes(v) for k,v in f.files.items()}==saved
 f.failwrite=False;tick(f);assert stock(f,0)[1:]==(2,1,0,0)
 # Actual v10 CRC covers exactly 416 bytes. No retroactive rent on migration.
 legacy=bytearray(e.files[key(e)][:416]);struct.pack_into('<I',legacy,4,10);h=2166136261
 for i,v in enumerate(legacy):
  if not 24<=i<28:h=((h^v)*16777619)&0xffffffff
 struct.pack_into('<I',legacy,24,h)
 old=GarrisonEngine();old.files={key(e):legacy};old.now=e.now+86400;tick(old)
 assert old.owned()==3 and stock(old,0)==stock(old,1)==(old.now,0,0,0,0)
 assert len(old.files[key(old)])==456 and struct.unpack_from('<I',old.files[key(old)],4)[0]==11
 # Other profiles do not inherit stores; switching back keeps the saved stock.
 f.put(PM+0x74,43);f.put(M+0x20,0);tick(f);assert f.owned()==0 and stock(f,0)==stock(f,1)==(0,0,0,0,0)
 f.put(PM+0x74,42);f.put(M+0x20,0);tick(f);assert f.owned()==1 and stock(f,0)[1:3]==(2,1)
 report=dict(owned_only=True,capture_begins_at_current_time=True,independent_stocks=True,rates=[40,20],caps=[2000,2000],fractional_seconds=True,offline_and_restart=True,no_automatic_rent_credit=True,clock_backwards_safe=True,capacity_capped=True,atomic_retry=True,v10_crc_migration_without_backfill=True,profile_isolation=True,runtime_game_verified=False)
 (c.OUT/'v90-production-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))

if __name__=='__main__':
 sys.meta_path.insert(0,Definitions());c=importlib.import_module('check_offline_pvp_v82_arm')
 check_production(c)
 c.check_reposition();c.check_capture();c.check_scout();c.check_ownership();c.check_businesses()
 old=importlib.import_module('check_offline_pvp_v76_arm');old.check_lifecycle();old.check_defense();old.check_residences()
