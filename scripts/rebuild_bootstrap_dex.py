"""Reassemble the small bootstrap DEX with sorted IDs after changing literals."""
from pathlib import Path
import subprocess,os,re,struct,hashlib,zlib

def rebuild_bootstrap(original, out, replacements, apktool):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 (out/'original.dex').write_bytes(original)
 subprocess.run(['javac','-cp',str(apktool),'-d',str(out),str(Path(__file__).with_name('RepairDex.java'))],check=True)
 cp=str(apktool)+os.pathsep+str(out)
 subprocess.run(['java','-Xmx256m','-cp',cp,'RepairDex','decode',str(out/'original.dex'),str(out/'smali')],check=True)
 p=out/'smali/com/popcap/pvz2cthd/BootActivity.smali';s=p.read_text(encoding='utf8')
 # One substitution pass avoids cascading if the new base checksum equals the old target.
 for old in replacements:assert old in s,old
 s=re.sub('|'.join(re.escape(k) for k in replacements),lambda m:replacements[m[0]],s)
 p.write_text(s,encoding='utf8')
 target=out/'classes8.dex'
 subprocess.run(['java','-Xmx256m','-cp',cp,'RepairDex','encode',str(out/'smali'),str(target)],check=True)
 b=target.read_bytes();count,off=struct.unpack_from('<II',b,56);strings=[]
 for i in range(count):
  p=struct.unpack_from('<I',b,off+4*i)[0]
  while b[p]&128:p+=1
  p+=1;strings.append(b[p:b.index(0,p)])
 assert all(a<c for a,c in zip(strings,strings[1:])), 'DEX string_ids not strictly sorted'
 assert hashlib.sha1(b[32:]).digest()==b[12:32]
 assert zlib.adler32(b[12:])&0xffffffff==struct.unpack_from('<I',b,8)[0]
 assert struct.unpack_from('<I',b,96)[0]==struct.unpack_from('<I',original,96)[0]
 return b
