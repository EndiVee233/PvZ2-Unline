package com.popcap.SexyAppFramework;

import android.content.pm.PackageManager;

/** JNI registration contract used only by the isolated ARM64 diagnostic. */
public final class AndroidGameApp {
    public native boolean Native_GameAppInitialize(
        AndroidSurfaceView surface, AndroidHttpProxy http, PackageManager packages);
    public native void Native_GameAppTeardown();
}
