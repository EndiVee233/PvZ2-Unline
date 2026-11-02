"""Check actual post-level routing and state transition, beyond the map queue."""
from pathlib import Path
from io import BytesIO
import struct,json,zipfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *

ROOT=Path(__file__).resolve().parents[1]
record=json.loads((ROOT/'docs/recovery/trial-v26-build.json').read_text())
after=(ROOT/'work/trial-v26/libSrc.so').read_bytes()
with zipfile.ZipFile(record['base']) as z:before=z.read('lib/armeabi/libSrc.so')
MEM,STOP,STACK=0x4000000,0x5000000,0x40f0000
APP,BOARD,MANAGER,GLOBAL,MODULE,STORY=[MEM+x for x in (0x10000,0x20000,0x30000,0x8000,0x9000,0xa000)]
def put(u,a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
def get(u,a):return struct.unpack('<I',u.mem_read(a,4))[0]
def raw(a):return struct.unpack_from('<I',before,a)[0]
def machine(blob,base):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);e=ELFFile(BytesIO(blob))
    segs=[s for s in e.iter_segments() if s['p_type']=='PT_LOAD']
    end=max(s['p_vaddr']+s['p_memsz'] for s in segs)
    u.mem_map(base,(end+4095)&~4095)
    for s in segs:u.mem_write(base+s['p_vaddr'],blob[s['p_offset']:s['p_offset']+s['p_filesz']])
    u.mem_map(MEM,0x100000);u.mem_map(STOP,4096);u.mem_map(0x6000000,0x10000)
    symbols=list(e.get_section_by_name('.dynsym').iter_symbols())
    for sec in e.iter_sections():
        if sec['sh_type']!='SHT_REL':continue
        for rel in sec.iter_relocations():
            address=base+rel['r_offset'];kind=rel['r_info_type']
            if kind==23:put(u,address,get(u,address)+base)
            elif kind in (2,21,22):
                sym=symbols[rel['r_info_sym']]
                v=0x6000000+rel['r_info_sym']*4 if sym['st_shndx']=='SHN_UNDEF' else base+sym['st_value']
                if kind==2:v+=get(u,address)
                put(u,address,v)
    # Real function's PIC singleton slots, not a fabricated offer decision.
    module_global=base+((0x353cf0+raw(0x353fb0))&0xffffffff)
    story_global=base+((0x355264+raw(0x355930))&0xffffffff)
    put(u,module_global,MODULE);put(u,MODULE+0x18,0)
    put(u,base+0x1821674,GLOBAL);put(u,GLOBAL,APP)
    put(u,story_global,STORY);put(u,APP+0x6bc,BOARD)
    u.reg_write(UC_ARM_REG_SP,STACK);u.reg_write(UC_ARM_REG_LR,STOP)
    return u

def run(u,start,end):
    try:u.emu_start(start,end,count=3000)
    except Exception:
        print('fault',hex(u.reg_read(UC_ARM_REG_PC)),hex(u.reg_read(UC_ARM_REG_LR)))
        raise
    assert u.reg_read(UC_ARM_REG_PC)==end,hex(u.reg_read(UC_ARM_REG_PC))

