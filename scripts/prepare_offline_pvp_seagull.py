"""Restore the missing original PvP seagull rig and projectile resources.

Only ZombiePVPSeagullGroup is imported; current shared pirate/explorer assets
and the deferred potion-art candidate remain byte-identical.
"""
from pathlib import Path
from io import BytesIO
import copy,hashlib,json,struct,zlib
from merge_legacy_pvp_resources import Bundle,u32,trie_write
from prepare_offline_pvp_skill_art import patch_pam
from pam_transform_index import PamIndex

GROUP='ZombiePVPSeagullGroup'

def section(bundle,i):
 block=bundle.payloads[i];start=u32(block,24)
 data=bytes(block[start:start+u32(block,28)])
 return zlib.decompress(data) if u32(block,16)&2 else data

def prepare(current,legacy,out):
 if legacy[:4]==bytes.fromhex('d4feadde'):legacy=zlib.decompress(legacy[8:])
 base,source=Bundle(current),Bundle(legacy)
 mi,mn,manifest=base.manifest();_,_,old_manifest=source.manifest()
 assert not any(g['ID'].startswith(GROUP+'_') for g in base.groups)
 wanted={i for i,g in enumerate(source.groups) if g['ID'].startswith(GROUP+'_')}
 assert {source.groups[i]['ID'] for i in wanted}=={GROUP+'_640',GROUP+'_Common'}
 preserved=[bytes(p) for p in base.payloads];remap={};changes=[]
 for j in sorted(wanted):
  i=len(base.groups);remap[j]=i
  base.groups.append(copy.deepcopy(source.groups[j]));base.infos.append(bytearray(source.infos[j]));base.pools.append(bytearray(source.pools[j]));base.payloads.append(bytearray(source.payloads[j]))
  count,start=struct.unpack_from('<II',base.infos[i],196)
  struct.pack_into('<I',base.infos[i],200,len(base.textures));base.textures.extend(copy.deepcopy(source.textures[start:start+count]))
  # Preserve the original image pixels. Their PAM image bases are normalized
  # for the 1536 selection; bone/frame transforms and events are untouched.
  files=base.files(i);data=section(base,i);entries=list(files)
  for k,(name,info) in enumerate(files):
   if not name.endswith('.PAM'):continue
   raw=data[info[1]:info[1]+info[2]];fixed,record=patch_pam(raw,True)
   before,after=PamIndex(raw),PamIndex(fixed)
   assert all(a['name']==b['name'] for a,b in zip(before.sprites,after.sprites))
   entries[k]=(name,(0,len(data),len(fixed)));data+=fixed
   changes.append(dict(name=name,old_sha256=hashlib.sha256(raw).hexdigest(),sha256=hashlib.sha256(fixed).hexdigest(),**record))
  if entries!=files:
   old=base.payloads[i];off=u32(old,24);head=bytearray(old[:off]);table=trie_write(entries,1);to=u32(head,0x4c);assert to+len(table)<=off
   head[to:to+len(table)]=table;struct.pack_into('<I',head,0x48,len(table));data+=bytes((-len(data))%4096)
   struct.pack_into('<I',head,16,u32(head,16)&~2);struct.pack_into('<II',head,28,len(data),len(data));struct.pack_into('<I',head,40,len(head)+len(data))
   tex=old[u32(old,40):u32(old,40)+u32(old,44)];base.payloads[i]=head+data+tex
  base.sync_info(i)
 for comp in source.composites:
  if bytes(comp[:128]).split(b'\0')[0].decode()!=GROUP:continue
  row=bytearray(comp);indices=[u32(row,128+16*k) for k in range(u32(row,1152))]
  assert set(indices)==wanted
  for k,j in enumerate(indices):
   struct.pack_into('<I',row,128+16*k,remap[j])
   if u32(row,132+16*k)==640:struct.pack_into('<I',row,132+16*k,1536)
  base.composites.append(row)
 slot=manifest['slot_count'];groups=[]
 for original in old_manifest['groups']:
  if original['id'] not in (GROUP,GROUP+'_640',GROUP+'_Common'):continue
  item=copy.deepcopy(original)
  if item.get('res')=='640':item['res']='1536'
  for sub in item.get('subgroups',[]):
   if sub.get('res')=='640':sub['res']='1536'
  for resource in item.get('resources',[]):resource['slot']=slot;slot+=1
  groups.append(item)
 assert len(groups)==3 and len(changes)==2
 manifest['groups'].extend(groups);manifest['slot_count']=slot;base.replace_manifest(mi,mn,manifest)
 result=base.build();check=Bundle(result)
 assert check.manifest()[2]==manifest
 for i,block in enumerate(preserved):
  if i!=mi:assert check.payloads[i]==block,'unrelated resource group changed'
 for j,i in remap.items():
  assert check.payloads[i]==base.payloads[i]
  old=source.payloads[j];new=check.payloads[i]
  assert old[u32(old,40):u32(old,40)+u32(old,44)]==new[u32(new,40):u32(new,40)+u32(new,44)]
 resources=[r for g in groups for r in g.get('resources',[])]
 assert len({r['id'] for r in resources})==len(resources)
 record=dict(group=GROUP,added_groups=[source.groups[j]['ID'] for j in sorted(wanted)],changes=changes,
  original_sha256=hashlib.sha256(legacy).hexdigest(),predecessor_sha256=hashlib.sha256(current).hexdigest(),sha256=hashlib.sha256(result).hexdigest(),size=len(result),
  shared_pirate_explorer_and_potions_unchanged=True,atlas_pixels_unchanged=True,animation_labels_commands_and_bones_preserved=True)
 out=Path(out);(out/'zombie2-seagull.rsb.smf').write_bytes(result);(out/'seagull-resource-build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
 return result,record
