"""Package the preset editor and GitHub matchmaking over accepted v107."""
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
import hashlib,json,os,re,subprocess,sys,shutil
from elftools.elf.elffile import ELFFile
from rebuild_bootstrap_dex import rebuild_bootstrap

ROOT=Path(__file__).resolve().parents[1]
VERSION=123
UNREGISTERED_EDITOR_RESOURCE='30aa5b432abc154d86e15ac27db8f4740296b3a95ced95be198712eeb2c20e1a'
UNFILTERED_EDITOR_RESOURCE='8d96905dbd01666912c5dd5bff65cf984d878c4a53f13c03d5b686dc693c3a32'
OUT=Path(f'C:/Users/SpokeIsThere/AppData/Local/Temp/pvz2-v{VERSION}-build')
BASE=Path('C:/Users/SpokeIsThere/Downloads/pvz2-builds/v107/PvZ2-v107-local-cup-matching.apk')
TOOLS=Path('K:/pvz2-tools/android-build-tools/android-14')
CLANG='Y:/Android/Sdk/ndk/27.0.12077973/toolchains/llvm/prebuilt/windows-x86_64/bin/clang++.exe'
ANDROID=Path('Y:/Android/Sdk/platforms/android-34/android.jar')
MUSIC={
    'assets/pvp-music/street.mp3':ROOT/'Mintaka-3 - 花园战争-街区.mp3',
    'assets/pvp-music/battle.mp3':ROOT/'Mintaka-3 - 花园战争-对战.mp3',
}
def run(args):subprocess.run([str(x) for x in args],cwd=ROOT,check=True)
def sha(data):return hashlib.sha256(data).hexdigest()

def bridge():
    out=OUT/'bridge';out.mkdir(parents=True,exist_ok=True)
    code=OUT/'code';elf=ELFFile(BytesIO((code/'offline.elf').read_bytes()))
    symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
    (out/'preset_bridge_addresses.h').write_text(
        '#define EDITOR_COMMAND %d\n#define EDITOR_POLL %d\n#define EDITOR_MUSIC_SAMPLE %d\n'%
        (symbols['offlinePresetCommand'],symbols['offlinePresetPoll'],symbols['offlinePvpMusicSample']))
    run([CLANG,'--target=armv7a-linux-androideabi21','-marm','-Os','-shared','-fPIC','-fno-exceptions','-fno-rtti','-nostdlib++','-Wl,--no-undefined','-Wl,-soname,libPresetEditor.so','-I'+str(out),ROOT/'src/preset-editor/bridge.cpp','-ldl','-o',out/'libPresetEditor.so'])
    classes=out/'classes';classes.mkdir(exist_ok=True);dex=out/'dex';dex.mkdir(exist_ok=True)
    sources=[ROOT/'src/bootstrap-extra/com/popcap/pvz2cthd'/name for name in ('PvpPresetDocument.java','PvpLevelStorage.java','PresetEditor.java','GithubPresetCatalog.java','PvpMusic.java')]
    run(['javac','-encoding','UTF-8','-source','8','-target','8','-Xlint:-options','-classpath',ANDROID,'-d',classes,*sources])
    with ZipFile(out/'editor.jar','w') as z:
        for p in classes.rglob('*.class'):z.write(p,p.relative_to(classes).as_posix())
    run(['K:/pvz2-tools/jdk21/jdk-21.0.13+9/bin/java.exe','-Xmx256m','-cp',TOOLS/'lib/d8.jar','com.android.tools.r8.D8','--min-api','21','--lib',ANDROID,'--output',dex,out/'editor.jar'])
    run(['javac','-cp',ROOT/'tools/apktool.jar','-d',out,ROOT/'scripts/RepairDex.java'])
    repair=['java','-Xmx384m','-cp',os.pathsep.join([str(ROOT/'tools/apktool.jar'),str(out)]),'RepairDex']
    with ZipFile(BASE) as z:(out/'game.dex').write_bytes(z.read('classes.dex'))
    # Always decode pristine input, so repeated packaging is idempotent.
    run([*repair,'decode',out/'game.dex',out/'smali'])
    renderer=out/'smali/com/popcap/SexyAppFramework/AndroidSurfaceView$AndroidRenderer.smali'
    s=renderer.read_text(encoding='utf8');needle='    invoke-static {p1}, Lcom/popcap/SexyAppFramework/AndroidSurfaceView;->access$300(Lcom/popcap/SexyAppFramework/AndroidSurfaceView;)V'
    assert s.count(needle)==1;s=s.replace(needle,needle+'\n\n    invoke-static {}, Lcom/popcap/pvz2cthd/PresetEditor;->frame()V');renderer.write_text(s,encoding='utf8')
    activity=out/'smali/com/popcap/SexyAppFramework/SexyAppFrameworkActivity.smali';s=activity.read_text(encoding='utf8')
    needle='.method protected onActivityResult(IILandroid/content/Intent;)V\n    .registers 6'
    assert s.count(needle)==1
    s=s.replace(needle,needle+'\n\n    invoke-static {p0, p1, p2, p3}, Lcom/popcap/pvz2cthd/PresetEditor;->onActivityResult(Landroid/app/Activity;IILandroid/content/Intent;)Z\n    move-result v0\n    if-eqz v0, :preset_original_result\n    return-void\n    :preset_original_result')
    for callback,hook in (
        ('onResume','    const/4 v0, 0x1\n    invoke-static {v0}, Lcom/popcap/pvz2cthd/PvpMusic;->setForeground(Z)V'),
        ('onPause','    const/4 v0, 0x0\n    invoke-static {v0}, Lcom/popcap/pvz2cthd/PvpMusic;->setForeground(Z)V'),
        ('onDestroy','    invoke-static {}, Lcom/popcap/pvz2cthd/PvpMusic;->shutdown()V'),
    ):
        entry=f'.method public {callback}()V\n    .registers 3'
        assert s.count(entry)==1
        s=s.replace(entry,entry+'\n\n'+hook)
    activity.write_text(s,encoding='utf8');run([*repair,'encode',out/'smali',out/'game-patched.dex'])
    return out

