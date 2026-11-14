"""Prepare the restored tutorial's actor resources and early level reward."""
from io import StringIO
import copy
import json

from prepare_offline_economy import JSONDecoder, cipher
from prepare_offline_neighbor_catalog import Bundle, decode, extract
from prepare_offline_pvp_seagull import section
from prepare_offline_pvp_seagull_hd import replace_section


TUTORIAL4 = 'PACKAGES\\LEVELS\\TUTORIAL4.RTON'
EGYPT2 = 'PACKAGES\\LEVELS\\EGYPT2.RTON'
MODULES = 'PACKAGES\\LEVELMODULES.RTON'
FINAL_STAGE = 'UnlineTutorialFinalStage'
TUTORIAL_STAGE_GROUPS = ('ZombieTutorialGroup', 'FrontLawnMowerGroup')


def update_level(bundle, path, update):
    index, = (i for i in range(len(bundle.groups)) if path in dict(bundle.files(i)))
    files = dict(bundle.files(index))
    data = section(bundle, index)
    original = extract(bundle, path)
    level = decode(original)
    update(level)
    encoded = JSONDecoder().encode_root_object(StringIO(json.dumps(level, ensure_ascii=False)))
    replacement = b'\x10\0' + cipher.encrypt(encoded) if original.startswith(b'\x10\0') else encoded
    files[path] = (0, len(data), len(replacement))
    replace_section(bundle, index, sorted(files.items()), data + replacement)
    return level


def preload(level, *groups):
    waves, = (obj['objdata'] for obj in level['objects']
              if obj['objclass'] == 'WaveGeneratorProperties')
    names = waves.setdefault('ResourceGroupNames', [])
    names.extend(group for group in groups if group not in names)


def cabbagepult_reward(level):
    definition, = (obj['objdata'] for obj in level['objects']
                   if obj['objclass'] == 'LevelDefinition')
    assert not definition.get('FirstRewardType') and not definition.get('FirstRewardParam')
    definition.update(FirstRewardType='seed_packet', FirstRewardParam='cabbagepult')
    preload(level, 'PlantCabbagepult')


def prepare(resource, *, egypt2_reward=False):
    bundle = Bundle(resource)
    updated = {
        TUTORIAL4: update_level(bundle, TUTORIAL4, lambda level: preload(
            level, 'ZombieTutorialGroup', 'FrontLawnMowerGroup'))
    }
    if egypt2_reward:
        updated[EGYPT2] = update_level(bundle, EGYPT2, cabbagepult_reward)
    result = bundle.build()
    installed = Bundle(result)
    for path, level in updated.items():
        assert decode(extract(installed, path)) == level
    return result


def prepare_chain(resource):
    """Declare persistent stage dependencies for a continuous Tutorial1–4 run.

    Tutorial4 has its own stage-property identity so the native transition
    initializes its stage/audio instead of reusing the preceding lesson's
    cached stage. Actor art, music events, rewards and lesson logic stay stock.
    """
    bundle = Bundle(resource)
    def stage_dependencies(document):
        stage, = (o for o in document['objects'] if 'TutorialStage' in o.get('aliases', []))
        groups = stage['objdata'].setdefault('ResourceGroupNames', [])
        for name in TUTORIAL_STAGE_GROUPS:
            if name not in groups: groups.append(name)
        assert 'AudioTutorial' in groups and 'DelayLoad_Background_FrontLawn' in groups
        final = [o for o in document['objects'] if FINAL_STAGE in o.get('aliases', [])]
        if final:
            assert len(final) == 1 and final[0]['objdata'] == stage['objdata']
        else:
            final_stage = copy.deepcopy(stage)
            final_stage.pop('uid', None)
            final_stage['aliases'] = [FINAL_STAGE]
            document['objects'].append(final_stage)
    def final_stage(document):
        level, = (o['objdata'] for o in document['objects'] if o['objclass'] == 'LevelDefinition')
        assert level['StageModule'] in ('RTID(TutorialStage@LevelModules)', f'RTID({FINAL_STAGE}@LevelModules)')
        level['StageModule'] = f'RTID({FINAL_STAGE}@LevelModules)'
    expected = {MODULES: update_level(bundle, MODULES, stage_dependencies),
                TUTORIAL4: update_level(bundle, TUTORIAL4, final_stage)}
    result = bundle.build()
    check = Bundle(result)
    for path, document in expected.items():
        assert decode(extract(check, path)) == document
    return result
