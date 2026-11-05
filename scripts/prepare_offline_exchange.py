"""Extract existing exchange offers; do not change goods, quantities or prices."""
from pathlib import Path
from io import BytesIO
import json,zlib
from prepare_offline_economy import Bundle,u32,cipher,RTONDecoder

def prepare(resource,out):
 b=Bundle(resource)
 for i in range(len(b.groups)):
  hit=next(((n,k) for n,k in b.files(i) if n.endswith('\\PVPSHOPCONFIGDATA.RTON')),None)
  if not hit:continue
  n,k=hit;d=b.payloads[i];sec=d[u32(d,0x18):u32(d,0x18)+u32(d,0x1c)]
  if u32(d,0x10)&2:sec=zlib.decompress(sec)
  raw=sec[k[1]:k[1]+k[2]]
  if raw[:2]==b'\x10\0':raw=cipher.decrypt(raw[2:])
  f=BytesIO(raw[4:]);f.name=n
  j=json.loads(RTONDecoder(repairFiles=False).parse_root_object(f))['objects'][0]['objdata']
  offers=[p for group in ('base','random','pad') for p in j[group]]
  assert len({p['ObjectId'] for p in offers})==len(offers)==28
  assert (j['baseCount'],j['randomCount'],j['padCount'])==(1,2,3)
  lines=['struct ExchangeSpec {unsigned id,quantity,price;};','static const ExchangeSpec EXCHANGE_SPECS[]={']
  for p in offers:
   assert 0<p['Quantity']<=100 and 0<p['Price']<=2000000000
   lines.append('{%d,%d,%d},'%(p['ObjectId'],p['Quantity'],p['Price']))
  lines+=['};','static const ExchangeSpec* exchangeSpec(unsigned id){for(const auto&s:EXCHANGE_SPECS)if(s.id==id)return &s;return nullptr;}',
   'static const unsigned EXCHANGE_REFRESH_COSTS[]={'+','.join(map(str,j['refreshCost']))+'};',
   'static constexpr unsigned EXCHANGE_AUTO_AT=%d;'%j['refreshTime']]
  out=Path(out);(out/'exchange_presets.h').write_text('\n'.join(lines)+'\n',encoding='utf8')
  record=dict(source=n,offers=offers,display_count=6,asset_unchanged=True,refresh_costs=j['refreshCost'],daily_refresh_local_seconds=j['refreshTime'],automatic_refresh_implemented=False)
  (out/'exchange-presets.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
  return record
 raise ValueError('Missing PVPSHOPCONFIGDATA')
