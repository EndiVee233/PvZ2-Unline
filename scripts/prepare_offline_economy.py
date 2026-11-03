"""Build local PvP star-coin prices and training presets from the owned bundle."""
from pathlib import Path
from io import BytesIO,StringIO
import sys,json,zlib,zipfile,hashlib,struct
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src/tools'),'K:/pvz2-tools/pyvz2/OBBEdit/libraries']
from merge_legacy_pvp_resources import Bundle,u32,trie_write
from pyvz2rton import RTONDecoder,JSONDecoder
from py3rijndael import RijndaelCbc,ZeroPadding
key=hashlib.md5(b'com_popcap_pvz2_magento_product_2013_05_05').hexdigest().encode();cipher=RijndaelCbc(key,key[4:28],ZeroPadding(24),block_size=24)

def prepare(source,out):
 out=Path(out);out.mkdir(exist_ok=True,parents=True)
 with zipfile.ZipFile(source) as z:original=z.read('assets/reconstruction/dynamic-original-speed.rsb.smf')
 b=Bundle(original);changed=[];strings={};specs=[]
 for i in range(len(b.groups)):
  files=b.files(i);old=b.payloads[i];off=u32(old,0x18);sec=old[off:off+u32(old,0x1c)]
  if u32(old,0x10)&2:sec=zlib.decompress(sec)
  entries=list(files);modified=False
  for idx,(name,info) in enumerate(files):
   if not name.endswith(('\\TRAININGTYPES.RTON','\\MAGENTO.RTON')):continue
   raw=sec[info[1]:info[1]+info[2]]
   if raw[:2]==b'\x10\0':raw=cipher.decrypt(raw[2:])
   fp=BytesIO(raw[4:]);fp.name=name;j=json.loads(RTONDecoder(repairFiles=False).parse_root_object(fp))
   if name.endswith('TRAININGTYPES.RTON'):
    for o in j['objects']:
     p=o['objdata'];assert p['ObjectType']=='zombie'
     specs.append((p['TypeName'],p['CostPVPCoin'],p['SpaceSize'],int(p['TrainingTime']),p['NeedHomeLevel']))
    continue
   categories=[o['objdata'] for o in j['objects'] if o.get('objclass')=='MagentoCategoryProps' and o['objdata'].get('Name')=='pvpCoins']
   assert len(categories)==1 and categories[0]['Products']==[f'RTID(MagentoProduct_pvp_coin_bag{i}@Magento)' for i in (1,2,3)] and not categories[0].get('Defaults'), 'dedicated bank index order changed'
   for o in j['objects']:
    if not o.get('aliases',[''])[0].startswith('MagentoProduct_pvp_coin_bag'):continue
    p=o['objdata'];count=p['ObjectCount'];assert count in (5000,20000,75000)
    price=count*110//5000;assert price*5000==count*110
    p['ObjectPurchaseType']='gem';p['Prices']=[{'Name':'','Price':price}]
    tag='V38_PVP_'+str(count);p['Names']=['['+tag+']']*6;p['ShortDescriptions']=['['+tag+']']*6;p['Descriptions']=['['+tag+']']*6
    strings[tag]='获得'+str(count)+'星币';changed.append(dict(receive_starcoins=count,spend_diamonds=price))
   encoded=JSONDecoder().encode_root_object(StringIO(json.dumps(j,ensure_ascii=False)));replacement=b'\x10\0'+cipher.encrypt(encoded)
   pos=len(sec);sec+=replacement;entries[idx]=(name,(0,pos,len(replacement)));modified=True
  if modified:
   sec+=bytes((-len(sec))%4096);table=trie_write(entries,1);head=bytearray(old[:off]);to=u32(head,0x4c);assert to+len(table)<=len(head)
   head[to:to+len(table)]=table;struct.pack_into('<I',head,0x48,len(table));struct.pack_into('<I',head,0x10,u32(head,0x10)&~2)
   struct.pack_into('<II',head,0x1c,len(sec),len(sec));struct.pack_into('<I',head,0x28,len(head)+len(sec))
   tex=old[u32(old,0x28):u32(old,0x28)+u32(old,0x2c)];b.payloads[i]=head+sec+tex;b.sync_info(i)
 assert len(changed)==3 and len(specs)==12
 h=['struct TrainSpec {char name[32]; unsigned cost,space,seconds,level;};','static const TrainSpec TRAIN_SPECS[]={']
 for name,cost,space,seconds,level in specs:
  assert len(name)<32 and name.isascii();h.append('{"%s",%d,%d,%d,%d},'%(name,cost,space,seconds,level))
 h+=['};','static constexpr unsigned TRAIN_COUNT=sizeof(TRAIN_SPECS)/sizeof(TRAIN_SPECS[0]);']
 (out/'training_presets.h').write_text('\n'.join(h)+'\n',encoding='utf8')
 strings.update(V38_NOTICE_TITLE='系统提示',V38_PVP_SAVE_ERROR='本地数据保存失败，请重试',V38_PVP_CAPACITY='训练容量已满',V38_PVP_LOCKED='基地等级不足，尚未解锁该僵尸')
 result=b.build();check=Bundle(result)
 for i in range(len(b.groups)):assert check.payloads[i]==b.payloads[i]
 (out/'dynamic-economy.rsb.smf').write_bytes(result)
 record=dict(prices=changed,training_types=len(specs),old_resource_sha256=hashlib.sha256(original).hexdigest(),resource_sha256=hashlib.sha256(result).hexdigest(),resource_size=len(result))
 (out/'economy-build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
 return result,strings,record
if __name__=='__main__':print(json.dumps(prepare(ROOT/'work/pvp-v36/PvZ2-v36-defense-return-flash-fix.apk',ROOT/'work/pvp-v38/generated')[2]))
