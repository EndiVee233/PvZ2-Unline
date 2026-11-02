# 最新进度：v28 离线 NPC 练习候选，未运行验收

用户选择先恢复本地 NPC 战斗，沿用无需游戏验证。v28 将地图对战入口改为原生 arena_battle_attack_tutorial NPC 练习战场，绕过云同步/在线登录；使用固定僵尸卡，保留原生教学和战斗，结束或相关退出请求返回地图。不包含完整在线经营、军队训练和排行榜。

APK：`work/pvp-v28/PvZ2-v28-offline-npc-practice.apk`。
SHA256：`f6770a24872e08178c46c0e65a0985e4d641aee75fb4f6d8a773169800c0e776`。
构建已完成，未安装或运行 v28，进入/操作/胜负/返回完整链路待验收。详情：`docs/recovery/pvp-v28-result.md`。

---

# v27 合并植物奇遇转场修正并补齐幸运宝藏后续引导

用户补充完成第七天仍触发幸运宝藏引导，并要求无需验证。v27 跳过后续教程 ID 21/23，保留此前 15/18 跳过逻辑；抽屉模式 4/6/7 改为无引导模式，避免指向隐藏按钮的箭头和输入锁定。

APK：`work/treasure-v27/PvZ2-v27-trial-transition-lucky-guide-fix.apk`。
SHA256：`d84f7ef9bd8aa92c4ff5c34d18de709cdba0b03c9ff91ff29f0272c203e87325`。
继承 v26 植物奇遇转场修正。未安装或运行 v27，按用户要求不再游戏验证。覆盖安装后需重新启动，清除旧进程已经生成的引导。详情：`docs/recovery/treasure-v27-result.md`。

---

# v26 修正植物奇遇场景切换软锁，待完整通关验收

用户已确认 v25 软锁。只读检查实机发现当前场景 19、购买窗口指针为 0：v25 在场景已切换后才阻止窗口创建，遗漏通关自动推荐分支。

v26 在 0x353d28/0x354e9c 的关卡结束判断处走完整无推荐路径，跳过购买场景与专用回调；保留地图动作完成补丁，撤回晚期窗口拦截。正常地图目标为场景 7。

APK：`work/trial-v26/PvZ2-v26-trial-offer-transition-fix.apk`。
SHA256：`7ba9869bda759650ddcfbc4762023672498c2b5a46fe7fc7c34b23ec23726dcc`。
两条原生路由及状态生命周期隔离检查通过，完整重打关卡衔接待验收。详情：`docs/recovery/trial-v26-result.md`。

---

# v25 历史版本：用户已确认植物奇遇跳过后软锁

此前仅隐藏地图入口，仍有独立自动推荐流程。v25 将 ActionShowPlantTrial 标记完成并由原队列结束，另关闭推荐窗口的创建入口，避免等待不存在的关闭事件。保留试用植物关卡与 v24 修改。

APK：`work/trial-v25/PvZ2-v25-no-plant-trial-offer.apk`。
SHA256：`8f0155872072b16b54037da4bd23e08c18bd43203ee75e0f3ec885e1540bf817`。
原生动作队列隔离检查、签名及对齐检查通过；尚未游戏内验收。详情：`docs/recovery/trial-v25-result.md`。

---

# v24 幸运宝藏移除与离线植物探险候选，待游戏内验收

现有 v23 源码已推送，APK 已发布：https://github.com/EndiVee233/pvz2-lostcity-wsa/releases/tag/v1.7.5-v23 。

v24 移除幸运宝藏子入口及教程 ID 15，保留宝物菜单其他功能；植物探险复用原生本地派遣和奖励逻辑，专用计时改为设备时间，解除探险界面的联网可用性阻拦。

APK：`work/adventure-v24/PvZ2-v24-offline-adventure-no-lucky-treasure.apk`。
SHA256：`3dbc4d5abb2d8a39942d40a28b1b60f14fb632b4d7f68797e49f3bc936e83d5d`。
隔离 ARM 检查、签名、对齐及载荷范围检查通过。未安装、运行 v24，未改用户存档。完整派遣、领奖及界面衔接待实机验收。详情：`docs/recovery/adventure-v24-result.md`。

---

# v23 修正按 1 崩溃及空格绕过教程暂停，待实机验收

