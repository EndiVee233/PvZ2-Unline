# 游戏测试与存档规则

用户要求：所有后续游戏运行测试均须先备份存档，测试完成后回档。

- 在首次启动或操作游戏进行测试前，运行 `python scripts/wsa_save_snapshot.py backup`。
- 如 `work/private-save-backups/ACTIVE.json` 显示待回档，沿用该备份，不能以测试中存档替换基线。
- 使用用户指定的 `WSA USER` 玩家。不得卸载应用、清空应用数据或手动修改玩家存档来推进测试。
- 测试结束后关闭游戏，运行 `python scripts/wsa_save_snapshot.py restore`，逐文件校验恢复结果，再交付。
- 用户要求继续工作时，保留上述规则；中途新增测试属于同一待回档测试批次。
- 私有存档、数据库、偏好设置和相关备份只保存在已忽略的 `work/private-save-backups/`，不得提交或上传。
