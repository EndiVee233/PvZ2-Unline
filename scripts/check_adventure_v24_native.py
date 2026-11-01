"""Bounded ARM execution checks; not a substitute for in-game acceptance."""
from pathlib import Path
from io import BytesIO
import json, struct, zipfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import *

ROOT = Path(__file__).resolve().parents[1]
record = json.loads((ROOT/'docs/recovery/adventure-v24-build.json').read_text())
blob = (ROOT/'work/adventure-v24/libSrc.so').read_bytes()
with zipfile.ZipFile(record['base']) as z:
    before = z.read('lib/armeabi/libSrc.so')
STOP, MEM, STACK = 0x5000000, 0x4000000, 0x40f0000
R = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3]

def put(u, a, v): u.mem_write(a, struct.pack('<I', v & 0xffffffff))
def get(u, a): return struct.unpack('<I', u.mem_read(a, 4))[0]
def machine(data=blob):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    e = ELFFile(BytesIO(data))
    segs = [s for s in e.iter_segments() if s['p_type']=='PT_LOAD']
    end = max(s['p_vaddr']+s['p_memsz'] for s in segs)
    u.mem_map(0, (end+4095)&~4095)
    for s in segs:
        u.mem_write(s['p_vaddr'], data[s['p_offset']:s['p_offset']+s['p_filesz']])
    # Resolve native data addresses, including singleton pointers, at load base 0.
    symbols = list(e.get_section_by_name('.dynsym').iter_symbols())
    for sec in e.iter_sections():
        if sec['sh_type']!='SHT_REL': continue
        for rel in sec.iter_relocations():
            if rel['r_info_type'] in (2,21,22):
                sym = symbols[rel['r_info_sym']]
                if sym['st_shndx']=='SHN_UNDEF': continue
                value = sym['st_value']
                if rel['r_info_type']==2: value += get(u, rel['r_offset'])
                put(u, rel['r_offset'], value)
    u.mem_map(MEM, 0x100000); u.mem_map(STOP, 4096)
    u.reg_write(UC_ARM_REG_SP, STACK); u.reg_write(UC_ARM_REG_LR, STOP)
    return u

def run(u, address, limit=2000, end=STOP):
    u.emu_start(address, end, count=limit)
    assert u.reg_read(UC_ARM_REG_PC)==end, hex(u.reg_read(UC_ARM_REG_PC))

def callback(u, callbacks):
    def hook(uc, address, size, _):
        if address in callbacks:
            callbacks[address](uc)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)

def clock(u, epoch, error=False):
    def read(uc):
        put(uc, uc.reg_read(R[0]), epoch)
        put(uc, uc.reg_read(R[0])+4, 0)
        uc.reg_write(R[0], -1 if error else 0)
    return read

# Compare actual tutorial query execution with the last released APK.
queries = 0
query_machines = [machine(before), machine(blob)]
for progress in (0,2,18,30):
    for completed in ([],[15,17,19,25],[18],list(range(15,26))):
        for ident in range(-1,31):
            values=[]
            for u in query_machines:
                u.reg_write(UC_ARM_REG_SP,STACK);u.reg_write(UC_ARM_REG_LR,STOP)
                vec=MEM+0x1000
                put(u,MEM+0x120,progress);put(u,MEM+0x124,vec);put(u,MEM+0x128,vec+4*len(completed))
                for j,v in enumerate(completed):put(u,vec+4*j,v)
                u.reg_write(R[0],MEM);u.reg_write(R[1],ident&0xffffffff)
                run(u,0x709808);values.append(u.reg_read(R[0]))
                assert u.reg_read(UC_ARM_REG_SP)==STACK
            assert values[1]==(1 if ident==15 else values[0]),(ident,values)
            queries+=1
