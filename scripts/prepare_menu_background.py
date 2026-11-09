"""Replace the native title atlas with the supplied image."""
from pathlib import Path
import struct
import subprocess

from PIL import Image
from prepare_offline_pvp_seagull_hd import Bundle, replace_section, section, texture_section


def prepare(resource, artwork, encoder, output):
    bundle = Bundle(resource)
    group_id = 'MainMenu_Background_1536'
    index, = (i for i, group in enumerate(bundle.groups) if group['ID'] == group_id)
    files = bundle.files(index)
    (_, (kind, offset, length, atlas_id, _, _, width, height)), = files
    count, texture_id = struct.unpack_from('<II', bundle.infos[index], 196)
    assert (kind, offset, atlas_id, count) == (1, 0, 0, 1)
    assert struct.unpack_from('<4I', bundle.textures[texture_id]) == (width, height, width, 152)
    assert length == width * height

    manifest_index, manifest_name, manifest = bundle.manifest()
    group, = (group for group in manifest['groups'] if group['id'] == group_id)
    atlas, image = group['resources']
    assert atlas['atlas'] and image['parent'] == atlas['id'] and (image['ax'], image['ay']) == (1, 1)
    output = Path(output)
    with Image.open(artwork) as source:
        art = source.convert('RGBA')
    w, h = art.size
    assert 0 < w <= width - 2 and 0 < h <= height - 2
    texture = Image.new('RGBA', (width, height))
    texture.paste(art, (1, 1))
    # Extrude one texel into the atlas border for bilinear filtering.
    texture.paste(art.crop((0, 0, 1, h)), (0, 1))
    texture.paste(art.crop((w - 1, 0, w, h)), (w + 1, 1))
    texture.paste(texture.crop((0, 1, w + 2, 2)), (0, 0))
    texture.paste(texture.crop((0, h, w + 2, h + 1)), (0, h + 1))
    png, astc = output / 'menu-atlas.png', output / 'menu-atlas.astc'
    texture.save(png)
    subprocess.run([str(encoder), '-cl', str(png), str(astc), '4x4', '-medium', '-silent'], check=True)
    encoded = astc.read_bytes()
    assert encoded[:7] == bytes.fromhex('13aba15c040401')
    assert tuple(int.from_bytes(encoded[pos:pos + 3], 'little') for pos in (7, 10, 13)) == (width, height, 1)
    assert len(encoded) == 16 + length
    atlas.update(width=w + 2, height=h + 2)
    image.update(aw=w, ah=h)

    replace_section(bundle, index, files, section(bundle, index), encoded[16:])
    bundle.replace_manifest(manifest_index, manifest_name, manifest)
    result = bundle.build()
    check = Bundle(result)
    assert check.manifest()[2] == manifest
    assert texture_section(check.payloads[index])[:length] == encoded[16:]
    for i, payload in enumerate(bundle.payloads):
        assert check.payloads[i] == payload
    return result
