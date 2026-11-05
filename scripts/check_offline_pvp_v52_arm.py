"""Execute native death accounting and the garden's original army-card refresh."""
from check_offline_pvp_v51_arm import SessionEngine,OUT,BOARD,MODULE
from check_offline_pvp_arm import BASE,M
from unicorn.arm_const import *
import json

class RecallEngine(SessionEngine):
 def __init__(self):
  super().__init__();self.map_cards=[]
  self.put(BASE+0x1822360,BASE+0x18a73a4) # ELF-relocated default empty TrainingEntry
 def hook(self,em,a,size,d):
  off=a-BASE;x,y,z=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
  if 0x108ed3c<=off<0x108eed8 or 0x108e930<=off<0x108eaa0 or 0x100918c<=off<0x10092d0 or 0x104e634<=off<0x104e814 or 0x1042f0c<=off<0x1042f24:return
  if off==0x4978b8:assert self.txt(self.get(y))=='pvp_change';result=201
  elif off in (0xf800d0,0x104d510):
   stride=8 if off==0xf800d0 else 32
   start,end=self.get(x),self.get(x+4);old=bytes(em.mem_read(start,end-start)) if start else b''
   p=self.alloc(len(old)+stride);em.mem_write(p,old+bytes(em.mem_read(y,stride)))
   self.put(x,p);self.put(x+4,p+len(old)+stride);self.put(x+8,p+len(old)+stride);result=0
  elif off in (0x104dfe4,0x104da80):result=0 # only one held type: sorting is inert
  elif off==0x1052150:self.map_cards.append(self.get(y+4));result=0
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_R0,result);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)
 def deaths(self,count):
  props=self.alloc(0x40);self.string(props+4,'pvp_change')
  entry=self.alloc(16);self.put(entry,props);self.put(entry+4,0);self.put(entry+8,0);self.put(entry+12,1)
  self.put(MODULE+0x60,entry);self.put(MODULE+0x64,entry+16);self.put(MODULE+0x68,entry+16)
  zombie=self.alloc(0x340);self.put(zombie+0xc8,props);self.put(zombie+0xcc,0);self.u.mem_write(zombie+0x323,b'\1')
  for _ in range(count):self.run(0x108ed3c,MODULE,zombie)
  assert self.get(entry+8)==count
  self.run(0x108e930,MODULE)
  assert self.army()==[(201,count)],'native death serializer gave an unexpected type/count'

def fixture():
 e=RecallEngine();e.run('offlineGarden');e.stub(0x9344a4,e.product(),1)
 for _ in range(3):e.train()
 ui,button,timer=e.training_ui();e.run('offlineTrainingDisplay',ui);e.stub(0x1059300,ui,1);e.confirm(timer)
 e.stub(0x1042fe8,M,0x70000001,3,0)
 name=e.alloc(4);e.string(name,'arena_battle_test');e.run('offlineBoardLoad',BOARD,name,0xffffffff);e.live()
 e.put(MODULE+0xb0,2);e.stub(0x1042fe8,M,0x70000001,2,0)
 e.run(0x1030a50,M+0x14300,2) # one unit placed, two still in the card
 return e

alive=fixture();alive.deaths(0);alive.stub(0x10448e8,M,0,0x70000001,2);alive.run('offlineTrainingTick',alive.get(M+0x20))
assert alive.held()==3,'surviving deployed zombie was not recalled'
dead=fixture();dead.deaths(1);dead.stub(0x10448e8,M,0,0x70000001,2);dead.run('offlineTrainingTick',dead.get(M+0x20))
assert dead.held()==2,'dead zombie was incorrectly recalled'

# Rebuild the same six-cell child list created by the native map constructor,
# then execute its real held-only filter and refresh loop.
ui=alive.alloc(0x340);camp=alive.get(M+0x20);alive.put(camp+8,0)
alive.run('offlineMapArmyPrepare',ui);assert alive.get(camp+8)==6
panel=alive.alloc(0xa0);alive.put(ui+0x2d4,panel);sentinel=panel+4
nodes=[alive.alloc(12) for _ in range(6)]
alive.put(sentinel,nodes[0]);alive.put(sentinel+4,nodes[-1])
for i,node in enumerate(nodes):
 alive.put(node,nodes[i+1] if i<5 else sentinel);alive.put(node+4,nodes[i-1] if i else sentinel);alive.put(node+8,alive.alloc(0xd0))
alive.run('offlineMapArmyReady',ui)
assert alive.map_cards==[3,0,0,0,0,0],alive.map_cards
result=dict(native_death_counter_and_serializer_executed=True,three_with_one_surviving_deployment_returns_three=True,three_with_one_death_returns_two=True,native_held_only_filter_and_map_refresh_executed=True,map_capacity_restored_before_cells_created=True,map_displays_three_and_empty_cells=True,previous_continuous_battle_checks=True,runtime_game_verified=False)
(OUT/'v52-arm-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
