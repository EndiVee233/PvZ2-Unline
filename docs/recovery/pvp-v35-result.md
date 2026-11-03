# v35：布阵返回卡槽动画资源

用户验证 v34：布阵入口、蓝旗、种植、不保存退出、铲除后的阳光与数量返还正常，网络故障弹窗不再出现。但铲除后返回卡槽时缺图，错误材质不消失。

本轮日志明确缺少 `UIActive/UI/pvp/inbattleanim/battle_account_v` 的图像加载结果。UIActive 资源清单中已有 `PVP_INBATTLEANIM`、`PVP_INBATTLEANIM_1536` 和 Common 分组；无需另造图片或重新导入原版资源。

在普通布阵关卡的 ResourceGroupNames 中增加 `PVP_INBATTLEANIM`，保留 v34 的旗帜参数和所有原有植物配置。原生库与 v34 完全一致，仅改 dynamic 资源及其校验升级 DEX。v32 的资源生命周期修复保持，诊断钩子未包含在包中。

构建：`python scripts/build_pvp_v35.py`。共用 `scripts/restore_defense_flags.py --with-inbattleanim`，不加该参数可复现 v34 的资源配置。构建脚本校验原生库不变、非目标负载一致、签名和对齐。

用户提供连续截图：植物变回卡片的图像正常，返回数量和阳光正常，但黄色星光依然一直残留；经对话框确认等待数秒仍不消失。因此本版只修复缺图，未完成特效清理。用户测试结束后已关闭游戏回档，32 个文件逐一校验通过。

进一步定位：原生 `0x1057d4c` 播放返回特效 idle，完成回调 `0x1055200` 将状态 `+0xe4` 从 1 改为 2，随后 `0x105994c` 处理飞回位置、透明度与完成回调；另有 `0x8ab100` / `0x8ab000` 通过实体系统创建相同 card_effect 资源。需要区分残留来自 UI 动画还是实体系统，不能仅凭同名资源认定根因。反编译位于忽略的 work/pvp-v35/decompiled；Ghidra 地址比 ELF 代码地址多 0x10000，数据段文件偏移比 VA 少 0x1000。

后续诊断排除上述三个候选回调作为本次植物回卡路径：正确路径是 CollectableArenaPlant `0x10b0674` 的收集回调，其调用 `0x8ab228` 生成 WORD_EFFECT（并非 `0x8ab100` 的 CARD_EFFECT）。详见 v36 记录。诊断轮已回档，32 个文件校验通过。

布阵保存与后续占领流程仍未恢复。所有用户测试均先备份，收到完成反馈后再回档。
