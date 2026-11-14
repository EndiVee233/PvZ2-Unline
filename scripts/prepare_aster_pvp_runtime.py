"""Bounded v166 fixes: optional skill preview and defense music selection."""
from io import BytesIO
from pathlib import Path
import hashlib
import json
import struct
import subprocess

from elftools.elf.elffile import ELFFile
from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM
from prepare_profile_memory import branch

ROOT=Path(__file__).resolve().parents[1]
PREVIEW_SITE=0x1082ae4
MUSIC_SITE=0x1a120c0


def file_offset(elf,address,size=4):
    for s in elf.iter_segments():
        if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address and address+size<=s['p_vaddr']+s['p_filesz']:
            return s['p_offset']+address-s['p_vaddr']
    raise ValueError(f'Unmapped code address {address:x}')


def patch(native,ndk,output,refresh_research=False):
    output.mkdir(parents=True,exist_ok=True)
    elf=ELFFile(BytesIO(native))
    preview=file_offset(elf,PREVIEW_SITE)
    music=file_offset(elf,MUSIC_SITE)
    if native[preview:preview+4]!=branch(PREVIEW_SITE,0x11699c4,True):
        raise ValueError('Unknown skill preview draw call')
    if native[music:music+12]!=bytes.fromhex('00482de90db0a0e10010a0e1'):
        raise ValueError('Unknown music selector prologue')
    loads=[(i,s) for i,s in enumerate(elf.iter_segments()) if s['p_type']=='PT_LOAD']
    (index,code),(_,following)=loads[-2:]
    if code['p_flags']!=5 or code['p_filesz']!=code['p_memsz']:
        raise ValueError('Expected final RX segment')
    used=(code['p_filesz']+15)&~15
    address=code['p_vaddr']+used
    offset=code['p_offset']+used
    # r1 is the optional PopAnim resource. The card has already drawn its
    # ordinary image. Never call Graphics::DrawPopAnim with null, but return
    # normally so the caller still executes Graphics::PopState at 0x1082aec.
    # This guard affects this one laboratory draw call, not gameplay effects.
    guard=bytes(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(
        'cmp r1,#0\nbxeq lr\nb #0x11699c4',address)[0])
    helper_address=address+32
    toolchain=ndk/'toolchains/llvm/prebuilt/windows-x86_64/bin'
    obj=output/'pvp-runtime.o';linked=output/'pvp-runtime.elf'
    subprocess.run([toolchain/'clang++.exe','--target=armv7a-linux-androideabi24',
                    '-marm','-Os','-fPIC','-ffreestanding','-fno-builtin',
                    '-fno-exceptions','-fno-rtti','-fno-unwind-tables',
                    '-fno-asynchronous-unwind-tables','-fno-stack-protector',
                    '-c',ROOT/'src/pvp-runtime-fixes/fixes.cpp','-o',obj],check=True)
    with obj.open('rb') as stream:
        object_elf=ELFFile(stream)
        for sec in object_elf.iter_sections():
            if sec['sh_type']=='SHT_REL' and 'exidx' not in sec.name:
                if any(r['r_info_type']==2 for r in sec.iter_relocations()):
                    raise ValueError('Absolute relocation in ASLR payload')
    linker=output/'pvp-runtime.ld'
    linker.write_text(f'SECTIONS {{ . = {helper_address}; .payload : {{ *(.text*) *(.rodata*) }} '
                      '/DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }')
    subprocess.run([toolchain/'ld.lld.exe','-T',linker,'--no-undefined',
                    '--entry=asterPvpMusicTrack',obj,'-o',linked],check=True)
    with linked.open('rb') as stream:
        helper=ELFFile(stream)
        payload=helper.get_section_by_name('.payload').data()
        symbols={s.name:s['st_value'] for s in helper.get_section_by_name('.symtab').iter_symbols()}
    injected=guard.ljust(32,b'\0')+payload
    research_report={}
    if refresh_research:
        site=0x1083d88
        def destination(at,link):
            word=struct.unpack_from('<I',native,file_offset(elf,at))[0]
            if word>>24!=(0xeb if link else 0xea):raise ValueError('Unknown research branch')
            displacement=word&0xffffff
            if displacement&0x800000:displacement-=0x1000000
            return at+8+displacement*4
        old_stub=destination(site,False)
        stub_at=file_offset(elf,old_stub,40)
        if native[stub_at:stub_at+8]!=bytes.fromhex('1f402de90010a0e1'):
            raise ValueError('Unknown research update trampoline')
        old_tick=destination(old_stub+20,True)
        if old_tick!=0x1a0fa10:raise ValueError('Unexpected original research tick')
        # Preserve the original hook's arguments and displaced prologue. The
        # existing tick settles/commits first; then update only UI card copies.
        wrapper_address=address+((len(injected)+15)&~15)
        source=f'''push {{r0-r4,lr}}
mov r4,r0
mov r1,r0
adr r0,basepoint
ldr ip,[r0]
sub r0,r0,ip
bl #{old_tick}
mov r1,r4
adr r0,basepoint
ldr ip,[r0]
sub r0,r0,ip
bl #{symbols['asterResearchCardRefresh']}
pop {{r0-r4,lr}}
.word 0xe92d4ff0
b #{site+4}
basepoint: .word 0x11223344'''
        wrapper=bytearray(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(source,wrapper_address)[0])
        literal=wrapper.index(struct.pack('<I',0x11223344))
        struct.pack_into('<I',wrapper,literal,wrapper_address+literal)
        injected=injected.ljust(wrapper_address-address,b'\0')+wrapper
        research_report=dict(research_hook=site,research_old_tick=old_tick,
                             research_wrapper=wrapper_address,research_helper=symbols['asterResearchCardRefresh'])
    if offset+len(injected)>following['p_offset'] or address+len(injected)>following['p_vaddr']:
        raise ValueError('Insufficient RX padding')
    if any(native[code['p_offset']+code['p_filesz']:offset+len(injected)]):
        raise ValueError('RX padding is not empty')
    result=bytearray(native)
    result[offset:offset+len(injected)]=injected
    result[preview:preview+4]=branch(PREVIEW_SITE,address,True)
    result[music:music+4]=branch(MUSIC_SITE,symbols['asterPvpMusicTrack'])
    if refresh_research:
        at=file_offset(elf,research_report['research_hook'])
        result[at:at+4]=branch(research_report['research_hook'],research_report['research_wrapper'])
    phdr=elf['e_phoff']+index*elf['e_phentsize']
    struct.pack_into('<II',result,phdr+16,used+len(injected),used+len(injected))
    report=dict(source_sha256=hashlib.sha256(native).hexdigest(),
                patched_sha256=hashlib.sha256(result).hexdigest(),
                preview_guard=address,music_helper=symbols['asterPvpMusicTrack'],
                injection_address=address,injection_size=len(injected),
                runtime_accepted=False,**research_report)
    (output/'pvp-runtime-patch.json').write_text(json.dumps(report,indent=2)+'\n')
    return bytes(result),report
