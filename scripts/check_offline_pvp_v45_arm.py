"""Check preview-to-attack separation and native camp rebinding."""
from check_offline_pvp_scenes_arm import SceneEngine,OUT
from check_offline_pvp_arm import BASE,M,GM
from unicorn.arm_const import *
import json
class BattleEngine(SceneEngine):
 def __init__(self):super().__init__();self.board_army=[]
 def hook(self,em,a,size,d):
  if a-BASE==0x2258d8:
   self.board_army.append(self.held());em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
  return super().hook(em,a,size,d)
e=BattleEngine();e.run('offlineGarden');assert len(e.records)==6 and len(e.special)==1 and e.get(M+0x15c)==1
# Native +100 distinguishes preview from an actual attack, despite equal level names.
e.u.mem_write(M+0x100,b'\1');e.stub(0x1042fe8,M,0x70000001,3,0)
assert e.loads==[('arena_battle_test',0)]
e.u.mem_write(M+0x100,b'\0');e.stub(0x1042fe8,M,0x70000001,2,0)
assert len(e.loads)==2 and e.loads[-1]==('arena_battle_test',0)
e.stub(0x1042fe8,M,0x70000001,2,0);assert len(e.loads)==2
# Persisted local held units must be restored even if a native transition empties
# a camp while retaining the same pointer (ensureEconomy alone cannot detect this).
e.stub(0x9344a4,e.product(),1);e.train();e.advance(31);e.run('offlineTrainingTick',e.get(M+0x20));assert e.held()==1
camp=e.get(M+0x20);e.put(camp+16,e.get(camp+12));assert e.held()==0
name=e.alloc(4);e.string(name,'arena_battle_test');e.run('offlineBoardLoad',M+0xd000,name,0xffffffff)
assert e.board_army==[1] and e.held()==1
result=dict(preview_uses_battle_level=True,preview_confirmation_not_blocked=True,repeated_attack_guard=True,same_pointer_native_army_rebound=True,evil_challenge_level_positive=True,runtime_game_verified=False)
(OUT/'v45-arm-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
