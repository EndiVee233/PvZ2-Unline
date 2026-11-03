"""Run real native success callbacks and compiled offline scene hooks in ARM."""
import check_offline_economy_arm as wallet
from check_offline_pvp_arm import BASE,M,GM,END,PROFILE
from unicorn.arm_const import *
from pathlib import Path
import json,struct,sys
OUT=Path(sys.argv[1]);wallet.core.OUT=OUT
APP=M+0x7000;BUS=M+0x9000;NODE=M+0xa000;VECTOR=M+0xa100
class SceneEngine(wallet.EconomyEngine):
 def __init__(self):
  super().__init__();self.special=[];self.loads=[];self.events=0;self.ends=0
  self.put(BASE+0x1830948,M);self.string(BASE+0x18a4cd0,'activity')
  self.put(BASE+0x18216a8,BASE+0x1835eec)
  self.put(BASE+0x182166c,M+0x8800);self.put(M+0x8800,0x12345678)
  self.put(BASE+0x1821678,M+0x8810);self.put(M+0x8810,BUS)
  self.put(BUS+12,NODE);self.put(NODE+16,BASE+0x10418bc)
  self.put(NODE+20,VECTOR);self.put(NODE+24,VECTOR+24);self.put(VECTOR+20,END+0x100)
 def hook(self,em,a,size,d):
  off=a-BASE;x,y,z,w=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  # Execute the ORIGINAL callback instructions, including its event lookup,
  # loop, mode change and production level load, rather than replacing it.
  if 0x104810c<=off<0x1048590 or 0x1046360<=off<0x1046454:return
  if a==END+0x100:
   assert self.get(APP+0x1218)==1,'attack mode set before native notification'
   self.events+=1;self.put(APP+0x6bc,0)
  elif off==0x15df41c:
   old=self.get(x);self.put(x,old+y);em.reg_write(UC_ARM_REG_R0,old);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR))
   return
  elif off==0x14ebf50:pass
  elif off==0x33f688:assert x==BUS
  elif off==0x226770:self.ends+=1;self.put(x+0xc0,9)
  elif off==0x14ecb0c:self.string(x,self.txt(self.get(y)))
  elif off==0x104678c:
   assert x==M
   record=bytes(em.mem_read(y,64));zone,pos=struct.unpack_from('<II',record,28)
   self.special=[r for r in self.special if struct.unpack_from('<II',r,28)!=(zone,pos)]+[record]
   p=self.alloc(64*len(self.special));em.mem_write(p,b''.join(self.special));self.put(M+0x128,p);self.put(M+0x12c,p+64*len(self.special))
  elif off==0x354360:
   assert x==GM and self.txt(self.get(y))=='activity'
   level=self.txt(self.get(z));mode=self.get(APP+0x1218)
   sp=em.reg_read(UC_ARM_REG_SP);assert w==0xffffffff and self.get(sp)==self.get(sp+4)==1
   self.loads.append((level,mode));self.put(GM+0xa24,6);self.string(GM+0xa40,level);self.string(GM+0xa44,'activity')
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_R0,0);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)

def count(e):return (e.get(M+0x88)-e.get(M+0x84))//12

def main():
 e=SceneEngine();e.run('offlineGarden');assert len(e.records)==6 and len(e.special)==1
 rec=e.special[0];assert struct.unpack_from('<III',rec,28)==(1,2,4)
 assert bytes(e.u.mem_read(struct.unpack_from('<I',rec,8)[0],20)).decode('utf-32-le')=='邪恶戴夫\0'
 slots=[struct.unpack_from('<II',r,48) for r in e.records]+[struct.unpack_from('<II',r,28) for r in e.special]
 assert len(set(slots))==7 and (1,1) not in slots
 e.run('offlineGarden');assert len(e.records)==6 and len(e.special)==1
 # Exercise native pre-load notification dispatch as well as board finish.
 # The former debug helper omitted both during repeated attack requests.
 e.stub(0x1043028,M,0,0x70000001,2);assert e.loads==[('arena_plant_test',1)] and count(e)==5
 e.u.mem_write(M+0x17d,b'\1');e.put(APP+0x6bc,M+0xb000);e.put(M+0xb000+0xc0,5)
 e.stub(0x1042fe8,M,0x70000001,3,0)
 assert e.events==1 and e.ends==1 and e.loads[-1]==('arena_battle_test',0) and count(e)==5
 before=e.get(M+0x84);e.stub(0x1042fe8,M,0x70000001,3,0)
 assert len(e.loads)==2 and e.events==1 and e.get(M+0x84)==before,'duplicate attack mutated scene/formation'
 # Map scouting does not set the friend-popup flag (+17d). The running
 # board still needs native finish before the battle success callback loads.
 plain=SceneEngine();plain.stub(0x1043028,M,0,0x70000001,2)
 plain.put(APP+0x6bc,M+0xb000);plain.put(M+0xb000+0xc0,5)
 plain.stub(0x1042fe8,M,0x70000001,3,0)
 assert plain.ends==1 and plain.events==0 and plain.loads[-1]==('arena_battle_test',0)
 assert plain.get(M+0xb000+0x7f4)==8
 # Special-house attacks use the native zero-player-id / reason-4 convention.
 boss=SceneEngine();boss.put(M+0x104,0x70000007);boss.put(M+0xfc,1);boss.put(M+0xf8,2)
 boss.stub(0x1042fe8,M,0,4,0);assert boss.loads==[('arena_battle_test',0)] and count(boss)==7
 assert boss.events==0,'map attack emitted an unrelated scout event'
 early=SceneEngine();early.put(PROFILE+0x75c,7);early.run('offlineGarden');assert not early.records and not early.special
 scene=json.loads((OUT/'generated/scene-resource-build.json').read_text());assert scene['changes'][0]['text_preserved']
 result=dict(arm_checked=True,original_attack_success_callback_executed=True,original_preload_event_dispatched=True,live_scout_board_finished=True,original_scout_loader_executed=True,duplicate_attack_ignored=True,native_evil_dave_house=True,seven_unique_plots=True,special_house_attack_routing=True,dialogue_split_preserves_text=True,runtime_game_verified=False)
 (OUT/'scene-arm-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
