"""Check restored rigs, donor cells, unchanged frames and centered bomb."""
from pathlib import Path
import json,sys,struct,zlib
from prepare_offline_pvp_seagull import Bundle,section,PamIndex
from prepare_offline_pvp_seagull_hd import normal_resource

def check(out):
 out=Path(out);root=Path(__file__).resolve().parents[1]
 before=Bundle((out/'generated/zombie2-seagull-hd.rsb.smf').read_bytes())
 after=Bundle((out/'generated/zombie2-extra-art.rsb.smf').read_bytes());record=json.loads((out/'generated/extra-art-build.json').read_text())
 manifest=after.manifest()[2];resources={r['id']:r for g in manifest['groups'] for r in g.get('resources',[])}
 def pams(b,gid):
  i=next(i for i,g in enumerate(b.groups) if g['ID']==gid+'_Common');data=section(b,i)
  return {n:data[f[1]:f[1]+f[2]] for n,f in b.files(i) if n.endswith('.PAM')}
 originals=[('ZombiePVPCannonGroup',root/'work/pvp-v61/original175-zombie1.smf',539,{'idle','walk','prep','fire','die','plantfood'}),
  ('ZombiePVPWizardGroup',root/'work/pvp-v32/original175-zombie2.rsb',751,{'idle','walk','eat','sheep','plantfood','die','stun'})]
 assert len(after.groups)==len(before.groups)+4 and len(after.composites)==len(before.composites)+2
 for prefix,path,frame_count,required in originals:
  old=path.read_bytes();old=Bundle(zlib.decompress(old[8:]) if old[:4]==bytes.fromhex('d4feadde') else old)
  expected=pams(old,prefix);actual=pams(after,prefix);assert actual.keys()==expected.keys()
  for name,raw in actual.items():
   a,b=PamIndex(expected[name]),PamIndex(raw)
   assert len(a.images)==len(b.images) and len(a.sprites)==len(b.sprites)
   for x,y in zip(a.sprites,b.sprites):assert expected[name][x['start']:x['end']]==raw[y['start']:y['end']]
   assert all(im['name'].split('|')[-1] in resources for im in b.images)
   if '\\ZOMBIE\\' in name:
    labels={f['label'] for f in b.sprites[-1]['frames'] if f['label']};assert required<=labels
    assert len(b.sprites[-1]['frames'])==frame_count
  composite=next(g for g in manifest['groups'] if g['id']==prefix)
  assert any(s['id']==prefix+'_640' and s['res']=='1536' for s in composite['subgroups'])
  group=next(g for g in manifest['groups'] if g['id']==prefix+'_640')
  for r in group['resources']:
   if 'parent' in r:assert r['parent'] in resources and resources[r['parent']].get('atlas')
 # Four bomb aliases now use the actual boss cell, and shifting their local
 # bases keeps the old center while increasing the visible pixel footprint.
 old_res={r['id']:r for g in before.manifest()[2]['groups'] for r in g.get('resources',[])}
 boss=resources['IMAGE_EXPLOSIVE_BOMB_PROJECTILE']
 for rid in record['bomb_aliases']:
  r=resources[rid];assert (r['ax'],r['ay'],r['aw'],r['ah'])==(boss['ax'],boss['ay'],98,96)
  assert r['parent']=='ATLASIMAGE_ATLAS_ZOMBIEPVPSEAGULLBOSSBOMB_1536_00'
 bp,ap=pams(before,'ZombiePVPSeagullGroup'),pams(after,'ZombiePVPSeagullGroup');assert bp.keys()==ap.keys();changed=0
 for name,raw in ap.items():
  old=bp[name];a,b=PamIndex(old),PamIndex(raw)
  for x,y in zip(a.sprites,b.sprites):assert old[x['start']:x['end']]==raw[y['start']:y['end']]
  for x,y in zip(a.images,b.images):
   rid=x['name'].split('|')[-1]
   if rid not in record['bomb_aliases']:assert x['size']==y['size'] and x['mat']==y['mat'];continue
   changed+=1;assert x['mat'][:4]==y['mat'][:4]
   def center(im,r):
    A,C,B,D,X,Y=im['mat'];return ((A*r['aw']/2+B*r['ah']/2)/1310720+X/20,(C*r['aw']/2+D*r['ah']/2)/1310720+Y/20)
   assert max(abs(u-v) for u,v in zip(center(x,old_res[rid]),center(y,resources[rid])))<=0.026
 assert changed==4
 # Existing skill and ordinary-zombie payloads are never replaced.
 allowed={'ZombiePVPSeagullGroup_640','ZombiePVPSeagullGroup_Common',before.groups[before.manifest()[0]]['ID']}
 for i,g in enumerate(before.groups):
  if g['ID'] not in allowed:assert before.payloads[i]==after.payloads[i]
 smali=(out/'bootstrap-art/smali/com/popcap/pvz2cthd/BootActivity.smali').read_text()
 assert record['predecessor_sha256'] in smali and record['sha256'] in smali
 result={'cannon_pvp_539_frames':True,'wizard_pvp_751_frames_and_bullet':True,'all_image_references_and_parents_resolve':True,
  'original_pvp_frame_events_preserved':True,'seagull_bomb_uses_boss_98x96_cell':True,'four_bomb_centers_preserved':True,
  'accepted_seagull_body_unchanged':True,'unrelated_assets_unchanged':True,'installed_v100_resource_predecessor_accepted':True,'runtime_game_verified':False}
 (out/'v101-art-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':check(Path(sys.argv[1]))
