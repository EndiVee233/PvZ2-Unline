"""Match the PvP basic zombie rig to the currently installed shared mummy art."""
from pathlib import Path
from io import BytesIO,StringIO
import copy,hashlib,json,struct,zlib
from prepare_offline_economy import Bundle,u32,trie_write,cipher,RTONDecoder,JSONDecoder

def prepare(resource,out):
 bundle=Bundle(resource);changes=[]
 for i in range(len(bundle.groups)):
  files=bundle.files(i)
  for index,(name,info) in enumerate(files):
   if not name.endswith('\\ZOMBIETYPES.RTON'):continue
   old=bundle.payloads[i];off=u32(old,0x18);section=old[off:off+u32(old,0x1c)]
   if u32(old,0x10)&2:section=zlib.decompress(section)
   raw=section[info[1]:info[1]+info[2]];encrypted=raw[:2]==b'\x10\0'
   if encrypted:raw=cipher.decrypt(raw[2:])
   fp=BytesIO(raw[4:]);fp.name=name;original=json.loads(RTONDecoder(repairFiles=False).parse_root_object(fp));data=copy.deepcopy(original)
   zombie=next(o['objdata'] for o in data['objects'] if o.get('aliases')==['pvp_change'])
   mummy=next(o['objdata'] for o in data['objects'] if o.get('aliases')==['mummy'])
   assert zombie['PopAnim']==mummy['PopAnim'] and zombie['ResourceGroups']==mummy['ResourceGroups']
   before=zombie['AnimRigClass'];assert before=='ZombieAnimRig_EgyptBasic' and mummy['AnimRigClass']=='ZombieAnimRig_IceAgeBasic'
   zombie['AnimRigClass']=mummy['AnimRigClass'];assert zombie['ZombieClass']=='ZombiePvpChange'
   encoded=JSONDecoder().encode_root_object(StringIO(json.dumps(data,ensure_ascii=False)))
   fp=BytesIO(encoded[4:]);fp.name=name;assert json.loads(RTONDecoder(repairFiles=False).parse_root_object(fp))==data
   replacement=b'\x10\0'+cipher.encrypt(encoded) if encrypted else encoded
   pos=len(section);section+=replacement;entries=list(files);entries[index]=(name,(0,pos,len(replacement)))
   section+=bytes((-len(section))%4096);table=trie_write(entries,1);head=bytearray(old[:off]);to=u32(head,0x4c);assert to+len(table)<=off
   head[to:to+len(table)]=table;struct.pack_into('<I',head,0x48,len(table));struct.pack_into('<I',head,0x10,u32(head,0x10)&~2)
   struct.pack_into('<II',head,0x1c,len(section),len(section));struct.pack_into('<I',head,0x28,len(head)+len(section))
   textures=old[u32(old,0x28):u32(old,0x28)+u32(old,0x2c)];bundle.payloads[i]=head+section+textures;bundle.sync_info(i)
   # Reversing this single field must reproduce the complete original object.
   zombie['AnimRigClass']=before;assert data==original
   changes.append(dict(name=name,zombie='pvp_change',old_rig=before,new_rig=mummy['AnimRigClass'],zombie_class_preserved=True))
 assert len(changes)==1
 result=bundle.build();check=Bundle(result)
 for i in range(len(bundle.groups)):assert check.payloads[i]==bundle.payloads[i]
 record=dict(changes=changes,predecessor_sha256=hashlib.sha256(resource).hexdigest(),resource_sha256=hashlib.sha256(result).hexdigest(),resource_size=len(result))
 out=Path(out);(out/'dynamic-pvp-rig.rsb.smf').write_bytes(result);(out/'rig-resource-build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
 return result,record
