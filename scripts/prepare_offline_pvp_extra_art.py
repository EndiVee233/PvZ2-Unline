"""Restore two missing PvP rigs and reuse the real Explosive Zomboss bomb.

Copy existing atlas pixels; preserve native animation events and gameplay.
"""
from pathlib import Path
import copy,hashlib,json,struct,zlib
from merge_legacy_pvp_resources import Bundle,u32,trie_write
from prepare_offline_pvp_seagull_hd import section,texture_section,replace_section
from pam_transform_index import PamIndex

def import_group(base,manifest,source,prefix):
 wanted={i for i,g in enumerate(source.groups) if g['ID'].startswith(prefix+'_')}
 assert {source.groups[i]['ID'] for i in wanted}=={prefix+'_640',prefix+'_Common'}
 assert not any(g['ID'].startswith(prefix+'_') for g in base.groups)
 remap={}
 for j in sorted(wanted):
  i=len(base.groups);remap[j]=i;base.groups.append(copy.deepcopy(source.groups[j]))
  base.infos.append(bytearray(source.infos[j]));base.pools.append(bytearray(source.pools[j]));base.payloads.append(bytearray(source.payloads[j]))
  count,start=struct.unpack_from('<II',source.infos[j],196);struct.pack_into('<I',base.infos[i],200,len(base.textures))
  base.textures.extend(copy.deepcopy(source.textures[start:start+count]));base.sync_info(i)
 for original in source.composites:
  if bytes(original[:128]).split(b'\0')[0].decode()!=prefix:continue
  row=bytearray(original)
  for k in range(u32(row,1152)):
   struct.pack_into('<I',row,128+16*k,remap[u32(row,128+16*k)])
   if u32(row,132+16*k)==640:struct.pack_into('<I',row,132+16*k,1536)
  base.composites.append(row)
 for old in source.manifest()[2]['groups']:
  if old['id'] not in (prefix,prefix+'_640',prefix+'_Common'):continue
  g=copy.deepcopy(old)
  if g.get('res')=='640':g['res']='1536'
  for sub in g.get('subgroups',[]):
   if sub.get('res')=='640':sub['res']='1536'
  for r in g.get('resources',[]):r['slot']=manifest['slot_count'];manifest['slot_count']+=1
  manifest['groups'].append(g)

def add_atlas(base,manifest,target,donor,normal_group,label):
 ti=next(i for i,g in enumerate(base.groups) if g['ID']==target+'_640')
 ni=next(i for i,g in enumerate(donor.groups) if g['ID']==normal_group)
 ng=next(g for g in donor.manifest()[2]['groups'] if g['id']==normal_group)
 donor_atlas=next(r for r in ng['resources'] if r.get('atlas'))
 source_name='\\'.join(donor_atlas['path']).upper()+'.PTX'
 inf=dict(donor.files(ni))[source_name]
 pixels=texture_section(donor.payloads[ni])[inf[1]:inf[1]+inf[2]]
 count,first=struct.unpack_from('<II',base.infos[ti],196);_,nf=struct.unpack_from('<II',donor.infos[ni],196)
 metas=copy.deepcopy(base.textures[first:first+count]);new_first=len(base.textures)
 base.textures.extend(metas+[copy.deepcopy(donor.textures[nf+inf[3]])]);struct.pack_into('<II',base.infos[ti],196,count+1,new_first)
 atlas=copy.deepcopy(donor_atlas);atlas.update(id='ATLASIMAGE_ATLAS_'+label.upper(),path=['atlases',label],slot=manifest['slot_count']);manifest['slot_count']+=1
 target_group=next(g for g in manifest['groups'] if g['id']==target+'_640')
 target_group['resources'].insert(count,atlas)
 textures=texture_section(base.payloads[ti]);filename='ATLASES\\'+label.upper()+'.PTX'
 files=base.files(ti)+[(filename,(1,len(textures),len(pixels),count,0,0,inf[6],inf[7]))]
 replace_section(base,ti,files,section(base,ti),textures+pixels)
 return atlas,ng

def body_aliases(base,manifest,prefix,donor,normal_group,old_token,new_token):
 atlas,ng=add_atlas(base,manifest,prefix,donor,normal_group,prefix+'_HD_1536_00')
 images={r['id']:r for r in ng['resources'] if 'parent' in r}
 group=next(g for g in manifest['groups'] if g['id']==prefix+'_640');mapped=set()
 for i,r in enumerate(group['resources']):
  if 'parent' not in r:continue
  key=r['id'].replace(old_token,new_token)
  if key not in images:continue
  n=copy.deepcopy(images[key]);n.update(id=r['id'],slot=r['slot'],parent=atlas['id'],path=['1536' if p=='640' else p for p in r['path']]);group['resources'][i]=n;mapped.add(r['id'])
 ci=next(i for i,g in enumerate(base.groups) if g['ID']==prefix+'_Common');data=section(base,ci);files=base.files(ci);normalized=0
 for j,(name,inf) in enumerate(files):
  if not name.endswith('.PAM'):continue
  original=data[inf[1]:inf[1]+inf[2]];raw=bytearray(original);before=PamIndex(original)
  for image in before.images:
   if image['name'].split('|')[-1] in mapped:continue
   off=image['off']+4;v=struct.unpack_from('<4i',raw,off);struct.pack_into('<4i',raw,off,*(round(x*1536/640) for x in v));normalized+=1
  after=PamIndex(bytes(raw))
  for a,b in zip(before.sprites,after.sprites):assert original[a['start']:a['end']]==raw[b['start']:b['end']]
  files[j]=(name,(0,len(data),len(raw)));data+=raw
 replace_section(base,ci,files,data)
 return {'group':prefix,'normal_group':normal_group,'normal_image_aliases':len(mapped),'legacy_effect_image_bases_normalized':normalized}

