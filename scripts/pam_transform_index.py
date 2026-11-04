"""Index PAM v6 records while retaining every original command and frame byte.

Wire layout reference: https://github.com/LambdaEd1th/pam-codec (decoder/types).
This indexer edits transforms only, without serializing unrelated animation data.
"""
from pathlib import Path
import struct,json
class PamIndex:
 def __init__(self,b):self.b=b;self.p=0;self.images=[];self.sprites=[];self.read()
 def n(self,f):z=struct.calcsize('<'+f);v=struct.unpack_from('<'+f,self.b,self.p);self.p+=z;return v[0] if len(v)==1 else v
 def s(self):n=self.n('H');v=self.b[self.p:self.p+n].decode();self.p+=n;return v
 def count(self):v=self.n('B');return self.n('H') if v==255 else v
 def read(self):
  assert self.n('I')==0xbaf01954 and self.n('I')==6
  self.p=17
  for _ in range(self.n('H')):
   name=self.s();off=self.p;size=self.n('hh');mat=self.n('4i2h');self.images.append(dict(name=name,size=size,mat=mat,off=off))
  count=self.n('H')
  for _ in range(count):self.sprite()
  if self.n('B'):self.sprite('MAIN')
  assert self.p==len(self.b),(self.p,len(self.b))
 def sprite(self,override=None):
  start=self.p;name=self.s();reserved=self.s();fps=self.n('i');count=self.n('H');area=self.n('hh');frames=[]
  for i in range(count):
   st=self.p;flags=self.n('B');adds=[];moves=[];label=None
   rem=[]
   if flags&1:
    for _ in range(self.count()):
     idx=self.n('H')&2047
     if idx==2047:idx=self.n('i')
     rem.append(idx)
   if flags&2:
    for _ in range(self.count()):
     num=self.n('H');index=num&2047
     if index==2047:index=self.n('i')
     res=self.n('B')
     if res==255:res=self.n('H')
     if num&8192:self.p+=2
     aname=self.s() if num&4096 else None
     if num&2048:self.p+=4
     adds.append(dict(index=index,res=res,sprite=bool(num&32768),name=aname))
   if flags&4:
    for _ in range(self.count()):
     ms=self.p;num=self.n('H');idx=num&1023
     if idx==1023:idx=self.n('i')
     mat=(1.,0.,0.,1.)
     if num&4096:mat=tuple(v/65536 for v in self.n('4i'))
     elif num&16384:self.p+=2
     pos=self.n('ii' if num&2048 else 'hh')
     if num&32768:self.p+=8
     color=self.n('4B') if num&8192 else None
     if num&1024:self.p+=2
     moves.append(dict(index=idx,flags=num,mat=mat,pos=pos,start=ms,end=self.p,color=color))
   if flags&8:label=self.s()
   commands=[]
   if flags&32:
    for _ in range(self.n('B')):commands.append((self.s(),self.s()))
   frames.append(dict(start=st,end=self.p,label=label,adds=adds,moves=moves,commands=commands,rem=rem))
  self.sprites.append(dict(name=override or name,start=start,end=self.p,frames=frames))
