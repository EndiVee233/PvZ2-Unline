"""Build an experimental ARM64 Aster APK with the existing Java/game assets."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import struct
import tempfile
from zipfile import ZipFile, ZIP_STORED

ROOT = Path(__file__).resolve().parents[1]
GUESTS = ('Src', 'czProject', 'HookPVZ2', 'Restart', 'PresetEditor', 'AsterRgbaPilot')
TYPES = dict(V='void', Z='jboolean', B='jbyte', C='jchar', S='jshort', I='jint',
             J='jlong', F='jfloat', D='jdouble')


def signature_parts(signature):
    def read(at):
        end = at
        while signature[end] == '[':
            end += 1
        end = signature.index(';', end) + 1 if signature[end] == 'L' else end + 1
        return signature[at:end], end
    assert signature[0] == '('
    params, at = [], 1
    while signature[at] != ')':
        value, at = read(at)
        params.append(value)
    result, end = read(at + 1)
    assert end == len(signature)
    return params, result


def reference(value):
    return value.startswith(('L', '['))


def contract_source(contracts):
    result = ['// Generated from native declarations in this APK, not a separate game version.']
    for index, (owner, methods) in enumerate(contracts):
        for number, (name, signature, static) in enumerate(methods):
            params, returns = signature_parts(signature)
            return_type = 'jobject' if reference(returns) else TYPES[returns]
            args = ['JNIEnv* env', ('jclass' if static else 'jobject') + ' receiver']
            values = []
            for i, kind in enumerate(params):
                args.append(('jobject' if reference(kind) else TYPES[kind]) + f' a{i}')
                if reference(kind):
                    values.append(f'Argument::ref(a{i})')
                elif kind in ('D', 'J'):
                    values.append(f'Argument::large(std::bit_cast<uint64_t>(a{i}))')
                elif kind == 'F':
                    values.append(f'Argument::scalar(std::bit_cast<uint32_t>(a{i}))')
                else:
                    values.append(f'Argument::scalar(uint32_t(a{i}))')
            result.append(f'static {return_type} wrapper_{index}_{number}({", ".join(args)}) {{')
            result.append(f'    const auto result=invoke(env,receiver,{index},"{name}","{signature}",'
                          f'{{{",".join(values)}}},{str(reference(returns)).lower()});')
            if reference(returns):
                result.append('    return result.object;')
            elif returns in ('F', 'D'):
                bits = 'uint32_t(result.bits)' if returns == 'F' else 'result.bits'
                result.append(f'    return std::bit_cast<{return_type}>({bits});')
            elif returns != 'V':
                result.append(f'    return static_cast<{return_type}>(result.bits);')
            result.append('}')
        result.append(f'static const JNINativeMethod methods_{index}[]={{')
        for number, (name, signature, static) in enumerate(methods):
            result.append(f'    {{const_cast<char*>("{name}"),const_cast<char*>("{signature}"),'
                          f'reinterpret_cast<void*>(&wrapper_{index}_{number})}},')
        result.append('};')
    result.append('Contract contracts[]={')
    for index, (owner, methods) in enumerate(contracts):
        result.append(f'    {{"{owner}",methods_{index},std::size(methods_{index}),nullptr}},')
    result.extend(['};', 'const size_t contractCount=std::size(contracts);'])
    return '\n'.join(result) + '\n'


def copy_compressed_entry(source, info, target):
    """Retain original compressed resource bytes; rewrite only ZIP offsets.

    Aster is a classic ZIP APK (<4 GiB per entry). Removing data descriptors
    lets the local header carry checked sizes from the source central index.
    ZipFile still owns central-directory serialization and finalization.
    """
    if info.file_size >= 0xffffffff or info.compress_size >= 0xffffffff or info.flag_bits & 1:
        raise ValueError('Encrypted/ZIP64 source entry unsupported')
    source.fp.seek(info.header_offset)
    header = source.fp.read(30)
    fields = list(struct.unpack('<IHHHHHIIIHH', header))
    if fields[0] != 0x04034b50 or fields[3] != info.compress_type:
        raise ValueError('Invalid source local header')
    fields[2] &= ~8
    fields[6:9] = info.CRC, info.compress_size, info.file_size
    suffix = source.fp.read(fields[9] + fields[10])
    clone = copy.copy(info)
    clone.flag_bits &= ~8
    clone.header_offset = target.fp.tell()
    target._writecheck(clone)
    target._didModify = True
    target.fp.write(struct.pack('<IHHHHHIIIHH', *fields))
    target.fp.write(suffix)
    remaining = info.compress_size
    while remaining:
        chunk = source.fp.read(min(1024 * 1024, remaining))
        if not chunk:
            raise ValueError('Truncated compressed source entry')
        target.fp.write(chunk)
        remaining -= len(chunk)
    target.start_dir = target.fp.tell()
    target.filelist.append(clone)
    target.NameToInfo[clone.filename] = clone


def adapt_desktop_focus(text):
    """Consume Tab on the game surface, without changing real text fields."""
    owner = 'Lcom/popcap/SexyAppFramework/AndroidSurfaceView;'
    helper = 'configureDesktopFocus'
    if f'.method private {helper}()V' not in text:
        anchor = f'invoke-virtual {{p0, p2}}, {owner}->setFocusableInTouchMode(Z)V'
        if text.count(anchor) != 1:
            raise ValueError('Unknown game surface focus initialization')
        text = text.replace(anchor, anchor + f'\n\n    invoke-direct {{p0}}, {owner}->{helper}()V')
        text += (
            f'\n.method private {helper}()V\n'
            '    .registers 3\n'
            '    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I\n'
            '    const/16 v1, 0x1a\n'
            '    if-lt v0, v1, :focus_configured\n'
            '    const/4 v0, 0x0\n'
            '    invoke-virtual {p0, v0}, Landroid/view/View;->setDefaultFocusHighlightEnabled(Z)V\n'
            '    :focus_configured\n'
            '    return-void\n'
            '.end method\n')
    for method in ('onKeyDown', 'onKeyUp'):
        pattern = rf'(?m)(^\.method public {method}\(ILandroid/view/KeyEvent;\)Z\n    \.registers 5\n)'
        start = re.search(pattern, text)
        if not start:
            raise ValueError('Unknown game surface key registers: ' + method)
        body = text[start.end():text.index('.end method', start.end())]
        if ':aster_non_tab' not in body:
            text = text[:start.end()] + (
                '\n    const/16 v0, 0x3d\n'
                '    if-ne p1, v0, :aster_non_tab\n'
                '    const/4 v0, 0x1\n'
                '    return v0\n'
                '    :aster_non_tab\n') + text[start.end():]
    return text


def compile_speed_feedback(sdk, output, repair):
    """Rebuild the standalone Android effect, including D8's synthetic classes."""
    source = ROOT / 'src/bootstrap-extra/com/popcap/pvz2cthd/SpeedFeedback.java'
    android = sdk / 'platforms/android-34/android.jar'
    with tempfile.TemporaryDirectory(prefix='speed-feedback-', dir=output) as temporary:
        temporary = Path(temporary)
        classes, dex, smali = [temporary / part for part in ('classes', 'dex', 'smali')]
        classes.mkdir()
        dex.mkdir()
        subprocess.run(['javac', '-source', '8', '-target', '8', '-classpath', android,
                        '-d', classes, source], check=True)
        jar = temporary / 'speed-feedback.jar'
        with ZipFile(jar, 'w') as archive:
            for path in classes.rglob('*.class'):
                archive.write(path, path.relative_to(classes).as_posix())
        subprocess.run(['java', '-cp', sdk / 'build-tools/34.0.0/lib/d8.jar',
                        'com.android.tools.r8.D8', '--lib', android, '--min-api', '24',
                        '--output', dex, jar], check=True)
        subprocess.run([*repair, 'decode', dex / 'classes.dex', smali], check=True)
        generated = {path.name: path.read_text(encoding='utf8') for path in
                     (smali / 'com/popcap/pvz2cthd').glob('SpeedFeedback*.smali')}
        if 'SpeedFeedback.smali' not in generated or len(generated) < 2:
            raise ValueError('Speed feedback class or animation callbacks missing')
        return generated


