"""Run native narrative callback objects with a local durable acknowledgement."""
from check_offline_pvp_v67_arm import LabelEngine,OUT
from check_offline_pvp_v66_arm import preview,start,result,return_map
from check_offline_pvp_arm import BASE,M,PM,END
from unicorn.arm_const import *
import json,struct

class NarrativeEngine(LabelEngine):
 def __init__(self):
  super().__init__();self.narratives=[];self.original_map_calls=0;self.put(M+0x7000+0x1358,self.alloc(0x100))
 def hook(self,em,a,size,d):
  off=a-BASE;x,y,z,w=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  if off in (0x100ad18,0x100906c,0x10090c4) or 0x1008e90<=off<0x1008ec0:return
  if off==0x100ad1c:
   self.original_map_calls+=1;assert self.get(M+0x160)==0xffffffff
   sp=em.reg_read(UC_ARM_REG_SP)
   for i,r in enumerate((UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_PC)):em.reg_write(r,self.get(sp+4*i))
   em.reg_write(UC_ARM_REG_SP,sp+36);return
  if off==0x2af780:
   assert x==self.get(M+0x7000+0x1358)
   callback=self.alloc(24);em.mem_write(callback,bytes(em.mem_read(z,24)))
   assert self.get(callback)==BASE+0x1787408 and self.get(callback+20)==BASE+0x1008e90
   self.narratives.append((self.txt(self.get(y)),callback));result=0
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_R0,result);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)
 def dialogue(self):
  suffix=f'offline-pvp-{self.get(PM+0x74):08x}.eco';raw=next(v for k,v in self.files.items() if k.endswith(suffix))
  # A valid legacy wallet is intentionally not rewritten just by drawing a
  # map. Its new journal fields remain zero until the next transaction.
  if len(raw)==332:
   assert struct.unpack_from('<I',raw,4)[0]==5;return (0,0,0)
  assert len(raw) in (344,364,400,412,416)
  return struct.unpack('<3I',raw[332:344])
 def setup(self):
  self.enter();self.run('offlineGarden');self.train();self.advance(31);self.run('offlineTrainingTick',self.get(M+0x20))
  self.put(M+0x104,0x70000007);self.put(M+0xfc,1);self.put(M+0xf8,1)
 def play(self,map):self.run(0x100ad18,map)
 def acknowledge(self,callback):self.run(0x1008e90,callback)

e=NarrativeEngine();e.setup();map=e.alloc(0x400);e.play(map);assert e.original_map_calls==1 and not e.narratives
preview(e);start(e);result(e,0);return_map(e);assert e.dialogue()==(1,0,0)
e.play(map);assert e.narratives[-1][0]=='MAP_PVPEVILDAVID_FAILED_INTRO' and e.original_map_calls==1
count=len(e.narratives);e.play(map);assert len(e.narratives)==count
callback=e.narratives[-1][1];before=(e.get(M+4),e.get(M+8),e.gems,e.held())
e.acknowledge(callback);assert e.dialogue()==(1,1,0) and (e.get(M+4),e.get(M+8),e.gems,e.held())==before
e.acknowledge(callback);assert e.dialogue()==(1,1,0)
e.play(map);assert e.original_map_calls==2 and len(e.narratives)==count

for win in range(1,7):
 preview(e);start(e);result(e,1);return_map(e);assert e.dialogue()==(win+1,win,win)
 # A process can be closed after result, before map dialogue. That message
 # remains available, and the completion callback never contacts the server.
 r=NarrativeEngine();r.now=e.now;r.copy_state(e);r.enter();r.run('offlineGarden')
 r.put(M+0x104,0x70000007);r.put(M+0xfc,1);r.put(M+0xf8,1);map=r.alloc(0x400);r.play(map)
 assert r.narratives[-1][0]==f'MAP_PVPEVILDAVID_SUCCESS_{win}_INTRO'
 if win==1:
  r.failwrite=True;r.acknowledge(r.narratives[-1][1]);assert r.dialogue()==(2,1,1)
  r.failwrite=False
 r.acknowledge(r.narratives[-1][1]);assert r.dialogue()==(win+1,win+1,win)
 r.acknowledge(r.narratives[-1][1]);assert r.dialogue()==(win+1,win+1,win)
 r.play(map);assert r.original_map_calls==1 and len(r.narratives)==1;e=r

# Accepted v5 migration does not play old victories retroactively.
key=next(k for k in e.files if k.endswith('.eco'));raw=e.files[key][:332];struct.pack_into('<I',raw,4,5);h=2166136261
for i,c in enumerate(raw):
 if not 24<=i<28:h=((h^c)*16777619)&0xffffffff
struct.pack_into('<I',raw,24,h)
legacy=NarrativeEngine();legacy.files[key]=raw;legacy.enter();legacy.play(legacy.alloc(0x400))
assert legacy.dialogue()==(0,0,0) and not legacy.narratives and legacy.get(M+0x15c)==6

cross=NarrativeEngine();cross.setup();preview(cross);start(cross);result(cross,0);return_map(cross);map=cross.alloc(0x400);cross.play(map);callback=cross.narratives[-1][1]
cross.put(PM+0x74,43);cross.put(M+0x20,0);cross.enter();cross.acknowledge(callback);assert cross.dialogue()==(0,0,0)

resource=json.loads((OUT/'generated/dave-dialogue-build.json').read_text())
assert len(resource['changes'])==7 and all(c['text_and_tags_preserved'] for c in resource['changes'])
report=dict(original_failure_and_six_success_keys=True,native_function_object_and_completion_callbacks=True,
 pending_dialogue_persists_across_restart=True,duplicate_ack_no_server_or_rewards=True,
 failed_ack_save_preserves_pending=True,cross_profile_callback_does_not_acknowledge=True,
 v5_migration_no_historical_replay=True,original_intro_dispatch_preserved=True,
 original_words_and_speaker_tags_paginated=True,previous_v67_regressions=True,runtime_game_verified=False)
(OUT/'v68-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
