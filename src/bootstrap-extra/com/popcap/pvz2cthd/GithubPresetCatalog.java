package com.popcap.pvz2cthd;

import android.app.Activity;
import android.util.AtomicFile;
import android.util.Log;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;
import javax.net.ssl.HttpsURLConnection;
import org.json.*;

final class GithubPresetCatalog {
    private static final String REPOSITORY = "EndiVee233/PvZ2-Unline";
    private static final String DIRECTORY = "pvp-presets";
    private static final int MAX_FILES = 1000;
    private static final int MAX_INDEX_BYTES = 2 * 1024 * 1024;
    private static final int ENTRY_WORDS = 224;
    private static final ExecutorService SYNC = Executors.newSingleThreadExecutor();
    private static volatile int generation;

    // Call and publication run on the UI thread. The cache and network use workers.
    static void refresh(Activity activity, boolean enabled) {
        final int request = ++generation;
        PresetEditor.send(8, 0);
        SYNC.execute(() -> load(activity, enabled, enabled, request));
    }

    static void reloadLocal(Activity activity, boolean enabled) {
        final int request = generation;
        SYNC.execute(() -> load(activity, enabled, false, request));
    }

    private static void load(Activity activity, boolean enabled, boolean download, int request) {
        if (request != generation) return;
        try {
            PvpPresetDocument.Catalogue plants = new PvpPresetDocument.Catalogue(new String(
                PvpPresetDocument.read(activity.getAssets().open("pvp-presets/catalogue.json")), StandardCharsets.UTF_8));
            PvpLevelStorage storage = new PvpLevelStorage(activity);
            File cache = enabled ? storage.github() : null;
            if (cache != null) migrateCache(activity, cache);
            publish(request, readPool(storage, cache, plants));
            if (download && request == generation) {
                sync(cache, request);
                publish(request, readPool(storage, cache, plants));
            }
        } catch (Exception e) {
            Log.i("PvpPresetEditor", "PVP level load failed (" + e.getClass().getSimpleName() + ")", e);
        }
    }

    private static void publish(int request, int[] pool) {
        PresetEditor.UI.post(() -> {
            if (request == generation) PresetEditor.send(8, pool);
        });
    }

    private static final class RemoteFile {
        final String name, sha;
        final int size;

        RemoteFile(String name, String sha, int size) {
            this.name = name;
            this.sha = sha;
            this.size = size;
        }

        AtomicFile cacheFile(File cache) { return new AtomicFile(new File(cache, sha + ".json")); }
    }

    private static List<RemoteFile> listing(byte[] bytes) throws Exception {
        PvpPresetDocument.checkDepth(bytes);
        JSONArray entries = new JSONArray(new String(bytes, StandardCharsets.UTF_8));
        if (entries.length() > MAX_FILES) throw new IOException("Too many GitHub directory entries");
        ArrayList<RemoteFile> result = new ArrayList<>();
        for (int i = 0; i < entries.length(); i++) {
            JSONObject entry = entries.getJSONObject(i);
            String name = entry.optString("name"), sha = entry.optString("sha");
            int size = entry.optInt("size", -1);
            if (!"file".equals(entry.optString("type")) || !name.endsWith(".json") || name.equals("catalog.json") ||
                name.indexOf('/') >= 0 || name.indexOf('\\') >= 0 || !sha.matches("[a-f0-9]{40}") ||
                size <= 0 || size > PvpPresetDocument.MAX_BYTES) continue;
            result.add(new RemoteFile(name, sha, size));
        }
        return result;
    }

    private static void migrateCache(Activity activity, File cache) {
        File index = new File(cache, "directory.json");
        if (index.exists()) return;
        File previous = new File(activity.getCacheDir(), "pvp-github-formations");
        try {
            byte[] data = read(new AtomicFile(new File(previous, "directory.json")).openRead(), MAX_INDEX_BYTES);
            for (RemoteFile file : listing(data)) {
                if (!file.cacheFile(previous).getBaseFile().isFile()) continue;
                byte[] contents = PvpPresetDocument.read(file.cacheFile(previous).openRead());
                if (matchesBlob(file, contents)) PvpLevelStorage.write(file.cacheFile(cache).getBaseFile(), contents);
            }
            PvpLevelStorage.write(index, data);
        } catch (Exception ignored) {
            // The old cache is optional and may have been reclaimed by Android.
        }
    }

