"""Remove the PvP rank/league entry while retaining native widget lookups."""
from pathlib import Path
from io import BytesIO,StringIO
import copy,hashlib,json,struct,zlib
from prepare_offline_economy import Bundle,u32,trie_write,cipher,RTONDecoder,JSONDecoder

def prepare(resource,out):
 bundle=Bundle(resource);changes=[]
 for i in range(len(bundle.groups)):
  entries=list(bundle.files(i))
  for j,(name,info) in enumerate(entries):
   if name!='PACKAGES\\LAYOUT\\PVPENTRY.RTON':continue
   old=bundle.payloads[i];off=u32(old,24);section=old[off:off+u32(old,28)]
   if u32(old,16)&2:section=zlib.decompress(section)
   raw=section[info[1]:info[1]+info[2]];encrypted=raw[:2]==b'\x10\0'
   if encrypted:raw=cipher.decrypt(raw[2:])
   fp=BytesIO(raw[4:]);fp.name=name;original=json.loads(RTONDecoder(repairFiles=False).parse_root_object(fp));data=copy.deepcopy(original)
   def nodes(o):
    if isinstance(o,dict):
     yield o
     for v in o.values():yield from nodes(v)
    elif isinstance(o,list):
     for v in o:yield from nodes(v)
   buttons=[n for n in nodes(data) if n.get('Name')=='RankBtn'];assert len(buttons)==1 and buttons[0]['ID']==6
   button=buttons[0];prior=copy.deepcopy(button)
   # The original controller still looks up RankIcon and updates its image.
   # Retain those objects to avoid null dereferences, but remove all geometry
   # and clipping/hit area. The native factory is independently disabled.
   for node in nodes(button):
    if 'Type' in node:
     node.update(X=-10000.0,Y=-10000.0,Width=0.0,Height=0.0,Clip=True)
     if 'Text' in node:node['Text']=''
   encoded=JSONDecoder().encode_root_object(StringIO(json.dumps(data,ensure_ascii=False)))
   fp=BytesIO(encoded[4:]);fp.name=name;assert json.loads(RTONDecoder(repairFiles=False).parse_root_object(fp))==data
   replacement=b'\x10\0'+cipher.encrypt(encoded) if encrypted else encoded
   entries[j]=(name,(0,len(section),len(replacement)));section+=replacement;section+=bytes((-len(section))%4096)
   head=bytearray(old[:off]);table=trie_write(entries,1);at=u32(head,0x4c);assert at+len(table)<=off
   head[at:at+len(table)]=table;struct.pack_into('<I',head,0x48,len(table));struct.pack_into('<I',head,16,u32(head,16)&~2)
   struct.pack_into('<II',head,28,len(section),len(section));struct.pack_into('<I',head,40,len(head)+len(section))
   textures=old[u32(old,40):u32(old,40)+u32(old,44)];bundle.payloads[i]=head+section+textures;bundle.sync_info(i)
   # Undoing this one subtree must reproduce the complete original layout.
   button.clear();button.update(prior);assert data==original
   changes.append(dict(name=name,button_id=6,native_lookups_preserved=True,rank_only_subtree=True))
 assert len(changes)==1
 result=bundle.build();check=Bundle(result)
 for i in range(len(bundle.groups)):assert check.payloads[i]==bundle.payloads[i]
 record=dict(changes=changes,predecessor_sha256=hashlib.sha256(resource).hexdigest(),sha256=hashlib.sha256(result).hexdigest(),size=len(result))
 Path(out,'no-rank-build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
 return result,record
