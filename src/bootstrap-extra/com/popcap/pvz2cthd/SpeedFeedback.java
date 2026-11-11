package com.popcap.pvz2cthd;

import android.app.Activity;
import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ValueAnimator;
import android.content.res.AssetFileDescriptor;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.media.AudioAttributes;
import android.media.SoundPool;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import java.io.IOException;

/** One-shot effects for successful speed changes. All calls run on the main thread. */
final class SpeedFeedback {
    private static final String TAG = "SpeedFeedback";
    private static final String[] ASSETS = {
        "game-audio/fast-forward-off.wav", "game-audio/fast-forward-on.wav"
    };
    private static final int[] samples = new int[ASSETS.length];
    private static final boolean[] ready = new boolean[ASSETS.length];
    private static SoundPool pool;
    private static boolean foreground;
    private static int stream;
    private static int pending = -1;
    private static float pendingGain;
    private static FlashView flash;
    private static ViewGroup flashHost;
    private static ValueAnimator flashAnimator;

    private static final class FlashView extends View {
        private final Paint paint = new Paint();

        FlashView(Activity activity) {
            super(activity);
            setFocusable(false);
            setFocusableInTouchMode(false);
            setClickable(false);
            setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
            paint.setColor(Color.WHITE);
            paint.setAlpha(89);
        }

        void setFlashAlpha(int alpha) {
            paint.setAlpha(alpha);
            invalidate();
        }

        @Override protected void onDraw(Canvas canvas) {
            canvas.drawRect(0, 0, getWidth(), getHeight(), paint);
        }
    }

    static void preload(Activity activity) {
        if (pool != null || activity.isDestroyed()) return;
        try {
            pool = new SoundPool.Builder().setMaxStreams(1)
                .setAudioAttributes(new AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_GAME)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build())
                .build();
            pool.setOnLoadCompleteListener((source, sample, status) -> {
                if (source != pool) return;
                for (int index = 0; index < samples.length; ++index) {
                    if (samples[index] != sample) continue;
                    ready[index] = status == 0;
                    if (!ready[index]) Log.w(TAG, "Could not decode " + ASSETS[index] + " status=" + status);
                    if (pending == index) {
                        pending = -1;
                        if (ready[index] && foreground) playSample(index, pendingGain);
                    }
                    return;
                }
            });
            for (int index = 0; index < ASSETS.length; ++index) {
                try (AssetFileDescriptor asset = activity.getAssets().openFd(ASSETS[index])) {
                    samples[index] = pool.load(asset, 1);
                }
            }
        } catch (IOException | RuntimeException error) {
            Log.w(TAG, "Could not preload speed cues", error);
        }
    }

    static void play(Activity activity, int mode, int gainBits) {
        if (!foreground || activity.isFinishing() || activity.isDestroyed() || mode < 1 || mode > 2) return;
        flash(activity);
        pending = -1;
        if (pool == null) return;
        if (stream != 0) {
            pool.stop(stream);
            stream = 0;
        }
        float gain = Math.min(1f, Float.intBitsToFloat(gainBits));
        if (!(gain > 0f)) return;
        int index = mode - 1;
        if (ready[index]) playSample(index, gain);
        else if (samples[index] != 0) {
            pending = index;
            pendingGain = gain;
        }
    }

    private static void playSample(int index, float gain) {
        stream = pool.play(samples[index], gain, gain, 1, 0, 1f);
        Log.i(TAG, "Speed " + (index + 1) + "x sound stream=" + stream);
    }

    private static void flash(Activity activity) {
        ViewGroup content = activity.findViewById(android.R.id.content);
        if (content == null || content.getWidth() <= 0 || content.getHeight() <= 0) return;
        clearFlash();
        // Keep the visible child used by WSA's SurfaceView compositor, but
        // animate paint opacity rather than View.alpha / a hardware layer.
        FlashView effect = new FlashView(activity);
        content.addView(effect, new ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        flash = effect;
        flashHost = content;
        ValueAnimator fade = ValueAnimator.ofInt(89, 0);
        flashAnimator = fade;
        fade.setDuration(150);
        fade.addUpdateListener(animation -> {
            if (flash == effect) effect.setFlashAlpha((Integer) animation.getAnimatedValue());
        });
        fade.addListener(new AnimatorListenerAdapter() {
            @Override public void onAnimationEnd(Animator animation) {
                if (flash == effect) clearFlash();
            }
        });
        fade.start();
        // Clean up even if a compositor/animator callback is cancelled or lost.
        content.postDelayed(() -> { if (flash == effect) clearFlash(); }, 250);
    }

    private static void clearFlash() {
        FlashView effect = flash;
        ViewGroup host = flashHost;
        ValueAnimator animation = flashAnimator;
        flash = null;
        flashHost = null;
        flashAnimator = null;
        if (animation != null) animation.cancel();
        if (effect == null || host == null) return;
        effect.setFlashAlpha(0);
        host.removeView(effect);
        host.requestLayout();
        host.invalidate();
        Log.i(TAG, "Speed flash cleared");
    }

    static void setForeground(boolean active) {
        foreground = active;
        if (active) return;
        pending = -1;
        clearFlash();
        if (pool != null && stream != 0) pool.stop(stream);
        stream = 0;
    }

    static void shutdown() {
        setForeground(false);
        if (pool != null) {
            pool.release();
            pool = null;
        }
        for (int index = 0; index < samples.length; ++index) {
            samples[index] = 0;
            ready[index] = false;
        }
    }
}
