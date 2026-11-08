"""Add a separate editor level; never change the live home/merchant level."""
import copy, hashlib, json, re, struct, zlib
from io import StringIO
from pathlib import Path
from prepare_offline_neighbor_catalog import Bundle, decode, extract, native_ids, u32
from prepare_offline_economy import trie_write, cipher, JSONDecoder

SOURCE = 'PACKAGES\\LEVELS\\ARENA_PLANT_TEST.RTON'
TARGET = 'PACKAGES\\LEVELS\\ARENA_PRESET_EDITOR.RTON'
SOURCE_RESOURCE = 'RESFILE_PACKAGES_LEVELS_ARENA_PLANT_TEST'
TARGET_RESOURCE = 'RESFILE_PACKAGES_LEVELS_ARENA_PRESET_EDITOR'

def prepare(resource, native, out, *, register_level=True, allowed_ids=None):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    bundle = Bundle(resource)
    props = decode(extract(bundle, '\\PROPERTYSHEETS.RTON'))['objects']
    game = next(x['objdata'] for x in props if x.get('objclass') == 'GamePropertySheet')
    aliases = {a:x['objdata'] for x in props for a in x.get('aliases', [])}
    types = {x['objdata']['TypeName']:x['objdata'] for x in decode(extract(bundle, '\\PLANTTYPES.RTON'))['objects']}
    names = game['PlantTypeOrder']; ids = native_ids(native, set(names))
    catalogue = []
    for name in names:
        p = aliases[re.fullmatch(r'RTID\((.+)@PropertySheets\)', types[name]['Properties'])[1]]
        catalogue.append(dict(id=ids[name], name=name, maxLevel=min(4,p.get('MaxLevel',1))))
    if allowed_ids is not None:
        assert allowed_ids <= {p['id'] for p in catalogue}
        for plant in catalogue:
            plant['allowed'] = plant['id'] in allowed_ids
    allowed = [p for p in catalogue if p.get('allowed', True)]
    level = copy.deepcopy(decode(extract(bundle, 'ARENA_PLANT_TEST.RTON')))
    bank = next(x['objdata'] for x in level['objects'] if x['objclass']=='PVPSeedBankProperties')
    bank['PlantList'] = [dict(PlantName=p['name'], MaxNum='45', NeedZoneLevel=0) for p in allowed]
    raw = JSONDecoder().encode_root_object(StringIO(json.dumps(level,ensure_ascii=False)))
    replacement = b'\x10\0' + cipher.encrypt(raw)
    matched = 0
    for i in range(len(bundle.groups)):
        entries = list(bundle.files(i))
        if not any(n==SOURCE for n,k in entries): continue
        matched += 1; old = bundle.payloads[i]; offset = u32(old,24)
        section = old[offset:offset+u32(old,28)]
        if u32(old,16)&2: section=zlib.decompress(section)
        entries.append((TARGET,(0,len(section),len(replacement))))
        section += replacement; section += bytes((-len(section))%4096)
        head=bytearray(old[:offset]); table=trie_write(sorted(entries),1); at=u32(head,0x4c)
        assert at+len(table)<=offset, 'RSG file table needs more space'
        head[at:at+len(table)]=table
        struct.pack_into('<I',head,0x48,len(table)); struct.pack_into('<I',head,16,u32(head,16)&~2)
        struct.pack_into('<II',head,28,len(section),len(section)); struct.pack_into('<I',head,40,len(head)+len(section))
        bundle.payloads[i]=head+section+old[u32(old,40):u32(old,40)+u32(old,44)]
        bundle.sync_info(i)
    assert matched==1
    if register_level:
        manifest_index, manifest_name, manifest = bundle.manifest()
        packages, source_entry = next(
            (group, entry)
            for group in manifest['groups']
            for entry in group.get('resources', [])
            if entry.get('id') == SOURCE_RESOURCE
        )
        assert packages['id'] == 'Packages'
        target_entry = copy.deepcopy(source_entry)
        target_entry['id'] = TARGET_RESOURCE
        target_entry['path'][-1] = 'arena_preset_editor.rton'
        target_entry['slot'] = manifest['slot_count']
        manifest['slot_count'] += 1
        packages['resources'].append(target_entry)
        bundle.replace_manifest(manifest_index, manifest_name, manifest)
    result=bundle.build(); check=Bundle(result)
    assert decode(extract(check,'ARENA_PRESET_EDITOR.RTON'))==level
    assert extract(check,'ARENA_PLANT_TEST.RTON')==extract(Bundle(resource),'ARENA_PLANT_TEST.RTON')
    if register_level:
        _, _, installed_manifest = check.manifest()
        installed_packages = next(group for group in installed_manifest['groups'] if group['id'] == 'Packages')
        registrations = {entry['id']:entry for entry in installed_packages['resources']}
        assert registrations[SOURCE_RESOURCE] == source_entry
        assert registrations[TARGET_RESOURCE] == target_entry
        assert '\\'.join(target_entry['path']).upper() == TARGET
        assert sum(entry.get('slot') == target_entry['slot'] for group in installed_manifest['groups']
                   for entry in group.get('resources', [])) == 1
    # The top-level RSB name directory must include the added package as well.
    lines=['struct EditorPlantSpec {unsigned id,maxLevel;char alias[32];};',
           'static const EditorPlantSpec EDITOR_PLANTS[]={']
    lines += ['{%d,%d,"%s"},'%(p['id'],p['maxLevel'],p['name']) for p in allowed]
    lines += ['};','static const unsigned EDITOR_PLANT_COUNT=sizeof(EDITOR_PLANTS)/sizeof(EDITOR_PLANTS[0]);']
    (out/'preset_editor_catalog.h').write_text('\n'.join(lines)+'\n',encoding='utf8')
    (out/'preset-editor-catalogue.json').write_text(json.dumps(catalogue,indent=2)+'\n',encoding='utf8')
    (out/'dynamic-preset-editor.rsb.smf').write_bytes(result)
    return result, catalogue
