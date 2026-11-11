"""Import missing original PvP resource groups without replacing modern groups.

Inputs are local, user-owned RSBs. No game assets are stored in this script.
Preserves existing RSG payloads, composite entries and texture metadata.
"""
from pathlib import Path
from io import BytesIO, StringIO
import copy, hashlib, json, struct, sys, zlib

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'src/tools'),
                'K:/pvz2-tools/pyvz2/OBBEdit/libraries']
import rsbtool


def u32(b, p):
    return struct.unpack_from('<I', b, p)[0]


def trie_read(b, off, length, kind=0):
    """Walk sibling pointers; a sequential prefix stack loses nested prefixes."""
    data = b[off:off + length]
    out, seen = [], set()

    def walk(p, prefix):
        assert p not in seen and p + 4 <= len(data)
        seen.add(p)
        word = u32(data, p)
        char, sibling = word & 255, word >> 8
        if char:
            walk(p + 4, prefix + chr(char))
        else:
            count = 1 if kind == 0 else (3 if u32(data, p + 4) == 0 else 8)
            value = struct.unpack_from('<' + 'I' * count, data, p + 4)
            out.append((prefix, value[0] if kind == 0 else value))
        if sibling:
            walk(sibling * 4, prefix)
    if length:
        walk(0, '')
    return out


