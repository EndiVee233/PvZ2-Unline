"""Execute rich roster generation, native refresh, persistence and history ABI."""
import sys,importlib,struct,json,collections
from check_offline_pvp_v76_focused import Definitions

def check_neighbors(c):
 from check_offline_pvp_v81_arm import GarrisonEngine
 from check_offline_pvp_arm import BASE,M,PM,END
 from check_offline_pvp_v93_focused import key,crc,old_record
 from check_offline_pvp_v60_arm import board,result,return_map
 from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_SP
 catalogue=json.loads((c.OUT/'generated/neighbor-catalogue.json').read_text(encoding='utf8'))
 plants={p['id']:p for p in catalogue['plants']}
 class Neighbors(GarrisonEngine):
  def __init__(self):super().__init__();self.reopened=[]
  def hook(self,em,a,size,d):
   if a==BASE+0x1019668:
    self.reopened.append(tuple(em.reg_read(r) for r in (UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)))
    em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
   if a==BASE+0x1013a3c:
    ui,map_,kind,zone=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
    for o,v in [(0xa4,kind),(0xa8,self.get(em.reg_read(UC_ARM_REG_SP))),(0xac,zone),(0xc0,map_)]:self.put(ui+o,v)
    em.reg_write(UC_ARM_REG_R0,ui);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
   return super().hook(em,a,size,d)
  def roster_key(self):return next(k for k in self.files if k.endswith(f'{self.get(PM+0x74):08x}.neighbors'))
  def roster(self):
   raw=self.files[self.roster_key()]
   return {struct.unpack_from('<I',raw,o)[0]:bytes(raw[o:o+740]) for o in range(24,len(raw),740)}
  def panel(self,id):
   row=next(p for p in self.residents() if self.get(p)==id);ui=self.alloc(0x150)
   self.stub(0x10196d0,ui,M+0x18000,5,self.get(row+28),self.get(row+32));return ui
  def replace(self,id):
   p=self.panel(id);self.stub(0x100b3d8,p,204);return p
 def decode(raw):
  id,seed,kind,cups,count=struct.unpack_from('<5I',raw)
  ps=[struct.unpack_from('<4I',raw,20+i*16) for i in range(count)]
  return id,seed,kind,cups,ps
 def validate(raw):
  id,seed,kind,cups,ps=decode(raw)
  if not seed:assert not ps;return
  assert 5<=len(ps)<=45 and len({(r,c) for _,_,r,c in ps})==len(ps)
  counts=collections.Counter(p[0] for p in ps);grades={};spent=0
  for type,grade,r,c in ps:
   spec=plants[type];assert 0<=r<5 and 0<=c<9 and 1<=grade<=spec['max_level']
   assert grades.setdefault(type,grade)==grade;spent+=spec['cost']
  if kind==1:assert cups==999 and len(ps)==45 and len(counts)==1 and all(g==plants[t]['max_level'] for t,g,_,_ in ps)
  else:assert max(counts.values())<=10 and spent<=5500 and len(set(grades.values()))>1
  if kind==2:assert cups>=60
  if kind==3:assert cups>=40
  mask={2:2,3:4,4:1,5:8,6:32,7:16}.get(kind,0)
  if mask:assert any(plants[t]['flags']&mask for t,_,_,_ in ps),'theme absent'
 e=Neighbors();e.enter();e.run('offlineGarden');initial=e.roster();assert len(e.residents())==4
 # Slot 5 is the final house in area 1; first visit always has the FBI guest.
 fbi=next(p for p in e.residents() if e.get(p+28)==1 and e.get(p+32)==5)
 fixed=decode(initial[e.get(fbi)]);assert fixed[2:4]==(1,999) and {q[0] for q in fixed[4]}=={34}
 for raw in initial.values():validate(raw)
 # Execute the exact roll function: independent 2%, 3%, 3%, 3%, 2%, 2%, 2%.
 rolls=[]
 for n in range(100):e.run('offlineNeighborRoll',n);rolls.append(e.u.reg_read(UC_ARM_REG_R0))
 assert collections.Counter(rolls)=={0:83,1:2,2:3,3:3,4:3,5:2,6:2,7:2}
 # Sample the actual ARM generator, including every theme and full-board case.
 output=e.alloc(740);covered=set();strength=[]
 for i in range(192):
  kind=1+i%8;e.run('offlineNeighborGenerate',output,0x70000001,(i+1)*104729,kind)
  raw=bytes(e.u.mem_read(output,740));validate(raw);_,_,k,cups,ps=decode(raw)
  covered.update(t for t,_,_,_ in ps);strength.append((cups,sum(plants[t]['cost'] for t,_,_,_ in ps),sum(g for _,g,_,_ in ps)/len(ps)))
 assert len(covered)>=85,(len(covered),set(plants)-covered)
 # Free refresh changes one plot, saves before replacing its native record,
 # and refuses duplicate/stale callbacks. Other residences remain identical.
 target=0x70000002;funds=(e.get(M+4),e.get(M+8),e.gems);before=e.roster();panel=e.replace(target);after=e.roster()
 assert before[target]!=after[target] and all(before[k]==after[k] for k in before if k!=target)
 assert (e.get(M+4),e.get(M+8),e.gems)==funds and e.reopened[-1][0]==5
 saved=bytes(e.files[e.roster_key()]);e.stub(0x100b3d8,panel,204);assert bytes(e.files[e.roster_key()])==saved
 # Full roster and native map projection survive process restart.
 r=Neighbors();r.copy_state(e);r.enter();r.run('offlineGarden');assert r.roster()==after
 for p in r.residents():
  if r.get(p)==0x70000007:continue
  assert r.get(p+16)==decode(after[r.get(p)])[3]
 old=r.roster();r.failwrite=True;r.replace(target);assert r.roster()==old and not r.reopened
 r.failwrite=False;r.replace(target);assert r.roster()[target]!=old[target]
 # Preview applies all 45 FBI cells and the actual per-species tiers.
 row=next(p for p in r.residents() if r.get(p)==e.get(fbi));r.selected(row);r.stub(0x1042fe8,M,0,4,0)
 raw=r.roster()[r.get(row)];ps=decode(raw)[4]
 positions=[struct.unpack('<3I',r.u.mem_read(p,12)) for p in range(r.get(M+0x84),r.get(M+0x88),12)]
 infos={r.get(p):r.get(p+4) for p in range(r.get(M+0x90),r.get(M+0x94),16)}
 assert positions==[(t,a,b) for t,g,a,b in ps] and infos=={t:g for t,g,a,b in ps}
 # Legacy three-area migration guarantees a special guest in areas 2 and 3.
 m=Neighbors();m.files={key(e):old_record(e,7,100000)};m.enter();m.run('offlineGarden')
 assert len(m.residents())==8
 for zone in (2,3):assert any(m.get(p+28)==zone and decode(m.roster()[m.get(p)])[2] for p in m.residents() if m.get(p)!=0x70000007)
 # All newly paid areas get a special on unlock, without editing a game save.
 for zone in (4,5,6):
  ui=m.alloc(0x150);m.stub(0x10196d0,ui,M+0x18000,0,zone,0);m.put(ui+0x144,{4:23500,5:31000,6:39000}[zone]);m.stub(0x100b3d8,ui,202)
  assert any(m.get(p+28)==zone and decode(m.roster()[m.get(p)])[2] for p in m.residents() if m.get(p)!=0x70000007)
 assert len(m.residents())==17
 # A different player gets independent initial neighbors; returning restores.
 saved=m.roster();m.put(PM+0x74,43);m.put(M+0x20,0);m.enter();m.run('offlineGarden');assert m.roster()!=saved and len(m.residents())==4
 m.put(PM+0x74,42);m.put(M+0x20,0);m.enter();m.run('offlineGarden');assert m.roster()==saved
 # Corruption is rejected, never silently resetting opponents.
 b=Neighbors();b.copy_state(e);bad=bytearray(b.files[e.roster_key()]);bad[100]^=1;b.files[e.roster_key()]=bad
 b.enter();b.run('offlineGarden');assert b.files[e.roster_key()]==bad and not b.residents()
 report=dict(catalogue_available=catalogue['available'],eligible=catalogue['eligible'],sampled_species=len(covered),samples=192,exact_special_probabilities=True,first_area_fbi_full_board=True,new_areas_guaranteed_special=True,budget5500_and_ten_per_species=True,mixed_per_species_tiers=True,native_preview_45_cells_and_tiers=True,refresh_atomic_free_single_plot=True,restart_profile_scope=True,corruption_rejected=True,runtime_game_verified=False)
 (c.OUT/'v95-neighbor-checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':
 sys.meta_path.insert(0,Definitions());c=importlib.import_module('check_offline_pvp_v82_arm')
 check_neighbors(c)
 p=importlib.import_module('check_offline_pvp_v93_focused');p.check_regions(c);p.accepted_legacy_fixtures()
 importlib.import_module('check_offline_pvp_v94_focused').check_history(c)
 importlib.import_module('check_offline_pvp_v91_focused').check_collection(c)
 importlib.import_module('check_offline_pvp_v90_focused').check_production(c)
 c.check_reposition();c.check_capture();c.check_scout();c.check_ownership();c.check_businesses()
 old=importlib.import_module('check_offline_pvp_v76_arm');old.check_lifecycle();old.check_defense();old.check_residences()
