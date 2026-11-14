"""Execute current ARM rules with synthetic users and native I/O/UI boundaries.

Never reads or changes a device/player save. Rendering and Android time are
mocked; this is not a substitute for game acceptance.
"""
from pathlib import Path
import sys,importlib,json,struct,math
from datetime import datetime,timezone,timedelta
from check_offline_pvp_v76_focused import Definitions


def check(folder):
    sys.argv=[sys.argv[0],str(folder)]
    sys.meta_path.insert(0,Definitions())
    core=importlib.import_module('check_offline_pvp_arm');core.OUT=folder
    Parent=importlib.import_module('check_offline_pvp_v81_arm').GarrisonEngine
    from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_PC,UC_ARM_REG_LR
    BASE,M,PM=core.BASE,core.M,core.PM

    class Rules(Parent):
        def __init__(self):
            super().__init__();self.now=int(datetime(2026,11,14,12,tzinfo=timezone.utc).timestamp())
            self.zone_objects={};self.board_zombies=[];self.tm=self.alloc(64);self.zone_list=self.alloc(12)
        def symbol(self,fragment):
            candidates=[v for k,v in self.exports.items() if fragment in k]
            assert len(candidates)==1,(fragment,candidates)
            return candidates[0]
        def state(self):return BASE+self.symbol('economyRuntime')+16
        def invoke(self,fragment,*args):
            # Exact local symbols retain the ordinary base-first helper ABI.
            name=next(k for k in self.exports if fragment in k)
            self.run(name,*args)
        def field(self,word):return self.get(self.state()+2912+word*4)
        def stored(self):return next(bytes(v) for k,v in self.files.items() if k.endswith('.eco'))
        def hook(self,em,a,size,d):
            off=a-BASE
            if self.payload_range[0]<=a<self.payload_range[1]:return
            if 0x10a7fd4<=off<=0x10a8008:return
            if 0x108ff0c<=off<=0x108ff20 or 0x1090244<=off<=0x1090258:return
            x,y,z,w=[em.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
            if a==core.END+0x300:
                self.closed+=1;result=0
            elif a==core.END+0x310:
                self.visible[x]=y;result=0
            elif a==core.END+0x330:result=0
            elif off==0x147854:
                self.put(self.tm+0x24,0);result=self.tm
            elif off in (0x23bcec,0x23bcd4):
                pos=struct.unpack('<f',em.mem_read(x+(16 if off==0x23bcec else 20),4))[0]
                result=math.floor((pos-(200 if off==0x23bcec else 160))/(64 if off==0x23bcec else 76))
            elif off==0x20ec10:result=core.M+0x30000
            elif off==0x20a1c0:result=self.zone_list
            elif off==0x348944:result=int(x in self.zone_objects and self.zone_objects[x][2])
            elif off==0x44a310:
                out=self.get(x);end=self.get(x+4);self.put(end,self.get(y));self.put(x+4,end+4);result=0
            elif off==0x11d74b4:result=M
            elif off==0x1da034 and self.get(y) in self.zone_objects:result=self.get(y)
            elif off==0xd06a04 and hasattr(self,'price_template'):
                self.string(x,self.price_template.replace('{CURRENCY_COST}',f'<IMAGE:ARENA_MONEY>{w}'),True);result=x
            elif off==0xd080f0 and hasattr(self,'price_template'):
                raw=bytes(em.mem_read(y,128)).decode('utf-32-le').split('\0')[0]
                assert raw=='[ARENA_PVP_OCCUPY_BTN]',raw
                self.string(x,self.price_template,True);result=x
            elif off==0x109fc30 and hasattr(self,'price_template'):
                text=self.get(y);self.rendered_price=bytes(em.mem_read(text,self.get(text-12)*4)).decode('utf-32-le')
                em.reg_write(UC_ARM_REG_PC,core.END);return
            elif off==0x10449b8:result=1
            elif off==0x109fc48 and hasattr(self,'price_template'):
                self.rendered_currency_cost=y;em.reg_write(UC_ARM_REG_PC,core.END);return
            else:return super().hook(em,a,size,d)
            em.reg_write(UC_ARM_REG_R0,result&0xffffffff);em.reg_write(UC_ARM_REG_PC,em.reg_read(UC_ARM_REG_LR)&~1)
        def point(self,col,row,dead=False):
            p=self.alloc(32);self.u.mem_write(p+16,struct.pack('<ff',232+64*col,198+76*row))
            self.zone_objects[p]=(col,row,dead);return p
        def start(self,id,live=True):
            self.put(BASE+self.symbol('arenaNpc'),id)
            npc=self.symbol('4NPCS');entry=next((npc+i*376 for i in range(17) if self.get(BASE+npc+i*376)==id),None)
            if entry is None:entry=self.symbol('VACANT_HOME')
            self.invoke('beginBattleFee',M,BASE+entry,int(live))
            return self.u.reg_read(UC_ARM_REG_R0)

    passed=0
    # The compiled range functions, including off-lawn columns and dead filter.
    e=Rules();center=e.point(8,2);out=e.alloc(12);buffer=e.alloc(4096);first=e.alloc(4096)
    points=[e.point(c,r) for c in range(5,12) for r in range(5)]
    dead=e.point(9,2,True);points.append(dead)
    for i,p in enumerate(points):e.put(first+4*i,p)
    e.put(e.zone_list,first);e.put(e.zone_list+4,first+4*len(points))
    for name,w,h in [('offlineFoodTargets',3,3),('offlineRageTargets',5,4)]:
        e.put(out,buffer);e.put(out+4,buffer);e.put(out+8,buffer+4096)
        e.run(name,out,2,center+16,0)
        got={e.get(p) for p in range(buffer,e.get(out+4),4)}
        expected={p for p,(c,r,d) in e.zone_objects.items() if p in points and not d and
                  (8-w//2<=c<8-w//2+w or 9<=c<=10) and 2-h//2<=r<2-h//2+h}
        assert got==expected,(name,len(got),len(expected));passed+=1
    for skill,offset in [('Aid',0x18),('Fog',0x14)]:
        zone=e.point(8,2);e.u.mem_write(zone+20,struct.pack('<f',198+2*76+24))
        weak=e.alloc(8);e.put(weak,zone);sub=e.alloc(40);e.put(sub+offset,weak);e.put(sub+offset+4,weak+8)
        for grade,(w,h) in enumerate([(3,3),(3,4),(4,4),(4,5)],1):
            e.put(BASE+e.symbol('skill'+skill+'Grade'),grade)
            for p in points:
                c,r,_=e.zone_objects[p];e.stub(0x1001a60 if skill=='Aid' else 0x10060cc,sub,p)
                want=int((8-w//2<=c<8-w//2+w or 9<=c<=10) and 2-h//2<=r<2-h//2+h)
                assert e.u.reg_read(UC_ARM_REG_R0)==want,(skill,grade,c,r);passed+=1

    e=Rules();e.enter();e.run('offlineGarden')
    assert len(e.stored())==2936 and struct.unpack_from('<I',e.stored(),4)[0]==18
    # A single persisted visitor replaces one ordinary record, never duplicates.
    rows=e.residents();dave=[p for p in rows if e.get(p)==0x70000007]
    assert len(dave)==1
    assert e.get(dave[0]+28)==1,'Dave must be on the initially visible main street'
    home=next(p for p in rows if e.get(p)==0x70000012)
    assert (e.get(home+28),e.get(home+32))==(1,1) and e.get(home+36)==1
    assert len({(e.get(p+28),e.get(p+32)) for p in rows})==len(rows)
    passed+=1
    # Auxiliary ordinary house persists and refreshes without roster/schema growth.
    e.invoke('vacantNeighbor');home_ptr=e.u.reg_read(UC_ARM_REG_R0)
    original=bytes(e.u.mem_read(home_ptr,900));word=e.get(e.state()+28)
    assert word&0x80000000 and e.get(home_ptr)==0x70000012
    e.run('offlineGarden');e.invoke('vacantNeighbor')
    assert bytes(e.u.mem_read(e.u.reg_read(UC_ARM_REG_R0),900))==original
    saved_home={k:bytearray(v) for k,v in e.files.items()}
    r=Rules();r.files=saved_home;r.enter();r.run('offlineGarden');r.invoke('vacantNeighbor')
    assert bytes(r.u.mem_read(r.u.reg_read(UC_ARM_REG_R0),900))==original
    r.invoke('replaceVacantNeighbor');assert r.u.reg_read(UC_ARM_REG_R0)==1
    assert r.get(r.state()+28)!=word and len(r.stored())==2936
    r.put(r.state()+2844+6*4,r.now+1800)
    r.invoke('neighborProtectionUntil',BASE+r.symbol('VACANT_HOME'))
    assert r.u.reg_read(UC_ARM_REG_R0)==r.now+1800
    r.failwrite=True;before=r.get(r.state()+28);r.invoke('replaceVacantNeighbor')
    assert r.u.reg_read(UC_ARM_REG_R0)==0 and r.get(r.state()+28)==before
    passed+=5
    # Direct map construction must populate houses before drawing, without
    # requiring the Garden menu callback or a second app launch.
    direct=Rules();direct.enter();direct.run('offlineMapArmyPrepare',direct.alloc(0x400))
    homes=direct.residents()
    assert any(direct.get(p)==0x70000012 for p in homes)
    assert sum(direct.get(p)==0x70000007 for p in homes)==1
    assert len({(direct.get(p+28),direct.get(p+32)) for p in homes})==len(homes)
    # A saved visitor in the far zone migrates into the initial main street.
    direct.put(direct.state()+2912+3*4,0x70000011)
    direct.invoke('saveEconomy',direct.state());direct.run('offlineGarden')
    visitor=next(p for p in direct.residents() if direct.get(p)==0x70000007)
    assert direct.get(visitor+28)==1 and direct.field(3)!=0x70000011
    direct.invoke('encounter',0x70000011)
    assert direct.get(direct.u.reg_read(UC_ARM_REG_R0))==0x70000011
    passed+=2
    victim=e.field(3);assert victim and victim!=0x70000007 and all(e.get(p)!=victim for p in rows)
    slot=(e.get(dave[0]+28),e.get(dave[0]+32));serial=e.field(2)
    e.run('offlineGarden');assert (e.field(2),e.field(3))==(serial,victim);passed+=1
    # Match ceiling affects both sampling and generated/validated encounters.
    for seed in range(1,25):
        values=[]
        for cups in (100,400,500,501,1000,2000000000):
            e.run(e.symbol('matchedNeighborCups'),cups,seed);values.append(e.u.reg_read(UC_ARM_REG_R0))
        assert values[2]==values[3]==values[4]==values[5] and 450<=values[2]<=550
        assert values[0]<values[1]<values[2];passed+=1
    e.put(e.state()+2840,500)
    roster=e.get(BASE+e.exports['_ZL14neighborRoster'])
    generated=e.alloc(900)
    e.run(e.symbol('generateRosterNeighbor'),roster,generated,0x70000002,12345,8,0)
    assert 450<=e.get(generated+12)<=550
    e.run(e.symbol('validEncounter'),generated,0x70000002,0,0)
    assert e.u.reg_read(UC_ARM_REG_R0)==1;passed+=1
    for day in range(1,15):
        # Repeated map opens/restarts do not reroll; Tue/Thu/Sat start a cycle.
        e.now=int(datetime(2026,11,14,12,tzinfo=timezone.utc).timestamp())+day*86400
        previous=e.field(2);e.run('offlineGarden');current=e.field(2)
        weekday=datetime.fromtimestamp(e.now,timezone.utc).weekday()
        assert (current>previous)==(weekday in (1,3,5)),(day,previous,current,weekday)
        rows=e.residents();assert len([p for p in rows if e.get(p)==0x70000007])==1
        assert len({(e.get(p+28),e.get(p+32)) for p in rows})==len(rows)
        passed+=1
    saved={k:bytearray(v) for k,v in e.files.items()};r=Rules();r.files=saved;r.now=e.now;r.enter();r.run('offlineGarden')
    assert (r.field(2),r.field(3))==(e.field(2),e.field(3));passed+=1
    # Use the same persisted result fields written on a real Dave victory.
    e.put(e.state()+2912+4*4,0);e.put(e.state()+2912+5*4,1)
    e.invoke('saveEconomy',e.state());e.run('offlineGarden')
    assert not e.field(4) and not e.field(5) and all(e.get(p)!=0x70000007 for p in e.residents())
    e.run('offlineGarden');assert not e.field(4);passed+=1
    # Execute the actual zero-id special-house route from its relocated plot.
    flow=Rules();flow.enter();flow.run('offlineGarden');flow.train();flow.advance(31)
    flow.run('offlineTrainingTick',flow.get(M+0x20))
    dave=next(p for p in flow.residents() if flow.get(p)==0x70000007)
    flow.selected(dave);before=len(flow.loads)
    flow.stub(0x1042fe8,M,0,4,0)
    assert len(flow.loads)==before+1 and flow.get(BASE+flow.symbol('arenaNpc'))==0x70000007
    passed+=1
    battle=importlib.import_module('check_offline_pvp_v60_arm')
    battle.board(flow)
    flow.run(0x1030a50,M+0x14300,1);flow.deaths(0)
    flow.run('offlineBattleResult',M,1,0x70000007,1)
    assert flow.u.reg_read(UC_ARM_REG_R0)==1
    assert flow.field(4)==0 and flow.field(5)==1
    flow.run('offlineGarden')
    assert not flow.field(5) and all(flow.get(p)!=0x70000007 for p in flow.residents())
    passed+=1
    # Ordinary attacks: fee tiers, atomic refusal, no double debit and refund.
    e=Rules();e.enter();wallet=e.state()+12;e.put(wallet,100000);e.invoke('saveEconomy',e.state())
    target=0x70000002
    e.price_template='{CURRENCY_COST}攻击!';label=e.alloc(4);key=e.alloc(4);template=e.alloc(4)
    def shown(site=0x10a7ffc,original=1):
        e.stub(site,label,template,key,original);text=e.get(label);length=e.get(text-12)
        return bytes(e.u.mem_read(text,length*4)).decode('utf-32-le')
    e.put(BASE+e.symbol('arenaNpc'),target)
    for index in range(18):
        fee=10 if index<5 else 20 if index<10 else 50 if index<15 else 100
        assert shown()==f'<IMAGE:ARENA_MONEY>{fee}攻击!';passed+=1
        assert shown(0x109f308,500)==f'<IMAGE:ARENA_MONEY>{fee}攻击!';passed+=1
        # Execute the real scout refresh tail: its literal localized key,
        # default property price of one, formatter and button label setter.
        props=e.alloc(0x80);e.put(props+0x5c,1)
        e.u.reg_write(UC_ARM_REG_R4,label);e.u.reg_write(UC_ARM_REG_R5,template);e.u.reg_write(UC_ARM_REG_R7,e.alloc(0x200))
        e.run(0x10a7fd4,props)
        assert e.rendered_price==f'<IMAGE:ARENA_MONEY>{fee}攻击!';passed+=1
        for entry in (0x108ff0c,0x1090244):
            e.u.reg_write(UC_ARM_REG_R8,e.alloc(0x200));e.run(entry)
            assert e.rendered_currency_cost==fee;passed+=1
        before=e.get(wallet);assert e.start(target)
        assert e.get(wallet)==before-fee,(index,e.get(wallet),before)
        assert not e.start(target) and e.get(wallet)==before-fee
        e.invoke('closeAbandonedBattle',M);passed+=1
    e.now+=86400;before=e.get(wallet);assert e.start(target) and e.get(wallet)==before-10
    e.invoke('closeAbandonedBattle',M);passed+=1
    e.put(BASE+e.symbol('arenaNpc'),0x70000007)
    assert shown()=='<IMAGE:ARENA_MONEY>1攻击!';passed+=1
    # The old fixed plot follows the same fee tiers and NPC resolution.
    before=e.get(wallet);assert e.start(0x70000012) and e.get(wallet)==before-10
    e.invoke('closeAbandonedBattle',M);passed+=1
    count=e.field(1);before=e.get(wallet);assert e.start(target,False)
    assert e.field(1)==count;e.invoke('closeAbandonedBattle',M)
    assert e.get(wallet)==before and e.field(1)==count;passed+=1
    e.failwrite=True;before=e.get(wallet);count=e.field(1);assert not e.start(target)
    assert e.get(wallet)==before and e.field(1)==count;passed+=1
    # Old v17 prefix survives migration, rather than treating it as corrupt.
    old=bytearray(e.stored()[:2912]);struct.pack_into('<I',old,4,17)
    checksum=2166136261
    for i,b in enumerate(old):
        if i<24 or i>=28:checksum=((checksum^b)*16777619)&0xffffffff
    struct.pack_into('<I',old,24,checksum)
    r=Rules();r.files={k:bytearray(v) for k,v in e.files.items()}
    key=next(k for k in r.files if k.endswith('.eco'));r.files[key]=old;r.enter()
    assert r.get(r.state()+12)==e.get(wallet) and r.get(r.state()+2840)==e.get(e.state()+2840);passed+=1
    # Keep the accepted v168 behavior in the fully rebuilt engine: one real
    # research/finish transaction updates its copied card and scope grade.
    f=Rules();f.enter();f.put(f.state()+12,10000);f.invoke('saveEconomy',f.state())
    f.invoke('applyEconomy',M);ui=f.research_ui(1);cards=f.alloc(16)
    for i,name in enumerate(['pvpskill_aid','pvpskill_invisible','pvpskill_rage','pvpskill_zombiefood']):
        card=f.alloc(0x204);f.put(cards+4*i,card);f.put(card+0x1f8,1);f.string(card+0x1fc,name)
    f.put(ui+0xb4,cards);f.put(ui+0xb8,cards+16)
    f.click_research(ui);assert f.get(f.get(cards+4)+0x1f8)==1
    f.click_research(ui)
    importlib.import_module('check_offline_pvp_v48_arm').SessionEngine.confirm(f,f.research_timer)
    f.run('offlineResearchTick',ui)
    assert f.get(f.get(cards+4)+0x1f8)==2 and f.get(BASE+f.symbol('skillFogGrade'))==2
    passed+=1
    remembered=Rules();remembered.files={k:bytearray(v) for k,v in f.files.items()};remembered.enter()
    assert remembered.get(BASE+remembered.symbol('skillFogGrade'))==2
    zone=remembered.point(4,2);remembered.u.mem_write(zone+20,struct.pack('<f',198+2*76+24))
    weak=remembered.alloc(8);remembered.put(weak,zone);sub=remembered.alloc(40)
    remembered.put(sub+0x14,weak);remembered.put(sub+0x18,weak+8)
    # In-game grade II is 4 rows, not the 5 rows reserved for grade IV.
    for grade,rows,cols in [(1,3,3),(2,4,3),(3,4,4),(4,5,4)]:
        remembered.put(remembered.state()+308+4,grade)
        remembered.invoke('applyResearch',M)
        assert remembered.get(BASE+remembered.symbol('skillFogGrade'))==grade
        for col,row in [(4,r) for r in range(5)]+[(c,2) for c in range(1,8)]:
            target=remembered.point(col,row);remembered.stub(0x10060cc,sub,target)
            want=int(4-cols//2<=col<4-cols//2+cols and 2-rows//2<=row<2-rows//2+rows)
            assert remembered.u.reg_read(UC_ARM_REG_R0)==want,(grade,col,row)
        passed+=1
    f.put(PM+0x74,43);f.put(core.PROFILE+0x75c,1);f.enter()
    assert f.get(BASE+f.symbol('skillFogGrade'))==1 and f.get(BASE+f.symbol('skillAidGrade'))==1
    passed+=1
    result=dict(arm_rule_cases_passed=passed,device_saves_touched=False,runtime_game_verified=False)
    (folder/'pvp-rule-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':check(Path(sys.argv[1]).resolve())
