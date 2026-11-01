# v16 商店兑换候选版（2026-11-01）

基于用户实测成功的 v15。输出：`work/exchange-v16/PvZ2-v16-currency-exchange.apk`。
SHA256：`d6e7bf298e0cf9da8d63e0c1c620057c0c803d22fa2b787a7da8d6a3e141f24e`。
与 v15 同证书，可覆盖安装；应完全退出游戏后重新打开。首次启动通过已有 BootActivity 资源覆盖更新机制替换 dynamic.rsb.smf，不需要卸载、删除存档或重解压整个资源包。

## 已实现的候选行为

基础比例 1 钻石 = 1000 金币，手续费从所得扣除10%。

| 支出 | 到账 |
|---|---|
|10钻石|9000金币|
|50钻石|45000金币|
|100钻石|90000金币|
|20000金币|18钻石|
|100000金币|90钻石|
|200000金币|180钻石|
|300000金币|270钻石|

修改 Magento 中这七个商品的 ObjectPurchaseType、Prices、ObjectCount、Names、Descriptions、ShortDescriptions；不再保留旧赠送数量或赠送文案，说明写明手续费10%。Gems/GemsFor360目录均只列出四档兑换并去掉旧默认商品。

原生分支 `0x93619c` 跳过“寻物启事”购买恢复卡及其子标签创建；`0x936dd0`、`0x936f50` 不再创建累计充值奖励区域，并保留已有实例的清理逻辑。

特别修正 `0x9312b8` 的钻石页完成路径：原函数面向现金购买，仅发送充值完成通知；兑换金币扣款后需要本地发放，因此该分支改为通过 `0x930648` 的原有 ObjectType 分发发放，再回到原始函数公共出口。原金币页继续沿用已有扣钻石/发金币流程。

84个有界ARM检查执行原生余额读取、余额不足分支、混淆余额扣款与发放算术，覆盖七档、四种混淆盐、三种余额边界；钻石页新发放分支的 this/弱句柄参数也核对通过。外部档案查询、商品解析、字符串匹配和预备dirty调用是受控边界，未仿真全部事件监听和磁盘持久化。

资源检查：解密/编码/再解密 Magento 数据一致，仅七个商品及两种钻石目录发生语义变化；RSB中其它包和字节不变。新包相对v15仅更改classes8.dex、libSrc.so与现有dynamic资源覆盖包，其他载荷逐项SHA256一致。DEX SHA1/Adler32、APK ZIP CRC、zipalign、v1/v2/v3签名检查通过。已实测成功的抽奖和教程原生补丁均保留。

## 待用户实机验收

本轮没有在设备安装或操作游戏，没有改用户存档；本候选尚不能宣称完整设备验收通过。

1. 商店金币页显示扣费后的到账数、钻石价格及10%手续费说明，没有另送文案。
2. 钻石页价格使用金币，四档到账18/90/180/270，没有人民币价格或赠送文案。
3. 寻物启事卡、累计充值标题、进度条与奖励卡消失，原位置不可点击。
4. 余额不足不扣款；足够时两类余额一次性正确变化。
5. 完全退出重启后余额保留，抽奖/教程修复没有回退。
6. 当前余额接近原引擎32位上限时的饱和处理仍沿用旧引擎，未额外改变其策略。

## 复现

- 外部依赖：py3rijndael；`nineteendo/pyvz2` 的 `OBBEdit/libraries/pyvz2rton.py`（本机位于 `K:/pvz2-tools/pyvz2`）。未将原游戏资源或第三方实现复制进Git。
- `python scripts/build_exchange_v16.py`
- `python scripts/validate_exchange_v16.py`
- 对 unsigned.apk 执行 zipalign，用 `work/keys/recovered-debug.keystore` 签名生成上述输出。
- `python scripts/verify_exchange_v16_apk.py`

记录：`docs/recovery/exchange-v16-{patches,validation,build}.json`。资源明文仅保存在被Git忽略的work目录。本轮不将未验收的候选包上传Releases；已发布v15保持为已验证稳定版。
