"""Overlay the native PvP update on the preceding accepted APK."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'work/pvp-v104/PvZ2-v104-dave-reference.apk'
LIB = 'lib/armeabi/libSrc.so'
TOOLS = Path('K:/pvz2-tools/android-build-tools/android-14')


def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    version = 107 if '--v107' in sys.argv else 106 if '--v106' in sys.argv else 105
    out = Path(sys.argv[sys.argv.index('--output-dir')+1]).resolve() if '--output-dir' in sys.argv else ROOT/f'work/pvp-v{version}'
    base = BASE
    expected = '80a6fdadd924a011e8aa0235baeec2dbb7f82980ab4e157b4a7800135db7af21'
    if version == 106:
        base = Path(sys.argv[sys.argv.index('--base-apk')+1]).resolve()
        expected = 'db8458222391926cabc7ac42e61fa0cbd56675117590ccae5db77c2f9edc337d'
    elif version == 107:
        base = Path(sys.argv[sys.argv.index('--base-apk')+1]).resolve()
        expected = '0fee25fcfdb94979f888ba9edad108f1cae91b2f99417163e86aa253e21cfe88'
    assert digest(base) == expected
    if '--package-only' not in sys.argv:
        subprocess.run([sys.executable,str(ROOT/'scripts/build_pvp_v39.py'),f'--v{version}','--compile-only','--output-dir',str(out)],cwd=ROOT,check=True)
    if version == 107:
        subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v107.py'),str(out)],cwd=ROOT,check=True)
    if version >= 106:
        subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v106.py'),str(out)],cwd=ROOT,check=True)
    subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v105.py'),str(out)],cwd=ROOT,check=True)
    subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v104.py'),str(out)],cwd=ROOT,check=True)
    subprocess.run([sys.executable,str(ROOT/'scripts/check_offline_pvp_v101_focused.py'),str(out),'--sales-only'],cwd=ROOT,check=True)
    scratch=Path(sys.argv[sys.argv.index('--intermediate-dir')+1]).resolve() if '--intermediate-dir' in sys.argv else out
    scratch.mkdir(parents=True,exist_ok=True)
    with ZipFile(base) as src:
        # The compiled IDs and original resource-property addresses still use
        # exactly the accepted dynamic configuration; do not regress v103 art.
        assert src.read('assets/reconstruction/dynamic-original-speed.rsb.smf') == (out/'generated/dynamic-drag.rsb.smf').read_bytes()
        with ZipFile(scratch/'unsigned.apk','w',allowZip64=True) as dst:
            for item in src.infolist():
                if item.filename.startswith('META-INF/'): continue
                if item.filename == LIB: dst.writestr(item,(out/'libSrc.so').read_bytes())
                else:
                    with src.open(item) as source, dst.open(item,'w') as target:
                        shutil.copyfileobj(source,target,1048576)
    finaldir=Path(sys.argv[sys.argv.index('--final-dir')+1]).resolve() if '--final-dir' in sys.argv else out
    finaldir.mkdir(parents=True,exist_ok=True)
    names = {105: 'PvZ2-v105-shop-opponents.apk', 106: 'PvZ2-v106-protection-cups.apk',
             107: 'PvZ2-v107-local-cup-matching.apk'}
    final = finaldir/names[version]
    align=str(TOOLS/'zipalign.exe'); signer=['java','-jar',str(TOOLS/'lib/apksigner.jar')]
    subprocess.run([align,'-f','4',str(scratch/'unsigned.apk'),str(scratch/'aligned.apk')],check=True)
    subprocess.run([*signer,'sign','--ks',str(ROOT/'work/keys/recovered-debug.keystore'),
                    '--ks-pass','pass:android','--key-pass','pass:android','--ks-key-alias','androiddebugkey',
                    '--out',str(final),str(scratch/'aligned.apk')],check=True)
    subprocess.run([*signer,'verify',str(final)],check=True)
    subprocess.run([align,'-c','4',str(final)],check=True)
    with ZipFile(base) as before, ZipFile(final) as after:
        def entries(z): return {i.filename:(i.file_size,i.CRC) for i in z.infolist() if not i.filename.startswith('META-INF/')}
        a,b=entries(before),entries(after)
        assert a.keys()==b.keys() and {k for k in a if a[k]!=b[k]}=={LIB}
        assert after.read(LIB)==(out/'libSrc.so').read_bytes()
    result=dict(apk=str(final),sha256=digest(final),size=final.stat().st_size,
                changed_entries=[LIB],accepted_v103_art_preserved=True,
                dave=json.loads((out/'generated/dave-build.json').read_text()),runtime_game_verified=False)
    (out/'build.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='dave'}))


if __name__=='__main__': main()
