"""Update the installed app labels and the native About page."""
import re
import struct
from io import BytesIO

from PIL import Image
from prepare_offline_pvp_seagull_hd import Bundle, replace_section, section

NAME = 'PvZ2-Unline'
CHINESE_NAME = '植物大战僵尸2-Unline'
BASE_VERSION = '1.7.5'
VERSION_NAME = f'{BASE_VERSION}-Unline'
SETTINGS_FOOTER = f'{NAME} {BASE_VERSION}'


def launcher_icons(apk, artwork):
    paths = [name for name in apk.namelist()
             if re.fullmatch(r'res/(?:drawable|mipmap)(?:-[^/]+)?/ic_launcher\.png', name)]
    assert paths, 'No launcher icons found'
    replacements = {}
    with Image.open(artwork) as source:
        assert source.width == source.height
        source = source.convert('RGBA')
        for path in paths:
            with Image.open(BytesIO(apk.read(path))) as previous:
                icon = source.resize(previous.size, Image.Resampling.LANCZOS)
            output = BytesIO()
            icon.save(output, format='PNG', optimize=True)
            replacements[path] = output.getvalue()
    return replacements


def patch_manifest(binary):
    # This manifest uses an unstyled UTF-16 AXML string pool. Preserve the
    # indices (including the resource map) and rewrite only the target labels.
    pool = 8
    kind, header, size, count, styles, flags, start, style_start = struct.unpack_from('<HH6I', binary, pool)
    assert (kind, header, styles, flags, style_start) == (1, 28, 0, 0, 0)
    strings = []
    for index in range(count):
        offset = pool + start + struct.unpack_from('<I', binary, pool + header + index * 4)[0]
        length = struct.unpack_from('<H', binary, offset)[0]
        strings.append(binary[offset + 2:offset + 2 + length * 2].decode('utf-16le'))
    name_index = strings.index('PvZ2 源码恢复验证')
    strings[name_index] = CHINESE_NAME
    strings[strings.index('1.7.5-offline-reconstruction')] = VERSION_NAME

    offsets = bytearray()
    encoded = bytearray()
    for value in strings:
        raw = value.encode('utf-16le')
        offsets += struct.pack('<I', len(encoded))
        encoded += struct.pack('<H', len(raw) // 2) + raw + b'\0\0'
    encoded += bytes((-len(encoded)) % 4)
    assert header + len(offsets) == start
    new_pool = struct.pack('<HH6I', kind, header, start + len(encoded), count, 0, 0, start, 0)
    tail = bytearray(binary[pool + size:])

    activities = {
        'com.popcap.pvz2cthd.BootActivity',
        'com.popcap.pvz2cmhd.SexyAppActivity',
    }
    changed = set()
    pos = 0
    while pos < len(tail):
        chunk, node_header, length = struct.unpack_from('<HHI', tail, pos)
        assert node_header <= length <= len(tail) - pos
        if chunk == 0x0102:  # start element
            ext = pos + node_header
            tag, first, stride, attributes = struct.unpack_from('<IHHH', tail, ext + 4)
            if strings[tag] == 'activity':
                attrs = {}
                for index in range(attributes):
                    at = ext + first + stride * index
                    namespace, key = struct.unpack_from('<II', tail, at)
                    if namespace != 0xffffffff and strings[namespace] == 'http://schemas.android.com/apk/res/android':
                        attrs[strings[key]] = at
                activity_name = attrs.get('name')
                if activity_name is not None:
                    name = strings[struct.unpack_from('<I', tail, activity_name + 16)[0]]
                    if name in activities:
                        label = attrs['label']
                        assert struct.unpack_from('<I', tail, label + 16)[0] == 0x7f060002
                        struct.pack_into('<IHBBI', tail, label + 8, name_index, 8, 0, 3, name_index)
                        changed.add(name)
        pos += length
    assert changed == activities
    result = bytearray(binary[:pool]) + new_pool + offsets + encoded + tail
    struct.pack_into('<I', result, 4, len(result))
    return bytes(result)


def patch_about(resource, *, credits=False):
    bundle = Bundle(resource)
    path = 'PROPERTIES\\LAWNSTRINGS.TXT'
    index, = (i for i in range(len(bundle.groups)) if path in dict(bundle.files(i)))
    files = dict(bundle.files(index))
    data = section(bundle, index)
    _, offset, length = files[path]
    raw = data[offset:offset + length]
    text = raw.decode('utf-8-sig')
    newline = '\r\n' if '\r\n' in text else '\n'
    about = newline.join((
        CHINESE_NAME,
        NAME,
        '版本号：{VersionName}',
        '',
        f'基于中文版 {BASE_VERSION} 的非官方离线改版。',
        '原作及素材版权归各自权利人所有。',
    ))
    for suffix in ('', '_HD', '_TELECOM', '_TELECOM_HD', '_QQ'):
        pattern = rf'(?m)(^\[SETTINGS_ABOUT_PROMPT{suffix}\]\r?\n).*?(?=\r?\n\r?\n\[)'
        text, count = re.subn(pattern, lambda match: match[1] + about, text, flags=re.S)
        assert count == 1
    replacement = (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + text.encode('utf-8')
    files[path] = (0, len(data), len(replacement))
    data += replacement
    if credits:
        path = 'PROPERTIES\\CREDITS.TXT'
        _, offset, length = files[path]
        original = data[offset:offset + length]
        credit_newline = b'\r\n' if b'\r\n' in original else b'\n'
        additions = ('', '', '{TITLE_CH}Unline制作人', 'Codex', 'GPT6-Sol', 'GPT6-Astra', 'EndiVee233', '', '')
        replacement = original + credit_newline.join(line.encode('utf-8') for line in additions)
        files[path] = (0, len(data), len(replacement))
        data += replacement
    replace_section(bundle, index, sorted(files.items()), data)
    return bundle.build()
