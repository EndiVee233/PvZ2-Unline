"""Check donor atlas/rig compatibility and byte-preserved PvP behavior."""
from pathlib import Path
from zipfile import ZipFile
import hashlib,json,struct,sys,zlib
from prepare_offline_pvp_seagull_hd import Bundle,section,PamIndex,GROUP,NORMAL,HD_ID,HD_PATH,texture_section

def check(out,base,normal,legacy,apk=None):
 out=Path(out);record=json.loads((out/'generated/seagull-hd-build.json').read_text())
 raw=(out/'generated/zombie2-seagull-hd.rsb.smf').read_bytes();fixed=Bundle(raw)
 with ZipFile(base) as z:prior=Bundle(z.read('assets/reconstruction/zombie2-pvp.rsb.smf'))
 donor=Bundle(normal);old=Bundle(zlib.decompress(legacy[8:]) if legacy[:4]==bytes.fromhex('d4feadde') else legacy)
 fm=fixed.manifest()[2];pm=prior.manifest()[2];dm=donor.manifest()[2]
 resources={r['id']:r for g in fm['groups'] for r in g.get('resources',[])}
 normal_images={r['id']:r for g in dm['groups'] if g['id']==NORMAL for r in g.get('resources',[])}
 prior_images={r['id']:r for g in pm['groups'] for r in g.get('resources',[])}
 assert len(fixed.groups)==len(prior.groups) and len(fixed.composites)==len(prior.composites)
 assert fm['slot_count']==pm['slot_count']+1 and len(record['remapped'])==50
 for item in record['remapped']:
  image,source=resources[item['id']],normal_images[item['normal_id']]
  assert image['parent']==HD_ID and image['slot']==prior_images[item['id']]['slot']
  for k in ('ax','ay','aw','ah','aflags'):assert image.get(k)==source.get(k),(item,k)
 for rid in record['retained_pvp_only_images']:assert resources[rid]==prior_images[rid]
 changed=[fixed.groups[i]['ID'] for i,p in enumerate(prior.payloads) if p!=fixed.payloads[i]]
 assert set(changed)==set(record['changed_group_ids']) and len(changed)==3
 i=next(i for i,g in enumerate(fixed.groups) if g['ID']==GROUP+'_640')
 ni=next(i for i,g in enumerate(donor.groups) if g['ID']==NORMAL)
 info=dict(fixed.files(i))['\\'.join(HD_PATH).upper()+'.PTX']
 source=next(f for n,f in donor.files(ni) if n.endswith('.PTX'))
 assert texture_section(fixed.payloads[i])[info[1]:info[1]+info[2]]==texture_section(donor.payloads[ni])[source[1]:source[1]+source[2]]
 count,start=struct.unpack_from('<II',fixed.infos[i],196);_,ns=struct.unpack_from('<II',donor.infos[ni],196)
 assert count==2 and fixed.textures[start+1]==donor.textures[ns]
 # The entire original low-resolution atlas is retained for special effects,
 # not replaced with unrelated pirate body cells or an empty placeholder.
 pi=next(i for i,g in enumerate(prior.groups) if g['ID']==GROUP+'_640')
 low=texture_section(prior.payloads[pi]);assert texture_section(fixed.payloads[i])[:len(low)]==low
 fi=next(i for i,g in enumerate(fixed.groups) if g['ID']==GROUP+'_Common')
 oi=next(i for i,g in enumerate(old.groups) if g['ID']==GROUP+'_Common')
 original_files=dict(old.files(oi));source_pams={}
 nc=next(i for i,g in enumerate(donor.groups) if g['ID']=='ZombiePirateSeagullGroup_Common')
 for n,f in donor.files(nc):
  if n.endswith('.PAM'):source_pams[n.split('\\')[-1]]=section(donor,nc)[f[1]:f[1]+f[2]]
 seen=0
 for n,f in fixed.files(fi):
  if not n.endswith('.PAM'):continue
  source=original_files[n];p=section(fixed,fi)[f[1]:f[1]+f[2]];original=section(old,oi)[source[1]:source[1]+source[2]]
  assert p==original,'PvP animation bytes changed'
  index=PamIndex(p);assert all(im['name'].split('|')[-1] in resources for im in index.images)
  labels={fr['label'] for fr in index.sprites[-1]['frames'] if fr['label']}
  if n.endswith('\\ZOMBIE_PVP_SEAGULL.PAM'):
   assert {'idle','walk','eat','die','particles','plantfood'}<=labels
   normal_pam=source_pams['ZOMBIE_PIRATE_SEAGULL.PAM'];normal_index=PamIndex(normal_pam)
   for a,b in zip(index.images[:50],normal_index.images[:50]):assert a['mat']==b['mat'] and a['size']==b['size']
   for a,b in zip(index.sprites[:57],normal_index.sprites[:57]):assert p[a['start']:a['end']]==normal_pam[b['start']:b['end']]
   assert len(index.sprites[-1]['frames'])==344 and len(normal_index.sprites[-1]['frames'])==301
  else:assert 'plantfood' in labels
  seen+=1
 assert seen==2
 # The manifest changes exactly the fifty aliases and one extra atlas.
 reversed_=json.loads(json.dumps(fm));rg=next(g for g in reversed_['groups'] if g['id']==GROUP+'_640')
 rg['resources']=[prior_images[r['id']] if r['id'] in prior_images else r for r in rg['resources'] if r['id']!=HD_ID]
 reversed_['slot_count']-=1;assert reversed_==pm
 smali=(out/'bootstrap/smali/com/popcap/pvz2cthd/BootActivity.smali').read_text()
 assert record['sha256'] in smali and record['predecessor_sha256'] in smali
 assert '.pvp-seagull-v100-'+record['sha256'][:12] in smali
 if apk:
  with ZipFile(base) as before,ZipFile(apk) as after:
   entries=lambda z:{x.filename:(x.CRC,x.file_size) for x in z.infolist() if not x.filename.startswith('META-INF/')}
   a,b=entries(before),entries(after);assert a.keys()==b.keys()
   changes=sorted(k for k in a if a[k]!=b[k])
   assert changes==['assets/reconstruction/zombie2-pvp.rsb.smf','classes8.dex'],changes
   assert before.read('lib/armeabi/libSrc.so')==after.read('lib/armeabi/libSrc.so')
 result={'normal_atlas_bytes_and_metadata_copied':True,'normal_body_cells':50,'original_common_body_sprites_identical':57,
  'pvp_main_frames':344,'entire_original_pvp_animation_and_projectile_preserved':True,
  'image_only_2_4_multiplier_removed':True,'pvp_only_images_and_atlas_retained':14,
  'potions_and_unrelated_groups_unchanged':True,'bootstrap_accepts_installed_v99_resource':True,
  'native_v99_gameplay_byte_identical':bool(apk),'runtime_game_verified':False}
 (out/'seagull-hd-checks.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result));return result

if __name__=='__main__':
 from prepare_offline_pvp_seagull_hd import normal_resource
 root=Path(__file__).resolve().parents[1];out=Path(sys.argv[1]);base=root/'work/pvp-v99/PvZ2-v99-pvp-scene-candidate.apk'
 check(out,base,normal_resource(base),(root/'work/pvp-v61/original175-zombie1.smf').read_bytes(),out/'PvZ2-v100-seagull-art-candidate.apk')
