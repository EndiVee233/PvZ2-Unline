package com.pvz2unline.arm64probe;

import android.app.Activity;
import android.content.res.AssetManager;
import android.os.Bundle;
import android.util.Log;
import android.widget.TextView;

public final class ProbeActivity extends Activity {
    static native String probe(AssetManager assets, String cacheDirectory);

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        TextView text = new TextView(this);
        text.setText("Running Aster ARM64 probe…");
        setContentView(text);
        new Thread(() -> {
            String result;
            try {
                System.loadLibrary("Android");
                result = probe(getAssets(), getCacheDir().getAbsolutePath());
            } catch (LinkageError e) {
                result = "Aster ARM64 probe: " + e;
            }
            Log.i("AsterArm64Probe", result);
            final String message = result;
            runOnUiThread(() -> text.setText(message));
        }, "aster-arm64-probe").start();
    }
}