def main():
    OUT.mkdir(exist_ok=True)
    if '--package-only' not in sys.argv:run([sys.executable,ROOT/'scripts/build_pvp_v39.py',f'--v{VERSION}','--compile-only','--output-dir',OUT/'code'])
    b=bridge();code=OUT/'code';resource=(code/'generated/dynamic-preset-editor.rsb.smf').read_bytes()
    with ZipFile(BASE) as z:
        old=z.read('assets/reconstruction/dynamic-original-speed.rsb.smf')
        method='.method private static isSupportedResourcePredecessor(Ljava/lang/String;)Z\n    .registers 2'
        extra=''
        for index,digest in enumerate((sha(old),UNREGISTERED_EDITOR_RESOURCE,UNFILTERED_EDITOR_RESOURCE)):
            label=f':preset_resource_predecessor_{index}'
            extra+=f'\n\n    const-string v0, "{digest}"\n    invoke-virtual {{v0, p0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n    move-result v0\n    if-eqz v0, {label}\n    const/4 v0, 0x1\n    return v0\n    {label}'
        boot=rebuild_bootstrap(z.read('classes8.dex'),OUT/'bootstrap',{sha(old):sha(resource),'.offline-pvp-v59-'+sha(old)[:12]:'.offline-pvp-v59-'+sha(resource)[:12],method:method+extra,hex(len(old)):hex(len(resource))},ROOT/'tools/apktool.jar')
        entries={'lib/armeabi/libSrc.so':(code/'libSrc.so').read_bytes(),'lib/armeabi/libPresetEditor.so':(b/'libPresetEditor.so').read_bytes(),
                 'classes.dex':(b/'game-patched.dex').read_bytes(),'classes8.dex':boot,'classes10.dex':(b/'dex/classes.dex').read_bytes(),
                 'assets/reconstruction/dynamic-original-speed.rsb.smf':resource,'assets/pvp-presets/catalogue.json':(code/'generated/preset-editor-catalogue.json').read_bytes()}
        with ZipFile(OUT/'unsigned.apk','w',allowZip64=True) as dst:
            for item in z.infolist():
                if item.filename.startswith('META-INF/'):continue
                if item.filename in entries:dst.writestr(item,entries.pop(item.filename))
                else:
                    with z.open(item) as src,dst.open(item,'w') as target:shutil.copyfileobj(src,target,1048576)
            for name,data in entries.items():dst.writestr(name,data,compress_type=ZIP_DEFLATED)
            for name,path in MUSIC.items():dst.write(path,name,compress_type=ZIP_STORED)
    finaldir=Path(f'C:/Users/SpokeIsThere/Downloads/pvz2-builds/v{VERSION}');finaldir.mkdir(parents=True,exist_ok=True)
    final=finaldir/f'PvZ2-v{VERSION}-preset-editor.apk'
    run([TOOLS/'zipalign.exe','-f','4',OUT/'unsigned.apk',OUT/'aligned.apk'])
    sign=['java','-jar',TOOLS/'lib/apksigner.jar'];run([*sign,'sign','--ks',ROOT/'work/keys/recovered-debug.keystore','--ks-pass','pass:android','--key-pass','pass:android','--ks-key-alias','androiddebugkey','--out',final,OUT/'aligned.apk'])
    run([*sign,'verify',final]);run([TOOLS/'zipalign.exe','-c','4',final])
    allowed={'lib/armeabi/libSrc.so','lib/armeabi/libPresetEditor.so','classes.dex','classes8.dex','classes10.dex','assets/reconstruction/dynamic-original-speed.rsb.smf','assets/pvp-presets/catalogue.json',*MUSIC}
    with ZipFile(BASE) as a,ZipFile(final) as z:
        before={i.filename:(i.CRC,i.file_size) for i in a.infolist() if not i.filename.startswith('META-INF/')}
        after={i.filename:(i.CRC,i.file_size) for i in z.infolist() if not i.filename.startswith('META-INF/')}
        changed={k for k in after if after[k]!=before.get(k)}
        assert before.keys()<=after.keys() and changed==allowed,changed
        assert len(z.read('classes10.dex'))>0
        assert all(z.getinfo(name).compress_type==ZIP_STORED and sha(z.read(name))==sha(path.read_bytes())
                   for name,path in MUSIC.items())
    with final.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    record=dict(apk=str(final),sha256=digest,size=final.stat().st_size,changed_entries=sorted(changed),runtime_verified=False)
    (OUT/'build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
if __name__=='__main__':main()
