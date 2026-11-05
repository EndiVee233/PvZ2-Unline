"""Extract the original per-zombie evolution costs/times, without editing assets."""
from pathlib import Path
from io import BytesIO
import json,zlib,hashlib,re
from prepare_offline_economy import Bundle,u32,cipher,RTONDecoder

def prepare(resource,out):
 bundle=Bundle(resource);docs={}
 for i in range(len(bundle.groups)):
  for name,info in bundle.files(i):
   if not name.endswith(('\\PROPERTYSHEETS.RTON','\\ZOMBIETYPES.RTON')):continue
   block=bundle.payloads[i];data=block[u32(block,24):u32(block,24)+u32(block,28)]
   if u32(block,16)&2:data=zlib.decompress(data)
   raw=data[info[1]:info[1]+info[2]]
   if raw[:2]==b'\x10\0':raw=cipher.decrypt(raw[2:])
   f=BytesIO(raw[4:]);f.name=name;docs[name.split('\\')[-1]]=json.loads(RTONDecoder(repairFiles=False).parse_root_object(f))
 props={a:o['objdata'] for o in docs['PROPERTYSHEETS.RTON']['objects'] for a in o.get('aliases',[])}
 types={a:o['objdata'] for o in docs['ZOMBIETYPES.RTON']['objects'] for a in o.get('aliases',[])}
 names=re.findall(r'\{"([^"]+)"',Path(out,'training_presets.h').read_text(encoding='utf8'))
 rows=[];lines=['struct EvolutionSpec {unsigned cost[3],seconds[3];};','static const EvolutionSpec EVOLUTION_SPECS[]={']
 for name in names:
  alias=types[name]['Properties'].split('(')[1].split('@')[0];data=props[alias]
  steps=data['ZombieSkillDisplay'];assert len(steps)==3
  costs=[int(s['LevelUpNeedCoin']) for s in steps];times=[int(s['LevelUpNeedTime']) for s in steps]
  assert all(0<x<=1000000 for x in costs) and all(0<x<=604800 for x in times)
  lines.append('{{%s},{%s}},'%(','.join(map(str,costs)),','.join(map(str,times))))
  rows.append(dict(alias=name,property=alias,costs=costs,seconds=times,stats=data['ZombieLevelStats']))
 lines.append('};');Path(out,'evolution_presets.h').write_text('\n'.join(lines)+'\n',encoding='utf8')
 record=dict(source_sha256=hashlib.sha256(resource).hexdigest(),asset_unchanged=True,types=rows)
 Path(out,'evolution-presets.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
 return record
