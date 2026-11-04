"""Exercise installed skill hooks at a relocated ARM base; engine queries mocked."""
import sys,json,math,struct
from pathlib import Path
import check_offline_pvp_arm as core
from unicorn.arm_const import *
core.OUT=Path(sys.argv[1]);BASE=core.BASE;END=core.END
class RangeEngine(core.Engine):
 def __init__(self):super().__init__();self.points=[];self.queries=[];self.draws=[]
 def fp(self,p):return struct.unpack('<f',self.u.mem_read(p,4))[0]
 def point(self,col,row):
  p=self.alloc(24);self.u.mem_write(p+16,struct.pack('<ff',232+col*64,198+row*76));return p
 def hook(self,em,a,size,d):
  off=a-BASE
  if off>=0x1a00000 or a==END:return
  x,y,z,w=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  if off in (0x23bcec,0x23bcd4):result=math.floor((self.fp(x+(16 if off==0x23bcec else 20))-(200 if off==0x23bcec else 160))/(64 if off==0x23bcec else 76))
  elif off==0xbf518c:
   assert y==2;rect=struct.unpack('<4i',em.mem_read(z,16));self.queries.append(rect)
   left,top,width,height=rect;found=[p for c,r,p in self.points if left<=c<left+width and top<=r<top+height]
   first=self.alloc(max(4,4*len(found)))
   for i,p in enumerate(found):self.put(first+4*i,p)
   for i,p in enumerate((first,first+4*len(found),first+4*len(found))):self.put(x+4*i,p)
   result=x
  elif off==0x11d74b4:result=core.M
  elif off==0x1da034:result=self.get(y)
  elif off==0xb82850:self.put(x,y);self.put(x+4,0);result=x
  elif off==0x1d9bb4:self.put(x,z);self.put(x+4,w);result=x
  elif off==0x207088:self.draws.append((z,w,self.get(em.reg_read(UC_ARM_REG_SP))));result=0
  elif off==0x1167128:self.draws.append(struct.unpack('<4i',em.mem_read(y,16)));result=0
  else:return super().hook(em,a,size,d)
  em.reg_write(UC_ARM_REG_R0,result&0xffffffff);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)

e=RangeEngine();out=e.alloc(12);center=e.point(4,2);props=e.alloc(0x198);cursor=e.alloc(64)
for r in range(-2,7):
 for c in range(-2,12):e.points.append((c,r,e.point(c,r)))
for site,width,height in [(0x10067f0,3,3),(0x1007924,5,4)]:
 e.stub(site,out,2,center+16,0)
 assert e.queries[-1]==(4-width//2,2-height//2,width,height)
 assert (e.get(out+4)-e.get(out))//4==width*height
for cost,width,height in [(60,3,3),(25,4,4),(20,3,3),(30,5,4)]:
 e.put(props+0x160,cost);e.put(cursor+0x30,props)
 e.u.reg_write(UC_ARM_REG_R6,cursor);e.stub(0x105a220,out,2,center+16,0)
 assert e.queries[-1]==(4-width//2,2-height//2,width,height)
 e.u.reg_write(UC_ARM_REG_R5,props);e.stub(0x209a90,0,0,4,2,0)
 assert e.draws[-1]==(4,2,width)
# Real installed predicate entry branches, including overlapping and stale zones.
zone=e.point(4,2);e.u.mem_write(zone+20,struct.pack('<f',e.fp(zone+20)+24))
weak=e.alloc(16);e.put(weak,0);e.put(weak+8,zone);sub=e.alloc(40)
for site,offset,width,height in [(0x1001a60,0x18,4,4),(0x10060cc,0x14,3,3)]:
 e.put(sub+offset,weak);e.put(sub+offset+4,weak+16)
 for c,r,p in e.points:
  e.stub(site,sub,p)
  assert e.u.reg_read(UC_ARM_REG_R0)==int(4-width//2<=c<4-width//2+width and 2-height//2<=r<2-height//2+height),(hex(site),c,r)
 e.put(sub+offset+4,weak);e.stub(site,sub,zone);assert e.u.reg_read(UC_ARM_REG_R0)==0
# Draw height is corrected only while the rectangular rage scope is active.
rect=e.alloc(16);gw=next(v for k,v in e.exports.items() if k.endswith('drawingSkillWidth'));gh=next(v for k,v in e.exports.items() if k.endswith('drawingSkillHeight'))
for width,height,expected in [(0,0,380),(3,3,380),(4,4,380),(5,4,304)]:
 e.put(BASE+gw,width);e.put(BASE+gh,height);e.u.mem_write(rect,struct.pack('<4i',0,0,320,380));e.stub(0x207298,0,rect);assert e.draws[-1][3]==expected
result=dict(installed_arm_hooks=True,food_3x3=True,aid_4x4=True,fog_3x3=True,rage_5x4=True,rectangular_corners_and_outside=True,stale_and_empty_zones=True,cursor_uses_same_rectangles=True,even_size_anchor=True,rage_indicator_height=True,engine_query_and_cell_conversion_are_boundaries=True,runtime_game_verified=False)
(core.OUT/'v57-arm-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
