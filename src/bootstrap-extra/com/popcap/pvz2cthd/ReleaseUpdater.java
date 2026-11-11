package com.popcap.pvz2cthd;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInstaller;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.Log;
import android.widget.Toast;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import java.net.ConnectException;
import java.net.Proxy;
import java.net.ProxySelector;
import java.net.SocketTimeoutException;
import java.net.URI;
import java.net.UnknownHostException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.net.ssl.HttpsURLConnection;
import org.json.JSONArray;
import org.json.JSONObject;

/** Checks published GitHub releases and stages an in-place Android package update. */
public final class ReleaseUpdater extends BroadcastReceiver {
    private static final String TAG = "UnlineUpdater";
    private static final String REPO = "EndiVee233/PvZ2-Unline-Aster";
    private static final GithubPresetCatalog.Endpoint RELEASE_API = new GithubPresetCatalog.Endpoint(
            "api.github.com", "140.82.113.5", "20.27.177.116");
    private static final String DOWNLOAD = "https://github.com/" + REPO + "/releases/download/";
    private static final String RESULT = "com.popcap.pvz2cthd.action.UNLINE_UPDATE_RESULT";
    private static final String STAGING = "download_session";
    private static final int INSTALL_PERMISSION = 20803;
    private static final Pattern BUILD = Pattern.compile("(?:^|-)v([1-9][0-9]{0,7})$");
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final ExecutorService IO = Executors.newSingleThreadExecutor();

    // These fields are confined to the UI thread, including installer callbacks.
    private static Activity foreground;
    private static Runnable onResume;
    private static Intent systemConfirmation;
    private static Release waitingForPermission;
    private static boolean busy;

    private static final class Release {
        final int build;
        final URL url;
        final long size;
        final String sha256;

        Release(int build, URL url, long size, String sha256) {
            this.build = build;
            this.url = url;
            this.size = size;
            this.sha256 = sha256;
        }
    }

    public static void resume(Activity activity) {
        foreground = activity;
        if (systemConfirmation != null) showSystemConfirmation();
        if (onResume != null) {
            Runnable action = onResume;
            onResume = null;
            action.run();
        }
    }

    public static void pause(Activity activity) {
        if (foreground == activity) foreground = null;
    }

    static void check(Activity activity) {
        if (busy) {
            toast(activity, "正在检查、下载或安装更新。");
            return;
        }
        busy = true;
        Context context = activity.getApplicationContext();
        toast(context, "正在检查 GitHub 更新…");
        IO.execute(() -> {
            try {
                cleanInterruptedDownload(context);
                int current = buildNumber(context.getPackageManager().getPackageInfo(context.getPackageName(), 0).versionName);
                Release release = latest(current);
                MAIN.post(() -> whenForeground(() -> {
                    if (release == null) {
                        busy = false;
                        toast(context, "当前版本 v" + current + "，没有更新的正式版。");
                    } else {
                        Activity host = foreground;
                        new AlertDialog.Builder(host).setTitle("发现新版本")
                                .setMessage(String.format(Locale.ROOT,
                                        "当前 v%d，最新 v%d。更新包 %.2f GB，确认后将在后台下载并安装。",
                                        current, release.build, release.size / 1_000_000_000.0))
                                .setNegativeButton("取消", (dialog, button) -> busy = false)
                                .setOnCancelListener(dialog -> busy = false)
                                .setPositiveButton("安装", (dialog, button) -> requestInstall(host, release))
                                .show();
                    }
                }));
            } catch (Exception error) {
                failed(context, "检查更新失败，请稍后重试。", error);
            }
        });
    }

    private static void whenForeground(Runnable action) {
        if (foreground == null) onResume = action;
        else action.run();
    }

    private static int buildNumber(String value) throws IOException {
        Matcher match = BUILD.matcher(value == null ? "" : value);
        if (!match.find()) throw new IOException("Invalid build number: " + value);
        return Integer.parseInt(match.group(1));
    }

    private static Release latest(int current) throws Exception {
        byte[] document = RELEASE_API.fetch("/repos/" + REPO + "/releases/latest", 1024 * 1024);
        return parseRelease(new JSONObject(new String(document, StandardCharsets.UTF_8)), current);
    }

