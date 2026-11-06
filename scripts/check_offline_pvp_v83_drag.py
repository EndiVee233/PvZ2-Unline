"""Check the real Board touch-down gate, not just edited position vectors.

Runs the original native 22a2c8 instructions. UI, reflection, grid lookup and
cursor construction are engine boundaries; no real application/save is used.
The resource check ensures only the defense level gains IsArenaEdit.
"""
from pathlib import Path
from io import BytesIO
import hashlib, json, struct, sys, zlib
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import *
from prepare_offline_economy import Bundle, u32, cipher, RTONDecoder
from prepare_offline_pvp_drag import EDITOR

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'work/pvp-v83'
BASE, MEM, END = 0x10000000, 0x40000000, 0x50000000
BOARD, TOUCH, LEVEL, MANAGER, PLANT, VTABLE, CURSOR = [MEM+i*0x2000 for i in range(7)]

def resources():
    old = Bundle((OUT/'generated/dynamic-dave-dialogue.rsb.smf').read_bytes())
    new = Bundle((OUT/'generated/dynamic-drag.rsb.smf').read_bytes())
    changed=[]
    for i in range(len(old.groups)):
        before=dict(old.files(i)); after=dict(new.files(i))
        assert before.keys()==after.keys()
        def content(bundle,name,info):
            p=bundle.payloads[i]; section=p[u32(p,24):u32(p,24)+u32(p,28)]
            if u32(p,16)&2: section=zlib.decompress(section)
            return section[info[1]:info[1]+info[2]]
        for name, info in before.items():
            a=content(old,name,info); b=content(new,name,after[name])
            if a==b: continue
            assert name==EDITOR
            def decode(raw):
                if raw[:2]==b'\x10\0': raw=cipher.decrypt(raw[2:])
                fp=BytesIO(raw[4:]); fp.name=name
                return json.loads(RTONDecoder(repairFiles=False).parse_root_object(fp))
            a,b=decode(a),decode(b)
            level=next(o['objdata'] for o in b['objects'] if o['objclass']=='LevelDefinition')
            assert level.pop('IsArenaEdit') is True and a==b
            changed.append(name)
    assert changed==[EDITOR]
    return changed

def native_case(edit, *, state=5, overlay=0, ui=0, tutorial=0, plant=True):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
    u.mem_map(BASE,0x2000000); u.mem_map(MEM,0x100000);u.mem_map(END,0x10000)
    with (OUT/'libSrc.so').open('rb') as f:
        for seg in ELFFile(f).iter_segments():
            if seg['p_type']=='PT_LOAD': u.mem_write(BASE+seg['p_vaddr'],seg.data())
    def put(p,v):u.mem_write(p,struct.pack('<I',v&0xffffffff))
    def get(p):return struct.unpack('<I',u.mem_read(p,4))[0]
    put(BOARD+0xc0,state);u.mem_write(BOARD+0x8d5,bytes([overlay]))
    u.mem_write(LEVEL+0x8c,bytes([edit]));u.mem_write(MANAGER+0x17d,bytes([tutorial]))
    put(TOUCH+8,500);put(TOUCH+12,300);put(PLANT,VTABLE);put(VTABLE+0x64,END+0x100)
    delta=struct.unpack('<i',u.mem_read(BASE+0x22a4c0,4))[0]
    put(BASE+0x22a398+delta,MANAGER)
    made=[]; added=[]; calls=[]
    def hook(em,a,size,_):
        off=a-BASE
        if 0x22a2c8<=off<0x22a4c8 or 0x1a00000<=off<0x2000000: return
        if a==END: return
        r=[em.reg_read(x) for x in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
        x,y,z,w=r; result=0; calls.append(off)
        if a==END+0x100: assert (x,y)==(PLANT,1)
        elif off==0x977738: pass
        elif off==0x9776d4: result=ui
        elif off==0x3476ac: result=overlay
        elif off==0x11d74b4: result=MEM+0xf000
        elif off==0x1da034: assert y==BOARD+0x958;result=LEVEL
        elif off==0x204930: put(x,2);put(x+4,1)
        elif off in (0x14ed0e0,0x14ebf58): pass
        elif off==0x203990: assert (x,y,z)==(BOARD,2,1);result=PLANT if plant else 0
        elif off==0x4b1994: put(x,PLANT);put(x+4,1)
        elif off==0x14c1a7c: assert x==0x48;result=CURSOR
        elif off==0x10ab71c:
            assert (x,y)==(CURSOR,TOUCH) and get(z)==PLANT
            sp=em.reg_read(UC_ARM_REG_SP);assert get(sp)==0 and get(sp+4)==PLANT
            made.append(True)
        elif off==0x229e8c: assert (x,y)==(BOARD,CURSOR);added.append(True)
        elif off==0x1d9bb4: pass
        else: raise AssertionError((hex(off),[hex(v) for v in r]))
        em.reg_write(UC_ARM_REG_R0,result);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    stack=MEM+0xff000
    u.reg_write(UC_ARM_REG_CPSR,0x10);u.reg_write(UC_ARM_REG_SP,stack)
    u.reg_write(UC_ARM_REG_LR,END);u.reg_write(UC_ARM_REG_R0,BOARD);u.reg_write(UC_ARM_REG_R1,TOUCH)
    u.emu_start(BASE+0x22a2c8,END,count=10000)
    assert u.reg_read(UC_ARM_REG_PC)==END and u.reg_read(UC_ARM_REG_SP)==stack
    expected=bool(edit and state in (3,4,5,6,7) and not overlay and not ui and not tutorial and plant)
    assert bool(made)==bool(added)==expected
    return dict(edit=edit,state=state,overlay=overlay,ui=ui,tutorial=tutorial,plant=plant,cursor_created=expected)

if __name__=='__main__':
    changed=resources()
    cases=[native_case(0),native_case(1),native_case(1,ui=1),native_case(1,overlay=1),
           native_case(1,tutorial=1),native_case(1,plant=False)]
    cases += [native_case(1,state=s) for s in (1,2,3,4,5,6,7,8,9)]
    result=dict(resource_changes=changed,original_native_touch_gate=True,cases=cases,
                runtime_verified=False,scope='cursor creation boundary; real drag/drop still requires user test')
    (OUT/'drag-check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print('v83 resource scope and original native drag-selection gate passed')