    private static void sync(File cache, int request) throws Exception {
        Endpoint api = new Endpoint("api.github.com", "140.82.113.5", "20.27.177.116");
        byte[] directory = api.fetch("/repos/" + REPOSITORY + "/contents/" + DIRECTORY + "?ref=main", MAX_INDEX_BYTES);
        List<RemoteFile> files = listing(directory);
        if (request != generation) return;
        Endpoint raw = new Endpoint("raw.githubusercontent.com", "185.199.108.133", "185.199.109.133");
        ExecutorService downloads = Executors.newFixedThreadPool(4);
        HashSet<String> scheduled = new HashSet<>();
        try {
            List<Future<?>> pending = new ArrayList<>();
            for (RemoteFile file : files) {
                if (!scheduled.add(file.sha) || file.cacheFile(cache).getBaseFile().isFile()) continue;
                pending.add(downloads.submit(() -> {
                    if (request != generation) return;
                    try {
                        String path = new URI(null, null, "/" + REPOSITORY + "/main/" + DIRECTORY + "/" + file.name, null).toASCIIString();
                        byte[] data = raw.fetch(path, PvpPresetDocument.MAX_BYTES);
                        if (!matchesBlob(file, data)) throw new IOException("Git blob changed during sync");
                        if (request == generation) PvpLevelStorage.write(file.cacheFile(cache).getBaseFile(), data);
                    } catch (Exception e) {
                        Log.w("PvpPresetEditor", "Skipped GitHub formation " + file.name + " (" + e.getClass().getSimpleName() + ")");
                    }
                }));
            }
            for (Future<?> pendingFile : pending) pendingFile.get();
        } finally { downloads.shutdownNow(); }
        if (request != generation) return;
        PvpLevelStorage.write(new File(cache, "directory.json"), directory);
        File[] blobs = cache.listFiles((dir, name) -> name.matches("[a-f0-9]{40}\\.json"));
        if (blobs != null) for (File blob : blobs) {
            if (!scheduled.contains(blob.getName().substring(0, 40))) new AtomicFile(blob).delete();
        }
        Log.i("PvpPresetEditor", "GitHub level directory synced: " + files.size());
    }

    private static boolean matchesBlob(RemoteFile file, byte[] data) throws Exception {
        if (data.length != file.size) return false;
        MessageDigest digest = MessageDigest.getInstance("SHA-1");
        digest.update(("blob " + data.length + "\0").getBytes(StandardCharsets.US_ASCII));
        byte[] hash = digest.digest(data);
        StringBuilder hex = new StringBuilder(40);
        for (byte b : hash) {
            hex.append(Character.forDigit((b >>> 4) & 15, 16));
            hex.append(Character.forDigit(b & 15, 16));
        }
        return file.sha.contentEquals(hex);
    }

    private static int[] readPool(PvpLevelStorage storage, File cache, PvpPresetDocument.Catalogue plants) {
        Pool pool = new Pool();
        for (File local : storage.localLevels()) {
            if (pool.full()) break;
            try {
                pool.add("local/" + local.getName(), PvpPresetDocument.read(new FileInputStream(local)), plants);
            } catch (Exception ignored) {
                // Individual invalid files cannot block the rest of the library.
            }
        }
        int localCount = pool.words[0];
        if (cache != null) try {
            AtomicFile index = new AtomicFile(new File(cache, "directory.json"));
            for (RemoteFile file : listing(read(index.openRead(), MAX_INDEX_BYTES))) {
                if (pool.full()) break;
                try {
                    byte[] data = PvpPresetDocument.read(file.cacheFile(cache).openRead());
                    if (matchesBlob(file, data)) pool.add(file.name, data, plants);
                    else file.cacheFile(cache).delete();
                } catch (Exception ignored) {
                    // An unavailable cache entry leaves other levels usable.
                }
            }
        } catch (Exception ignored) {
            // No usable GitHub index yet.
        }
        Log.i("PvpPresetEditor", "PVP level library loaded: local=" + localCount + ", github=" + (pool.words[0] - localCount));
        return Arrays.copyOf(pool.words, 1 + pool.words[0] * ENTRY_WORDS);
    }

