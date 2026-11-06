"""Native queued/completed upgrade UI transitions, with rendering bounded."""
import sys,importlib,struct,json
from check_offline_pvp_v76_focused import Definitions

if __name__=='__main__':
 sys.meta_path.insert(0,Definitions())
 old=importlib.import_module('check_offline_pvp_v54_arm')
 from check_offline_pvp_arm import BASE,M,END
 from unicorn.arm_const import *
 class VisualEngine(old.ProgressionEngine):
  def __init__(self):
   super().__init__();self.rectangles=[];self.parent_calls=0;self.image=self.alloc(0x80)
   site=BASE+0x1078334;word=self.get(site);delta=word&0xffffff;delta-=1<<24 if delta&(1<<23) else 0
   self.draw_hook=site+8+4*delta
   # Original parent draw is a deliberate boundary, reached through the
   # actual installed wrapper. Volatile registers are clobbered on return.
   self.parent_boundary=next(a for a in range(self.draw_hook,self.draw_hook+160,4) if self.get(a)==0xe92d4ff0)
  def hook(self,em,a,size,d):
   if a==getattr(self,'parent_boundary',None):
    self.parent_calls+=1
    for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R12):em.reg_write(r,0xabc000+r)
    em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR));return
   if a==BASE+0x1dd8f0:
    assert em.reg_read(UC_ARM_REG_R0)==BASE+0x18a5bd0;result=self.image
   elif a==BASE+0x9734b0:
    x,y,z=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
    assert x==M+0x9000 and z==self.image
    self.rectangles.append(struct.unpack('<4i',em.mem_read(y,16)));result=0
   else:return super().hook(em,a,size,d)
   em.reg_write(UC_ARM_REG_R0,result);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR))
 e=VisualEngine();e.enter();e.upgrade(1);ui,button,timer=e.training_ui()
 for off,v in ((0xa4,37),(0xa8,53),(0xac,1),(0xb0,button),(0xb4,timer)):e.put(ui+off,v)
 balances=e.get(M+4),e.get(M+8),e.gems;files={k:bytes(v) for k,v in e.files.items()}
 for scale in (0.75,1.0,1.25,2.0):
  e.u.mem_write(M+0x7000+0x698,struct.pack('<f',scale));before=len(e.rectangles)
  e.stub(0x1078334,ui,M+0x9000)
  assert e.rectangles[-1]==(37+int(780*scale)-int(12*scale)-int(230*scale),53+int(490*scale)-int(12*scale)-int(66*scale),int(230*scale),int(66*scale))
  assert len(e.rectangles)==before+1 and e.labels[button+0xa4]=='15钻石立即完成'
  assert e.visible[button]==1 and e.visible[timer]==0 and bytes(e.u.mem_read(button+0x4e,1))==b'\0'
 assert (e.get(M+4),e.get(M+8),e.gems)==balances and {k:bytes(v) for k,v in e.files.items()}==files
 # Use the real offer/checkout dispatch: completion must clear the temporary
 # caption before a normal upgrade footer is shown again.
 e.stub(0x107486c,ui,0xfffffffe);e.confirm(timer,0);assert e.level(1)==1
 e.stub(0x107486c,ui,0xfffffffe);e.confirm(timer);assert e.level(1)==2 and e.gems==85
 count=len(e.rectangles);e.stub(0x1078334,ui,M+0x9000)
 assert e.labels[button+0xa4]=='' and len(e.rectangles)==count
 e.stub(0x1078334,ui,M+0x9000);assert e.labels[button+0xa4]=='' and len(e.rectangles)==count
 # A different building's pending queue does not paint a base completion CTA.
 e.upgrade(2);e.stub(0x1078334,ui,M+0x9000);assert len(e.rectangles)==count and e.labels[button+0xa4]==''
 e.put(ui+0xac,2);e.stub(0x1078334,ui,M+0x9000);assert len(e.rectangles)==count+1
 e.upgrade(2,-3);e.stub(0x1078334,ui,M+0x9000);assert e.labels[button+0xa4]=='' and len(e.rectangles)==count+1
 report=dict(installed_parent_wrapper_preserves_graphics=True,queued_frame_uses_original_resource_and_scaled_rect=True,scales=[0.75,1,1.25,2],queued_button_enabled_and_cash_overlay_hidden=True,gem_offer_cancel_complete_preserved=True,completed_and_cancelled_caption_cleared=True,other_building_queue_not_overlaid=True,draw_does_not_change_money_or_save=True,rendering_is_bounded_not_visual_acceptance=True,runtime_game_verified=False)
 (old.OUT/'v92-visual-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
