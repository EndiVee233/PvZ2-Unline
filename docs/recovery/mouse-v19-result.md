# v19 输入诊断候选

用户反馈 v18 能绘制选择预览，但只停留在单击处。不能视为鼠标跟随成功。

实际 WSA `dumpsys input` 只有 virtual_touchscreen（TOUCHSCREEN | STYLUS）、virtual_keyboard，没有注册 MOUSE 输入设备。用户按要求无按键移动约 10 秒期间，`adb shell getevent -lt` 记录为零字节（work/mouse-v18/hover-input-trace.txt）。这仅是底层输入证据，不排除 WSA 在更高层注入事件，不能宣称已证明 WSA 无法支持。

v17/v18 Java onHoverEvent 使用 SOURCE_MOUSE=0x2002 过滤，会排除 STYLUS 悬停。v19 改为 SOURCE_CLASS_POINTER=2，接受触笔与鼠标；同时 override dispatchGenericMotionEvent，直接将 HOVER_ENTER/HOVER_MOVE 转发给已有悬停处理，避免默认视图分发路径影响。仍不伪造按下或释放。临时诊断标签 PVZHover19 记录到达 Surface 的悬停事件及坐标，可用 adb logcat -d -s PVZHover19:D 检查。

APK：work/mouse-v19/PvZ2-v19-pointer-hover-diagnostic.apk
SHA256：b5332051e63e11691471268b2904a901857352c9c2508d45a78e8c36e18e9b44
仅 classes.dex 相对 v18 改变；v18 原生预览与此前成果保留。重建 scripts/build_mouse_v19.py，然后原工具 zipalign 与原密钥 apksigner。此版本是诊断候选，不代表已修复。
