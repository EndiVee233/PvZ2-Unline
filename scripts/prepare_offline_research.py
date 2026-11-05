"""Extract original four-skill research prices, times and base requirements."""
from pathlib import Path
from io import BytesIO
import json,zlib,hashlib
from prepare_offline_economy import Bundle,u32,cipher,RTONDecoder

def prepare(resource,out):
 b=Bundle(resource);docs={}
 for i in range(len(b.groups)):
  for name,info in b.files(i):
   if not name.endswith(('\\PROPERTYSHEETS.RTON','\\ZOMBIETYPES.RTON')):continue
   block=b.payloads[i];data=block[u32(block,24):u32(block,24)+u32(block,28)]
   if u32(block,16)&2:data=zlib.decompress(data)
   raw=data[info[1]:info[1]+info[2]]
   if raw[:2]==b'\x10\0':raw=cipher.decrypt(raw[2:])
   f=BytesIO(raw[4:]);f.name=name;docs[name.split('\\')[-1]]=json.loads(RTONDecoder(repairFiles=False).parse_root_object(f))
 props={a:o['objdata'] for o in docs['PROPERTYSHEETS.RTON']['objects'] for a in o.get('aliases',[])}
 types={a:o['objdata'] for o in docs['ZOMBIETYPES.RTON']['objects'] for a in o.get('aliases',[])}
 names=['pvpskill_aid','pvpskill_invisible','pvpskill_rage','pvpskill_zombiefood']
 rows=[];lines=['struct ResearchSpec {char name[32];unsigned cost[3],seconds[3],base[3];};','static const ResearchSpec RESEARCH_SPECS[]={']
 for name in names:
  alias=types[name]['Properties'].split('(')[1].split('@')[0];data=props[alias]
  costs=data['UpgradeCoin'];times=data['UpgradeTime'];base=data['UpgradeBaseLevel'][1:]
  assert len(costs)==len(times)==len(base)==3 and all(0<x<=1000000 for x in costs) and all(0<x<=604800 for x in times) and base==[1,5,10]
  lines.append('{"%s",{%s},{%s},{%s}},'%(name,','.join(map(str,costs)),','.join(map(str,times)),','.join(map(str,base))))
  rows.append(dict(alias=name,property=alias,costs=costs,seconds=times,required_base=base))
 lines.append('};');Path(out,'research_presets.h').write_text('\n'.join(lines)+'\n',encoding='utf8')
 record=dict(source_sha256=hashlib.sha256(resource).hexdigest(),asset_unchanged=True,types=rows)
 Path(out,'research-presets.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');return record
