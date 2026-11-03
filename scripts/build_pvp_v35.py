"""Preload the native in-battle atlas used by defense return-card animations."""
from pathlib import Path
import hashlib,json,zipfile,struct,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'work/pvp-v34/PvZ2-v34-defense-flags-network.apk'
OUT=ROOT/'work/pvp-v35';OUT.mkdir(exist_ok=True)
assert hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest()=='c2d4ebc2c363c48e9cb4f01e5aafe09849788a6cec8a3a8e960858e189a10499'
site,target=0x1093d40,0x403988
def bl(a,t):return struct.pack('<I',0xeb000000|(((t-a-8)//4)&0xffffff))
with zipfile.ZipFile(BASE) as src:
 native=bytearray(src.read('lib/armeabi/libSrc.so'))
 assert native[site:site+4]==struct.pack('<I',0xe3a00000)
 subprocess.run(['python',str(ROOT/'scripts/restore_defense_flags.py'),'--with-inbattleanim'],check=True)
 resource=(ROOT/'work/pvp-v33/dynamic-flags.rsb.smf').read_bytes()
 from rebuild_bootstrap_dex import rebuild_bootstrap
 oldsha='0b9fce0df6a190018cd6710726643bcd75b8b47aedcda93cdf63e4389526e140'
 method='.method private static isSupportedResourcePredecessor(Ljava/lang/String;)Z\n    .registers 2'
 extra=f'\n\n    const-string v0, "{oldsha}"\n    invoke-virtual {{v0, p0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n    move-result v0\n    if-eqz v0, :check_older_versions\n    const/4 v0, 0x1\n    return v0\n    :check_older_versions'
 dex=rebuild_bootstrap(src.read('classes8.dex'),OUT/'bootstrap',{
  oldsha:hashlib.sha256(resource).hexdigest(),method:method+extra,
  '.offline-defense-v34':'.offline-defense-v35','0x165f000':hex(len(resource))},ROOT/'tools/apktool.jar')
 unsigned=OUT/'unsigned.apk';aligned=OUT/'aligned.apk'
 final=OUT/'PvZ2-v35-defense-card-return.apk'
 with zipfile.ZipFile(unsigned,'w',allowZip64=True) as dst:
  for item in src.infolist():
   if item.filename.startswith('META-INF/'):continue
   if item.filename=='lib/armeabi/libSrc.so':dst.writestr(item,native)
   elif item.filename=='classes8.dex':dst.writestr(item,dex)
   elif item.filename=='assets/reconstruction/dynamic-original-speed.rsb.smf':dst.writestr(item,resource)
   else:
    with src.open(item) as a,dst.open(item,'w') as b:shutil.copyfileobj(a,b,1048576)
subprocess.run(['K:/pvz2-tools/android-build-tools/android-14/zipalign.exe','-f','4',str(unsigned),str(aligned)],check=True)
subprocess.run(['java','-jar','K:/pvz2-tools/android-build-tools/android-14/lib/apksigner.jar','sign','--ks',str(ROOT/'work/keys/recovered-debug.keystore'),'--ks-pass','pass:android','--key-pass','pass:android','--ks-key-alias','androiddebugkey','--out',str(final),str(aligned)],check=True)
with zipfile.ZipFile(BASE) as src,zipfile.ZipFile(final) as dst:
 for item in src.infolist():
  if item.filename.startswith('META-INF/') or item.filename in ('lib/armeabi/libSrc.so','classes8.dex','assets/reconstruction/dynamic-original-speed.rsb.smf'):continue
  other=dst.getinfo(item.filename)
  assert (other.CRC,other.file_size)==(item.CRC,item.file_size),item.filename
 before=src.read('lib/armeabi/libSrc.so');after=dst.read('lib/armeabi/libSrc.so')
 assert before==after
subprocess.run(['java','-jar','K:/pvz2-tools/android-build-tools/android-14/lib/apksigner.jar','verify','--verbose',str(final)],check=True)
subprocess.run(['K:/pvz2-tools/android-build-tools/android-14/zipalign.exe','-c','4',str(final)],check=True)
record=dict(apk=str(final.relative_to(ROOT)),sha256=hashlib.file_digest(final.open('rb'),'sha256').hexdigest(),native_unchanged=True,changed_payloads=['classes8.dex','assets/reconstruction/dynamic-original-speed.rsb.smf'],resource_sha256=hashlib.sha256(resource).hexdigest(),runtime_verified=False)
(OUT/'build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
print(json.dumps(record))
