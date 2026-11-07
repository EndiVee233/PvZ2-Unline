"""Validate and compile six independent offline Dave formations."""
from pathlib import Path
import json,hashlib

def prepare(out,reference=False):
 if reference:
  return prepare_reference(out)
 p=Path(__file__).resolve().parents[1]/'src/offline-pvp/evil-dave.json';raw=p.read_bytes();j=json.loads(raw)
 assert j['version']==1 and len(j['rounds'])==6
 lines=['struct DaveRound {unsigned count,plants[16][3];};','static const DaveRound DAVE_ROUNDS[]={'];seen=set()
 for r in j['rounds']:
  plants=r['plants'];assert 1<=len(plants)<=16 and len({(p[1],p[2]) for p in plants})==len(plants)
  assert all(t in (2,3,6) and 0<=row<5 and 0<=col<9 for t,row,col in plants)
  key=tuple(map(tuple,plants));assert key not in seen;seen.add(key)
  lines.append('{%d,{%s}},'%(len(plants),','.join('{%d,%d,%d}'%tuple(p) for p in plants)))
 lines+=['};','static constexpr unsigned DAVE_ROUND_COUNT=6;'];out=Path(out)
 (out/'dave_presets.h').write_text('\n'.join(lines)+'\n',encoding='utf8')
 record=dict(source_sha256=hashlib.sha256(raw).hexdigest(),rounds=6,plant_counts=[len(r['plants']) for r in j['rounds']],original_server_formations_restored=False,reward_and_reset_policy_not_changed=True)
 (out/'dave-build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');return record

def prepare_reference(out):
 root=Path(__file__).resolve().parents[1]
 raw=(root/'src/offline-pvp/dave-reference.json').read_bytes();data=json.loads(raw)
 # Exact native PlantType ids from the original 1.7.5 constructor/catalogue.
 types=dict(peashooter=2,wallnut=3,tallnut=4,bonkchoy=5,potatomine=13,
            snapdragon=15,spikeweed=16,kernelpult=19,snowpea=21,bloomerang=27,
            starfruit=31,wintermelon=34,turnip=42,peach=43,bamboo=45)
 assert data['version']==1 and len(data['rounds'])==6
 lines=['struct DaveRound {unsigned count,plants[45][3],level,medals;};',
        'static const DaveRound DAVE_ROUNDS[]={']
 counts=[];resolved=[]
 for index,r in enumerate(data['rounds']):
  assert len(r['rows'])==5 and all(len(row)==9 for row in r['rows'])
  assert r['level']==(1,1,2,2,2,3)[index]
  assert r['coins']==0 and r['medals']==250+50*index
  plants=[(types[data['legend'][symbol]],row,col)
          for row,line in enumerate(r['rows']) for col,symbol in enumerate(line) if symbol!='.']
  assert len(plants)==(11,16,23,18,26,24)[index]
  assert len({p[0] for p in plants})<=16
  lines.append('{%d,{%s},%d,%d},'%(len(plants),','.join('{%d,%d,%d}'%p for p in plants),r['level'],r['medals']))
  counts.append(len(plants));resolved.append(dict(round=index+1,level=r['level'],medals=r['medals'],plants=plants))
 lines+=['};','static constexpr unsigned DAVE_ROUND_COUNT=6;']
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 (out/'dave_presets.h').write_text('\n'.join(lines)+'\n',encoding='utf8')
 record=dict(source_sha256=hashlib.sha256(raw).hexdigest(),rounds=resolved,plant_counts=counts,
             formation_source='user screenshots; tiers user confirmed',reset_policy_not_changed=True,
             prior_wins_preserved_no_retroactive_rewards=True,runtime_game_verified=False)
 (out/'dave-build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
 return record
