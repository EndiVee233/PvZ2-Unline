"""Omit the standalone cosmetic word flash after a defense plant returns.

The native card flight, count refund, sun refund and collectible destruction stay.
"""
from pathlib import Path
import hashlib,json,zipfile,struct,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'work/pvp-v35/PvZ2-v35-defense-card-return.apk'
OUT=ROOT/'work/pvp-v36';OUT.mkdir(exist_ok=True)
assert hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest()=='a2f9fb8280849e87c86bf5258bc6463e59e8fa95a4ef936b61d45b924fc3f538'
site,target=0x10b07f8,0x8ab228
def bl(a,t):return struct.pack('<I',0xeb000000|(((t-a-8)//4)&0xffffff))
with zipfile.ZipFile(BASE) as src:
 native=bytearray(src.read('lib/armeabi/libSrc.so'))
 assert native[site:site+4]==bl(site,target)
 # CollectableArenaPlant::collect has already refunded the seed count here.
 # The next instructions still call native 0x27b974 to retire the collectible.
 assert native[site+4:site+8]==bytes.fromhex('0700a0e1')
 assert native[site+8:site+12]==bl(site+8,0x27b974)
 native[site:site+4]=struct.pack('<I',0xe1a00000)
 unsigned=OUT/'unsigned.apk';aligned=OUT/'aligned.apk'
 final=OUT/'PvZ2-v36-defense-return-flash-fix.apk'
 with zipfile.ZipFile(unsigned,'w',allowZip64=True) as dst:
  for item in src.infolist():
   if item.filename.startswith('META-INF/'):continue
   if item.filename=='lib/armeabi/libSrc.so':dst.writestr(item,native)
   else:
    with src.open(item) as a,dst.open(item,'w') as b:shutil.copyfileobj(a,b,1048576)
subprocess.run(['K:/pvz2-tools/android-build-tools/android-14/zipalign.exe','-f','4',str(unsigned),str(aligned)],check=True)
subprocess.run(['java','-jar','K:/pvz2-tools/android-build-tools/android-14/lib/apksigner.jar','sign','--ks',str(ROOT/'work/keys/recovered-debug.keystore'),'--ks-pass','pass:android','--key-pass','pass:android','--ks-key-alias','androiddebugkey','--out',str(final),str(aligned)],check=True)
with zipfile.ZipFile(BASE) as src,zipfile.ZipFile(final) as dst:
 for item in src.infolist():
  if item.filename.startswith('META-INF/') or item.filename=='lib/armeabi/libSrc.so':continue
  other=dst.getinfo(item.filename)
  assert (other.CRC,other.file_size)==(item.CRC,item.file_size),item.filename
 before=src.read('lib/armeabi/libSrc.so');after=dst.read('lib/armeabi/libSrc.so')
 assert before[:site]==after[:site] and before[site+4:]==after[site+4:]
subprocess.run(['java','-jar','K:/pvz2-tools/android-build-tools/android-14/lib/apksigner.jar','verify','--verbose',str(final)],check=True)
subprocess.run(['K:/pvz2-tools/android-build-tools/android-14/zipalign.exe','-c','4',str(final)],check=True)
record=dict(apk=str(final.relative_to(ROOT)),sha256=hashlib.file_digest(final.open('rb'),'sha256').hexdigest(),patch_site=hex(site),target=hex(target),only_four_native_bytes_changed=True,other_payloads_unchanged=True,runtime_verified=False)
(OUT/'build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
print(json.dumps(record))