    private static final class Pool {
        final int[] words = new int[1 + MAX_FILES * ENTRY_WORDS];
        final HashSet<Integer> seeds = new HashSet<>();

        boolean full() { return words[0] == MAX_FILES; }

        void add(String key, byte[] data, PvpPresetDocument.Catalogue plants) throws Exception {
            PvpPresetDocument formation = PvpPresetDocument.parse(data, plants);
            if (formation.plants.isEmpty()) return;
            byte[] hash = MessageDigest.getInstance("SHA-256").digest(key.getBytes(StandardCharsets.UTF_8));
            int seed = java.nio.ByteBuffer.wrap(hash).getInt();
            if (seed == 0 || !seeds.add(seed)) return;
            int at = 1 + words[0]++ * ENTRY_WORDS;
            words[at] = seed;
            words[at + 1] = formation.matchingTrophies();
            words[at + 2] = formation.plants.size();
            for (int j = 0, offset = 0; offset < formation.name.length(); j++) {
                int point = formation.name.codePointAt(offset);
                words[at + 3 + j] = point;
                offset += Character.charCount(point);
            }
            words[at + 43] = formation.effectiveSpecial() ? formation.appearance + 1 : 0;
            for (int j = 0; j < formation.plants.size(); j++)
                System.arraycopy(formation.plants.get(j), 0, words, at + 44 + 4 * j, 4);
        }
    }

    private static byte[] read(InputStream stream, int limit) throws IOException {
        try (InputStream in = stream; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            for (int n; (n = in.read(buffer)) != -1;) {
                if (out.size() + n > limit) throw new IOException("GitHub response exceeds size limit");
                out.write(buffer, 0, n);
            }
            return out.toByteArray();
        }
    }

    private static final class Endpoint {
        final String host;
        final String[] edges;
        volatile String workingEdge;

        Endpoint(String host, String... edges) {
            this.host = host;
            this.edges = edges;
        }

        byte[] fetch(String path, int limit) throws IOException {
            URL source = new URL("https", host, path);
            String cachedEdge = workingEdge;
            if (cachedEdge != null) {
                try { return download(edge(cachedEdge, path), limit); }
                catch (IOException ignored) { workingEdge = null; }
            }
            try {
                return download((HttpsURLConnection)source.openConnection(), limit);
            } catch (UnknownHostException | SocketTimeoutException | ConnectException directFailure) {
                ProxySelector selector = ProxySelector.getDefault();
                if (selector != null && !selector.select(URI.create(source.toString())).contains(Proxy.NO_PROXY))
                    throw directFailure;
                // WSA can have working routing and no DNS. Keep GitHub's TLS hostname check.
                IOException lastFailure = directFailure;
                for (String address : edges) {
                    try {
                        byte[] result = download(edge(address, path), limit);
                        workingEdge = address;
                        return result;
                    } catch (IOException edgeFailure) { lastFailure = edgeFailure; }
                }
                throw lastFailure;
            }
        }

        private HttpsURLConnection edge(String address, String path) throws IOException {
            HttpsURLConnection connection = (HttpsURLConnection)new URL("https", address, path).openConnection(Proxy.NO_PROXY);
            connection.setRequestProperty("Host", host);
            connection.setHostnameVerifier((ignored, session) ->
                HttpsURLConnection.getDefaultHostnameVerifier().verify(host, session));
            return connection;
        }

        private byte[] download(HttpsURLConnection connection, int limit) throws IOException {
            connection.setConnectTimeout(5000);
            connection.setReadTimeout(5000);
            connection.setInstanceFollowRedirects(false);
            connection.setRequestProperty("User-Agent", "PvZ2-Offline-Preset");
            try {
                int status = connection.getResponseCode();
                if (status != 200) throw new IOException("HTTP " + status);
                return read(connection.getInputStream(), limit);
            } finally { connection.disconnect(); }
        }
    }
}
