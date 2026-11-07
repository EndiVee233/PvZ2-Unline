"""Exercise v17 migration, residential protection and local cup settlement."""
import importlib
from pathlib import Path
import struct
import sys

from check_offline_pvp_v76_focused import Definitions


def main():
    sys.meta_path.insert(0, Definitions())
    g = importlib.import_module('check_offline_pvp_v81_arm')
    battle = importlib.import_module('check_offline_pvp_v60_arm')
    h = importlib.import_module('check_offline_pvp_v93_focused')
    c = importlib.import_module('check_offline_pvp_arm')
    M = c.M

    def new():
        e = g.GarrisonEngine()
        e.heap = M+0x30000
        return e

    def tick(e):
        e.run('offlineTrainingTick',e.get(M+0x20))

    def timer(e):
        return struct.unpack('<f',e.u.mem_read(M+0x78,4))[0]

    def row(e, id):
        return next(p for p in e.residents() if e.get(p)==id)

    def target(e, id):
        e.selected(row(e,id))

    def restart(e):
        r=new()
        r.copy_state(e)
        r.advance(e.now-r.now)
        r.enter()
        r.run('offlineGarden')
        return r

    seed=new()
    seed.enter()
    older=new()
    older.files={h.key(seed):h.old_record(seed)}
    older.enter()
    older.run("offlineGarden")
    tick(older)
    legacy=bytearray(older.files[h.key(older)][:2840])
    struct.pack_into('<I',legacy,4,16)
    e=new()
    e.files={h.key(seed):h.crc(legacy)}
    e.enter()
    e.run('offlineGarden')
    assert e.get(M+12)==0 and timer(e)>1e30
    e.train()
    assert timer(e)==1030
    e.train()
    assert timer(e)==1060
    e=restart(e)
    assert timer(e)==1060
    e.advance(61)
    tick(e)
    assert e.held()==2 and timer(e)>1e30
    e.train()
    assert timer(e)<1e30
    e.train(2)
    assert timer(e)>1e30

    ids=[e.get(p) for p in e.residents() if e.get(p+16)!=999 and e.get(p)!=0x70000007][:4]
    assert len(ids)==4
    total=0
    for stars,id in enumerate(ids):
        target(e,id)
        e.stub(0x1042fe8,M,0,1,0)
        battle.board(e)
        e.run(0x1030a50,M+0x14300,e.held())
        e.deaths(0)
        if stars==2:
            saved=bytes(e.files[h.key(e)])
            e.failwrite=True
            battle.result(e,stars,id)
            assert bytes(e.files[h.key(e)])==saved and e.get(M+12)==total
            e.failwrite=False
        battle.result(e,stars,id)
        gain=(0,1,3,5)[stars]
        total+=gain
        assert e.get(M+12)==total and e.get(M+0xcc)==gain,(stars,total,e.get(M+12),e.get(M+0xcc),e.notices,e.messages[-20:])
        assert e.get(M+0xc4)==100*stars//3
        battle.result(e,stars,id)
        assert e.get(M+12)==total
        e.advance(60)
        battle.return_map(e)
        e.reset_map()

        p=row(e,id)
        assert e.get(p+0x24)==(2 if stars else 1)
        assert e.get(p+0x28)==(e.now+1800 if stars else 0)

    e=restart(e)
    id=ids[-1]
    p=row(e,id)
    deadline=e.get(p+0x28)
    assert e.get(M+12)==9 and e.get(p+0x24)==2
    before=e.get(M+4)
    loads=len(e.loads)
    target(e,id)
    e.stub(0x1042fe8,M,0,1,0)
    assert e.get(M+4)==before and len(e.loads)==loads
    assert e.notices[-1]=='[PVP_MAP_PVP_STATE]'
    e.stub(0x1042fe8,M,0,4,0)
    battle.board(e)
    e.stub(0x1042fe8,M,0,1,0)
    assert e.get(M+4)==before and e.starts==0
    e.cancel()
    e.advance(deadline-e.now-1)
    target(e,id)
    loads=len(e.loads)
    before=e.get(M+4)
    e.stub(0x1042fe8,M,0,1,0)
    assert len(e.loads)==loads and e.get(M+4)==before
    e.advance(1)
    tick(e)
    assert e.get(row(e,id)+0x24)==1
    before=e.get(M+4)
    e.stub(0x1042fe8,M,0,1,0)
    assert len(e.loads)==loads+1 and e.get(M+4)==before-1

    importlib.import_module('check_offline_pvp_v99_events').check_events(
        importlib.import_module('check_offline_pvp_v82_arm'))
    print('PASS: v16 migration, v17 restart, cups and protection settlement, deadline boundary, training timer')


if __name__=='__main__':
    main()
