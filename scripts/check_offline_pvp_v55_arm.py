"""Run native base-panel copying, Dave preview handoff and return callbacks."""
from check_offline_pvp_v54_arm import ProgressionEngine,OUT,BOARD,MODULE
from check_offline_pvp_arm import BASE,M,END
from unicorn.arm_const import *
import struct,json

def f32(x):return struct.unpack('<f',struct.pack('<I',x))[0]
def bits(x):return struct.unpack('<I',struct.pack('<f',x))[0]
class DisplayEngine(ProgressionEngine):
 def hook(self,em,a,size,d):
  off=a-BASE;x,y,z,w=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  if 0x10191fc<=off<=0x1019230 or 0x290f08<=off<=0x290f28:return
  if off in (0x1013c38,0x290dd0):em.reg_write(UC_ARM_REG_PC,END);return
  if 0x10401f0<=off<0x1040a5c or 0x103eaf4<=off<0x103eb24 or 0x10412dc<=off<0x1041318 or 0x1041104<=off<0x1041270:return
  if off==0x15dea84:result=bits(f32(x)-f32(y))
  elif off==0x15dea88:result=bits(f32(x)+f32(y))
  elif off==0x15dec20:result=bits(x if x<0x80000000 else x-0x100000000)
  elif off==0x15df0f8:result=int(f32(x))
  elif off==0x15df0ac:result=int(f32(x)>f32(y))
  elif off==0x15de2dc:
   value=struct.unpack('<Q',struct.pack('<d',f32(x)))[0]
   em.reg_write(UC_ARM_REG_R1,value>>32);result=value&0xffffffff
  elif off==0x15de918:
   left=struct.unpack('<d',struct.pack('<II',x,y))[0];right=struct.unpack('<d',struct.pack('<II',z,w))[0];result=int(left>right)
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_R0,result);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)
 def panel(self):
  popup=self.alloc(0x160);self.u.reg_write(UC_ARM_REG_R10,popup);self.run(0x10191fc)
  return [self.get(popup+i) for i in (0x12c,0x130,0x134,0x138,0x13c,0x140)]

e=DisplayEngine();e.enter();assert e.panel()==[1000,2000,40,200,2000,20]
e.upgrade(1);e.advance(14400);e.run('offlineTrainingTick',e.get(M+0x20))
assert e.panel()==[1010,2600,50,280,2200,21]
e.stub(0x9344a4,e.product(),1);assert e.panel()==[6010,2600,50,280,2200,21]

# Dave map context's scout uses zero-id reason 4, with kind 1 retained.
d=DisplayEngine();d.enter();d.run('offlineGarden');d.train();d.advance(31);d.run('offlineTrainingTick',d.get(M+0x20))
d.put(M+0x104,0x70000007);d.put(M+0xfc,1);d.put(M+0xf8,1);d.u.mem_write(M+0x102,b'\1')
d.stub(0x1042fe8,M,0,4,0)
assert bytes(d.u.mem_read(M+0x100,1))==b'\1' and bytes(d.u.mem_read(M+0x102,1))==b'\0'
assert d.get(M+0xa8)==1
name=d.alloc(4);d.string(name,'arena_battle_test');d.run('offlineBoardLoad',BOARD,name,0xffffffff);d.live();d.put(MODULE+0xb0,2)
plants=d.get(M+0x84);loads=len(d.loads);d.stub(0x1042fe8,M,0,2,0)
assert d.starts==1 and d.get(MODULE+0xb0)==3 and d.get(M+0x84)==plants and len(d.loads)==loads
assert bytes(d.u.mem_read(M+0x100,1))==b'\0'

# The real zombie packet setter must still refund one card before the omitted effect.
card=e.alloc(0x180);e.put(card+0x154,2);e.u.reg_write(UC_ARM_REG_R4,card);e.run(0x290f08)
assert e.get(card+0x154)==3

# Execute the original AddEnergyEffect states 3 -> 4 -> 0 and its actual
# bound callback, including PVPSkillEnergyUI's native counter setter/event.
energy=DisplayEngine();ui=energy.alloc(0x140);effect=energy.alloc(0x60)
energy.put(ui+0xf0,100);energy.put(effect+0x10,3);energy.put(effect+0x40,bits(1000));energy.put(effect+0x44,bits(30))
energy.put(effect+0x4c,BASE+0x10412dc);energy.put(effect+0x50,0);energy.put(effect+0x54,ui);energy.put(effect+0x58,1);energy.put(effect+0x5c,BASE+0x103eaf4)
# Reuse the event bus fixture with the energy counter's own key and no listeners.
library=(OUT/'libSrc.so').read_bytes();delta=struct.unpack_from('<I',library,0x1041274)[0]
energy.put(M+0xa000+16,(BASE+0x1041154+delta)&0xffffffff);energy.put(M+0xa000+20,0);energy.put(M+0xa000+24,0)
energy.advance(1);energy.run(0x10401f0,effect);assert energy.get(effect+0x10)==4 and energy.get(ui+0xf0)==100
energy.advance(1);energy.run(0x10401f0,effect);assert energy.get(effect+0x10)==0 and energy.get(ui+0xf0)==130
energy.run(0x10401f0,effect);assert energy.get(ui+0xf0)==130,'energy callback repeated'
result=dict(native_own_base_context_copy_executed=True,level_two_details_and_purchase_refresh=True,dave_scout_keeps_preview=True,dave_preview_starts_in_place_without_duplicates=True,native_zombie_card_refund_preserved=True,native_energy_landing_and_actual_counter_callback_executed=True,energy_arrival_awards_once_without_landing_flash=True,prior_v54_checks=True,runtime_game_verified=False)
(OUT/'v55-arm-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
