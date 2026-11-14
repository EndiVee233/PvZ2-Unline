"""Run the real JNI bridge into its paired ARM engine, including startup calls."""
import argparse,json,struct
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_PROT_READ,UC_PROT_WRITE
from unicorn.arm_const import *


def verify(native,bridge,targets,expect_stale=False):
    count=0
    for base,bridge_base in ((0x10000000,0x30000000),(0x20000000,0x31000000)):
        m=Uc(UC_ARCH_ARM,UC_MODE_ARM)
        def load(blob,at):
            elf=ELFFile(BytesIO(blob));segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
            lo=min(s['p_vaddr'] for s in segments)&~4095
            hi=(max(s['p_vaddr']+s['p_memsz'] for s in segments)+4095)&~4095
            m.mem_map(at+lo,hi-lo)
            for s in segments:m.mem_write(at+s['p_vaddr'],s.data())
            return elf
        engine=load(native,base);wrapper=load(bridge,bridge_base)
        symbols={s.name:s['st_value'] for s in wrapper.get_section_by_name('.symtab').iter_symbols()}
        dyn=list(wrapper.get_section_by_name('.dynsym').iter_symbols())
        # Resolve local relative/GOT relocations as Android's loader does.
        imports={}
        for section in wrapper.iter_sections():
            if section['sh_type']!='SHT_REL':continue
            for relocation in section.iter_relocations():
                at=bridge_base+relocation['r_offset'];kind=relocation['r_info_type']
                if kind==23:value=struct.unpack('<I',m.mem_read(at,4))[0]+bridge_base
                elif kind in (21,22):
                    sym=dyn[relocation['r_info_sym']]
                    value=(0x50003000+relocation['r_info_sym']*4 if sym['st_shndx']=='SHN_UNDEF' else bridge_base+sym['st_value'])
                    if sym['st_shndx']=='SHN_UNDEF':imports[value]=sym.name
                else:raise AssertionError(('unknown bridge relocation',kind))
                m.mem_write(at,struct.pack('<I',value))
        heap=0x40000000;external=0x50000000;stop=external+0x100
        m.mem_map(heap,0x20000,UC_PROT_READ|UC_PROT_WRITE);m.mem_map(external,0x10000)
        def put(at,value):m.mem_write(at,struct.pack('<I',value&0xffffffff))
        def get(at):return struct.unpack('<I',m.mem_read(at,4))[0]
        env=heap;table=heap+0x1000;input_data=heap+0x3000
        put(env,table);put(bridge_base+symbols['_ZL4base'],base)
        callbacks={171:external+0x200,187:external+0x210,195:external+0x220,179:external+0x230,211:external+0x240}
        for index,at in callbacks.items():put(table+4*index,at)
        native_targets=set(targets.values());events=[];state=dict(size=1,releases=0,output=None,in_engine=False)
        bridge_ranges=[(bridge_base+s['p_vaddr'],bridge_base+s['p_vaddr']+s['p_filesz']) for s in wrapper.iter_segments() if s['p_type']=='PT_LOAD']
        def hook(uc,address,size,data):
            lr=uc.reg_read(UC_ARM_REG_LR)
            from_bridge=state.get('previous_bridge',False)
            state['previous_bridge']=any(lo<=address<hi for lo,hi in bridge_ranges)
            if base+0x1a00000<=address<base+0x1b00000 and from_bridge:
                if address-base not in native_targets:raise AssertionError(('stale JNI target',hex(address-base)))
                if address-base not in events:events.append(address-base)
            if imports.get(address)=='memset':
                ptr=uc.reg_read(UC_ARM_REG_R0);value=uc.reg_read(UC_ARM_REG_R1);length=uc.reg_read(UC_ARM_REG_R2)
                uc.mem_write(ptr,bytes([value&255])*length);result=ptr
            elif address==base+0x147adc:result=0
            elif address==callbacks[171]:result=state['size']
            elif address==callbacks[187]:result=input_data
            elif address==callbacks[195]:state['releases']+=1;result=0
            elif address==callbacks[179]:state['new_array_size']=uc.reg_read(UC_ARM_REG_R1);result=1
            elif address==callbacks[211]:
                state['output']=bytes(uc.mem_read(get(uc.reg_read(UC_ARM_REG_SP)),4*uc.reg_read(UC_ARM_REG_R3)));result=0
            else:return
            uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,lr)
        m.hook_add(UC_HOOK_CODE,hook)
        exports={s.name:s['st_value'] for s in wrapper.get_section_by_name('.dynsym').iter_symbols()}
        def run(name,*args):
            for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),(env,0,*args)):m.reg_write(r,v)
            m.reg_write(UC_ARM_REG_SP,heap+0x1f000);m.reg_write(UC_ARM_REG_LR,stop)
            m.emu_start(bridge_base+exports['Java_com_popcap_pvz2cthd_PresetEditor_'+name],stop,count=100000)
            assert m.reg_read(UC_ARM_REG_PC)==stop and m.reg_read(UC_ARM_REG_SP)==heap+0x1f000
            return m.reg_read(UC_ARM_REG_R0)
        try:
            # PresetEditor.frame() queues network preference before first poll.
            put(input_data,0);assert run('command',5,1)==1;count+=1
        except AssertionError as exc:
            if expect_stale and exc.args and isinstance(exc.args[0],tuple) and exc.args[0][0]=='stale JNI target':return True
            raise
        if expect_stale:raise AssertionError('Old bridge unexpectedly matched this engine')
        assert run('command',8,1)==1;count+=1 # empty GitHub catalogue
        assert state['releases']==2
        state['size']=183;assert run('command',5,1)==0 and state['releases']==2;count+=1
        state['size']=224002;assert run('command',8,1)==0;count+=1
        assert run('poll')==0;count+=1
        assert run('musicSample')==0;count+=1
        assert set(events)==native_targets
    return count


def check(code,bridge,old_apk=None):
    native=(code/'libSrc.so').read_bytes();binding=json.loads((bridge.parent/'bridge-binding.json').read_text())
    count=verify(native,bridge.read_bytes(),binding['targets'])
    rejected=False
    if old_apk:
        with ZipFile(old_apk) as z:old=z.read('lib/armeabi/libPresetEditor.so')
        rejected=verify(native,old,binding['targets'],True)
    result=dict(arm_jni_cases_passed=count,old_stale_bridge_rejected=rejected,aslr_bases=2,actual_engine_calls=True,runtime_game_verified=False)
    (bridge.parent/'jni-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('code',type=Path);p.add_argument('bridge',type=Path);p.add_argument('--old-apk',type=Path)
    check(**vars(p.parse_args()))
