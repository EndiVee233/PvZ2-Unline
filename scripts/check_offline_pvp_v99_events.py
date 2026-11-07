"""Silent raid transactions on public synthetic profiles and engine boundaries."""
import struct,json

def check_events(c):
 from check_offline_pvp_v81_arm import GarrisonEngine,claim
 from check_offline_pvp_v93_focused import key,crc,old_record
 from check_offline_pvp_v60_arm import board,result,return_map
 from check_offline_pvp_arm import M,PM
 from unicorn.arm_const import UC_ARM_REG_R0
 DAY=86400
 def fixture(shop=False):
  seed=GarrisonEngine();seed.enter();e=GarrisonEngine();e.files={key(seed):old_record(seed,7,100000)};e.enter();e.run('offlineGarden')
  e.own();e.arrangement(2,0,0);p=e.alloc(60);e.u.mem_write(p,b''.join(struct.pack('<III',2,r,0) for r in range(5)))
  for off,v in ((0x84,p),(0x88,p+60),(0x8c,p+60)):e.put(M+off,v)
  e.save();e.request(3)
  for _ in range(3):e.train()
  e.advance(91);e.run('offlineTrainingTick',e.get(M+0x20))
  if shop:claim(e,0);e.reset_map()
  return e
 def reload(e,mutate=None):
  f=GarrisonEngine();f.files={k:bytearray(v) for k,v in e.files.items()};raw=bytearray(f.files[key(e)])
  if mutate:mutate(raw)
  f.files[key(e)]=crc(raw);f.advance(e.now-f.now);f.enter();f.run('offlineGarden');return f
 def tick(e):e.run('offlineTrainingTick',e.get(M+0x20))
 def rows(e):
  raw=e.files[key(e)];n=struct.unpack_from('<I',raw,464)[0]
  return [struct.unpack_from('<6I',raw,468+24*i) for i in range(n)]
 def word(e,at):return struct.unpack_from('<I',e.files[key(e)],at)[0]
 def xorshift(v):
  v^=(v<<13)&0xffffffff;v^=v>>17;v^=(v<<5)&0xffffffff;return v&0xffffffff
 def rng_for(low,high):
  for n in range(1,100000):
   value=xorshift(n)-1
   if value<4294960000 and low<=value%10000<high:return n
  raise AssertionError('missing deterministic fixture seed')
 def funded(raw,now,rng):
  if len(raw)>2840:struct.pack_into("<I",raw,2840,7)
  for at,value in [(12,100000),(180,50000),(204,now),(208,0),(212,0),(788,1),(792,rng),(796,now)]:struct.pack_into('<I',raw,at,value)
 e=fixture();out=e.alloc(16)
 for strength,kind,stars,expected in [(5,8,0,(8800,500,500,200)),(405,8,0,(9776,24,0,200)),(5,0,0,(9000,500,500,0)),(405,1,1,(500,0,9500,0)),(0,1,0,(10000,0,0,0))]:
  e.run('offlineSilentHistogram',strength,kind,stars,out);actual=struct.unpack('<4I',e.u.mem_read(out,16));assert actual==expected,(strength,kind,actual)
 # Daily FBI: exactly one global trial, true frozen identity, no scene/bank
 # transition and only wallet starcoins/medals lose five percent.
 f=reload(e,lambda raw:funded(raw,e.now,rng_for(0,200)));history=rows(f);loads=len(f.loads);army=f.held();gems=f.gems
 f.advance(DAY);tick(f);h=rows(f)[0]
 assert h[3:]==(3,5000,3) and word(f,832)==2500 and word(f,748)==1
 assert (f.get(M+4),f.get(M+8),f.held(),f.gems)==(95000,47500,army,gems)
 if len(f.files[key(f)])>2840:assert f.get(M+12)==2 and word(f,2840)==2
 assert len(f.loads)==loads and rows(f)[1:]==history
 frozen=next(k for k in f.files if k.endswith('.npc'));assert len(f.files[frozen])==760
 saved={k:bytes(v) for k,v in f.files.items()};tick(f);assert {k:bytes(v) for k,v in f.files.items()}==saved
 r=reload(f);assert rows(r)==rows(f) and (r.get(M+4),r.get(M+8))==(95000,47500)
 r.advance(-DAY);tick(r);assert rows(r)==rows(f),'clock rollback replayed a daily trial'
 # Queue real completed attacks on the visible FBI. Defeating it retains
 # the actual 45-plant identity and marks the special 95% trigger condition.
 attack=fixture();fbi=next(p for p in attack.residents() if attack.get(p+16)==999);target=attack.get(fbi)
 attack.selected(fbi);attack.stub(0x1042fe8,M,0,1,0);board(attack);attack.run(0x1030a50,M+0x14300,attack.held());attack.deaths(0)
 result(attack,1,target);return_map(attack);attack.reset_map()
 assert word(attack,1032)==1 and word(attack,1044)==1 and word(attack,1052)==1
 for low,high,wins in [(0,9500,True),(9500,10000,False)]:
  q=reload(attack,lambda raw:funded(raw,attack.now,rng_for(low,high)));old=rows(q);q.advance(31);loads=len(q.loads);tick(q)
  assert word(q,1032)==0 and len(q.loads)==loads
  if wins:assert rows(q)[0][3:]==(3,5000,3) and q.get(M+4)==95000
  else:assert rows(q)==old and q.get(M+4)==100000
 # Ordinary revenge branches are a single mutually exclusive draw. Retain
 # sub-20 balances without imposing an unapproved minimum-one deduction.
 seed=fixture();target=seed.get(seed.residents()[0]);npc=seed.alloc(740);ids=seed.alloc(8);seed.run('offlineNeighborGenerate',npc,target,7654321,8);seed.run('offlineFreezeEncounter',npc,ids)
 assert seed.u.reg_read(UC_ARM_REG_R0)==1;lo,hi=struct.unpack('<II',seed.u.mem_read(ids,8))
 for roll_range,stars in [((0,500),3),((500,1000),0),((1000,10000),None)]:
  def prepare(raw):
   funded(raw,seed.now,rng_for(*roll_range));struct.pack_into('<I',raw,1032,1);struct.pack_into('<7I',raw,1036,target,7654321,0,seed.now+1,0,lo,hi)
  q=reload(seed,prepare);old=rows(q);q.advance(2);tick(q)
  if stars is None:assert rows(q)==old and q.get(M+4)==100000
  else:assert rows(q)[0][3:]==(stars,5000 if stars else 0,3)
 def small(raw):
  funded(raw,seed.now,rng_for(0,500));struct.pack_into('<I',raw,12,19);struct.pack_into('<I',raw,180,19)
  struct.pack_into('<I',raw,1032,1);struct.pack_into('<7I',raw,1036,target,7654321,0,seed.now+1,0,lo,hi)
 tiny=reload(seed,small)
 if len(tiny.files[key(tiny)])>2840:tiny=reload(tiny,lambda raw:struct.pack_into("<I",raw,2840,2))
 tiny.advance(2);tick(tiny)
 assert tiny.get(M+12)==0
 assert rows(tiny)[0][3:]==(3,0,3) and (tiny.get(M+4),tiny.get(M+8))==(19,19)
 # A failed snapshot/write leaves the RNG, clocks, funds and report together
 # unchanged; a later successful retry applies the same trial exactly once.
 failure=reload(e,lambda raw:funded(raw,e.now,rng_for(0,200)));old=bytes(failure.files[key(failure)]);failure.failwrite=True;failure.advance(DAY);tick(failure)
 assert bytes(failure.files[key(failure)])==old and not any(k.endswith('.tmp') for k in failure.files)
 failure.failwrite=False;failure.advance(1);tick(failure);assert failure.get(M+4)==95000 and rows(failure)[0][4]==5000
 # Shop loss at day one stops production at that time, even after two days
 # offline. Keep the 24h rent inventory, saved formation, and no extra loss.
 shop=fixture(True);shop.edit(0);p=shop.get(M+0x84);shop.put(p+8,2);shop.save();shop.request(3)
 garrison=next(k for k in shop.files if k.endswith('-shop-71000001.def'));line=bytes(shop.files[garrison])
 def shop_ready(raw):
  funded(raw,shop.now,rng_for(0,1000));struct.pack_into('<I',raw,796,shop.now+10*DAY);struct.pack_into('<I',raw,800,shop.now)
  struct.pack_into('<5I',raw,416,shop.now,0,0,0,0)
 lost=reload(shop,shop_ready);lost.advance(2*DAY);oldarmy=lost.held();tick(lost)
 assert lost.owned()==0 and word(lost,808) and lost.get(lost.shops()[0]+8)==word(lost,808)
 assert (lost.get(M+4),lost.get(M+8),lost.held())==(95000,47500,oldarmy)
 assert (word(lost,420),word(lost,424))==(960,480) and bytes(lost.files[garrison])==line
 if len(lost.files[key(lost)])>2840:assert lost.get(M+12)==7
 assert rows(lost)[0][3:]==(3,5000,4) and word(lost,872)==0x71000001
 saved_stock=(word(lost,420),word(lost,424));lost.advance(DAY);tick(lost);assert (word(lost,420),word(lost,424))==saved_stock
 # Scout and recapture an NPC-held merchant using the existing real local
 # entry paths. No editor line is cleared and rent resumes from recapture.
 lost.scout_shop(0);board(lost);assert struct.unpack_from('<III',lost.plants(),0)==(2,0,2);lost.cancel()
 claim(lost,0);assert lost.owned()==1 and word(lost,808)==0 and word(lost,800)==lost.now
 assert (word(lost,420),word(lost,424))==saved_stock and bytes(lost.files[garrison])==line
 # A different player never inherits clocks, pending revenge or occupiers.
 lost.put(PM+0x74,43);lost.enter();assert word(lost,1032)==0 and word(lost,808)==0
 # The acceptance-only code exercises the real redemption callback and the
 # same transaction path. Formal builds reject it, including after upgrading
 # from an armed test build; no host clock or production time is accelerated.
 from check_offline_pvp_arm import BASE
 from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_LR
 class Acceptance(GarrisonEngine):
  def __init__(self):super().__init__();self.dismissals=0
  def hook(self,em,a,size,data):
   if a==BASE+0x3feb40:
    self.dismissals+=1;em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
   return super().hook(em,a,size,data)
  def redeem(self):
   ui=self.alloc(0x100);field=self.alloc(0x110);self.put(ui+0xac,field);self.string(field+0xa4,'raid!',True)
   self.run('offlineRedeem',ui);return self.u.reg_read(UC_ARM_REG_R0)
 prepared=fixture(True);a=Acceptance();a.files={k:bytearray(v) for k,v in prepared.files.items()}
 raw=a.files[key(prepared)];funded(raw,prepared.now,rng_for(9900,10000));crc(raw)
 a.advance(prepared.now-a.now);a.enter();a.run('offlineGarden');before=rows(a);wall=a.now;loads=len(a.loads)
 test_build=c.OUT.name.endswith('-test')
 if test_build:
  assert a.redeem()==1 and a.dismissals==1 and a.now==wall
  assert word(a,2828)==3 and word(a,2832)==wall+30 and word(a,2836)==0
  seq=word(a,20);assert a.redeem()==1 and word(a,20)==seq,'acceptance trigger was armed twice'
  a.advance(29);tick(a);assert rows(a)==before
  a.advance(1);tick(a);assert len(rows(a))==len(before)+2 and word(a,2836)==3 and len(a.loads)==loads
  assert (a.get(M+4),a.get(M+8),a.owned())==(90250,45125,0)
  assert rows(a)[0][5]==4 and rows(a)[1][5]==3 and word(a,752)==1
  r=reload(a);old=rows(r);r.advance(31);tick(r);assert rows(r)==old and r.get(M+4)==90250
 else:
  assert a.redeem()==0 and a.dismissals==0 and rows(a)==before
  def stale_test(raw):struct.pack_into('<3I',raw,2828,3,prepared.now-1,0)
  clean=reload(a,stale_test);tick(clean)
  assert word(clean,2828)==word(clean,2832)==word(clean,2836)==0 and rows(clean)==before
 report={'daily_fbi_exact_2_percent':True,'no_stacked_fbi_rolls':True,'ordinary_reference_5_win_5_loss':True,'beaten_fbi_95_win_5_none':True,'mutually_exclusive_revenge_results':True,'wallet_only_five_percent_floor':True,'no_scene_or_player_army_change':True,'restart_and_clock_rollback_dedup':True,'atomic_failure_retry':True,'shop_day_one_loss_stops_offline_production':True,'inventory_and_garrison_retained':True,'npc_shop_scout_recapture':True,'profile_isolation':True,'runtime_game_verified':False}
 report['acceptance_trigger_once' if test_build else 'formal_rejects_test_trigger_and_clears_stale_jobs']=True
 (c.OUT/'v99-event-checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
