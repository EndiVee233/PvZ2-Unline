"""Apply the shared desktop-focus/speed-feedback Java fixes to ARM32 Aster."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from zipfile import ZipFile

from build_aster_arm64_game import (
    ROOT, adapt_desktop_focus, compile_speed_feedback, copy_compressed_entry,
)


def build(apk, sdk, output, profile_memory_ndk=None):
    apk, output = apk.resolve(), output.resolve()
    if apk == output / 'PvZ2-Unline-Aster-ARM32.apk':
        raise ValueError('Input and output must differ')
    output.mkdir(parents=True, exist_ok=True)
    java = output / 'java'
    java.mkdir(exist_ok=True)
    apktool = ROOT / 'tools/apktool.jar'
    subprocess.run(['javac', '-cp', apktool, '-d', java, ROOT / 'scripts/RepairDex.java'], check=True)
    repair = ['java', '-Xmx512m', '-cp', str(apktool) + os.pathsep + str(java), 'RepairDex']
    feedback = compile_speed_feedback(sdk, java, repair)
    replacements = {}
    with ZipFile(apk) as source:
        natives = {name: hashlib.sha256(source.read(name)).hexdigest()
                   for name in source.namelist() if name.startswith('lib/') and name.endswith('.so')}
        if not natives or any(not name.startswith('lib/armeabi/') for name in natives):
            raise ValueError('Expected the existing ARM32 Aster native libraries')
        native_changes = []
        if profile_memory_ndk is not None:
            from prepare_profile_memory import patch
            name = 'lib/armeabi/libSrc.so'
            patched, _ = patch(source.read(name), profile_memory_ndk, output / 'profile-memory')
            replacements[name] = patched
            natives[name] = hashlib.sha256(patched.read_bytes()).hexdigest()
            native_changes.append(name)
        for name in ('classes.dex', 'classes10.dex'):
            original, folder = java / name, java / name.replace('.', '-')
            data = source.read(name)
            digest = hashlib.sha256(data).hexdigest()
            marker = folder / '.source-sha256'
            if not marker.exists() or marker.read_text() != digest:
                if folder.exists():
                    if not folder.resolve().is_relative_to(java.resolve()):
                        raise ValueError('DEX work directory outside output')
                    shutil.rmtree(folder)
                original.write_bytes(data)
                subprocess.run([*repair, 'decode', original, folder], check=True)
                marker.write_text(digest)
            if name == 'classes.dex':
                surface = folder / 'com/popcap/SexyAppFramework/AndroidSurfaceView.smali'
                surface.write_text(adapt_desktop_focus(surface.read_text(encoding='utf8')), encoding='utf8')
            else:
                speed = folder / 'com/popcap/pvz2cthd/SpeedFeedback.smali'
                if not speed.exists():
                    raise ValueError('Original speed feedback class missing')
                for path in speed.parent.glob('SpeedFeedback*.smali'):
                    path.unlink()
                for filename, content in feedback.items():
                    speed.with_name(filename).write_text(content, encoding='utf8')
            rebuilt = java / ('adapted-' + name)
            subprocess.run([*repair, 'encode', folder, rebuilt], check=True)
            replacements[name] = rebuilt
        unsigned, aligned, signed = [output / name for name in
                                    ('unsigned.apk', 'aligned.apk', 'PvZ2-Unline-Aster-ARM32.apk')]
        with ZipFile(unsigned, 'w') as target:
            for info in source.infolist():
                if info.filename.startswith('META-INF/'):
                    continue
                if info.filename in replacements:
                    target.writestr(info, replacements[info.filename].read_bytes())
                else:
                    copy_compressed_entry(source, info, target)
    tools = sdk / 'build-tools/34.0.0'
    subprocess.run([tools / 'zipalign.exe', '-p', '-f', '4', unsigned, aligned], check=True)
    signer = ['java', '-jar', tools / 'lib/apksigner.jar']
    subprocess.run([*signer, 'sign', '--ks', ROOT / 'work/keys/recovered-debug.keystore',
                    '--ks-pass', 'pass:android', '--ks-key-alias', 'androiddebugkey',
                    '--out', signed, aligned], check=True)
    subprocess.run([*signer, 'verify', signed], check=True)
    badging = subprocess.check_output([tools / 'aapt.exe', 'dump', 'badging', signed]).decode()
    if "package: name='com.pvz2unline.aster'" not in badging or "native-code: 'armeabi'" not in badging:
        raise ValueError('Unexpected package or architecture')
    with ZipFile(signed) as target:
        for name, expected in natives.items():
            if hashlib.sha256(target.read(name)).hexdigest() != expected:
                raise ValueError('ARM32 native library changed: ' + name)
    with signed.open('rb') as stream:
        apk_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    validation = {'package': 'com.pvz2unline.aster', 'abi': 'armeabi',
                  'native_libraries_expected': natives,
                  'changed_native_libraries': native_changes,
                  'changed_dex': [name for name in replacements if name.endswith('.dex')],
                  'apk_sha256': apk_hash}
    (output / 'validation.json').write_text(json.dumps(validation, indent=2), encoding='utf8')
    print(signed, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('apk', 'sdk', 'output'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--profile-memory-ndk', type=Path,
                        help='Compile and apply last-player persistence to the shared engine')
    build(**vars(parser.parse_args()))
