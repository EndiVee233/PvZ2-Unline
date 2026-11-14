"""Bind the JNI bridge to this exact engine, rather than a prior build's offsets."""
from pathlib import Path
from io import BytesIO
import argparse,hashlib,json,subprocess
from elftools.elf.elffile import ELFFile

ROOT=Path(__file__).resolve().parents[1]
TARGETS=dict(EDITOR_COMMAND='offlinePresetCommand',EDITOR_POLL='offlinePresetPoll',EDITOR_MUSIC_SAMPLE='offlinePvpMusicSample')


def build(code,output,sdk):
    output.mkdir(parents=True,exist_ok=True)
    native=(code/'libSrc.so').read_bytes()
    with (code/'offline.elf').open('rb') as f:
        elf=ELFFile(f);symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
        payload=elf.get_section_by_name('.payload');address=payload['sh_addr'];data=payload.data()
    engine=ELFFile(BytesIO(native))
    segment=next(s for s in engine.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address and address+len(data)<=s['p_vaddr']+s['p_filesz'])
    at=segment['p_offset']+address-segment['p_vaddr']
    if native[at:at+len(data)]!=data:raise ValueError('Symbol ELF does not describe this engine payload')
    targets={key:symbols[name] for key,name in TARGETS.items()}
    if any(not address<=p<address+len(data) for p in targets.values()):raise ValueError('JNI target outside engine payload')
    (output/'preset_bridge_addresses.h').write_text(''.join(f'#define {k} {v}\n' for k,v in targets.items()))
    clang=sdk/'ndk/27.0.12077973/toolchains/llvm/prebuilt/windows-x86_64/bin/clang++.exe'
    result=output/'libPresetEditor.so'
    subprocess.run([clang,'--target=armv7a-linux-androideabi21','-marm','-Os','-shared','-fPIC',
                    '-fno-exceptions','-fno-rtti','-nostdlib++','-Wl,--no-undefined','-Wl,-soname,libPresetEditor.so',
                    '-I'+str(output),ROOT/'src/preset-editor/bridge.cpp','-ldl','-o',result],check=True)
    from check_aster_preset_bridge import verify
    cases=verify(native,result.read_bytes(),targets)
    report=dict(native_sha256=hashlib.sha256(native).hexdigest(),bridge_sha256=hashlib.sha256(result.read_bytes()).hexdigest(),targets=targets,arm_jni_cases_passed=cases,runtime_verified=False)
    (output/'bridge-binding.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('code','output','sdk'):p.add_argument(name,type=Path)
    build(**vars(p.parse_args()))
