"""Execute the real v168 research refresh hook with native-call spies."""
import argparse
from io import BytesIO
from pathlib import Path
import json
import struct

from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *


def verify(native,report):
    elf=ELFFile(BytesIO(native));passed=0
    names=['pvpskill_aid','pvpskill_invisible','pvpskill_rage','pvpskill_zombiefood']
    cases=[
        ('fog-completed',1,[1,1,1,1],[1,2,1,1],9,False,False,False),
        ('third-grade',1,[1,2,1,1],[1,3,1,1],9,False,False,False),
        ('max-grade',1,[1,3,1,1],[1,4,1,1],9,False,False,False),
        ('pending-or-cancelled',1,[1,1,1,1],[1,1,1,1],9,False,False,False),
        ('other-skill-completed',0,[1,1,1,1],[1,1,2,1],9,False,False,False),
        ('tutorial',1,[1,1,1,1],[1,2,1,1],8,False,False,False),
        ('missing-info',1,[1,1,1,1],[1,0,1,1],9,False,False,False),
        ('bad-grade',1,[1,1,1,1],[1,5,1,1],9,False,False,False),
        ('unrelated-card',1,[1,1,1,1],[1,2,1,1],9,True,False,False),
        ('invalid-vector',1,[1,1,1,1],[1,2,1,1],9,False,True,False),
        ('null-card',1,[1,1,1,1],[1,2,1,1],9,False,False,True),
    ]
    for base in (0,0x20000000):
        m=Uc(UC_ARCH_ARM,UC_MODE_ARM)
        for s in elf.iter_segments():
            if s['p_type']!='PT_LOAD':continue
            begin=(base+s['p_vaddr'])&~4095
            size=((base+s['p_vaddr']+s['p_memsz']+4095)&~4095)-begin
            m.mem_map(begin,size);m.mem_write(base+s['p_vaddr'],s.data())
        heap=0x40000000;m.mem_map(heap,0x10000)
        ui=heap+0x100;vector=heap+0x1000;player=heap+0x2000;manager=heap+0x3000
        cards=[heap+0x4000+i*0x400 for i in range(4)]
        infos=[heap+0x6000+i*0x100 for i in range(4)]
        strings=[heap+0x7000+i*0x100 for i in range(4)]
        stack=heap+0xe000;events=[]
        def put(at,value):m.mem_write(at,struct.pack('<I',value))
        def get(at):return struct.unpack('<I',m.mem_read(at,4))[0]
        def text(at):
            raw=bytes(m.mem_read(at,40));return raw.split(b'\0')[0].decode()
        def hook(machine,address,size,data):
            a=address-base;r0=machine.reg_read(UC_ARM_REG_R0);r1=machine.reg_read(UC_ARM_REG_R1)
            if a==report['research_old_tick']:
                assert r0==base and r1==ui;events.append('tick');value=0
            elif a==0x1df738:value=heap+0x3100
            elif a==0x7a98dc:value=player
            elif a==0x7fa754:value=manager
            elif a==0x1046764:
                assert r0==manager
                index=names.index(text(get(r1)));value=infos[index] if get(infos[index]+4) else 0
            elif a==0x1084a38:
                assert r0==ui and r1==get(ui+0xc0)
                events.append(('select',r1,get(cards[r1]+0x1f8)));value=0
            else:return
            machine.reg_write(UC_ARM_REG_R0,value)
            machine.reg_write(UC_ARM_REG_PC,machine.reg_read(UC_ARM_REG_LR))
        m.hook_add(UC_HOOK_CODE,hook)
        for name,selected,initial,grades,phase,unknown,bad_vector,null_card in cases:
            m.mem_write(heap,bytes(0xc000))
            put(ui+0xb4,vector);put(ui+0xb8,vector+(20 if bad_vector else 16));put(ui+0xc0,selected)
            put(player+0x75c,phase)
            for i in range(4):
                put(vector+4*i,0 if null_card and i==selected else cards[i])
                put(cards[i]+0x1f8,initial[i]);put(cards[i]+0x1fc,strings[i])
                m.mem_write(strings[i],('unrelated' if unknown and i==selected else names[i]).encode()+b'\0')
                put(infos[i]+4,grades[i])
            before=bytes(m.mem_read(heap,0xc000))
            expected=list(initial)
            if phase>=9 and not bad_vector:
                for i in range(4):
                    if not ((unknown or null_card) and i==selected) and 1<=grades[i]<=4:expected[i]=grades[i]
            for iteration in range(2):
                events.clear()
                registers=[0x9000+i for i in range(8)]
                for r,v in zip(range(UC_ARM_REG_R4,UC_ARM_REG_R11+1),registers):m.reg_write(r,v)
                m.reg_write(UC_ARM_REG_R0,ui);m.reg_write(UC_ARM_REG_R1,0x1234)
                m.reg_write(UC_ARM_REG_R2,0x5678);m.reg_write(UC_ARM_REG_R3,0x9abc)
                m.reg_write(UC_ARM_REG_SP,stack);m.reg_write(UC_ARM_REG_LR,heap+0xf000)
                m.emu_start(base+report['research_hook'],base+report['research_hook']+4,count=10000)
                assert m.reg_read(UC_ARM_REG_PC)==base+report['research_hook']+4
                assert m.reg_read(UC_ARM_REG_SP)==stack-36
                assert m.reg_read(UC_ARM_REG_R0)==ui and m.reg_read(UC_ARM_REG_R1)==0x1234
                assert [m.reg_read(r) for r in range(UC_ARM_REG_R4,UC_ARM_REG_R11+1)]==registers
                assert [get(card+0x1f8) for card in cards]==expected,(name,events)
                wanted=['tick']
                if iteration==0 and initial[selected]!=expected[selected]:wanted.append(('select',selected,expected[selected]))
                assert events==wanted,(name,events,wanted)
                after=bytearray(m.mem_read(heap,0xc000))
                # Apart from the four card grade copies, model/manager/save
                # state is byte-for-byte unchanged, including currency data.
                for i in range(4):struct.pack_into('<I',after,cards[i]+0x1f8-heap,initial[i])
                assert bytes(after)==before,name
                passed+=1
    print(json.dumps(dict(research_hook_cases_passed=passed,aslr_bases=2,
                         original_tick_preserved=True,no_wallet_or_model_writes=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('native',type=Path);p.add_argument('report',type=Path);a=p.parse_args()
    verify(a.native.read_bytes(),json.loads(a.report.read_text()))
