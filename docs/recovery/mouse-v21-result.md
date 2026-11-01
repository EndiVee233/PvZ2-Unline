# v21：鼠标悬停选择的十字种植提示

用户反馈 v20 跟随位置已改善，鼠标松开跟随时缺少长按拖动时的十字提示。继续反编译 Board 的提示绘制函数 0x2096a0（Ghidra 映像偏移 +0x10000，因此伪 C 名为 0x2196a0）：只遍历 Board+0x940/+0x944 活动光标，不包含 Board+0x94c 的等待选择。PacketCursor 分支沿用虚函数判断来源矩形、可用格子，并由原函数计算格子、绘制提示。

v21 在此函数统一退出处 0x209894 接入等待光标一次迭代，回到原局部变量初始化入口 0x2096c4 后执行原有判断和绘制。用遍历地址 slot+4 防止重复，跳过空与 finished 光标，不改活动列表、不绑定触点、不触发种植。v20 悬停坐标转换及 v19 WSA 来源兼容均保留。

APK：work/mouse-v21/PvZ2-v21-hover-planting-cross.apk
构建：scripts/build_mouse_v21.py，然后 zipalign、原 recovered-debug 密钥签名。
检查：scripts/check_mouse_v21_native.py 隔离 ARM 的空/结束选择、仅额外一次迭代和原栈退出检查通过。未安装 WSA，实际十字提示由用户验收。只替换 libSrc.so，候选不得标记实机成功。
