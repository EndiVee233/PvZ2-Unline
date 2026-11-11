"""Add the adventure coin balance to Aster's PvP entrance HUD."""
from copy import deepcopy
from io import BytesIO
import struct

from elftools.elf.elffile import ELFFile
from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM

from prepare_offline_neighbor_catalog import Bundle, decode, extract
from prepare_opening_tutorial_resources import update_level


LAYOUT = 'PACKAGES\\LAYOUT\\PVPENTRY.RTON'


def nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


def add_slot(layout):
    top, = (node for node in nodes(layout) if node.get('Name') == 'TopBar')
    cup, rank = top['Childs']
    assert cup['Name'] == 'Cup_Back'
    assert rank['Name'] == 'RankBtn' and rank['Width'] == 0
    gold = deepcopy(cup)
    gold.update(Name='Gold_Back', X=634.0, Width=118.0)
    icon, label = gold['Childs']
    # The PvP entry already loads this atlas for the neighboring trophy icon.
    icon.update(Name='Gold_Image', X=-15.0, Y=-3.0, Width=38.0, Height=38.0,
                ImageNormal='IMAGE_UI_PVP_UI_DIALOG_COIN')
    label.update(Name='Gold_Text', X=24.0, Width=93.0, Text='')
    top['Childs'].append(gold)


def prepare_layout(original):
    bundle = Bundle(original)
    layout = update_level(bundle, LAYOUT, add_slot)
    output = bundle.build()
    assert decode(extract(Bundle(output), LAYOUT)) == layout
    return output


