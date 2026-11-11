"""Inject bounded last-player persistence into the shared Aster ARM32 engine."""
from io import BytesIO
from pathlib import Path
import hashlib
import json
import struct
import subprocess

from elftools.elf.elffile import ELFFile
from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM

ROOT = Path(__file__).resolve().parents[1]


def branch(site, target, link=False):
    delta = target - site - 8
    if delta % 4 or not -0x2000000 <= delta < 0x2000000:
        raise ValueError('ARM branch out of range')
    return struct.pack('<I', (0xeb000000 if link else 0xea000000) | ((delta // 4) & 0xffffff))


def patch(native, ndk, output):
    output.mkdir(parents=True, exist_ok=True)
    source_hash = hashlib.sha256(native).hexdigest()
    if source_hash != '7f9c297e3fa973fa9940fb4e0ea75621c0424fa77325457f6aa036226fb2a690':
        raise ValueError('Unexpected Aster engine baseline')
    elf = ELFFile(BytesIO(native))
    loads = [(i, s) for i, s in enumerate(elf.iter_segments()) if s['p_type'] == 'PT_LOAD']
    (index, code), (_, following) = loads[-2:]
    if code['p_flags'] != 5 or code['p_filesz'] != code['p_memsz']:
        raise ValueError('Expected final RX segment followed by RW segment')
    padding = -code['p_filesz'] % 16
    used = code['p_filesz'] + padding
    address, offset = code['p_vaddr'] + used, code['p_offset'] + used
    helper_address = address + 256
    toolchain = ndk / 'toolchains/llvm/prebuilt/windows-x86_64/bin'
    object_file, linked = output / 'selection.o', output / 'selection.elf'
    subprocess.run([toolchain / 'clang++.exe', '--target=armv7a-linux-androideabi24',
                    '-marm', '-march=armv7-a', '-mfloat-abi=softfp', '-Os', '-fPIC',
                    '-fno-exceptions', '-fno-rtti', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
                    '-fno-stack-protector', '-ffreestanding', '-c',
                    ROOT / 'src/profile-memory/selection.cpp', '-o', object_file], check=True)
    linker = output / 'selection.ld'
    linker.write_text(f'SECTIONS {{ . = {helper_address}; .payload : {{ *(.text*) *(.rodata*) }} '
                      '/DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }')
    subprocess.run([toolchain / 'ld.lld.exe', '-T', linker, '--no-undefined',
                    '--entry=rememberPlayer', object_file, '-o', linked], check=True)
    with linked.open('rb') as stream:
        helper = ELFFile(stream)
        payload = helper.get_section_by_name('.payload').data()
        symbols = {s.name: s['st_value'] for s in helper.get_section_by_name('.symtab').iter_symbols()}
    assembler = Ks(KS_ARCH_ARM, KS_MODE_ARM)
    save = bytes(assembler.asm(f'''
    save_entry:
        push {{r0-r3, r4, lr}}
        mov r1, r5
        adr r0, save_entry
        ldr r2, save_offset
        sub r0, r0, r2
        bl #{symbols['rememberPlayer']}
        pop {{r0-r3, r4, lr}}
        b #0x7aaa28
    save_offset: .word {address}
    ''', address)[0])
    restore_address = address + 128
    restore = bytes(assembler.asm(f'''
    restore_entry:
        push {{r0, r4, r5, lr}}
        mov r1, r0
        adr r0, restore_entry
        ldr r2, restore_offset
        sub r0, r0, r2
        bl #{symbols['restorePlayer']}
        mov r1, r0
        pop {{r0, r4, r5, lr}}
        cmp r1, #0
        beq original_first
        mov r0, #1
        bx lr
    original_first:
        push {{r4, r5, r6, r7, fp, lr}}
        b #0x7aaa78
    restore_offset: .word {restore_address}
    ''', restore_address)[0])
    assert len(save) <= 128 and len(restore) <= 128
    injected = save.ljust(128, b'\0') + restore.ljust(128, b'\0') + payload
    if offset + len(injected) > following['p_offset'] or address + len(injected) > following['p_vaddr']:
        raise ValueError('Insufficient verified RX padding')
    if any(native[code['p_offset'] + code['p_filesz']:offset + len(injected)]):
        raise ValueError('Injection would overwrite existing data')
    data = bytearray(native)
    if data[0x7aaa70:0x7aaa74] != branch(0x7aaa70, 0x7aaa28):
        raise ValueError('Unknown successful profile-selection tail')
    if data[0x7aaa74:0x7aaa78] != bytes.fromhex('f0482de9'):
        raise ValueError('Unknown select-first prologue')
    data[offset:offset + len(injected)] = injected
    data[0x7aaa70:0x7aaa74] = branch(0x7aaa70, address)
    data[0x7aaa74:0x7aaa78] = branch(0x7aaa74, restore_address)
    phdr = elf['e_phoff'] + index * elf['e_phentsize']
    struct.pack_into('<II', data, phdr + 16, used + len(injected), used + len(injected))
    target = output / 'libSrc-profile-memory.so'
    target.write_bytes(data)
    report = {'source_sha256': source_hash, 'patched_sha256': hashlib.sha256(data).hexdigest(),
              'injection_address': address, 'injection_size': len(injected),
              'save_trampoline': address, 'restore_trampoline': restore_address,
              'remember_function': symbols['rememberPlayer'], 'restore_function': symbols['restorePlayer'],
              'engine_hooks': [0x7aaa70, 0x7aaa74], 'runtime_verified': False}
    (output / 'profile-memory-validation.json').write_text(json.dumps(report, indent=2))
    print('Profile-memory payload bytes:', len(injected), flush=True)
    return target, report
