"""Build a compressed Aster APK that stages the dynamic RSB in RGBA on device."""
import argparse
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import shutil
import struct
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile

from bake_rgba_resources import OVERLAYS, bake, decode, rsbtool, trie_read, u32
from index_texture_prefetch import ResourceZip
from rebuild_bootstrap_dex import rebuild_bootstrap


ROOT = Path(__file__).resolve().parents[1]
DEX = 'classes8.dex'
PILOT_DEX = 'classes11.dex'
ASSET = OVERLAYS['dynamic.rsb.smf']
PLAN = 'assets/reconstruction/aster-dynamic-rgba.plan'
BASELINE = 'assets/reconstruction/aster-background-baseline'
PILOT = 'Lcom/popcap/pvz2cthd/AsterRgbaPilot;'
BOOT = 'Lcom/popcap/pvz2cthd/BootActivity;'


def group_list(data):
    h = rsbtool.parse_head(data)
    return rsbtool.read_rsgp_info(data, h['rsgpInfo_BeginOffset'],
                                 h['rsgp_Number'], h['rsgpInfo_EachLength'])


def create_plan(original, output):
    baked = output / 'dynamic-rgba.reference'
    assert bake(BytesIO(original), baked) == (2, 0)
    target = baked.read_bytes()
    instructions = []
    reconstructed = sha256()

    def literal(data):
        if data:
            instructions.append(struct.pack('>BI', 0, len(data)) + data)
            reconstructed.update(data)

    def copy(offset, size):
        if size:
            instructions.append(struct.pack('>BII', 1, offset, size))
            reconstructed.update(original[offset:offset + size])

    literal(target[:u32(target, 12)])
    end = u32(target, 12)
    textures = 0
    for before, after in zip(group_list(original), group_list(target), strict=True):
        assert before['ID'] == after['ID']
        old_start, old_size = before['fields'][:2]
        new_start, new_size = after['fields'][:2]
        assert new_start == end
        end += new_size
        old = original[old_start:old_start + old_size]
        new = target[new_start:new_start + new_size]
        if old == new:
            copy(old_start, old_size)
            continue
        assert u32(old, 16) & 1 == 0 and u32(new, 16) & 1 == 0
        header_end = u32(new, 24)
        texture_start = u32(new, 40)
        assert (header_end, texture_start) == (u32(old, 24), u32(old, 40))
        assert old[header_end:texture_start] == new[header_end:texture_start]
        literal(new[:header_end])
        copy(old_start + header_end, texture_start - header_end)
        old_items = dict(trie_read(old, u32(old, 0x4c), u32(old, 0x48), 1))
        new_items = [(n, e) for n, e in trie_read(new, u32(new, 0x4c), u32(new, 0x48), 1)
                     if e[0] == 1]
        position = texture_start
        for name, entry in sorted(new_items, key=lambda item: item[1][1]):
            _, old_offset, old_length, *old_info = old_items[name]
            _, new_offset, new_length, *new_info = entry
            assert old_info == new_info
            width, height = entry[-2:]
            assert width % 4 == height % 4 == 0 and width <= 4096
            assert old_length == width * height and new_length == width * height * 4
            old_position = texture_start + old_offset
            new_position = texture_start + new_offset
            assert new_position >= position
            literal(new[position:new_position])
            instructions.append(struct.pack('>BIII', 2, old_start + old_position, width, height))
            reconstructed.update(decode(old[old_position:old_position + old_length], width, height, 152))
            position = new_position + new_length
            textures += 1
        literal(new[position:])
    assert end == len(target) and textures == 2
    assert reconstructed.digest() == sha256(target).digest()
    return (struct.pack('>4sII', b'ABG1', len(original), len(target)) + sha256(original).digest()
            + struct.pack('>I', len(instructions)) + b''.join(instructions))


def patch_boot(dex, out):
    overlay = f'    invoke-direct {{p0}}, {BOOT}->applyOriginalSpeedResource()V'
    synthetic = f'.method static synthetic access$300({BOOT})V\n    .registers 1'
    launch = f'    iput-boolean v0, p0, {BOOT}->gameStarted:Z\n\n    .line 448'
    changes = {
        synthetic: synthetic.replace('.registers 1', '.registers 2'),
        overlay: f'''    invoke-static {{p0}}, {PILOT}->ensureBaseline(Landroid/content/Context;)V

    invoke-static {{p0}}, {PILOT}->useReady(Landroid/content/Context;)Z
    move-result v0
    if-nez v0, :aster_skip_overlay
{overlay}
    :aster_skip_overlay''',
        launch: f'''    iput-boolean v0, p0, {BOOT}->gameStarted:Z

    invoke-static {{p0}}, {PILOT}->start(Landroid/content/Context;)V

    .line 448''',
    }
    return rebuild_bootstrap(dex, out, changes, ROOT / 'tools/apktool.jar')