cases=[]
for base in (0,0x20000000):
    for path in ('normal_return','alternate_completion'):
        for blob,flag,expected,label in ((before,1,19,'v24 offer eligible'),
                                        (before,0,7,'v24 no offer'),
                                        (after,1,7,'v26 offer eligible'),
                                        (after,0,7,'v26 no offer')):
            u=machine(blob,base);u.mem_write(BOARD+0xa61,bytes([flag]))
            u.reg_write(UC_ARM_REG_R0,MANAGER)
            def boundaries(uc,address,size,_):
                if address in (base+0x401edc,base+0x1043e00):
                    uc.reg_write(UC_ARM_REG_R0,1 if address==base+0x401edc else 0)
                    uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
            u.hook_add(UC_HOOK_CODE,boundaries)
            if path=='normal_return':start=base+0x353cd8
            else:
                start=base+0x354e98
                u.reg_write(UC_ARM_REG_R3,APP);u.reg_write(UC_ARM_REG_R4,MANAGER)
            # Stop at actual transition request, before any offer-specific
            # notification or close-listener registration can run.
            run(u,start,base+0x352498)
            assert u.reg_read(UC_ARM_REG_R1)==expected,(path,label)
            assert u.reg_read(UC_ARM_REG_R2)==5 and u.reg_read(UC_ARM_REG_R3)==5
            run(u,base+0x352498,base+0x3524c8)
            assert get(u,MANAGER+0xa24)==expected
            # Exercise native pending-scene consumption and exit/enter callbacks.
            # Scene 7 is the same destination as original no-offer/map-return.
            if expected==7:
                put(u,MANAGER+0x984,6)
                desc=MANAGER+4+7*0x4c
                put(u,desc,7);put(u,desc+8,APP);put(u,desc+0x10,1);put(u,desc+0x18,STOP+0x100)
                put(u,MANAGER+0x984+0x40,1);put(u,MANAGER+0x984+0x48,STOP+0x104)
                events=[]
                for a in (STOP+0x100,STOP+0x104):u.mem_write(a,bytes.fromhex('1eff2fe1'))
                def lifecycle(uc,address,size,_):
                    if address in (STOP+0x100,STOP+0x104):
                        events.append('map_enter' if address==STOP+0x100 else 'old_exit')
                        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
                u.hook_add(UC_HOOK_CODE,lifecycle)
                u.reg_write(UC_ARM_REG_R0,MANAGER);u.reg_write(UC_ARM_REG_SP,STACK);u.reg_write(UC_ARM_REG_LR,STOP)
                run(u,base+0x351eb8,STOP)
                assert events==['old_exit','map_enter'],events
                assert get(u,MANAGER+0x984)==7 and get(u,MANAGER+0xa24)==0xffffffff
                assert u.reg_read(UC_ARM_REG_SP)==STACK
            cases.append(dict(base=hex(base),path=path,variant=label,target=expected))

# Preserve actual map-action queue progression without opening a scene.
for base in (0,0x20000000):
    u=machine(after,base);action=MEM+0x1000;vt=MEM+0x2000;queue=MEM+0x3000;destroyed=[]
    put(u,action,vt);put(u,MEM+0x27c,queue);put(u,MEM+0x280,queue+4);put(u,queue,action)
    for off,target in [(4,STOP+0x100),(8,base+0xa13804),(12,base+0x9dc888),(16,base+0x9dc89c)]:put(u,vt+off,target)
    u.mem_write(STOP+0x100,bytes.fromhex('1eff2fe1'))
    def scheduler_boundary(uc,address,size,_):
        if address in (STOP+0x100,base+0x1135464):
            if address==STOP+0x100:destroyed.append(uc.reg_read(UC_ARM_REG_R0))
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,scheduler_boundary)
    for reg,value in [(UC_ARM_REG_R4,MEM),(UC_ARM_REG_R3,queue),(UC_ARM_REG_R6,1),
                      (UC_ARM_REG_R5,0),(UC_ARM_REG_R7,0)]:u.reg_write(reg,value)
    run(u,base+0x9e9e50,base+0x9e9e4c)
    assert get(u,MEM+0x280)==queue and destroyed==[action]
    assert u.mem_read(action+4,2)==b'\1\1' and u.reg_read(UC_ARM_REG_SP)==STACK
    assert u.mem_read(base+0x40c9c4,8)==bytes.fromhex('f0482de94a5da0e3')
result=dict(post_level_cases=cases,original_map_state_lifecycle_checked=True,
            map_action_scheduler_cases=2,fallback_offer_window_restored=True,
            offer_callbacks_not_registered_on_no_offer_branch=True,
            device_verified=False,limitations='Native routing and transition callbacks checked; full game UI needs acceptance.')
(ROOT/'docs/recovery/trial-v26-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
