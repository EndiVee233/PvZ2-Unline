"""Exercise screenshot formations and transactional Dave rewards in ARM code."""
import importlib
import json
import struct
import sys
from pathlib import Path
from check_offline_pvp_v76_focused import Definitions


def main():
    sys.meta_path.insert(0, Definitions())
    dave = importlib.import_module('check_offline_pvp_v66_arm')
    core = importlib.import_module('check_offline_pvp_arm')
    garrison = importlib.import_module('check_offline_pvp_v81_arm')
    helpers = importlib.import_module('check_offline_pvp_v93_focused')
    M = core.M
    out = Path(sys.argv[1])
    rounds = json.loads((out/'generated/dave-build.json').read_text())['rounds']

    def ready():
        e = garrison.GarrisonEngine()
        # Keep dynamically allocated fixtures clear of the fixed native bank
        # stand-ins at M+0x14000..0x14500 during consecutive six-round tests.
        e.heap = M+0x30000
        e.enter(); e.run('offlineGarden')
        for _ in range(3): e.train()
        e.advance(91); e.run('offlineTrainingTick', e.get(M+0x20))
        return e

    def preview(e, index):
        e.put(M+0x104, 0x70000007); e.put(M+0xfc, 1); e.put(M+0xf8, 1)
        positions = dave.preview(e)
        expected = b''.join(struct.pack('<III', *p) for p in rounds[index]['plants'])
        assert positions == expected, ('formation', index)
        infos = [tuple(e.get(p+j) for j in (0,4)) for p in range(e.get(M+0x90), e.get(M+0x94),16)]
        assert dict(infos) == {p[0]: rounds[index]['level'] for p in rounds[index]['plants']}
        loads = len(e.loads)
        dave.start(e)
        assert len(e.loads) == loads and e.get(dave.MODULE+0xb0) == 3
        e.run(0x1030a50, M+0x14300, e.held())

    e = ready()
    preview(e, 0)
    before = (e.get(M+4), e.get(M+8), e.gems, e.held())
    dave.result(e, 0)
    assert e.get(M+0x15c) == 0 and (e.get(M+4),e.get(M+8),e.gems,e.held()) == before
    assert (e.get(M+0xc4),e.get(M+0xc8),e.get(M+0xcc)) == (0,0,0)
    dave.return_map(e)

    for index, r in enumerate(rounds):
        preview(e, index)
        before = (e.get(M+4), e.get(M+8), e.gems, e.held())
        saved = bytes(e.files[helpers.key(e)])
        if index == 0:
            e.failwrite = True; dave.result(e, 1)
            assert bytes(e.files[helpers.key(e)]) == saved and e.get(M+0x15c) == 0
            assert (e.get(M+4),e.get(M+8),e.gems,e.held()) == before
            e.failwrite = False
            e.stub(0x10448e8, M, 1, 0x70000001, 1)
            assert bytes(e.files[helpers.key(e)]) == saved
        dave.result(e, index%3+1)
        assert e.get(M+0x15c) == index+1
        assert (e.get(M+4),e.get(M+8),e.gems,e.held()) == (before[0],before[1]+r['medals'],before[2],before[3])
        assert (e.get(M+0xc4),e.get(M+0xc8),e.get(M+0xcc)) == (0,r['medals'],0)
        raw = bytes(e.files[helpers.key(e)])
        assert struct.unpack_from('<I',raw,832)[0] == r['medals'], 'journal medal amount'
        dave.result(e, 3)
        assert bytes(e.files[helpers.key(e)]) == raw, 'duplicate result paid twice'
        dave.return_map(e)
        f = garrison.GarrisonEngine(); f.heap = M+0x30000; f.copy_state(e); f.now = e.now
        f.enter(); f.run('offlineGarden')
        assert f.get(M+0x15c) == index+1 and f.get(M+8) == before[1]+r['medals']
        e = f

    loads = len(e.loads)
    e.put(M+0x104,0x70000007); e.put(M+0xfc,1); e.put(M+0xf8,1)
    e.stub(0x1042fe8,M,0,4,0)
    assert len(e.loads) == loads and e.notices[-1] == '[V66_DAVE_FINISHED]'

    # Preserve already completed rounds on upgrade; no guessed back payment.
    old = ready(); data = bytearray(old.files[helpers.key(old)])
    struct.pack_into('<I',data,216,4)
    old.files[helpers.key(old)] = helpers.crc(data)
    migrated = garrison.GarrisonEngine(); migrated.heap = M+0x30000; migrated.copy_state(old); migrated.now = old.now
    migrated.enter(); migrated.run('offlineGarden')
    assert migrated.get(M+0x15c) == 4 and migrated.get(M+8) == old.get(M+8)
    preview(migrated,4)

    # Existing non-Dave currency behavior must retain its accepted formula.
    battle = importlib.import_module('check_offline_pvp_v60_arm')
    normal = ready(); funds=(normal.get(M+4),normal.get(M+8))
    normal.selected(normal.residents()[0]); target=normal.get(normal.residents()[0])
    normal.stub(0x1042fe8,M,0,4,0); battle.board(normal)
    normal.stub(0x1042fe8,M,0,1,0)
    normal.run(0x1030a50,M+0x14300,normal.held()); normal.deaths(0)
    battle.result(normal,2,target)
    assert (normal.get(M+4),normal.get(M+8)) == (funds[0]-1+66,funds[1])
    report=dict(six_formations_and_tiers=True,zero_star_no_reward=True,positive_star_round_reward=True,
                native_result_medal_display=True,army_and_currency_atomic=True,duplicate_and_failed_save_safe=True,
                history_and_restart_preserved=True,old_wins_no_back_payment=True,
                ordinary_neighbor_rewards_unchanged=True,runtime_game_verified=False)
    (out/'v104-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__': main()
