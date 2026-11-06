"""Production/rent/base-upgrade transaction boundaries in the compiled ARM."""
import sys,importlib,struct,json
from check_offline_pvp_v76_focused import Definitions

def check_collection(c):
 from check_offline_pvp_arm import M,PM,BASE,END
 from check_offline_pvp_v81_arm import GarrisonEngine,claim
 from check_offline_pvp_v48_arm import SessionEngine
 class CombinedEngine(GarrisonEngine):
  # Shared historical fixtures reuse these synthetic vtable slots for shop
  # dialogs. Route checkout rendering/close slots explicitly in this batch.
  def hook(self,em,a,size,d):
   if a in (END+0x300,END+0x310,END+0x330):return SessionEngine.hook(self,em,a,size,d)
   return super().hook(em,a,size,d)
 def key(e):return next(k for k in e.files if k.endswith(f'offline-pvp-{e.get(PM+0x74):08x}.eco'))
 def stock(e,i):return struct.unpack_from('<5I',e.files[key(e)],416+i*20)
 def tick(e):e.enter();e.run('offlineGarden')
 def fixture():
  e=CombinedEngine();tick(e)
  for _ in range(3):e.train()
  e.advance(91);e.run('offlineTrainingTick',e.get(M+0x20));claim(e,0);claim(e,1);return e
 def collect(e,i):
  ui,_=e.shop_panel(e.shops()[i]);e.put(ui+0xa4,2);e.put(ui+0xc0,M+0x18000);e.stub(0x100b3d8,ui,200)
 e=fixture();e.advance(180);tick(e);before=e.get(M+4),e.get(M+8);second=stock(e,1)
 assert stock(e,0)[1:3]==(2,1)
 collect(e,0);assert (e.get(M+4),e.get(M+8))==(before[0]+2,before[1]+1)
 assert stock(e,0)[1:3]==(0,0) and stock(e,1)==second
 data=bytes(e.files[key(e)]);collect(e,0);assert bytes(e.files[key(e)])==data,'empty repeated collection saved/credited again'
 assert e.dismissed[-1]==M+0x18000
 # Receiving rent then upgrading the home keeps merchant rates/capacity intact.
 e.upgrade(1);assert e.get(M+0x6c)==1,(e.get(M+0x6c),e.notices,e.level(1));ui,button,timer=e.training_ui();e.put(ui+0xac,1);e.put(ui+0xb0,button);e.put(ui+0xb4,timer)
 e.run('offlineUpgradeDisplay',ui);e.stub(0x107486c,ui,0xfffffffe);gems=e.gems
 # The inherited exchange fixture also has a confirm() method. Select the
 # checkout fixture explicitly so this exercises the installed native hook.
 SessionEngine.confirm(e,timer,0);assert e.level(1)==1 and e.gems==gems
 SessionEngine.confirm(e,timer,1);assert e.level(1)==2 and e.gems==gems-15 and e.closed>=2
 for p in e.shops():assert [e.get(p+o) for o in (28,36,40,44)]==[2000,2000,20,40]
 r=CombinedEngine();r.copy_state(e);r.now=e.now;tick(r)
 assert r.level(1)==2 and stock(r,0)[1:3]==(0,0) and stock(r,1)==second
 funds=r.get(M+4),r.get(M+8);collect(r,1);assert (r.get(M+4),r.get(M+8))==(funds[0]+2,funds[1]+1)
 # A write failure cannot clear the shop or increase wallet; retry credits once.
 f=fixture();f.advance(190);tick(f);saved={k:bytes(v) for k,v in f.files.items()};funds=f.get(M+4),f.get(M+8)
 f.failwrite=True;collect(f,0);assert {k:bytes(v) for k,v in f.files.items()}==saved and (f.get(M+4),f.get(M+8))==funds
 f.failwrite=False;collect(f,0);assert (f.get(M+4),f.get(M+8))==(funds[0]+2,funds[1]+1)
 assert stock(f,0)[3:]==(400,200),'sub-unit production remainder was discarded'
 # Near wallet limit, retain unclaimable stock instead of losing earned units.
 data=bytearray(f.files[key(f)]);struct.pack_into('<I',data,12,1999999999);struct.pack_into('<I',data,180,2000000000)
 # Medal offset follows initialized, and the fixture train count is 12.
 assert struct.unpack_from('<I',data,176)[0]==1
 struct.pack_into('<II',data,420,2,1);h=2166136261
 for i,v in enumerate(data):
  if not 24<=i<28:h=((h^v)*16777619)&0xffffffff
 struct.pack_into('<I',data,24,h)
 cap=CombinedEngine();cap.files={key(f):data};cap.now=f.now;tick(cap);collect(cap,0)
 assert (cap.get(M+4),cap.get(M+8))==(2000000000,2000000000) and stock(cap,0)[1:3]==(1,1)
 saved=bytes(cap.files[key(cap)]);collect(cap,0);assert bytes(cap.files[key(cap)])==saved
 report=dict(original_collect_button_executed=True,wallet_and_stock_atomic=True,repeated_and_restart_no_duplicate=True,two_shops_isolated=True,empty_collect_safe=True,save_failure_retry=True,fraction_preserved=True,overflow_retained_in_stock=True,base_upgrade_and_gem_cancel_confirm_preserved=True,merchant_rates_not_tied_to_home=True,runtime_game_verified=False)
 (c.OUT/'v91-collection-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))

if __name__=='__main__':
 sys.meta_path.insert(0,Definitions());c=importlib.import_module('check_offline_pvp_v82_arm')
 check_collection(c);p=importlib.import_module('check_offline_pvp_v90_focused');p.check_production(c)
 c.check_reposition();c.check_capture();c.check_scout();c.check_ownership();c.check_businesses()
 old=importlib.import_module('check_offline_pvp_v76_arm');old.check_lifecycle();old.check_defense();old.check_residences()