def branch_link(site, target):
    offset = target - site - 8
    assert offset % 4 == 0 and -0x2000000 <= offset < 0x2000000
    return struct.pack('<I', 0xeb000000 | ((offset // 4) & 0xffffff))


def patch_native(native):
    data = bytearray(native)
    elf = ELFFile(BytesIO(native))
    loads = [(i, s) for i, s in enumerate(elf.iter_segments()) if s['p_type'] == 'PT_LOAD']
    (index, code), (_, following) = loads[-2:]
    assert code['p_flags'] == 5 and code['p_filesz'] == code['p_memsz']
    end = code['p_filesz']
    address = code['p_vaddr'] + end
    offset = code['p_offset'] + end
    refresh_site = 0x107a148
    layout_site = 0x107a874
    assert native[refresh_site:refresh_site + 4] == branch_link(refresh_site, 0x10c2548)
    assert struct.unpack_from('<I', native, layout_site)[0] == 0xe58a0028

    # The surrounding entry refresh keeps its widget root in r6. Use the
    # engine's native string constructors, label setter and wide formatter.
    # The profile's ordinary coin fields use the same rotate/XOR as redeem.h.
    asm = """
        push {r4, r5, lr}
        sub sp, sp, #12
        bl #0x10c2548
        mov r0, sp
        adr r1, name
        add r2, sp, #8
        blx #0x14ed0e0
        mov r0, r6
        mov r1, sp
        bl #0x10b80f0
        mov r4, r0
        ldr r0, [sp]
        sub r0, r0, #12
        add r1, sp, #8
        blx #0x14ebf58
        cmp r4, #0
        beq finish
        mov r0, r4
        bl #0x10c3024
        movs r4, r0
        beq finish
        bl #0x1df738
        bl #0x7a98dc
        cmp r0, #0
        beq finish
        ldr r3, [r0, #0x9c]
        ldr r2, [r0, #0x98]
        and r1, r3, #31
        ror r2, r2, r1
        eor r2, r2, r3
        adr r1, format
        add r0, sp, #4
        bl #0x1136fdc
        mov r0, r4
        add r1, sp, #4
        bl #0x10c2548
        ldr r0, [sp, #4]
        sub r0, r0, #12
        add r1, sp, #8
        blx #0x14ea238
    finish:
        add sp, sp, #12
        pop {r4, r5, pc}
    format:
        .word 37, 100, 0
    name:
        .asciz "Gold_Text"
    """
    assembler = Ks(KS_ARCH_ARM, KS_MODE_ARM)
    refresh = bytes(assembler.asm(asm, address)[0])
    refresh += bytes(-len(refresh) % 4)
    layout_address = address + len(refresh)
    layout = """
        str r0, [sl, #0x28]
        push {r0-r8, lr}
        sub sp, sp, #8
        mov r0, r5
        adr r1, gold_name
        bl lookup
        movs r4, r0
        beq layout_done
        mov r0, sl
        adr r1, gem_name
        bl lookup
        movs r6, r0
        beq layout_done
        mov r0, sl
        adr r1, medal_name
        bl lookup
        movs r7, r0
        beq layout_done
        mov r0, sl
        adr r1, starcoin_name
        bl lookup
        movs r8, r0
        beq layout_done
        mov r0, r6
        adr r1, button_name
        bl lookup
        cmp r0, #0
        beq layout_done

        @ The diamond background is 32 units high in CurrencyBar.rton.
        @ Its native height carries the same layout scale as its children.
        ldr r3, [r6, #0x34]
        mov r1, #73
        bl scaled
        str r1, [r0, #0x28]

        @ Make room for the full-size button, preserving the HUD's right edge.
        mov r1, #25
        bl scaled
        mov ip, r1

        @ Anchor gold to the original diamond position plus the extra space.
        ldr r0, [sl, #0x28]
        ldr r1, [r5, #0x28]
        sub r0, r0, r1
        ldr r2, [r6, #0x28]
        add r2, r0, r2
        add r2, r2, ip
        str r2, [r4, #0x28]

        @ Move the bar origin left and shift medals and starcoins together.
        mov r1, #94
        bl scaled
        sub r0, r0, r1
        ldr r2, [r5, #0x28]
        add r1, r2, r1
        str r1, [sl, #0x28]
        add r0, r0, ip
        ldr r1, [r7, #0x28]
        add r1, r1, r0
        str r1, [r7, #0x28]
        ldr r1, [r8, #0x28]
        add r1, r1, r0
        str r1, [r8, #0x28]
        mov r1, #14
        bl scaled
        str r1, [r6, #0x28]
        @ End the background beneath the button, like the original bar.
        mov r1, #98
        bl scaled
        str r1, [r6, #0x30]
    layout_done:
        add sp, sp, #8
        pop {r0-r8, pc}
    scaled:
        mul r1, r1, r3
        add r1, r1, #16
        lsr r1, r1, #5
        bx lr
    lookup:
        push {r4, lr}
        sub sp, sp, #8
        mov r4, r0
        mov r0, sp
        add r2, sp, #4
        blx #0x14ed0e0
        mov r0, r4
        mov r1, sp
        bl #0x10b80f0
        mov r4, r0
        ldr r0, [sp]
        sub r0, r0, #12
        add r1, sp, #4
        blx #0x14ebf58
        mov r0, r4
        add sp, sp, #8
        pop {r4, pc}
    gold_name: .asciz "Gold_Back"
    .balign 4
    gem_name: .asciz "CBar_Gem_Back"
    .balign 4
    medal_name: .asciz "CBar_Metal_Back"
    .balign 4
    starcoin_name: .asciz "CBar_Coin_Back"
    .balign 4
    button_name: .asciz "CBar_Coin_Btn"
    """
    geometry = bytes(assembler.asm(layout, layout_address)[0])
    assert geometry.startswith(native[layout_site:layout_site + 4])
    stub = refresh + geometry
    assert offset + len(stub) <= following['p_offset']
    assert address + len(stub) <= following['p_vaddr']
    assert not any(native[offset:offset + len(stub)])
    data[offset:offset + len(stub)] = stub
    data[refresh_site:refresh_site + 4] = branch_link(refresh_site, address)
    data[layout_site:layout_site + 4] = branch_link(layout_site, layout_address)
    phdr = elf['e_phoff'] + index * elf['e_phentsize']
    struct.pack_into('<II', data, phdr + 16, end + len(stub), end + len(stub))
    return bytes(data)