def trie_write(items, kind=0):
    tree = {}
    for key, value in items:
        node = tree
        for c in key.upper() + '\0':
            node = node.setdefault(c, {})
        assert 'value' not in node
        node['value'] = value
    out = bytearray()

    def emit(node):
        previous = None
        for char in sorted(node):
            pos = len(out)
            if previous is not None:
                struct.pack_into('<I', out, previous,
                                 u32(out, previous) | ((pos // 4) << 8))
            previous = pos
            out.extend(struct.pack('<I', ord(char)))
            if char == '\0':
                v = node[char]['value']
                out.extend(struct.pack('<I', v) if kind == 0 else
                           struct.pack('<' + 'I' * len(v), *v))
            else:
                emit(node[char])
    emit(tree)
    assert sorted(trie_read(out, 0, len(out), kind)) == sorted(
        (n.upper(), v) for n, v in items)
    return bytes(out)


class Bundle:
    def __init__(self, data):
        self.data = data
        self.h = h = rsbtool.parse_head(data)
        self.groups = rsbtool.read_rsgp_info(data, h['rsgpInfo_BeginOffset'],
                                           h['rsgp_Number'], h['rsgpInfo_EachLength'])
        self.composites = self.table('compositeInfo', 'composite_Number')
        self.pools = self.table('autopoolInfo', 'autopool_Number')
        self.textures = self.table('ptxInfo', 'ptx_Number')
        self.infos = self.table('rsgpInfo', 'rsgp_Number')
        self.payloads = [bytearray(data[g['fields'][0]:g['fields'][0]+g['fields'][1]])
                         for g in self.groups]

    def table(self, prefix, count):
        h = self.h
        start, size = h[prefix + '_BeginOffset'], h[prefix + '_EachLength']
        return [bytearray(self.data[start+i*size:start+(i+1)*size])
                for i in range(h[count])]

    def files(self, i):
        b = self.payloads[i]
        return trie_read(b, u32(b, 0x4c), u32(b, 0x48), 1)

    def manifest(self):
        from pyvz2rton import RTONDecoder

        for i in range(len(self.groups)):
            for name, info in self.files(i):
                if name.startswith('PROPERTIES\\RESOURCES') and name.endswith('.RTON'):
                    b = self.payloads[i]
                    raw = b[u32(b, 0x18):u32(b, 0x18)+u32(b, 0x1c)]
                    if u32(b, 0x10) & 2:
                        raw = zlib.decompress(raw)
                    f = BytesIO(raw[info[1]:info[1]+info[2]][4:])
                    f.name = name
                    return i, name, json.loads(RTONDecoder(repairFiles=False).parse_root_object(f))
        raise ValueError('Missing resource manifest')

    def replace_manifest(self, i, name, manifest):
        from pyvz2rton import JSONDecoder

        old = self.payloads[i]
        assert len(self.files(i)) == 1 and not u32(old, 0x30)
        raw = JSONDecoder().encode_root_object(StringIO(json.dumps(manifest)))
        head = bytearray(old[:u32(old, 0x18)])
        info = trie_write([(name, (0, 0, len(raw)))], 1)
        assert u32(head, 0x4c) + len(info) <= len(head)
        head[u32(head, 0x4c):u32(head, 0x4c)+len(info)] = info
        struct.pack_into('<I', head, 0x48, len(info))
        raw += bytes((-len(raw)) % 4096)
        struct.pack_into('<I', head, 0x10, 0)
        struct.pack_into('<II', head, 0x1c, len(raw), len(raw))
        struct.pack_into('<III', head, 0x28, len(head)+len(raw), 0, 0)
        self.payloads[i] = head + raw
        self.sync_info(i)

    def sync_info(self, i):
        info, b = self.infos[i], self.payloads[i]
        struct.pack_into('<II', info, 132, len(b), i)
        info[140:176] = b[16:36] + b[32:36] + b[40:52]
        # The native loader allocates these pools before copying the RSG. A
        # larger manifest must grow its pool, even when the RSG header is valid.
        struct.pack_into('<II', self.pools[i], 128,
                         u32(b, 0x18) + u32(b, 0x20), u32(b, 0x30))

    def build(self):
        header = bytearray(self.data[:112])
        files = [(n, i) for i in range(len(self.groups)) for n, _ in self.files(i)]
        rsgs = [(g['ID'], i) for i, g in enumerate(self.groups)]
        comps = [(bytes(c[:128]).split(b'\0')[0].decode(), i)
                 for i, c in enumerate(self.composites)]
        def add(data, length_off, start_off):
            struct.pack_into('<II', header, length_off, len(data), len(header))
            header.extend(data)
        add(trie_write(files), 0x10, 0x14)
        add(trie_write(rsgs), 0x20, 0x24)
        # The three info tables store count, offset, stride rather than length.
        def table(rows, off, stride):
            struct.pack_into('<III', header, off, len(rows), len(header), stride)
            header.extend(b''.join(rows))
        table(self.composites, 0x34, 1156)
        add(trie_write(comps), 0x40, 0x44)
        info_offset = len(header)
        table(self.infos, 0x28, 204)
        table(self.pools, 0x48, 152)
        table(self.textures, 0x54, self.h['ptxInfo_EachLength'])
        header.extend(bytes((-len(header)) % 4096))
        struct.pack_into('<I', header, 0x0c, len(header))
        struct.pack_into('<4I', header, 0x60, 0, 0, 0, len(header))
        out = bytearray(header)
        for i, payload in enumerate(self.payloads):
            assert len(out) % 4096 == 0 and len(payload) % 4096 == 0
            struct.pack_into('<I', out, info_offset+i*204+128, len(out))
            out.extend(payload)
        return bytes(out)


def merge(current, legacy):
    base, source = Bundle(current), Bundle(legacy)
    mi, mn, manifest = base.manifest()
    _, _, original = source.manifest()
    existing = {g['ID'].upper() for g in base.groups}
    wanted = {g['ID'].upper() for g in source.groups
              if g['ID'].startswith('ZombiePVPSkill') and g['ID'].upper() not in existing
              and 'Rage' not in g['ID']}
    remap, added = {}, []
    for j, g in enumerate(source.groups):
        if g['ID'].upper() not in wanted:
            continue
        i = len(base.groups)
        remap[j] = i
        base.groups.append(copy.deepcopy(g))
        base.infos.append(bytearray(source.infos[j]))
        base.pools.append(bytearray(source.pools[j]))
        base.payloads.append(bytearray(source.payloads[j]))
        count, start = struct.unpack_from('<II', base.infos[i], 196)
        struct.pack_into('<I', base.infos[i], 200, len(base.textures))
        base.textures.extend(copy.deepcopy(source.textures[start:start+count]))
        base.sync_info(i)
        added.append(g['ID'])
    for comp in source.composites:
        count = u32(comp, 1152)
        indices = [u32(comp, 128+16*k) for k in range(count)]
        if not indices or not all(i in remap for i in indices):
            continue
        c = bytearray(comp)
        for k, i in enumerate(indices):
            struct.pack_into('<I', c, 128+16*k, remap[i])
            # This build requests 1536 groups only. Keep the original atlas and
            # PAM paths, but make the recovered low-resolution group selectable.
            if u32(c, 132+16*k) == 640:
                struct.pack_into('<I', c, 132+16*k, 1536)
        base.composites.append(c)
    added_ids = set(added) | {g.rsplit('_', 1)[0] for g in added}
    slot = manifest['slot_count']
    for group in original['groups']:
        if group['id'] not in added_ids:
            continue
        g = copy.deepcopy(group)
        if g.get('res') == '640':
            g['res'] = '1536'
        for subgroup in g.get('subgroups', []):
            if subgroup.get('res') == '640':
                subgroup['res'] = '1536'
        for resource in g.get('resources', []):
            resource['slot'] = slot
            slot += 1
        manifest['groups'].append(g)
    manifest['slot_count'] = slot
    base.replace_manifest(mi, mn, manifest)
    result = base.build()
    check = Bundle(result)
    assert check.manifest()[2] == manifest
    assert len(check.groups) == len(base.groups)
    assert len(check.composites) == len(base.composites)
    for i, payload in enumerate(base.payloads):
        assert check.payloads[i] == payload
    return result, added


if __name__ == '__main__':
    current, legacy, destination = map(Path, sys.argv[1:4])
    data, groups = merge(current.read_bytes(), legacy.read_bytes())
    destination.write_bytes(data)
    print(json.dumps({'added_groups': groups, 'bytes': len(data),
                      'sha256': hashlib.sha256(data).hexdigest()}))