用户报告 v22 按 1 崩溃，教程对话时空格仍可暂停；其它功能未完成验收。日志确认原生类型判定返回 bool 被当作指针，v23 改为判定成功后保留原对象；空格改走 UIPauseButton 的原按下/释放输入路径，不再直接暂停。
APK：`work/input-v23/PvZ2-v23-shortcut-crash-pause-fix.apk`。
SHA256：`ba8bf7aa978b83b6a0b9ec5959da9fb9c0bcdc5fdba4564a9698e43c71604bfc`。
隔离检查已使用布尔返回值 1，签名及对齐通过；仅 libSrc.so 相对 v22 改变。未安装或运行 v23。详情：`docs/recovery/input-v23-result.md`。

---

# v22 历史候选：用户已确认快捷键崩溃与教程暂停限制失效

APK：`work/input-v22/PvZ2-v22-keyboard-hover-collect.apk`。
SHA256：`a534079f9822d98d554325f659397d376bee1e0e37f4c24fddd245382208c5fa`。
新增 1–4/QWER 卡槽、F 能量豆、D 铲子、空格暂停/继续、V 加速、M 黄瓜、A 一次收集、右键取消等待选择；鼠标划过收集物调用原有命中与收集逻辑。原控件和关卡可用性判断保留，试用卡不映射。
隔离 ARM 检查、签名、对齐、载荷范围检查通过，未安装或运行 v22，未改用户存档。完整键鼠效果不能标为已验证。详情：`docs/recovery/input-v22-result.md`。分支沿用 `codex/mouse-v18`。

---

# v21 鼠标跟随十字种植提示候选

新增等待选择的原生种植提示绘制迭代，保留 v20 坐标修正与既有改动。APK：`work/mouse-v21/PvZ2-v21-hover-planting-cross.apk`。隔离 ARM 检查通过，未做游戏内验收。详情：`docs/recovery/mouse-v21-result.md`。

---

# 最新进度：v20 修复悬停预览战场原点偏移，待验收

v19 用户确认开始跟随但偏移。v20 在悬停坐标转换中补减 Board 原点，保留原缩放和正常拖动。APK：`work/mouse-v20/PvZ2-v20-hover-board-coordinates.apk`。隔离 ARM 坐标检查通过，未做游戏内验收。详情：`docs/recovery/mouse-v20-result.md`。

---

# 最新进度：v19 已定位 WSA 悬停来源过滤错误

WSA 实际发送 source=0x1002 的 ACTION_HOVER_MOVE，v18 仅接受 0x2002，导致丢弃。v19 已放宽为 pointer 类并补充通用移动分发，已覆盖安装成功，日志确认坐标持续变化，游戏内跟随待用户确认。APK：`work/mouse-v19/PvZ2-v19-pointer-hover-diagnostic.apk`。详情：`docs/recovery/mouse-v19-result.md`。

---

# 最新进度：v18 原生等待光标跟随候选，等待用户验收

用户已反馈 v17 鼠标跟随失败。继续反编译发现：单击释放后光标从活动列表移入 Board+0x94c，绑定编号归零，因此旧移动回调既不能更新它，也没有绘制它。

v18 同时补上等待光标的位置更新、每帧更新和预览绘制，保留下一次点击的原始使用逻辑。APK：`work/mouse-v18/PvZ2-v18-pending-cursor-follow.apk`。
SHA256：`a631bac08fccdaea2bab483a780a7ce79b2d10b6a8abc863e59cea63db656da3`。
仅 libSrc.so 改变，v17 后台解码、商店、既有抽奖和教程修复保留。隔离 ARM 控制流检查、签名及对齐通过，未启动 WSA，未改用户存档，不能标记游戏内验收通过。
详情：`docs/recovery/mouse-v18-result.md`。源码分支：`codex/mouse-v18`。

---

# v17 历史候选：鼠标跟随已被用户确认失败

最终包：`work/desktop-v17/PvZ2-v17-background-cache-mouse-hover.apk`。
SHA256：`8f9bbc4b822cf7ee855a0a3f846f6ed6da4b2b0c8ec1ffaaa65406397aa15114`。
基于v16r10：2–4条常驻解码线程，754张ASTC图集后台预缓存，加载请求优先；商店文案“获得X 金币/钻石”，隐藏手续费说明但保留原扣费；鼠标悬停经Java事件队列和原生phase5移动回调，尝试支持选中植物、能量豆、铲子后跟随鼠标。
按用户要求未安装或运行WSA，未进行游戏/鼠标/性能验证。不得称v17已验收。上轮v16r10的实测结论保留在下方。
源码分支：`codex/desktop-v17`。详情和复现步骤：`docs/recovery/desktop-v17-result.md`；构建记录：`docs/recovery/desktop-v17-build.json`。

