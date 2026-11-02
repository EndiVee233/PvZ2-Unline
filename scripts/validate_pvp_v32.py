"""Check the full APK and exercise rebuilt resource tries in original ARM code."""
from pathlib import Path
from io import BytesIO
import hashlib, json, struct, subprocess, zipfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import *
from merge_legacy_pvp_resources import Bundle, trie_read, u32

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'work/pvp-v32'
record = json.loads((P / 'build.json').read_text(encoding='utf8'))
apk = ROOT / record['apk']
assert not record['thin']
assert hashlib.file_digest(apk.open('rb'), 'sha256').hexdigest() == record['apk_sha256']
with zipfile.ZipFile(apk) as z, zipfile.ZipFile(ROOT / record['base']) as original:
    native = z.read('lib/armeabi/libSrc.so')
    bundle = Bundle(z.read('assets/reconstruction/zombie2-pvp.rsb.smf'))
    changed = []
    for item in original.infolist():
        if item.filename.startswith('META-INF/'):
            continue
        new = z.getinfo(item.filename)
        if (new.CRC, new.file_size) != (item.CRC, item.file_size):
            changed.append(item.filename)
    assert sorted(changed) == ['classes8.dex', 'lib/armeabi/libSrc.so']
    parts = [n for n in z.namelist() if n.startswith('assets/pvz2data.zip.')]
    assert len(parts) == 3
    for tag in [b'PvPResourceDiag', b'PvPDialogDiag', b'PvPTitleDiag', b'PvpStringDiag']:
        assert tag not in native
    elf = ELFFile(BytesIO(native))
    for seg in elf.iter_segments():
        if seg['p_type'] == 'PT_LOAD':
            assert seg['p_filesz'] <= seg['p_memsz']
            assert seg['p_offset'] + seg['p_filesz'] <= len(native)
            assert seg['p_flags'] & 3 != 3, 'Writable executable segment'
    old_native = original.read('lib/armeabi/libSrc.so')
    for site in [0x11c76fc, 0x4045fc, 0x7f1290, 0x11e8528]:
        assert native[site:site+4] == old_native[site:site+4]

# Use the actual original native lookup loop rather than the writer's decoder.
# Only its libc uppercase-table load is adapted for this isolated emulator.
uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
uc.mem_map(0x1405000, 0x2000)
uc.mem_write(0x1405000, native[0x1405000:0x1407000])
uc.mem_map(0x20000000, 0x10000)
uc.mem_map(0x21000000, 0x100000)
uc.mem_map(0x22000000, 0x1000)
ctype = bytearray(1024)
for c in range(256):
    ctype[c*2+2] = ord(chr(c).upper()) if 97 <= c <= 122 else c
uc.mem_write(0x21002000, bytes(ctype))

def adapt(emu, address, size, _):
    if address == 0x1405f48:
        emu.reg_write(UC_ARM_REG_R0, emu.reg_read(UC_ARM_REG_R5))
        emu.reg_write(UC_ARM_REG_R4, 0x21002000)
        emu.reg_write(UC_ARM_REG_PC, 0x1405f58)
uc.hook_add(UC_HOOK_CODE, adapt)

def native_lookup(table, name):
    uc.mem_write(0x21010000, bytes(table))
    uc.mem_write(0x21000000, struct.pack('<I', 0x21010000))
    uc.mem_write(0x21001000, name.encode('ascii') + b'\0')
    uc.reg_write(UC_ARM_REG_R0, 0x21000000)
    uc.reg_write(UC_ARM_REG_R1, 0x21001000)
    uc.reg_write(UC_ARM_REG_SP, 0x20008000)
    uc.reg_write(UC_ARM_REG_LR, 0x22000000)
    uc.emu_start(0x1405f34, 0x22000000, count=20000)
    value = uc.reg_read(UC_ARM_REG_R0)
    return None if not value else u32(uc.mem_read(value, 4), 0)

checked = 0
for length_key, offset_key in [('fileList_Length', 'fileList_BeginOffset'),
                               ('rsgpList_Length', 'rsgpList_BeginOffset'),
                               ('compositeList_Length', 'compositeList_BeginOffset')]:
    off, length = bundle.h[offset_key], bundle.h[length_key]
    table = bundle.data[off:off+length]
    for name, value in trie_read(table, 0, len(table)):
        assert native_lookup(table, name.lower()) == value, name
        checked += 1
    assert native_lookup(table, 'MISSING_RESOURCE_V32') is None

for i, data in enumerate(bundle.payloads):
    data_pool, texture_pool = struct.unpack_from('<II', bundle.pools[i], 128)
    assert data_pool >= u32(data, 0x18) + u32(data, 0x20)
    assert texture_pool >= u32(data, 0x30)
    for _, info in bundle.files(i):
        assert info[1]+info[2] <= u32(data, 0x20 if info[0] == 0 else 0x30)
_, _, manifest = bundle.manifest()
assert manifest['slot_count'] == 7904
assert len(bundle.groups) == 148
assert len(bundle.composites) == 92
subprocess.run(['java', '-jar', 'K:/pvz2-tools/android-build-tools/android-14/lib/apksigner.jar',
                'verify', '--verbose', str(apk)], check=True)
subprocess.run(['K:/pvz2-tools/android-build-tools/android-14/zipalign.exe',
                '-c', '4', str(apk)], check=True)
result = dict(passed=True, native_trie_lookups=checked, resource_groups=len(bundle.groups),
              all_resource_pools_sufficient=True, full_resource_parts=len(parts),
              diagnostics_removed=True, apk_sha256=record['apk_sha256'])
(P / 'validation.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf8')
print(json.dumps(result))
