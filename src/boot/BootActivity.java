package com.popcap.pvz2cthd;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.AssetManager;
import android.content.res.ColorStateList;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.Gravity;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

public class BootActivity extends Activity {
    private static final String TAG = "PvZ2Bootstrap";
    private static final String PREFIX = "com.popcap.pvz2cthd/files/";
    private static final String[] PARTS = {"pvz2data.zip.001", "pvz2data.zip.002", "pvz2data.zip.003"};
    private static final long TOTAL_BYTES = 2746000000L;

    private TextView statusView;
    private ProgressBar progressBar;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private volatile long written = 0;
    private volatile boolean done = false;
    private volatile String error = null;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                WindowManager.LayoutParams.FLAG_FULLSCREEN);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        buildUi();

        if (Build.VERSION.SDK_INT >= 23
                && checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{
                    Manifest.permission.WRITE_EXTERNAL_STORAGE,
                    Manifest.permission.READ_EXTERNAL_STORAGE
            }, 100);
            return;
        }
        begin();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == 100) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                begin();
            } else {
                fail("需要存储权限才能解压资源");
            }
        }
    }

    private void begin() {
        final File base = getExternalFilesDir(null);
        if (base == null) {
            fail("无法访问外部存储");
            return;
        }
        final File marker = new File(base, ".pvz2_extracted");
        if (marker.exists() || (new File(base, "init.rsb.smf").exists() && new File(base, "dynamic.rsb.smf").exists())) {
            startGame();
            return;
        }
        new Thread(new Runnable() {
            public void run() {
                extract(base);
            }
        }, "pvz2-extract").start();
        ui.postDelayed(new Runnable() {
            public void run() {
                updateProgress();
            }
        }, 250);
    }

    private void buildUi() {
        float density = getResources().getDisplayMetrics().density;
        int sw = getResources().getDisplayMetrics().widthPixels;
        int sh = getResources().getDisplayMetrics().heightPixels;
        Typeface tf = Typeface.DEFAULT_BOLD;
        try {
            tf = Typeface.createFromAsset(getAssets(), "pvz2font.ttf");
        } catch (Throwable ignored) {
        }

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(0xFF000000);

        ImageView logo = new ImageView(this);
        try {
            logo.setImageBitmap(BitmapFactory.decodeStream(getAssets().open("ea_logo.png")));
            logo.setScaleType(ImageView.ScaleType.FIT_CENTER);
            FrameLayout.LayoutParams logoLp = new FrameLayout.LayoutParams(
                    (int) (sw * 0.55f), (int) (sh * 0.30f),
                    Gravity.TOP | Gravity.CENTER_HORIZONTAL);
            logoLp.topMargin = (int) (sh * 0.10f);
            root.addView(logo, logoLp);
        } catch (Throwable ignored) {
        }

        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setGravity(Gravity.CENTER_HORIZONTAL);
        int pad = (int) (24 * density);
        panel.setPadding(pad, pad, pad, pad);

        ImageView title = new ImageView(this);
        title.setImageResource(0x7f020047); // drawable/splash_1080p_1
        title.setScaleType(ImageView.ScaleType.FIT_CENTER);
        title.setContentDescription("正在进行第一次解压");
        panel.addView(title, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, (int) (58 * density)));

        TextView sub = new TextView(this);
        sub.setText("首次启动需要释放约 2.6 GB 游戏资源，请勿关闭应用");
        sub.setTextColor(0xFFBDBDBD);
        sub.setTextSize(13);
        sub.setTypeface(tf);
        sub.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams subLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        subLp.topMargin = (int) (12 * density);
        panel.addView(sub, subLp);

        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progressBar.setMax(1000);
        progressBar.setProgress(0);
        progressBar.setProgressTintList(ColorStateList.valueOf(0xFF7CB342));
        progressBar.setProgressBackgroundTintList(ColorStateList.valueOf(0xFF1B2E1B));
        int w = (int) (sw * 0.72f);
        LinearLayout.LayoutParams barLp = new LinearLayout.LayoutParams(w, (int) (16 * density));
        barLp.topMargin = (int) (26 * density);
        panel.addView(progressBar, barLp);

        statusView = new TextView(this);
        statusView.setText("0%");
        statusView.setTextColor(0xFFFFFFFF);
        statusView.setTextSize(18);
        statusView.setTypeface(tf);
        statusView.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams stLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        stLp.topMargin = (int) (12 * density);
        panel.addView(statusView, stLp);

        TextView hint = new TextView(this);
        hint.setText("解压完成后会自动进入游戏");
        hint.setTextColor(0xFF9E9E9E);
        hint.setTextSize(12);
        hint.setTypeface(tf);
        hint.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams hLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        hLp.topMargin = (int) (8 * density);
        panel.addView(hint, hLp);

        FrameLayout.LayoutParams panelLp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
        panelLp.bottomMargin = (int) (sh * 0.08f);
        root.addView(panel, panelLp);
        setContentView(root);
    }

    private void updateProgress() {
        if (error != null) {
            fail(error);
            return;
        }
        int p = (int) Math.min(1000L, written * 1000L / TOTAL_BYTES);
        progressBar.setProgress(p);
        statusView.setText(String.format("%.1f%%   %d / %d MB", p / 10.0,
                written >> 20, TOTAL_BYTES >> 20));
        if (done) {
            progressBar.setProgress(1000);
            statusView.setText("解压完成，正在启动游戏...");
            ui.postDelayed(new Runnable() {
                public void run() {
                    startGame();
                }
            }, 600);
            return;
        }
        ui.postDelayed(new Runnable() {
            public void run() {
                updateProgress();
            }
        }, 250);
    }

    private void extract(File base) {
        InputStream in = null;
        ZipInputStream zis = null;
        try {
            base.mkdirs();
            in = new ConcatAssetInputStream(getAssets(), PARTS);
            zis = new ZipInputStream(new BufferedInputStream(in, 1 << 20));
            byte[] buf = new byte[1 << 20];
            ZipEntry e;
            while ((e = zis.getNextEntry()) != null) {
                String name = e.getName();
                if (name == null || !name.startsWith(PREFIX)) continue;
                String rel = name.substring(PREFIX.length());
                if (rel.length() == 0) continue;
                File out = new File(base, rel);
                if (e.isDirectory()) {
                    out.mkdirs();
                    continue;
                }
                if ("sdcardid.dat".equals(rel) && out.isFile()) continue;
                File parent = out.getParentFile();
                if (parent != null) parent.mkdirs();
                FileOutputStream fos = new FileOutputStream(out);
                try {
                    int n;
                    while ((n = zis.read(buf)) > 0) {
                        fos.write(buf, 0, n);
                        written += n;
                    }
                } finally {
                    fos.close();
                }
            }
            new File(base, ".pvz2_extracted").createNewFile();
            done = true;
            Log.i(TAG, "extract done: " + written + " bytes");
        } catch (Throwable t) {
            error = t.toString();
            Log.e(TAG, "extract failed", t);
        } finally {
            try { if (zis != null) zis.close(); } catch (Throwable ignored) {}
        }
    }

    private void fail(String msg) {
        if (statusView != null) {
            statusView.setText("解压失败：" + msg + "\n请重启应用重试");
            statusView.setTextColor(0xFFFF8A80);
        }
    }

    private void startGame() {
        try {
            Intent i = new Intent();
            i.setClassName(this, "com.popcap.pvz2cmhd.SexyAppActivity");
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
            startActivity(i);
        } catch (Throwable t) {
            Log.e(TAG, "start game failed", t);
        }
        finish();
    }

    static class ConcatAssetInputStream extends InputStream {
        private final AssetManager am;
        private final String[] names;
        private int idx = -1;
        private InputStream cur;

        ConcatAssetInputStream(AssetManager am, String[] names) {
            this.am = am;
            this.names = names;
        }

        private boolean next() throws IOException {
            if (cur != null) {
                try { cur.close(); } catch (IOException ignored) {}
                cur = null;
            }
            idx++;
            if (idx >= names.length) return false;
            cur = am.open(names[idx], AssetManager.ACCESS_STREAMING);
            return true;
        }

        @Override
        public int read() throws IOException {
            byte[] one = new byte[1];
            int n = read(one, 0, 1);
            return n < 0 ? -1 : (one[0] & 0xff);
        }

        @Override
        public int read(byte[] b, int off, int len) throws IOException {
            while (true) {
                if (cur == null && !next()) return -1;
                int n = cur.read(b, off, len);
                if (n >= 0) return n;
                if (!next()) return -1;
            }
        }

        @Override
        public void close() throws IOException {
            if (cur != null) {
                try { cur.close(); } catch (IOException ignored) {}
                cur = null;
            }
        }
    }
}
