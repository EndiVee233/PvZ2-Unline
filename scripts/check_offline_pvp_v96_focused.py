"""Unique visible guests, legacy roster cleanup and exhausted-area fallback."""
import sys,importlib,json,struct,collections
from check_offline_pvp_v76_focused import Definitions

def roster_crc(raw):
 h=2166136261
 for i,v in enumerate(raw):
  if not 20<=i<24:h=((h^v)*16777619)&0xffffffff
 struct.pack_into('<I',raw,20,h);return raw

def check_unique(c):
 from check_offline_pvp_v81_arm import GarrisonEngine
 from check_offline_pvp_v93_focused import key,old_record
 from check_offline_pvp_arm import BASE,M,END
 from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_SP
 class Unique(GarrisonEngine):
  def hook(self,em,a,size,d):
   if a==BASE+0x1013a3c:
    ui,map_,kind,zone=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
    for o,v in [(0xa4,kind),(0xa8,self.get(em.reg_read(UC_ARM_REG_SP))),(0xac,zone),(0xc0,map_)]:self.put(ui+o,v)
    em.reg_write(UC_ARM_REG_R0,ui);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
   if a==BASE+0x1019668:
    em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1);return
   return super().hook(em,a,size,d)
  def roster_key(self):return next(k for k in self.files if k.endswith('.neighbors'))
  def entries(self):return [bytes(self.files[self.roster_key()][o:o+740]) for o in range(24,11864,740)]
  def action(self,kind,zone,pos,button,price=0):
   ui=self.alloc(0x150);self.stub(0x10196d0,ui,M+0x18000,kind,zone,pos);self.put(ui+0x144,price);self.stub(0x100b3d8,ui,button)
 catalogue=json.loads((c.OUT/'generated/neighbor-catalogue.json').read_text(encoding='utf8'))
 banned={'sunflower','twinsunflower','sunshroom','birthsunflower','sunbean','toadstool','saucer'}
 assert not banned&{p['name'] for p in catalogue['plants']} and banned<=catalogue['omitted'].keys()
 forbidden={1,35,54,55,88,99,308}
 def check(e):
  assert struct.unpack_from('<I',e.files[e.roster_key()],4)[0]==2
  kinds=[]
  for entry in e.entries():
   _,seed,kind,cups,count=struct.unpack_from('<5I',entry)
   if not seed:continue
   if kind>1:kinds.append(kind)
   assert all(struct.unpack_from('<I',entry,20+k*16)[0] not in forbidden for k in range(count))
  assert len(kinds)==len(set(kinds)),kinds
 # Create a public synthetic pre-change wallet; no actual player data is used.
 seed=Unique();seed.enter();wallet=old_record(seed,7,200000)
 initial=Unique();initial.files={key(seed):wallet};initial.enter();initial.run('offlineGarden');check(initial)
 # Build a valid legacy v1 file with two Liu Kun guests and a sunflower.
 legacy=bytearray(initial.files[initial.roster_key()]);struct.pack_into('<I',legacy,4,1)
 output=initial.alloc(740);live=[i for i,p in enumerate(initial.entries()) if struct.unpack_from('<I',p,4)[0] and struct.unpack_from('<I',p,8)[0]!=1]
 for i in live[:2]:
  id=struct.unpack_from('<I',legacy,24+740*i)[0];initial.run('offlineNeighborGenerate',output,id,1009+i,2)
  legacy[24+740*i:24+740*(i+1)]=bytes(initial.u.mem_read(output,740))
 # Sunflower replaces one cell; tier 1 differs from the remaining high tiers.
 struct.pack_into('<II',legacy,24+740*live[0]+20,1,1);roster_crc(legacy)
 m=Unique();m.files={key(seed):wallet,initial.roster_key():legacy};m.enter();m.failwrite=True;m.run('offlineGarden')
 assert bytes(m.files[m.roster_key()])==legacy and not m.residents(),'failed migration partially replaced the roster'
 m.failwrite=False;m.run('offlineGarden');check(m)
 assert sum(struct.unpack_from('<I',p,8)[0]==2 for p in m.entries())==1
 # Saved upgraded files remain stable across restarting; no repeat migration.
 r=Unique();r.copy_state(m);r.enter();r.run('offlineGarden');assert r.entries()==m.entries()
 # Fill all six non-FBI guests in the seven first-three-area residential slots.
 full=bytearray(m.files[m.roster_key()]);live=[i for i,p in enumerate(m.entries()) if struct.unpack_from('<I',p,4)[0] and struct.unpack_from('<I',p,8)[0]!=1]
 assert len(live)>=6
 for kind,i in zip(range(2,8),live):
  id=struct.unpack_from('<I',full,24+i*740)[0];m.run('offlineNeighborGenerate',output,id,9001+i,kind)
  full[24+i*740:24+(i+1)*740]=bytes(m.u.mem_read(output,740))
 roster_crc(full)
 all_=Unique();all_.files={key(seed):wallet,m.roster_key():full};all_.enter();all_.run('offlineGarden');check(all_)
 all_.action(0,4,0,202,23500);check(all_)
 row=next(p for p in all_.residents() if all_.get(p+28)==4 and all_.get(p+32)==1)
 entry=next(p for p in all_.entries() if struct.unpack_from('<I',p)[0]==all_.get(row))
 assert struct.unpack_from('<I',entry,8)[0]==1,'exhausted special pool did not choose FBI'
 # Repeat replacement against occupied guests: collisions fall back to normal,
 # and the sole eligible same-kind target can be replaced without duplication.
 for n in range(40):
  all_.action(5,1,3,204);check(all_)
 assert sum(struct.unpack_from('<I',p,8)[0]==1 for p in all_.entries())>=2,'multiple FBI guests incorrectly blocked'
 # Malformed v2 duplicates are rejected, never silently fixed as legacy data.
 invalid=bytearray(full);struct.pack_into('<I',invalid,24+live[1]*740+8,2);roster_crc(invalid)
 bad=Unique();bad.files={key(seed):wallet,m.roster_key():invalid};bad.enter();bad.run('offlineGarden')
 assert not bad.residents() and bytes(bad.files[bad.roster_key()])==invalid
 report=dict(non_fbi_unique_across_visible_areas=True,new_area_unseen_first_fbi_when_exhausted=True,multiple_fbi_allowed=True,replacement_collision_cannot_duplicate=True,legacy_v1_banned_and_duplicate_cleanup=True,migration_atomic_failure_retry=True,restart_keeps_cleaned_roster=True,v2_corruption_rejected=True,sun_producers_and_saucer_removed=True,eligible=catalogue['eligible'],runtime_game_verified=False)
 (c.OUT/'v96-unique-checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':
 sys.meta_path.insert(0,Definitions());c=importlib.import_module('check_offline_pvp_v82_arm')
 check_unique(c)
 importlib.import_module('check_offline_pvp_v95_focused').check_neighbors(c)
 p=importlib.import_module('check_offline_pvp_v93_focused');p.check_regions(c);p.accepted_legacy_fixtures()
 importlib.import_module('check_offline_pvp_v94_focused').check_history(c)
 importlib.import_module('check_offline_pvp_v91_focused').check_collection(c)
 importlib.import_module('check_offline_pvp_v90_focused').check_production(c)
 c.check_reposition();c.check_capture();c.check_scout();c.check_ownership();c.check_businesses()
 old=importlib.import_module('check_offline_pvp_v76_arm');old.check_lifecycle();old.check_defense();old.check_residences()
