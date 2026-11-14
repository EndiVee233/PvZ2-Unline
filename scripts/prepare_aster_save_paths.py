"""Repair v163's constant-folded PvP path lengths after application-ID rename."""
from io import BytesIO
import struct
from elftools.elf.elffile import ELFFile

OLD = b'/data/data/com.popcap.pvz2cthd.reconstruction/files/userdata/offline-pvp-'
NEW = b'/data/data/com.pvz2unline.aster/files/userdata/offline-pvp-'
ENTRIES = {'economy': 0x1a1a3b8, 'defense': 0x1a1dc18}


def patch(data):
    elf = ELFFile(BytesIO(data))
    segments = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
    def offset(address):
        matches = [s['p_offset'] + address - s['p_vaddr'] for s in segments
                   if s['p_vaddr'] <= address < s['p_vaddr'] + s['p_filesz']]
        if len(matches) != 1:
            raise ValueError('Path instruction outside a unique file-backed segment')
        return matches[0]
    if data.count(NEW + b'\0') != 1 or OLD in data:
        raise ValueError('Expected renamed Aster v163 library')
    result = bytearray(data)
    changed = []
    for name, entry in ENTRIES.items():
        # Verify that this exact ARM helper references the renamed path, not
        # merely another function that happens to contain the same immediates.
        literal = struct.unpack_from('<I', data, offset(entry + 0xbc))[0]
        pointer = (entry + 0x1c + literal) & 0xffffffff
        start = offset(pointer)
        if data[start:start + len(NEW) + 1] != NEW + b'\0':
            raise ValueError('Unexpected path helper literal: ' + name)
        instructions = {
            0x28: (0xe3530000, len(OLD), len(NEW)),  # cmp r3, prefix length
            0x34: (0xe281c000, len(OLD), len(NEW)),  # player ID begins
            0x80: (0xe281c000, len(OLD)+8, len(NEW)+8),
            0xa4: (0xe2830000, len(OLD)+8, len(NEW)+8),
            0xac: (0xe3a00000, len(OLD)+8, len(NEW)+8),
        }
        states = []
        for relative, (opcode, old, new) in instructions.items():
            at = offset(entry + relative)
            word = struct.unpack_from('<I', data, at)[0]
            if word not in (opcode | old, opcode | new):
                raise ValueError('Unknown path instruction: ' + hex(entry + relative))
            states.append(word == opcode | new)
        if any(states) and not all(states):
            raise ValueError('Partially patched path helper: ' + name)
        for relative, (opcode, old, new) in instructions.items():
            struct.pack_into('<I', result, offset(entry + relative), opcode | new)
        if not all(states):
            changed.append(name)
    return bytes(result), changed
