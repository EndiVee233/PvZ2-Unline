"""Build the obtainable land-defense catalogue from original game properties.

PlantType RTIDs are resource identities, not the game's plant enum. Recover
the name-to-enum constructor and cross-check the four early map insertions.
"""
from pathlib import Path
from io import BytesIO
import json,re,zlib,hashlib,struct
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM
from prepare_offline_economy import Bundle,u32,cipher,RTONDecoder

EXCLUDED={
 'cherry_bomb':'immediate explosion','jalapeno':'immediate explosion',
 'gravebuster':'requires a grave','empea':'instant effect','blover':'instant effect',
 'imitater':'requires a target seed','powerlily':'instant food grant',
 'powerplant':'instant power-up','coffeebean':'requires another plant',
 'hurrikale':'instant effect','hotpotato':'requires an ice target',
 'goldleaf':'instant tile effect','ghostpepper':'temporary disappearing plant',
 'lilypad':'water-only placement','tanglekelp':'water-only placement',
}
TANK={'wallnut','tallnut','holonut','sweetpotato','chardguard','chestnut','endurian','pumpkinwitch'}
SUPPORT={'sunflower','twinsunflower','sunshroom','birthsunflower','turnip','peach','streetlamp','iceburg','stunion','stallia','torchwood','magnetshroom','sunbean','groundcherry'}
PEA={'peashooter','repeater','threepeater','snowpea','splitpea','peapod','torchwood','peanut','oakshooter','firepeashooter','xshot'}
COLD={'snowpea','wintermelon','iceburg','iceshroom','wintersweet','stallia'}
THROW={'cabbagepult','kernelpult','melonpult','wintermelon','bloomerang','carrotlauncher','pepperpult','bowlingbulb','acorn','asparagus','banana'}

def extract(bundle,suffix):
 for i in range(len(bundle.groups)):
  for n,k in bundle.files(i):
   if not n.endswith(suffix):continue
   p=bundle.payloads[i];raw=p[u32(p,24):u32(p,24)+u32(p,28)]
   if u32(p,16)&2:raw=zlib.decompress(raw)
   return raw[k[1]:k[1]+k[2]]
 raise ValueError(suffix)

def decode(raw):
 if raw[:2]==b'\x10\0':raw=cipher.decrypt(raw[2:])
 f=BytesIO(raw[4:]);f.name='public-neighbor-catalogue'
 return json.loads(RTONDecoder(repairFiles=False).parse_root_object(f))

def native_ids(native,names):
 cs=Cs(CS_ARCH_ARM,CS_MODE_ARM);cs.skipdata=True
 ins=list(cs.disasm(native[0x498200:0x49b000],0x498200));out={}
 for at,i in enumerate(ins):
  if i.mnemonic!='add' or i.op_str!='r1, pc, r1':continue
  text=None
  for prev in reversed(ins[max(0,at-12):at]):
   if prev.mnemonic=='ldr' and prev.op_str.startswith('r1, [pc, #'):
    delta=int(prev.op_str.split('#')[1].split(']')[0],0)
    p=i.address+8+struct.unpack_from('<i',native,prev.address+8+delta)[0]
    if 0<=p<len(native):text=native[p:p+80].split(b'\0')[0].decode('ascii',errors='ignore')
    break
  if text not in names:continue
  regs={};started=False
  for op in cs.disasm(native[i.address:i.address+104],i.address):
   if op.mnemonic=='bl' and op.op_str=='#0x498158':started=True;continue
   if not started:continue
   args=op.op_str.split(', ')
   if op.mnemonic=='mov' and len(args)==2 and args[1].startswith('#'):regs[args[0]]=int(args[1][1:],0)
   elif op.mnemonic=='add' and len(args)==3 and args[1] in regs and args[2].startswith('#'):regs[args[0]]=regs[args[1]]+int(args[2][1:],0)
   elif op.mnemonic=='str' and len(args)==2 and args[1]=='[r0]':
    if args[0] in regs:out[text]=regs[args[0]]
    break
 # These early entries use the map node's +14 value instead of operator[].
 for alias,addr,word,value in [('wallnut',0x498454,0xe3a03003,3),('tallnut',0x4984e4,0xe3a03004,4)]:
  assert struct.unpack_from('<I',native,addr)[0]==word;out[alias]=value
 out.update(bonkchoy=5,melonpult=7)
 assert names<=out.keys(),sorted(names-out.keys())
 assert out['lemon']==71 and out['wintermelon']==34 and out['dragonfruit']==316
 return out

