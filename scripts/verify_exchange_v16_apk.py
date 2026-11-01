from pathlib import Path
from io import BytesIO
import sys,struct,json,zipfile,hashlib,zlib
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root/'src/tools'),'K:/pvz2-tools/pyvz2/OBBEdit/libraries']
import rsbtool
from pyvz2rton import RTONDecoder
from py3rijndael import RijndaelCbc,ZeroPadding
key=hashlib.md5(b'com_popcap_pvz2_magento_product_2013_05_05').hexdigest().encode();cipher=RijndaelCbc(key,key[4:28],ZeroPadding(24),block_size=24)
old=root/'work/tutorial-v15/PvZ2-v15-skip-return-guide.apk';new=root/'work/launch-fix/PvZ2-v16r10-currency-exchange.apk';record=json.loads((root/'docs/recovery/exchange-v16-patches.json').read_text(encoding='utf8'))
def package(data):
 h=rsbtool.parse_head(data);g=next(g for g in rsbtool.read_rsgp_info(data,h['rsgpInfo_BeginOffset'],h['rsgp_Number'],h['rsgpInfo_EachLength']) if g['ID'].lower()=='packages');start=g['fields'][0];d=data[start:];do=struct.unpack_from('<I',d,0x18)[0];ln,lo=struct.unpack_from('<II',d,0x48);_,(_,pos,size)=next((n,i) for n,i in rsbtool.read_string_list(d,lo,ln,1) if n.upper().endswith('MAGENTO.RTON'));a=start+do+pos
 p=cipher.decrypt(data[a+2:a+size]);fp=BytesIO(p[4:]);fp.name='magento';return json.loads(RTONDecoder(repairFiles=False).parse_root_object(fp)),a,size
with zipfile.ZipFile(old) as a,zipfile.ZipFile(new) as b:
 changed=[]
 for i in a.infolist():
  if i.filename.startswith('META-INF/'):continue
  j=b.getinfo(i.filename);assert i.compress_type==j.compress_type
  with a.open(i) as x,b.open(j) as y:
   if hashlib.file_digest(x,'sha256').digest()!=hashlib.file_digest(y,'sha256').digest():changed.append(i.filename)
 assert set(changed)==set(record['changed_payloads'])
 for n,sha in record['changed_payloads'].items():assert hashlib.sha256(b.read(n)).hexdigest()==sha
 assert b.testzip() is None
 name='assets/reconstruction/dynamic-original-speed.rsb.smf';before=a.read(name);after=b.read(name);orig,start,size=package(before);modified,newstart,newsize=package(after);assert (start,size)==(newstart,newsize)
 assert before[:start]==after[:start] and before[start+size:]==after[start+size:]
 specs={s['alias']:s for s in record['exchanges']};categories=['Gems','GemsFor360'];affected=[]
 assert len(orig['objects'])==len(modified['objects'])
 for x,y in zip(orig['objects'],modified['objects']):
  alias=next(iter(x.get('aliases',[])),None)
  if alias in specs:
   s=specs[alias];p=y['objdata'];assert p['ObjectCount']==s['receive'] and p['ObjectPurchaseType']==s['spend_currency'];assert p['Prices']==[{'Name':'','Price':s['spend']}]
   assert '赠送' not in str(p) and '另送' not in str(p);assert any('10%' in record['native_patches'][-1]['strings'][t.strip('[]')] for t in p['Descriptions'])
   assert (s['receive']*10==(s['spend']*1000*9 if s['spend_currency']=='gem' else s['spend']*9//1000))
   affected.append(alias)
  elif x.get('objclass')=='MagentoCategoryProps' and x['objdata'].get('Name') in categories:
   assert len(y['objdata']['Products'])==4 and y['objdata']['Defaults']==[]
  else:assert x==y,alias
 dex=b.read('classes8.dex');assert hashlib.sha1(dex[32:]).digest()==dex[12:32] and zlib.adler32(dex[12:])&0xffffffff==struct.unpack_from('<I',dex,8)[0]
 n,o=struct.unpack_from('<II',dex,56);ss=[]
 for i in range(n):
  t=struct.unpack_from('<I',dex,o+i*4)[0]
  while dex[t]&128:t+=1
  t+=1;ss.append(dex[t:dex.index(0,t)])
 assert all(a<b for a,b in zip(ss,ss[1:]))
 assert struct.unpack_from('<I',dex,96)[0]==struct.unpack_from('<I',a.read('classes8.dex'),96)[0]
 assert record['old_resource_sha256'].encode() in dex and record['new_resource_sha256'].encode() in dex and record['marker'].encode() in dex
 assert b.read('lib/armeabi/libHookPVZ2.so')==a.read('lib/armeabi/libHookPVZ2.so')
result=dict(sha256=hashlib.file_digest(new.open('rb'),'sha256').hexdigest(),output=str(new),changed_entries=changed,exactly_seven_exchange_products_verified=affected,unrelated_products_and_resources_unchanged=True,dex_integrity_verified=True,zip_crc_verified=True,device_verified=False)
(root/'docs/recovery/exchange-v16-build.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result,indent=2))
