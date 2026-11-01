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
