"""Compile the small preset importer as an additional DEX, using shipped codec."""
from pathlib import Path
import subprocess,zipfile,json,hashlib,sys
ROOT=Path(__file__).resolve().parents[1]
def build(out,test=False):
 out=Path(out);classes=out/'classes';dex=out/'dex';classes.mkdir(parents=True,exist_ok=True);dex.mkdir(exist_ok=True)
 jar=Path('Y:/Android/Sdk/platforms/android-34/android.jar')
 sources=[ROOT/'src/bootstrap-extra/com/popcap/pvz2cthd/PresetProfileImporter.java']
 if test:sources.append(ROOT/'src/bootstrap-extra-test/com/popcap/pvz2cthd/PresetImporterTest.java')
 subprocess.run(['javac','-encoding','UTF-8','-source','8','-target','8','-Xlint:-options','-bootclasspath',str(jar),'-d',str(classes),*[str(p) for p in sources]],check=True)
 archive=out/'classes.jar'
 with zipfile.ZipFile(archive,'w') as z:
  for p in sorted(classes.rglob('*.class')):z.write(p,p.relative_to(classes).as_posix())
 subprocess.run(['K:/pvz2-tools/jdk21/jdk-21.0.13+9/bin/java.exe','-Xmx256m','-cp','K:/pvz2-tools/android-build-tools/android-14/lib/d8.jar','com.android.tools.r8.D8','--min-api','21','--lib',str(jar),'--output',str(dex),str(archive)],check=True)
 raw=(dex/'classes.dex').read_bytes()
 (out/'build.json').write_text(json.dumps(dict(sha256=hashlib.sha256(raw).hexdigest(),sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},synthetic_test_only=test),indent=2)+'\n',encoding='utf8')
 return raw
if __name__=='__main__':build(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'work/preset-v86', '--test' in sys.argv)
