package com.popcap.pvz2cthd;

import android.content.Context;
import android.util.AtomicFile;
import java.io.*;
import java.util.*;

final class PvpLevelStorage {
    static final String SUFFIX = ".pvz2-pvp.json";
    final File root;

    PvpLevelStorage(Context context) throws IOException {
        root = directory(context.getExternalFilesDir("pvp_level"));
        migrateDraft(context, root);
    }

    private static synchronized void migrateDraft(Context context, File root) {
        File legacy = new File(context.getFilesDir(), "pvp-preset-drafts/latest.pvz2-pvp.json");
        File recovered = new File(root, "previous-draft" + SUFFIX);
        if (legacy.isFile() && !context.getSharedPreferences("pvp-preset-options", 0)
            .getBoolean("previous_draft_imported", false)) {
            try {
                if (!recovered.exists()) write(recovered, PvpPresetDocument.read(new FileInputStream(legacy)));
                context.getSharedPreferences("pvp-preset-options", 0).edit()
                    .putBoolean("previous_draft_imported", true).apply();
            } catch (IOException e) {
                android.util.Log.w("PvpPresetEditor", "Could not migrate the previous draft", e);
            }
        }
    }

    File github() throws IOException { return directory(new File(root, "github")); }

    File[] localLevels() {
        File[] entries = root.listFiles(file -> file.isFile() && file.getName().endsWith(".json"));
        if (entries == null) return new File[0];
        Arrays.sort(entries, Comparator.comparingLong(File::lastModified).reversed().thenComparing(File::getName));
        return entries;
    }

    File saveLocal(File existing, byte[] data) throws IOException {
        File target = existing != null ? existing : new File(root, "PVP-" + UUID.randomUUID() + SUFFIX);
        write(target, data);
        return target;
    }

    private static File directory(File dir) throws IOException {
        if (dir == null || (!dir.isDirectory() && !dir.mkdirs() && !dir.isDirectory()))
            throw new IOException("无法打开 pvp_level 目录");
        return dir;
    }

    static void write(File target, byte[] data) throws IOException {
        AtomicFile file = new AtomicFile(target);
        FileOutputStream out = file.startWrite();
        try {
            out.write(data);
            out.getFD().sync();
            file.finishWrite(out);
        } catch (IOException e) {
            file.failWrite(out);
            throw e;
        }
    }
}
