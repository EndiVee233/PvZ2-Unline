"""Add mouse hover to the existing Java event queue and native touch dispatcher."""
from pathlib import Path
import hashlib, os, struct, subprocess, zlib
from io import BytesIO
from elftools.elf.elffile import ELFFile
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM

MANAGER = '''
.method public HandleHoverEvent(Landroid/view/MotionEvent;)Z
    .locals 5
    iget-boolean v0, p0, Lcom/popcap/SexyAppFramework/AndroidUIEventManager;->mbAppHasFocus:Z
    if-nez v0, :focused
    const/4 v0, 0x0
    return v0
    :focused
    iget-object v0, p0, Lcom/popcap/SexyAppFramework/AndroidUIEventManager;->mMouseHoverTracker:Lcom/popcap/SexyAppFramework/AndroidUIEventManager$UITouchTracker;
    if-nez v0, :update
    new-instance v0, Lcom/popcap/SexyAppFramework/AndroidUIEventManager$UITouchTracker;
    invoke-direct {v0, p0}, Lcom/popcap/SexyAppFramework/AndroidUIEventManager$UITouchTracker;-><init>(Lcom/popcap/SexyAppFramework/AndroidUIEventManager;)V
    const/4 v1, 0x0
    const/4 v2, 0x5
    invoke-virtual {v0, p1, v1, v2, v1}, Lcom/popcap/SexyAppFramework/AndroidUIEventManager$UITouchTracker;->InitializeFromMotionEvent(Landroid/view/MotionEvent;III)V
    iput-object v0, p0, Lcom/popcap/SexyAppFramework/AndroidUIEventManager;->mMouseHoverTracker:Lcom/popcap/SexyAppFramework/AndroidUIEventManager$UITouchTracker;
    goto :enqueue
    :update
    const/4 v1, 0x0
    const/4 v2, 0x5
    invoke-virtual {v0, p1, v2, v1}, Lcom/popcap/SexyAppFramework/AndroidUIEventManager$UITouchTracker;->UpdateFromMotionEvent(Landroid/view/MotionEvent;II)V
    :enqueue
    invoke-virtual {p1, v1}, Landroid/view/MotionEvent;->getPointerId(I)I
    move-result v4
    iput v4, v0, Lcom/popcap/SexyAppFramework/AndroidUIEventManager$UITouchTracker;->mPointerId:I
    new-instance v3, Lcom/popcap/SexyAppFramework/AndroidUIEventManager$UITouchEvent;
    invoke-direct {v3, p0, v0}, Lcom/popcap/SexyAppFramework/AndroidUIEventManager$UITouchEvent;-><init>(Lcom/popcap/SexyAppFramework/AndroidUIEventManager;Lcom/popcap/SexyAppFramework/AndroidUIEventManager$UITouchTracker;)V
    invoke-direct {p0, v3}, Lcom/popcap/SexyAppFramework/AndroidUIEventManager;->EnqueueEvent(Lcom/popcap/SexyAppFramework/AndroidUIEventManager$UIEvent;)V
    const/4 v0, 0x1
    return v0
.end method
'''

SURFACE = '''
.method public onHoverEvent(Landroid/view/MotionEvent;)Z
    .locals 3
    invoke-virtual {p1}, Landroid/view/MotionEvent;->getSource()I
    move-result v0
    const/16 v1, 0x2002
    and-int/2addr v0, v1
    if-ne v0, v1, :fallback
    invoke-virtual {p1}, Landroid/view/MotionEvent;->getActionMasked()I
    move-result v0
    const/16 v1, 0xa
    if-eq v0, v1, :consumed
    const/4 v1, 0x7
    if-eq v0, v1, :move
    const/16 v1, 0x9
    if-ne v0, v1, :fallback
    :move
    invoke-static {}, Lcom/popcap/SexyAppFramework/SexyAppFrameworkActivity;->instance()Lcom/popcap/SexyAppFramework/SexyAppFrameworkActivity;
    move-result-object v0
    invoke-virtual {v0}, Lcom/popcap/SexyAppFramework/SexyAppFrameworkActivity;->SplashScreenShowing()Z
    move-result v0
    if-eqz v0, :forward
    const/4 v0, 0x0
    return v0
    :forward
    iget-object v0, p0, Lcom/popcap/SexyAppFramework/AndroidSurfaceView;->mUIEventManager:Lcom/popcap/SexyAppFramework/AndroidUIEventManager;
    invoke-virtual {v0, p1}, Lcom/popcap/SexyAppFramework/AndroidUIEventManager;->HandleHoverEvent(Landroid/view/MotionEvent;)Z
    move-result v0
    return v0
    :consumed
    const/4 v0, 0x1
    return v0
    :fallback
    invoke-super {p0, p1}, Landroid/opengl/GLSurfaceView;->onHoverEvent(Landroid/view/MotionEvent;)Z
    move-result v0
    return v0
.end method
'''

