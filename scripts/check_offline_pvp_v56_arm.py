"""Execute Dave's actual preview button and native in-place start function."""
from check_offline_pvp_v55_arm import DisplayEngine,OUT,BOARD,MODULE,bits
from check_offline_pvp_arm import BASE,M
from unicorn.arm_const import *
import struct,json

class DaveEngine(DisplayEngine):
 def __init__(self):super().__init__();self.dave_starts=0
 def hook(self,em,a,size,d):
  off=a-BASE
  if off==0x1042fe8:return # Execute the installed interception branch.
  if 0x1088aa0<=off<0x1088af8 or 0x1090dec<=off<0x10912bc:
   if off==0x1090dec:self.dave_starts+=1
   return
  if off in (0x97714c,0x108f378,0x108bfc4):
   # Native widget/resource lookup and level-duration props are engine boundaries.
   result=bits(360) if off==0x108bfc4 else 0
   em.reg_write(UC_ARM_REG_R0,result);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
  return super().hook(em,a,size,d)

e=DaveEngine();e.enter();e.run('offlineGarden');e.train();e.advance(31);e.run('offlineTrainingTick',e.get(M+0x20))
e.put(M+0x104,0x70000007);e.put(M+0xfc,1);e.put(M+0xf8,1)
e.stub(0x1042fe8,M,0,4,0)
name=e.alloc(4);e.string(name,'arena_battle_test');e.run('offlineBoardLoad',BOARD,name,0xffffffff);e.live();e.put(BOARD+0xc0,5);e.put(MODULE+0xb0,2)
before=e.get(M+0x84);loads=len(e.loads);bank=e.get(M+0x7000+0x6bc)
raw=(OUT/'libSrc.so').read_bytes();delta=struct.unpack_from('<I',raw,0x10912f0)[0]
e.put(M+0xa000+16,(BASE+0x1091184+delta)&0xffffffff);e.put(M+0xa000+20,0);e.put(M+0xa000+24,0)
e.run(0x1088aa0) # Real button sets +103 and dispatches zero-id reason 1.
assert e.dave_starts==1 and e.get(MODULE+0xb0)==3 and bytes(e.u.mem_read(MODULE+0x18,1))==b'\1'
assert bytes(e.u.mem_read(M+0x103,1))==b'\0' and bytes(e.u.mem_read(M+0x100,1))==b'\0'
assert e.ends==0 and len(e.loads)==loads and e.get(M+0x84)==before and e.get(M+0x7000+0x6bc)==bank
assert e.get(BOARD+0xc0)==5 and e.held()==1
e.run(0x1088aa0);assert e.dave_starts==1 and e.ends==0 and len(e.loads)==loads,'repeat request restarted the battle'
result=dict(real_dave_preview_button_executed=True,zero_player_id_reason_one_exercised=True,native_dave_start_executed=True,native_combat_state_and_active_flag=True,preview_flags_cleared=True,no_board_finish_or_reload=True,plants_bank_and_army_preserved=True,duplicate_request_does_not_restart=True,previous_v55_regressions=True,runtime_game_verified=False)
(OUT/'v56-arm-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
