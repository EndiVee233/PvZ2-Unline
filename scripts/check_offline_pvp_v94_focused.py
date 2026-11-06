"""Local original-UI battle summaries and balance-only region purchases."""
import sys,importlib,struct,json
from check_offline_pvp_v76_focused import Definitions

def check_history(c):
 from check_offline_pvp_v81_arm import GarrisonEngine,claim
 from check_offline_pvp_v60_arm import board,result,return_map
 from check_offline_pvp_arm import BASE,M,PM,END
 from check_offline_pvp_v93_focused import key,crc
 from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_SP
 ns=0x4c4f434c
 class History(GarrisonEngine):
  def __init__(self):super().__init__();self.views=[];self.ui_actions=[];self.original_rows=0
  def hook(self,em,a,size,d):
   if a==BASE+0x105b774:
    ui,v=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1)]
    ids=[struct.unpack('<II',em.mem_read(p,8)) for p in range(self.get(v),self.get(v+4),8)]
    self.views.append((ui,ids));em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR));return
   if a in (BASE+0x105acc0,BASE+0x103bdb4):
    # Native formatting/table lookup bodies are bounded; execute their actual
    # installed wrappers and preserve the original pushed-register ABI.
    if a==BASE+0x105acc0:
     self.original_rows+=1;self.put(em.reg_read(UC_ARM_REG_R0)+0xd0,0xffffffff)
     regs=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_LR)
    else:regs=(UC_ARM_REG_R4,UC_ARM_REG_R11,UC_ARM_REG_LR)
    sp=em.reg_read(UC_ARM_REG_SP);vals=struct.unpack('<'+'I'*len(regs),em.mem_read(sp,4*len(regs)))
    for r,v in zip(regs,vals):em.reg_write(r,v)
    em.reg_write(UC_ARM_REG_SP,sp+4*len(regs));em.reg_write(UC_ARM_REG_R0,0x1234)
    em.reg_write(UC_ARM_REG_PC,vals[-1]);return
   if a in (END+0x600,END+0x610):
    self.ui_actions.append((a,em.reg_read(UC_ARM_REG_R0),em.reg_read(UC_ARM_REG_R1)))
    em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR));return
   return super().hook(em,a,size,d)
  def history(self):
   raw=self.files[key(self)]
   if len(raw)<468:return []
   n=struct.unpack_from('<I',raw,464)[0]
   return [struct.unpack_from('<6I',raw,468+24*i) for i in range(n)]
  def open(self):
   ui=self.alloc(0x100);self.u.reg_write(UC_ARM_REG_R4,ui);self.stub(0x105a954);return ui
  def lookup(self,serial,high=ns):
   self.stub(0x103bdb0,0,0,serial,high);return self.u.reg_read(UC_ARM_REG_R0)
  def row(self,serial,high=ns):
   row=self.alloc(0xd8);self.put(row+0xa8,serial);self.put(row+0xac,high)
   table=self.alloc(0xc0);self.put(table+0x8c,END+0x600);self.put(table+0xa4,END+0x610)
   for o in (0xb0,0xb4):
    button=self.alloc(0x240);self.put(button,table);self.put(row+o,button)
   self.stub(0x105acbc,row);return row
 def fixture():
  e=History();e.enter();e.run('offlineGarden')
  for _ in range(3):e.train()
  e.advance(91);e.run('offlineTrainingTick',e.get(M+0x20));return e
 def attack(e,stars,fail=False):
  e.reset_map();p=e.residents()[0];target=e.get(p);e.selected(p)
  e.stub(0x1042fe8,M,0,1,0);board(e)
  e.run(0x1030a50,M+0x14300,e.held());e.deaths(0)
  e.failwrite=fail;result(e,stars,target);return target
 empty=History();empty.enter();saved=bytes(empty.files[key(empty)]);empty.open()
 assert empty.views[-1][1]==[] and bytes(empty.files[key(empty)])==saved
 e=fixture();target=attack(e,2);h=e.history();assert len(h)==1 and h[0][2:]==(target,2,66,1)
 saved=bytes(e.files[key(e)]);result(e,2,target);assert bytes(e.files[key(e)])==saved
 return_map(e);e.reset_map();ui=e.open();ids=e.views[-1][1];assert ids==[(h[0][0],ns)]
 ptr=e.lookup(h[0][0]);assert ptr and [e.get(ptr+o) for o in (0x90,0x94,0xa0,0xa8,0xb4,0xc8)]==[1,1,target,2,66,h[0][1]]
 name=e.get(ptr+0x9c);assert e.get(name-12)>0
 row=e.row(h[0][0]);assert e.get(row+0xd0)==66 and len(e.ui_actions)==4 and [v for _,_,v in e.ui_actions]==[0,1,0,1]
 e.stub(0x105c06c,row,100);e.stub(0x105c06c,row,101)
 assert bytes(e.files[key(e)])==saved,'viewing/unsupported replay or revenge changed wallet'
 assert e.lookup(h[0][0],0)==0x1234,'foreign lookup no longer follows original table'
 assert e.lookup(0xffffffff)==0,'unknown local record leaked a prior brief'
 r=History();r.copy_state(e);r.enter();r.open();assert r.history()==h and r.views[-1][1]==ids
 # Each completed result commits exactly once with its reward; newest ten win.
 for i in range(13):
  e.advance(1);attack(e,i%4);return_map(e);e.reset_map()
 rows=e.history();assert len(rows)==10 and all(rows[i][0]>rows[i+1][0] for i in range(9))
 assert [r[3] for r in rows]==list(reversed([i%4 for i in range(3,13)]))
 e.open();assert len(e.views[-1][1])==10
 # Save failure neither appends a row nor pays; retry appends one, not two.
 f=fixture();saved_count=len(f.history());target=attack(f,3,True)
 assert len(f.history())==saved_count and f.windows==0
 f.failwrite=False;result(f,3,target);assert len(f.history())==saved_count+1 and f.history()[0][4]==100
 return_map(f);f.reset_map();claim(f,0);assert f.history()[0][2:]==(0x71000001,3,100,2)
 # The previous v12 envelope migrates empty history without replaying battles.
 raw=bytearray(e.files[key(e)][:464]);struct.pack_into('<I',raw,4,12);crc(raw)
 m=History();m.files={key(e):raw};m.enter();assert m.history()==[] and m.get(M+4)==e.get(M+4)
 # Changing players never shows a cached brief or grants former rewards.
 e.put(PM+0x74,43);e.put(M+0x20,0);e.enter();e.open();assert e.history()==[] and e.views[-1][1]==[] and e.lookup(rows[0][0])==0
 e.put(PM+0x74,42);e.put(M+0x20,0);e.enter();e.open();assert e.history()==rows
 report=dict(original_list_and_lookup_wrappers=True,newest_ten=True,actual_settled_reward_recorded=True,shop_kind_and_neighbor_kind=True,atomic_save_failure_retry=True,duplicate_result_no_duplicate_history=True,restart_and_player_scope=True,v12_migration_empty_no_fabrication=True,original_row_then_starcoin_field=True,unrestored_replay_revenge_cannot_network=True,view_does_not_spend_or_reward=True,rendering_is_engine_boundary=True,runtime_game_verified=False)
 (c.OUT/'v94-history-checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':
 sys.meta_path.insert(0,Definitions());c=importlib.import_module('check_offline_pvp_v82_arm')
 p=importlib.import_module('check_offline_pvp_v93_focused');p.check_regions(c);p.accepted_legacy_fixtures();check_history(c)
 importlib.import_module('check_offline_pvp_v91_focused').check_collection(c)
 importlib.import_module('check_offline_pvp_v90_focused').check_production(c)
 c.check_reposition();c.check_capture();c.check_scout();c.check_ownership();c.check_businesses()
 old=importlib.import_module('check_offline_pvp_v76_arm');old.check_lifecycle();old.check_defense();old.check_residences()
