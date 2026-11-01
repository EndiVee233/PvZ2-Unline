"""Build the ARMv7 WSA shim with a local Android NDK and astc-codec checkout."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk', type=Path, required=True)
    parser.add_argument('--astc', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache-root', default='/data/data/com.popcap.pvz2cthd/cache')
    parser.add_argument('--prefetch-index', type=Path, help='Generated prefetch_index.inc for this resource release')
    parser.add_argument('--test', action='store_true', help='Also build the Android differential test executable')
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    toolchain = args.ndk.resolve() / 'toolchains/llvm/prebuilt/windows-x86_64/bin'
    compiler = toolchain / 'clang++.exe'
    codec = args.astc.resolve()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    # The Windows NDK driver needs an ASCII build path on some installations.
    for name in ['glshim.cpp', 'test_decode.cpp', 'decode_pool.inc']:
        shutil.copy2(source / name, args.output / name)
    if args.prefetch_index:
        shutil.copy2(args.prefetch_index,args.output/'prefetch_index.inc')
    else:
        (args.output/'prefetch_index.inc').write_text('static const PrefetchTexture kPrefetchTextures[1] = {};\nstatic const size_t kPrefetchTextureCount = 0;\n')
    names = ['astc_file', 'codec', 'endpoint_codec', 'footprint', 'integer_sequence_codec',
             'intermediate_astc_block', 'logical_astc_block', 'partition',
             'physical_astc_block', 'quantization', 'weight_infill']
    common = [str(compiler), '--target=armv7a-linux-androideabi21', '-std=c++17',
              '-O2', '-fPIC', '-mthumb', '-fno-exceptions', '-fno-rtti',
              '-I' + str(codec), '-I' + str(codec / 'include')]
    objects = []
    def emit(command, destination):
        # Pipe artifacts through Python: this Windows NDK can emit to stdout
        # even on hosts where its direct output-file open returns EACCES.
        result = subprocess.run([*command, '-o', '-'], stdout=subprocess.PIPE, check=True)
        destination.write_bytes(result.stdout)

    for name in names:
        src = codec / 'src/decoder' / (name + '.cc')
        obj = args.output / (name + '.o')
        emit([*common, '-c', str(src)], obj)
        objects.append(str(obj))
    definition = '-DPVZ2_GL_CACHE_ROOT=' + json.dumps(args.cache_root)
    link = ['-static-libstdc++', '-Wl,--no-undefined', '-llog', '-landroid', '-ldl', '-lz']
    output = args.output / 'libRestart.so'
    shim_object = args.output / 'glshim.o'
    emit([*common, definition, '-c', str(args.output / 'glshim.cpp')], shim_object)
    emit([*common, '-shared', '-Wl,-soname,libRestart.so',
          str(shim_object), *objects, *link], output)
    if args.test:
        test_object = args.output / 'test_decode.o'
        emit([*common, definition, '-c', str(args.output / 'test_decode.cpp')], test_object)
        emit([*common, str(test_object), *objects, *link], args.output / 'test_decode')
    record = {'abi': 'armeabi-v7a', 'api': 21, 'max_astc_threads': 4, 'persistent_workers': '2-4',
              'background_prefetch': bool(args.prefetch_index), 'demand_priority': True,
              'cache_root': args.cache_root,
              'ndk': (args.ndk / 'source.properties').read_text(encoding='utf-8'),
              'source_sha256': hashlib.sha256((source / 'glshim.cpp').read_bytes()).hexdigest(),
              'pool_source_sha256': hashlib.sha256((source / 'decode_pool.inc').read_bytes()).hexdigest(),
              'prefetch_index_sha256': hashlib.sha256((args.output / 'prefetch_index.inc').read_bytes()).hexdigest(),
              'library_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
              'runtime_verified': False}
    (args.output / 'build-validation.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
