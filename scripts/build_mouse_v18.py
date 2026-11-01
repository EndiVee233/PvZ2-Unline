"""Extend the recovered pending-cursor lifecycle; package over v17 without device access."""
from pathlib import Path
from io import BytesIO
import hashlib, json, struct, shutil, zipfile
from elftools.elf.elffile import ELFFile
from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/mouse-v18'
BASE = ROOT / 'work/desktop-v17/PvZ2-v17-background-cache-mouse-hover.apk'
sha = lambda b: hashlib.sha256(b).hexdigest()
assert sha(BASE.read_bytes()) == '8f9bbc4b822cf7ee855a0a3f846f6ed6da4b2b0c8ec1ffaaa65406397aa15114'
OUT.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(BASE) as src:
    b = bytearray(src.read('lib/armeabi/libSrc.so'))
    elf = ELFFile(BytesIO(b))
    idx, seg = [(i,s) for i,s in enumerate(elf.iter_segments()) if s['p_type']=='PT_LOAD'][-1]
    assert seg['p_flags']==5 and seg['p_offset']+seg['p_filesz']==len(b)
    initial_size = len(b)
    patches = []
    def hook(site, expected, asm):
        before = bytes(b[site:site+4])
        if expected is not None: assert before.hex()==expected, (hex(site),before.hex())
        va = seg['p_vaddr'] + len(b) - seg['p_offset']
        code = bytes(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(asm,addr=va)[0])
        b.extend(code)
        struct.pack_into('<I',b,site,0xea000000|(((va-site-8)//4)&0xffffff))
        patches.append(dict(site=hex(site),before=before.hex(),after=b[site:site+4].hex(),stub_va=hex(va),assembly=asm))

    # r4 is the parsed touch record, r5 the Android driver. Hover never binds a
    # touch, promotes a cursor, or invokes a release/action callback.
    hook(0x132b660, None, '''cmp r3,#5
        beq hover
        cmp r3,#4
        b #0x132b664
        hover:
        mov r0,r5
        mov r1,r4
        bl #0x1327d0c
        ldr r0,[r5,#0x44]
        ldr r0,[r0,#0x6bc]
        cmp r0,#0
        beq done
        ldr r0,[r0,#0x94c]
        cmp r0,#0
        beq done
        ldrb r2,[r0,#0x1d]
        cmp r2,#0
        bne done
        add r1,r4,#8
        bl #0x1efccc
        done:
        b #0x132b688''')

    # Board's cursor drawing routine uses r4 as a scratch double later. Reserve
    # an aligned extra eight bytes and retain the address of its pending slot.
    assert b[0x20761c:0x207620].hex()=='14d04de2'
    b[0x20761c:0x207620]=bytes.fromhex('1cd04de2')
    hook(0x207678,'407994e5','''add r3,r4,#0x940
        add r3,r3,#0xc
        str r3,[fp,#-0x38]
        ldr r7,[r4,#0x940]
        b #0x20767c''')
    # Append a single pending-cursor iteration to the unchanged native draw loop.
    # Its original coordinate transform, graphics push/pop and preview draw all
    # run unchanged. r7==slot+4 is a local termination sentinel, not game state.
    hook(0x2077d8,'20d04be2','''ldr r3,[fp,#-0x38]
        add r2,r3,#4
        cmp r7,r2
        beq finish
        ldr r2,[r3]
        cmp r2,#0
        beq finish
        mov r7,r3
        add r8,r7,#4
        b #0x207698
        finish:
        sub sp,fp,#0x20
        b #0x2077dc''')
    # Animate/update the pending preview once per normal board update, rather
    # than at the rate of mouse messages. Original active-vector update remains.
    hook(0x20f534,'146a94e5','''ldr r0,[r4,#0x94c]
        cmp r0,#0
        beq resume
        ldrb r3,[r0,#0x1d]
        cmp r3,#0
        bne resume
        bl #0x1ef90c
        resume:
        ldr r6,[r4,#0xa14]
        b #0x20f538''')
    ph=elf['e_phoff']+idx*elf['e_phentsize']
    for p in [ph+16,ph+20]: struct.pack_into('<I',b,p,struct.unpack_from('<I',b,p)[0]+len(b)-initial_size)
    (OUT/'libSrc-v18.so').write_bytes(b)
    with zipfile.ZipFile(OUT/'unsigned.apk','w',allowZip64=True) as dst:
        for item in src.infolist():
            if item.filename.startswith('META-INF/'): continue
            if item.filename=='lib/armeabi/libSrc.so': dst.writestr(item,b)
            else:
                with src.open(item) as a,dst.open(item,'w') as c: shutil.copyfileobj(a,c,1024*1024)
record=dict(base=str(BASE),base_sha256=sha(BASE.read_bytes()),native_sha256=sha(b),
    changed_payloads=['lib/armeabi/libSrc.so'],device_verified=False,
    patches=patches,frame_reservation=dict(site='0x20761c',before='14d04de2',after='1cd04de2'))
(ROOT/'docs/recovery/mouse-v18-build.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(native_sha256=sha(b),hooks=len(patches),unsigned=str(OUT/'unsigned.apk'))))