def prepare_java(apk, output, sdk):
    # classes3..7 contain resource payloads. Executable framework is in the
    # small original/main and bootstrap/extension DEX files.
    names = ('classes.dex', 'classes2.dex', 'classes8.dex', 'classes9.dex',
             'classes10.dex', 'classes11.dex')
    output.mkdir(parents=True, exist_ok=True)
    apktool = ROOT / 'tools/apktool.jar'
    subprocess.run(['javac', '-cp', apktool, '-d', output, ROOT / 'scripts/RepairDex.java'], check=True)
    repair = ['java', '-Xmx512m', '-cp', str(apktool) + os.pathsep + str(output), 'RepairDex']
    speed_feedback = compile_speed_feedback(sdk, output, repair)
    speed_owners = 0
    contracts, replacements = {}, {}
    with ZipFile(apk) as source:
        for name in names:
            if name not in source.namelist():
                continue
            data = source.read(name)
            folder = output / name.replace('.', '-')
            original = output / name
            marker = folder / '.source-sha256'
            digest = hashlib.sha256(data).hexdigest()
            if not marker.exists() or marker.read_text() != digest:
                if folder.exists():
                    # Fixed work directory, checked before recursive deletion.
                    resolved = folder.resolve()
                    if not resolved.is_relative_to(output.resolve()):
                        raise ValueError('Decoded DEX outside output directory')
                    shutil.rmtree(resolved)
                original.write_bytes(data)
                subprocess.run([*repair, 'decode', original, folder], check=True)
                marker.write_text(digest)
            changed = False
            speed = folder / 'com/popcap/pvz2cthd/SpeedFeedback.smali'
            if speed.exists():
                speed_owners += 1
                # Remove only this standalone effect's former generated classes.
                for path in speed.parent.glob('SpeedFeedback*.smali'):
                    path.unlink()
                for filename, content in speed_feedback.items():
                    speed.with_name(filename).write_text(content, encoding='utf8')
                changed = True
            for path in folder.rglob('*.smali'):
                text = path.read_text(encoding='utf8')
                # Package-private classes have no access modifier after .class.
                # TWPurchase registers its natives lazily during surface setup.
                match = re.search(r'^\.class (?:.* )?L([^;]+);$', text, re.M)
                if not match or not match[1].startswith('com/popcap/'):
                    continue
                owner = match[1]
                methods = []
                for line in re.findall(r'^\.method .+$', text, re.M):
                    if ' native ' not in line:
                        continue
                    declaration = line.rsplit(' ', 1)[-1]
                    method, signature = declaration.split('(', 1)
                    methods.append((method, '(' + signature, ' static ' in line))
                if methods:
                    if owner in contracts:
                        raise ValueError('Duplicate class in executable DEX: ' + owner)
                    contracts[owner] = methods
                # The ARM64 host loads the A32 guests itself. Repeated load of
                # Src is idempotent; Android must not load an A32 helper natively.
                edited = re.sub(r'(const-string(?:/jumbo)? \w+, )"(?:czProject|HookPVZ2|Restart|PresetEditor|AsterRgbaPilot)"',
                                r'\1"Src"', text)
                if owner == 'com/popcap/SexyAppFramework/SexyAppFrameworkActivity':
                    edited, count = re.subn(r'(?<=    )invoke-direct \{p0\}, Lcom/popcap/SexyAppFramework/SexyAppFrameworkActivity;->NeedLoadCacheLib\(\)Z\s+move-result v0',
                                           'const/4 v0, 0x1', edited)
                    already = re.search(r'\.line 191\s+const/4 v0, 0x1\s+if-nez v0,', edited)
                    if count != 1 and not (count == 0 and already):
                        raise ValueError('Unknown native-library loading gate')
                if owner == 'com/popcap/purchase/TW/TWPurchase':
                    # Aster's purchases are local/offline. Do not start the
                    # retired carrier billing SDK, whose own Java worker tries
                    # to load an unrelated ARM32 payment library via ART.
                    edited, count = re.subn(
                        r'(?ms)^\.method public InitializeSDK\(Ljava/lang/String;\)V\n.*?^\.end method',
                        '.method public InitializeSDK(Ljava/lang/String;)V\n'
                        '    .registers 4\n'
                        '    const-string v0, "AsterArm64"\n'
                        '    const-string v1, "Legacy network billing SDK init skipped for offline ARM64 runtime"\n'
                        '    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I\n'
                        '    return-void\n'
                        '.end method', edited)
                    if count != 1:
                        raise ValueError('Unknown legacy billing initialization method')
                if owner == 'com/popcap/SexyAppFramework/AndroidSurfaceView':
                    edited = adapt_desktop_focus(edited)
                    changed = True
                if edited != text:
                    path.write_text(edited, encoding='utf8')
                # A cached decoded tree already contains the edits on rebuild.
                if edited != text or '"Src"' in edited and 'loadLibrary(' in edited:
                    changed = True
            if changed:
                rebuilt = output / ('adapted-' + name)
                subprocess.run([*repair, 'encode', folder, rebuilt], check=True)
                replacements[name] = rebuilt
    if speed_owners != 1:
        raise ValueError('Expected one speed feedback class in executable DEX')
    ordered = sorted(contracts.items(), key=lambda item: (item[0] != 'com/popcap/SexyAppFramework/AndroidGameApp', item[0]))
    if not ordered or len(ordered[0][1]) < 10:
        raise ValueError('Aster game JNI contract missing')
    output.joinpath('aster_jni_contract.inc').write_text(contract_source(ordered), encoding='utf8')
    output.joinpath('jni-contracts.json').write_text(json.dumps(dict(ordered), ensure_ascii=False, indent=2), encoding='utf8')
    print(f'Generated {sum(len(m) for _,m in ordered)} JNI wrappers in {len(ordered)} classes', flush=True)
    return replacements


