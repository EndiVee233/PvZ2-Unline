"""Execute the maintenance ARM code with null/valid art and scene transitions."""
import argparse
from io import BytesIO
from pathlib import Path
import json
import struct

from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *


def verify(native,music_entry=0x1a120c0):
    elf=ELFFile(BytesIO(native));total=0
    for base in (0,0x20000000):
        m=Uc(UC_ARCH_ARM,UC_MODE_ARM)
        for s in elf.iter_segments():
            if s['p_type']!='PT_LOAD':continue
            begin=(base+s['p_vaddr'])&~4095
            length=((base+s['p_vaddr']+s['p_memsz']+4095)&~4095)-begin
            m.mem_map(begin,length)
            m.mem_write(base+s['p_vaddr'],s.data())
        heap=0x40000000;stop=heap+0xf000
        m.mem_map(heap,0x10000)
        stack=heap+0xe000
        def put(at,value):m.mem_write(at,struct.pack('<I',value))
        game=heap+0x100;holder=heap+0x1100;app=heap+0x1200;board=heap+0x2100
        put(base+0x1835eec,game);put(base+0x1821674,holder)
        put(holder,app);put(app+0x6bc,board)
        def music(scene,level,pending_scene=0,pending=None,game_exists=True):
            put(base+0x1835eec,game if game_exists else 0)
            put(game+0x984,scene);put(game+0xa24,pending_scene)
            for off,text,storage in [(board+0xc4,level,heap+0x3100),(game+0xa40,pending,heap+0x3200)]:
                put(off,storage if text else 0)
                if text:m.mem_write(storage,text.encode()+b'\0')
            m.reg_write(UC_ARM_REG_R0,base);m.reg_write(UC_ARM_REG_SP,stack);m.reg_write(UC_ARM_REG_LR,stop)
            m.emu_start(base+music_entry,stop,count=3000)
            assert m.reg_read(UC_ARM_REG_SP)==stack
            return m.reg_read(UC_ARM_REG_R0)
        cases=[
            (25,None,0,None,True,1),(28,None,0,None,True,1),(29,None,0,None,True,1),
            (6,'arena_plant_test',0,None,True,2),(6,'arena_battle_test',0,None,True,2),
            (6,None,6,'arena_plant_test',True,2),(6,None,6,'arena_battle_test',True,2),
            (6,'egypt4',0,None,True,0),(6,'arena_plant_test_extra',0,None,True,0),
            (6,None,6,'egypt4',True,0),(1,'arena_plant_test',0,None,True,0),
            (6,'arena_plant_test',0,None,False,0),(6,None,0,None,True,0),
        ]
        for *args,expected in cases:
            assert music(*args)==expected,(base,args,expected)
            total+=1
        visits=[]
        def intercept(machine,address,size,data):
            if address in (base+0x11699c4,base+0x116d764):
                visits.append((address-base,[machine.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]))
                machine.reg_write(UC_ARM_REG_PC,machine.reg_read(UC_ARM_REG_LR))
        handle=m.hook_add(UC_HOOK_CODE,intercept)
        for resource in (0,heap+0x5000):
            visits.clear()
            args=[heap+0x4000,resource,heap+0x4100,heap+0x4200]
            for r,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):m.reg_write(r,value)
            preserved=[0x9000+i for i in range(8)]
            for r,value in zip(range(UC_ARM_REG_R4,UC_ARM_REG_R11+1),preserved):m.reg_write(r,value)
            m.reg_write(UC_ARM_REG_SP,stack)
            m.emu_start(base+0x1082ae4,base+0x1082af0,count=30)
            assert [r[0] for r in visits]==([0x11699c4,0x116d764] if resource else [0x116d764])
            if resource:assert visits[0][1]==args
            assert m.reg_read(UC_ARM_REG_SP)==stack
            assert [m.reg_read(r) for r in range(UC_ARM_REG_R4,UC_ARM_REG_R11+1)]==preserved
            total+=1
        m.hook_del(handle)
    print(json.dumps(dict(arm_cases_passed=total,aslr_bases=2,null_preview_skipped=True,
                         graphics_pop_state_preserved=True,valid_preview_unchanged=True)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('native',type=Path)
    verify(parser.parse_args().native.read_bytes())
