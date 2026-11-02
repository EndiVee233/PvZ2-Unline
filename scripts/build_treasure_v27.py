"""Retire later Lucky Treasure tutorials as well as the first introduction."""
from pathlib import Path
from io import BytesIO
import hashlib,json,struct,shutil,zipfile
from elftools.elf.elffile import ELFFile
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/treasure-v27';OUT.mkdir(exist_ok=True)
BASE=ROOT/'work/trial-v26/PvZ2-v26-trial-offer-transition-fix.apk'
assert hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest()=='7ba9869bda759650ddcfbc4762023672498c2b5a46fe7fc7c34b23ec23726dcc'
patches=[]
with zipfile.ZipFile(BASE) as src:
    blob=bytearray(src.read('lib/armeabi/libSrc.so'));e=ELFFile(BytesIO(blob))
    idx,tail=[(i,s) for i,s in enumerate(e.iter_segments()) if s['p_type']=='PT_LOAD'][-1]
    oldlen=len(blob);assert tail['p_offset']+tail['p_filesz']==oldlen and tail['p_flags']==5
    def branch(site,target):
        delta=target-site-8;assert delta%4==0 and -(1<<25)<=delta<(1<<25)
        return struct.pack('<I',0xea000000|((delta//4)&0xffffff))
    def patch(va,expected,data,role):
        assert blob[va:va+len(expected)]==expected,(role,hex(va))
        blob[va:va+len(data)]=data
        patches.append(dict(va=hex(va),before=expected.hex(),after=data.hex(),role=role))
    instruction=struct.unpack_from('<I',blob,0x709808)[0];assert instruction>>24==0xea
    offset=instruction&0xffffff;offset=offset-0x1000000 if offset&0x800000 else offset
    prior=0x709808+8+offset*4
    while len(blob)%4:blob.append(0)
    stub=tail['p_vaddr']+len(blob)-tail['p_offset']
    asm=f'''cmp r1,#21
    moveq r0,#1
    bxeq lr
    cmp r1,#23
    moveq r0,#1
    bxeq lr
    b #{prior}'''
    blob.extend(bytes(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(asm,addr=stub)[0]))
    patch(0x709808,struct.pack('<I',instruction),branch(0x709808,stub),
          'retire tutorials 21 and 23 before map overlay/input-lock state is written; retain previous 15/18 hook')
    # Drawer tutorial modes 4/6/7 belong to IDs 15/21/23. Modes 6/7
    # explicitly point at the second child (+0xa8), the hidden Lucky button.
    # Clear modes at their source, before initializer/arrow/locking code.
    for va,mode,ident in [(0xa38844,4,15),(0xa38864,6,21),(0xa38874,7,23)]:
        patch(va,bytes([mode,0x30,0xa0,0x03]),bytes.fromhex('0030a003'),
              f'drawer tutorial {ident}: select no-guide mode instead of mode {mode}')
    added=len(blob)-oldlen;ph=e['e_phoff']+idx*e['e_phentsize']
    for off in (16,20):struct.pack_into('<I',blob,ph+off,struct.unpack_from('<I',blob,ph+off)[0]+added)
    (OUT/'libSrc.so').write_bytes(blob)
    with zipfile.ZipFile(OUT/'unsigned.apk','w',allowZip64=True) as dst:
        for item in src.infolist():
            if item.filename.startswith('META-INF/'):continue
            if item.filename=='lib/armeabi/libSrc.so':dst.writestr(item,blob)
            else:
                with src.open(item) as a,dst.open(item,'w') as b:shutil.copyfileobj(a,b,1024*1024)
result=dict(base=str(BASE),patches=patches,previous_tutorial_hook=hex(prior),tutorial_hook=hex(stub),
            assembly=asm,native_sha256=hashlib.sha256(blob).hexdigest(),
            device_verified=False,game_validation_skipped_per_user=True,
            inherited_trial_offer_transition_fix=True)
(ROOT/'docs/recovery/treasure-v27-build.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
