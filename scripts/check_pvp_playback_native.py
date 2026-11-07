"""Recover the original replay schema and exercise its real ARM frame dispatcher.

This does not launch Android, read player files, or calculate a battle outcome.
Only the leaf action callback is controlled: spawning zombies and resolving
skills require a live Board and are deliberately outside these assertions.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--library', type=Path, default=ROOT/'work/libSrc_orig.so')
parser.add_argument('--output', type=Path, default=ROOT/'work/pvp-v98/playback-native-check.json')
args = parser.parse_args()
os.environ['PVZ2_NATIVE_ORIGINAL'] = str(args.library.resolve())

from reflection_emulation_support import h, seed
from unicorn import UC_HOOK_CODE

seed()
registry = h.call(0x11b10ec, [])
classes = [('PFrame', 0x1043c04), ('PlaybackData', 0x10440d8)]
# Register all dependencies before draining the original schema queue once.
metas = [h.call(getter, []) for _, getter in classes]
h.call(0x11b15b4, [registry])
schemas = {}
for (name, _), meta in zip(classes, metas):
    schema = h.words(meta+0x24)[0]
    begin, end = h.words(schema+0x134, 2)
    schemas[name] = {
        h.narrow(h.words(field+0x38)[0]).decode(): h.words(field+0x48)[0]
        for field in h.words(begin, (end-begin)//4)
    }
assert schemas == {
    'PFrame': {'i': 4, 'ts': 8},
    'PlaybackData': {'n': 16, 'fs': 4, 'ppd': 32, 'di': 72,
                     'zd': 92, 'sd': 104, 'zr': 116},
}

# Constructors and virtual execute slots are original instructions, not inferred
# from a display name or a decompiler's guessed function boundary.
actions = []
for constructor, tag, execute in [
    (0x10338e4, b'pz_t', 0x10334d8),
    (0x10339f8, b'ks_t', 0x10335b8),
    (0x1033b14, b'fp_t', 0x1031d0c),
]:
    obj = h.alloc(32)
    h.call(constructor+0x10000, [obj])
    vtable, actual_tag = h.words(obj, 2)
    assert struct.pack('<I', actual_tag) == tag
    assert h.words(vtable+0x24)[0] == execute+0x10000
    actions.append({'tag': tag.decode(), 'constructor': hex(constructor),
                    'execute': hex(execute)})

playback = h.call(0x10447d8, [])
h.put(playback+0x10, 100)
h.call(0x1044980, [playback])
clock_slot = (h.words(0x1044974)[0]+0x1044820)&0xffffffff
clock = h.words(clock_slot)[0]
scale = struct.unpack('<f', struct.pack('<I', h.words(0x1044978)[0]))[0]
assert abs(scale-1000/30) < 0.00001
assert h.words(playback+0x14, 3) == [0, 0, 2]

events = []
leaf = 0x5000700
fake_vtable = h.alloc(40)
h.put(fake_vtable+0x24, leaf)

def action(marker):
    obj = h.alloc(8)
    h.put(obj, fake_vtable, marker)
    return obj

def dispatch(uc, address, size, unused):
    if address == leaf:
        events.append(h.words(uc.reg_read(h.UC_ARM_REG_R0)+4)[0])
        uc.reg_write(h.UC_ARM_REG_PC, uc.reg_read(h.UC_ARM_REG_LR))

h.u.hook_add(UC_HOOK_CODE, dispatch)
frames = h.alloc(80)
for index, (time, markers) in enumerate([(10, [11]), (20, [21, 22]),
                                         (20, [31]), (50, [41])]):
    pointers = [action(marker) if marker else 0 for marker in markers]
    # Include a null action: native playback must skip it safely.
    if index == 1:
        pointers.insert(1, 0)
    vector = h.alloc(4*len(pointers))
    h.put(vector, *pointers)
    h.put(frames+index*20, 0, time, vector, vector+4*len(pointers),
          vector+4*len(pointers))
h.put(playback+4, frames, frames+80, frames+80)

checks = []
for delta, expected in [
    (0, []), (5, []), (5, [11]), (0, [11]), (5, [11]),
    (5, [11, 21, 22, 31]), (30, [11, 21, 22, 31, 41]),
    (0, [11, 21, 22, 31, 41]), (50, [11, 21, 22, 31, 41]),
    (20, [11, 21, 22, 31, 41]),
]:
    # Clock +28 is native simulation delta. Do not call it wall-clock seconds:
    # the original dispatcher multiplies it by the fixed 1000/30 scale.
    h.put(clock+0x28, struct.unpack('<I', struct.pack('<f', delta/scale))[0])
    h.call(0x10447f8, [playback])
    assert events == expected, (delta, events, expected)
    elapsed, frame_index, mode = h.words(playback+0x14, 3)
    done = h.call(0x1044a10, [playback])
    assert done == int(elapsed >= 100)
    assert mode == 2
    checks.append({'delta': delta, 'elapsed': elapsed, 'frame_index': frame_index,
                   'actions': list(events), 'finished': bool(done)})

# Stopped replay must not advance or execute callbacks; record mode advances
# duration and invalidates its current frame index instead of playing actions.
before = h.words(playback+0x10, 4)
h.put(playback+0x1c, 0)
h.call(0x10447f8, [playback])
assert h.words(playback+0x10, 3) == before[:3]
assert h.call(0x1044a10, [playback]) == 0
h.put(playback+0x1c, 1)
h.call(0x10447f8, [playback])
assert h.words(playback+0x10, 3) == [before[0]+20, before[1]+20, 0xffffffff]
assert events == [11, 21, 22, 31, 41]

# Exercise the exact constructor/append/teardown path used by local NPC input.
# These triggers retain their real vtables; do not dispatch them without Board.
owned = h.call(0x10447d8, [])
h.put(owned+0x1c, 1)
allocator = h.alloc(4)
h.put(allocator, 0)
alias = h.alloc(16)
h.u.mem_write(alias, b'pvp_change\0')
for index in range(10):
    event = h.alloc(24)
    h.call(0x10438e4, [event])
    previous = h.words(event+8)[0]
    h.call(0x14fd0e1, [event+8, alias, allocator])
    h.call(0x14fbf59, [previous-12, allocator])
    h.put(event+12, 8, index%5, 0)
    h.put(owned+0x14, 1000+index*1500, 0xffffffff)
    h.call(0x104585c, [owned, event])
begin, end = h.words(owned+4, 2)
assert end-begin == 200
for index, frame in enumerate(range(begin, end, 20)):
    time, begin_events, end_events = h.words(frame+4, 3)
    assert time == 1000+index*1500 and end_events-begin_events == 4
    event = h.words(begin_events)[0]
    assert h.narrow(h.words(event+8)[0]) == b'pvp_change'
    assert h.words(event+12, 2) == [8, index%5]
vtable = h.words(owned)[0]
h.call(h.words(vtable+12)[0], [owned])

report = {
    'original_sha256': hashlib.sha256(args.library.read_bytes()).hexdigest(),
    'address_base': 'Native ELF virtual addresses; emulator mapping adds 0x10000.',
    'schemas': schemas, 'actions': actions, 'dispatcher': '0x10347f8',
    'start_playback': '0x1034980', 'finished': '0x1034a10',
    'checks': checks, 'owned_native_trigger_append_and_teardown': True, 'passed': True,
    'scope': 'Real ARM metadata, factories, event constructors, frame dispatch, '
             'mode guards and finish predicate. Allocator/libc/single-thread '
             'primitives and leaf action callback are controlled. No live Board, '
             'zombie movement, combat outcome, persistence, resource parity, '
             'network interception, NPC scheduling or player-save validation.',
}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
print(f'PASS: {len(schemas)} original schemas, {len(actions)} action constructors, '
      f'{len(checks)} timed dispatch checkpoints and mode guards')
