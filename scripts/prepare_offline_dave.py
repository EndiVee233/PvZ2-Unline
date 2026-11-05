"""Validate and compile six independent offline Dave formations."""
from pathlib import Path
import json,hashlib

def prepare(out):
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
