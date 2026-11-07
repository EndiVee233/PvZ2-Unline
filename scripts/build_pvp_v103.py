"""Rebind original PvP animations to correctly cropped 1536-resolution art."""

import hashlib
import struct
import subprocess
import zlib
from pathlib import Path

import texture2ddecoder
from PIL import Image

from build_pvp_v102 import ROOT, build
from merge_legacy_pvp_resources import Bundle
from pam_transform_index import PamIndex
from prepare_offline_pvp_seagull_hd import replace_section, section, texture_section

OUT = ROOT / "work/pvp-v103"
SCALE = 1536 / 640
SOURCES = (
    ("ZombiePVPCannonGroup", "zombie1",
     "01da273f274e35f31bcde4397056fa7d1df5369f68546d592ee71a7bdbc54a3c",
     "f6e947b777ad99d466f123b2ac55b9512d16153b21ce1806e9b3efd6032559fb"),
    ("ZombiePVPWizardGroup", "zombie2",
     "0c6abf1b07cf6c0f32d3cc0b1ceda30a793174dd4bfc706275aaf12af6264995",
     "92f10d7fc4adab48dc7277895a15b25f3314a65baab42c0eede723d9662d221f"),
)


def read_source(version, name, expected_hash):
    raw = (OUT / f"{version}-{name}.rsb.smf").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected_hash
    if raw.startswith(bytes.fromhex("d4feadde")):
        raw = zlib.decompress(raw[8:])
    return Bundle(raw)


def group_index(bundle, name):
    return next(i for i, row in enumerate(bundle.groups) if row["ID"] == name)


def atlas_group(manifest, prefix):
    return next(g for g in manifest["groups"] if g["id"] == prefix + "_640")


def decode_legacy_atlas(bundle, index):
    [(name, info)] = bundle.files(index)
    assert name.endswith(".PTX")
    _, offset, size, _, _, _, width, height = info
    pixels = width * height
    raw = texture_section(bundle.payloads[index])[offset:offset + size]
    rgb_size = pixels // 2
    assert raw[rgb_size] == 16 and size == pixels + 17
    palette = raw[rgb_size + 1:rgb_size + 17]
    assert set(palette) == set(range(16))
    alpha = bytes(palette[nibble] * 17 for byte in raw[rgb_size + 17:]
                  for nibble in (byte >> 4, byte & 15))
    rgba = texture2ddecoder.decode_etc1(raw[:rgb_size], width, height)
    atlas = Image.frombytes("RGBA", (width, height), rgba, "raw", "BGRA")
    atlas.putalpha(Image.frombytes("L", (width, height), alpha))
    return atlas


def cell(row):
    return tuple(row[key] for key in ("ax", "ay", "aw", "ah"))


