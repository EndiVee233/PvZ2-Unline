"""Exercise the native attack-army vector assignment at a relocated base."""
from check_offline_pvp_scenes_arm import SceneEngine,OUT
from check_offline_pvp_arm import BASE,M,END
from unicorn.arm_const import *
import json,struct

class BattleEngine(SceneEngine):
 def __init__(self):super().__init__();self.board_army=[];self.aliases=[]
 def army(self):
  a,e=self.get(M+0xd4),self.get(M+0xd8)
  return [struct.unpack('<II',bytes(self.u.mem_read(p,8))) for p in range(a,e,8)]
 def hook(self,em,a,size,d):
  off=a-BASE
  # Execute the real native vector setter and assignment, including allocation
  # and replacement of an existing vector; the copy primitive is the boundary.
  if off==0x10454b0 or 0x10451f0<=off<0x10454d4:return
  x,y,z=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
  if off==0xfb6ef0:
   alias=self.txt(self.get(y));self.aliases.append(alias)
   types={'pvp_change':201,'pvp_imp':202}
   self.put(x,0);self.put(x+4,types.get(alias,0))
  elif off==0x1477a0:
   em.mem_write(x,bytes(em.mem_read(y,z)))
  elif off==0x2258d8:self.board_army.append(self.army())
  elif a==BASE+0x101a220:
   self.dave_available=True
   em.reg_write(UC_ARM_REG_PC,END);return
  elif 0x101a3d8<=off<0x101a3f4:return
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)

e=BattleEngine();e.run('offlineGarden')
assert e.get(M+0x15c)==0 and len(e.special)==(7 if 'offlineResidentialMode' in e.exports else 1)
e.dave_available=False;e.u.reg_write(UC_ARM_REG_R8,M)
e.u.reg_write(UC_ARM_REG_R5,next(i*64 for i,r in enumerate(e.special) if struct.unpack_from('<I',r,0)[0]==0x70000007))
e.run(0x101a3d8)
assert e.dave_available,'native map misclassified the untouched Dave house'
e.u.mem_write(M+0x100,b'\1');e.stub(0x1042fe8,M,0x70000001,3,0)
assert e.loads==[('arena_battle_test',0)]
e.stub(0x1042fe8,M,0x70000001,2,0)
assert bytes(e.u.mem_read(M+0x100,1))==b'\0' and len(e.loads)==2
e.stub(0x1042fe8,M,0x70000001,2,0);assert len(e.loads)==2
e.stub(0x9344a4,e.product(),1);e.train();e.advance(31)
e.run('offlineTrainingTick',e.get(M+0x20));assert e.held()==1
name=e.alloc(4);e.string(name,'arena_battle_test')
e.run('offlineBoardLoad',M+0xd000,name,0xffffffff)
assert e.board_army==[[(201,1)]] and e.aliases==['pvp_change']
# Re-entering must replace the transient army, never add another copy.
e.run('offlineBoardLoad',M+0xd000,name,0xffffffff)
assert e.board_army[-1]==[(201,1)] and e.held()==1
# Queue-only units cannot be deployed; other levels must not mutate the army.
e.train();e.run('offlineBoardLoad',M+0xd000,name,0xffffffff)
assert e.army()==[(201,1)] and e.queued()==1
other=e.alloc(4);e.string(other,'egypt4');before=e.army()
e.run('offlineBoardLoad',M+0xd000,other,0xffffffff);assert e.army()==before
result=dict(native_army_vector_assignment=True,trained_units_handed_to_battle=True,queued_units_excluded=True,reentry_replaces_not_accumulates=True,preview_confirmation_not_blocked=True,native_dave_click_challenge_available=True,runtime_game_verified=False)
(OUT/'v46-arm-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