def rebuild_mouse_dex(original, output, apktool):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    source=Path(__file__).with_name('RepairDex.java')
    subprocess.run(['javac','-cp',str(apktool),'-d',str(output),str(source)],check=True)
    cp=str(apktool)+os.pathsep+str(output)
    (output/'original.dex').write_bytes(original)
    subprocess.run(['java','-Xmx512m','-cp',cp,'RepairDex','decode',str(output/'original.dex'),str(output/'smali')],check=True)
    for name,code in [('AndroidSurfaceView',SURFACE),('AndroidUIEventManager',MANAGER)]:
        p=output/'smali/com/popcap/SexyAppFramework'/f'{name}.smali'
        text=p.read_text(encoding='utf8')
        if name=='AndroidUIEventManager':
            import re
            pos=text.index('\n.method')
            text=text[:pos]+'\n.field private mMouseHoverTracker:Lcom/popcap/SexyAppFramework/AndroidUIEventManager$UITouchTracker;\n'+text[pos:]
            text,n=re.subn(r'(\.method public HandleLostFocus\(\)V\s+\.(?:locals|registers) \d+)',
                r'\1\n    const/4 v0, 0x0\n    iput-object v0, p0, Lcom/popcap/SexyAppFramework/AndroidUIEventManager;->mMouseHoverTracker:Lcom/popcap/SexyAppFramework/AndroidUIEventManager$UITouchTracker;',text)
            assert n==1
        signature='onHoverEvent(' if name=='AndroidSurfaceView' else 'HandleHoverEvent('
        assert '.method public '+signature not in text
        p.write_text(text+'\n'+code,encoding='utf8')
    target=output/'classes.dex'
    subprocess.run(['java','-Xmx512m','-cp',cp,'RepairDex','encode',str(output/'smali'),str(target)],check=True)
    b=target.read_bytes()
    assert hashlib.sha1(b[32:]).digest()==b[12:32]
    assert zlib.adler32(b[12:])&0xffffffff==struct.unpack_from('<I',b,8)[0]
    assert struct.unpack_from('<I',b,96)[0]==struct.unpack_from('<I',original,96)[0]
    return b

def add_native_hover(original):
    b=bytearray(original);e=ELFFile(BytesIO(b))
    idx,s=[(i,s) for i,s in enumerate(e.iter_segments()) if s['p_type']=='PT_LOAD'][-1]
    assert s['p_flags']==5 and s['p_offset']+s['p_filesz']==len(b)
    offset=len(b);start=s['p_vaddr']+s['p_filesz'];site=0x132b660
    old=bytes(b[site:site+4]);assert old==bytes.fromhex('040053e3')
    asm='''cmp r3,#5
    beq hover
    cmp r3,#4
    b #0x132b664
    hover:
    mov r0,r5
    mov r1,r4
    bl #0x1327d0c
    mov r2,#1
    str r2,[r4,#0x28]
    ldr r0,[r5,#0x44]
    mov r1,r4
    ldr r3,[r0]
    ldr r3,[r3,#0x1d0]
    blx r3
    b #0x132b688'''
    code=bytes(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(asm,addr=start)[0]);b.extend(code)
    struct.pack_into('<I',b,site,0xea000000|(((start-site-8)//4)&0xffffff))
    ph=e['e_phoff']+idx*e['e_phentsize']
    for p in [ph+16,ph+20]:struct.pack_into('<I',b,p,struct.unpack_from('<I',b,p)[0]+len(code))
    return b,dict(site=hex(site),before=old.hex(),after=b[site:site+4].hex(),stub_offset=hex(offset),stub_va=hex(start),stub_size=len(code),hover_phase=5,button_events_synthesized=False,device_verified=False)
