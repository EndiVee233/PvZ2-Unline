"""Split the original Evil Dave introduction using native sequential dialogue keys."""
from pathlib import Path
import hashlib,json,re,struct,zlib
from merge_legacy_pvp_resources import Bundle,u32,trie_write

KEY='NARRATIVE_MAP_PVPEVILDAVID_START_INTRO_'

def prepare(resource,out):
 bundle=Bundle(resource);matched=[]
 for i in range(len(bundle.groups)):
  files=bundle.files(i)
  for index,(name,info) in enumerate(files):
   if not name.endswith('\\LAWNSTRINGS.TXT'):continue
   old=bundle.payloads[i];off=u32(old,0x18);section=old[off:off+u32(old,0x1c)]
   if u32(old,0x10)&2:section=zlib.decompress(section)
   raw=section[info[1]:info[1]+info[2]];text=raw.decode('utf-8-sig')
   pattern=r'(\['+KEY+r'2\]\r?\n)([^\r\n]+)'
   found=re.search(pattern,text);assert found and '['+KEY+'3]' not in text
   original=found[2];split=original.index('能打败')
   first,second=original[:split],original[split:]
   assert first+second==original and len(first)<=32 and len(second)<=32
   newline='\r\n' if '\r\n' in text else '\n'
   text=text[:found.start(2)]+first+newline+newline+'['+KEY+'3]'+newline+second+text[found.end(2):]
   replacement=(b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+text.encode('utf8')
   pos=len(section);section+=replacement;entries=list(files);entries[index]=(name,(0,pos,len(replacement)))
   section+=bytes((-len(section))%4096);table=trie_write(entries,1);head=bytearray(old[:off]);table_at=u32(head,0x4c)
   assert table_at+len(table)<=off
   head[table_at:table_at+len(table)]=table;struct.pack_into('<I',head,0x48,len(table));struct.pack_into('<I',head,0x10,u32(head,0x10)&~2)
   struct.pack_into('<II',head,0x1c,len(section),len(section));struct.pack_into('<I',head,0x28,len(head)+len(section))
   textures=old[u32(old,0x28):u32(old,0x28)+u32(old,0x2c)]
   bundle.payloads[i]=head+section+textures;bundle.sync_info(i)
   matched.append(dict(group=i,name=name,original_length=len(original),page_lengths=[len(first),len(second)],text_preserved=True))
 assert len(matched)==1,matched
 result=bundle.build();check=Bundle(result)
 for i in range(len(bundle.groups)):assert check.payloads[i]==bundle.payloads[i]
 record=dict(changes=matched,predecessor_sha256=hashlib.sha256(resource).hexdigest(),resource_sha256=hashlib.sha256(result).hexdigest(),resource_size=len(result))
 out=Path(out);(out/'dynamic-scenes.rsb.smf').write_bytes(result);(out/'scene-resource-build.json').write_text(json.dumps(record,indent=2)+'\n')
 return result,record
