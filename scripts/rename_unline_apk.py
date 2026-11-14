"""Give a packaged Unline build its own Android application ID."""
import argparse
from pathlib import Path
import re
import shutil
import struct
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from rebuild_bootstrap_dex import rebuild_bootstrap


ROOT = Path(__file__).resolve().parents[1]
VARIANTS = {
    'aster': ('com.popcap.pvz2cthd.reconstruction', 'recovered-debug.keystore', 'androiddebugkey'),
    'iris': ('com.ea.game.pvz2_na', 'unline-lite.jks', 'unline-lite'),
}


def rename_manifest(data, old, new):
    pool = 8
    kind, header, size, count, styles, flags, start, style_start = struct.unpack_from('<HH6I', data, pool)
    assert (kind, header, styles, flags, style_start) == (1, 28, 0, 0, 0)
    offsets, values = bytearray(), bytearray()
    replaced = []
    for i in range(count):
        at = pool + start + struct.unpack_from('<I', data, pool + header + i * 4)[0]
        chars = struct.unpack_from('<H', data, at)[0]
        value = data[at + 2:at + 2 + chars * 2].decode('utf-16le')
        if value == old or value.startswith(old + '.'):
            replaced.append(value)
            value = new + value[len(old):]
        encoded = value.encode('utf-16le')
        offsets += struct.pack('<I', len(values))
        values += struct.pack('<H', len(encoded) // 2) + encoded + bytes(2)
    assert old in replaced
    values += bytes(-len(values) % 4)
    start = header + len(offsets)
    result = (bytearray(data[:pool]) + struct.pack('<HH6I', 1, 28, start + len(values), count, 0, 0, start, 0)
              + offsets + values + data[pool + size:])
    struct.pack_into('<I', result, 4, len(result))
    return result


def rename_resource_table(data, old, new):
    result = bytearray(data)
    at = struct.unpack_from('<H', data, 2)[0]
    patched = 0
    while at < len(data):
        kind, header, size = struct.unpack_from('<HHI', data, at)
        assert header <= size <= len(data) - at and header >= 8
        if kind == 0x200 and struct.unpack_from('<I', data, at + 8)[0] == 0x7f:
            name = data[at + 12:at + 268].decode('utf-16le').split('\0', 1)[0]
            assert name == old, name
            result[at + 12:at + 268] = new.encode('utf-16le').ljust(256, b'\0')
            patched += 1
        at += size
    assert patched == 1
    return result


def replace_aster_paths(data, old, new, count):
    def replace(match):
        path = match[0]
        return path.replace(old, new).ljust(len(path), b'\0')

    path = rb'/(?:data/data|sdcard/Android/data)/' + re.escape(old) + rb'/[^\x00]+\x00'
    result, changed = re.subn(path, replace, data)
    assert changed == count and old not in result and len(result) == len(data)
    return result


def rename_aster_dex(data, old, new, work):
    apktool = ROOT / 'tools/apktool.jar'
    helper = ROOT / 'scripts/RepairDex.java'
    subprocess.run(['javac', '-cp', apktool, '-d', work, helper], check=True)
    classpath = f'{apktool};{work}'
    original, decoded, result = (work / name for name in ('original.dex', 'smali', 'renamed.dex'))
    original.write_bytes(data)
    repair = ['java', '-Xmx512m', '-cp', classpath, 'RepairDex']
    subprocess.run([*repair, 'decode', original, decoded], check=True)
    app = decoded / 'com/popcap/SexyAppFramework/AndroidGameApp.smali'
    content = app.read_text(encoding='utf-8')
    assert content.count(f'"{old}"') == 1
    app.write_text(content.replace(f'"{old}"', f'"{new}"'), encoding='utf-8')
    subprocess.run([*repair, 'encode', decoded, result], check=True)
    return result.read_bytes()


def preserve_aster_identity(data, work):
    anchor = '    :cond_51\n    invoke-virtual {v6}, Ljava/io/File;->getParentFile()Ljava/io/File;'
    replacement = '''    :cond_51
    const-string v4, "sdcardid.dat"
    invoke-virtual {v4, v5}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v4
    if-eqz v4, :unline_extract_resource
    invoke-virtual {v6}, Ljava/io/File;->isFile()Z
    move-result v4
    if-nez v4, :goto_74
    :unline_extract_resource
    invoke-virtual {v6}, Ljava/io/File;->getParentFile()Ljava/io/File;'''
    return rebuild_bootstrap(data, work, {anchor: replacement}, ROOT / 'tools/apktool.jar')


def build(variant, source, destination, tools, key=None):
    old, key_name, alias = VARIANTS[variant]
    new = 'com.pvz2unline.' + variant
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() == destination.resolve():
        raise ValueError('Use a separate output APK')
    if key is None:
        key = (ROOT / 'work/keys' if variant == 'aster'
               else ROOT.parent / 'PvZ2-Unline-Iris/work/signing') / key_name

    with TemporaryDirectory(dir=destination.parent) as temporary:
        work = Path(temporary)
        unsigned, aligned = work / 'unsigned.apk', work / 'aligned.apk'
        with ZipFile(source) as base, ZipFile(unsigned, 'w') as apk:
            replacements = {
                'AndroidManifest.xml': rename_manifest(base.read('AndroidManifest.xml'), old, new),
                'resources.arsc': rename_resource_table(base.read('resources.arsc'), old, new),
            }
            old_bytes, new_bytes = old.encode('ascii'), new.encode('ascii')
            if variant == 'aster':
                replacements['classes.dex'] = rename_aster_dex(base.read('classes.dex'), old, new, work)
                replacements['classes8.dex'] = preserve_aster_identity(base.read('classes8.dex'), work / 'bootstrap')
                for name, count in [('libSrc.so', 1), ('libRestart.so', 4)]:
                    path = 'lib/armeabi/' + name
                    replacements[path] = replace_aster_paths(base.read(path), old_bytes, new_bytes, count)
                    if name == 'libSrc.so':
                        # The compiler folded prefix length into ARM instructions.
                        # NUL-padding the shorter package name alone truncates all
                        # per-player .eco/.def names to the same prefix.
                        from prepare_aster_save_paths import patch
                        replacements[path], _ = patch(replacements[path])
            else:
                # The OBB filename is an asset identifier and keeps its original name.
                path = 'lib/armeabi-v7a/libPVZ2.so'
                data = base.read(path)
                assert len(old_bytes) == len(new_bytes) and data.count(old_bytes + b'\0') == 1
                replacements[path] = data.replace(old_bytes + b'\0', new_bytes + b'\0')
            for info in base.infolist():
                if re.fullmatch(r'META-INF/(MANIFEST\.MF|[^/]+\.(SF|RSA|DSA|EC))', info.filename, re.I):
                    continue
                if info.filename in replacements:
                    apk.writestr(info, replacements[info.filename])
                else:
                    with base.open(info) as stream, apk.open(info, 'w') as output:
                        shutil.copyfileobj(stream, output, 1024 * 1024)
        zipalign = tools / 'zipalign.exe'
        signer = ['java', '-jar', tools / 'lib/apksigner.jar']
        subprocess.run([zipalign, '-f', '4', unsigned, aligned], check=True)
        subprocess.run([*signer, 'sign', '--ks', key, '--ks-pass', 'pass:android',
                        '--ks-key-alias', alias, '--out', destination, aligned], check=True)
        subprocess.run([*signer, 'verify', destination], check=True)
        subprocess.run([zipalign, '-c', '4', destination], check=True)
        badging = subprocess.check_output([tools / 'aapt.exe', 'dump', 'badging', destination])
        assert f"package: name='{new}'".encode() in badging
    print(f'{destination}: {new}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant', choices=VARIANTS)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('tools', type=Path)
    parser.add_argument('--key', type=Path)
    build(**vars(parser.parse_args()))