def prepare(current,normal1,normal2,normal3,legacy1,legacy2,out):
 if legacy1[:4]==bytes.fromhex('d4feadde'):legacy1=zlib.decompress(legacy1[8:])
 if legacy2[:4]==bytes.fromhex('d4feadde'):legacy2=zlib.decompress(legacy2[8:])
 base=Bundle(current);mi,mn,manifest=base.manifest();original_payloads={g['ID']:bytes(base.payloads[i]) for i,g in enumerate(base.groups)}
 old1,old2=Bundle(legacy1),Bundle(legacy2)
 import_group(base,manifest,old1,'ZombiePVPCannonGroup');import_group(base,manifest,old2,'ZombiePVPWizardGroup')
 changes=[body_aliases(base,manifest,'ZombiePVPCannonGroup',Bundle(normal1),'ZombiePirateCannonGroup_1536','ZOMBIE_PVP_CANNON','ZOMBIE_PIRATE_CANNON'),
  body_aliases(base,manifest,'ZombiePVPWizardGroup',Bundle(normal3),'ZombieDarkWizardGroup_1536','ZOMBIE_PVP_WIZARD','ZOMBIE_DARK_WIZARD')]
 assert [c['normal_image_aliases'] for c in changes]==[17,53]
 # Use the real boss's projectile cell for both bomb phases. Keep the PvP
 # fuse/flight animation and center the larger image on its previous center.
 prefix='ZombiePVPSeagullGroup';atlas,ng=add_atlas(base,manifest,prefix,Bundle(normal2),'ZombieKongFuZombossExplosiveGroup_1536','ZombiePVPSeagullBossBomb_1536_00')
 boss=next(r for r in ng['resources'] if r['id']=='IMAGE_EXPLOSIVE_BOMB_PROJECTILE')
 group=next(g for g in manifest['groups'] if g['id']==prefix+'_640');bombs={};aliases=[]
 for i,r in enumerate(group['resources']):
  if not r['id'].endswith(('_59X68','_59X68_2')):continue
  n=copy.deepcopy(boss);n.update(id=r['id'],slot=r['slot'],parent=atlas['id'],path=r['path']);group['resources'][i]=n
  bombs[r['id']]=((boss['aw']-r['aw'])/2,(boss['ah']-r['ah'])/2);aliases.append(r['id'])
 assert len(bombs)==4
 ci=next(i for i,g in enumerate(base.groups) if g['ID']==prefix+'_Common');data=section(base,ci);files=base.files(ci);adjusted=0
 for j,(name,inf) in enumerate(files):
  if not name.endswith('.PAM'):continue
  raw=bytearray(data[inf[1]:inf[1]+inf[2]]);index=PamIndex(bytes(raw))
  for image in index.images:
   rid=image['name'].split('|')[-1]
   if rid not in bombs:continue
   dx,dy=bombs[rid];off=image['off']+4;a,c,b,d,x,y=struct.unpack_from('<4i2h',raw,off)
   tx=round(x-20*(a*dx+b*dy)/1310720);ty=round(y-20*(c*dx+d*dy)/1310720)
   assert -32768<=tx<=32767 and -32768<=ty<=32767
   struct.pack_into('<2h',raw,off+16,tx,ty);adjusted+=1
  files[j]=(name,(0,len(data),len(raw)));data+=raw
 replace_section(base,ci,files,data);assert adjusted==4
 base.replace_manifest(mi,mn,manifest);result=base.build();check=Bundle(result)
 assert check.manifest()[2]==manifest
 changed_ids={base.groups[mi]['ID'],prefix+'_640',prefix+'_Common'}
 for i,g in enumerate(check.groups):
  if g['ID'] in original_payloads and g['ID'] not in changed_ids:assert bytes(check.payloads[i])==original_payloads[g['ID']]
 record={'predecessor_sha256':hashlib.sha256(current).hexdigest(),'sha256':hashlib.sha256(result).hexdigest(),'size':len(result),
  'rigs':changes,'bomb_source':'IMAGE_EXPLOSIVE_BOMB_PROJECTILE','bomb_dimensions':[boss['aw'],boss['ah']],
  'bomb_aliases':aliases,'bomb_centers_adjusted':adjusted,'unrelated_groups_preserved':True,'runtime_game_verified':False}
 out=Path(out);(out/'zombie2-extra-art.rsb.smf').write_bytes(result);(out/'extra-art-build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
 return result,record
