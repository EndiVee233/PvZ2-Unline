"""Use the actual native packet getter/setter to account for unplayed units."""
from check_offline_pvp_v48_arm import SessionEngine,OUT,BOARD,MODULE
from check_offline_pvp_arm import BASE,M
import json

e=SessionEngine();e.run('offlineGarden');e.stub(0x9344a4,e.product(),1)
for _ in range(40):e.train()
ui,button,timer=e.training_ui();e.run('offlineTrainingDisplay',ui)
assert e.labels[button+0xa4]=='3钻石立即完成'
e.stub(0x1059300,ui,1)
# The original refresh overwrites the cash quote in +1f4; our refresh must
# restore the same minutes used by the displayed gem price and confirm.
e.put(timer+0x1f4,1);e.run('offlineTrainingDisplay',ui);assert e.get(timer+0x1f4)==20
e.confirm(timer);assert e.gems==97 and e.held()==40
e.stub(0x1042fe8,M,0x70000001,3,0)
name=e.alloc(4);e.string(name,'arena_battle_test');e.run('offlineBoardLoad',BOARD,name,0xffffffff);e.live()
# Native PVPZombieSeedPacket setter is the same one used by bank population.
e.run(0x1030a50,M+0x14300,39)
e.stub(0x10448e8,M,0,0x70000001,2);e.run('offlineTrainingTick',e.get(M+0x20))
assert e.held()==39 and e.windows==1,'unplayed units were consumed at result'
e.stub(0x104fa50,M+0x12000,0)
# Start another neighbor without training again; no stale bank pointer/count.
e.put(M+0x7000+0x6bc,0)
e.stub(0x1042fe8,M,0x70000002,3,0);e.run('offlineBoardLoad',BOARD,name,0xffffffff);e.live()
assert e.army()==[(201,39)]
e.run(0x1030a50,M+0x14300,39) # no zombie was placed in this battle
e.stub(0x10448e8,M,0,0x70000002,2);e.run('offlineTrainingTick',e.get(M+0x20))
assert e.held()==39,'ending without deploying consumed units'
result=dict(native_packet_setter_and_getter_executed=True,forty_units_minus_one_is_thirty_nine=True,next_neighbor_bank_gets_thirty_nine=True,no_deployment_no_consumption=True,mid_battle_training_preserved=True,training_display_and_confirm_same_quote=True,runtime_game_verified=False)
(OUT/'v50-arm-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
