"""Adjust two PvP render tracks without changing gameplay or animation events."""

import struct

from merge_legacy_pvp_resources import Bundle
from pam_transform_index import PamIndex
from prepare_offline_pvp_seagull_hd import replace_section, section


def shift_position(raw, move, dx, dy):
    flags = move["flags"]
    offset = move["start"] + 2
    if flags & 1023 == 1023:
        offset += 4
    if flags & 4096:
        offset += 16
    elif flags & 16384:
        offset += 2
    layout = "<ii" if flags & 2048 else "<hh"
    x, y = move["pos"]
    assert struct.unpack_from(layout, raw, offset) == (x, y)
    struct.pack_into(layout, raw, offset, x + 20 * dx, y + 20 * dy)


def cannon_tube(index):
    active = {}
    for frame in index.sprites[-1]["frames"]:
        for layer in frame["rem"]:
            active.pop(layer, None)
        for entry in frame["adds"]:
            active[entry["index"]] = entry
        for move in frame["moves"]:
            entry = active[move["index"]]
            if entry["sprite"] and index.sprites[entry["res"]]["name"] == "cannon_tube":
                yield move


def wizard_flight(index):
    label = None
    for frame in index.sprites[-1]["frames"]:
        label = frame["label"] or label
        if label == "attack":
            yield from frame["moves"]


def adjust_pam(original, select, dx, dy):
    raw = bytearray(original)
    before = PamIndex(original)
    edits = list(select(before))
    assert edits
    for move in edits:
        shift_position(raw, move, dx, dy)

    # Reparse and reverse only the selected translations to prove that all
    # frames, nested sprites, events, and other bytes are still identical.
    after = PamIndex(bytes(raw))
    adjusted = list(select(after))
    assert len(edits) == len(adjusted)
    verified = bytearray(raw)
    for old, new in zip(edits, adjusted):
        assert new["pos"] == (old["pos"][0] + dx * 20, old["pos"][1] + dy * 20)
        shift_position(verified, new, -dx, -dy)
    assert verified == original
    return raw, len(edits)


def prepare(original):
    bundle = Bundle(original)
    original_payloads = [bytes(payload) for payload in bundle.payloads]
    manifest = bundle.manifest()[2]
    changes = {}
    # Keep the recoil movement while bringing its muzzle toward the front.
    # The flight PAM is centered near y=174 with a native attachment offset
    # of -95. Remove the remaining 79 units without moving the impact PAM.
    for group, suffix, select, dx, dy in (
        ("ZombiePVPCannonGroup_Common", "ZOMBIE_PVP_CANNON.PAM", cannon_tube, -45, 0),
        ("ZombiePVPWizardGroup_Common", "ZOMBIE_PVP_WIZARD_BULLET.PAM", wizard_flight, 0, -79),
    ):
        i = next(i for i, row in enumerate(bundle.groups) if row["ID"] == group)
        files = bundle.files(i)
        [(name, (_, offset, size))] = [(name, info) for name, info in files if name.endswith(suffix)]
        data = section(bundle, i)
        adjusted, count = adjust_pam(data[offset:offset + size], select, dx, dy)
        replace_section(bundle, i, files, data[:offset] + adjusted + data[offset + size:])
        changes[i] = {"group": group, "file": name, "moves": count, "dx": dx, "dy": dy}

    result = bundle.build()
    check = Bundle(result)
    assert check.manifest()[2] == manifest
    for i, payload in enumerate(check.payloads):
        if i in changes:
            assert payload == bundle.payloads[i]
        else:
            assert payload == original_payloads[i]
    return result, list(changes.values())
