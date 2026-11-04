"""Check original Board::Finish dispatch on result return and stale reentry."""
from check_offline_pvp_v50_arm import SessionEngine,OUT,BOARD,MODULE
from check_offline_pvp_arm import M
import json

e=SessionEngine();e.run('offlineGarden');e.stub(0x9344a4,e.product(),1);e.train();e.advance(31);e.run('offlineTrainingTick',e.get(M+0x20))
e.stub(0x1042fe8,M,0x70000001,3,0)
name=e.alloc(4);e.string(name,'arena_battle_test');e.run('offlineBoardLoad',BOARD,name,0xffffffff);e.live();e.put(BOARD+0xc0,5)
e.run(0x1030a50,M+0x14300,1) # no deployment
e.put(M+0xd8,e.get(M+0xd4))
e.stub(0x10448e8,M,0,0x70000001,2);e.run('offlineTrainingTick',e.get(M+0x20));assert e.windows==1
e.stub(0x104fa50,M+0x12000,0)
assert e.ends==1 and e.get(BOARD+0xc0)==9 and e.scenes[-1]==25 and e.held()==1
e.stub(0x1042fe8,M,0x70000002,3,0);assert e.ends==1,'already-finished board ended twice'
e.run('offlineBoardLoad',BOARD,name,0xffffffff);e.live();e.put(BOARD+0xc0,5)
e.run(0x1030a50,M+0x14300,1)
e.put(M+0xd8,e.get(M+0xd4))
e.stub(0x10448e8,M,0,0x70000002,2);e.run('offlineTrainingTick',e.get(M+0x20));assert e.windows==2
e.stub(0x104fa50,M+0x12000,0);assert e.ends==2 and e.held()==1
# A previously abandoned board is also finished before the next native load.
e.put(BOARD+0xc0,5);e.put(M+0x7000+0x1218,3)
e.stub(0x1042fe8,M,0x70000003,3,0);assert e.ends==3
result=dict(native_board_finish_guard_executed=True,result_return_finishes_board_before_map=True,second_zero_deployment_result_and_exit=True,already_finished_board_not_repeated=True,stale_board_finished_before_next_load=True,army_preserved=True,runtime_game_verified=False)
(OUT/'v51-arm-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
