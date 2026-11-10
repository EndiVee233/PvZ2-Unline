"""Bake the textures used by the packaged Aster RSBs into RGBA8888."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import shutil
import struct
from zipfile import ZipFile
import zlib

from PIL import Image
import texture2ddecoder

from index_texture_prefetch import ResourceZip
from merge_legacy_pvp_resources import rsbtool, trie_read, trie_write, u32


OVERLAYS = {
    'dynamic.rsb.smf': 'assets/reconstruction/dynamic-original-speed.rsb.smf',
    'zombie2.rsb.smf': 'assets/reconstruction/zombie2-pvp.rsb.smf',
}
ASTC_BLOCK = {152: 4, 161: 5, 162: 6}


def pad(length):
    return bytes(-length % 4096)


def decode(data, width, height, fmt):
    if fmt == 0:
        if len(data) != width * height * 4:
            raise ValueError('Incorrect RGBA8888 texture length')
        return data
    if fmt in ASTC_BLOCK:
        edge = ASTC_BLOCK[fmt]
        if len(data) != ((width + edge - 1) // edge) * ((height + edge - 1) // edge) * 16:
            raise ValueError('Incorrect ASTC texture length')
        bgra = texture2ddecoder.decode_astc(data, width, height, edge, edge)
        return Image.frombytes('RGBA', (width, height), bgra, 'raw', 'BGRA').tobytes()
    if fmt != 147:
        raise ValueError(f'Unsupported texture format {fmt}')
    rgb_size = ((width + 3) // 4) * ((height + 3) // 4) * 8
    rgb, alpha = data[:rgb_size], data[rgb_size:]
    if len(alpha) == width * height:
        plane = alpha
    else:
        count = alpha[0]
        palette, indices = alpha[1:1 + count], alpha[1 + count:]
        if not 0 < count <= 16 or any(value > 15 for value in palette) or len(indices) * 2 != width * height:
            raise ValueError('Invalid ETC1 alpha palette')
        # Two four-bit palette indices per byte, high nibble first.
        if any((value >> 4) >= count or (value & 15) >= count for value in set(indices)):
            raise ValueError('Invalid ETC1 alpha index')
        values = bytes(value * 17 for value in palette).ljust(16, b'\0')
        plane = bytearray(width * height)
        plane[::2] = indices.translate(bytes(values[i >> 4] for i in range(256)))
        plane[1::2] = indices.translate(bytes(values[i & 15] for i in range(256)))
        plane = bytes(plane)
    bgra = texture2ddecoder.decode_etc1(rgb, width, height)
    image = Image.frombytes('RGBA', (width, height), bgra, 'raw', 'BGRA')
    image.putalpha(Image.frombytes('L', (width, height), plane))
    return image.tobytes()


def rewrite_group(block, header, first, count, texture_start, stride):
    table_size, table_start = struct.unpack_from('<II', block, 0x48)
    entries = trie_read(block, table_start, table_size, 1)
    texture_offset, stored_size, original_size = struct.unpack_from('<III', block, 40)
    if not any(info[0] == 1 for _, info in entries):
        if original_size:
            raise ValueError('Texture bytes without PTX entries')
        return block, set()

    source = block[texture_offset:texture_offset + stored_size]
    if u32(block, 16) & 1:
        source = zlib.decompress(source)
    if len(source) != original_size:
        raise ValueError('Unexpected RSG texture pool size')
    output = bytearray()
    updated = []
    converted = {}
    for name, info in entries:
        if info[0] != 1:
            updated.append((name, info))
            continue
        _, offset, length, slot, _, _, width, height = info
        if slot >= count or offset + length > len(source):
            raise ValueError(f'Invalid texture range: {name}')
        row = texture_start + (first + slot) * stride
        key = (row, offset, length)
        if key not in converted:
            w, h, _, fmt = struct.unpack_from('<4I', header, row)
            if (w, h) != (width, height):
                raise ValueError(f'Mismatched texture dimensions: {name}')
            pixels = decode(source[offset:offset + length], width, height, fmt)
            converted[key] = (len(output), len(pixels))
            output.extend(pixels)
            output.extend(pad(len(output)))
        updated.append((name, (1, *converted[key], *info[3:])))
    rows = {row for row, _, _ in converted}
    for row in rows:
        struct.pack_into('<II', header, row + 8, u32(header, row) * 4, 0)

    new_table = trie_write(updated, 1)
    if table_start + len(new_table) > u32(block, 24):
        raise ValueError('New texture table exceeds the RSG header')
    head = bytearray(block[:texture_offset])
    head[table_start:table_start + len(new_table)] = new_table
    struct.pack_into('<I', head, 0x48, len(new_table))
    # This engine's startup path expects uncompressed RSG texture sections.
    # Compress the APK resource archive instead of these individual sections.
    struct.pack_into('<I', head, 16, u32(head, 16) & ~1)
    struct.pack_into('<II', head, 44, len(output), len(output))
    if trie_read(head, table_start, len(new_table), 1) != updated:
        raise ValueError('RSG texture index failed its round trip')
    return head + output, rows


def bake(source, target):
    lead = source.read(112)
    if lead[:4] != b'1bsr':
        raise ValueError('Expected an unwrapped RSB')
    h = rsbtool.parse_head(lead)
    header = bytearray(lead + source.read(u32(lead, 12) - len(lead)))
    groups = rsbtool.read_rsgp_info(header, h['rsgpInfo_BeginOffset'], h['rsgp_Number'], h['rsgpInfo_EachLength'])
    texture_start, stride = h['ptxInfo_BeginOffset'], h['ptxInfo_EachLength']
    pool_start, pool_stride = h['autopoolInfo_BeginOffset'], h['autopoolInfo_EachLength']
    all_rows = set()
    with target.open('wb') as out:
        out.write(header)
        for i, group in enumerate(groups):
            at = group['at']
            offset, size = group['fields'][:2]
            count, first = struct.unpack_from('<II', header, at + 196)
            source.seek(offset)
            block = source.read(size)
            if len(block) != size or block[:4] != b'pgsr':
                raise ValueError(f'Invalid RSG {group["ID"]}')
            block, rows = rewrite_group(block, header, first, count, texture_start, stride)
            if out.tell() % 4096 or len(block) % 4096:
                raise ValueError('RSB payload alignment changed')
            struct.pack_into('<II', header, at + 128, out.tell(), len(block))
            if rows:
                header[at + 140:at + 176] = block[16:36] + block[32:36] + block[40:52]
                struct.pack_into('<II', header, pool_start + i * pool_stride + 128,
                                 u32(block, 24) + u32(block, 32), u32(block, 48))
                all_rows.update(rows)
            out.write(block)
        out.seek(0)
        out.write(header)
    inactive = h['ptx_Number'] - len(all_rows)
    print(f'{target.name}: {len(all_rows)} RGBA atlases, {inactive} unreferenced slots, {target.stat().st_size:,} bytes', flush=True)
    return len(all_rows), inactive


def bake_one(args):
    source, target = args
    with source.open('rb') as f:
        return bake(f, target)


def main(apk, output, workers):
    originals = output / 'original'
    originals.mkdir(parents=True, exist_ok=True)
    tasks = []
    with ZipFile(apk) as outer, ZipFile(ResourceZip(apk)) as inner:
        for member in inner.namelist():
            if not member.endswith('.rsb.smf'):
                continue
            name = Path(member).name
            base = originals / name
            if name in OVERLAYS:
                source = outer.open(OVERLAYS[name])
            else:
                source = inner.open(member)
            with source, base.open('wb') as destination:
                shutil.copyfileobj(source, destination, 1024 * 1024)
            tasks.append((base, output / name))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        counts = list(pool.map(bake_one, tasks))
    print(f'Total: {sum(n for n, _ in counts)} RGBA atlases, {sum(n for _, n in counts)} unreferenced slots', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    main(args.apk, args.output, args.workers)