for ident in (15,18):
    u=machine();put(u,MEM+0x124,MEM+0x2000);put(u,MEM+0x128,MEM+0x2000)
    u.reg_write(R[0],MEM);u.reg_write(UC_ARM_REG_R7,MEM)
    u.reg_write(UC_ARM_REG_R5,ident);u.reg_write(UC_ARM_REG_R6,MEM+0x1000)
    run(u,0x9fce24,end=0x9fce38)
    assert get(u,MEM+0x129c)==0

# Exercise the actual drawer splice, original add callback, and both virtual calls.
for mode in (0,4,5):
    for child_present in (False,True):
        u=machine();child=MEM+0x1000;vt=MEM+0x2000;calls=[]
        put(u,MEM+0xa8,child if child_present else 0);put(u,MEM+0xbc,mode)
        put(u,child,vt);put(u,vt+0x8c,STOP+0x104);put(u,vt+0xa4,STOP+0x108)
        u.reg_write(UC_ARM_REG_R4,MEM);u.reg_write(R[3],STOP+0x100)
        def capture(label):
            return lambda uc: calls.append((label,uc.reg_read(R[0]),uc.reg_read(R[1])))
        callback(u,{STOP+0x100:capture('add'),STOP+0x104:capture('visible'),STOP+0x108:capture('disabled')})
        run(u,0xa36000,end=0xa36004)
        assert [c[0] for c in calls]==(['add','visible','disabled'] if child_present else ['add'])
        if child_present: assert calls[1:]==[('visible',child,0),('disabled',child,1)]
        assert get(u,MEM+0xa8)==(child if child_present else 0)
        assert get(u,MEM+0xbc)==(0 if mode==4 else mode)

for epoch,error in ((1793548800,False),(1793549000,False),(0,True)):
    u=machine();callback(u,{0x147974:clock(u,epoch,error)})
    u.reg_write(UC_ARM_REG_R4,0x12345678)
    run(u,int(record['clock_stub'],16))
    assert u.reg_read(R[0])==(0 if error else epoch)
    assert u.reg_read(UC_ARM_REG_R4)==0x12345678 and u.reg_read(UC_ARM_REG_SP)==STACK

# Run the original profile maturation loop with fixture records and intercepted
# state/save boundaries, on both sides of the expiry and after process restart.
maturation=[]
for now in (1793548800,1793548920,1793549000):
    u=machine();vec=MEM+0x1000;changes=[];saves=[]
    put(u,MEM+0x220,vec);put(u,MEM+0x224,vec+2*0x34)
    for j,end in enumerate((1793548920,1793549100)):
        put(u,vec+j*0x34+4,10401+j);put(u,vec+j*0x34+0x24,end)
    def update(uc): changes.append((uc.reg_read(R[1]),uc.reg_read(R[2]),uc.reg_read(R[3])))
    callback(u,{0xf754ac:lambda uc:None,0x147974:clock(u,now),
                0x71ecbc:update,0x7110c4:lambda uc:saves.append(uc.reg_read(R[0]))})
    u.reg_write(R[0],MEM);run(u,0x71f3e4)
    expected=[] if now<1793548920 else [(10401,3,0xffffffff)]
    assert changes==expected and saves==([MEM] if expected else [])
    assert u.reg_read(R[0])==bool(expected)
    maturation.append(dict(now=now,changes=changes,saved=bool(saves)))

# Native list query must report success offline (the old zero server clock
# reports failure). Capture native event boundaries, not a fabricated list.
events=[];u=machine()
callback(u,{0xf754ac:lambda uc:None,0x147974:clock(u,1793548800),
            0x21e1e0:lambda uc:events.append(uc.reg_read(R[2]))})
run(u,0xf93d8c);assert events==[1,1],events

result=dict(tutorial_differential_cases=queries,overlay_bypass_ids=[15,18],
    drawer_cases=6,clock_cases=3,maturation_cases=maturation,native_list_success_events=events,
    device_verified=False,limitations='Bounded native execution only; dispatch, reward claim and full UI require in-game acceptance.')
(ROOT/'docs/recovery/adventure-v24-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
