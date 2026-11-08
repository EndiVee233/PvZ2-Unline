"""Verify local trophy matchmaking through the compiled map and replacement paths."""
import importlib
import hashlib
import json
from pathlib import Path
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
    from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_SP

    class MatchEngine(fixtures.GarrisonEngine):
        def __init__(self):
            super().__init__()
            self.heap = core.M+0x30000
            self.spawn_probe=None

        def hook(self, em, address, size, data):
            if self.spawn_probe is not None and address==core.BASE+0x21ab00:
                stack=em.reg_read(UC_ARM_REG_SP)
                grade_address=next(v for k,v in self.exports.items() if k.endswith('sharedSpawnGrade'))
                self.spawn_probe.append((tuple(self.get(stack+i*4) for i in range(6)),self.get(core.BASE+grade_address)))
                em.reg_write(UC_ARM_REG_R0,0x12345678)
                em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)
                return
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
            stride=900 if struct.unpack_from('<I',raw,4)[0]==3 else 740
            return {struct.unpack_from('<I',raw,i)[0]: bytes(raw[i:i+stride])
                    for i in range(24,len(raw),stride)}

        def catalog(self, words):
            data=self.alloc(4*len(words))
            self.u.mem_write(data,struct.pack(f'<{len(words)}I',*words))
            self.run('offlinePresetCommand',8,data,len(words))
            return self.u.reg_read(UC_ARM_REG_R0)

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

    def load(cups, roster=None, forced_raid=False, catalog=None):
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
        if catalog is not None: assert e.catalog(catalog)==catalog[0]+1
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

    if 'offlineSharedSpawnBegin' in low.exports:
        raw=bytearray(initial[:24]+b''.join(v[:740] for v in low.entries().values()))
        struct.pack_into('<I',raw,4,2)
        checksum=2166136261
        for i,value in enumerate(raw):
            if i<20 or i>=24:checksum=((checksum^value)*16777619)&0xffffffff
        struct.pack_into('<I',raw,20,checksum)
        migrated=load(0,raw)
        assert migrated.entries()=={key:entry[:740] for key,entry in low.entries().items()}
        catalog={p.name:json.loads(p.read_text(encoding='utf8')) for p in Path('pvp-presets').glob('*.pvz2-pvp.json')}
        plant_ids={p['name']:p['id'] for p in json.loads((Path(sys.argv[1])/'generated/preset-editor-catalogue.json').read_text())}
        def encode_pool(catalog):
            words=[len(catalog)];shared={}
            for filename,doc in catalog.items():
                seed=int.from_bytes(hashlib.sha256(filename.encode()).digest()[:4],'big')
                name=list(map(ord,doc['名字']));plants=doc['阵容']
                cups=doc['奖杯']
                if cups is None:cups=min(150,2*len(plants)+3*sum(p['level']-1 for p in plants))
                chance=doc['出现概率']
                appearance=round(chance*100)+1 if doc['特殊值'] and name and doc['奖杯'] is not None and chance is not None else 0
                shared[seed]=(doc,cups)
                words.extend([seed,cups,len(plants),*name,*([0]*(40-len(name))),appearance])
                for p in plants:words.extend((plant_ids[p['type']],p['row'],p['column'],p['level']))
                words.extend([0]*(180-4*len(plants)))
            return words,shared
        words,shared=encode_pool(catalog)
        online=load(0,catalog=words)
        assigned=[entry for entry in online.entries().values() if fields(entry)[2]==8]
        assert assigned
        named=[]
        for entry in assigned:
            id,seed,kind,cups,count=fields(entry);doc,expected=shared[seed]
            assert count==len(doc['阵容']) and cups==expected
            title=entry[740:].decode('utf-32-le').rstrip('\0')
            assert title
            if doc['名字']:
                assert title==doc['名字']
                named.append(seed)
            for i,p in enumerate(doc['阵容']):
                assert struct.unpack_from('<4I',entry,20+16*i)==(plant_ids[p['type']],p['level'],p['row'],p['column'])
        assert len(set(named))==len(named)
        online_initial=bytes(online.files[online.roster_key()]);offline=load(0,online_initial)
        assert offline.entries()==online.entries()
        row=next(p for p in online.residents() if fields(online.entries()[online.get(p)])[2]==8)
        id=online.get(row);seed=fields(online.entries()[id])[1]
        entry=online.entries()[id];saved=online.alloc(len(entry));online.u.mem_write(saved,entry)
        for name,value in (('sharedBattle',saved),('arenaNpc',id)):
            address=next(v for k,v in online.exports.items() if k.endswith(name))
            online.put(core.BASE+address,value)
        board=online.alloc(0x140);online.string(board+0xc4,'arena_battle_test')
        online.spawn_probe=[]
        for site,index in ((0x108d204,0),(0x108ddf0,1)):
            _,grade,plant_row,col=struct.unpack_from('<4I',entry,20+16*index)
            online.stub(site,board,col,plant_row,0,1,1,0xffffffff,0,1,0)
            assert online.spawn_probe[-1]==((1,1,0xffffffff,0,1,0),grade)
            assert online.u.reg_read(UC_ARM_REG_R0)==0x12345678
            online.run('offlinePresetGrade',core.M,0)
            assert online.u.reg_read(UC_ARM_REG_R0)==0
        online.spawn_probe=None
        online.action(5,online.get(row+28),online.get(row+32),204)
        assert fields(online.entries()[id])[1]!=seed
        before=online.entries();assert online.catalog([0])==1
        online.action(5,online.get(row+28),online.get(row+32),204)
        assert fields(online.entries()[id])[2]!=8
        assert {k for k in before if online.entries()[k]!=before[k]}=={id}
        common=dict(catalog['pea-yard.pvz2-pvp.json'],名字='',奖杯=0)
        special=dict(common,名字='测试特殊敌人',奖杯=999,特殊值=True,出现概率=100)
        never=dict(special,名字='不出现',出现概率=0)
        words,shared=encode_pool({'generic.json':common,'special.json':special,'never.json':never})
        mixed=load(0,catalog=words)
        selected=[e for e in mixed.entries().values() if fields(e)[2]==8]
        names=[e[740:].decode('utf-32-le').rstrip('\0') for e in selected]
        assert names.count(special['名字'])==1 and never['名字'] not in names
        assert len(set(names)-{special['名字']})>=2
        assert all(fields(e)[3] in (0,999) for e in selected)
        print('PASS: legacy roster, one-file formations, generic reuse, special odds, mixed ranks, restart and local fallback')


if __name__=='__main__':
    main()
