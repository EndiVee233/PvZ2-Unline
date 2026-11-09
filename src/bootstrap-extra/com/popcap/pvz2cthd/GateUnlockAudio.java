package com.popcap.pvz2cthd;

import android.content.Context;
import android.content.res.AssetFileDescriptor;
import android.media.AudioAttributes;
import android.media.MediaPlayer;
import android.util.Log;
import java.io.IOException;

/** One-shot branch gate audio. All MediaPlayer operations run on the UI thread. */
final class GateUnlockAudio {
    private static final String TAG = "GateUnlockAudio";
    private static final String ASSET = "map-audio/branch-unlock.mp3";
    private static final Runnable TIMEOUT = GateUnlockAudio::stop;
    private static MediaPlayer player;
    private static boolean foreground;
    private static int nextToken;
    private static int duckToken;

    static void setForeground(boolean active) {
        foreground = active;
        if (!active) stop();
    }

    static void play(Context context, int gainBits) {
        float gain = Math.max(0f, Math.min(1f, Float.intBitsToFloat(gainBits)));
        if (!foreground || !(gain > 0f)) return;
        stop();
        try (AssetFileDescriptor source = context.getAssets().openFd(ASSET)) {
            MediaPlayer candidate = new MediaPlayer();
            player = candidate;
            candidate.setAudioAttributes(new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_GAME).setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build());
            candidate.setDataSource(source.getFileDescriptor(), source.getStartOffset(), source.getLength());
            candidate.setOnPreparedListener(ready -> {
                if (ready != player || !foreground) return;
                try {
                    ready.setVolume(gain, gain);
                    duckToken = ++nextToken;
                    PresetEditor.send(10, duckToken);
                } catch (RuntimeException error) {
                    fail(error);
                }
            });
            candidate.setOnCompletionListener(done -> { if (done == player) stop(); });
            candidate.setOnErrorListener((failed, what, extra) -> {
                if (failed == player) fail(new IllegalStateException("MediaPlayer " + what + "/" + extra));
                return true;
            });
            candidate.prepareAsync();
            PresetEditor.UI.postDelayed(TIMEOUT, 5000);
        } catch (IOException | RuntimeException error) {
            fail(error);
        }
    }

    static void duckApplied(int token) {
        if (player == null || !foreground || token != duckToken) return;
        try {
            int duration = player.getDuration();
            player.start();
            PresetEditor.UI.removeCallbacks(TIMEOUT);
            PresetEditor.UI.postDelayed(TIMEOUT, duration > 0 ? duration + 1000L : 12000L);
            Log.i(TAG, "Started one-shot, durationMs=" + duration);
        } catch (RuntimeException error) {
            fail(error);
        }
    }

    private static void fail(Exception error) {
        Log.w(TAG, "Could not play branch gate audio", error);
        stop();
    }

    private static void stop() {
        PresetEditor.UI.removeCallbacks(TIMEOUT);
        if (duckToken != 0) {
            duckToken = 0;
            PresetEditor.send(10, 0);
        }
        MediaPlayer previous = player;
        player = null;
        if (previous != null) previous.release();
    }
}