def convert_atlas(bundle, manifest, clean, prefix):
    group = atlas_group(manifest, prefix)
    donor = atlas_group(clean.manifest()[2], prefix)
    donor_images = {row["id"]: row for row in donor["resources"] if "parent" in row}
    atlas, hd_atlas = [row for row in group["resources"] if row.get("atlas")]
    index = group_index(bundle, prefix + "_640")
    source = decode_legacy_atlas(clean, group_index(clean, prefix + "_640"))
    dimensions = tuple(1 << (round(edge * SCALE) - 1).bit_length() for edge in source.size)
    output = Image.new("RGBA", dimensions)
    changed_cells = {}
    native_cells = {}
    for row in group["resources"]:
        if row.get("parent") != atlas["id"]:
            continue
        image_id = row["id"]
        x, y, width, height = cell(donor_images[image_id])
        assert (width, height) == cell(row)[2:]
        if prefix == "ZombiePVPCannonGroup":
            # The standard cannon atlas already in the APK has true HD
            # versions of the main barrel and the charging streak.
            normal = {
                "250X107": (645, 307, 321, 139),
                "189X166": (728, 1, 244, 213),
            }.get(image_id.rsplit("_", 1)[-1])
            if normal:
                row.update(parent=hd_atlas["id"], ax=normal[0], ay=normal[1], aw=normal[2], ah=normal[3])
                native_cells[image_id] = normal
                changed_cells[image_id] = (width, height, normal[2], normal[3])
                continue
        left, top = round(x * SCALE), round(y * SCALE)
        right, bottom = round((x + width) * SCALE), round((y + height) * SCALE)
        new_width, new_height = right - left, bottom - top
        art = source.crop((x, y, x + width, y + height))
        output.paste(art.resize((new_width, new_height), Image.Resampling.LANCZOS), (left, top))
        row.update(ax=left, ay=top, aw=new_width, ah=new_height)
        changed_cells[image_id] = (width, height, new_width, new_height)

    generated = OUT / "generated"
    generated.mkdir(exist_ok=True)
    png, astc = generated / (prefix + ".png"), generated / (prefix + ".astc")
    output.save(png)
    compressor = OUT / "astcenc/bin/astcenc-sse2.exe"
    subprocess.run([str(compressor), "-cl", str(png), str(astc), "6x6", "-medium", "-silent"], check=True)
    raw = astc.read_bytes()
    width, height = dimensions
    assert raw[:7] == bytes.fromhex("13aba15c060601")
    assert int.from_bytes(raw[7:10], "little") == width
    assert int.from_bytes(raw[10:13], "little") == height
    pixels = raw[16:]
    assert len(pixels) == ((width + 5) // 6) * ((height + 5) // 6) * 16
    files = bundle.files(index)
    legacy_name, legacy_info = next((name, info) for name, info in files if info[3] == 0)
    normal_name, normal_info = next((name, info) for name, info in files if info[3] == 1)
    textures = texture_section(bundle.payloads[index])
    normal = textures[normal_info[1]:normal_info[1] + normal_info[2]]
    offset = (len(pixels) + 4095) & ~4095
    files = [
        (legacy_name, (*legacy_info[:1], 0, len(pixels), *legacy_info[3:6], width, height)),
        (normal_name, (1, offset, *normal_info[2:])),
    ]
    first = struct.unpack_from("<I", bundle.infos[index], 200)[0]
    meta = bytearray(bundle.textures[first + 1])
    struct.pack_into("<III", meta, 0, width, height, width * 16 // 36)
    bundle.textures[first] = meta
    replace_section(bundle, index, files, section(bundle, index), pixels.ljust(offset, b"\0") + normal)
    atlas.update(width=width, height=height)
    return changed_cells, native_cells


def animations(bundle, prefix):
    index = group_index(bundle, prefix + "_Common")
    data = section(bundle, index)
    return index, {name: data[info[1]:info[1] + info[2]]
                   for name, info in bundle.files(index) if name.endswith(".PAM")}


def restore_animations(bundle, original, clean, prefix, cells):
    index, existing = animations(bundle, prefix)
    _, originals = animations(original, prefix)
    _, donors = animations(clean, prefix)
    assert existing.keys() == originals.keys() == donors.keys()
    data = section(bundle, index)
    for name, raw in originals.items():
        original_pam = PamIndex(raw)
        donor_pam = PamIndex(donors[name])
        # The clean atlas comes from a newer package. Its animation tracks
        # agree byte-for-byte with the 1.7.5 choreography and callbacks.
        original_frames = raw[original_pam.sprites[0]["start"]:]
        assert original_frames == donors[name][donor_pam.sprites[0]["start"]:]
        adjusted = bytearray(raw)
        for image in original_pam.images:
            image_id = image["name"].split("|")[-1]
            if image_id not in cells:
                continue
            w, h, new_w, new_h = cells[image_id]
            a, c, b, d = image["mat"][:4]
            # Match the original 640-space quad at 1536, including rounding
            # at individual atlas boundaries. The local pivot is unchanged.
            factors = (SCALE * w / new_w, SCALE * h / new_h)
            fixed = tuple(round(value * factors[j // 2]) for j, value in enumerate((a, c, b, d)))
            struct.pack_into("<4i", adjusted, image["off"] + 4, *fixed)
        assert adjusted[original_pam.sprites[0]["start"]:] == original_frames
        parsed = PamIndex(bytes(adjusted))
        for before, after in zip(original_pam.images, parsed.images):
            assert before["mat"][4:] == after["mat"][4:]
        assert len(adjusted) == len(existing[name])
        _, offset, size = dict(bundle.files(index))[name]
        data = data[:offset] + adjusted + data[offset + size:]
    replace_section(bundle, index, bundle.files(index), data)
    return len(originals)


def prepare(raw):
    bundle = Bundle(raw)
    manifest_index, manifest_name, manifest = bundle.manifest()
    expected_changes = {manifest_index}
    changes = []
    for prefix, filename, original_hash, clean_hash in SOURCES:
        original = read_source("1.7.5", filename, original_hash)
        clean = read_source("2.0.1", filename, clean_hash)
        cells, native_cells = convert_atlas(bundle, manifest, clean, prefix)
        pams = restore_animations(bundle, original, clean, prefix, cells)
        expected_changes.update(group_index(bundle, prefix + suffix) for suffix in ("_640", "_Common"))
        changes.append({"group": prefix, "aligned_cells": len(cells), "native_hd_cells": len(native_cells),
                        "original_animation_files": pams})
    bundle.replace_manifest(manifest_index, manifest_name, manifest)
    result = bundle.build()
    before, after = Bundle(raw), Bundle(result)
    assert after.manifest()[2] == manifest
    assert {i for i, (a, b) in enumerate(zip(before.payloads, after.payloads)) if a != b} == expected_changes
    return result, changes


if __name__ == "__main__":
    build(
        ROOT / "work/pvp-v102/PvZ2-v102-pvp-art-alignment.apk", OUT,
        "7f07d73d1a0a8df158adabe151fc9606c46c73b926300648ee2f71c25a797e93",
        prepare, ".pvp-art-alignment-v102-", ".pvp-original-art-v103-", "PvZ2-v103-pvp-original-art.apk",
    )
