"""Rebuild desktop input and append a freestanding native command handler to v21."""
from pathlib import Path
from io import BytesIO
import hashlib,json,os,re,shutil,struct,subprocess,zipfile
from elftools.elf.elffile import ELFFile
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'work/input-v22';OUT.mkdir(exist_ok=True)
os.environ['TEMP']=os.environ['TMP']=str(ROOT/'work/tmp')
BASE=ROOT/'work/mouse-v21/PvZ2-v21-hover-planting-cross.apk'
assert hashlib.file_digest(BASE.open('rb'),'sha256').hexdigest()=='75ae8c54e41faccfde54d4baddc4a58eeb30057e6b4078f19ff86d95f114e29e'
MANAGER='Lcom/popcap/SexyAppFramework/AndroidUIEventManager;'
TRACK='Lcom/popcap/SexyAppFramework/AndroidUIEventManager$UITouchTracker;'
surface='Lcom/popcap/SexyAppFramework/AndroidSurfaceView;'
queue=f'''
.method public QueueDesktopCommand(I)V
 .locals 5
 iget-boolean v0,p0,{MANAGER}->mbAppHasFocus:Z
 if-eqz v0,:done
 new-instance v0,{TRACK}
 invoke-direct {{v0,p0}},{TRACK}-><init>({MANAGER})V
 int-to-float v1,p1
 iput v1,v0,{TRACK}->X:F
 const/4 v1,0x6
 iput v1,v0,{TRACK}->phase:I
 const/4 v1,0x1
 iput v1,v0,{TRACK}->mTapCount:I
 invoke-direct {{p0}},{MANAGER}->GetTimeStamp()D
 move-result-wide v1
 iput-wide v1,v0,{TRACK}->mTimestampMS:D
 const/high16 v1,-0x40800000
 iput v1,v0,{TRACK}->previousX:F
 iput v1,v0,{TRACK}->previousY:F
 iget-object v2,p0,{MANAGER}->mMouseHoverTracker:{TRACK}
 if-eqz v2,:enqueue
 iget v1,v2,{TRACK}->X:F
 iput v1,v0,{TRACK}->previousX:F
 iget v1,v2,{TRACK}->Y:F
 iput v1,v0,{TRACK}->previousY:F
 :enqueue
 new-instance v3,Lcom/popcap/SexyAppFramework/AndroidUIEventManager$UITouchEvent;
 invoke-direct {{v3,p0,v0}},Lcom/popcap/SexyAppFramework/AndroidUIEventManager$UITouchEvent;-><init>({MANAGER}{TRACK})V
 invoke-direct {{p0,v3}},{MANAGER}->EnqueueEvent(Lcom/popcap/SexyAppFramework/AndroidUIEventManager$UIEvent;)V
 :done
 return-void
.end method

.method public HandleDesktopKey(Landroid/view/KeyEvent;)Z
 .locals 3
 invoke-virtual {{p1}},Landroid/view/KeyEvent;->getKeyCode()I
 move-result v0
 sparse-switch v0,:keys
 const/4 v0,0x0
 return v0
 :matched
 invoke-virtual {{p1}},Landroid/view/KeyEvent;->getAction()I
 move-result v1
 if-nez v1,:consumed
 invoke-virtual {{p1}},Landroid/view/KeyEvent;->getRepeatCount()I
 move-result v1
 if-nez v1,:consumed
 invoke-virtual {{p0,v0}},{MANAGER}->QueueDesktopCommand(I)V
 :consumed
 const/4 v0,0x1
 return v0
 :keys
 .sparse-switch
'''+''.join(f'  {k} -> :matched\n' for k in [8,9,10,11,29,32,33,34,41,45,46,50,51,62])+'''
 .end sparse-switch
.end method
'''
right=f'''
.method public HandleDesktopRight(Landroid/view/MotionEvent;)Z
 .locals 3
 invoke-virtual {{p1}},Landroid/view/MotionEvent;->getButtonState()I
 move-result v0
 and-int/lit8 v0,v0,0x2
 if-nez v0,:held
 iget-boolean v0,p0,{surface}->mDesktopRightDown:Z
 if-eqz v0,:no
 const/4 v1,0x0
 iput-boolean v1,p0,{surface}->mDesktopRightDown:Z
 const/4 v0,0x1
 return v0
 :held
 iget-boolean v0,p0,{surface}->mDesktopRightDown:Z
 if-nez v0,:yes
 const/4 v0,0x1
 iput-boolean v0,p0,{surface}->mDesktopRightDown:Z
 iget-object v0,p0,{surface}->mUIEventManager:{MANAGER}
 const/16 v1,0x64
 invoke-virtual {{v0,v1}},{MANAGER}->QueueDesktopCommand(I)V
 :yes
 const/4 v0,0x1
 return v0
 :no
 const/4 v0,0x0
 return v0
.end method

.method public dispatchTouchEvent(Landroid/view/MotionEvent;)Z
 .locals 1
 invoke-virtual {{p0,p1}},{surface}->HandleDesktopRight(Landroid/view/MotionEvent;)Z
 move-result v0
 if-eqz v0,:normal
 return v0
 :normal
 invoke-super {{p0,p1}},Landroid/opengl/GLSurfaceView;->dispatchTouchEvent(Landroid/view/MotionEvent;)Z
 move-result v0
 return v0
.end method
'''
with zipfile.ZipFile(BASE) as src:
 dex=src.read('classes.dex');b=bytearray(src.read('lib/armeabi/libSrc.so'))
 cp=str(ROOT/'tools/apktool.jar')+os.pathsep+str(ROOT/'work/desktop-v17/input-dex')
 (OUT/'original.dex').write_bytes(dex)
 subprocess.run(['java','-Xmx512m','-cp',cp,'RepairDex','decode',str(OUT/'original.dex'),str(OUT/'smali')],check=True)
 p=OUT/'smali/com/popcap/SexyAppFramework/AndroidUIEventManager.smali';t=p.read_text(encoding='utf8')
 sig='.method public HandleKeyEvent(Landroid/view/KeyEvent;)Z\n    .registers 4'
 assert sig in t
 t=t.replace(sig,sig+f'\n invoke-virtual {{p0,p1}},{MANAGER}->HandleDesktopKey(Landroid/view/KeyEvent;)Z\n move-result v0\n if-eqz v0,:original_key\n return v0\n :original_key',1)
 p.write_text(t+queue,encoding='utf8')
 p=OUT/'smali/com/popcap/SexyAppFramework/AndroidSurfaceView.smali';t=p.read_text(encoding='utf8')
 sig='.method public dispatchGenericMotionEvent(Landroid/view/MotionEvent;)Z\n    .registers 5';assert sig in t
 t=t.replace(sig,sig+f'\n invoke-virtual {{p0,p1}},{surface}->HandleDesktopRight(Landroid/view/MotionEvent;)Z\n move-result v0\n if-eqz v0,:normal_generic\n return v0\n :normal_generic',1)
 # The v19 per-move diagnostic is no longer needed in the regular input build.
 t=re.sub(r'    const-string v0, "PVZHover19".*?invoke-static \{v0, v1\}, Landroid/util/Log;->d\(Ljava/lang/String;Ljava/lang/String;\)I\n','',t,flags=re.S)
 t=t.replace('\n# instance fields','\n.field private mDesktopRightDown:Z\n\n# instance fields',1)
 p.write_text(t+right,encoding='utf8')
 subprocess.run(['java','-Xmx512m','-cp',cp,'RepairDex','encode',str(OUT/'smali'),str(OUT/'classes.dex')],check=True)
 e=ELFFile(BytesIO(b));idx,seg=[(i,s) for i,s in enumerate(e.iter_segments()) if s['p_type']=='PT_LOAD'][-1]
 assert seg['p_offset']+seg['p_filesz']==len(b)
 entry=seg['p_vaddr']+seg['p_filesz']
 compiler=Path('Y:/Android/Sdk/ndk/27.0.12077973/toolchains/llvm/prebuilt/windows-x86_64/bin/clang++.exe')
 flags=['--target=armv7a-linux-androideabi21','-marm','-Os','-fPIC','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-exceptions','-fno-rtti','-fno-unwind-tables','-fno-asynchronous-unwind-tables']
 obj=subprocess.run([str(compiler),*flags,'-c',str(ROOT/'src/desktop-input/shortcuts.cpp'),'-o','-'],stdout=subprocess.PIPE,check=True).stdout
 (OUT/'shortcuts.o').write_bytes(obj)
 (OUT/'flat.ld').write_text(f'ENTRY(desktopInput)\nSECTIONS {{ . = {entry}; .payload : {{ *(.text.entry) *(.text*) *(.rodata*) *(.data*) *(.got*) }} /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }} }}')
 payload=subprocess.run([str(compiler),*flags,'-nostdlib','-static','-no-pie','-Wl,--no-undefined','-Wl,-T,'+str(OUT/'flat.ld'),str(OUT/'shortcuts.o'),'-o','-'],stdout=subprocess.PIPE,check=True).stdout
 (OUT/'shortcuts.elf').write_bytes(payload);pe=ELFFile(BytesIO(payload));code=pe.get_section_by_name('.payload').data();assert pe['e_entry']==entry
 assert pe.get_section_by_name('.bss') is None
 b.extend(code)
 while len(b)%4:b.append(0)
 stub=seg['p_vaddr']+len(b)-seg['p_offset'];old=bytes(b[0x132b660:0x132b664]);branch=struct.unpack('<I',old)[0]&0xffffff
 if branch&0x800000:branch-=0x1000000
 previous=0x132b660+8+branch*4
 asm=f'''cmp r3,#6
 beq command
 cmp r3,#5
 beq hover
 b #{previous}
 command:
 mov r1,r5
 mov r2,r4
 mov r3,#6
 adr r0,basepoint
 ldr ip,baseoffset
 sub r0,r0,ip
 bl #{entry}
 b #0x132b688
 hover:
 mov r0,r5
 mov r1,r4
 bl #0x1327d0c
 ldr r0,[r5,#0x44]
 ldr r0,[r0,#0x6bc]
 cmp r0,#0
 beq done
 ldr r2,[r0,#0x2c]
 ldr r3,[r4,#8]
 sub r3,r3,r2
 str r3,[r4,#8]
 ldr r2,[r0,#0x30]
 ldr r3,[r4,#0xc]
 sub r3,r3,r2
 str r3,[r4,#0xc]
 mov r1,r5
 mov r2,r4
 mov r3,#5
 adr r0,basepoint
 ldr ip,baseoffset
 sub r0,r0,ip
 bl #{entry}
 ldr r0,[r5,#0x44]
 ldr r0,[r0,#0x6bc]
 cmp r0,#0
 beq done
 ldr r0,[r0,#0x94c]
 cmp r0,#0
 beq done
 ldrb r2,[r0,#0x1d]
 cmp r2,#0
 bne done
 add r1,r4,#8
 bl #0x1efccc
 done:
 b #0x132b688
 basepoint:
 nop
 baseoffset:
 .word 0'''
 bridge=bytearray(Ks(KS_ARCH_ARM,KS_MODE_ARM).asm(asm,addr=stub)[0]);struct.pack_into('<I',bridge,len(bridge)-4,stub+len(bridge)-8)
 b.extend(bridge);struct.pack_into('<I',b,0x132b660,0xea000000|(((stub-0x132b660-8)//4)&0xffffff))
 ph=e['e_phoff']+idx*e['e_phentsize'];added=len(b)-(seg['p_offset']+seg['p_filesz'])
 for p in [ph+16,ph+20]:struct.pack_into('<I',b,p,struct.unpack_from('<I',b,p)[0]+added)
 (OUT/'libSrc.so').write_bytes(b)
 replacements={'classes.dex':(OUT/'classes.dex').read_bytes(),'lib/armeabi/libSrc.so':b}
 with zipfile.ZipFile(OUT/'unsigned.apk','w',allowZip64=True) as dst:
  for item in src.infolist():
   if item.filename.startswith('META-INF/'):continue
   if item.filename in replacements:dst.writestr(item,replacements[item.filename])
   else:
    with src.open(item) as a,dst.open(item,'w') as z:shutil.copyfileobj(a,z,1024*1024)
 (ROOT/'docs/recovery/input-v22-build.json').write_text(json.dumps(dict(base=str(BASE),native_entry=hex(entry),stub=hex(stub),prior_stub=hex(previous),assembly=asm,device_verified=False),indent=2)+'\n')
 print('v22 native commands, keyboard/right button and hover collection packaged')
