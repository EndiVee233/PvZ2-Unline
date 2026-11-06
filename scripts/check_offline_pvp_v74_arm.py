"""Check native residential record ABI, panel selection and local combat routing."""
from check_offline_pvp_v73_arm import ClockEngine,OUT
from check_offline_pvp_v60_arm import board,result,return_map
from check_offline_pvp_arm import BASE,M,PROFILE,GM,END
from unicorn.arm_const import *
import json,struct

class ResidenceEngine(ClockEngine):
 def __init__(self):super().__init__();self.opened=[];self.messages=[]
 def hook(self,em,a,size,d):
  off=a-BASE
  # Payload instructions need no engine boundary emulation. Avoid walking
  # every historical UI fixture (and its register reads) for each instruction.
  if off>=0x1a00000 or a==END:return
  if off==0x1046a04:
   source=em.reg_read(UC_ARM_REG_R1);item=bytes(em.mem_read(source,64))
   begin,end=self.get(M+0x110),self.get(M+0x114)
   rows=[bytes(em.mem_read(p,64)) for p in range(begin,end,64)]
   rows=[r for r in rows if r[48:56]!=item[48:56]]+[item]
   self.records=rows;p=self.alloc(len(rows)*64);em.mem_write(p,b''.join(rows))
   self.put(M+0x110,p);self.put(M+0x114,p+len(rows)*64);self.put(M+0x118,p+len(rows)*64)
   em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
  if off==0x147adc:
   self.messages.append(self.txt(em.reg_read(UC_ARM_REG_R3)))
   return super().hook(em,a,size,d)
  if 0x1060b68<=off<0x1060bc0 or 0x10190f4<=off<0x1019170 or 0x101a20c<=off<0x101a234:return
  if off==0x1019668:
   self.opened.append(tuple(em.reg_read(r) for r in (UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)))
   em.reg_write(UC_ARM_REG_PC,END);return
  return super().hook(em,a,size,d)
 def residents(self):return list(range(self.get(M+0x128),self.get(M+0x12c),64))
 def native_panel(self,record):
  ui=self.alloc(0x150);self.put(ui+0xac,self.get(record+28));self.put(ui+0xa8,self.get(record+32))
  self.u.reg_write(UC_ARM_REG_R10,ui);self.run(0x10190f4)
  return [self.get(ui+o) for o in (0x12c,0x130,0x134,0x138,0x13c,0x140,0x148,0x14c)]
 def selected(self,p):
  self.put(M+0x104,self.get(p));self.put(M+0xfc,self.get(p+28));self.put(M+0xf8,self.get(p+32))

def check_residences():
 e=ResidenceEngine();e.enter();assert not e.records and e.panel()==[1000,2000,40,200,2000,20]
 e.run('offlineGarden')
 def only_businesses():
  rows=range(e.get(M+0x110),e.get(M+0x114),64)
  assert all(e.get(p) in (0x71000001,0x71000002) for p in rows),'residences leaked into businesses'
 only_businesses()
 rich='offlineRandomNeighborsMode' in e.exports
 rows=e.residents();assert len(rows)==7+int(rich)
 for i,p in enumerate(rows):
  id=e.get(p);kind=e.get(p+36)
  e.run(0x1060b68,p);slot=e.u.reg_read(UC_ARM_REG_R0);assert slot<20 and slot!=1
  e.run(0x1060ba0,p);assert e.u.reg_read(UC_ARM_REG_R0)==int(id==0x70000007)
  assert e.get(e.get(p+8)-12)>0,'empty residential name'
  if id==0x70000007:assert kind==4 and e.get(p+48)==6;continue
  assert kind==1 and (rich or e.get(p+16)==0) and e.get(p+20)==0 and e.get(p+24)==100
  assert e.native_panel(p)==[100,0,0,0,0,0,1,0],'merchant production/capacity fields shown'
  # Execute the real map-click branch into the native kind-5 panel opener.
  e.u.reg_write(UC_ARM_REG_R8,M);e.u.reg_write(UC_ARM_REG_R5,i*64);e.u.reg_write(UC_ARM_REG_R6,e.alloc(0x300))
  e.run(0x101a20c);assert e.opened[-1]==(5,e.get(p+28),e.get(p+32))
 e.run('offlineGarden');assert len(e.residents())==7+int(rich);only_businesses()
 # Migration removes only our former fake businesses, retaining foreign shops.
 first=rows[0];old=e.alloc(64*3);e.u.mem_write(old,bytes(64*3))
 e.put(old,e.get(first));e.put(old+48,e.get(first+28));e.put(old+52,e.get(first+32));e.string(old+16,'old fake',True)
 e.put(old+64,777);e.put(old+64+48,3);e.put(old+64+52,2);e.string(old+64+16,'real shop',True)
 e.put(old+128,42);e.put(old+128+48,1);e.put(old+128+52,2);e.string(old+128+16,'duplicate own',True)
 e.put(M+0x110,old);e.put(M+0x114,old+192);e.put(M+0x118,old+192);e.run('offlineGarden')
 remaining=list(range(e.get(M+0x110),e.get(M+0x114),64))
 foreign=next(p for p in remaining if e.get(p)==777)
 assert e.get(foreign+48)==3 and e.get(e.get(foreign+16)-12)>0
 assert all(e.get(p) in (777,0x71000001,0x71000002) for p in remaining)
 # Real residential requests use selected-id, zero player-id, reasons 4/1.
 f=ResidenceEngine();f.enter();f.run('offlineGarden')
 for _ in range(3):f.train()
 f.advance(91);f.run('offlineTrainingTick',f.get(M+0x20));assert f.held()==3
 p=f.residents()[0];f.selected(p);before=f.get(M+4)
 f.stub(0x1042fe8,M,0,4,0);board(f)
 assert f.get(M+4)==before and f.get(M+0xa8)==2 and f.get(M+0xf4)==0x70000001
 plants=f.get(M+0x84);loads=len(f.loads)
 f.stub(0x1042fe8,M,0,1,0)
 assert f.get(M+4)==before-1 and f.starts==1 and f.get(M+0x84)==plants and len(f.loads)==loads
 f.stub(0x1042fe8,M,0,1,0);assert f.get(M+4)==before-1 and f.starts==1
 f.deaths(0);result(f,0);return_map(f);assert f.held()==3 and f.get(M+4)==before-1
 # Direct raid, then result/return, uses the same accepted settlement kind.
 f.put(GM+0x984,25);f.put(GM+0xa24,0xffffffff)
 f.selected(f.residents()[1]);before=f.get(M+4);f.stub(0x1042fe8,M,0,1,0);board(f)
 assert f.get(M+4)==before-1,(f.get(M+4),before,f.messages[-12:]);f.deaths(0);result(f,1,0x70000002);return_map(f)
 assert f.get(M+4)==before+32 and f.held()==3
 report=dict(residential_map_records_and_cup_labels=True,native_residential_panel_selection=True,
 native_panel_reward_fields_not_business_production=True,own_base_dedicated_panel_preserved=True,
 legacy_fake_shop_cleanup_preserves_foreign_shops=True,zero_id_residential_scout_and_raid_routing=True,
 preview_in_place_no_duplicate_plants_or_fee=True,direct_raid_settlement_and_survivors_preserved=True,
 runtime_game_verified=False)
 (OUT/'v74-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))

if __name__=='__main__':
 check_residences()
 from check_offline_pvp_v73_arm import check_clock,check_manual_refresh
 check_manual_refresh();check_clock()
 from check_offline_exchange_sampler_arm import check
 check()
