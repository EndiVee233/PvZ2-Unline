# v18：等待点击状态的原生光标预览

用户反馈 v17 鼠标跟随失败，仍需长按。v18 为新的验收候选，尚未获得游戏内成功结论。

APK：`work/mouse-v18/PvZ2-v18-pending-cursor-follow.apk`

SHA256：`a631bac08fccdaea2bab483a780a7ce79b2d10b6a8abc863e59cea63db656da3`

## 继续反编译的结果

使用 Ghidra 11.3.2、JDK 21 和 ARM 反汇编继续分析 libSrc.so。Ghidra 导入时映像偏移为 0x10000；下列地址均已还原为 ELF 原始虚拟地址，不可直接使用 Ghidra 输出的函数名作补丁地址。

- `BaseCursor::HandleTouch`，0x1ef560：cursor+0x24 是绑定的触摸编号。编号为零时只接受按下，普通移动在编号比较处被忽略。
- 0x1efe24：原按键释放后的保留选择路径调用 Board 的 0x224204。
- `Board::RetainCursor`，0x224204：从 Board+0x940 的活动列表移走光标，写入 Board+0x94c，并清零 cursor+0x24。原生输入监听优先级改为 7，等待下一次按下。
- 0x216600：下一次按下重新绑定编号，把 Board+0x94c 移回活动列表，并置 cursor+0x1e。此原始路径保留。
- `BaseCursor::SetPosition`，0x1efccc：仅更新 cursor+4/+8，使用应用+0x690 的比例转换，不改变原始点击矩形、绑定编号、选择状态，不触发使用。
- 0x207614：Board 光标绘制函数只遍历活动列表，没有遍历等待光标。仅补发移动事件不足以显示预览。
- 0x20f4f8：每帧活动光标更新调用 0x1ef90c；等待光标同样缺少此更新。
- PlantfoodCursor 和 ShovelCursor 的释放处理分别位于 0x4e8adc、0x8e9c74；它们保留“点击原位置保留选择，点击场地使用”的逻辑。

反编译工作文件、Ghidra 项目及原始伪 C 输出保留于 `work/mouse-v18`。原始伪 C 含有未分析边界和类型，以上结论同时核对 ARM 指令，未将错误边界的输出作为补丁依据。

## 修改

复用 v17 的 Java 悬停事件 phase=5，重写原生分支：先做原有坐标转换，读取当前 Board+0x94c，经过空指针和 finished 检查后调用 0x1efccc。悬停不会调用放置、使用、释放或触摸绑定函数。

绘制函数额外保留八字节对齐栈空间，保存等待光标槽的地址。在原活动循环结束后，用原有坐标转换、绘图状态保护和 0x1ef9b4 绘制逻辑额外执行一次等待光标迭代。局部结束标志防止循环重复，不改活动列表。每帧更新额外调用等待光标的 0x1ef90c，避免把动画更新频率绑定到鼠标消息。

只替换 v17 的 libSrc.so。DEX、后台解码兼容库、商店及前期抽奖/教程修改全部沿用 v17。使用原签名，支持覆盖安装。

## 检查与限制

`scripts/check_mouse_v18_native.py` 的隔离 ARM 执行检查通过：等待光标分发、空/已结束光标保护、普通 phase0–4 原路径、额外绘制仅执行一次。APK v1/v2/v3 签名及四字节对齐检查通过；包内非签名载荷仅 libSrc.so 改变。

按前次用户要求未启动 WSA、未安装或修改用户存档。隔离检查不能证明 WSA 会投递悬停事件，也不能替代植物、能量豆、铲子的实机验收。验收方式：单击选择后松开，移动鼠标观察预览，再单击目标位置，确认只使用一次；另外确认长按拖动仍可用。

重建：`python scripts/build_mouse_v18.py`，再使用同目录工具 zipalign、apksigner 和保留的 recovered-debug.keystore 签名。详细补丁和哈希见 `mouse-v18-build.json`。
