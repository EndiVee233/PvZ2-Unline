"""Enable the original formation-drag path only in the defense editor level."""
from pathlib import Path
from io import BytesIO, StringIO
import copy, hashlib, json, struct, zlib
from prepare_offline_economy import Bundle, u32, trie_write, cipher, RTONDecoder, JSONDecoder

EDITOR = 'PACKAGES\\LEVELS\\ARENA_PLANT_TEST.RTON'

def prepare(resource, out):
    bundle = Bundle(resource)
    changes = []
    for i in range(len(bundle.groups)):
        entries = list(bundle.files(i))
        for j, (name, info) in enumerate(entries):
            if name != EDITOR:
                continue
            old = bundle.payloads[i]
            offset = u32(old, 24)
            section = old[offset:offset + u32(old, 28)]
            if u32(old, 16) & 2:
                section = zlib.decompress(section)
            raw = section[info[1]:info[1] + info[2]]
            encrypted = raw[:2] == b'\x10\0'
            if encrypted:
                raw = cipher.decrypt(raw[2:])
            fp = BytesIO(raw[4:]); fp.name = name
            original = json.loads(RTONDecoder(repairFiles=False).parse_root_object(fp))
            data = copy.deepcopy(original)
            levels = [o['objdata'] for o in data['objects'] if o.get('objclass') == 'LevelDefinition']
            assert len(levels) == 1 and 'IsArenaEdit' not in levels[0]
            # Native Board touch-down (22a2c8) checks this flag before creating
            # ArenaEditPlantCursor. Merely selecting ArenaPlant kind 2 hides
            # the seed bank/shovel; it does not enable dragging existing plants.
            levels[0]['IsArenaEdit'] = True
            encoded = JSONDecoder().encode_root_object(StringIO(json.dumps(data, ensure_ascii=False)))
            fp = BytesIO(encoded[4:]); fp.name = name
            assert json.loads(RTONDecoder(repairFiles=False).parse_root_object(fp)) == data
            replacement = b'\x10\0' + cipher.encrypt(encoded) if encrypted else encoded
            entries[j] = (name, (0, len(section), len(replacement)))
            section += replacement
            section += bytes((-len(section)) % 4096)
            head = bytearray(old[:offset])
            table = trie_write(entries, 1); at = u32(head, 0x4c)
            assert at + len(table) <= offset
            head[at:at + len(table)] = table
            struct.pack_into('<I', head, 0x48, len(table))
            struct.pack_into('<I', head, 16, u32(head, 16) & ~2)
            struct.pack_into('<II', head, 28, len(section), len(section))
            struct.pack_into('<I', head, 40, len(head) + len(section))
            textures = old[u32(old, 40):u32(old, 40) + u32(old, 44)]
            bundle.payloads[i] = head + section + textures
            bundle.sync_info(i)
            del levels[0]['IsArenaEdit']
            assert data == original, 'only the edit flag may change'
            changes.append(dict(name=name, field='IsArenaEdit', value=True))
    assert len(changes) == 1
    result = bundle.build(); check = Bundle(result)
    for i in range(len(bundle.groups)):
        assert check.payloads[i] == bundle.payloads[i]
    record = dict(changes=changes, predecessor_sha256=hashlib.sha256(resource).hexdigest(),
                  sha256=hashlib.sha256(result).hexdigest(), size=len(result))
    Path(out, 'dynamic-drag.rsb.smf').write_bytes(result)
    Path(out, 'drag-resource-build.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf8')
    return result, record