def build(apk, bridge, sdk, ndk, output, astc_source, diagnostics=False):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    replacements = prepare_java(apk, output / 'java', sdk)
    cmake = sdk / 'cmake/3.22.1/bin/cmake.exe'
    tools = sdk / 'build-tools/34.0.0'
    native = output / 'native'
    subprocess.run([cmake, '-S', ROOT / 'src/arm64-probe', '-B', native, '-G', 'Ninja',
        f'-DCMAKE_MAKE_PROGRAM={cmake.with_name("ninja.exe")}',
        f'-DCMAKE_TOOLCHAIN_FILE={ndk / "build/cmake/android.toolchain.cmake"}',
        f'-DA7_BRIDGE_SOURCE={bridge.resolve().as_posix()}',
        '-DASTER_INCLUDE_COMPANIONS=ON', '-DASTER_GAME_RUNTIME=ON',
        f'-DASTER_RUNTIME_DIAGNOSTICS={"ON" if diagnostics else "OFF"}',
        f'-DASPHALT7_FINAL_SILENT={"OFF" if diagnostics else "ON"}',
        '-DASPHALT7_FAILURE_TELEMETRY=ON',
        f'-DASTER_CONTRACT_DIR={(output / "java").as_posix()}',
        f'-DASTER_ASTC_SOURCE={astc_source.resolve().as_posix()}',
        '-DANDROID_ABI=arm64-v8a', '-DANDROID_PLATFORM=android-24',
        '-DANDROID_STL=c++_static', '-DCMAKE_BUILD_TYPE=Release'], check=True)
    subprocess.run([cmake, '--build', native, '--parallel', '6'], check=True)
    stripped = native / 'libSrc-stripped.so'
    strip = ndk / 'toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-strip.exe'
    subprocess.run([strip, '--strip-debug', '-o', stripped, native / 'a7/libSrc.so'], check=True)
    unsigned, aligned, signed = [output / name for name in
        ('unsigned.apk', 'aligned.apk', 'PvZ2-Unline-Aster-ARM64-experimental.apk')]
    with ZipFile(apk) as source, ZipFile(unsigned, 'w') as package:
        for info in source.infolist():
            if info.filename.startswith('lib/') or re.fullmatch(r'META-INF/(MANIFEST\.MF|[^/]+\.(SF|RSA|DSA|EC))', info.filename, re.I):
                continue
            if info.filename in replacements:
                package.writestr(info, replacements[info.filename].read_bytes())
            else:
                copy_compressed_entry(source, info, package)
        package.write(stripped, 'lib/arm64-v8a/libSrc.so', compress_type=ZIP_STORED)
        for guest in GUESTS:
            with source.open(f'lib/armeabi/lib{guest}.so') as stream:
                with package.open(f'assets/guest_libs/lib{guest}_a32.so', 'w') as target:
                    shutil.copyfileobj(stream, target, 1024 * 1024)
        package.write(astc_source / 'LICENSE', 'assets/bridge/google-astc-codec-LICENSE', compress_type=ZIP_STORED)
    subprocess.run([tools / 'zipalign.exe', '-p', '-f', '4', unsigned, aligned], check=True)
    signer = ['java', '-jar', tools / 'lib/apksigner.jar']
    subprocess.run([*signer, 'sign', '--ks', ROOT / 'work/keys/recovered-debug.keystore',
        '--ks-pass', 'pass:android', '--ks-key-alias', 'androiddebugkey', '--out', signed, aligned], check=True)
    subprocess.run([*signer, 'verify', signed], check=True)
    badging = subprocess.check_output([tools / 'aapt.exe', 'dump', 'badging', signed]).decode()
    if "package: name='com.pvz2unline.aster'" not in badging or "native-code: 'arm64-v8a'" not in badging:
        raise ValueError('Unexpected application ID or ABI')
    print(signed, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('apk', 'bridge', 'sdk', 'ndk', 'output'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--astc-source', type=Path, required=True, help='Checkout of google/astc-codec')
    parser.add_argument('--diagnostics', action='store_true', help='Enable slow cycle/call/animation diagnostics (off by default)')
    build(**vars(parser.parse_args()))
