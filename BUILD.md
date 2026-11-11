# BUILD

These notes describe how the released APK was assembled. Paths in
`src/boot/build_single.py` are absolute placeholders from the build machine;
adjust them for your layout.

## Prerequisites

- Android SDK Build-Tools 34.0.0 (`aapt2`, `zipalign`, `apksigner`, `d8`)
- Android NDK 27 (`clang`, CMake 3.22)
- JDK 17+ (the build used Android Studio JBR)
- Python 3 with Pillow (only if regenerating screenshots/crops)
- The original Chinese 1.7.5 APK and a full resource directory, legally obtained

## 1. Manifest and label

- Set the MAIN/LAUNCHER activity to `com.popcap.pvz2cthd.BootActivity`
  (`src/tools/patch_axml_index.py`).
- Set the application `android:label` and `app_label` to `植物大战僵尸2`
  (`patch_axml_string.py`, `patch_arsc_label.py`).

## 2. BootActivity

```bash
javac -source 1.8 -target 1.8 \
  -bootclasspath $ANDROID_SDK/platforms/android-34/android.jar \
  -d classes src/boot/BootActivity.java
jar cf classes.jar -C classes com
java -cp $ANDROID_STUDIO/plugins/android/lib/r8.jar \
  com.android.tools.r8.D8 --min-api 21 \
  --lib $ANDROID_SDK/platforms/android-34/android.jar \
  --output dex classes.jar
cp dex/classes.dex classes8.dex
```

## 3. GL shim

```bash
cmake -S src/glshim -B build -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE=$ANDROID_NDK/build/cmake/android.toolchain.cmake \
  -DANDROID_ABI=armeabi-v7a -DANDROID_PLATFORM=android-21 \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build -j1
```

`astc-codec` is added as a subdirectory; place it next to `src/glshim`.

Alternatively, on Windows, build `libRestart.so` directly with local NDK and
astc-codec checkouts (use an ASCII output directory):

```powershell
python src/glshim/build.py --ndk C:/tools/android-ndk --astc C:/tools/astc-codec --output C:/build/pvz2-glshim --test
```

The ASTC runtime worker limit is 16, capped by online CPUs and available strip
jobs. Failed thread creation falls back to fewer workers or synchronous decoding.
This runtime setting is independent of CMake's build-job count. For the isolated
test application, also pass
`--cache-root /data/data/com.popcap.pvz2cthd.reconstruction/cache`.
The Android `test_decode` executable requires astc-codec's
`src/decoder/testdata/atlas_small_{4x4,5x5,6x6}.astc` in its directory argument.
It compares production strip output byte-for-byte with serial decoding and
checks partial/all thread-creation failure. The build script compiles API 21 ARMv7
and statically links libc++; it does not package or sign the APK.

## 4. Resource parts

Split the resource zip into <512 MB chunks so each asset can be opened by a 32-bit
process without a huge mmap:

```
assets/pvz2data.zip.001
assets/pvz2data.zip.002
assets/pvz2data.zip.003
```

`BootActivity` concatenates them with `ConcatAssetInputStream` and feeds a
`ZipInputStream`.

## 5. Assemble and sign

`src/boot/build_single.py` removes the old launcher assets
(`assets/pvz2tool/version/`), adds `classes8.dex`, `assets/ea_logo.png`,
`assets/pvz2font.ttf`, the three data parts, the patched manifest and
`resources.arsc` (stored uncompressed and 4-byte aligned).

```bash
zipalign -p -f 4 unsigned.apk aligned.apk
apksigner sign --ks pvz2.keystore --ks-key-alias pvz2 \
  --v1-signing-enabled true --v2-signing-enabled true \
  --out 植物大战僵尸2-1.7.5.apk aligned.apk
```

`resources.arsc` **must** be `ZIP_STORED` and 4-byte aligned, otherwise
Android 11+ refuses to install (`Targeting R+ requires resources.arsc ...`).

## 7. Recovered Java snapshot and offline validation

