# v24：移除幸运宝藏入口与引导，恢复离线植物探险（待游戏内验收）

已有成果已推送到 `codex/mouse-v18`，v23 APK 已发布：
https://github.com/EndiVee233/pvz2-lostcity-wsa/releases/tag/v1.7.5-v23

本次 APK：`work/adventure-v24/PvZ2-v24-offline-adventure-no-lucky-treasure.apk`

SHA256：`3dbc4d5abb2d8a39942d40a28b1b60f14fb632b4d7f68797e49f3bc936e83d5d`

## 幸运宝藏

地图教程查询 0x709808 对教程 ID 15 直接返回已完成，沿用此前 ID 18 的跳过逻辑。地图 0x9fce24 的实际查询分支在写入 Map+0x29c 的锁定状态前退出，避免埃及 6、植物探险教程后出现指向已删除入口的引导。此改动不写玩家存档。

宝物抽屉 kind 4 初始化时，0xa36000 仍调用原 AddWidget，随后将第二个子按钮（ID 12，抽屉+0xa8，幸运宝藏）设为不可见、禁用；不破坏控件所有权。抽屉引导模式 4 被清零。第一项潘妮宝物及外层宝物菜单保留。

## 离线植物探险

继续反编译确认 NetworkMgr+0xc 已是本地实现，包含配置读取、派遣验证、随机奖励生成、次数扣除和存档。0xf93d8c 查询、0xf94bcc 派遣、0xf957f4 开始确认、0xf95a1c 跳过、0xf95f54 领奖、0xf96574 惊喜奖励走本地代码；此前正数服务器时间检查与界面可联网检查阻断离线流程。

本次将 17 个植物探险专用 ServerTime getter 调用改为原游戏已导入的 gettimeofday，使用设备 UTC 秒数；另将 5 个探险界面可用性查询改为可用，使其进入已有本地后端。没有全局替换网络接口或服务器时间，没有改解锁条件、奖励配置和存档结构。

保留原有植物要求、次数限制、派遣时间、奖励、提前完成费用及存档逻辑。倒计时、到期成熟、重新进入界面都使用相同设备时间；离线计时依赖设备时钟准确。配置仍来自原 PLANTADVENTURECONFIGDATA。

## 检查范围

`scripts/check_adventure_v24_native.py` 执行真实 ARM 指令，外部边界使用夹具：512 组教程查询与 v23 对比，ID 15/18 的地图入口跳过，6 组抽屉隐藏/禁用及空指针检查，设备时间读取与失败返回，原生存档成熟循环在到期前、到期时及重新创建执行环境后的状态切换，原生列表查询的成功通知。均通过。

APK v1/v2/v3 签名和 zipalign 检查通过。相对 v23 只有 lib/armeabi/libSrc.so 载荷改变，其余 DEX、库与资源一致。未安装、运行 v24，未改用户数据。完整派遣、领奖、地图入口外观和教程衔接仍需游戏内验收；此前 v23 快捷键修复也未完成用户验收，不能据此宣称全部功能通过。

重建：`python scripts/build_adventure_v24.py`；检查：`python scripts/check_adventure_v24_native.py`；再用原 zipalign 和 recovered-debug.keystore 对齐签名。补丁记录见 adventure-v24-build.json，隔离检查结果见 adventure-v24-validation.json。