---

# 最新进度：v16r10 已修复启动并完成 WSA 双向兑换自测

最终包：`work/launch-fix/PvZ2-v16r10-currency-exchange.apk`。
SHA256：`53d7806ab8fa7a81596f7ed5b9572eeede5876e0c10ad3838bc2caaca16ed338`。
原 v16 的 DEX 字符串排序错误导致无法启动，现通过重新组装修复。
WSA 完整覆盖安装后，进入地图/商店、20000金币换18钻石、10钻石换9000金币、余额不足不扣款均通过；强制结束并重启后153钻石/16570金币保持一致。
用户原有存档已在测试前备份，测试结束恢复到原有195钻石/2570金币，已在最终地图画面核对一致。
v15 抽奖与教程修复保留；本轮未重新打关验证。源码在 codex/fix-exchange-startup 分支。旧 v16 与 r2–r9 不可交付。
详情：`docs/recovery/exchange-v16-result.md`，设备记录：`docs/recovery/exchange-v16-device-validation.json`。

---
用户最新验收：v15 教程软锁修复成功，通关抽奖修复成功。用户已授权将两项修复上传 GitHub。

# 当前进度更新 — v15（2026-11-01）

用户实测：v14 通关抽奖修复成功；教程软锁仍存在。复现：埃及第2关通关 → 完成图鉴教程 → 返回地图出现指向已删除“60倍返还”的箭头并锁住输入。

最新候选包：`work/tutorial-v15/PvZ2-v15-skip-return-guide.apk`。
SHA256：`c2e83e2c80e75b6c18672739285b8b8b1e7a9085e1a9ce983f6578578cf575e9`。
与 v14 同签名，可覆盖安装；本轮未安装、卸载或修改设备存档。需完全结束游戏进程后冷启动，由用户验证原软锁存档及新触发路径。

新方向：v14 只改了 `0x9f4080` 的引导退出/完成路径。引导建立入口 `0x9fcdc8` 先在 `0x9fce2c` 查询 `0x709808(profile,id)`，若未完成，则在 `0x9fce5c` 写入 map+0x29c，引导18会跳到 `0x9fe048` 创建箭头并配置按钮。`0x9fce34` 的已完成分支在这些写入之前直接返回。这解释了旧补丁无法预防箭头与输入锁定的建立。

v15 在 `0x709808` 入口增加仅针对 id=18 的完成查询短路（返回1）。其余 id 执行原始被覆盖的 `str fp,[sp,#-4]!` 后跳回原函数+4。新代码追加到已有末尾可执行 PT_LOAD，从虚拟地址 `0x1a000a8`、文件偏移 `0x18300a8` 起20字节；该段 filesz/memsz 从168扩到188，不改已有追加补丁或其他段。没有使用不明用途的零填充空间。

512 组差分检查覆盖 id=-1..30、4种顺序教程进度和4种已完成列表，除18外返回值完全相同；栈及被调用方保存寄存器一致。额外运行真实入口 `0x9fce24` → 查询 → `0x9fce38`，确认不写 map+0x29c。签名v1/v2/v3、zipalign、ZIP CRC、全载荷哈希核对通过；相对v14仅libSrc.so改变，已实测成功的抽奖Hook库保持逐字节一致。

本轮只得到静态/有界仿真证据，尚未实机验收。已有箭头是内存状态，覆盖安装后需冷启动再验证；若仍失败，应采集具体存档和实际教程id/调用链，不应继续把有界仿真通过等同于软锁解除。

复现：`python scripts/build_tutorial_v15.py`，`python scripts/validate_tutorial_v15.py`，使用保留密钥 `work/keys/recovered-debug.keystore` 签名，然后 `python scripts/verify_tutorial_v15_apk.py`。
验证记录：`docs/recovery/tutorial-v15-{patches,validation,build}.json`。

以下为v14历史检查点，未验收表述已由上述用户反馈更新。

---

# 恢复检查点 — 2026-11-01

