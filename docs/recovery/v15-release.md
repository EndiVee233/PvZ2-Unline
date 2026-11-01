# v15：通关抽奖与地图引导修复

用户实测确认：通关捡完钱袋后直接继续原结算返回流程；埃及第2关通关、完成图鉴教程后返回地图，不再被“60倍返还”引导锁住。

- 移除强制创建通关抽奖窗口的 Hook，并保留原关闭流程。
- 在教程完成状态查询入口将已删除按钮的第18号引导视为完成，阻止箭头及输入锁定初始化。其余教程查询保持原行为。
- 不清空存档。与本地后续 v12/v13/v14 的 Android Debug 证书一致；若旧安装证书不同，不要直接卸载，应先保存存档。
- 512组查询差分检查、引导入口执行检查、APK签名与ZIP校验通过。

APK：`PvZ2-v15-skip-return-guide.apk`
SHA256：`c2e83e2c80e75b6c18672739285b8b8b1e7a9085e1a9ce983f6578578cf575e9`

构建与验证脚本：`scripts/build_restored_v14.py`、`scripts/build_tutorial_v15.py`、`scripts/validate_tutorial_v15.py`。详细边界和记录见 `RECOVERY_STATUS.md` 与 `docs/recovery/tutorial-v15-*.json`。

下一步的货币兑换改造尚不属于此发布版。
