from pathlib import Path
import sys,zipfile,shutil,hashlib,json,os
sys.path.insert(0,'scripts')
import build_desktop_hover as h
out=Path('work/mouse-v19');out.mkdir(exist_ok=True)
os.environ['TMP']=os.environ['TEMP']=str(Path('work/tmp').resolve())
h.SURFACE=h.SURFACE.replace('const/16 v1, 0x2002','const/4 v1, 0x2')
h.SURFACE+='''
.method public dispatchGenericMotionEvent(Landroid/view/MotionEvent;)Z
    .locals 3
    invoke-virtual {p1}, Landroid/view/MotionEvent;->getActionMasked()I
    move-result v0
    const/4 v1, 0x7
    if-eq v0, v1, :hover
    const/16 v1, 0x9
    if-ne v0, v1, :fallback
    :hover
    const-string v0, "PVZHover19"
    invoke-virtual {p1}, Landroid/view/MotionEvent;->toString()Ljava/lang/String;
    move-result-object v1
    invoke-static {v0, v1}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I
    invoke-virtual {p0, p1}, Lcom/popcap/SexyAppFramework/AndroidSurfaceView;->onHoverEvent(Landroid/view/MotionEvent;)Z
    move-result v0
    if-nez v0, :done
    :fallback
    invoke-super {p0, p1}, Landroid/opengl/GLSurfaceView;->dispatchGenericMotionEvent(Landroid/view/MotionEvent;)Z
    move-result v0
    :done
    return v0
.end method
'''
with zipfile.ZipFile('work/launch-fix/PvZ2-v16r10-currency-exchange.apk') as z:
 dex=h.rebuild_mouse_dex(z.read('classes.dex'),out/'input-dex',Path('tools/apktool.jar').resolve())
with zipfile.ZipFile('work/mouse-v18/PvZ2-v18-pending-cursor-follow.apk') as src,zipfile.ZipFile(out/'unsigned.apk','w',allowZip64=True) as dst:
 for item in src.infolist():
  if item.filename.startswith('META-INF/'):continue
  if item.filename=='classes.dex':dst.writestr(item,dex)
  else:
   with src.open(item) as a,dst.open(item,'w') as b:shutil.copyfileobj(a,b,1024*1024)
print('v19 dex built: pointer-class hover and direct generic dispatch')
