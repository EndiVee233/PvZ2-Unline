# PvZ2-Unline:Aster
> 启动器/资源方案来自 [DreamMoonCai/Pvz2Tool](https://github.com/DreamMoonCai/Pvz2Tool)；
> ASTC 解码基于 [google/astc-codec](https://github.com/google/astc-codec)。

一个面向 Windows Subsystem for Android / 普通 Android 的单文件直装版

**当前 GitHub 正式包为更名前的 PvZ2-Unline v147。** 应用图标使用 `PVP.png`，开始界面使用等比铺满窗口的新版背景。

[下载 v147](https://github.com/EndiVee233/PvZ2-Unline-Aster/releases/tag/v1.7.5-v147) · [离线 PvP 功能与待办](docs/recovery/pvp-v123-release.md) · [分项验收记录](docs/recovery/README.md)

**全量 RGBA8888 预览版。** v163 的 19 个 RSB 中，773 张实际引用的图集已在构建时转为 RGBA8888。APK 约 2.87 GB，首次解包后的资源约 13.30 GB。已在 WSA 核对覆盖安装、资源迁移和启动画面，各世界及 PvP 尚待逐项验收。下载两段后按发布页说明合并并校验。 [v163 RGBA8888 预览版](https://github.com/EndiVee233/PvZ2-Unline-Aster/releases/tag/v1.7.5-v163-rgba-preview)

## 特性

- **程序名** 植物大战僵尸2-Unline
- **单文件直装**：资源以分卷形式内置在 APK 中 首次启动自动解压
- **尝试跳过“服务器通讯中”**：`AndroidHttpProxy.GetNetworkStatus()` 固定返回 `0`
- **WSA 纹理兼容层**：`libRestart.so` 作为 GL shim
  - RGBA4444 → RGBA8888
  - ETC1 → RGBA8888
  - ASTC 4x4/5x5/6x6 等 → RGBA8888
  - **全分辨率**解码：常驻 2～4 个工作线程，空闲时预解码并缓存，未就绪资源加入同一线程池处理
- **无启动器入口**：启动器杂七杂八的东西我会好奇的乱点...然后就控制不住的开始作弊了 所以干脆不要启动器了

## 下载安装

到 [Releases](../../releases) 下载 `PvZ2-Unline-v147.apk` 后覆盖安装。

```bat
adb install -r PvZ2-Unline-v147.apk
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
