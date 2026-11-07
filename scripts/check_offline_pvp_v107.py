"""Verify local trophy matchmaking through the compiled map and replacement paths."""
import importlib
import struct
import sys

from check_offline_pvp_v76_focused import Definitions


def expected_cups(cups, seed):
    mask = 0xffffffff
    state = seed ^ 0xb27159af
    state = ((state ^ (state >> 16))*0x7feb352d) & mask
    state = ((state ^ (state >> 15))*0x846ca68b) & mask
    state = (state ^ (state >> 16)) or 1

    def draw(n):
        n ^= (n << 13) & mask
        n ^= n >> 17
        return n ^ ((n << 5) & mask)

    roll = draw(state)
    radius = 10 if roll % 100 < 75 else 25 if roll % 100 < 95 else 50
    center = min(cups,100)
    low = max(0,center-radius)
    return low+draw(roll) % (center+radius-low+1)


def main():
    sys.meta_path.insert(0, Definitions())
    core = importlib.import_module('check_offline_pvp_arm')
    fixtures = importlib.import_module('check_offline_pvp_v81_arm')
    wallet = importlib.import_module('check_offline_pvp_v93_focused')
    from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_LR

    class MatchEngine(fixtures.GarrisonEngine):
        def __init__(self):
            super().__init__()
            self.heap = core.M+0x30000

        def hook(self, em, address, size, data):
            if address == core.BASE+0x1019668:
                em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)
                return
            return super().hook(em,address,size,data)

        def action(self, kind, zone, position, button, price=0):
            panel = self.alloc(0x160)
            for offset,value in ((0xa4,kind),(0xac,zone),(0xa8,position),(0xc0,core.M+0x18000),(0x144,price)):
                self.put(panel+offset,value)
            self.run('offlinePvpPanelReady',panel)
            self.stub(0x100b3d8,panel,button)

        def roster_key(self):
            return next(path for path in self.files if path.endswith('.neighbors'))

        def entries(self):
            raw = self.files[self.roster_key()]
            return {struct.unpack_from('<I',raw,i)[0]: bytes(raw[i:i+740])
                    for i in range(24,len(raw),740)}

        def tick(self):
            self.run('offlineTrainingTick',self.get(core.M+0x20))

    def fields(entry):
        return struct.unpack_from('<5I',entry)

    seed = MatchEngine()
    seed.enter()
    base = MatchEngine()
    base.files = {wallet.key(seed): wallet.old_record(seed,7,200000)}
    base.enter()
    base.tick()
    key = wallet.key(base)
    template = bytes(base.files[key])
    assert struct.unpack_from('<I',template,4)[0] == 17

    def load(cups, roster=None, forced_raid=False):
        e = MatchEngine()
        raw = bytearray(template)
        struct.pack_into('<I',raw,2840,cups)
        if forced_raid:
            # Choose a deterministic daily FBI roll to drive a real cup loss.
            for rng in range(1,10000):
                x = rng ^ (rng << 13)
                x &= 0xffffffff
                x ^= x >> 17
                x ^= (x << 5) & 0xffffffff
                if (x-1) % 10000 < 200:
                    break
            else:
                raise AssertionError('no FBI-range seed')
            struct.pack_into('<3I',raw,788,1,rng,e.now)
        e.files = {key:wallet.crc(raw)}
        if roster is not None:
            e.files[base_roster_key] = roster
        e.enter()
        e.run('offlineGarden')
        return e

    def check_ordinary(entry, cups):
        _,rng,kind,actual,_ = fields(entry)
        if rng and not kind:
            assert actual == expected_cups(cups,rng), (cups,rng,actual)

    low = load(0)
    middle = load(60)
    capped = load(100)
    over = load(260)
    assert capped.entries() == over.entries()
    assert low.entries() != middle.entries() != capped.entries()
    ordinary = 0
    for id,entry in low.entries().items():
        _,rng,kind,_,_ = fields(entry)
        if not rng or kind:
            assert middle.entries()[id] == capped.entries()[id] == entry
        else:
            ordinary += 1
            for e,cups in ((low,0),(middle,60),(capped,100)):
                check_ordinary(e.entries()[id],cups)
    assert ordinary

    base_roster_key = low.roster_key()
    initial = bytes(low.files[base_roster_key])
    high = load(101,initial,forced_raid=True)
    assert bytes(high.files[base_roster_key]) == initial
    original = high.entries()
    high.advance(86400)
    high.tick()
    assert high.get(core.M+12) == 96
    assert bytes(high.files[base_roster_key]) == initial

    row = next(p for p in high.residents() if high.get(p) in original and fields(original[high.get(p)])[2] == 0)
    id = high.get(row)
    zone,position = high.get(row+28),high.get(row+32)
    ordinary_rolls = []
    for _ in range(18):
        before = high.entries()
        high.action(5,zone,position,204)
        after = high.entries()
        assert after[id] != before[id]
        assert {k for k in before if before[k]!=after[k]} == {id}
        _,rng,kind,cups,_ = fields(after[id])
        check_ordinary(after[id],96)
        if not kind:
            ordinary_rolls.append(cups != expected_cups(100,rng))
    assert any(ordinary_rolls), 'replacement never differentiated 96 from 100'

    # A new area's vacant slots use the current balance, leaving populated slots intact.
    before = high.entries()
    high.action(0,4,0,202,23500)
    after = high.entries()
    filled = [k for k in before if not fields(before[k])[1] and fields(after[k])[1]]
    assert filled and any(not fields(after[k])[2] for k in filled)
    for k in before:
        if k in filled:
            check_ordinary(after[k],96)
        else:
            assert before[k]==after[k]
    reloaded=MatchEngine()
    reloaded.copy_state(high)
    reloaded.advance(high.now-reloaded.now)
    reloaded.enter()
    reloaded.run('offlineGarden')
    assert reloaded.get(core.M+12)==96 and reloaded.entries()==after
    print('PASS: local cup matching, 100-cap, special snapshots, live cup loss, replacement, new region, restart')


if __name__=='__main__':
    main()
