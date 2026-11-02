# v29：修正 v27 升级 v28 的资源版本阻拦

用户反馈 v28 停在资源解压画面，提示“资源更新失败”，重启无效。

只读 ADB 日志确认 PvZ2Bootstrap 在 BootActivity.applyOriginalSpeedResource 抛出 `IOException: Unexpected resource version`。已安装资源 dynamic.rsb.smf 的 SHA256 为 f835e0f3fe60466dbf81a71c4850f2eb086390103c70709f15991b474657219c，与 v27 APK 内资源一致。

v28 把目标更新为 cd4626cfc3afe0148962b14564c4bd27f185063c4d1bf9dd4a8c7d705d303bf5，却仍仅接受旧 BASE_RESOURCE_SHA=0aae11cf…，没有接受 v27 的 f835e0f3…；因此启动器在拷贝前拒绝合法旧资源。这是构建脚本的升级兼容遗漏，与存档、WSA 解压空间或游戏战斗代码无关。

v29 给启动器新增明确的资源前置版本列表，接受 v27、早期原速资源及初始资源的完整散列。未知文件仍被拒绝；临时文件完整 SHA256 校验、同步写盘和替换流程保留。更新标记改为 .offline-npc-v29，使旧标记不跳过本次检查。

APK：`work/bootstrap-v29/PvZ2-v29-resource-upgrade-fix.apk`

SHA256：`9eff94ac5c90f04c1201cae480bab281179aff23c957ad9d3d95b5a152894a2d`

相对 v28 仅 classes8.dex 改变，对战候选的原生代码、关卡资源及其它修复保持一致。DEX 用原工具完整重组，完成对齐和签名。未安装或运行 v29，沿用用户无需游戏验证的要求；启动和 NPC 战斗仍需用户验收。

请直接覆盖安装，无需卸载或清理资源/存档。构建脚本 scripts/build_bootstrap_v29.py；记录 bootstrap-v29-build.json。此次只读取设备日志和资源散列，没有操作设备文件。
