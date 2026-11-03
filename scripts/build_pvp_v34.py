"""Restore defense flags and suppress the diagnosed local-defense error modal."""
from pathlib import Path
import hashlib,json,zipfile,struct,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'work/pvp-v33/PvZ2-v33-local-defense-entry.apk'
OUT=ROOT/'work/pvp-v34';OUT.mkdir(exist_ok=True)
assert hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest()=='e64043c761cab6d979ea7882a6561f4d54570ad1a210ce6c7d742a9aa07f428c'
site,target=0x1093d40,0x403988
def bl(a,t):return struct.pack('<I',0xeb000000|(((t-a-8)//4)&0xffffff))
with zipfile.ZipFile(BASE) as src:
 native=bytearray(src.read('lib/armeabi/libSrc.so'))
 assert native[site:site+4]==bl(site,target)
 native[site:site+4]=struct.pack('<I',0xe3a00000)
 subprocess.run(['python',str(ROOT/'scripts/restore_defense_flags.py')],check=True)
 resource=(ROOT/'work/pvp-v33/dynamic-flags.rsb.smf').read_bytes()
 from rebuild_bootstrap_dex import rebuild_bootstrap
 oldsha='cd4626cfc3afe0148962b14564c4bd27f185063c4d1bf9dd4a8c7d705d303bf5'
 method='.method private static isSupportedResourcePredecessor(Ljava/lang/String;)Z\n    .registers 2'
 extra=f'\n\n    const-string v0, "{oldsha}"\n    invoke-virtual {{v0, p0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n    move-result v0\n    if-nez v0, :cond_1a'
 dex=rebuild_bootstrap(src.read('classes8.dex'),OUT/'bootstrap',{
  oldsha:hashlib.sha256(resource).hexdigest(),method:method+extra,
  '.offline-npc-v29':'.offline-defense-v34','0x165e000':hex(len(resource))},ROOT/'tools/apktool.jar')
 unsigned=OUT/'unsigned.apk';aligned=OUT/'aligned.apk'
 final=OUT/'PvZ2-v34-defense-flags-network.apk'
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
 assert before[:site]==after[:site] and before[site+4:]==after[site+4:]
subprocess.run(['java','-jar','K:/pvz2-tools/android-build-tools/android-14/lib/apksigner.jar','verify','--verbose',str(final)],check=True)
subprocess.run(['K:/pvz2-tools/android-build-tools/android-14/zipalign.exe','-c','4',str(final)],check=True)
record=dict(apk=str(final.relative_to(ROOT)),sha256=hashlib.file_digest(final.open('rb'),'sha256').hexdigest(),patch_site=hex(site),only_four_native_bytes_changed=True,changed_payloads=['lib/armeabi/libSrc.so','classes8.dex','assets/reconstruction/dynamic-original-speed.rsb.smf'],resource_sha256=hashlib.sha256(resource).hexdigest(),runtime_verified=False)
(OUT/'build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
print(json.dumps(record))
