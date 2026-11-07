"""Bind normal seagull atlas cells to the original PvP animation.

No pixels are resampled or repainted. The fifty shared images use the exact
normal-game atlas bytes/metadata; PvP-only skill/projectile cells keep their
original atlas. All original PvP PAM bytes, including image transforms, stay
intact. Inputs are local owned resources, never included in source control.
"""
from pathlib import Path
from zipfile import ZipFile
import copy,hashlib,json,struct,zlib
from index_texture_prefetch import ResourceZip
from prepare_offline_pvp_seagull import Bundle,section,PamIndex,GROUP,u32
from merge_legacy_pvp_resources import trie_write

NORMAL='ZombiePirateSeagullGroup_1536'
HD_ID='ATLASIMAGE_ATLAS_ZOMBIEPVPSEAGULLGROUP_1536_HD_00'
HD_PATH=['atlases','ZombiePVPSeagullGroup_1536_HD_00']

def normal_resource(apk):
 stream=ResourceZip(apk)
 try:
  with ZipFile(stream) as z:
   path=next(n for n in z.namelist() if n.endswith('/zombie1.rsb.smf'))
   return z.read(path)
 finally:stream.map.close();stream.file.close()

def texture_section(block):
 raw=bytes(block[u32(block,40):u32(block,40)+u32(block,44)])
 return zlib.decompress(raw) if u32(block,16)&1 else raw

def replace_section(bundle,index,files,data,textures=None):
 old=bundle.payloads[index];off=u32(old,24);head=bytearray(old[:off]);table=trie_write(files,1);start=u32(head,0x4c)
 assert start+len(table)<=off,'resource table outgrew its reserved header'
 head[start:start+len(table)]=table;struct.pack_into('<I',head,0x48,len(table))
 textures=texture_section(old) if textures is None else textures
 data+=bytes((-len(data))%4096);textures+=bytes((-len(textures))%4096)
 struct.pack_into('<I',head,16,u32(head,16)&~3)
 struct.pack_into('<II',head,28,len(data),len(data));struct.pack_into('<III',head,40,len(head)+len(data),len(textures),len(textures))
 bundle.payloads[index]=head+data+textures;bundle.sync_info(index)

def prepare(current,normal,legacy,out):
 if legacy[:4]==bytes.fromhex('d4feadde'):legacy=zlib.decompress(legacy[8:])
 base,donor,original=Bundle(current),Bundle(normal),Bundle(legacy)
 mi,mn,manifest=base.manifest();normal_manifest=donor.manifest()[2]
 source_group=next(g for g in normal_manifest['groups'] if g['id']==NORMAL)
 source_images={r['id']:r for r in source_group['resources']}
 source_atlas=next(r for r in source_group['resources'] if r.get('atlas'))
 group=next(g for g in manifest['groups'] if g['id']==GROUP+'_640')
 index=next(i for i,g in enumerate(base.groups) if g['ID']==GROUP+'_640')
 ni=next(i for i,g in enumerate(donor.groups) if g['ID']==NORMAL)
 _,source_info=next((n,f) for n,f in donor.files(ni) if n.endswith('.PTX'))
 source_textures=texture_section(donor.payloads[ni])
 pixels=source_textures[source_info[1]:source_info[1]+source_info[2]]
 assert len(pixels)==source_info[2] and source_info[3]==0
 original_payloads=[bytes(p) for p in base.payloads]
 old_texture_count,first=struct.unpack_from('<II',base.infos[index],196)
 assert old_texture_count==1 and first+old_texture_count==len(base.textures)
 normal_count,normal_first=struct.unpack_from('<II',donor.infos[ni],196)
 assert normal_count==1
 base.textures.append(copy.deepcopy(donor.textures[normal_first]))
 struct.pack_into('<I',base.infos[index],196,2)
 atlas=copy.deepcopy(source_atlas);atlas.update(id=HD_ID,path=HD_PATH,slot=manifest['slot_count'])
 manifest['slot_count']+=1
 group['resources'].insert(1,atlas)
 remapped=[];retained=[]
 for pos,resource in enumerate(group['resources']):
  if 'parent' not in resource:continue
  key=resource['id'].replace('ZOMBIE_PVP_SEAGULL','ZOMBIE_PIRATE_SEAGULL')
  normal_image=source_images.get(key)
  if normal_image is None:retained.append(resource['id']);continue
  replacement=copy.deepcopy(normal_image)
  replacement.update(id=resource['id'],slot=resource['slot'],parent=HD_ID,
   path=['1536' if p=='640' else p for p in resource['path']])
  group['resources'][pos]=replacement
  remapped.append({'id':resource['id'],'normal_id':key})
 assert len(remapped)==50 and len(retained)==14
 packed=texture_section(base.payloads[index]);offset=len(packed)
 filename='\\'.join(HD_PATH).upper()+'.PTX'
 files=base.files(index)+[(filename,(1,offset,len(pixels),1,0,0,source_info[6],source_info[7]))]
 replace_section(base,index,files,section(base,index),packed+pixels)
 # Restore complete original animation records, undoing v61's image-only
 # 2.4x multiplier. Skeletons, frame timing, commands and events were already
 # original and must remain byte-identical rather than guessed/re-authored.
 common=next(i for i,g in enumerate(base.groups) if g['ID']==GROUP+'_Common')
 old_common=next(i for i,g in enumerate(original.groups) if g['ID']==GROUP+'_Common')
 old_data=section(original,old_common);original_files=dict(original.files(old_common))
 data=section(base,common);files=base.files(common);pams=[]
 for pos,(name,info) in enumerate(files):
  if not name.endswith('.PAM'):continue
  source=original_files[name];raw=old_data[source[1]:source[1]+source[2]]
  before=data[info[1]:info[1]+info[2]];a,b=PamIndex(before),PamIndex(raw)
  assert len(a.images)==len(b.images) and len(a.sprites)==len(b.sprites)
  for x,y in zip(a.sprites,b.sprites):assert before[x['start']:x['end']]==raw[y['start']:y['end']]
  for x,y in zip(a.images,b.images):assert x['name']==y['name'] and x['size']==y['size']
  files[pos]=(name,(0,len(data),len(raw)));data+=raw
  pams.append({'path':name,'image_count':len(b.images),'sha256':hashlib.sha256(raw).hexdigest()})
 assert len(pams)==2
 replace_section(base,common,files,data)
 base.replace_manifest(mi,mn,manifest)
 result=base.build();check=Bundle(result)
 assert check.manifest()[2]==manifest
 for i,payload in enumerate(original_payloads):
  if i not in (mi,index,common):assert bytes(check.payloads[i])==payload,'unrelated group changed'
 for i in (index,common):assert check.payloads[i]==base.payloads[i]
 record={'normal_group':NORMAL,'normal_source_sha256':hashlib.sha256(normal).hexdigest(),
  'predecessor_sha256':hashlib.sha256(current).hexdigest(),'sha256':hashlib.sha256(result).hexdigest(),
  'size':len(result),'normal_atlas_sha256':hashlib.sha256(pixels).hexdigest(),
  'copied_texture_metadata':bytes(donor.textures[normal_first]).hex(),'remapped':remapped,
  'retained_pvp_only_images':retained,'original_pams':pams,'changed_group_ids':[base.groups[i]['ID'] for i in (mi,index,common)],
  'unrelated_groups_unchanged':True,'pixels_copied_without_resampling':True,'runtime_game_verified':False}
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 (out/'zombie2-seagull-hd.rsb.smf').write_bytes(result)
 (out/'seagull-hd-build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
 return result,record