def compile_pilot(out, sdk, ndk, astc):
    source = ROOT / 'src/bootstrap-extra'
    classes = out / 'classes'
    dex = out / 'dex'
    classes.mkdir(exist_ok=True)
    dex.mkdir(exist_ok=True)
    android = sdk / 'platforms/android-34/android.jar'
    tools = sdk / 'build-tools/34.0.0'
    subprocess.run(['javac', '-source', '8', '-target', '8', '-Xlint:-options',
                    '-bootclasspath', android, '-d', classes,
                    source / 'com/popcap/pvz2cthd/AsterRgbaPilot.java'], check=True)
    jar = out / 'pilot.jar'
    with ZipFile(jar, 'w') as archive:
        for path in sorted(classes.rglob('*.class')):
            archive.write(path, path.relative_to(classes).as_posix())
    subprocess.run(['java', '-Xmx256m', '-cp', tools / 'lib/d8.jar', 'com.android.tools.r8.D8',
                    '--min-api', '21', '--lib', android, '--output', dex, jar], check=True)
    clang = ndk / 'toolchains/llvm/prebuilt/windows-x86_64/bin/clang++.exe'
    names = ('astc_file', 'codec', 'endpoint_codec', 'footprint', 'integer_sequence_codec',
             'intermediate_astc_block', 'logical_astc_block', 'partition', 'physical_astc_block',
             'quantization', 'weight_infill')
    cpp = [source / 'aster_rgba_astc.cpp', *(astc / 'src/decoder' / (name + '.cc') for name in names)]
    flags = [clang, '--target=armv7a-linux-androideabi21', '-std=c++17', '-O2', '-mthumb', '-fPIC',
             '-fno-exceptions', '-fno-rtti', '-fvisibility=hidden', '-I' + str(astc), '-I' + str(astc / 'include')]
    objects = []
    for path in cpp:
        obj = out / (path.stem + '.o')
        obj.write_bytes(subprocess.check_output([*flags, '-c', path, '-o', '-']))
        objects.append(obj)
    library = subprocess.check_output([*flags, '-shared', '-static-libstdc++', '-Wl,--no-undefined',
                                       '-Wl,-soname,libAsterRgbaPilot.so', *objects, '-o', '-'])
    return (dex / 'classes.dex').read_bytes(), library


def baseline_sizes(source, base):
    with ZipFile(ResourceZip(source)) as archive:
        names = {
            Path(item.filename).name: item.file_size for item in archive.infolist()
            if item.filename.startswith('com.popcap.pvz2cthd/files/') and item.filename.endswith('.rsb.smf')
        }
    assert len(names) == 19
    del names['dynamic.rsb.smf']
    names['zombie2.rsb.smf'] = base.getinfo(OVERLAYS['zombie2.rsb.smf']).file_size
    result = bytearray(struct.pack('>H', len(names)))
    for name, size in sorted(names.items()):
        raw = name.encode('ascii')
        result.extend(struct.pack('>H', len(raw)) + raw + struct.pack('>I', size))
    return bytes(result)


def build(source, out, sdk, ndk, astc, pvp_gold=False):
    out.mkdir(parents=True, exist_ok=True)
    final_name = ('PvZ2-Unline-Aster-v163-pvp-gold.apk' if pvp_gold
                  else 'PvZ2-Unline-Aster-v163-background-rgba-pilot-r2.apk')
    unsigned, aligned, final = (out / name for name in
                                ('unsigned.apk', 'aligned.apk', final_name))
    tools = sdk / 'build-tools/34.0.0'
    pilot_dex, library = compile_pilot(out, sdk, ndk, astc)
    with ZipFile(source) as base:
        abi = 'lib/armeabi'
        native = abi + '/libSrc.so'
        assert native in base.namelist()
        original = base.read(ASSET)
        replacements = {DEX}
        extra = {}
        if pvp_gold:
            from prepare_aster_pvp_gold import patch_native, prepare_layout
            original = prepare_layout(original)
            extra = {ASSET: original, native: patch_native(base.read(native))}
            replacements.update(extra)
        changes = {
            **extra,
            DEX: patch_boot(base.read(DEX), out / 'boot'),
            PILOT_DEX: pilot_dex,
            PLAN: create_plan(original, out),
            BASELINE: baseline_sizes(source, base),
            abi + '/libAsterRgbaPilot.so': library,
            'assets/reconstruction/aster-astc-codec-LICENSE': (astc / 'LICENSE').read_bytes(),
        }
        assert set(changes).intersection(base.namelist()) == replacements
        with ZipFile(unsigned, 'w') as apk:
            for item in base.infolist():
                if item.filename in changes or item.filename.startswith('META-INF/'):
                    continue
                with base.open(item) as stream, apk.open(item, 'w') as dest:
                    shutil.copyfileobj(stream, dest, 1024 * 1024)
            for name, data in changes.items():
                apk.writestr(name, data, ZIP_DEFLATED)
    subprocess.run([tools / 'zipalign.exe', '-f', '4', unsigned, aligned], check=True)
    signer = ['java', '-jar', tools / 'lib/apksigner.jar']
    subprocess.run([*signer, 'sign', '--ks', ROOT / 'work/keys/recovered-debug.keystore',
                    '--ks-pass', 'pass:android', '--key-pass', 'pass:android',
                    '--ks-key-alias', 'androiddebugkey', '--out', final, aligned], check=True)
    subprocess.run([*signer, 'verify', final], check=True)
    subprocess.run([tools / 'zipalign.exe', '-c', '4', final], check=True)
    unsigned.unlink()
    aligned.unlink()
    print(f'APK: {final} ({final.stat().st_size:,} bytes). Plan: {len(changes[PLAN]):,} bytes.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'out', 'sdk', 'ndk', 'astc'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--pvp-gold', action='store_true')
    build(**vars(parser.parse_args()))
