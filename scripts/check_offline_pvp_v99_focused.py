"""Silent policy/revenge checks on public synthetic data, never actual saves."""
import sys,importlib,json,struct
from check_offline_pvp_v76_focused import Definitions

def check_policy(c):
 from check_offline_pvp_v81_arm import GarrisonEngine
 from check_offline_pvp_arm import M
 from unicorn.arm_const import UC_ARM_REG_R0
 e=GarrisonEngine();e.enter();output=e.alloc(8);last=(10001,10001);examples={}
 for power in range(1153):
  e.run('offlineSilentOdds',power,output);attack,win=struct.unpack('<II',e.u.mem_read(output,8))
  assert 0<=win<=attack<=10000 and attack<=last[0] and win<=last[1]
  last=(attack,win)
  if power in (0,5,10,35,45,405):examples[power]={'attacked_bp':attack,'attacker_win_bp':win,'attacker_loss_bp':attack-win}
 assert examples[5]=={'attacked_bp':1000,'attacker_win_bp':500,'attacker_loss_bp':500}
 assert examples[0]['attacked_bp']>examples[5]['attacked_bp']>examples[405]['attacked_bp']
 e.run('offlineSilentHomePower');assert e.u.reg_read(UC_ARM_REG_R0)==0xffffffff,'missing defense treated as a real empty line'
 e.run('offlineGarden');e.own();e.arrangement(2,1,2);e.save();e.request(3)
 e.run('offlineSilentHomePower');assert e.u.reg_read(UC_ARM_REG_R0)==1
 e.own();info=e.get(M+0x90);e.put(info+4,5);e.save();e.request(3)
 e.run('offlineSilentHomePower');assert e.u.reg_read(UC_ARM_REG_R0)==9
 (c.OUT/'v99-policy-checks.json').write_text(json.dumps({'monotone_all_strengths':True,'reference_five_tier_one':True,'saved_defense_only':True,'tier_increases_strength':True,'examples':examples,'runtime_game_verified':False},indent=2)+'\n')
 print('PASS: 1153 monotonic defense strengths, reference odds, saved tiers')