    private static Release parseRelease(JSONObject release, int current) throws Exception {
        if (release.optBoolean("draft") || release.optBoolean("prerelease")) throw new IOException("Not a public stable release");
        String tag = release.getString("tag_name");
        if (!tag.matches("v(?:[0-9]+\\.[0-9]+\\.[0-9]+-v)?[1-9][0-9]{0,7}")) {
            throw new IOException("Unrecognized release tag: " + tag);
        }
        int build = buildNumber(tag);
        if (build <= current) return null;
        String filename = "PvZ2-Unline-Aster-v" + build + ".apk";
        String expected = DOWNLOAD + tag + "/" + filename;
        JSONArray assets = release.getJSONArray("assets");
        for (int i = 0; i < assets.length(); i++) {
            JSONObject asset = assets.getJSONObject(i);
            if (!filename.equals(asset.optString("name")) || !"uploaded".equals(asset.optString("state"))) continue;
            long size = asset.getLong("size");
            String digest = asset.optString("digest");
            if (size > 0 && size <= 2_000_000_000L && digest.matches("sha256:[a-f0-9]{64}")
                    && expected.equals(asset.optString("browser_download_url"))) {
                return new Release(build, new URL(expected), size, digest.substring(7));
            }
        }
        throw new IOException("No matching verified APK in release " + tag);
    }

    private static HttpsURLConnection connect(URL url) throws IOException {
        for (int redirects = 0; redirects <= 5; redirects++) {
            String host = url.getHost();
            String[] edges;
            if (host.equals("github.com")) edges = new String[]{"20.27.177.113"};
            else if (host.equals("release-assets.githubusercontent.com") || host.equals("objects.githubusercontent.com")) {
                edges = new String[]{"185.199.109.133", "185.199.108.133", "185.199.110.133", "185.199.111.133"};
            } else throw new IOException("Unexpected GitHub host");
            if (!"https".equals(url.getProtocol()) || url.getUserInfo() != null
                    || (url.getPort() != -1 && url.getPort() != 443)) throw new IOException("Unexpected GitHub URL");
            HttpsURLConnection connection = connectDownload(url, edges);
            boolean connected = false;
            try {
                int status = connection.getResponseCode();
                if (status == 200) {
                    connected = true;
                    return connection;
                }
                String location = connection.getHeaderField("Location");
                if (status < 300 || status > 399 || location == null) throw new IOException("GitHub HTTP " + status);
                url = new URL(url, location);
            } finally {
                if (!connected) connection.disconnect();
            }
        }
        throw new IOException("Too many GitHub redirects");
    }

    private static HttpsURLConnection connectDownload(URL url, String[] edges) throws IOException {
        try {
            return openDownload((HttpsURLConnection) url.openConnection());
        } catch (UnknownHostException | ConnectException | SocketTimeoutException directFailure) {
            ProxySelector selector = ProxySelector.getDefault();
            if (selector != null && !selector.select(URI.create(url.toString())).contains(Proxy.NO_PROXY)) throw directFailure;
            IOException lastFailure = directFailure;
            GithubPresetCatalog.Endpoint endpoint = new GithubPresetCatalog.Endpoint(url.getHost());
            for (String edge : edges) {
                try { return openDownload(endpoint.edge(edge, url.getFile())); }
                catch (IOException error) { lastFailure = error; }
            }
            throw lastFailure;
        }
    }

    private static HttpsURLConnection openDownload(HttpsURLConnection connection) throws IOException {
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(15000);
        connection.setReadTimeout(30000);
        connection.setRequestProperty("User-Agent", "PvZ2-Unline-Updater");
        connection.setRequestProperty("Accept", "application/octet-stream");
        try {
            connection.getResponseCode();
            return connection;
        } catch (IOException error) {
            connection.disconnect();
            throw error;
        }
    }

