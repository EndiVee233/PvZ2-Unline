"""Package the baked Aster bundles and migrate existing installations on launch."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import zipfile
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from bake_rgba_resources import OVERLAYS
from index_texture_prefetch import ResourceZip
from rebuild_bootstrap_dex import rebuild_bootstrap


ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'com.popcap.pvz2cthd/files/'
PARTS = [f'assets/pvz2data.zip.{i:03d}' for i in range(1, 4)]


def pack_resources(source, baked, archive):
    with ZipFile(ResourceZip(source)) as original, ZipFile(archive, 'w', ZIP_DEFLATED, compresslevel=1) as output:
        for item in original.infolist():
            if not item.filename.startswith(PREFIX) or item.is_dir():
                continue
            if item.filename.endswith('.rsb.smf'):
                bundle = baked / Path(item.filename).name
                if not bundle.is_file() or not bundle.stat().st_size:
                    raise ValueError(f'Missing converted bundle: {bundle}')
                output.write(bundle, item.filename)
            else:
                output.writestr(item.filename, original.read(item))


def bootstrap(original, out, expanded, marker):
    # The existing worker and progress UI still drive extraction. The old
    # fallback for an already populated directory must require the new marker.
    old_check = '''    if-nez v1, :cond_50

    new-instance v1, Ljava/io/File;

    const-string v2, "init.rsb.smf"

    invoke-direct {v1, v0, v2}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    invoke-virtual {v1}, Ljava/io/File;->exists()Z

    move-result v1

    if-eqz v1, :cond_34

    new-instance v1, Ljava/io/File;

    const-string v2, "dynamic.rsb.smf"

    invoke-direct {v1, v0, v2}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    invoke-virtual {v1}, Ljava/io/File;->exists()Z

    move-result v1

    if-nez v1, :cond_50'''
    identity = '''    invoke-direct {v6, p1, v5}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    .line 224'''
    preserve_identity = identity.replace('    .line 224', '''    const-string v7, "sdcardid.dat"
    invoke-virtual {v7, v5}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v7
    if-eqz v7, :rgba_write_entry
    invoke-virtual {v6}, Ljava/io/File;->exists()Z
    move-result v7
    if-nez v7, :goto_21
    :rgba_write_entry

    .line 224''')
    # Both overlays are already merged into the archive. Skip the previous
    # resource-replacement and optional prebuilt-cache import on startup.
    cache_start = '.method private startGameWithCache()V\n    .registers 5'
    no_cache = cache_start + '\n\n    invoke-direct {p0}, Lcom/popcap/pvz2cthd/BootActivity;->startGame()V\n    return-void\n'
    return rebuild_bootstrap(original, out, {
        '".pvz2_extracted"': f'"{marker}"',
        old_check: '    if-nez v1, :cond_50',
        identity: preserve_identity,
        cache_start: no_cache,
        '0xa3aca280L': f'{hex(expanded)}L',
        '2.6 GB': f'{expanded / 1e9:.1f} GB',
    }, ROOT / 'tools/apktool.jar')


def package(source, baked, out, tools, reuse_archive):
    out.mkdir(parents=True, exist_ok=True)
    inner = out / 'resources.zip'
    if not reuse_archive:
        pack_resources(source, baked, inner)
    with ZipFile(inner) as archive:
        expanded = sum(item.file_size for item in archive.infolist())
        if reuse_archive and archive.testzip() is not None:
            raise ValueError('Invalid saved resource archive')
    with inner.open('rb') as stream:
        marker = '.pvz2_rgba_' + hashlib.file_digest(stream, 'sha256').hexdigest()[:20]
    print(f'Resource archive: {inner.stat().st_size:,} bytes; unpacked: {expanded:,} bytes', flush=True)
    unsigned, aligned, final = (out / name for name in (
        'unsigned.apk', 'aligned.apk', source.stem + '-rgba-all.apk'))
    excluded = set(PARTS) | set(OVERLAYS.values()) | {'classes8.dex'}
    with ZipFile(source) as original:
        remaining = sum(i.compress_size for i in original.infolist() if i.filename not in excluded)
        if inner.stat().st_size + remaining >= 0xffff0000:
            raise ValueError('The baked assets exceed the single APK ZIP32 limit')
        boot = bootstrap(original.read('classes8.dex'), out / 'boot', expanded, marker)
        # APKs use unsigned 32-bit ZIP offsets. Python switches to ZIP64 at
        # the signed 32-bit boundary by default; Android requires classic ZIP.
        zipfile.ZIP64_LIMIT = 0xffffffff
        with ZipFile(unsigned, 'w', allowZip64=False) as apk:
            for item in original.infolist():
                if item.filename in excluded or item.filename.startswith('META-INF/'):
                    continue
                with original.open(item) as src, apk.open(item, 'w') as dst:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
            apk.writestr('classes8.dex', boot, ZIP_DEFLATED)
            size = (inner.stat().st_size + len(PARTS) - 1) // len(PARTS)
            with inner.open('rb') as stream:
                for name in PARTS:
                    part = out / Path(name).name
                    with part.open('wb') as dst:
                        left = size
                        while left and (chunk := stream.read(min(left, 1024 * 1024))):
                            dst.write(chunk)
                            left -= len(chunk)
                    apk.write(part, name, ZIP_STORED)
                    part.unlink()
    subprocess.run([tools / 'zipalign.exe', '-f', '4', unsigned, aligned], check=True)
    unsigned.unlink()
    signer = ['java', '-jar', tools / 'lib/apksigner.jar']
    subprocess.run([*signer, 'sign', '--ks', ROOT / 'work/keys/recovered-debug.keystore',
                    '--ks-pass', 'pass:android', '--key-pass', 'pass:android',
                    '--ks-key-alias', 'androiddebugkey', '--out', final, aligned], check=True)
    subprocess.run([*signer, 'verify', final], check=True)
    subprocess.run([tools / 'zipalign.exe', '-c', '4', final], check=True)
    aligned.unlink()
    print(f'APK: {final} ({final.stat().st_size:,} bytes)', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk', type=Path)
    parser.add_argument('baked', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--build-tools', type=Path, default=Path('Y:/Android/Sdk/build-tools/34.0.0'))
    parser.add_argument('--reuse-archive', action='store_true')
    args = parser.parse_args()
    package(args.apk, args.baked, args.output, args.build_tools, args.reuse_archive)
