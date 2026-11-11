"""Run injected ARM persistence/ABI paths with synthetic players and file I/O."""
import argparse
import json
import os
from pathlib import Path
import struct

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *


def check(folder):
    os.environ['PVZ2_NATIVE_ORIGINAL'] = str(folder / 'libSrc-profile-memory.so')
    from native_emulation_support import machine
    report = json.loads((folder / 'profile-memory-validation.json').read_text())
    uc, imports = machine()
    base, manager, player, stack, stop = 0x10000, 0x6000000, 0x6001000, 0x4080000, 0x5000100
    state = {}

    def put(address, value): uc.mem_write(address, struct.pack('<I', value & 0xffffffff))
    def get(address): return struct.unpack('<I', uc.mem_read(address, 4))[0]
    def string(address):
        value = bytearray()
        while True:
            c = uc.mem_read(address, 1)[0]
            if not c: return bytes(value).decode()
            value.append(c); address += 1

    def hook(uc, address, size, unused):
        if address in (stop, base + 0x7aaa78, base + 0x7aaa28):
            state['exit'] = address; uc.emu_stop(); return
        r = [uc.reg_read(x) for x in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        name = imports.get(address)
        if name == 'open':
            path = string(r[0]); writing = r[1] != 0
            if writing:
                state['temporary'] = b''; state['position'] = 0
                result = -1 if state.get('fail') == 'open' else 7
            else:
                state['position'] = 0
                result = 7 if state.get('record') is not None else -1
        elif name == 'read':
            record = state.get('record', b''); at = state['position']
            data = record[at:at + r[2]]; state['position'] += len(data)
            if data: uc.mem_write(r[1], data)
            result = len(data)
        elif name == 'write':
            data = bytes(uc.mem_read(r[1], r[2]))
            if state.get('fail') == 'write': data = data[:4]
            state['temporary'] = data; result = len(data)
        elif name in ('fsync', 'close', 'rename'):
            result = -1 if state.get('fail') == name else 0
            if name == 'rename' and result == 0: state['record'] = state['temporary']
        elif name == 'remove':
            state['temporary'] = None; result = 0
        elif name == '__android_log_print':
            state['messages'].append(string(r[3])); result = 0
        elif address == base + 0x7aab68:
            state['lookup'] = r[2]
            present = r[2] in state['players']
            uc.mem_write(r[0], struct.pack('<II', *( (1, 2) if present else (0, 0))))
            result = r[0]
        elif address == base + 0x11d74b4: result = 0x6002000
        elif address == base + 0x1da034:
            result = 0 if state.get('expired') else player
            put(player + 0x1ec, state.get('resolved_id', state.get('lookup', 0)))
        elif address == base + 0x1d9bb4:
            assert r[2:4] == [0, 0]
            state['releases'] += 1; result = r[0]
        else: return
        uc.reg_write(UC_ARM_REG_R0, result & 0xffffffff)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    uc.hook_add(UC_HOOK_CODE, hook)
    cases = []
    def run(entry, record=None, players=(7, 99), fail=None, expired=False, resolved_id=None):
        state.clear(); state.update(record=record, players=set(players), fail=fail,
                                    expired=expired, messages=[], releases=0)
        if resolved_id is not None: state['resolved_id'] = resolved_id
        for register in range(UC_ARM_REG_R0, UC_ARM_REG_R12 + 1): uc.reg_write(register, 0)
        for register in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                         UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11):
            uc.reg_write(register, 0xabc000 + register)
        put(manager + 0x74, 7)
        uc.reg_write(UC_ARM_REG_R0, base)
        uc.reg_write(UC_ARM_REG_R1, manager)
        uc.reg_write(UC_ARM_REG_SP, stack)
        uc.reg_write(UC_ARM_REG_LR, stop)
        uc.emu_start(base + entry, 0, count=20000)
        assert state['exit'] == stop and uc.reg_read(UC_ARM_REG_SP) == stack
        for register in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                         UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11):
            assert uc.reg_read(register) == 0xabc000 + register
        return uc.reg_read(UC_ARM_REG_R0)

    def record(id): return struct.pack('<III', 0x314c5055, id, ~id & 0xffffffff)
    for id in (0, 7, 99, 0x7e860001):
        assert run(report['restore_function'], record(id), players=(id, 100)) == 1
        assert get(manager + 0x74) == id and state['releases'] == 1
        cases.append('valid ID %d including zero; independent of list order' % id)
    for name, data, players, expired, mismatch in (
        ('absent', None, (7, 99), False, None),
        ('short', record(99)[:8], (7, 99), False, None),
        ('checksum', record(99)[:8] + b'bad!', (7, 99), False, None),
        ('trailing', record(99) + b'x', (7, 99), False, None),
        ('deleted', record(99), (7,), False, None),
        ('expired', record(99), (7, 99), True, None),
        ('wrong-resolved-ID', record(99), (7, 99), False, 100),
    ):
        assert run(report['restore_function'], data, players, expired=expired, resolved_id=mismatch) == 0
        assert get(manager + 0x74) == 7
        cases.append(name + ' safely retains original fallback')
    for fail in (None, 'open', 'write', 'fsync', 'close', 'rename'):
        old = record(99)
        run(report['remember_function'], old, fail=fail)
        assert state['record'] == (record(7) if fail is None else old)
        cases.append('atomic remember: ' + str(fail))

    # Verify entry trampolines preserve the surrounding original caller's ABI.
    for restore in (False, True):
        state.clear(); state.update(record=record(99) if restore else None, players={7, 99},
                                    messages=[], releases=0)
        uc.reg_write(UC_ARM_REG_R0, manager); uc.reg_write(UC_ARM_REG_SP, stack)
        uc.reg_write(UC_ARM_REG_LR, stop); uc.reg_write(UC_ARM_REG_R4, 444); uc.reg_write(UC_ARM_REG_R5, 555)
        uc.emu_start(base + 0x7aaa74, 0, count=20000)
        assert state['exit'] == (stop if restore else base + 0x7aaa78)
        assert uc.reg_read(UC_ARM_REG_SP) == stack - (0 if restore else 24)
        assert uc.reg_read(UC_ARM_REG_R0) == (1 if restore else manager)
        assert uc.reg_read(UC_ARM_REG_R4) == 444 and uc.reg_read(UC_ARM_REG_R5) == 555
        cases.append('restore trampoline ABI: ' + str(restore))
    state.clear(); state.update(record=record(99), players={7, 99}, messages=[], releases=0)
    put(manager + 0x74, 7)
    uc.reg_write(UC_ARM_REG_R0, 123); uc.reg_write(UC_ARM_REG_R3, 7)
    uc.reg_write(UC_ARM_REG_R4, 444); uc.reg_write(UC_ARM_REG_R5, manager); uc.reg_write(UC_ARM_REG_R6, 1)
    uc.reg_write(UC_ARM_REG_SP, stack); uc.reg_write(UC_ARM_REG_LR, stop)
    uc.emu_start(base + 0x7aaa70, 0, count=20000)
    assert state['exit'] == base + 0x7aaa28 and state['record'] == record(7)
    assert uc.reg_read(UC_ARM_REG_SP) == stack and uc.reg_read(UC_ARM_REG_R0) == 123
    assert uc.reg_read(UC_ARM_REG_R3) == 7 and uc.reg_read(UC_ARM_REG_R4) == 444
    assert uc.reg_read(UC_ARM_REG_R5) == manager and uc.reg_read(UC_ARM_REG_R6) == 1
    cases.append('successful select trampoline preserves registers and return path')
    result = {'passed_cases': len(cases), 'cases': cases,
              'scope': 'Injected ARM code, synthetic players and mocked filesystem/registry boundaries; not game acceptance'}
    (folder / 'emulation-validation.json').write_text(json.dumps(result, indent=2))
    print('Profile-memory ARM cases passed:', len(cases))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    check(**vars(parser.parse_args()))
