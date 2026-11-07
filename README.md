> **基于《植物大战僵尸2》中文版 1.7.5（失落之城，包名 `com.popcap.pvz2cthd`）制作。**
> 启动器/资源方案来自 [DreamMoonCai/Pvz2Tool](https://github.com/DreamMoonCai/Pvz2Tool)；
> ASTC 解码基于 [google/astc-codec](https://github.com/google/astc-codec)。

一个面向 Windows Subsystem for Android / 普通 Android 的单文件直装版

离线改造及 PVP 恢复进度见 [恢复记录](docs/recovery/README.md)。PVP 仍在逐项恢复；各版记录区分用户验收结果和仅通过模型检查的候选改动。

已发布阶段版为 **v97（2026-11-06）**：已恢复本地邻居攻防、商铺占领/调整阵型/产出/收租、货币与训练/研究/升级、兑换商店及本地战报摘要。新增多样邻居和特殊对手、更换对手、地区解锁，并修复首次布阵教程带入旧阵容及退出崩溃。v97尚未包含NPC自动反击、防守结算、回放和复仇；具体分项验收与待办见[当前进度](docs/recovery/README.md)。

本地最新分项验收为 **v99（2026-11-07，尚未上传）**：按用户指定规则恢复静默NPC袭击、钱包损失、商铺失守与夺回、失败战报复仇侦察及重启去重。本轮已获用户确认并回档校验；概率频率、实际复仇开战和战斗回放的验证边界见[v99记录](docs/recovery/pvp-v99-result.md)。下载页仍为已发布的v97。

## 特性

- **程序名**：植物大战僵尸2
- **单文件直装**：资源以分卷形式内置在 APK 中 首次启动自动解压
- **尝试跳过“服务器通讯中”**：`AndroidHttpProxy.GetNetworkStatus()` 固定返回 `0`
- **WSA 纹理兼容层**：`libRestart.so` 作为 GL shim
  - RGBA4444 → RGBA8888
  - ETC1 → RGBA8888
  - ASTC 4x4/5x5/6x6 等 → RGBA8888
  - **全分辨率**解码：常驻 2～4 个工作线程，空闲时预解码并缓存，未就绪资源加入同一线程池处理
- **无启动器入口**：启动器杂七杂八的东西我会好奇的乱点...然后就控制不住的开始作弊了 所以干脆不要启动器了

## 下载安装

已验收的离线 PVP 阶段版见 [v97 发布页](https://github.com/EndiVee233/PvZ2-Unline/releases/tag/v1.7.5-v97)，本轮验证范围见 [v97 记录](docs/recovery/pvp-v97-result.md)。

到 [Releases](../../releases) 下载 `PvZ2-v97-pvp-scene-candidate.apk`：

```bat
adb install -r PvZ2-v97-pvp-scene-candidate.apk
```

首次启动会请求存储权限，请允许；否则无法写入 `Android/data`。

WSA 建议把 **设置 → 高级设置 → 窗口焦点** 改为 **独立**，否则切到 Windows窗口时游戏会被挂起

## 为什么第一次加载比较慢？

WSA 的 GLES 实现不支持游戏使用的
ASTC/ETC1/RGBA4444 纹理需要由 libRestart.so 解码成 RGBA8888，再由 GL 线程上传。若资源尚未预解码完成，首次加载仍需等待对应任务。

- 一张 4096×4096 ASTC 单线程在 Houdini（ARM32 翻译）下约 4–6 秒
- 游戏启动会依次上传几十张大纹理 所以会出现“宣传图停留很久 → 开场动画 → 又加载”
- 等纹理全部解码完就会进入游戏

本版做了两项**不损失画质**的优化：

1. **常驻线程池与预解码**：预留 2～4 个工作线程；空闲时持续解码资源并准备缓存。用户加载尚未完成的资源时，同一线程池参与处理；大纹理按块边界拆分。
2. **解码缓存**：解码后的 RGBA 写入内部缓存
   第二次启动优先读应用内部缓存，减少重复解码。

因此：**第一次启动**仍需解码全部纹理 可能 1–2 分钟 **之后启动**会快很多

## 构建

源码在 `src/`：

- `src/boot/BootActivity.java`：首次解压 Activity（进度条 EA logo PVZ 字体）
- `src/boot/build_single.py`：把资源分卷 字体 logo `classes8.dex` 打进 APK
- `src/glshim/`：GL shim（C++ / CMake）
- `src/tools/`：AXML/ARSC 字符串补丁脚本

大概流程：

1. 用 `apktool`/自定义脚本把 `AndroidManifest.xml` 的 MAIN 改成 `BootActivity`；
2. 用 `patch_arsc_label.py` 改 `app_label` 为“植物大战僵尸2”；
3. 编译 `BootActivity` → `classes8.dex`（d8/R8）；
4. 用 `build_single.py` 移除原启动器资源 加入 `assets/pvz2data.zip.00x` 字体 EA logo；
5. `zipalign -p 4` + `apksigner` 签名

## Java 源码恢复进展

`src/recovered/` 保存了从本地取得的中文版 1.7.5 APK 恢复出的维护用源码快照：85 个 Java 文件生成 169 个类，其中包括启动入口和主 DEX 的 84 个 `com.popcap` Java 文件。WSA 中已验证独立离线包可进入神秘埃及第 1 天教程，本地玩家资料可在冷启动后保留；详细范围和限制见 [`src/recovered/report.md`](src/recovered/report.md)。

这不是完整游戏源码工程：大部分第三方托管代码仍是 Smali，C++ 游戏核心仍依赖原始 `.so`，完整战役和联网功能未验证。为避免分发游戏内容，仓库不包含 APK、游戏资源、原生库或签名密钥。请先阅读 [`NOTICE.md`](NOTICE.md)。

## 签名

- 证书：`CN=PvZ2 Patched`
- 升级必须使用同一签名 否则需要卸载重装

 ## 已知问题

- 首次启动解压约 2.6 GB 低配设备可能需要几分钟 请保持窗口在前台
- WSA 的 `Android/data` 目录如果被反复手动恢复/覆盖 可能出现 project id 损坏 表现为解压 `EACCES` 删除该目录后重启应用即可 必要时用 root 
  ```sh
  magiskpolicy --live "allow magisk media_rw_data_file dir { * }"
  rm -rf /data/media/0/Android/data/com.popcap.pvz2cthd
  ```

## 致谢

- [DreamMoonCai/Pvz2Tool](https://github.com/DreamMoonCai/Pvz2Tool)：启动器与资源处理思路
- [google/astc-codec](https://github.com/google/astc-codec)：ASTC 解码（Apache-2.0）

## 免责声明

本项目仅用于学习 研究与个人备份 不提供任何游戏资源的分发授权
《植物大战僵尸2》及其素材版权归 PopCap Games / Electronic Arts 所有
请支持正版

## 你知道吗

本项目由AI编写

最新 WSA 验证版 v5 关闭了离线启动时的网络故障与公告弹窗，并保留多存档修复。补丁与验证范围见 [docs/startup-dialog-suppression.md](docs/startup-dialog-suppression.md)。APK、游戏库与用户存档不纳入仓库。
