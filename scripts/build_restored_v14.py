"""Rebuild a combined candidate from verified v11; never modifies saves or installs it.
Run from repository root: python scripts/build_restored_v14.py
Then zipalign/sign work/restored-v14/unsigned.apk with the retained signing key.
"""
from pathlib import Path
import hashlib,json,zipfile,shutil
BASE=Path(__file__).resolve().parents[1]
source=BASE/'PvZ2-reconstruction-multiuser-v11.apk'
out=BASE/'work/restored-v14';out.mkdir(parents=True,exist_ok=True)
def sha(b):return hashlib.sha256(b).hexdigest()
assert hashlib.file_digest(source.open('rb'),'sha256').hexdigest()=='f2fc92088bac761e9d6eb9f2055f9f60ae00de3f482da2c13bc156f6ec0a6d44'
edits={
 'lib/armeabi/libSrc.so':('a91e002a63326750e14043084d59d2076a6234c15f62f77c87a56b19fc9c70b7',[
 (0x9970b8,'000094e5','fbffffea','Restore earlier delivered v13 victory gate: branch to 0x9970ac'),
 (0x9f4080,'8a01000a','8a0100ea','Tutorial id 18: take existing completion/cleanup path 0x9f46b0')]),
 'lib/armeabi/libHookPVZ2.so':('ffd2fd05606d79afa4585d65423ead1432dfbbca1db28a67e75b83afdee32678',[
 (0x6afc,'07f0d8f8','00bf00bf','Remove forced CardPlay hook on original outro 0x993578'),
 (0x6c02,'07f055f8','00bf00bf','Remove associated hook that swallows original UI closure 0x3fe358')])}
records=[];libs={}
with zipfile.ZipFile(source) as z:
 for name,(expected,patches) in edits.items():
  original=z.read(name);assert sha(original)==expected
  b=bytearray(original)
  for offset,before,after,role in patches:
   assert b[offset:offset+4]==bytes.fromhex(before),(name,hex(offset))
   b[offset:offset+4]=bytes.fromhex(after)
   records.append(dict(entry=name,offset=hex(offset),before=before,after=after,role=role))
  allowed={p+i for p,_,_,_ in patches for i in range(4)}
  assert all(x==y or i in allowed for i,(x,y) in enumerate(zip(original,b)))
  libs[name]=bytes(b);(out/Path(name).name).write_bytes(b)
 with zipfile.ZipFile(out/'unsigned.apk','w',allowZip64=True) as dst:
  for i in z.infolist():
   if i.filename.startswith('META-INF/'):continue
   if i.filename in libs:dst.writestr(i,libs[i.filename])
   else:
    with z.open(i) as a,dst.open(i,'w') as b:shutil.copyfileobj(a,b,1024*1024)
record=dict(base=str(source),patches=records,library_sha256={n:sha(b) for n,b in libs.items()},device_verified=False)
(out/'patches.json').write_text(json.dumps(record,indent=2),encoding='utf8')
(BASE/'docs/recovery/restored-v14-patches.json').write_text(json.dumps(record,indent=2),encoding='utf8')
print(json.dumps(record,indent=2))
