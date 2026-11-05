"""Execute paid battle lifecycles with the built ARM payload and native stubs.

Filesystem, rendering and resource lookup are explicit engine boundaries;
this is not a substitute for the user's WSA acceptance test.
"""
from check_offline_pvp_v56_arm import DaveEngine as BattleEngine,OUT,BOARD,MODULE
from check_offline_pvp_arm import M,GM,PM
import json,struct

NPC=0x70000001
def wallet(e):
 raw=next(v for k,v in e.files.items() if k.endswith('.eco'))
 assert (len(raw),struct.unpack_from('<I',raw,4)[0]) in ((244,3),(304,4),(332,5),(344,6),(364,7),(400,8),(412,9))
 return struct.unpack('<61I',raw[:244])

def fixture():
 e=BattleEngine();e.enter();e.run('offlineGarden')
 for _ in range(3):e.train()
 ui,button,timer=e.training_ui();e.run('offlineTrainingDisplay',ui)
 e.stub(0x1059300,ui,1);e.confirm(timer)
 assert e.held()==3
 return e

def board(e):
 name=e.alloc(4);e.string(name,'arena_battle_test')
 e.run('offlineBoardLoad',BOARD,name,0xffffffff);e.live();e.put(BOARD+0xc0,5)
 e.put(MODULE+0xb0,2 if bytes(e.u.mem_read(M+0x100,1))==b'\1' else 3)

def scout(e,n=NPC):
 e.stub(0x1042fe8,M,n,3,0);board(e)

def start(e,n=NPC):e.stub(0x1042fe8,M,n,2,0)

def result(e,stars,n=NPC):
 e.put(MODULE+0x78,stars);e.stub(0x10448e8,M,stars,n,2)
 e.run('offlineTrainingTick',e.get(M+0x20))

def return_map(e):e.stub(0x104fa50,M+0x12000,0)

# Scouting and cancelling are free. Preview start debits exactly once without
# placing another formation or loading a second board.
e=fixture();initial=e.get(M+4);scout(e)
assert e.get(M+4)==initial and wallet(e)[56]==0
e.stub(0x104305c,M,4);e.run('offlineTrainingTick',e.get(M+0x20))
assert e.get(M+4)==initial and e.scenes[-1]==25
e.put(M+0x7000+0x6bc,0);e.put(GM+0xa24,0xffffffff);e.put(GM+0x984,25)
scout(e);loads=len(e.loads);positions=e.get(M+0x84);start(e)
assert e.get(M+4)==initial-1 and e.starts==1
start(e);assert e.get(M+4)==initial-1 and e.starts==1
assert len(e.loads)==loads and e.get(M+0x84)==positions
assert wallet(e)[55:]==(1,1,0,NPC,2,1)

# Each star band uses the agreed local formula, even zero deployments. Result
# callbacks, continue clicks and process restarts cannot pay a second time.
for stars,reward in enumerate((0,33,66,100)):
 f=fixture();before=f.get(M+4);medals=f.get(M+8);gems=f.gems
 scout(f);start(f);f.run(0x1030a50,M+0x14300,3);f.deaths(0)
 result(f,stars)
 assert f.get(M+4)==before-1+reward,(stars,f.get(M+4),before)
 assert (f.get(M+0xc4),f.get(M+0xc8),f.get(M+0xcc))==(reward,0,0)
 assert (f.get(M+0xac),f.get(M+0xb0))==(before-1+reward,medals)
 assert (f.get(M+8),f.gems,f.held())==(medals,gems,3)
 assert wallet(f)[55:]==(1,0,1,0,0,0)
 result(f,stars);assert f.get(M+4)==before-1+reward and f.windows==1
 return_map(f)
 result(f,stars);assert f.get(M+4)==before-1+reward and f.windows==1
 r=BattleEngine();r.copy_state(f);r.enter()
 assert r.get(M+4)==before-1+reward and r.held()==3

# A finished board can remain attached until the next scene update. It must
# not block another paid attack on the same neighbor as an "active" duplicate.
f=fixture();scout(f);start(f);f.deaths(0);result(f,0);return_map(f)
f.put(GM+0x984,25);f.put(GM+0xa24,0xffffffff)
before=f.get(M+4);loads=len(f.loads);f.stub(0x1042fe8,M,NPC,1,0)
assert len(f.loads)==loads+1 and f.get(M+4)==before-1
board(f);f.deaths(0);result(f,1)
assert f.get(M+4)==before+32 and wallet(f)[55:]==(2,0,2,0,0,0)

