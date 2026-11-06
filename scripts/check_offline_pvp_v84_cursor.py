"""Execute the installed cursor hook and original release/retain decision code."""
import sys, importlib, struct, json
from check_offline_pvp_v76_focused import Definitions
sys.meta_path.insert(0,Definitions())
c=importlib.import_module('check_offline_pvp_v82_arm')
core=importlib.import_module('check_offline_pvp_arm')
from unicorn.arm_const import *
BASE,M,PM,END=core.BASE,core.M,core.PM,core.END
BOARD=importlib.import_module('check_offline_pvp_v56_arm').BOARD
OUT=c.OUT

class CursorEngine(c.GarrisonEngine):
 def __init__(self):
  super().__init__();self.actions=[];self.cursor=self.alloc(0x80);self.event=self.alloc(64)
  self.table=self.alloc(0x80);self.put(self.cursor,self.table)
  self.put(self.table+0x24,BASE+0x10aac90);self.put(self.table+0x44,END+0x100)
  # The shared fixture already binds the native app GOT entry, including its
  # extra indirection, used by the real ArenaEdit hit-test/retain code.
 def hook(self,em,a,size,d):
  off=a-BASE
  if off==0x22a48c or 0x4e55b8<=off<0x4e5648 or 0x10aac90<=off<0x10aacfc or 0x1ef3d0<=off<0x1ef438 or 0x1efe24<=off<0x1eff24 or off==0x209894:return
  if off in (0x22a490,0x2096c4):
   if off==0x22a490:assert em.reg_read(UC_ARM_REG_R0)==BOARD;self.actions.append('cursor-added-boundary')
   else:self.actions.append('pending-crosshair-pass')
   em.reg_write(UC_ARM_REG_PC,END);return
  r=[em.reg_read(x) for x in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  x,y,z,w=r;handled=True;result=0
  if a==END+0x100:assert x==self.cursor;self.actions.append('native-place')
  elif off==0xf26fc8:result=M+0x1f000
  elif off==0x43af38 and y==M+0x1f000:result=0 # no conveyor module in these editors
  elif off==0x1efd38:self.actions.append('native-finish');self.u.mem_write(x+0x1d,b'\1')
  elif off==0x223db8:assert x==BOARD;result=M+0x1e000
  elif off==0x11d761c:self.put(x,0);self.put(x+4,0)
  elif off==0x224204:
   assert (x,y)==(BOARD,self.cursor);self.actions.append('native-retain')
   self.put(BOARD+0x94c,self.cursor);self.put(self.cursor+0x24,0)
  else:handled=False
  if handled:
   em.reg_write(UC_ARM_REG_R0,result);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR));return
  return super().hook(em,a,size,d)
 def born(self,x=500,y=250):
  self.u.mem_write(self.cursor+4,bytes(0x44));self.put(self.cursor+4,x);self.put(self.cursor+8,y)
  self.u.reg_write(UC_ARM_REG_R5,BOARD);self.u.reg_write(UC_ARM_REG_R10,self.cursor)
  self.run(0x22a48c)
 def rectangle(self):return struct.unpack('<iiii',self.u.mem_read(self.cursor+12,16))
 def release(self,x,y,*,second=False,moved=False):
  self.actions=[];self.put(self.cursor+4,x);self.put(self.cursor+8,y)
  self.u.mem_write(self.cursor+0x1d,bytes([0,second,moved]));self.put(self.event+0x28,3)
  self.run(0x4e55b8,self.cursor,self.event);return list(self.actions)

def check():
 e=CursorEngine();e.enter();e.run('offlineGarden');e.own()
 before={k:bytes(v) for k,v in e.files.items()}
 e.born();assert e.rectangle()==(490,240,20,20)
 assert e.release(500,250)==['native-retain']
 frame=e.alloc(0x100)+0x80;e.put(frame-0x44,BOARD)
 e.u.reg_write(UC_ARM_REG_R11,frame);e.u.reg_write(UC_ARM_REG_R4,M+0x30000)
 e.actions=[];e.run(0x209894);assert e.actions==['pending-crosshair-pass']
 # The next target click and a conventional hold-drag both use the original
 # placement callback once, then finish. Clicking the origin again cancels.
 assert e.release(600,300,second=True)==['native-place','native-finish']
 e.born();assert e.release(600,300,moved=True)==['native-place','native-finish']
 e.born();assert e.release(500,250,second=True)==['native-finish']
 # A different user, ended board, battle preview and detached session cannot
 # gain a desktop click rectangle through this constructor boundary.
 e.put(PM+0x74,43);e.born();assert e.rectangle()==(0,0,0,0);e.put(PM+0x74,42)
 e.put(BOARD+0xc0,9);e.born();assert e.rectangle()==(0,0,0,0);e.put(BOARD+0xc0,5)
 e.string(BOARD+0xc4,'arena_battle_test');e.born();assert e.rectangle()==(0,0,0,0)
 e.string(BOARD+0xc4,'arena_plant_test');e.request(3);e.born();assert e.rectangle()==(0,0,0,0)
 assert {k:bytes(v) for k,v in e.files.items()}==before,'selection changed persistence'
 # Owned shop uses the same native cursor lifecycle, without making tools.
 for _ in range(3):e.train()
 e.advance(91);e.run('offlineTrainingTick',e.get(M+0x20));c.claim(e,0)
 assert e.edit(0)==1;e.born(300,200);assert e.rectangle()==(290,190,20,20)
 assert e.release(300,200)==['native-retain']
 assert e.release(450,250,second=True)==['native-place','native-finish']
 report=dict(installed_post_constructor_hook=True,real_arena_hit_test_and_release=True,
  click_retains=True,second_click_places_once=True,hold_drag_preserved=True,origin_click_cancels=True,
  pending_crosshair_pass=True,home_and_owned_shop=True,foreign_user_and_stale_board_guard=True,
  no_selection_save_write=True,runtime_verified=False,
  engine_boundaries=['native placement action','retained vector update','cursor destruction','render body'])
 (OUT/'desktop-cursor-check.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
 print('v84 desktop formation cursor checks passed')

if __name__=='__main__':
 if '--legacy-regions-fixture' in sys.argv:
  importlib.import_module('check_offline_pvp_v93_focused').accepted_legacy_fixtures()
 check()

