"""Validate the complete seagull asset graph and v60 gameplay preservation."""
from pathlib import Path
from zipfile import ZipFile
import hashlib,json,sys
from prepare_offline_pvp_seagull import Bundle,section,PamIndex,GROUP,u32

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'work/pvp-v61'
raw=(OUT/'generated/zombie2-seagull.rsb.smf').read_bytes();bundle=Bundle(raw)
manifest=bundle.manifest()[2];groups=[g for g in manifest['groups'] if g['id'] in (GROUP,GROUP+'_640',GROUP+'_Common')]
assert len(groups)==3
composite=next(g for g in groups if g['type']=='composite')
assert next(s for s in composite['subgroups'] if s['id']==GROUP+'_640')['res']=='1536'
resources={r['id']:r for g in groups for r in g.get('resources',[])}
assert 'POPANIM_ZOMBIE_ZOMBIE_PVP_SEAGULL' in resources
assert 'POPANIM_EFFECTS_ZOMBIE_PVP_SEAGULL_BULLET' in resources
assert len(resources)==67
atlas=next(r['id'] for r in resources.values() if r.get('atlas'))
assert all(r.get('parent')==atlas for r in resources.values() if r['type']=='Image' and not r.get('atlas'))
files={name:(i,info) for i in range(len(bundle.groups)) for name,info in bundle.files(i)}
for resource in resources.values():
 if resource.get('atlas'):assert ('\\'.join(resource['path'])+'.ptx').upper() in files
 if resource['type']!='PopAnim':continue
 path='\\'.join(resource['path']).upper();assert path in files
 i,info=files[path];data=section(bundle,i);pam=PamIndex(data[info[1]:info[1]+info[2]])
 assert all(image['name'].split('|')[-1] in resources for image in pam.images),'unresolved image reference'
 labels={f['label'] for f in pam.sprites[-1]['frames'] if f['label']}
 if resource['id']=='POPANIM_ZOMBIE_ZOMBIE_PVP_SEAGULL':assert {'idle','walk','eat','die','particles','plantfood'}<=labels
 else:assert 'plantfood' in labels
record=json.loads((OUT/'generated/seagull-resource-build.json').read_text(encoding='utf8'))
assert record['atlas_pixels_unchanged'] and record['animation_labels_commands_and_bones_preserved']
assert record['shared_pirate_explorer_and_potions_unchanged']
assert (OUT/'libSrc.so').read_bytes()==(ROOT/'work/pvp-v60/libSrc.so').read_bytes(),'gameplay/native code changed'
smali=(OUT/'bootstrap-art/smali/com/popcap/pvz2cthd/BootActivity.smali').read_text(encoding='utf8')
assert record['sha256'] in smali and record['predecessor_sha256'] in smali
assert '.pvp-seagull-v61-'+record['sha256'][:12] in smali
apk=OUT/(f'PvZ2-{OUT.name[4:]}-pvp-scene-candidate.apk')
if apk.exists():
 with ZipFile(ROOT/'work/pvp-v60/PvZ2-v60-pvp-scene-candidate.apk') as prior,ZipFile(apk) as current:
  before={i.filename:(i.CRC,i.file_size) for i in prior.infolist() if not i.filename.startswith('META-INF/')}
  after={i.filename:(i.CRC,i.file_size) for i in current.infolist() if not i.filename.startswith('META-INF/')}
  changes=sorted(k for k in before.keys()|after.keys() if before.get(k)!=after.get(k))
  assert changes==['assets/reconstruction/zombie2-pvp.rsb.smf','classes8.dex'],changes
report=dict(full_original_seagull_group_and_projectile=True,resource_count=67,
 all_animation_image_and_atlas_references_resolve=True,original_move_death_and_skill_labels_present=True,
 original_events_bones_and_atlas_preserved=True,current_shared_and_potion_groups_unchanged=True,
 native_gameplay_byte_identical_to_v60=True,bootstrap_accepts_v58_v60_resource=True,runtime_game_verified=False)
(OUT/'seagull-asset-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps(report))
