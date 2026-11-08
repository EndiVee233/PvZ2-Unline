package com.popcap.pvz2cthd;

import android.content.Context;
import android.content.res.AssetFileDescriptor;
import android.media.AudioAttributes;
import android.media.MediaPlayer;
import android.os.SystemClock;
import android.util.Log;
import java.io.IOException;

/** Runs on Android's main thread. The lobby, map and lab share one player. */
public final class PvpMusic {
    private static final String TAG = "PvpMusic";
    private static final long FADE_MS = 900;
    private static final long FADE_STEP_MS = 25;
    private static final Runnable FADE = PvpMusic::advanceFade;
    private static MediaPlayer player;
    private static int track;
    private static float gain;
    private static float fadeGain;
    private static long fadeStart;
    private static boolean prepared;
    private static boolean foreground;

    static void update(Context context, int state) {
        int next = state & 3;
        gain = Math.max(0f, Math.min(1f, Float.intBitsToFloat(state & ~3)));
        if (next == track) {
            if (prepared) applyGain();
            return;
        }
        release();
        track = next;
        if (track == 0) return;
        String asset = track == 1 ? "pvp-music/street.mp3" : "pvp-music/battle.mp3";
        MediaPlayer candidate = new MediaPlayer();
        player = candidate;
        try (AssetFileDescriptor source = context.getAssets().openFd(asset)) {
            candidate.setAudioAttributes(new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_GAME).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build());
            candidate.setDataSource(source.getFileDescriptor(), source.getStartOffset(), source.getLength());
            candidate.setOnPreparedListener(PvpMusic::ready);
            candidate.setOnErrorListener((failed, what, extra) -> {
                if (failed == player) fallback("MediaPlayer error " + what + "/" + extra, null);
                return true;
            });
            candidate.prepareAsync();
        } catch (IOException | RuntimeException error) {
            fallback("Could not open " + asset, error);
        }
    }

    private static void ready(MediaPlayer candidate) {
        if (candidate != player) return;
        try {
            candidate.setLooping(true);
            applyGain();
            prepared = true;
            PresetEditor.send(9, track);
            if (foreground) startPlayback();
            Log.i(TAG, "Prepared track " + track + " loop=true gain=" + gain + " fadeMs=" + FADE_MS
                + " durationMs=" + candidate.getDuration());
        } catch (RuntimeException error) {
            fallback("Could not start PvP music", error);
        }
    }

    public static void setForeground(boolean active) {
        foreground = active;
        if (!prepared) return;
        try {
            if (active && !player.isPlaying()) startPlayback();
            else if (!active) {
                PresetEditor.UI.removeCallbacks(FADE);
                if (player.isPlaying()) player.pause();
            }
        } catch (RuntimeException error) {
            fallback("Could not change PvP playback state", error);
        }
    }

    private static void startPlayback() {
        player.start();
        if (fadeGain < 1f) {
            fadeStart = SystemClock.uptimeMillis() - Math.round(fadeGain * FADE_MS);
            advanceFade();
        }
    }

    private static void advanceFade() {
        if (!prepared || !foreground) return;
        fadeGain = Math.min(1f, (SystemClock.uptimeMillis() - fadeStart) / (float) FADE_MS);
        try {
            applyGain();
            if (fadeGain < 1f) PresetEditor.UI.postDelayed(FADE, FADE_STEP_MS);
            else Log.i(TAG, "Fade complete for track " + track);
        } catch (RuntimeException error) {
            fallback("Could not fade in PvP music", error);
        }
    }

    private static void applyGain() {
        float volume = gain * fadeGain;
        player.setVolume(volume, volume);
    }

    public static void shutdown() {
        release();
        track = 0;
        foreground = false;
        PresetEditor.send(9, 0);
    }

    private static void fallback(String message, Throwable error) {
        Log.w(TAG, message, error);
        release();
        PresetEditor.send(9, 0);
    }

    private static void release() {
        PresetEditor.UI.removeCallbacks(FADE);
        if (player != null) {
            player.release();
            Log.i(TAG, "Released track " + track);
        }
        player = null;
        prepared = false;
        fadeGain = 0f;
    }
}
