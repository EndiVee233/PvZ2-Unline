"""Execute the isolated editor ARM boundaries; does not start WSA or touch saves."""
from pathlib import Path
import importlib,struct,sys,json
from check_offline_pvp_v76_focused import Definitions

def main():
    sys.meta_path.insert(0,Definitions());core=importlib.import_module('check_offline_pvp_arm')
    core.OUT=Path(sys.argv[1]);from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R6,UC_ARM_REG_R9,UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_SP
    class EditorEngine(core.Engine):
        def __init__(self):
            super().__init__();self.heap=core.M+0x30000;self.app=core.M+0x6000;self.board=core.M+0x8000
            self.put(core.BASE+0x1821674,core.M+0x5800);self.put(core.M+0x5800,self.app)
            self.put(core.GM+0x984,2);self.put(self.app+0x1218,17);self.put(core.M+0xa8,2);self.put(core.M+0x9c,6)
            for i in range(7):self.put(core.M+0xf4+4*i,1000+i)
            self.put(core.M+0x17c,0x00000500);self.originals=self.state();self.cells={};self.native_calls=[]
            self.stock_board='offlinePresetLevelDefinition' in self.exports
            self.edit_tools='offlinePresetAdvanceDefensePhase' in self.exports
        def state(self):return (self.get(self.app+0x1218),self.get(core.M+0xa8),self.get(core.M+0x9c),bytes(self.u.mem_read(core.M+0xf4,28)),bytes(self.u.mem_read(core.M+0x17d,1)))
        def hook(self,em,a,size,data):
            off=a-core.BASE;r=[em.reg_read(x) for x in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];x,y,z,w=r;result=0
            if off==0x8e8884:self.native_calls.append(('close_settings',y))
            elif off==0x354360:
                assert y==core.BASE+0x184700c # same package argument as the stock launcher
                self.loaded.append(self.txt(self.get(z)));assert self.loaded[-1]=='arena_preset_editor'
            elif off==0x85e7d8:
                self.put(self.app+0x1218,0);self.loaded.append('arena_plant_test')
            elif off==0x440dc4:
                self.native_calls.append(('definition',self.txt(self.get(z))));result=x
            elif off==0x9766f4:self.native_calls.append(('stock-button-visibility',x,y))
            elif off==0x1097d00:self.native_calls.append(('defense-phase',y,self.state()[4][0]))
            elif off in (0x10989a4,0x1098e38):pass
            elif off==0x203990:result=self.cells.get((y,z),0)
            elif off==0x226770:self.put(x+0xc0,9);self.native_calls.append(('finish',))
            elif off==0x1f7380:result=core.M+0x24000
            elif off==0x11d74b4:result=core.M+0x24100
            elif off in (0x1da034,0x43af38,0x10290ac):result=0
            elif off in (0x4b6808,0x4b6ce0):self.native_calls.append(('plant-grade-path',off))
            elif off==0x15de9dc:result=struct.unpack('<I',struct.pack('<f',struct.unpack('<d',struct.pack('<II',x,y))[0]))[0]
            elif off==0x15deccc:
                left,right=struct.unpack('<ff',struct.pack('<II',x,y))
                result=struct.unpack('<I',struct.pack('<f',left*right))[0]
            elif off==0x706da0:result=self.keys
            elif off==0x748b50:
                self.native_calls.append(('key-debit',x,y,z))
                self.keys=max(0,self.keys-z)
            elif off==0x1363898:return
            elif off==0x136389c:
                self.native_calls.append(('music-gain',x,y))
                em.reg_write(UC_ARM_REG_SP,em.reg_read(UC_ARM_REG_SP)+24)
            elif off==0x235048:
                translation=struct.unpack('<f',struct.pack('<I',self.get(y+8)))[0]
                self.native_calls.append(('board-draw',self.get(x+0x2c),translation,self.get(y+0x20),self.get(y+0x28)))
            elif off==0x8f358c and 'offlineSpeedFeedbackRate' in self.exports:
                assert x==self.speed_widget
                if self.speed_target is not None:
                    self.put(self.speed_controller+0x30,self.speed_target)
                em.reg_write(UC_ARM_REG_SP,em.reg_read(UC_ARM_REG_SP)+36)
                result=0x1234
            elif off==0x1166c30:
                em.mem_write(x+0x4c,bytes(em.mem_read(y,16)))
            elif off==0x1167010:
                height=self.get(em.reg_read(UC_ARM_REG_SP))
                self.native_calls.append(('bar',y,z,w,height,self.get(x+0x4c)))
            elif off==0x11698b4:
                stack=em.reg_read(UC_ARM_REG_SP)
                self.native_calls.append(('art',z,w,self.get(stack),self.get(stack+4),self.get(x+0x4c)))
            elif off==0x11699c4:
                destination=struct.unpack('<4i',em.mem_read(z,16))
                source=struct.unpack('<4i',em.mem_read(w,16))
                self.native_calls.append(('cover',destination,source))
            elif off==0x15ddedc:result=x//y
            else:return super().hook(em,a,size,data)
            em.reg_write(UC_ARM_REG_R0,result);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)
        def values(self,values):p=self.alloc(4*len(values));self.u.mem_write(p,struct.pack('<'+'I'*len(values),*values));return p
        def command(self,cmd,values=()):p=self.values(values) if values else 0;self.run('offlinePresetCommand',cmd,p,len(values));return self.u.reg_read(UC_ARM_REG_R0)
        def poll(self):p=self.alloc(1024);self.run('offlinePresetPoll',p,256);n=self.u.reg_read(UC_ARM_REG_R0);return list(struct.unpack('<'+'I'*n,bytes(self.u.mem_read(p,n*4)))) if n else []
    e=EditorEngine();valid=[15,2,2,0,0,1,2,1,0,3]
    def validate(v):p=e.values(v);e.run(e.exports['offlinePresetValidate'],p,len(v));return e.u.reg_read(UC_ARM_REG_R0)
    assert validate(valid)==1
    catalog=json.loads((core.OUT/'generated/preset-editor-catalogue.json').read_text())
    forbidden=[p for p in catalog if not p.get('allowed',True)]
    for plant in forbidden:assert validate([1,1,plant['id'],0,0,1])==0
    for bad in ([0,0],[16,0],[1,46],[1,1,999999,0,0,1],[1,1,2,5,0,1],[1,1,2,0,9,1],[1,1,2,0,0,5],[15,2,2,0,0,1,2,0,0,3]):assert validate(bad)==0,bad
    assert e.command(1,valid)==0 # no stale/unrequested settings entry
    settings=core.M+0x22000
    e.run('offlinePresetSettingsClick',settings,1002)
    if 'offlinePresetPageRows' in e.exports:
        assert e.u.reg_read(UC_ARM_REG_R0)==2
        opened=e.poll()
        assert opened in ([],[20])
        if opened==[20]:
            e.run('offlinePresetSettingsClick',settings,1010);assert e.poll()==[14]
        e.run('offlinePresetSettingsClick',settings,1011);assert e.poll()==[21]
    else:assert e.poll()==[2]
    board_name='arena_plant_test' if e.stock_board else 'arena_preset_editor'
    assert e.command(1,valid)==1;assert e.loaded==[board_name];assert e.get(core.M+0xa8)==1
    if e.stock_board:
        name=e.alloc(4);e.string(name,'arena_plant_test')
        out=e.alloc(8)
        e.run('offlinePresetLevelDefinition',out,core.M,name)
        assert e.native_calls[-1]==('definition','arena_preset_editor')
        assert e.txt(e.get(name))=='arena_plant_test'
        if e.edit_tools:
            assert e.state()[4]==b'\0'
            e.run('offlinePresetAdvanceDefensePhase',core.M+0x22000,3)
            assert e.native_calls[-1]==('defense-phase',3,1) and e.state()[4]==b'\0'
        else:
            e.run('offlinePresetHideTutorialSave',core.M+0x22000,0)
            assert e.native_calls[-1]==('definition','arena_preset_editor')
    assert e.command(1,valid)==0 # cannot recursively open / replace snapshot
    assert e.get(core.M+0x88)-e.get(core.M+0x84)==24
    assert e.command(2,[3])==1
    e.run('offlinePresetGrade',core.M,0);assert e.u.reg_read(UC_ARM_REG_R0)==3
    e.run('offlinePresetSpawnGrade',0,0);e.run('offlinePresetGrade',core.M,0);assert e.u.reg_read(UC_ARM_REG_R0)==1
    e.run('offlinePresetSpawnGrade',0,1);e.run('offlinePresetGrade',core.M,0);assert e.u.reg_read(UC_ARM_REG_R0)==3
    e.run('offlinePresetSpawnDone');assert e.command(2,[1])==1
    e.put(e.app+0x6bc,e.board);e.string(e.board+0xc4,board_name);e.put(e.board+0xc0,5)
    if 'offlinePresetUsePlacementGrade' in e.exports:
        e.stub(0x4b6804)
        assert e.native_calls[-1]==('plant-grade-path',0x4b6ce0)
    for row,grade in ((0,1),(1,3)):
        plant=e.alloc(0x200);e.put(plant+0x38,grade);e.cells[(0,row)]=plant
    for key in (0,0x19833080,0x6d773b43):
        e.put(e.board+0x130,key)
        assert e.poll()==([10] if key==0 else [])
        encoded=e.get(e.board+0x12c);shift=key&31
        assert (((encoded>>shift)|(encoded<<((32-shift)&31)))&0xffffffff)^key==100000
        assert e.get(e.board+0x130)==key
    files=dict(e.files);e.run('offlineTrainingTick',core.M);assert e.files==files
    e.run('offlinePresetSaveClick');event=e.poll();assert event==[11,*valid],event
    assert e.files==files # export only; no wallet or home/shop file writes
    assert e.poll()==[] and e.scenes==[] # waiting for the durable draft acknowledgement
    assert e.command(3)==1;assert e.state()==e.originals
    assert e.get(core.M+0x84)==0 and e.get(core.M+0x90)==0
    assert e.scenes[-1]==2;assert ('finish',) in e.native_calls
    assert e.poll()==[16] # export is released only after the scene has been restored
    e.run('offlinePresetGrade',core.M,0);assert e.u.reg_read(UC_ARM_REG_R0)==0
    if 'offlinePresetUsePlacementGrade' in e.exports:
        e.stub(0x4b6804)
        assert e.native_calls[-1]==('plant-grade-path',0x4b6808)
    assert e.command(2,[3])==0
    if e.stock_board:
        e.run('offlinePresetLevelDefinition',out,core.M,name)
        assert e.native_calls[-1]==('definition','arena_plant_test')
        if e.edit_tools:
            e.run('offlinePresetAdvanceDefensePhase',core.M+0x22000,3)
            assert e.native_calls[-1]==('defense-phase',3,5)
        else:
            e.run('offlinePresetHideTutorialSave',core.M+0x22000,0)
            assert e.native_calls[-1]==('stock-button-visibility',core.M+0x22000,0)
    print('PASS: schema limits, mixed individual grades, scoped unlock/session, native save export, teardown and manager restoration; no save writes')
    if 'offlinePvpMusicSample' in e.exports:
        volume=struct.pack('<d',0.75)
        gain=struct.unpack('<I',struct.pack('<f',0.75))[0]
        mixer=e.alloc(0x50)
        e.u.mem_write(e.app+0x88,volume);e.put(e.app+0x460,mixer)
        def sample(scene,board=None):
            e.put(core.GM+0x984,scene)
            if board is not None:e.string(e.board+0xc4,board)
            e.run('offlinePvpMusicSample')
            return e.u.reg_read(UC_ARM_REG_R0)
        assert sample(28)==sample(25)==sample(29)==gain|1
        assert e.command(9,[1])==1 and e.native_calls[-1]==('music-gain',mixer,0)
        e.stub(0x1363898,mixer,gain)
        assert e.native_calls[-1]==('music-gain',mixer,0)
        assert sample(6,'arena_battle_test')==gain|2
        assert e.command(9,[2])==1
        assert sample(25)==gain|1 and sample(7)==0
        assert e.native_calls[-1]==('music-gain',mixer,gain)
        assert sample(6,'arena_plant_test')==0
        e.stub(0x1363898,mixer,gain)
        assert e.native_calls[-1]==('music-gain',mixer,gain)
        print('PASS: lobby/map/lab continuity, PvP board track, scoped mixer mute and original music gain restoration')
    if 'offlineBranchGateOpened' in e.exports or 'offlineBranchGateSpend' in e.exports:
        def float_bits(value):return struct.unpack('<I',struct.pack('<f',value))[0]
        e.u.mem_write(e.app+0x90,struct.pack('<d',0.5))
        if 'offlineBranchGateSpend' in e.exports:
            gate,scene,world=e.alloc(0xb0),e.alloc(0x200),e.alloc(4)
            e.put(scene+0x170,gate)
            for site in (0x9f2110,0x9f2b90,0x9f2e18,0x9f305c):
                for kind,cost,keys,plays in ((8,2,4,True),(8,2,1,False),(8,0,4,False),(7,2,4,False)):
                    e.keys=keys
                    e.put(gate+0x10,kind)
                    e.u.reg_write(UC_ARM_REG_R6,gate);e.u.reg_write(UC_ARM_REG_R9,scene)
                    e.stub(site,core.PROFILE,world,cost)
                    assert e.native_calls[-1]==('key-debit',core.PROFILE,world,cost)
                    assert e.keys==max(0,keys-cost)
                    assert e.poll()==([17,float_bits(0.5)] if plays else []) and e.poll()==[]
        else:
            for gate,caller,state in ((7,0x809bec,3),(8,0x809bec,2),(8,0x228058,3)):
                e.run('offlineBranchGateOpened',gate,core.BASE+caller,state)
                assert e.poll()==[]
            for caller in (0x809bec,0x74abb8,0x9f258c):
                e.run('offlineBranchGateOpened',8,core.BASE+caller,3)
                assert e.poll()==[17,float_bits(0.5)] and e.poll()==[]
        assert e.command(10,[1])==1
        _,target,ducked=e.native_calls[-1]
        assert target==mixer and abs(struct.unpack('<f',struct.pack('<I',ducked))[0]-0.0375)<1e-7
        e.u.mem_write(e.app+0x88,struct.pack('<d',0.5))
        e.stub(0x1363898,mixer,float_bits(0.5))
        assert e.native_calls[-1]==('music-gain',mixer,float_bits(0.025))
        assert e.command(10,[0])==1
        assert e.native_calls[-1]==('music-gain',mixer,float_bits(0.5))
        print('PASS: key-gate success only, one-shot dispatch and 5% mixer gain restored to current slider')
    if 'offlineSpeedFeedbackRate' in e.exports:
        e=EditorEngine()
        e.speed_controller=e.alloc(0x80)
        e.speed_widget=e.alloc(0x100)
        e.put(core.BASE+0x1830528,e.speed_controller)
        e.put(e.app+0x6bc,e.board)
        e.u.mem_write(e.app+0x90,struct.pack('<d',0.5))
        normal,fast=0x3f800000,0x40000000
        for phase,paused,before,target,event in (
            (5,0,normal,fast,[18,2,0x3f000000]),
            (5,0,fast,normal,[18,1,0x3f000000]),
            (5,0,normal,None,[]),
            (5,1,normal,fast,[]),
            (3,0,normal,fast,[]),
        ):
            e.put(e.board+0xc0,phase)
            e.u.mem_write(e.board+0x8d5,bytes([paused]))
            e.put(e.speed_controller+0x30,before)
            e.speed_target=target
            e.stub(0x8f3588,e.speed_widget)
            assert e.u.reg_read(UC_ARM_REG_R0)==0x1234
            assert e.get(e.speed_controller+0x30)==(before if target is None else target)
            assert e.poll()==event and e.poll()==[]
        print('PASS: speed hook preserves the stock handler and emits one cue per valid transition')
    if 'boardCameraDraw' in e.exports:
        board,graphics=e.board,e.alloc(0xc0)
        for offset,value in ((0x34,3395),(0x994,-557)):e.put(board+offset,value)
        def draw(x,width):
            e.put(board+0x2c,x)
            e.put(e.app+0x524,width)
            e.put(graphics+8,struct.unpack('<I',struct.pack('<f',x))[0])
            e.put(graphics+0x20,0);e.put(graphics+0x28,width)
            e.stub(0x23aa00,board,graphics)
            assert (e.get(graphics+0x20),e.get(graphics+0x28))==(0,width)
            tag,actual,translation,clip_x,clip_width=e.native_calls[-1]
            assert tag=='board-draw'
            return struct.unpack('<i',struct.pack('<I',actual))[0],translation,clip_x,clip_width
        assert draw(-1223,2462)==(-1223,-1223,0,2462) # no stage yet
        e.put(board+0x938,core.M+0x24000)
        assert draw(-1223,2462)==(-933,-933,0,2462) # after the extra intro offset
        assert draw(-589,2462)==(-589,-589,0,2462) # seed selection
        assert draw(650,2462)==(557,557,0,2462) # left edge
        assert draw(-1223,3000)==(-395,-395,0,3000) # resized before draw
        assert draw(-1223,4352)==(757,757,200,3952) # center and clip only the world
        print('PASS: draw call clamps the post-offset camera at both edges and scopes ultrawide clipping')
    if 'drawWideMenuBackground' in e.exports:
        graphics,image=e.alloc(0xc0),e.alloc(0x80)
        if e.get(core.BASE+0x462958)==0xe1a00000:
            assert e.get(core.BASE+0x95e2d8)==0xe1a00000
            e.put(image+0x28,2306);e.put(image+0x2c,1538)
            for site in (0x462a00,0x95e3bc):
                for width,height,source in (
                    (2306,1538,(0,0,2306,1538)),
                    (1024,768,(128,0,2050,1538)),
                    (2560,1440,(0,120,2306,1297)),
                    (3840,1080,(0,256,2306,648)),
                ):
                    e.native_calls.clear()
                    e.stub(site,graphics,image,10,20,width,height)
                    assert e.native_calls==[('cover',(10,20,width,height),source)],e.native_calls
            print('PASS: both title draws cover the viewport and crop only the source artwork')
        else:
            e.put(image+0x28,2272);e.put(image+0x2c,1536)
            color=struct.pack('<4I',230,240,250,255)
            for site in (0x462a00,0x95e3bc):
                e.u.mem_write(graphics+0x4c,color)
                for width,height,expected in (
                    (2272,1536,[('art',10,20,2272,1536,230)]),
                    (2560,1440,[('bar',10,20,215,1440,0),('bar',2355,20,215,1440,0),
                                ('art',225,20,2130,1440,230)]),
                    (3841,1536,[('bar',10,20,784,1536,0),('bar',3066,20,785,1536,0),
                                ('art',794,20,2272,1536,230)]),
                ):
                    e.native_calls.clear()
                    e.stub(site,graphics,image,10,20,width,height)
                    assert e.native_calls==expected,e.native_calls
                    assert bytes(e.u.mem_read(graphics+0x4c,16))==color
            print('PASS: both title draws center proportional art, fill wide margins and restore tint')
if __name__=='__main__':main()
