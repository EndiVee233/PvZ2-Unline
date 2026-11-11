package com.popcap.pvz2cthd;

import android.content.Context;
import android.os.Process;
import android.system.Os;
import android.util.Log;

import java.io.BufferedInputStream;
import java.io.DataInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.RandomAccessFile;
import java.io.SequenceInputStream;
import java.nio.ByteBuffer;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

public final class AsterRgbaPilot {
    private static final String TAG = "AsterRgbaPilot";
    private static final String PLAN = "reconstruction/aster-dynamic-rgba.plan";
    private static final String ORIGINAL = "reconstruction/dynamic-original-speed.rsb.smf";
    private static final String BASELINE = "reconstruction/aster-background-baseline";
    private static final String ARCHIVE_PREFIX = "com.popcap.pvz2cthd/files/";
    private static final String PVP = "zombie2.rsb.smf";
    private static final String RESOURCE = "dynamic.rsb.smf";
    private static final String PREFIX = ".aster-dynamic-rgba-v1";
    private static final int ROWS = 128;
    private static final int DIGEST_SIZE = 32;
    private static boolean started;
    private static boolean active;

    private AsterRgbaPilot() {}

    // A previous full-RGBA build may leave expanded RSBs with the same names.
    // Restore the compressed baseline before the engine can combine both generations.
    public static void ensureBaseline(Context context) throws Exception {
        File base = context.getExternalFilesDir(null);
        if (base == null) return;
        Map<String, Integer> pending = new HashMap<>();
        try (DataInputStream in = new DataInputStream(context.getAssets().open(BASELINE))) {
            int count = in.readUnsignedShort();
            for (int i = 0; i < count; i++) {
                String name = in.readUTF();
                int size = in.readInt();
                if (!name.matches("[a-z0-9]+\\.rsb\\.smf") || name.equals(RESOURCE) || size <= 0)
                    throw new IOException("Invalid Aster resource baseline");
                if (new File(base, name).length() != size) pending.put(name, size);
            }
        }
        if (!pending.isEmpty()) {
            byte[] buffer = new byte[256 * 1024];
            Integer pvp = pending.remove(PVP);
            if (pvp != null) {
                try (InputStream in = context.getAssets().open("reconstruction/zombie2-pvp.rsb.smf")) {
                    migrateResource(base, PVP, in, pvp, buffer);
                }
            }
            if (!pending.isEmpty()) {
                try (InputStream first = context.getAssets().open("pvz2data.zip.001");
                     InputStream second = context.getAssets().open("pvz2data.zip.002");
                     InputStream third = context.getAssets().open("pvz2data.zip.003");
                     ZipInputStream archive = new ZipInputStream(new BufferedInputStream(new SequenceInputStream(
                             Collections.enumeration(Arrays.asList(first, second, third)))))) {
                    ZipEntry entry;
                    while (!pending.isEmpty() && (entry = archive.getNextEntry()) != null) {
                        if (!entry.getName().startsWith(ARCHIVE_PREFIX)) continue;
                        String name = entry.getName().substring(ARCHIVE_PREFIX.length());
                        Integer size = pending.remove(name);
                        if (size != null) migrateResource(base, name, archive, size, buffer);
                    }
                }
            }
            if (!pending.isEmpty()) throw new IOException("Aster baseline resources missing: " + pending.keySet());
            Log.i(TAG, "Migrated legacy resource generation to the compressed baseline");
        }
        File[] oldMarkers = base.listFiles();
        if (oldMarkers != null) {
            for (File marker : oldMarkers) {
                if (marker.getName().matches("\\.pvz2_rgba_[0-9a-f]{20}") && marker.isFile()) marker.delete();
            }
        }
    }

    private static void migrateResource(File base, String name, InputStream in, int size, byte[] buffer) throws Exception {
        File temp = new File(base, PREFIX + ".baseline-partial");
        try {
            try (FileOutputStream out = new FileOutputStream(temp)) {
                int n;
                long written = 0;
                while ((n = in.read(buffer)) != -1) {
                    written += n;
                    if (written > size) throw new IOException("Oversize Aster resource: " + name);
                    out.write(buffer, 0, n);
                }
                if (written != size) throw new IOException("Truncated Aster resource: " + name);
                out.getFD().sync();
            }
            Os.rename(temp.getPath(), new File(base, name).getPath());
            Log.i(TAG, "Restored compressed baseline " + name);
        } finally {
            temp.delete();
        }
    }

    // Called by the existing extraction worker before the speed overlay and before libSrc.
    public static synchronized boolean useReady(Context context) {
        if (started) return active;
        File base = context.getExternalFilesDir(null);
        if (base == null) return false;
        File current = new File(base, RESOURCE);
        File pending = new File(base, PREFIX + ".next");
        File ready = new File(base, PREFIX + ".sha256");
        try (DataInputStream plan = openPlan(context)) {
            int sourceSize = plan.readInt();
            int targetSize = plan.readInt();
            byte[] sourceHash = new byte[DIGEST_SIZE];
            plan.readFully(sourceHash);
            byte[] targetHash = null;
            if (ready.length() == 2 * DIGEST_SIZE) {
                try (DataInputStream proof = new DataInputStream(new FileInputStream(ready))) {
                    byte[] proofSource = new byte[DIGEST_SIZE];
                    proof.readFully(proofSource);
                    if (Arrays.equals(proofSource, sourceHash)) {
                        targetHash = new byte[DIGEST_SIZE];
                        proof.readFully(targetHash);
                    }
                }
            }
            if (matches(current, targetSize, targetHash)) {
                active = true;
                return true;
            }
            boolean originalReady = matches(current, sourceSize, sourceHash);
            if (originalReady && matches(pending, targetSize, targetHash)) {
                Os.rename(pending.getPath(), current.getPath());
                active = true;
                Log.i(TAG, "Activated verified RGBA dynamic bundle");
                return true;
            }
            // Recover from a damaged bundle or an overlay left by an older APK.
            if (!originalReady) {
                restoreOriginal(context, base, current, sourceSize, sourceHash);
                Log.i(TAG, "Restored compressed dynamic bundle");
            }
            pending.delete();
            ready.delete();
            return true;
        } catch (Exception e) {
            Log.w(TAG, "RGBA activation unavailable", e);
        }
        return false;
    }

