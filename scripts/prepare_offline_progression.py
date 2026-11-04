"""Extract original base/lawn/camp upgrade values without changing assets."""
from pathlib import Path
from io import BytesIO
import json,zlib
from prepare_offline_economy import Bundle,u32,cipher,RTONDecoder

def prepare(resource,out):
 b=Bundle(resource)
 for i in range(len(b.groups)):
  hit=next(((n,k) for n,k in b.files(i) if n.endswith('\\PVPUPGRADE.RTON')),None)
  if not hit:continue
  n,k=hit;d=b.payloads[i];sec=d[u32(d,0x18):u32(d,0x18)+u32(d,0x1c)]
  if u32(d,0x10)&2:sec=zlib.decompress(sec)
  raw=sec[k[1]:k[1]+k[2]]
  if raw[:2]==b'\x10\0':raw=cipher.decrypt(raw[2:])
  f=BytesIO(raw[4:]);f.name=n;j=json.loads(RTONDecoder(repairFiles=False).parse_root_object(f))['objects'][0]['objdata']
  lines=['struct BaseSpec {unsigned coins,medals,coinLimit,medalLimit,cost,seconds;};','static const BaseSpec BASE_SPECS[]={']
  for p in j['base']:lines.append('{%d,%d,%d,%d,%d,%d},'%(p['coin'],p['medal'],p['coinLimit'],p['medalLimit'],p['cost'],p['time']))
  lines+=['};','struct CapacitySpec {unsigned capacity,cost,seconds;};']
  for key,name in [('sunLimit','SUN_SPECS'),('zombieLimit','CAMP_SPECS')]:
   lines.append('static const CapacitySpec '+name+'[]={')
   for p in j[key]:lines.append('{%d,%d,%d},'%(p['limit'],p['cost'],p['time']))
   lines.append('};')
  assert all(len(j[k])==20 for k in ('base','sunLimit','zombieLimit'))
  Path(out,'progression_presets.h').write_text('\n'.join(lines)+'\n',encoding='utf8')
  return dict(source=n,base_levels=20,sun_levels=20,camp_levels=20,asset_unchanged=True)
 raise ValueError('Missing PVPUPGRADE')