## 当前交付

`work/restored-v14/PvZ2-v14-restored-lottery-tutorial.apk`

SHA256: `5b610a5ecba26fddb7b13ec76561c8afb2731f755764f406a7ce1025cf34c1e8`

这是本次核对后重建的合并候选版，尚未实机验收。不要把其他文件名里的 v12/v13 当成同一产物。

## 核对结果与历史冲突

- 先前聊天交付的 `work/PvZ2-v13-no-victory-lottery.apk` 已不在目录中，相关早期补丁脚本也不在。
- 磁盘有 `PvZ2-reconstruction-multiuser-v13-nolottery.apk` 和 `work/v13-nolottery-summary.md`，但其胜利分支与先前聊天版方向相反；不能视作原交付的无损恢复。
- 教程的有效进度在 `work/v12-patch-summary.md`：地图教程第 18 步的 `0x9f4080` 分支转为无条件跳转。已重新反汇编核对，目标为原有完成、记录和清理路径。部分旧脚本/`FIX_SUMMARY.md` 建议删预装存档或禁用全部教程，这些并非本次方案，不能作为有效修复证据。
- 从原始 v11 的 APK 与两个库 SHA256 重新核对基线，不沿用任何存档清空或 apktool 重编译产物。

## v14 明确修改

1. `libSrc.so 0x9970b8`: `000094e5` → `fbffffea`，恢复聊天交付版的分支，转到 `0x9970ac` 调用原流程 `0x9967a0`。这只是恢复已有候选补丁，不宣称全局通关链路已由实机验证。
2. `libHookPVZ2.so 0x6afc`: `07f0d8f8` → `00bf00bf`，移除 `0x993578` 的强制 CardPlay 接管。
3. `libHookPVZ2.so 0x6c02`: `07f055f8` → `00bf00bf`，同时移除配套拦截 `0x3fe358` 的接管，保留原关闭处理。此项为配套恢复。
4. `libSrc.so 0x9f4080`: `8a01000a` → `8a0100ea`，第 18 号引导跳过已删除的“60倍返还”按钮。`0x9f46b0` 路径执行清理、记录第18步完成、清空界面标志并切换到后续引导状态4。其他教程保留。

其他 APK 载荷逐项 SHA256 一致，只有两个库发生以上改动；游戏资源、存档、Manifest 和 DEX 未改。本轮未连接设备、安装、卸载或修改用户存档。

## 验证边界

- 24 项有界 ARM/Thumb 检查通过：教程控件存在/不存在时均执行原完成路径，完成记录参数为18、后续状态为4、界面标志归零；恢复后的胜利分支与两处 Hook 注册 NOP 核对通过。
- 教程检查中的外部函数为受控边界，不能代替真实存档/地图输入验收。
- 全 APK ZIP CRC、非目标条目内容、两个库哈希、zipalign、v1/v2/v3 签名验证通过。
- 仍需用户验证：冷启动已卡住的存档，地图不再等待不存在按钮；关卡通关捡钱袋后不显示四卡抽奖，返回地图，进度与收益保存。

## 签名

找回并保留 `work/keys/recovered-debug.keystore`，证书 SHA256：
`1e08a903aef9c3a721510b64ec764d01d3d094eb954161b62544ea8f187b5953`。
与当前磁盘 `PvZ2-reconstruction-multiuser-v13-nolottery.apk` 同证书。更早聊天版使用的 `CN=PvZ2 Local Patch` 私钥已不在现有目录；不能保证覆盖该签名的安装。不要为解决签名冲突直接卸载用户旧版。

## 复现与续接

在仓库根目录执行：

```powershell
python scripts/build_restored_v14.py
python scripts/validate_restored_v14.py
```

随后将 `work/restored-v14/unsigned.apk` 用 `K:/pvz2-tools/android-build-tools/android-14/zipalign.exe` 对齐，用同目录 `lib/apksigner.jar` 和保留密钥签名，输出上面的 v14 文件名，再执行：

```powershell
python scripts/verify_restored_v14_apk.py
```

验证记录：`docs/recovery/restored-v14-{patches,validation,build}.json`。

下一步等待用户对这一个明确文件的实机反馈。若抽奖仍出现，应在真实运行路径中继续定位 `0x9967a0` 以及其他开窗调用，不应再次仅用分支仿真宣称行为修复。



