"""Paginate original Dave result dialogue without changing words or speaker tags."""
from pathlib import Path
import hashlib,json,re,struct,zlib
from merge_legacy_pvp_resources import Bundle,u32,trie_write

def pages(line,limit=32):
 tokens=re.findall(r'\{[^}]*\}|.',line);out=[];chunk='';count=0
 for token in tokens:
  if token.startswith('{'):chunk+=token;continue
  if count==limit:out.append(chunk);chunk='';count=0
  chunk+=token;count+=1
 if chunk:out.append(chunk)
 assert ''.join(out)==line
 return out

def prepare(resource,out):
 bundle=Bundle(resource);changes=[]
 for i in range(len(bundle.groups)):
  files=bundle.files(i)
  for index,(name,info) in enumerate(files):
   if not name.endswith('\\LAWNSTRINGS.TXT'):continue
   old=bundle.payloads[i];off=u32(old,24);section=old[off:off+u32(old,28)]
   if u32(old,16)&2:section=zlib.decompress(section)
   raw=section[info[1]:info[1]+info[2]];text=raw.decode('utf-8-sig');newline='\r\n' if '\r\n' in text else '\n'
   for prefix in ['NARRATIVE_MAP_PVPEVILDAVID_FAILED_INTRO_']+[f'NARRATIVE_MAP_PVPEVILDAVID_SUCCESS_{n}_INTRO_' for n in range(1,7)]:
    pattern=r'\['+prefix+r'(\d+)\]\r?\n([^\r\n]+)';matches=list(re.finditer(pattern,text));assert matches
    assert [int(m[1]) for m in matches]==list(range(1,len(matches)+1))
    chunks=[p for m in matches for p in pages(m[2])]
    replacement=(newline*2).join('['+prefix+str(k+1)+']'+newline+p for k,p in enumerate(chunks))
    old_text=''.join(m[2] for m in matches);assert ''.join(chunks)==old_text
    assert all(len(re.sub(r'\{[^}]*\}','',p))<=32 for p in chunks)
    text=text[:matches[0].start()]+replacement+text[matches[-1].end():]
    changes.append(dict(prefix=prefix,old_pages=len(matches),new_pages=len(chunks),text_and_tags_preserved=True))
   replacement=(b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+text.encode('utf8')
   pos=len(section);section+=replacement;entries=list(files);entries[index]=(name,(0,pos,len(replacement)))
   section+=bytes((-len(section))%4096);table=trie_write(entries,1);head=bytearray(old[:off]);at=u32(head,0x4c);assert at+len(table)<=off
   head[at:at+len(table)]=table;struct.pack_into('<I',head,0x48,len(table));struct.pack_into('<I',head,16,u32(head,16)&~2)
   struct.pack_into('<II',head,28,len(section),len(section));struct.pack_into('<I',head,40,len(head)+len(section))
   textures=old[u32(old,40):u32(old,40)+u32(old,44)];bundle.payloads[i]=head+section+textures;bundle.sync_info(i)
 assert len(changes)==7
 result=bundle.build();check=Bundle(result)
 for i in range(len(bundle.groups)):assert check.payloads[i]==bundle.payloads[i]
 record=dict(changes=changes,predecessor_sha256=hashlib.sha256(resource).hexdigest(),sha256=hashlib.sha256(result).hexdigest(),size=len(result))
 out=Path(out);(out/'dynamic-dave-dialogue.rsb.smf').write_bytes(result);(out/'dave-dialogue-build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');return result,record