def check_revenge(c):
 from check_offline_pvp_v81_arm import GarrisonEngine
 from check_offline_pvp_v93_focused import key,crc
 from check_offline_pvp_v60_arm import board,result,return_map
 from check_offline_pvp_arm import BASE,M,GM,PM,END
 from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_R4
 ns=0x4c4f434c
 class Revenge(GarrisonEngine):
  def __init__(self):super().__init__();self.closed=0;self.buttons=[]
  def hook(self,em,a,size,d):
   if a==BASE+0x105b774:
    em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR));return
   if a==END+0x900:
    self.closed+=1;em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR));return
   if a in (END+0x910,END+0x920):
    self.buttons.append((a,em.reg_read(UC_ARM_REG_R1)));em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR));return
   return super().hook(em,a,size,d)
  def open(self):
   ui=self.alloc(0x100);table=self.alloc(0x190);self.put(table+0x17c,END+0x900);self.put(ui,table);self.put(BASE+0x18a54c0,ui);self.run('offlineHistoryLoad',ui)
   return ui
  def row(self,serial):
   row=self.alloc(0xd8);self.put(row+0xa8,serial);self.put(row+0xac,ns)
   table=self.alloc(0xb0);self.put(table+0x8c,END+0x910);self.put(table+0xa4,END+0x920)
   for offset in (0xb0,0xb4):button=self.alloc(0x180);self.put(button,table);self.put(row+offset,button)
   self.run('offlineHistoryRowReady',row);return row
 seed=Revenge();seed.enter();seed.run('offlineGarden');target=seed.get(seed.residents()[0]);raw=bytearray(seed.files[key(seed)])
 assert len(raw)==2828
 npc=seed.alloc(740);frozen=seed.alloc(8);seed.run('offlineNeighborGenerate',npc,target,123456,1);seed.run('offlineFreezeEncounter',npc,frozen)
 assert seed.u.reg_read(UC_ARM_REG_R0)==1;lo,hi=struct.unpack('<II',seed.u.mem_read(frozen,8))
 # Public synthetic past defense: no real user progress is read or edited.
 serial=struct.unpack_from('<I',raw,20)[0]+1;struct.pack_into('<I',raw,20,serial);struct.pack_into('<I',raw,464,1)
 struct.pack_into('<6I',raw,468,serial,seed.now,target,3,0,3);struct.pack_into('<I',raw,708,123456);struct.pack_into('<I',raw,748,1);struct.pack_into('<II',raw,952,lo,hi);crc(raw)
 e=Revenge();e.files={k:bytearray(v) for k,v in seed.files.items()};e.files[key(seed)]=raw;e.enter();e.run('offlineGarden');e.open();row=e.row(serial)
 assert e.buttons[-4:]==[(END+0x910,0),(END+0x920,1),(END+0x910,1),(END+0x920,0)],e.buttons
 funds=(e.get(M+4),e.get(M+8),e.gems,e.held());e.stub(0x105c06c,row,101)
 assert e.closed==1 and bytes(e.u.mem_read(M+0x100,1))==b'\1'
 assert (e.get(M+4),e.get(M+8),e.gems,e.held())==funds,'revenge scout charged money/army'
 plants=e.plants();assert len(plants)==45*12 and all(struct.unpack_from('<I',plants,p)[0]==struct.unpack_from('<I',plants,0)[0] for p in range(0,len(plants),12))
 assert struct.unpack_from('<I',e.files[key(e)],912)[0]==0,'scouting prematurely consumed revenge'
 board(e);e.request(4);e.run('offlineTrainingTick',e.get(M+0x20));assert e.scenes[-1]==25
 e.open();e.buttons=[];e.row(serial);assert e.buttons[-2:]==[(END+0x910,1),(END+0x920,0)]
 # The opportunity is consumed atomically with a real paid attack, not with
 # opening the row, viewing the immutable formation or cancelling the scout.
 e.train();e.advance(31);e.run('offlineTrainingTick',e.get(M+0x20));assert e.held()==1
 e.open();row=e.row(serial);e.stub(0x105c06c,row,101);board(e)
 coins=e.get(M+4);loads=len(e.loads);e.stub(0x1042fe8,M,0,1,0)
 assert e.get(M+4)==coins-1 and len(e.loads)==loads
 assert struct.unpack_from('<I',e.files[key(e)],912)[0]==1
 e.run(0x1030a50,M+0x14300,e.held());e.deaths(0);result(e,0,target);return_map(e)
 e.open();e.buttons=[];e.row(serial);assert e.buttons[-2:]==[(END+0x910,0),(END+0x920,1)]
 # Successful defenses and damaged snapshots do not expose an action.
 zero=bytearray(raw);struct.pack_into('<I',zero,480,0);crc(zero)
 safe=Revenge();safe.files={k:bytearray(v) for k,v in seed.files.items()};safe.files[key(seed)]=zero;safe.enter();safe.open();safe.row(serial)
 assert safe.buttons[-2:]==[(END+0x910,0),(END+0x920,1)]
 corrupt=Revenge();corrupt.files={k:bytearray(v) for k,v in seed.files.items()};corrupt.files[key(seed)]=bytearray(raw)
 snapshot=next(k for k in corrupt.files if k.endswith('.npc'));corrupt.files[snapshot][30]^=1;damaged=bytes(corrupt.files[snapshot]);corrupt.enter();corrupt.open();corrupt.row(serial)
 assert corrupt.buttons[-2:]==[(END+0x910,0),(END+0x920,1)] and bytes(corrupt.files[snapshot])==damaged
 # Changing players invalidates old rows and snapshots.
 e.put(PM+0x74,43);e.enter();loads=len(e.loads);e.stub(0x105c06c,row,101);assert len(e.loads)==loads
 report={'failed_defense_only':True,'revenge_enters_scout':True,'frozen_fbi_line':True,'scout_and_cancel_free':True,'cancel_does_not_consume':True,'real_attack_debits_and_consumes_once':True,'corrupt_snapshot_preserved_action_disabled':True,'old_player_row_rejected':True,'actual_click_render_and_attack_requires_runtime':True,'runtime_game_verified':False}
 (c.OUT/'v99-revenge-checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':
 sys.meta_path.insert(0,Definitions());c=importlib.import_module('check_offline_pvp_v82_arm');check_policy(c);check_revenge(c)
