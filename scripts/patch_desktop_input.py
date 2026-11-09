"""Extend the established Android desktop-command queue."""

MANAGER = 'Lcom/popcap/SexyAppFramework/AndroidUIEventManager;'
SURFACE = 'Lcom/popcap/SexyAppFramework/AndroidSurfaceView;'
TRACKER = 'Lcom/popcap/SexyAppFramework/AndroidUIEventManager$UITouchTracker;'
MOTION = 'Landroid/view/MotionEvent;'


def patch_desktop_input(smali):
    manager = smali / 'com/popcap/SexyAppFramework/AndroidUIEventManager.smali'
    text = manager.read_text(encoding='utf8')
    key = '        0x33 -> :sswitch_9'
    assert text.count(key) == 1
    text = text.replace(key, key + '\n        0x34 -> :sswitch_9\n        0x36 -> :sswitch_9')
    start = text.index('.method public QueueDesktopCommand(I)V')
    end = text.index('.end method', start)
    command = text[start:end]
    command = command.replace('QueueDesktopCommand(I)V\n    .registers 7',
                              'QueueDesktopCommand(IFF)V\n    .registers 9')
    # Middle-click has the actual pointer position. Keyboard events continue
    # to use the most recent hover, as they did before.
    point = f'    iget-object v2, p0, {MANAGER}->mMouseHoverTracker:{TRACKER}'
    assert command.count(point) == 1
    command = command.replace(point, f'''
    const/16 v2, 0x65
    if-ne p1, v2, :desktop_hover
    iput p2, v0, {TRACKER}->previousX:F
    iput p3, v0, {TRACKER}->previousY:F
    goto :cond_2a
    :desktop_hover
{point}''')
    wrapper = f'''.method public QueueDesktopCommand(I)V
    .locals 1
    const/4 v0, 0x0
    invoke-virtual {{p0,p1,v0,v0}}, {MANAGER}->QueueDesktopCommand(IFF)V
    return-void
.end method

'''
    manager.write_text(text[:start] + wrapper + command + text[end:], encoding='utf8')

    surface = smali / 'com/popcap/SexyAppFramework/AndroidSurfaceView.smali'
    text = surface.read_text(encoding='utf8')
    field = '.field private mDesktopRightDown:Z'
    assert text.count(field) == 1
    text = text.replace(field, field + '\n.field private mDesktopMiddleDown:Z')
    for name in ('dispatchTouchEvent', 'dispatchGenericMotionEvent'):
        start = text.index(f'.method public {name}({MOTION})Z')
        entry = text.index(f'    invoke-virtual {{p0, p1}}, {SURFACE}->HandleDesktopRight', start)
        text = text[:entry] + f'''
    invoke-direct {{p0,p1}}, {SURFACE}->handleDesktopMiddle({MOTION})Z
    move-result v0
    if-eqz v0, :desktop_other_buttons
    return v0
    :desktop_other_buttons
''' + text[entry:]
    text += f'''
.method private handleDesktopMiddle({MOTION})Z
    .locals 4
    invoke-virtual {{p1}}, {MOTION}->getButtonState()I
    move-result v0
    and-int/lit8 v0,v0,0x4
    if-nez v0,:held
    iget-boolean v0,p0,{SURFACE}->mDesktopMiddleDown:Z
    if-eqz v0,:done
    const/4 v1,0x0
    iput-boolean v1,p0,{SURFACE}->mDesktopMiddleDown:Z
    return v0
    :held
    iget-boolean v0,p0,{SURFACE}->mDesktopMiddleDown:Z
    if-nez v0,:handled
    const/4 v0,0x1
    iput-boolean v0,p0,{SURFACE}->mDesktopMiddleDown:Z
    iget-object v0,p0,{SURFACE}->mUIEventManager:{MANAGER}
    const/16 v1,0x65
    invoke-virtual {{p1}}, {MOTION}->getX()F
    move-result v2
    invoke-virtual {{p1}}, {MOTION}->getY()F
    move-result v3
    invoke-virtual {{v0,v1,v2,v3}}, {MANAGER}->QueueDesktopCommand(IFF)V
    :handled
    const/4 v0,0x1
    :done
    return v0
.end method
'''
    surface.write_text(text, encoding='utf8')
