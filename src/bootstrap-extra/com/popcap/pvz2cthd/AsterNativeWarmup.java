package com.popcap.pvz2cthd;

import android.app.Activity;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.widget.TextView;
import java.lang.ref.WeakReference;
import java.lang.reflect.Field;
import java.lang.reflect.Method;

/** Keep the visible bootstrap responsive while Android/Houdini loads libraries. */
public final class AsterNativeWarmup {
    private static final String TAG = "AsterNativeWarmup";
    private static final Handler UI = new Handler(Looper.getMainLooper());
    private static boolean loading, loaded;
    private static WeakReference<Activity> waiting = new WeakReference<Activity>(null);

    public static void prepare(final Activity activity) {
        synchronized (AsterNativeWarmup.class) {
            waiting = new WeakReference<Activity>(activity);
            if (loaded) { launch(activity); return; }
            status(activity, "正在启动游戏…");
            if (loading) return;
            loading = true;
        }
        new Thread(new Runnable() {
            public void run() {
                Throwable failure = null;
                try {
                    // This class is merged into BootActivity's existing DEX,
                    // retaining the same application class loader/namespace.
                    for (String library : new String[]{"Src", "czProject", "HookPVZ2", "Restart"}) {
                        Log.i(TAG, "Loading " + library + " on " + Thread.currentThread().getName());
                        System.loadLibrary(library);
                    }
                } catch (Throwable error) { failure = error; Log.e(TAG, "Native loading failed", error); }
                final Throwable result = failure;
                UI.post(new Runnable() {
                    public void run() {
                        Activity current;
                        synchronized (AsterNativeWarmup.class) {
                            loading = false; loaded = result == null; current = waiting.get();
                        }
                        if (current == null || current.isFinishing() || current.isDestroyed()) return;
                        if (result == null) {
                            Log.i(TAG, "Native libraries ready; launching game");
                            launch(current);
                        } else status(current, "启动失败，请关闭后重试");
                    }
                });
            }
        }, "AsterNativeLoad").start();
    }

    private static void status(Activity activity, String message) {
        try {
            Field field = activity.getClass().getDeclaredField("statusView");
            field.setAccessible(true);
            Object value = field.get(activity);
            if (value instanceof TextView) ((TextView)value).setText(message);
        } catch (ReflectiveOperationException ignored) { }
    }

    private static void launch(Activity activity) {
        if (activity.isFinishing() || activity.isDestroyed()) return;
        try {
            Method method = activity.getClass().getDeclaredMethod("asterLaunchReady");
            method.setAccessible(true); method.invoke(activity);
        } catch (ReflectiveOperationException error) {
            Log.e(TAG, "Game launch callback failed", error);
            status(activity, "启动失败，请关闭后重试");
        }
    }
}
