"""Extract the original name-entry pool and emit read-only native NPC presets."""
from pathlib import Path
import sys,zipfile,json,zlib,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from merge_legacy_pvp_resources import Bundle,u32

def generate(out):
 with zipfile.ZipFile(ROOT/'pvz2data.zip') as z:
  bundle=Bundle(z.read('com.popcap.pvz2cthd/files/dynamic.rsb.smf'))
 i,name,info=next((i,n,k) for i in range(len(bundle.groups)) for n,k in bundle.files(i) if n.endswith('PROPERTIES\\RANDOMSTRINGS.TXT'))
 d=bundle.payloads[i];sec=d[u32(d,0x18):u32(d,0x18)+u32(d,0x1c)]
 if u32(d,0x10)&2:sec=zlib.decompress(sec)
 raw=sec[info[1]:info[1]+info[2]]
 lines=[s.strip() for s in raw.decode('utf8').splitlines() if s.strip()]
 assert len(lines)==2
 prefixes,suffixes=[s.split(',') for s in lines]
 config=json.loads((ROOT/'src/offline-pvp/neighbors.json').read_text(encoding='utf8'))
 text=['struct NpcPreset { unsigned id,zone,position,level,count; unsigned name[40]; unsigned plants[16][3]; };','static const NpcPreset NPCS[] = {']
 names=set();slots=set()
 for index,npc in enumerate(config['neighbors']):
  key=(npc['zone'],npc['position']);assert key not in slots and key!=(1,1);slots.add(key)
  assert 1<=npc['zone']<=6 and 1<=npc['position']<=(5 if npc['zone']==1 else 3)
  assert len(npc['plants'])<=16
  assert len({(p[1],p[2]) for p in npc['plants']})==len(npc['plants'])
  assert all(0<=r<5 and 0<=c<9 and t in (2,3,6) for t,r,c in npc['plants'])
  seed=(npc['id']*2654435761)&0xffffffff
  name=prefixes[seed%len(prefixes)]+suffixes[(seed//len(prefixes))%len(suffixes)]
  assert name not in names and len(name)<40;names.add(name)
  chars=','.join(str(ord(c)) for c in name)+',0'
  plants=','.join('{'+','.join(map(str,p))+'}' for p in npc['plants'])
  text.append('{%d,%d,%d,%d,%d,{%s},{%s}},'%(npc['id'],*key,npc['level'],len(npc['plants']),chars,plants))
 text+=['};','static constexpr unsigned NPC_COUNT=sizeof(NPCS)/sizeof(NPCS[0]);']
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 (out/'npc_presets.h').write_text('\n'.join(text)+'\n',encoding='utf8')
 record=dict(source='PROPERTIES/RANDOMSTRINGS.TXT',source_sha256=hashlib.sha256(raw).hexdigest(),prefix_count=len(prefixes),suffix_count=len(suffixes),neighbors=len(names),unique_slots=True,unique_names=True)
 (out/'names-build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
 return record
if __name__=='__main__':print(json.dumps(generate(ROOT/'work/pvp-v37/generated')))
