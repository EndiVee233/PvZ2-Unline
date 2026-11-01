"""Skip PlantTrial purchase recommendations, retaining the trial level itself."""
from pathlib import Path
from io import BytesIO
import hashlib, json, shutil, zipfile
from elftools.elf.elffile import ELFFile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/trial-v25';OUT.mkdir(exist_ok=True)
BASE=ROOT/'work/adventure-v24/PvZ2-v24-offline-adventure-no-lucky-treasure.apk'
assert hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest()=='3dbc4d5abb2d8a39942d40a28b1b60f14fb632b4d7f68797e49f3bc936e83d5d'
patches=[]
with zipfile.ZipFile(BASE) as src:
    original=src.read('lib/armeabi/libSrc.so');blob=bytearray(original)
    segments=[s for s in ELFFile(BytesIO(original)).iter_segments() if s['p_type']=='PT_LOAD']
    def patch(va,expected,data,role):
        seg=next(s for s in segments if s['p_vaddr']<=va<s['p_vaddr']+s['p_filesz'])
        off=seg['p_offset']+va-seg['p_vaddr']
        assert blob[off:off+len(expected)]==expected,(role,hex(va))
        blob[off:off+len(data)]=data
        patches.append(dict(va=hex(va),offset=off,before=expected.hex(),after=data.hex(),role=role))
    # ActionShowPlantTrial's start function normally creates the offer, waits
    # for its close event and sets a profile flag. Complete the action instead.
    # Map scheduler 0x9e9dc0 checks action+5, then runs its original end/destructor.
    patch(0xa13804,bytes.fromhex('f04f2de934739fe534339fe5'),
          bytes.fromhex('0130a0e30530c0e51eff2fe1'),
          'ActionShowPlantTrial: set completed byte and return without opening/waiting')
    # This is the sole native UI_PlantTrial constructor owner (call at 0x40ca74).
    # Block alternate event-driven opens too, before allocation or modal setup.
    patch(0x40c9c4,bytes.fromhex('f0482de94a5da0e3'),bytes.fromhex('0000a0e31eff2fe1'),
          'LawnApp PlantTrial offer show: return before allocation and modal setup')
    allowed={i for p in patches for i in range(p['offset'],p['offset']+len(bytes.fromhex(p['after'])))}
    assert len(original)==len(blob)
    assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(original,blob)))
    (OUT/'libSrc.so').write_bytes(blob)
    with zipfile.ZipFile(OUT/'unsigned.apk','w',allowZip64=True) as dst:
        for entry in src.infolist():
            if entry.filename.startswith('META-INF/'):continue
            if entry.filename=='lib/armeabi/libSrc.so':dst.writestr(entry,blob)
            else:
                with src.open(entry) as a,dst.open(entry,'w') as b:shutil.copyfileobj(a,b,1024*1024)
result=dict(base=str(BASE),patches=patches,native_sha256=hashlib.sha256(blob).hexdigest(),
            device_verified=False,scope='Skip purchase offer; preserve trial plants, level rewards and offline adventures')
(ROOT/'docs/recovery/trial-v25-build.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
