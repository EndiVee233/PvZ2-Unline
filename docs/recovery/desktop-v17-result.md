# v17 桌面交互与后台解码候选（等待用户验收）

APK：work/desktop-v17/PvZ2-v17-background-cache-mouse-hover.apk
SHA256：8f9bbc4b822cf7ee855a0a3f846f6ed6da4b2b0c8ec1ffaaa65406397aa15114
基线：已完成 WSA 自测的 v16r10，保留原证书，可覆盖安装。

按本次要求，仅编译和签名打包，未安装到 WSA、未运行游戏、未进行鼠标或解码性能验证。当前属于待验收候选，不能把上轮 v16 的验证结果套用于本轮改动。

## 后台解码

原 libRestart.so 每次按需解码临时创建最多16条线程。现在改为进程常驻共享线程池：报告CPU数至少8时请求4条，4–7时请求3条，其余请求2条；线程创建失败保留降级处理。线程空闲时等待，不反复创建和销毁。

基于原资源包生成仅含元数据的索引，覆盖754张ASTC图集：466张5×5和288张6×6。后台一次组织一张图集的条带任务，完成后原子写入私有 glcache，再处理下一张。RGBA4444/ETC1兼容转换沿用原路径；其它ASTC规格仍支持按需解码。

前台未命中缓存时，把任务加入高优先级队列，使用同一批预留线程。若请求正是后台正在解码的图集，则提升该图集剩余条带的优先级并等待已有结果，避免重复解码。工作线程只做CPU解码和文件缓存，GL上传仍在原渲染线程。缓存临时文件完成后rename发布；资源大小与压缩内容哈希不匹配时跳过预解码；可用空间不足约256MiB加当前图集大小时暂停后台预缓存。

## 商店

七档兑换说明改为“获得X 金币/钻石”，隐藏手续费文字。实际到账数和原10%扣费算法均保持不变。通过原生UTF-32本地化字符串修改，不改已稳定的Magento覆盖资源及启动校验常量。

## 鼠标跟随

AndroidSurfaceView 接收鼠标 HOVER_ENTER/HOVER_MOVE，使用 AndroidUIEventManager 原事件队列投递扩展phase=5。保留实际pointer ID及前后坐标，失去焦点时重置鼠标跟踪器；不合成按下、释放或长按事件。

原生0x132b660识别phase=5，沿用0x1327d0c坐标转换，再调用应用原移动回调，绕过只允许活动触点移动的驱动层限制。普通触屏phase0–4继续执行原路径。植物、能量豆、铲子的实际跟随和落点行为由用户验收，尚无实机成功结论。

## 重建

1. python scripts/index_texture_prefetch.py work/launch-fix/PvZ2-v16r10-currency-exchange.apk work/desktop-v17/index
2. 使用 src/glshim/build.py，传入本地NDK、google/astc-codec、生成的prefetch_index.inc及 reconstruction 私有cache路径。
3. scripts/build_desktop_hover.py 的 rebuild_mouse_dex 从基线 classes.dex 重新组装输入模块。
4. python scripts/build_desktop_v17.py
5. zipalign，再用保留的 recovered-debug.keystore 签名。

生成记录：desktop-v17-build.json。新增或替换的APK载荷只有 classes.dex、libSrc.so、libRestart.so；原资源包、classes8.dex启动器与抽奖Hook库沿用v16r10。签名包和资源索引留在私有work目录，不提交游戏资源或用户存档。
