"""Add a checksum-verified, atomic PvP resource overlay to the existing launcher."""
from pathlib import Path
import hashlib, os, re, subprocess


def rebuild_pvp_bootstrap(original, out, source_sha, target_sha, target_size, root):
    out, root = Path(out), Path(root)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'original.dex').write_bytes(original)
    apktool = root / 'tools/apktool.jar'
    subprocess.run(['javac', '-cp', str(apktool), '-d', str(out),
                    str(root / 'scripts/RepairDex.java')], check=True)
    cp = str(apktool) + os.pathsep + str(out)
    subprocess.run(['java', '-Xmx256m', '-cp', cp, 'RepairDex', 'decode',
                    str(out / 'original.dex'), str(out / 'smali')], check=True)
    path = out / 'smali/com/popcap/pvz2cthd/BootActivity.smali'
    text = path.read_text(encoding='utf8')
    match = re.search(r'\.method private applyOriginalSpeedResource\(\)V.*?\.end method',
                      text, re.S)
    assert match
    method = match[0].replace('applyOriginalSpeedResource', 'applyPvpSkillResource')
    replacements = {
        'cd4626cfc3afe0148962b14564c4bd27f185063c4d1bf9dd4a8c7d705d303bf5': target_sha,
        '0aae11cf23e05377026323816f6e458264bdc193b312177bca6824589fa1d29f': source_sha,
        'reconstruction/dynamic-original-speed.rsb.smf': 'reconstruction/zombie2-pvp.rsb.smf',
        'dynamic.rsb.smf': 'zombie2.rsb.smf',
        '.offline-npc-v29': '.pvp-skills-v32-' + target_sha[:12],
        '0x165e000': hex(target_size),
        'dynamic-original-speed.tmp': 'zombie2-pvp.tmp',
        'original speed resource': 'PvP skill resource',
        '57d9c44': 'v32',
        'isSupportedResourcePredecessor': 'isPvpResourcePredecessor',
    }
    for old, new in replacements.items():
        assert old in method, old
        method = method.replace(old, new)
    call = 'invoke-direct {p0}, Lcom/popcap/pvz2cthd/BootActivity;->applyOriginalSpeedResource()V'
    assert text.count(call) == 1
    text = text.replace(call, call + '\n\n    invoke-direct {p0}, '
                        'Lcom/popcap/pvz2cthd/BootActivity;->applyPvpSkillResource()V')
    # Include the two local test predecessors so interrupted upgrades repair
    # their own resource candidate instead of reporting an extraction failure.
    accepted = [source_sha,
                'b213ae0db80c1cce5195f47fed0cfd80908b71df47906d80a8e1fb9bbf9d643b',
                '3119408dc19713cbb4076a4c4b5a19089d9252358725a2e5e642a51a92234767']
    helper = '\n.method private static isPvpResourcePredecessor(Ljava/lang/String;)Z\n    .locals 1\n'
    for sha in accepted:
        helper += f'''    const-string v0, "{sha}"
    invoke-virtual {{v0, p0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :accepted
'''
    helper += '''    const/4 v0, 0x0
    return v0
    :accepted
    const/4 v0, 0x1
    return v0
.end method
'''
    path.write_text(text + '\n' + method + '\n' + helper, encoding='utf8')
    result = out / 'classes8.dex'
    subprocess.run(['java', '-Xmx256m', '-cp', cp, 'RepairDex', 'encode',
                    str(out / 'smali'), str(result)], check=True)
    data = result.read_bytes()
    import struct, zlib
    assert hashlib.sha1(data[32:]).digest() == data[12:32]
    assert zlib.adler32(data[12:]) & 0xffffffff == struct.unpack_from('<I', data, 8)[0]
    count, off = struct.unpack_from('<II', data, 56)
    strings = []
    for i in range(count):
        p = struct.unpack_from('<I', data, off + 4*i)[0]
        while data[p] & 128:
            p += 1
        p += 1
        strings.append(data[p:data.index(0, p)])
    assert all(a < b for a, b in zip(strings, strings[1:]))
    return data
