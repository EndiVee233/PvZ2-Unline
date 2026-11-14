# v170：完整引擎重编译后的JNI桥接地址同步

用户报告v169进入游戏立即闪退，规则验收未开始。范围3×3、4×3、4×4、5×4，以及进攻费每日零点重置，均已得到明确确认。

## 故障证据

2026-11-14 13:11:59，Aster GLThread 37被Houdini终止。ARM原始PC是不可执行的`[anon:stack_and_tls:4577]`地址`b1759468`，LR位于`libPresetEditor.so`的`Java_com_popcap_pvz2cthd_PresetEditor_command+208`。主线程不是日志里早先出现的旧支付SDK后台异常。

v169完整重编译了libSrc.so，命令、轮询和音乐采样函数都移动了；复用v168的libPresetEditor.so却保留了旧preset_bridge_addresses.h中的地址。首次PresetEditor.frame发送网络设置命令时进入错误函数位置，最终跳入栈。之前的358个玩法模拟检查直接调用引擎，没有执行这个跨库边界，因此没有发现打包错配。

## 修改

- `build_aster_preset_bridge.py`从同一份offline.elf提取三个入口，先逐字节验证ELF负载确实属于待打包引擎，再编译JNI桥。
- 每次完整构建，包括`--compile-only`，都生成配套桥并执行JNI集成检查。
- 打包必须提供桥库；引擎SHA256、桥SHA256、集成检查记录必须匹配，否则拒绝打包。
- ARM32同时替换libSrc.so和libPresetEditor.so；ARM64同步替换两个ARM32客体库，ARM64宿主桥不变，不安装或运行ARM64。
- v170玩法引擎与v169逐字节相同，保留358场景及64路径、30预览/音乐、20玩家记忆检查所针对的原引擎；本次修正桥接配对，manifest升到v170。所有资源和Java继续沿用v168。

新增集成检查加载真实JNI桥和真实ARM引擎，在两个ASLR基址执行首次网络设置、共享阵型空目录导入、长度上限拒绝、每帧轮询与音乐采样，共12个场景；JNI数组与Android日志是边界替身。另以v168旧桥作为负例，确认会被识别为过期地址。栈不具备执行权限，不允许模拟环境掩盖跳入栈的问题。

## 存档与验收状态

v169批次已结束，20261114-123445-865750-before-test的58个文件回档并逐一验证通过，保留此前实际游玩基线。v170新备份为20261114-132144-208179-before-test，58文件校验成功。构建/集成检查不等同于WSA启动成功；需先完成ARM32启动检查，再交给用户继续原规则验收。

ARM32已通过实际启动检查：versionCode1170、armeabi，主进程4725在10/25/40秒持续存活；截图确认为WSA USER开始界面，日志记录Last player restored，无本次启动的致命错误。首次默认增量安装因WSA Shared temp file not found失败，改用--no-incremental完整安装后成功；没有禁用安装校验、卸载或清空数据。ARM64两份客体库与ARM32相同，仅构建和签名校验，未运行。PVP玩法仍待用户继续验收，保持当前菜单和58文件备份现场。