    private static void requestInstall(Activity activity, Release release) {
        if (Build.VERSION.SDK_INT >= 26 && !activity.getPackageManager().canRequestPackageInstalls()) {
            waitingForPermission = release;
            try {
                activity.startActivityForResult(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                        Uri.parse("package:" + activity.getPackageName())), INSTALL_PERMISSION);
            } catch (RuntimeException error) {
                waitingForPermission = null;
                failed(activity, "无法打开安装授权，请在系统设置中允许本游戏安装应用后重试。", error);
            }
            return;
        }
        download(activity.getApplicationContext(), release);
    }

    static boolean onActivityResult(Activity activity, int request) {
        if (request != INSTALL_PERMISSION) return false;
        Release release = waitingForPermission;
        waitingForPermission = null;
        if (release != null && Build.VERSION.SDK_INT >= 26 && activity.getPackageManager().canRequestPackageInstalls()) {
            download(activity.getApplicationContext(), release);
        } else {
            busy = false;
            toast(activity, "未获得系统安装授权，更新已取消。");
        }
        return true;
    }

    private static void download(Context context, Release release) {
        toast(context, "开始后台下载 v" + release.build + "。");
        IO.execute(() -> {
            try {
                stage(context, release);
            } catch (Exception error) {
                failed(context, "更新下载或校验失败，请检查网络和可用空间后重试。", error);
            }
        });
    }

    private static void cleanInterruptedDownload(Context context) {
        int id = context.getSharedPreferences(TAG, 0).getInt(STAGING, -1);
        if (id < 0) return;
        PackageInstaller installer = context.getPackageManager().getPackageInstaller();
        if (installer.getSessionInfo(id) != null) installer.abandonSession(id);
        context.getSharedPreferences(TAG, 0).edit().remove(STAGING).apply();
    }

    private static void stage(Context context, Release release) throws Exception {
        PackageInstaller installer = context.getPackageManager().getPackageInstaller();
        PackageInstaller.SessionParams params = new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
        params.setAppPackageName(context.getPackageName());
        params.setSize(release.size);
        if (Build.VERSION.SDK_INT >= 31) params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED);
        if (Build.VERSION.SDK_INT >= 33) params.setPackageSource(PackageInstaller.PACKAGE_SOURCE_DOWNLOADED_FILE);
        int id = installer.createSession(params);
        boolean committed = false;
        try (PackageInstaller.Session session = installer.openSession(id)) {
            if (!context.getSharedPreferences(TAG, 0).edit().putInt(STAGING, id).commit()) throw new IOException("Cannot record update session");
            HttpsURLConnection connection = connect(release.url);
            try (InputStream input = connection.getInputStream(); OutputStream output = session.openWrite("base.apk", 0, release.size)) {
                MessageDigest digest = MessageDigest.getInstance("SHA-256");
                byte[] buffer = new byte[128 * 1024];
                long total = 0;
                int n;
                while ((n = input.read(buffer)) != -1) {
                    total += n;
                    if (total > release.size) throw new IOException("APK exceeds release size");
                    digest.update(buffer, 0, n);
                    output.write(buffer, 0, n);
                }
                StringBuilder hash = new StringBuilder(64);
                for (byte value : digest.digest()) hash.append(Character.forDigit((value & 0xff) >>> 4, 16))
                        .append(Character.forDigit(value & 0xf, 16));
                if (total != release.size || !release.sha256.contentEquals(hash)) throw new IOException("APK failed size or SHA-256 verification");
                session.fsync(output);
            } finally {
                connection.disconnect();
            }
            Intent callback = new Intent(context, ReleaseUpdater.class).setAction(RESULT);
            int flags = PendingIntent.FLAG_UPDATE_CURRENT;
            if (Build.VERSION.SDK_INT >= 31) flags |= PendingIntent.FLAG_MUTABLE;
            PendingIntent status = PendingIntent.getBroadcast(context, id, callback, flags);
            if (!context.getSharedPreferences(TAG, 0).edit().remove(STAGING).commit()) throw new IOException("Cannot finalize update session");
            session.commit(status.getIntentSender());
            committed = true;
        } finally {
            if (!committed) {
                try { installer.abandonSession(id); }
                catch (RuntimeException error) { Log.w(TAG, "Could not abandon update session", error); }
                context.getSharedPreferences(TAG, 0).edit().remove(STAGING).apply();
            }
        }
    }

    @Override public void onReceive(Context context, Intent intent) {
        if (!RESULT.equals(intent.getAction())) return;
        int status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE);
        if (status == PackageInstaller.STATUS_PENDING_USER_ACTION) {
            systemConfirmation = intent.getParcelableExtra(Intent.EXTRA_INTENT);
            busy = systemConfirmation != null;
            if (busy) showSystemConfirmation();
            else toast(context, "系统未能打开安装确认，请重试更新。");
            return;
        }
        busy = false;
        systemConfirmation = null;
        if (status == PackageInstaller.STATUS_SUCCESS) {
            toast(context, "更新安装完成，请重新打开游戏。");
        } else {
            Log.w(TAG, "Installation status " + status + ": " + intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE));
            toast(context, status == PackageInstaller.STATUS_FAILURE_ABORTED ? "安装已取消。" : "系统未能安装更新，请检查安装授权或可用空间后重试。");
        }
    }

    private static void showSystemConfirmation() {
        if (foreground == null) return;
        Intent confirmation = systemConfirmation;
        systemConfirmation = null;
        try { foreground.startActivity(confirmation); }
        catch (RuntimeException error) { failed(foreground, "无法打开系统安装确认，请重试。", error); }
    }

    private static void failed(Context context, String message, Exception error) {
        Log.w(TAG, message, error);
        MAIN.post(() -> { busy = false; toast(context, message); });
    }

    private static void toast(Context context, String text) {
        Toast.makeText(context, text, Toast.LENGTH_LONG).show();
    }
}
