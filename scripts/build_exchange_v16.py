"""Build v16 exchange candidate from the verified v15 APK. No save mutation."""
from pathlib import Path
import struct,sys,json,zipfile,hashlib,shutil,zlib
from io import BytesIO,StringIO
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/tools'),'K:/pvz2-tools/pyvz2/OBBEdit/libraries']
import rsbtool
from pyvz2rton import RTONDecoder,JSONDecoder
from py3rijndael import RijndaelCbc,ZeroPadding
key=hashlib.md5(b'com_popcap_pvz2_magento_product_2013_05_05').hexdigest().encode();cipher=RijndaelCbc(key,key[4:28],ZeroPadding(24),block_size=24)
source=ROOT/'work/tutorial-v15/PvZ2-v15-skip-return-guide.apk';out=ROOT/'work/exchange-v16';out.mkdir(exist_ok=True)
def sha(b):return hashlib.sha256(b).hexdigest()
def branch(a,b):return struct.pack('<I',0xea000000|(((b-a-8)//4)&0xffffff))
def decode(b):
 if b[:2]==b'\x10\0':b=cipher.decrypt(b[2:])
 fp=BytesIO(b[4:]);fp.name='magento';return json.loads(RTONDecoder(repairFiles=False).parse_root_object(fp))
with zipfile.ZipFile(source) as z:
 dynamic=bytearray(z.read('assets/reconstruction/dynamic-original-speed.rsb.smf'));old_resource_sha=sha(dynamic)
 h=rsbtool.parse_head(dynamic);groups=rsbtool.read_rsgp_info(dynamic,h['rsgpInfo_BeginOffset'],h['rsgp_Number'],h['rsgpInfo_EachLength']);g=next(g for g in groups if g['ID'].lower()=='packages');start=g['fields'][0];d=dynamic[start:]
 assert struct.unpack_from('<I',d,0x10)[0]&2==0
 dataoff=struct.unpack_from('<I',d,0x18)[0];ln,lo=struct.unpack_from('<II',d,0x48);files=rsbtool.read_string_list(d,lo,ln,1)
 name,info=next((n,i) for n,i in files if n.upper().endswith('MAGENTO.RTON'));_,pos,size=info;absolute=start+dataoff+pos
 before=bytes(dynamic[absolute:absolute+size]);j=decode(before);original_json=json.loads(json.dumps(j));changes=[];local_strings={}
 specs={'MagentoProduct_coin_10000':(10,9000,'gem','金币兑换'), 'MagentoProduct_coin_20000':(50,45000,'gem','金币兑换'), 'MagentoProduct_coin_40000':(100,90000,'gem','金币兑换'), 'MagentoProduct_gem_20':(20000,18,'coin','钻石兑换'), 'MagentoProduct_gem_100':(100000,90,'coin','钻石兑换'), 'MagentoProduct_gem_200':(200000,180,'coin','钻石兑换'), 'MagentoProduct_gem_300':(300000,270,'coin','钻石兑换')}
 for o in j['objects']:
  alias=next(iter(o.get('aliases',[])),None)
  if alias in specs:
   price,count,currency,title=specs[alias];p=o['objdata'];p['ObjectCount']=count;p['ObjectPurchaseType']=currency;p['Prices']=[{'Name':'','Price':price}]
   unit='金币' if currency=='gem' else '钻石';tag=f'V16_{currency}_{count}';local_strings[tag+'_T']=title;local_strings[tag+'_S']=f'{count}{unit}';local_strings[tag+'_D']=f'到账{count}{unit}\n手续费10%';p['Names']=['['+tag+'_T]']*6;p['Descriptions']=['['+tag+'_D]']*6;p['ShortDescriptions']=['['+tag+'_S]']*6
   changes.append(dict(alias=alias,spend=price,spend_currency=currency,receive=count,receive_currency=p['ObjectType'],fee_percent=10))
  if o.get('objclass')=='MagentoCategoryProps' and o['objdata'].get('Name') in ['Gems','GemsFor360']:
   o['objdata']['Products']=[f'RTID({a}@Magento)' for a in specs if a.startswith('MagentoProduct_gem_')];o['objdata']['Defaults']=[]
 assert len(changes)==7
 encoded=JSONDecoder().encode_root_object(StringIO(json.dumps(j,ensure_ascii=False)))
 print('Magento plaintext encoded',len(encoded),'capacity',size,flush=True)
 newplain=encoded+bytes((size-2)-len(encoded));encrypted=b'\x10\0'+cipher.encrypt(newplain)
 assert len(encrypted)==size and decode(encrypted)==j
 dynamic[absolute:absolute+size]=encrypted;new_resource_sha=sha(dynamic)
 (out/'dynamic-exchange.rsb.smf').write_bytes(dynamic)
 # Existing BootActivity overlay updater: change only checksum strings and marker.
 from rebuild_bootstrap_dex import rebuild_bootstrap
 import re
 boot=(ROOT/'src/recovered/bootstrap/com/popcap/pvz2cthd/BootActivity.java').read_text(encoding='utf8')
 constants=dict(re.findall(r'(BASE_RESOURCE_SHA|SPEED_RESOURCE_SHA)\s*=\s*"([0-9a-f]{64})"',boot))
 assert constants['SPEED_RESOURCE_SHA']==old_resource_sha
 newmarker=b'.exchange-shop-v16-r10'
 dex=rebuild_bootstrap(z.read('classes8.dex'),out/'bootstrap',{
  constants['BASE_RESOURCE_SHA']:old_resource_sha,
  constants['SPEED_RESOURCE_SHA']:new_resource_sha,
  '.original-speed-57d9c44':newmarker.decode()},ROOT/'tools/apktool.jar')
 lib=bytearray(z.read('lib/armeabi/libSrc.so'));patches=[]
 for a,target,role in [(0x93619c,0x935ebc,'Omit restore-purchase card and child label creation'),(0x936dd0,0x936f54,'Omit cumulative recharge panel for Gems'),(0x936f50,0x936f54,'Omit cumulative recharge panel for GemsFor360'),(0x92c110,0x92c3b4,'Omit recharge footer rendering including banner and separator')]:
  old=bytes(lib[a:a+4]);assert old[3] in [0x0a,0x1a],(hex(a),old.hex());new=branch(a,target);lib[a:a+4]=new;patches.append(dict(offset=hex(a),before=old.hex(),after=new.hex(),target=hex(target),role=role))
 a=0x92b4a8;old=bytes(lib[a:a+4]);new=bytes.fromhex('00f020e3');lib[a:a+4]=new;patches.append(dict(offset=hex(a),before=old.hex(),after=new.hex(),role='Suppress root store recharge banner draw call'))
 # Alternate Gems card callback uses the cash completion even for coin payment.
 a=0x933844;old=bytes(lib[a:a+4]);new=struct.pack('<I',0xeb000000|(((0x930648-a-8)//4)&0xffffff));lib[a:a+4]=new;patches.append(dict(offset=hex(a),before=old.hex(),after=new.hex(),role='Gems card completion invokes generic local grant instead of cash completion'))
 for a,target in [(0x9323e8,0x9322e4),(0x932e58,0x932e74)]:
  old=bytes(lib[a:a+4]);new=branch(a,target);lib[a:a+4]=new;patches.append(dict(offset=hex(a),before=old.hex(),after=new.hex(),role='Skip legacy coin-spend transaction notification; retain local product grant and temporary cleanup'))
 from exchange_localization import add_exchange_localization
 lib,locpatch=add_exchange_localization(lib,local_strings);patches.append(locpatch)
 (out/'libSrc.so').write_bytes(lib)
 replacements={'assets/reconstruction/dynamic-original-speed.rsb.smf':bytes(dynamic),'classes8.dex':bytes(dex),'lib/armeabi/libSrc.so':bytes(lib)}
 with zipfile.ZipFile(out/'unsigned.apk','w',allowZip64=True) as dst:
  for i in z.infolist():
   if i.filename.startswith('META-INF/'):continue
   if i.filename in replacements:dst.writestr(i,replacements[i.filename])
   else:
    with z.open(i) as a,dst.open(i,'w') as b:shutil.copyfileobj(a,b,1024*1024)
 record=dict(candidate=True,device_verified=False,source=str(source),exchanges=changes,native_patches=patches,old_resource_sha256=old_resource_sha,new_resource_sha256=new_resource_sha,marker=newmarker.decode(),changed_payloads={n:sha(b) for n,b in replacements.items()})
 (ROOT/'docs/recovery/exchange-v16-patches.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8');(out/'magento-exchange.json').write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(record,ensure_ascii=True,indent=2))