def matrix(name,values,width):
 assert all(len(s)<width for s in values)
 return ['static const unsigned '+name+'[]['+str(width)+']={']+['{'+','.join(map(str,[ord(c) for c in s]+[0]))+'},' for s in values]+['};']

def prepare(resource,native,out):
 bundle=Bundle(resource);types=decode(extract(bundle,'\\PLANTTYPES.RTON'))['objects']
 props=decode(extract(bundle,'\\PROPERTYSHEETS.RTON'))['objects']
 aliases={a:o['objdata'] for o in props for a in o.get('aliases',[]) if 'objdata' in o}
 game=next(o['objdata'] for o in props if o.get('objclass')=='GamePropertySheet')
 available=set(game['PlantTypeOrder']);mapping=native_ids(native,available)
 catalogue=[];omitted={}
 for o in types:
  d=o['objdata'];name=d['TypeName']
  if name not in available:continue
  if name in EXCLUDED:omitted[name]=EXCLUDED[name];continue
  ref=re.fullmatch(r'RTID\((.+)@PropertySheets\)',d['Properties']);p=aliases[ref[1]]
  assert isinstance(p.get('Cost'),int) and 0<=p['Cost']<=5500,name
  latest=int(o['uid'].split('.')[1])>=109
  flags=(1 if name in PEA else 0)|(2 if latest else 0)|(4 if name=='lemon' else 0)|(8 if name in COLD else 0)|(16 if name in THROW else 0)|(32 if name in TANK else 0)
  catalogue.append(dict(id=mapping[name],name=name,cost=p['Cost'],max_level=p.get('MaxLevel',1),role=1 if name in TANK else 2 if name in SUPPORT else 0,flags=flags))
 assert len({p['id'] for p in catalogue})==len(catalogue)
 names=extract(bundle,'PROPERTIES\\RANDOMSTRINGS.TXT').decode('utf8').splitlines()
 prefixes,suffixes=[s.strip().split(',') for s in names if s.strip()]
 special=['','FBI探员追风','妙趣横生的刘琨','迷路的柠小檬','','寒潮预报员小雪','坚果评审员阿橡','投手教练玉米叔']
 upgrade=decode(extract(bundle,'\\PVPUPGRADE.RTON'))['objects'][0]['objdata']
 max_sun=upgrade['sunLimit'][-1]['limit']
 lines=['static constexpr unsigned NEIGHBOR_MAX_SUN='+str(max_sun)+';','struct NeighborPlantSpec {unsigned id,cost,maxLevel,role,flags;};','static const NeighborPlantSpec NEIGHBOR_PLANTS[]={']
 lines+=['{%d,%d,%d,%d,%d},'%(p['id'],p['cost'],p['max_level'],p['role'],p['flags']) for p in catalogue]
 lines+=['};','static constexpr unsigned NEIGHBOR_PLANT_COUNT=sizeof(NEIGHBOR_PLANTS)/sizeof(NEIGHBOR_PLANTS[0]);']
 lines+=matrix('NEIGHBOR_PREFIXES',prefixes,24)+matrix('NEIGHBOR_SUFFIXES',suffixes,24)+matrix('NEIGHBOR_SPECIAL_NAMES',special,40)
 lines+=matrix('NEIGHBOR_BOWL_SUFFIX',['的小碗碗'],8)
 for family in ('PREFIXES','SUFFIXES'):lines+=['static constexpr unsigned NEIGHBOR_'+family+'_COUNT=sizeof(NEIGHBOR_'+family+')/sizeof(NEIGHBOR_'+family+'[0]);']
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 (out/'neighbor_catalog.h').write_text('\n'.join(lines)+'\n',encoding='utf8')
 record=dict(source='original PlantTypeOrder, PlantTypes, PropertySheets, native enum constructor',available=len(available),eligible=len(catalogue),omitted=omitted,plants=catalogue,max_sun=max_sun,name_source_sha256=hashlib.sha256(extract(bundle,'PROPERTIES\\RANDOMSTRINGS.TXT')).hexdigest())
 (out/'neighbor-catalogue.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return record