    public static synchronized void start(Context context) {
        if (started) return;
        started = true;
        if (active) return;
        Context app = context.getApplicationContext();
        new Thread(new Runnable() {
            @Override
            public void run() {
                bake(app);
            }
        }, "aster-rgba-pilot").start();
    }

    private static void bake(Context context) {
        File base = context.getExternalFilesDir(null);
        if (base == null) return;
        File current = new File(base, RESOURCE);
        File partial = new File(base, PREFIX + ".partial");
        File pending = new File(base, PREFIX + ".next");
        File proof = new File(base, PREFIX + ".proof");
        File ready = new File(base, PREFIX + ".sha256");
        try (DataInputStream plan = openPlan(context)) {
            Process.setThreadPriority(Process.THREAD_PRIORITY_BACKGROUND);
            int sourceSize = plan.readInt();
            int targetSize = plan.readInt();
            byte[] sourceHash = new byte[DIGEST_SIZE];
            plan.readFully(sourceHash);
            if (!matches(current, sourceSize, sourceHash) || base.getUsableSpace() < targetSize) return;
            System.loadLibrary("AsterRgbaPilot");
            int operations = plan.readInt();
            byte[] buffer = new byte[256 * 1024];
            byte[] compressed = null;
            ByteBuffer rgba = ByteBuffer.allocateDirect(4096 * ROWS * 4);
            try (RandomAccessFile input = new RandomAccessFile(current, "r");
                 FileOutputStream out = new FileOutputStream(partial)) {
                for (int op = 0; op < operations; op++) {
                    int kind = plan.readUnsignedByte();
                    if (kind == 0) {
                        write(plan, out, buffer, plan.readInt());
                    } else if (kind == 1) {
                        input.seek(plan.readInt());
                        int left = plan.readInt();
                        while (left > 0) {
                            int bytes = Math.min(left, buffer.length);
                            input.readFully(buffer, 0, bytes);
                            out.write(buffer, 0, bytes);
                            left -= bytes;
                        }
                    } else if (kind == 2) {
                        input.seek(plan.readInt());
                        int width = plan.readInt();
                        int height = plan.readInt();
                        for (int row = 0; row < height; row += ROWS) {
                            int rows = Math.min(height - row, ROWS);
                            int size = width * rows;
                            if (compressed == null || compressed.length != size) compressed = new byte[size];
                            input.readFully(compressed);
                            if (!decodeAstc(compressed, width, rows, rgba)) throw new IOException("ASTC decode failed");
                            rgba.position(0);
                            rgba.limit(size * 4);
                            while (rgba.hasRemaining()) out.getChannel().write(rgba);
                        }
                    } else {
                        throw new IOException("Unknown conversion operation");
                    }
                }
                if (plan.read() != -1 || out.getChannel().size() != targetSize)
                    throw new IOException("Incomplete RGBA conversion");
                out.getFD().sync();
            }
            byte[] hash = digest(partial);
            try (FileOutputStream out = new FileOutputStream(proof)) {
                out.write(sourceHash);
                out.write(hash);
                out.getFD().sync();
            }
            Os.rename(partial.getPath(), pending.getPath());
            Os.rename(proof.getPath(), ready.getPath());
            Log.i(TAG, "Staged RGBA dynamic bundle for cold start");
        } catch (Exception | LinkageError e) {
            Log.w(TAG, "Background RGBA conversion deferred", e);
        } finally {
            partial.delete();
            proof.delete();
        }
    }

    private static void restoreOriginal(Context context, File base, File current, int size, byte[] hash) throws Exception {
        File temp = new File(base, PREFIX + ".restore");
        try {
            try (InputStream input = context.getAssets().open(ORIGINAL);
                 FileOutputStream out = new FileOutputStream(temp)) {
                byte[] buffer = new byte[256 * 1024];
                int n;
                while ((n = input.read(buffer)) != -1) out.write(buffer, 0, n);
                out.getFD().sync();
            }
            if (!matches(temp, size, hash)) throw new IOException("Compressed recovery source differs");
            Os.rename(temp.getPath(), current.getPath());
        } finally {
            temp.delete();
        }
    }

    private static DataInputStream openPlan(Context context) throws IOException {
        DataInputStream input = new DataInputStream(new BufferedInputStream(context.getAssets().open(PLAN)));
        if (input.readInt() == 0x41424731) return input; // ABG1
        input.close();
        throw new IOException("Wrong RGBA plan format");
    }

    private static void write(DataInputStream input, FileOutputStream out, byte[] buffer, int left) throws IOException {
        while (left > 0) {
            int n = Math.min(left, buffer.length);
            input.readFully(buffer, 0, n);
            out.write(buffer, 0, n);
            left -= n;
        }
    }

    private static boolean matches(File file, int size, byte[] hash) throws Exception {
        return hash != null && file.length() == size && Arrays.equals(digest(file), hash);
    }

    private static byte[] digest(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] buffer = new byte[256 * 1024];
        try (FileInputStream in = new FileInputStream(file)) {
            int n;
            while ((n = in.read(buffer)) != -1) digest.update(buffer, 0, n);
        }
        return digest.digest();
    }

    private static native boolean decodeAstc(byte[] input, int width, int height, ByteBuffer rgba);
}