The additional `src/recovered/` tree is a source and evidence snapshot, not a
standalone replacement for the original APK project. It contains the recovered
bootstrap plus all 84 exported `com.popcap` Java files from the main DEX. The
verified offline test APK uses package `com.popcap.pvz2cthd.reconstruction`,
enables the `pvz2.reconstruction.offline` manifest flag, and stores its local
profile under its private app data directory. The original package and its
network branch were left unchanged.

The WSA evidence records 433 differential Java checks, welcome/menu/first-level
gameplay, and local profile retention after a cold restart. It does not validate
the full campaign, cloud services, purchases, sharing, or system notifications.
Native libraries and most other SDK classes remain binary/Smali. The bounded
native bridge fragment is analysis evidence only; it was not compiled or linked.

The source snapshot omits the original APK, decoded assets/Smali, API stub JARs,
native libraries, signing key, and device-specific files. Rebuilding the complete
APK therefore requires a legally obtained original APK and the local workspace
layout described above. `src/recovered/tools/build_dex_reference_jar.py` creates
compile-only declarations from `raw/classes*.dex`; the generated JAR contains
no original method implementations and must never be packaged as application
code. Current sanitized validation records are under
`src/recovered/`.

## 8. Original "Turbo" speed button instead of the PvP one

## 6. Skip the `服务器通讯中` overlay

`AndroidHttpProxy.GetNetworkStatus()` must return `0` (NET_NOT_REACHABLE).
With the original implementation the native side keeps issuing
`POST http://cloudpvz2android.ditwan.cn/index.php` once per frame while the
notice dialog is open (the endpoint is long dead), never leaves the waiting
state, and the `服务器通讯中...` overlay stays on screen and swallows taps.

Run the dex patch after assembling and before `zipalign`:

```bash
python src/tools/patch_dex_network_status.py unsigned.apk unsigned_netpatch.apk
mv unsigned_netpatch.apk unsigned.apk
```

The script rewrites `classes.dex` (keeping the APK layout, stored entries stay
4-byte aligned) and leaves the APK unsigned, so sign afterwards as usual.
With the patch no transaction is created at all (`CreateHttpTransaction`
count stays 0 in logcat) and the notice dialog shows its built-in text without
the overlay.
## 7. Original "Turbo" speed button instead of the PvP one

The Chinese 1.7.5 build ships `UIChangeSpeedButton` as
`ArenaChangeSpeedButton` / `IMAGE_UI_HUD_INGAME_ARENA_CHANGE_SPEED`
(the PvP style). The launcher used to flip it at runtime
(`assets/pvz2tool/features/speed/double_speed.js`); without the launcher
the PvP style becomes the default.

`src/tools/patch_speed.py` rebuilds `dynamic.rsb` with the original style:

```
Class         = SpeedChange
SizeFromImage = IMAGE_UI_HUD_INGAME_SPEED
```

The `Packages` group of `dynamic.rsb` (an `1bsr` v4 container) stores each
package as a Rijndael-CBC encrypted RTON blob:

* header `0x10 0x00`, then ciphertext
* key = ASCII of `md5("com_popcap_pvz2_magento_product_2013_05_05")`
* iv  = key[4:28], block size 192, ZeroBytePadding

The script decrypts all packages, replaces the two strings (both `0x90` and
`0x81` string encodings), pads the plaintext back to its original length and
re-encrypts, so the container layout, sizes and offsets stay untouched.

Then rebuild the split `pvz2data.zip` (raw copy of unchanged entries):

```bash
python src/tools/repack_raw.py
```

and replace `assets/pvz2data.zip.001/.002/.003` in the APK before signing.
`src/tools/rsbtool.py` is the minimal RSB reader used by the patcher.

## 8. Offline challenge recovery (local v10 candidate)

In the analysis workspace with the original ARM library, local Python dependencies
and the existing v9 reconstruction APK:

```powershell
python scripts/restore_offline_challenge.py
python scripts/test_offline_challenge_attempts.py
python scripts/build_multiuser_test.py v10
```

The challenge task alone falls back to the device clock and original daily reset
when its time request fails. The challenge submenu also bypasses its introduction
highlight lock without changing saved tutorial progress or difficulty unlocks.
The builder preserves the isolated application ID and full resource parts.
This remains a patch of the original engine, not a full source-only game build.

