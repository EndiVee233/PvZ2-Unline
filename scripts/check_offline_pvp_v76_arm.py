"""Check editor Board::Finish before map return, retry and repeated entry."""
from check_offline_pvp_v75_arm import DefenseEngine,OUT,check_defense
from check_offline_pvp_v74_arm import check_residences
from check_offline_pvp_v56_arm import BOARD
from check_offline_pvp_arm import BASE,M
from unicorn.arm_const import *
import struct,json

class LifecycleEngine(DefenseEngine):
 def __init__(self):super().__init__();self.order=[]
 def hook(self,em,a,size,d):
  off=a-BASE
  if off==0x2262b0:self.order.append('finish')
  elif off==0x352498:self.order.append('map')
  elif off==0x85e7d8:self.order.append('load-editor')
  return super().hook(em,a,size,d)

def formation(e):
 p=e.alloc(12);e.u.mem_write(p,struct.pack('<III',2,2,3));i=e.alloc(16)
 e.u.mem_write(i,struct.pack('<III',2,1,0));e.string(i+12,'')
 for o,v in ((4,p),(8,p+12),(12,p+12),(16,i),(20,i+16),(24,i+16)):e.put(M+0x80+o,v)

def check_lifecycle():
 e=LifecycleEngine();e.enter();e.run('offlineGarden');e.own();formation(e)
 e.order=[];before=e.ends;e.run('offlineSave',0,0,1,1)
 assert e.order==['finish','map'] and e.ends==before+1 and e.get(BOARD+0xc0)==9
 e.request(3);e.order=[];e.own()
 assert e.order==['load-editor'],'finished board ended twice'
 assert bytes(e.u.mem_read(e.get(M+0x84),12))==struct.pack('<III',2,2,3)
 assert e.get(M+0x88)-e.get(M+0x84)==12
 # Another save/reentry cannot leave an unfinished editor attached to the map.
 e.order=[];e.run('offlineSave',0,0,1,1);assert e.order==['finish','map']
 e.request(3);e.order=[];e.own();assert e.order==['load-editor']
 # Failed write keeps the current editor alive and does not switch scenes.
 e.failwrite=True;e.order=[];e.run('offlineSave',0,0,1,1)
 assert not e.order and e.get(BOARD+0xc0)==5
 e.failwrite=False
 # Guard stale, unfinished editor boards before replacing formation memory.
 e.order=[];e.own();assert e.order==['finish','load-editor']
 e.request(1);e.request(3)
 report=dict(native_finish_dispatched_before_saved_map_transition=True,
 editor_reentry_replaces_one_saved_formation=True,already_finished_board_not_finished_twice=True,
 failed_save_preserves_live_editor=True,stale_editor_finished_before_reloading=True,
 original_engine_audio_and_pause_cleanup_runtime_boundary=True,runtime_game_verified=False)
 (OUT/'v76-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))

if __name__=='__main__':
 check_lifecycle();check_defense();check_residences()
 from check_offline_pvp_v73_arm import check_clock,check_manual_refresh
 check_manual_refresh();check_clock()
 from check_offline_exchange_sampler_arm import check
 check()
