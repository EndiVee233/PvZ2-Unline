"""Actual sale callback and atomic wallet/army checks on public fixtures."""
import sys,importlib,struct,json,runpy
from pathlib import Path
from check_offline_pvp_v76_focused import Definitions

def check_sales(c):
 from check_offline_pvp_v81_arm import GarrisonEngine
 from check_offline_pvp_v93_focused import old_record,key
 from check_offline_pvp_arm import BASE,M,PM,PROFILE
 from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_SP
 class Sales(GarrisonEngine):
  def __init__(self):super().__init__();self.fallbacks=0;self.left_sale=0;self.rebuild_sale=None
  def hook(self,em,a,size,data):
   off=a-BASE
   if off==0x10584d4 or off==0x10591ec:
    # The original initializer / early-tutorial fallback is a native UI
    # boundary. The installed prologue and post-initialization wrapper run.
    sp=em.reg_read(UC_ARM_REG_SP);ret=self.get(sp+32);em.reg_write(UC_ARM_REG_SP,sp+36)
    if off==0x10591ec:self.fallbacks+=1
    em.reg_write(UC_ARM_REG_R0,1);em.reg_write(UC_ARM_REG_PC,ret);return
   if off==0x10584d0 or off==0x10591e8 or 0x1052168<=off<0x1052190:return
   if off==0x1056f84:
    ui=em.reg_read(UC_ARM_REG_R0);self.u.mem_write(ui+0x110,b'\0');self.left_sale+=1;em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR));return
   result=super().hook(em,a,size,data)
   if off==0x1042a5c and self.rebuild_sale:
    ui=self.rebuild_sale;self.rebuild_sale=None
    for p in range(self.get(ui+0xe4),self.get(ui+0xe8),4):self.put(p,0xfffffff0)
    empty=self.alloc(4);self.put(ui+0xe4,empty);self.put(ui+0xe8,empty)
   return result
  def count(self,name):
   camp=self.get(M+0x20)
   for p in range(self.get(camp+12),self.get(camp+16),32):
    if self.txt(self.get(p))==name:return self.get(p+4)
   return 0
  def sale(self,selection):
   ui=self.alloc(0x130);self.put(ui,self.alloc(0x20));cards=[]
   for name,amount in selection:
    p=self.alloc(0xc0);self.string(p+0xa8,name);self.put(p+0xac,self.count(name));self.put(p+0xb0,amount);cards.append(p)
   entries=self.alloc(max(4,len(cards)*4))
   for i,p in enumerate(cards):self.put(entries+4*i,p)
   self.put(ui+0xe4,entries);self.put(ui+0xe8,entries+len(cards)*4);self.put(ui+0xec,entries+len(cards)*4)
   self.u.mem_write(ui+0x110,b'\1');self.run(0x10584d0,ui);return ui,cards
  def confirm(self,ui,yes=1):self.run(0x10591e8,ui,yes)
 def fixture():
  seed=Sales();seed.enter();e=Sales();e.files={key(seed):old_record(seed,10,100000)};e.enter();e.run('offlineGarden')
  for _ in range(3):e.train()
  for _ in range(2):e.train(name='pvp_imp')
  e.advance(121);e.run('offlineTrainingTick',e.get(M+0x20));assert e.count('pvp_change')==3 and e.count('pvp_imp')==2
  return e
 e=fixture();e.train();queued=e.queued();ui,cards=e.sale([('pvp_change',2),('pvp_imp',1)])
 balance=e.get(M+4);saved=bytes(e.files[key(e)]);e.confirm(ui,0)
 assert e.get(M+4)==balance and bytes(e.files[key(e)])==saved and all(e.get(p+0xb0)==0 for p in cards)
 ui,cards=e.sale([('pvp_change',2),('pvp_imp',1)]);e.confirm(ui)
 assert e.get(M+4)==balance+9 and e.count('pvp_change')==e.count('pvp_imp')==1
 assert e.queued()==queued and e.held()==2 and all(e.get(p+0xb0)==0 for p in cards)
 assert [e.get(p+0xac) for p in cards]==[1,1] and e.left_sale==2
 saved=bytes(e.files[key(e)]);e.confirm(ui);assert bytes(e.files[key(e)])==saved,'duplicate confirmation sold twice'
 r=Sales();r.files={k:bytearray(v) for k,v in e.files.items()};r.advance(e.now-r.now);r.enter()
 assert (r.get(M+4),r.count('pvp_change'),r.count('pvp_imp'),r.queued())==(balance+9,1,1,queued)
 # Failed writes retain both selections and inventory; a second confirmation
 # retries exactly once rather than losing the refund or minting extra coins.
 f=fixture();ui,cards=f.sale([('pvp_change',3)]);before=bytes(f.files[key(f)]);funds=f.get(M+4);f.failwrite=True;f.confirm(ui)
 assert bytes(f.files[key(f)])==before and f.get(M+4)==funds and f.count('pvp_change')==3 and f.get(cards[0]+0xb0)==3
 f.failwrite=False;f.confirm(ui);assert f.count('pvp_change')==0 and f.get(M+4)==funds+6
 # Native currency listeners may rebuild/free the selection vector during
 # projection. The transaction may not walk the stale vector afterwards.
 rebuilt=fixture();ui,_=rebuilt.sale([('pvp_change',1)]);rebuilt.rebuild_sale=ui;rebuilt.confirm(ui)
 assert rebuilt.count('pvp_change')==2 and rebuilt.rebuild_sale is None
 # Reject overselling, duplicate aliases, unknown types and stale players.
 for selected in [[('pvp_imp',3)],[('pvp_change',1),('pvp_change',1)],[('not_a_train',1)]]:
  bad=fixture();ui,_=bad.sale(selected);before=bytes(bad.files[key(bad)]);bad.confirm(ui);assert bytes(bad.files[key(bad)])==before
 bad=fixture();ui,_=bad.sale([('pvp_change',1)]);bad.put(PM+0x74,43);before={k:bytes(v) for k,v in bad.files.items()};bad.confirm(ui)
 assert {k:bytes(v) for k,v in bad.files.items()}==before and not bad.fallbacks
 # Selling frees population immediately so the normal train-capacity path
 # can accept a new unit, without deleting queued training.
 cap=fixture()
 for _ in range(35):cap.train()
 assert cap.held()+cap.queued()==40
 ui,_=cap.sale([('pvp_imp',1)]);cap.confirm(ui);cap.train();assert cap.held()+cap.queued()==40
 early=fixture();ui,_=early.sale([('pvp_change',1)]);early.put(PROFILE+0x75c,8);early.confirm(ui);assert early.fallbacks==1
 report={'installed_confirmation_wrapper':True,'profile_bound_ui':True,'original_half_cost_quote':True,'mixed_batch_atomic_sale':True,
  'cancel_and_duplicate_safe':True,'write_failure_preserves_selection_retry':True,'native_listener_rebuild_safe':True,'queued_training_preserved':True,'restart_preserved':True,
  'oversell_duplicate_unknown_rejected':True,'capacity_freed_for_new_training':True,'early_tutorial_native_fallback':True,'runtime_game_verified':False}
 (c.OUT/'v101-sale-checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':
 sys.meta_path.insert(0,Definitions());c=importlib.import_module('check_offline_pvp_v82_arm');check_sales(c)
 if '--sales-only' not in sys.argv:runpy.run_path(str(Path(__file__).with_name('check_offline_pvp_v99_focused.py')),run_name='__main__')
