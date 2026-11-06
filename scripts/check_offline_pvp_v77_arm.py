"""Business/residence separation, native detail fields and offline boundaries."""
from check_offline_pvp_v76_arm import LifecycleEngine,OUT
from check_offline_pvp_arm import BASE,M,PROFILE,END
from unicorn.arm_const import *
import json

class BusinessEngine(LifecycleEngine):
 def hook(self,em,a,size,d):
  off=a-BASE
  if 0x1019170<=off<0x10191f0 or 0x1060c1c<=off<0x1060c54:return
  return super().hook(em,a,size,d)
 def shops(self):return list(range(self.get(M+0x110),self.get(M+0x114),64))
 def shop_panel(self,p):
  ui=self.alloc(0x160);self.put(ui+0xa4,3)
  self.put(ui+0xac,self.get(p+48));self.put(ui+0xa8,self.get(p+52))
  self.u.reg_write(UC_ARM_REG_R10,ui);self.run(0x1019170)
  return ui,[self.get(ui+o) for o in (0x12c,0x130,0x134,0x138,0x13c,0x140,0x148)]

def check_businesses():
 e=BusinessEngine();e.enter();funds=(e.get(M+4),e.get(M+8),e.gems,{k:bytes(v) for k,v in e.files.items() if not k.endswith('.neighbors')})
 e.run('offlineGarden');assert len(e.shops())==2 and len(e.residents())==7+int('offlineRandomNeighborsMode' in e.exports)
 houseplots={(e.get(p+28),e.get(p+32)) for p in e.residents()}|{(1,2)}
 slots=[]
 for i,p in enumerate(e.shops()):
  assert e.get(p)==0x71000001+i and e.get(p+8)==e.get(p+12)==0
  assert (e.get(p+48),e.get(p+52)) not in houseplots
  e.run(0x1060c1c,p);slots.append(e.u.reg_read(UC_ARM_REG_R0))
  ui,fields=e.shop_panel(p);assert fields==[0,2000,0,0,2000,0,1]
  for button in ((200,201,202,204) if 'offlineBusinessScoutMode' in e.exports else (200,201,202,204,205)):
   count=len(e.messages);e.stub(0x100b3d8,ui,button)
   assert e.messages[count:]==['business-action-pending']
   assert e.u.reg_read(UC_ARM_REG_R0)==ui,'void native callback arguments not preserved'
  e.run('offlineBusinessAction',ui,203);assert e.u.reg_read(UC_ARM_REG_R0)==0
  if 'offlineBusinessBattleMode' in e.exports:
   e.run('offlineBusinessRaidInput',ui);assert e.u.reg_read(UC_ARM_REG_R0)==0
  else:
   count=len(e.messages);e.stub(0x101a564,ui,0)
   assert e.messages[count:]==['business-raid-pending']
 assert slots==[9,10] and len(set(slots))==2
 e.run('offlineGarden');assert len(e.shops())==2 and len(e.residents())==7+int('offlineRandomNeighborsMode' in e.exports)
 assert (e.get(M+4),e.get(M+8),e.gems,{k:bytes(v) for k,v in e.files.items() if not k.endswith('.neighbors')})==funds
 # A residence/own base is never intercepted by the shop-only button guard.
 for kind,zone,pos in ((5,1,3),(4,1,2),(5,1,1),(3,6,3)):
  ui=e.alloc(0x160);e.put(ui+0xa4,kind);e.put(ui+0xac,zone);e.put(ui+0xa8,pos)
  e.run('offlineBusinessAction',ui,205);assert e.u.reg_read(UC_ARM_REG_R0)==0
  e.run('offlineBusinessRaidInput',ui);assert e.u.reg_read(UC_ARM_REG_R0)==0
 # Preserve a foreign business on the reserved plot, including its title.
 foreign=e.shops()[0];e.put(foreign,777);e.put(foreign+8,778)
 e.run('offlineGarden');assert len(e.shops())==2 and e.get(e.shops()[0])==777
 ui,_=e.shop_panel(e.shops()[0]);e.run('offlineBusinessAction',ui,205)
 assert e.u.reg_read(UC_ARM_REG_R0)==0
 r=BusinessEngine();r.copy_state(e);r.enter();r.run('offlineGarden')
 assert len(r.shops())==2 and len(r.residents())==7+int('offlineRandomNeighborsMode' in r.exports)
 early=BusinessEngine();early.put(PROFILE+0x75c,1);early.run('offlineGarden')
 assert not early.shops() and not early.residents(),'tutorial map changed'
 report=dict(independent_unowned_shop_records=True,native_slot_mapping_executed=True,
 no_collision_with_houses_or_own_base=True,native_business_detail_copy_executed=True,
 repeat_entry_and_restart_no_duplicate=True,no_wallet_or_save_mutation=True,
 foreign_shop_preserved=True,unrestored_actions_cannot_reach_network=True,
 residential_own_dave_buttons_not_intercepted=True,tutorial_map_preserved=True,
 ownership_garrison_rent_not_implemented=True,runtime_game_verified=False)
 (OUT/'v77-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
