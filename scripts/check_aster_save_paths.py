"""Execute the shipped ARM path helpers, including ASLR and per-player isolation."""
import argparse
from io import BytesIO
from zipfile import ZipFile
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR
from prepare_aster_save_paths import patch, ENTRIES, NEW


def paths(data, entries=None, garrison_entry=0x1a1d9e0):
    elf = ELFFile(BytesIO(data))
    results = []
    for base in (0, 0x20000000):
        machine = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        machine.mem_map(base + 0x1000, 0x3000000)
        machine.mem_map(0x6000000, 0x20000)
        for segment in elf.iter_segments():
            if segment['p_type'] == 'PT_LOAD':
                skip = max(0, 4096 - segment['p_vaddr'])
                machine.mem_write(base + segment['p_vaddr'] + skip, segment.data()[skip:])
        for kind, entry in (entries or ENTRIES).items():
            for user in (0, 1, 99, 0xffffffff):
                for temporary in (False, True):
                    machine.mem_write(0x6000000, b'\xcc' * 160)
                    for reg, value in ((UC_ARM_REG_R0,user),(UC_ARM_REG_R1,0x6000000),
                                       (UC_ARM_REG_R2,int(temporary)),(UC_ARM_REG_SP,0x6010000),
                                       (UC_ARM_REG_LR,0x6020000)):
                        machine.reg_write(reg,value)
                    machine.emu_start(base + entry, 0x6020000, count=10000)
                    actual = bytes(machine.mem_read(0x6000000,160)).split(b'\0',1)[0]
                    extension = b'.eco' if kind == 'economy' else b'.def'
                    expected = NEW + f'{user:08x}'.encode() + extension + (b'.tmp' if temporary else b'')
                    results.append((actual,expected))
        for user in (0,1,99,0xffffffff):
            for target in (1001,1002):
                for temporary in (False,True):
                    machine.mem_write(0x6000000,b'\xcc'*160)
                    for reg,value in ((UC_ARM_REG_R0,user),(UC_ARM_REG_R1,target),
                                      (UC_ARM_REG_R2,0x6000000),(UC_ARM_REG_R3,int(temporary)),
                                      (UC_ARM_REG_SP,0x6010000),(UC_ARM_REG_LR,0x6020000)):
                        machine.reg_write(reg,value)
                    machine.emu_start(base+garrison_entry,0x6020000,count=10000)
                    actual=bytes(machine.mem_read(0x6000000,160)).split(b'\0',1)[0]
                    expected=NEW+f'{user:08x}-shop-{target:08x}.def'.encode()+(b'.tmp' if temporary else b'')
                    results.append((actual,expected))
    return results


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk',type=Path)
    args=parser.parse_args()
    with ZipFile(args.apk) as archive:
        original=archive.read('lib/armeabi/libSrc.so')
    before=paths(original)
    repaired,changed=patch(original)
    after=paths(repaired)
    assert all(actual==expected for actual,expected in after)
    assert len(set(actual for actual,_ in after))==32
    assert patch(repaired)==(repaired,[])
    print('Original failing paths:',sum(a!=e for a,e in before),'of',len(before))
    print('Fixed paths passed:',len(after),'; corrected helpers:',changed)
