"""Build an isolated ARM64 Android diagnostic using the Asphalt 7 bridge."""
import argparse
from pathlib import Path
import shutil
import subprocess
from zipfile import ZIP_STORED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/arm64-probe'


def build(apk, bridge, sdk, ndk, output, with_companions=False, initialize_companions=False):
    if initialize_companions and not with_companions:
        raise ValueError('--initialize-companions requires --with-companions')
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cmake = sdk / 'cmake/3.22.1/bin/cmake.exe'
    ninja = cmake.with_name('ninja.exe')
    tools = sdk / 'build-tools/34.0.0'
    android = sdk / 'platforms/android-34/android.jar'
    build_dir = output / 'native'
    run = lambda *args: subprocess.run(args, check=True)
    run(cmake, '-S', SOURCE, '-B', build_dir, '-G', 'Ninja',
        f'-DCMAKE_MAKE_PROGRAM={ninja}',
        f'-DCMAKE_TOOLCHAIN_FILE={ndk / "build/cmake/android.toolchain.cmake"}',
        f'-DA7_BRIDGE_SOURCE={bridge.resolve().as_posix()}',
        f'-DASTER_INCLUDE_COMPANIONS={"ON" if with_companions else "OFF"}',
        f'-DASTER_INITIALIZE_COMPANIONS={"ON" if initialize_companions else "OFF"}',
        '-DANDROID_ABI=arm64-v8a', '-DANDROID_PLATFORM=android-24',
        '-DANDROID_STL=c++_static', '-DCMAKE_BUILD_TYPE=Release')
    run(cmake, '--build', build_dir, '--parallel', '6')

    classes = output / 'classes'
    dex = output / 'dex'
    classes.mkdir(exist_ok=True)
    dex.mkdir(exist_ok=True)
    run('javac', '--release', '8', '-encoding', 'UTF-8',
        '-classpath', android, '-d', classes,
        *sorted(SOURCE.rglob('*.java')))
    run('java', '-cp', tools / 'lib/d8.jar', 'com.android.tools.r8.D8',
        '--min-api', '24', '--lib', android, '--output', dex,
        *sorted(classes.rglob('*.class')))
    unsigned, aligned, signed = (output / name for name in
                                 ('unsigned.apk', 'aligned.apk', 'Aster-ARM64-Probe.apk'))
    run(tools / 'aapt2.exe', 'link', '--manifest', SOURCE / 'AndroidManifest.xml',
        '-I', android, '-o', unsigned)
    with ZipFile(apk) as source, ZipFile(unsigned, 'a', compression=ZIP_STORED) as package:
        package.write(dex / 'classes.dex', 'classes.dex')
        package.write(build_dir / 'a7/libAndroid.so', 'lib/arm64-v8a/libAndroid.so')
        with source.open('lib/armeabi/libSrc.so') as guest, package.open('assets/guest_libs/libSrc_a32.so', 'w') as asset:
            shutil.copyfileobj(guest, asset)
        if with_companions:
            for name in ('czProject', 'HookPVZ2', 'Restart', 'PresetEditor', 'AsterRgbaPilot'):
                with source.open(f'lib/armeabi/lib{name}.so') as guest:
                    with package.open(f'assets/guest_libs/lib{name}_a32.so', 'w') as asset:
                        shutil.copyfileobj(guest, asset)
    run(tools / 'zipalign.exe', '-p', '-f', '4', unsigned, aligned)
    signer = ('java', '-jar', tools / 'lib/apksigner.jar')
    run(*signer, 'sign', '--ks', ROOT / 'work/keys/recovered-debug.keystore',
        '--ks-pass', 'pass:android', '--ks-key-alias', 'androiddebugkey', '--out', signed, aligned)
    run(*signer, 'verify', signed)
    run(tools / 'aapt.exe', 'dump', 'badging', signed)
    print(signed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('apk', 'bridge', 'sdk', 'ndk', 'output'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--with-companions', action='store_true',
                        help="Also audit the PVP, input, resource and preset libraries")
    parser.add_argument('--initialize-companions', action='store_true',
                        help="Run companion constructors; retain the guest until process exit for its worker threads")
    build(**vars(parser.parse_args()))