# Deployment losses and income share a single atomic replacement. A failed
# write changes neither, and retry pays once.
f=fixture();before=f.get(M+4);scout(f);start(f)
f.run(0x1030a50,M+0x14300,2);f.deaths(1)
saved={k:bytes(v) for k,v in f.files.items()};f.failwrite=True
result(f,3)
assert f.get(M+4)==before-1 and f.held()==3 and f.windows==0
assert {k:bytes(v) for k,v in f.files.items()}==saved
f.failwrite=False;result(f,3)
assert f.get(M+4)==before+99 and f.held()==2 and f.windows==1
result(f,3);assert f.get(M+4)==before+99 and f.held()==2

# Direct attack reserves a fee once, then commits when the real bank appears.
d=fixture();before=d.get(M+4);d.stub(0x1042fe8,M,NPC,1,0)
assert d.get(M+4)==before-1 and wallet(d)[59]==1
d.put(GM+0xa24,6);d.string(GM+0xa40,'arena_battle_test')
d.stub(0x1042fe8,M,NPC,1,0)
assert d.get(M+4)==before-1
reserved=BattleEngine();reserved.copy_state(d);reserved.enter()
assert reserved.get(M+4)==before and wallet(reserved)[56]==0
board(d);assert wallet(d)[59]==2
active=BattleEngine();active.copy_state(d);active.enter()
assert active.get(M+4)==before-1 and wallet(active)[56]==0
active.enter();assert active.get(M+4)==before-1

# No funds / failed fee save leave the live scouting board untouched. These
# cases cannot reveal the banks, debit funds, or add plants.
for failure in ('empty','write'):
 f=fixture();scout(f);before=f.get(M+4);positions=f.get(M+0x84)
 if failure=='empty':
  # Drain through successful public purchases/training is impractical for a
  # unit fixture; seed a valid zero-wallet snapshot, then load a fresh process.
  raw=bytearray(next(v for k,v in f.files.items() if k.endswith('.eco')))
  struct.pack_into('<I',raw,12,0)
  h=2166136261
  for i,c in enumerate(raw):
   if not 24<=i<28:h=((h^c)*16777619)&0xffffffff
  struct.pack_into('<I',raw,24,h)
  r=BattleEngine();r.files={k:bytearray(raw) if k.endswith('.eco') else bytearray(v) for k,v in f.files.items()};r.enter();r.run('offlineGarden');f=r;scout(f);before=0;positions=f.get(M+0x84)
 else:f.failwrite=True
 start(f)
 assert f.get(M+4)==before and f.starts==0 and f.get(M+0x84)==positions
 assert bytes(f.u.mem_read(M+0x100,1))==b'\1' and wallet(f)[56]==0

# Reject a result from another NPC, an out-of-range star count and an unpaid
# preview result. Neither income nor army losses may be committed.
f=fixture();scout(f);before=f.get(M+4);result(f,3)
assert f.windows==0 and f.get(M+4)==before
start(f);f.deaths(0);result(f,3,NPC+1);result(f,4)
assert f.windows==0 and f.get(M+4)==before-1 and wallet(f)[56]==1
result(f,2);assert f.windows==1 and f.get(M+4)==before+65

# v2 (220-byte) wallets migrate on the first new transaction without replacing
# balances, training inventory or building progress. v1 migration is covered
# by the shared v54 regression checks above.
f=fixture();key=next(k for k in f.files if k.endswith('.eco'));raw=f.files[key][:220]
struct.pack_into('<I',raw,4,2);h=2166136261
for i,c in enumerate(raw):
 if not 24<=i<28:h=((h^c)*16777619)&0xffffffff
struct.pack_into('<I',raw,24,h)
r=BattleEngine();r.files[key]=raw;r.enter();assert r.held()==3 and r.get(M+4)==f.get(M+4)
scout(r);start(r);assert wallet(r)[56]==1 and r.get(M+4)==f.get(M+4)-1

report=dict(scout_and_cancel_free=True,actual_start_costs_one_once=True,
 star_rewards=[0,33,66,100],no_medal_or_gem_awards=True,
 army_losses_and_reward_atomic=True,result_retry_and_duplicate_safe=True,
 restart_no_duplicate_reward=True,unloaded_attack_refunded=True,
 started_attack_fee_retained=True,insufficient_and_failed_write_keep_preview=True,
 invalid_stars_foreign_and_unpaid_results_rejected=True,legacy_v1_v2_wallets_preserved=True,
 previous_v56_and_v57_regressions=True,runtime_game_verified=False)
(OUT/'v60-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps(report))
