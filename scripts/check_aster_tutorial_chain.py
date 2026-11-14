"""Check tutorial dependencies without starting the game or editing saves."""
import argparse
import copy
from pathlib import Path
from zipfile import ZipFile

from prepare_opening_tutorial_resources import MODULES,TUTORIAL4,FINAL_STAGE,TUTORIAL_STAGE_GROUPS
from prepare_offline_neighbor_catalog import Bundle,decode,extract
from prepare_offline_pvp_seagull_hd import texture_section


def verify(original,current,baked):
    before,after,rgba=map(Bundle,(original,current,baked))
    names={name for i in range(len(before.groups)) for name,_ in before.files(i)}
    assert names=={name for i in range(len(after.groups)) for name,_ in after.files(i)}
    changed={n for n in names if extract(before,n)!=extract(after,n)}
    assert changed=={MODULES,TUTORIAL4},changed
    assert before.manifest()[2]==after.manifest()[2]
    for i in range(len(before.groups)):
        assert before.groups[i]['ID']==after.groups[i]['ID']
        assert texture_section(before.payloads[i])==texture_section(after.payloads[i])
    old=decode(extract(before,MODULES));new=decode(extract(after,MODULES))
    wanted=copy.deepcopy(old)
    stage,=(o for o in wanted['objects'] if 'TutorialStage' in o.get('aliases',[]))
    stage['objdata']['ResourceGroupNames'].extend(n for n in TUTORIAL_STAGE_GROUPS if n not in stage['objdata']['ResourceGroupNames'])
    final=copy.deepcopy(stage);final.pop('uid',None);final['aliases']=[FINAL_STAGE]
    wanted['objects'].append(final)
    assert new==wanted
    fourth=decode(extract(before,TUTORIAL4))
    definition,=(o['objdata'] for o in fourth['objects'] if o['objclass']=='LevelDefinition')
    definition['StageModule']=f'RTID({FINAL_STAGE}@LevelModules)'
    assert decode(extract(after,TUTORIAL4))==fourth
    for day in range(1,5):
        path=f'PACKAGES\\LEVELS\\TUTORIAL{day}.RTON'
        a=decode(extract(after,path));b=decode(extract(rgba,path))
        assert a==b
        level,=(o['objdata'] for o in a['objects'] if o['objclass']=='LevelDefinition')
        assert level['ForceNextLevel']==('egypt1' if day==4 else f'tutorial{day+1}')
        assert level['StageModule']==f'RTID({FINAL_STAGE if day==4 else "TutorialStage"}@LevelModules)'
    assert decode(extract(rgba,MODULES))==new
    print('PASS: only two RTON documents changed; actors/atlas pixels, rewards, waves and lesson order preserved.')
    print('PASS: continuous and cold-start tutorial4 resolve the same final stage; compressed and RGBA stages match.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('apk',type=Path);p.add_argument('resource',type=Path);p.add_argument('baked',type=Path)
    a=p.parse_args()
    with ZipFile(a.apk) as z:original=z.read('assets/reconstruction/dynamic-original-speed.rsb.smf')
    verify(original,a.resource.read_bytes(),a.baked.read_bytes())
