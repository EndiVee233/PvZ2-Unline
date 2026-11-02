"""Accept shipped resource predecessors when upgrading v27 to offline NPC v28."""
from pathlib import Path
import zipfile,hashlib,subprocess,os,json,shutil
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/bootstrap-v29';OUT.mkdir(exist_ok=True)
BASE=ROOT/'work/pvp-v28/PvZ2-v28-offline-npc-practice.apk'
assert hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest()=='f6770a24872e08178c46c0e65a0985e4d641aee75fb4f6d8a773169800c0e776'
accepted=['f835e0f3fe60466dbf81a71c4850f2eb086390103c70709f15991b474657219c',
          '0aae11cf23e05377026323816f6e458264bdc193b312177bca6824589fa1d29f',
          '12af3e81260ee7ad2a438a9175506839474a1ec4b7aa39b61ed9bda7fdda5835']
os.environ['TEMP']=os.environ['TMP']=str(ROOT/'work/tmp')
with zipfile.ZipFile(BASE) as src:
 (OUT/'original.dex').write_bytes(src.read('classes8.dex'))
 cp=str(ROOT/'tools/apktool.jar')+os.pathsep+str(ROOT/'work/pvp-v28/bootstrap')
 subprocess.run(['java','-Xmx256m','-cp',cp,'RepairDex','decode',str(OUT/'original.dex'),str(OUT/'smali')],check=True)
 p=OUT/'smali/com/popcap/pvz2cthd/BootActivity.smali';s=p.read_text(encoding='utf8')
 needle='invoke-virtual {v6, v5}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z'
 assert s.count(needle)==1
 s=s.replace(needle,'invoke-static {v5}, Lcom/popcap/pvz2cthd/BootActivity;->isSupportedResourcePredecessor(Ljava/lang/String;)Z')
 s=s.replace('.offline-npc-v28','.offline-npc-v29')
 helper='\n.method private static isSupportedResourcePredecessor(Ljava/lang/String;)Z\n    .locals 1\n'
 for i,h in enumerate(accepted):
  helper+=f'''    const-string v0, "{h}"
    invoke-virtual {{v0, p0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :accepted
'''
 helper+='''    const/4 v0, 0x0
    return v0
    :accepted
    const/4 v0, 0x1
    return v0
.end method
'''
 s+=helper;p.write_text(s,encoding='utf8')
 subprocess.run(['java','-Xmx256m','-cp',cp,'RepairDex','encode',str(OUT/'smali'),str(OUT/'classes8.dex')],check=True)
 dex=(OUT/'classes8.dex').read_bytes()
 with zipfile.ZipFile(OUT/'unsigned.apk','w',allowZip64=True) as dst:
  for item in src.infolist():
   if item.filename.startswith('META-INF/'):continue
   if item.filename=='classes8.dex':dst.writestr(item,dex)
   else:
    with src.open(item) as a,dst.open(item,'w') as b:shutil.copyfileobj(a,b,1024*1024)
record=dict(base=str(BASE),accepted_predecessors=accepted,
            installed_resource_before_upgrade=accepted[0],
            target_resource_sha256='cd4626cfc3afe0148962b14564c4bd27f185063c4d1bf9dd4a8c7d705d303bf5',
            target_checksum_verification_preserved=True,game_verified=False,
            changed_payloads=['classes8.dex'])
(ROOT/'docs/recovery/bootstrap-v29-build.json').write_text(json.dumps(record,indent=2)+'\n')
print('Built resource-upgrade compatibility fix')
