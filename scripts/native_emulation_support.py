"""Map the original ARM ELF with relocations for small bounded recovery checks."""
from pathlib import Path
import os,sys,struct
base=Path(__file__).resolve().parents[1];sys.path.insert(0,str(base/'tools/python_libs'))
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM
from elftools.elf.elffile import ELFFile

def machine():
    path=Path(os.environ.get('PVZ2_NATIVE_ORIGINAL',base/'raw/lib/armeabi/libSrc.so'));blob=path.read_bytes()
    with path.open('rb') as fp:
        elf=ELFFile(fp);segments=[dict(s.header) for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
        symbols=[dict(s.entry,name=s.name) for s in elf.get_section_by_name('.dynsym').iter_symbols()]
        relocs=[dict(r.entry) for section in elf.iter_sections() if section['sh_type']=='SHT_REL' for r in section.iter_relocations()]
    uc=Uc(UC_ARCH_ARM,UC_MODE_ARM);lo=min(s['p_vaddr']+0x10000 for s in segments)&~4095
    hi=(max(s['p_vaddr']+0x10000+s['p_memsz'] for s in segments)+4095)&~4095;uc.mem_map(lo,hi-lo)
    for seg in segments:uc.mem_write(seg['p_vaddr']+0x10000,blob[seg['p_offset']:seg['p_offset']+seg['p_filesz']])
    external=0x7000000;uc.mem_map(external,0x10000);imports={}
    for r in relocs:
        address=r['r_offset']+0x10000;kind=r['r_info_type']
        if kind==23:
            value=struct.unpack('<I',uc.mem_read(address,4))[0];uc.mem_write(address,struct.pack('<I',(value+0x10000)&0xffffffff))
        elif kind in (2,21,22):
            symbol=symbols[r['r_info_sym']]
            if symbol['st_shndx']=='SHN_UNDEF':
                target=external+r['r_info_sym']*4;imports[target]=symbol['name'];uc.mem_write(target,bytes.fromhex('1eff2fe1'))
            else:target=symbol['st_value']+0x10000
            if kind==2:target+=struct.unpack('<I',uc.mem_read(address,4))[0]
            uc.mem_write(address,struct.pack('<I',target&0xffffffff))
    for address,size in [(0x4000000,0x100000),(0x5000000,0x1000),(0x6000000,0x20000)]:uc.mem_map(address,size)
    return uc,imports
