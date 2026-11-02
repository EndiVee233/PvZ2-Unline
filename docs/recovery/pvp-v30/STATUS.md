# PvP crash investigation — 2026-11-02

Entry crash workaround verified with WSA USER: opened NPC arena, advanced opening dialogue, observed five lanes of peashooters firing at NPC zombies. Whole-match completion and return remain unverified. Use WSA USER only. Do not clear/uninstall application.

Confirmed: repeated read of `images\1536\UIActive\UI\pvp\inbattleanim\add_energy\add_energy.pam` returns size 30594 but source pointer 0x1000. First read is valid. Crash is in Buffer vector insertion, not evidence of a WSA input problem.

Rejected experiments: changing world string address (original 0x18a6708 correctly contains activity); forcing uncached lookup in ReadBufferFromFile; adding PVP_INBATTLEANIM to tutorial module ResourceGroupNames. All failed or unproven; do not ship these changes.

Current diagnostic: work/pvp-v30/cache.apk. Native cache.s/cache.so caches exact file names plus lengths for pvp inbattleanim reads and supplies previously copied bytes only if later source pointer is below 0x10000. Cache head uses four newly reserved BSS bytes at end of RW segment. Executable segment remains RX, not RWX. First attempt with RWX was rejected by Android loader; corrected diagnostic installs and starts.

Baseline full APK: work/bootstrap-v29/PvZ2-v29-resource-upgrade-fix.apk. Diagnostic APKs omit resource splits and are not deliverables. The full v30 deliverable was then installed successfully and WSA USER entered the arena opening again, without diagnostic logger hooks. Device now has the full v30 package. Full deliverable: work/pvp-v30/PvZ2-v30-offline-npc-entry-crash-fix.apk. SHA256 c27e2ac0ee5781a0a45000153ff6614ee64e8a011a0c01c5867c3a862788a355. Only lib/armeabi/libSrc.so differs from full v29; all three resource asset splits retained. v1/v2/v3 signatures pass. Built by scripts/build_pvp_v30.py, with diagnostic logger hooks removed.

All temporary device dev overrides created during this investigation were removed, including generated RTON. User saves untouched.

Cleanup: recycled-apks.json records 56 generated unsigned/aligned APK intermediates, 59.65 GiB. Recycle Bin was not emptied. Final signed versions and build dependencies retained.

Native recovery: work/pvp-v30/decompiled/11d784c.c, 11dbb18.c, 11d53fc.c, 11db8c8.c, 120bcdc.c. Ghidra addresses have +0x10000 bias relative to ELF VAs. Recovered pseudocode is not original source.

Installation verification failures recovered after normal WSA shutdown/restart. No security settings were disabled.
