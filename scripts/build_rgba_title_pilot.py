"""Repackage one Aster title atlas as RGBA8888 for a controlled APK comparison."""
import argparse
import hashlib
from pathlib import Path
import shutil
import struct
import subprocess
from zipfile import ZipFile

from PIL import Image
import texture2ddecoder

from prepare_offline_pvp_seagull_hd import Bundle, replace_section, section, texture_section
from rebuild_bootstrap_dex import rebuild_bootstrap


ROOT = Path(__file__).resolve().parents[1]
ASSET = 'assets/reconstruction/dynamic-original-speed.rsb.smf'
BOOTSTRAP = 'classes8.dex'
TITLE_GROUP = 'MainMenu_Background_1536'


def convert(resource):
    bundle = Bundle(resource)
    index, = (i for i, group in enumerate(bundle.groups) if group['ID'] == TITLE_GROUP)
    (name, info), = bundle.files(index)
    kind, offset, size, atlas, _, _, width, height = info
    count, row = struct.unpack_from('<II', bundle.infos[index], 196)
    assert (kind, offset, atlas, count) == (1, 0, 0, 1)
    assert struct.unpack_from('<4I', bundle.textures[row]) == (width, height, width, 152)
    assert size == ((width + 3) // 4) * ((height + 3) // 4) * 16
    encoded = texture_section(bundle.payloads[index])[:size]
    assert len(encoded) == size
    pixels = texture2ddecoder.decode_astc(encoded, width, height, 4, 4)
    rgba = Image.frombytes('RGBA', (width, height), pixels, 'raw', 'BGRA').tobytes()
    assert len(rgba) == width * height * 4

    original = Bundle(resource)
    struct.pack_into('<II', bundle.textures[row], 8, width * 4, 0)
    entry = (kind, offset, len(rgba), *info[3:])
    replace_section(bundle, index, [(name, entry)], section(bundle, index), rgba)
    output = bundle.build()
    verified = Bundle(output)
    assert verified.files(index) == [(name, entry)]
    assert verified.textures == bundle.textures
    assert texture_section(verified.payloads[index])[:len(rgba)] == rgba
    assert section(verified, index) == section(original, index)
    assert all(a == b for i, (a, b) in enumerate(zip(verified.payloads, original.payloads)) if i != index)
    print(f'{TITLE_GROUP}: {width} x {height}, {size:,} ASTC bytes -> {len(rgba):,} RGBA bytes', flush=True)
    return output


def build(source, output, tools, predecessor_apk=None):
    output.mkdir(parents=True, exist_ok=True)
    unsigned, aligned = (output / name for name in ('unsigned.apk', 'aligned.apk'))
    final = output / (source.stem + '-rgba-title-pilot.apk')
    with ZipFile(source) as base:
        old = base.read(ASSET)
        resource = convert(old)
        old_hash, new_hash = (hashlib.sha256(data).hexdigest() for data in (old, resource))
        method = '.method private static isSupportedResourcePredecessor(Ljava/lang/String;)Z\n    .registers 2'
        accepted = {old_hash}
        if predecessor_apk is not None:
            with ZipFile(predecessor_apk) as predecessor:
                accepted.add(hashlib.sha256(predecessor.read(ASSET)).hexdigest())
        predecessor = method
        for i, digest in enumerate(sorted(accepted)):
            predecessor += f'''

    const-string v0, "{digest}"
    invoke-virtual {{v0, p0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :rgba_pilot_predecessor_{i}
    const/4 v0, 0x1
    return v0
    :rgba_pilot_predecessor_{i}'''
        boot = rebuild_bootstrap(base.read(BOOTSTRAP), output / 'boot', {
            old_hash: new_hash,
            '.offline-pvp-v59-' + old_hash[:12]: '.offline-pvp-v59-' + new_hash[:12],
            f'const-wide/32 v7, {hex(len(old))}': f'const-wide/32 v7, {hex(len(resource))}',
            method: predecessor,
        }, ROOT / 'tools/apktool.jar')
        changes = {ASSET: resource, BOOTSTRAP: boot}
        with ZipFile(unsigned, 'w') as apk:
            for item in base.infolist():
                if item.filename.startswith('META-INF/'):
                    continue
                if item.filename in changes:
                    apk.writestr(item, changes[item.filename])
                else:
                    with base.open(item) as src, apk.open(item, 'w') as dst:
                        shutil.copyfileobj(src, dst, 1024 * 1024)

    subprocess.run([tools / 'zipalign.exe', '-f', '4', unsigned, aligned], check=True)
    unsigned.unlink()
    signer = ['java', '-jar', tools / 'lib/apksigner.jar']
    subprocess.run([*signer, 'sign', '--ks', ROOT / 'work/keys/recovered-debug.keystore',
                    '--ks-pass', 'pass:android', '--key-pass', 'pass:android',
                    '--ks-key-alias', 'androiddebugkey', '--out', final, aligned], check=True)
    subprocess.run([*signer, 'verify', final], check=True)
    subprocess.run([tools / 'zipalign.exe', '-c', '4', final], check=True)
    aligned.unlink()

    def inventory(apk):
        return {item.filename: (item.CRC, item.file_size) for item in apk.infolist()
                if not item.filename.startswith('META-INF/')}

    with ZipFile(source) as base, ZipFile(final) as apk:
        before, after = inventory(base), inventory(apk)
        assert before.keys() == after.keys()
        assert {name for name in after if before[name] != after[name]} == changes.keys()
        assert all(apk.read(name) == data for name, data in changes.items())
        print(f'APK: {final}\nSize delta: {final.stat().st_size - source.stat().st_size:+,} bytes', flush=True)
        print(f'Installed dynamic resource SHA-256: {new_hash}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--build-tools', type=Path, default=Path('Y:/Android/Sdk/build-tools/34.0.0'))
    parser.add_argument('--predecessor-apk', type=Path)
    args = parser.parse_args()
    build(args.apk, args.output, args.build_tools, args.predecessor_apk)
