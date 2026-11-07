"""Overlay the Dave gameplay update on the accepted v103 art package."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'work/pvp-v104'
BASE = ROOT/'work/pvp-v103/PvZ2-v103-pvp-original-art.apk'
LIB = 'lib/armeabi/libSrc.so'
TOOLS = Path('K:/pvz2-tools/android-build-tools/android-14')


def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    assert digest(BASE) == '893d2cc7cfd1ea7c9ec4b6e50fa6d748dc144295ea4e2006625bc25872c9d4cd'
    if '--package-only' not in sys.argv:
        subprocess.run([sys.executable,str(ROOT/'scripts/build_pvp_v39.py'),'--v104','--compile-only'],cwd=ROOT,check=True)
    subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v104.py'),str(OUT)],cwd=ROOT,check=True)
    subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v101_focused.py'),str(OUT),'--sales-only'],cwd=ROOT,check=True)
    scratch=Path(sys.argv[sys.argv.index('--intermediate-dir')+1]).resolve() if '--intermediate-dir' in sys.argv else OUT
    scratch.mkdir(parents=True,exist_ok=True)
    with ZipFile(BASE) as src:
        # The compiled IDs and original resource-property addresses still use
        # exactly the accepted dynamic configuration; do not regress v103 art.
        assert src.read('assets/reconstruction/dynamic-original-speed.rsb.smf') == (OUT/'generated/dynamic-drag.rsb.smf').read_bytes()
        with ZipFile(scratch/'unsigned.apk','w',allowZip64=True) as dst:
            for item in src.infolist():
                if item.filename.startswith('META-INF/'): continue
                if item.filename == LIB: dst.writestr(item,(OUT/'libSrc.so').read_bytes())
                else:
                    with src.open(item) as source, dst.open(item,'w') as target:
                        shutil.copyfileobj(source,target,1048576)
    final=OUT/'PvZ2-v104-dave-reference.apk'
    align=str(TOOLS/'zipalign.exe'); signer=['java','-jar',str(TOOLS/'lib/apksigner.jar')]
    subprocess.run([align,'-f','4',str(scratch/'unsigned.apk'),str(scratch/'aligned.apk')],check=True)
    subprocess.run([*signer,'sign','--ks',str(ROOT/'work/keys/recovered-debug.keystore'),
                    '--ks-pass','pass:android','--key-pass','pass:android','--ks-key-alias','androiddebugkey',
                    '--out',str(final),str(scratch/'aligned.apk')],check=True)
    subprocess.run([*signer,'verify',str(final)],check=True)
    subprocess.run([align,'-c','4',str(final)],check=True)
    with ZipFile(BASE) as before, ZipFile(final) as after:
        def entries(z): return {i.filename:(i.file_size,i.CRC) for i in z.infolist() if not i.filename.startswith('META-INF/')}
        a,b=entries(before),entries(after)
        assert a.keys()==b.keys() and {k for k in a if a[k]!=b[k]}=={LIB}
        assert after.read(LIB)==(OUT/'libSrc.so').read_bytes()
    result=dict(apk=str(final.relative_to(ROOT)),sha256=digest(final),size=final.stat().st_size,
                changed_entries=[LIB],accepted_v103_art_preserved=True,
                dave=json.loads((OUT/'generated/dave-build.json').read_text()),runtime_game_verified=False)
    (OUT/'build.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='dave'}))


if __name__=='__main__': main()
