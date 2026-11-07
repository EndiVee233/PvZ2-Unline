"""Shop keeper changes on compiled ARM using synthetic profiles only."""
import importlib
import json
import struct
import sys
from pathlib import Path
from check_offline_pvp_v76_focused import Definitions


def main():
    sys.meta_path.insert(0, Definitions())
    g = importlib.import_module('check_offline_pvp_v81_arm')
    h = importlib.import_module('check_offline_pvp_v93_focused')
    c = importlib.import_module('check_offline_pvp_arm')
    battle = importlib.import_module('check_offline_pvp_v60_arm')
    M, PM = c.M, c.PM
    from unicorn.arm_const import UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_PC,UC_ARM_REG_LR

    class ShopEngine(g.GarrisonEngine):
        def hook(self,em,a,size,d):
            if a==c.BASE+0x1019668:
                self.opened.append(tuple(em.reg_read(r) for r in (UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)))
                em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)
                return
            return super().hook(em,a,size,d)

    def new():
        e = ShopEngine(); e.heap = M+0x30000
        return e

    seed = new(); seed.enter()
    e = new(); e.files = {h.key(seed): h.old_record(seed)}
    e.enter(); e.run('offlineGarden')

    def panel(e, index):
        p, _ = e.shop_panel(e.shops()[index]); e.put(p+0xc0, M+0x18000)
        e.run('offlinePvpPanelReady', p)
        return p

    def title(e, index):
        p = e.get(e.shops()[index]+16); out = []
        for i in range(40):
            v = e.get(p+4*i)
            if not v: break
            out.append(v)
        return tuple(out)

    def files(e): return {k: bytes(v) for k,v in e.files.items()}
    def funds(e): return e.get(M+4), e.get(M+8), e.gems, e.held()
    before = funds(e); original = files(e)
    second = bytes(e.u.mem_read(e.shops()[1],64))
    p = panel(e,0); old_title = title(e,0)
    e.failwrite = True; e.stub(0x100b3d8,p,204)
    assert files(e)==original and title(e,0)==old_title and not e.opened
    e.failwrite = False; e.stub(0x100b3d8,p,204)
    assert title(e,0)!=old_title and e.opened[-1]==(3,3,2)
    assert bytes(e.u.mem_read(e.shops()[1],64))==second and funds(e)==before
    assert all(bytes(e.files[k])==v for k,v in original.items() if k!=h.key(e))
    saved = files(e); e.stub(0x100b3d8,p,204)
    assert files(e)==saved, 'stale double callback changed opponent'
    for index in (0,1,0,1):
        names = [title(e,i) for i in (0,1)]
        e.stub(0x100b3d8,panel(e,index),204)
        assert title(e,index)!=names[index] and title(e,1-index)==names[1-index]
        assert funds(e)==before
    names = [title(e,i) for i in (0,1)]
    r = new(); r.copy_state(e); r.now=e.now; r.enter(); r.run('offlineGarden')
    assert [title(r,i) for i in (0,1)]==names and funds(r)==before
    # An old profile's panel is never accepted after a user change.
    p=panel(r,0); saved=files(r); r.put(PM+0x74,43)
    r.stub(0x100b3d8,p,204); assert files(r)==saved
    r.put(PM+0x74,42)
    # New keepers still use each shop's existing formation and free scouting.
    for index,plant in ((0,2),(1,6),(0,2)):
        r.scout_shop(index); battle.board(r)
        assert r.plants()==b''.join(struct.pack('<III',plant,row,0) for row in range(5))
        r.cancel(); assert funds(r)==before
    r.train(); r.advance(31); r.run('offlineTrainingTick',r.get(M+0x20))
    g.claim(r,0); assert r.owned()==1
    # Ownership, real capture, garrison persistence and rejection of stale
    # unowned panels are exercised rather than mocking the ownership flag.
    r.edit(0); positions=r.plants(); r.save(); r.request(3)
    saved=files(r); name=title(r,0); p=panel(r,0)
    r.stub(0x100b3d8,p,204)
    assert files(r)==saved and title(r,0)==name and r.owned()==1
    r.stub(0x100b3d8,panel(r,1),204)
    assert all(bytes(r.files[k])==v for k,v in saved.items() if k!=h.key(r))
    r.edit(0); assert r.plants()==positions; r.request(3)
    result=dict(transactional_replacement=True,distinct_names=True,two_shops_isolated=True,
                funds_army_roster_unchanged=True,write_failure_and_stale_callback_guards=True,
                restart_and_profile_scope=True,original_formations_and_scouting_preserved=True,
                capture_and_owned_garrison_preserved=True,runtime_game_verified=False)
    (Path(sys.argv[1])/'v105-checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__': main()
