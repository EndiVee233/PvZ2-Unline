"""Move native library loading to the visible bootstrap's worker, in its DEX."""
import argparse,hashlib,json,os,shutil,struct,subprocess,zlib
from pathlib import Path
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]


def prepare(apk,output,sdk):
    output.mkdir(parents=True,exist_ok=True)
    with ZipFile(apk) as z:original=z.read('classes8.dex')
    original_path=output/'original.dex';original_path.write_bytes(original)
    classes=output/'classes';classes.mkdir(exist_ok=True)
    source=ROOT/'src/bootstrap-extra/com/popcap/pvz2cthd/AsterNativeWarmup.java'
    android=sdk/'platforms/android-34/android.jar'
    subprocess.run(['javac','-encoding','UTF-8','-source','8','-target','8','-Xlint:-options','-classpath',android,'-d',classes,source],check=True)
    jar=output/'warmup.jar'
    with ZipFile(jar,'w') as z:
        for p in classes.rglob('*.class'):z.write(p,p.relative_to(classes).as_posix())
    dex=output/'dex';dex.mkdir(exist_ok=True)
    java21=Path('M:/Program Files/Zulu/zulu-21/bin/java.exe')
    subprocess.run([java21,'-Xmx256m','-cp',sdk/'build-tools/34.0.0/lib/d8.jar','com.android.tools.r8.D8',
                    '--min-api','21','--lib',android,'--output',dex,jar],check=True)
    apktool=ROOT/'tools/apktool.jar'
    subprocess.run(['javac','-cp',apktool,'-d',output,ROOT/'scripts/RepairDex.java'],check=True)
    repair=['java','-Xmx256m','-cp',str(apktool)+os.pathsep+str(output),'RepairDex']
    smali=output/'smali';helper=output/'helper-smali'
    subprocess.run([*repair,'decode',original_path,smali],check=True)
    subprocess.run([*repair,'decode',dex/'classes.dex',helper],check=True)
    before={p.relative_to(smali).as_posix():p.read_bytes() for p in smali.rglob('*.smali')}
    boot=smali/'com/popcap/pvz2cthd/BootActivity.smali';text=boot.read_text(encoding='utf8')
    signature='.method private startGame()V'
    if text.count(signature)!=1:raise ValueError('Unknown bootstrap launch method')
    text=text.replace(signature,'.method private asterLaunchReady()V',1)
    text+='''
.method private startGame()V
    .registers 1
    invoke-static {p0}, Lcom/popcap/pvz2cthd/AsterNativeWarmup;->prepare(Landroid/app/Activity;)V
    return-void
.end method
'''
    boot.write_text(text,encoding='utf8')
    added=[]
    for p in helper.rglob('*.smali'):
        relative=p.relative_to(helper)
        if not relative.name.startswith('AsterNativeWarmup'):raise ValueError('Unexpected helper class')
        target=smali/relative
        if target.exists():raise ValueError('Duplicate bootstrap helper')
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);added.append(relative.as_posix())
    changed=[name for name,data in before.items() if (smali/name).read_bytes()!=data]
    assert changed==['com/popcap/pvz2cthd/BootActivity.smali'],changed
    target=output/'classes8.dex'
    subprocess.run([*repair,'encode',smali,target],check=True)
    data=target.read_bytes();assert hashlib.sha1(data[32:]).digest()==data[12:32]
    assert zlib.adler32(data[12:])&0xffffffff==struct.unpack_from('<I',data,8)[0]
    report=dict(source_dex_sha256=hashlib.sha256(original).hexdigest(),dex_sha256=hashlib.sha256(data).hexdigest(),
                added_classes=added,only_original_class_changed=changed[0],same_dex_classloader=True,runtime_verified=False)
    (output/'warmup-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
    return target


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','output','sdk'):p.add_argument(name,type=Path)
    prepare(**vars(p.parse_args()))
