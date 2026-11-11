package com.pvz2unline.arm64probe;

import android.app.Activity;
import android.app.Instrumentation;
import android.os.Bundle;

public final class ProbeInstrumentation extends Instrumentation {
    @Override public void onCreate(Bundle args) {
        super.onCreate(args);
        start();
    }

    @Override public void onStart() {
        Bundle result = new Bundle();
        try {
            System.loadLibrary("Android");
            String first = ProbeActivity.probe(getContext().getAssets(), getContext().getCacheDir().getAbsolutePath());
            String second = ProbeActivity.probe(getContext().getAssets(), getContext().getCacheDir().getAbsolutePath());
            if (!first.equals(second)) {
                result.putString("stream", "Aster ARM64 probe: repeated initialization changed the result");
                finish(Activity.RESULT_CANCELED, result);
                return;
            }
            result.putString("stream", first);
            finish(Activity.RESULT_OK, result);
        } catch (LinkageError e) {
            result.putString("stream", e.toString());
            finish(Activity.RESULT_CANCELED, result);
        }
    }
}
