"""Seagull art-only update on the accepted formal v99 APK."""
from pathlib import Path
from zipfile import ZipFile
import hashlib,json,shutil,subprocess,sys
from prepare_offline_pvp_seagull_hd import prepare,normal_resource
from rebuild_bootstrap_dex import rebuild_bootstrap
from check_offline_pvp_v100_seagull import check

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/pvp-v100';OUT.mkdir(parents=True,exist_ok=True)
BASE=ROOT/'work/pvp-v99/PvZ2-v99-pvp-scene-candidate.apk'
assert hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest()=='11beb0891ddcc0e8884c25e362d46b6c71cd7f5536cd61b1a60de7100b8d84d2'
normal=normal_resource(BASE);legacy=(ROOT/'work/pvp-v61/original175-zombie1.smf').read_bytes()
with ZipFile(BASE) as src:
 old=src.read('assets/reconstruction/zombie2-pvp.rsb.smf');art,record=prepare(old,normal,legacy,OUT/'generated')
 oldsha,newsha=record['predecessor_sha256'],record['sha256']
 method='.method private static isPvpResourcePredecessor(Ljava/lang/String;)Z\n    .registers 2'
 extra=f'\n\n    const-string v0, "{oldsha}"\n    invoke-virtual {{v0, p0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n    move-result v0\n    if-eqz v0, :v100_art_previous\n    const/4 v0, 0x1\n    return v0\n    :v100_art_previous'
 dex=rebuild_bootstrap(src.read('classes8.dex'),OUT/'bootstrap',
  {oldsha:newsha,method:method+extra,'.pvp-seagull-v61-'+oldsha[:12]:'.pvp-seagull-v100-'+newsha[:12],hex(len(old)):hex(len(art))},ROOT/'tools/apktool.jar')
 check(OUT,BASE,normal,legacy)
 if '--assets-only' in sys.argv:raise SystemExit(0)
 unsigned=OUT/'unsigned.apk';aligned=OUT/'aligned.apk';final=OUT/'PvZ2-v100-seagull-art-candidate.apk'
 with ZipFile(unsigned,'w',allowZip64=True) as dst:
  for item in src.infolist():
   if item.filename.startswith('META-INF/'):continue
   if item.filename=='classes8.dex':dst.writestr(item,dex)
   elif item.filename=='assets/reconstruction/zombie2-pvp.rsb.smf':dst.writestr(item,art)
   else:
    with src.open(item) as a,dst.open(item,'w') as b:shutil.copyfileobj(a,b,1048576)
subprocess.run(['K:/pvz2-tools/android-build-tools/android-14/zipalign.exe','-f','4',str(unsigned),str(aligned)],check=True)
signer=['java','-jar','K:/pvz2-tools/android-build-tools/android-14/lib/apksigner.jar']
subprocess.run([*signer,'sign','--ks',str(ROOT/'work/keys/recovered-debug.keystore'),'--ks-pass','pass:android','--key-pass','pass:android','--ks-key-alias','androiddebugkey','--out',str(final),str(aligned)],check=True)
subprocess.run([*signer,'verify',str(final)],check=True)
subprocess.run(['K:/pvz2-tools/android-build-tools/android-14/zipalign.exe','-c','4',str(final)],check=True)
checks=check(OUT,BASE,normal,legacy,final)
build={'apk':str(final.relative_to(ROOT)),'sha256':hashlib.file_digest(final.open('rb'),'sha256').hexdigest(),'size':final.stat().st_size,
 'base_apk':str(BASE.relative_to(ROOT)),'art':record,'checks':checks,'changed_payloads':['assets/reconstruction/zombie2-pvp.rsb.smf','classes8.dex'],'runtime_game_verified':False}
(OUT/'build.json').write_text(json.dumps(build,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:build[k] for k in ('apk','sha256','size','changed_payloads','runtime_game_verified')}))