WSA tested all three normal challenge level loads. Full victory/reward collection
and hard/legend difficulties remain unverified. The observation/validation scripts
expect private snapshots from an existing isolated test install; they are not a
fresh-install automated gameplay suite. See
`docs/recovery/离线挑战模式恢复结果.md` for hashes and exact test boundaries.

## Android package IDs

After producing an Aster or Iris APK with the legacy package ID, run this
release packaging step from the Aster checkout. Keep the original signing key.

```powershell
python scripts/rename_unline_apk.py aster <built-aster.apk> <output-aster.apk> <sdk-build-tools>
python scripts/rename_unline_apk.py iris <built-iris.apk> <output-iris.apk> <sdk-build-tools>
```

The resulting IDs are `com.pvz2unline.aster` and `com.pvz2unline.iris`.
Android keeps the old installations and their saves in separate sandboxes.

## Experimental Aster ARM64 game wrapper

Future GitHub releases must include separate ARM32 and ARM64 APKs, labeled
with their architecture and independent acceptance status. Common changes
must be carried into both packages. WSA gameplay acceptance uses ARM32.
ARM64 is maintained conservatively: do not run proactive ARM64 tests/rechecks;
investigate it only for an issue explicitly affecting ARM64. Release descriptions
must say **ARM64 is not recommended; prefer ARM32**, with outstanding ARM64
issues/unverified behavior listed. A passing ARM32 run does not validate ARM64.
Do not replace the Iris installation used by another session.

To apply the shared Java desktop-focus/speed-flash fixes while retaining the
existing ARM32 native libraries:

```powershell
python scripts/build_aster_feedback_arm32.py <renamed-aster-v163.apk> <android-sdk> <output-dir>
```

This produces `PvZ2-Unline-Aster-ARM32.apk` with the same application ID and
signing key. `validation.json` records the unchanged native-library hashes.

To add native last-player memory as well, append
`--profile-memory-ndk <android-ndk>`. This applies the two checked engine hooks
and records the changed `libSrc.so` hash separately from the other libraries.
Use that resulting ARM32 APK as the ARM64 builder input, so its guest engine
contains the identical persistence fix. Run the shared ARM32 patch checks with
`python scripts/check_profile_memory.py <output-dir>/profile-memory`.

This preserves the renamed Aster Java/resources and executes its six
ARM32 native libraries through the ARM64 bridge. The current ARM32 candidate
has passed user acceptance on WSA. The synchronized ARM64 candidate is not
acceptance-tested and is not recommended; performance and physical-device
compatibility remain unverified. Do not proactively test ARM64 without a
reported ARM64-specific issue.

Initialize the submodules of [arm64-bridge-a7](https://github.com/phys-winner/arm64-bridge-a7)
in a separate checkout. Obtain the Apache-2.0 [google/astc-codec](https://github.com/google/astc-codec)
source and use JDK 17+, Android SDK API 34/Build Tools 34.0.0, CMake 3.22.1,
and an Android NDK. Third-party sources and original game binaries are local
build inputs, not bundled in this repository.

```powershell
python scripts/build_aster_arm64_game.py <renamed-aster-v163.apk> <a7-checkout/arm64_bridge> <android-sdk> <android-ndk> <output-dir> --astc-source <google-astc-codec-checkout>
```

The result is `PvZ2-Unline-Aster-ARM64-experimental.apk`, using
`com.pvz2unline.aster` and the existing signing key. Installing it replaces the
Aster executable in place; it is not an isolated diagnostic. Back up saves
first with `scripts/wsa_save_snapshot.py backup`, preserve any pending baseline,
and restore/verify them after tests. Do not install over an active user test.
The snapshot tool accepts `PVZ2_ADB` and `PVZ2_PACKAGE` overrides; its defaults
are the current SDK path and `com.pvz2unline.aster`. `ADB_SERVER_SOCKET` can select
an isolated local ADB server without interrupting other development sessions.

The game builder defaults to the lean runtime profile: cycle-count sampling,
animated-resource tracing and repeated JNI/file-operation logs are disabled.
Bridge/JNI failure reports remain enabled. Add `--diagnostics` to rebuild with
the slower investigation profile. The profile does not change the A32 game
engine or resource payloads.
