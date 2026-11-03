"""Recover normal arena flag configuration using the existing tutorial values."""
from pathlib import Path
import sys,zipfile,hashlib,json,zlib
from io import BytesIO
sys.path[:0]=['scripts','src/tools','K:/pvz2-tools/pyvz2/OBBEdit/libraries']
from merge_legacy_pvp_resources import Bundle,u32
from pyvz2rton import RTONDecoder
from py3rijndael import RijndaelCbc,ZeroPadding
key=hashlib.md5(b'com_popcap_pvz2_magento_product_2013_05_05').hexdigest().encode()
cipher=RijndaelCbc(key,key[4:28],ZeroPadding(24),block_size=24)
from io import StringIO
from merge_legacy_pvp_resources import trie_write
from pyvz2rton import JSONDecoder
import struct
with_inbattleanim='--with-inbattleanim' in sys.argv
with zipfile.ZipFile('work/pvp-v32/PvZ2-v32-first-pvp-tutorial-skills.apk') as z:
 original=z.read('assets/reconstruction/dynamic-original-speed.rsb.smf')
bundle=Bundle(original)
for i,g in enumerate(bundle.groups):
 files=bundle.files(i)
 hit=next(((n,info) for n,info in files if n.endswith('LEVELS\\ARENA_PLANT_TEST.RTON')),None)
 if not hit:continue
 name,info=hit;old=bundle.payloads[i];off=u32(old,0x18)
 sec=old[off:off+u32(old,0x1c)]
 if u32(old,0x10)&2:sec=zlib.decompress(sec)
 raw=sec[info[1]:info[1]+info[2]]
 assert raw[:2]==b'\x10\0'
 f=BytesIO(cipher.decrypt(raw[2:])[4:]);f.name=name
 j=json.loads(RTONDecoder(repairFiles=False).parse_root_object(f))
 props=next(o['objdata'] for o in j['objects'] if o['objclass']=='ArenaPlantProperties')
 props.update(ResourceGroupNames=['PVP_Brain'],MowerEntryAnimDuration=2.5,MowerActivatedAudioEvent='Play_Lawn_Lawnmower',MowerPopAnim='POPANIM_EFFECTS_BRAIN')
 if with_inbattleanim:props['ResourceGroupNames'].append('PVP_INBATTLEANIM')
 encoded=JSONDecoder().encode_root_object(StringIO(json.dumps(j,ensure_ascii=False)))
 replacement=b'\x10\0'+cipher.encrypt(encoded)
 pos=len(sec);sec=bytes(sec)+replacement;sec+=bytes((-len(sec))%4096)
 entries=[(n,(0,pos,len(replacement)) if n==name else data) for n,data in files]
 table=trie_write(entries,1)
 head=bytearray(old[:off]);to=u32(head,0x4c)
 assert to+len(table)<=len(head)
 head[to:to+len(table)]=table;struct.pack_into('<I',head,0x48,len(table))
 tex=old[u32(old,0x28):u32(old,0x28)+u32(old,0x2c)]
 struct.pack_into('<I',head,0x10,u32(head,0x10)&~2)
 struct.pack_into('<II',head,0x1c,len(sec),len(sec))
 struct.pack_into('<I',head,0x28,len(head)+len(sec))
 bundle.payloads[i]=head+sec+tex;bundle.sync_info(i)
 result=bundle.build();check=Bundle(result)
 assert len(check.groups)==len(bundle.groups)
 for k in range(len(bundle.groups)):
  if k!=i:assert check.payloads[k]==bundle.payloads[k]
  else:assert check.files(k)==entries
 Path('work/pvp-v33/dynamic-flags.rsb.smf').write_bytes(result)
 print('source_sha256',hashlib.sha256(original).hexdigest(),'target_sha256',hashlib.sha256(result).hexdigest(), 'size',len(result))
 break
else:raise ValueError('Missing ordinary arena level')
