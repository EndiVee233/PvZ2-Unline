package com.popcap.pvz2cthd;

import android.content.Context;
import android.util.Log;
import java.io.*;
import java.lang.reflect.*;
import java.math.BigDecimal;
import java.security.MessageDigest;
import java.util.*;
import org.json.*;

/** Adds the shipped public preset as one independent player before game load. */
public final class PresetProfileImporter {
    static final String SOURCE_SHA = "ee08d895f7fb56670f8cb834896e6c90d8f67ab37a28f7404dd35425ae73b0c6";
    static final int LIMIT = 8 * 1024 * 1024;
    private PresetProfileImporter() {}

    public static void apply(Context context) {
        File scratch = new File(context.getCacheDir(), "preset-import-v86");
        try {
            File folder = new File(context.getFilesDir(), "userdataNo_Backup");
            File save = new File(folder, "pp.dat");
            File marker = new File(folder, ".preset-allone-v86");
            if (!save.isFile() || marker.isFile()) return;
            if (!scratch.isDirectory() && !scratch.mkdirs()) throw new IOException("scratch");
            File source = new File(scratch, "public-preset.dat");
            InputStream in = context.getAssets().open("pvz2tool/saves/save_1/pp.dat");
            try { write(source, read(in)); } finally { in.close(); }
            if (!SOURCE_SHA.equals(sha(read(source)))) throw new IOException("preset checksum");
            boolean added = importProfile(save, marker, source, scratch);
            Log.i("PresetImport", added ? "public all-one player added" : "public all-one player already present");
        } catch (Throwable error) {
            // A failed optional import must not prevent the existing game from
            // starting, replace an undecodable save, or log any private data.
            Log.e("PresetImport", "preset deferred: " + error.getClass().getSimpleName());
        } finally { clean(scratch); }
    }

    static boolean importProfile(File save, File marker, File preset, File scratch) throws Exception {
        if (!save.isFile() || marker.isFile()) return false;
        byte[] baseline = read(save);
        JSONObject before = decode(save, new File(scratch, "before.json"));
        JSONObject original = decode(preset, new File(scratch, "preset.json"));
        JSONArray templates = original.getJSONArray("objects");
        if (templates.length() != 1) throw new IOException("preset objects");
        JSONObject template = templates.getJSONObject(0);
        validatePreset(template);
        JSONObject expected = new JSONObject(before.toString());
        JSONArray objects = expected.getJSONArray("objects");
        String name = template.getJSONObject("objdata").getString("n") + " TEST";
        Set<String> used = new HashSet<String>();
        for (int i = 0; i < objects.length(); ++i) {
            JSONObject obj = objects.getJSONObject(i);
            String id = obj.optString("uid", "");
            used.add(id.toLowerCase(Locale.ROOT));
            if ("PlayerInfo".equals(obj.optString("objclass")) &&
                    name.equals(obj.getJSONObject("objdata").optString("n"))) {
                // Crash after save replacement but before marker creation:
                // recognize this same preset, never add a duplicate or reset it.
                atomicMarker(marker, id);
                return false;
            }
        }
        String uid = null;
        for (long id = 0x7e860001L; id < 0x7e860401L; ++id) {
            String candidate = String.format(Locale.ROOT, "1.0.%08x", id);
            if (!used.contains(candidate)) { uid = candidate; break; }
        }
        if (uid == null) throw new IOException("preset identities exhausted");
        JSONObject player = new JSONObject(template.toString());
        player.put("uid", uid);
        player.getJSONObject("objdata").put("n", name);
        objects.put(player);
        File json = new File(scratch, "merged.json");
        File encoded = new File(scratch, "merged.dat");
        write(json, expected.toString().getBytes("UTF-8"));
        codec("encodeAndEncrypt", json, encoded);
        JSONObject checked = decode(encoded, new File(scratch, "checked.json"));
        if (!same(expected, checked)) throw new IOException("roundtrip mismatch");
        // Protect against a running process or another importer changing the
        // baseline after it was decoded. This never overwrites its changes.
        if (!Arrays.equals(baseline, read(save))) throw new IOException("save changed");
        File temporary = new File(save.getParentFile(), "pp.dat.preset-v86.tmp");
        try {
            write(temporary, read(encoded));
            if (!temporary.renameTo(save)) throw new IOException("save replace");
        } finally { if (temporary.exists()) temporary.delete(); }
        // Do not touch the game's existing pp.dat.bak or current-player prefs.
        atomicMarker(marker, uid);
        return true;
    }

    static void validatePreset(JSONObject player) throws Exception {
        if (!"PlayerInfo".equals(player.getString("objclass"))) throw new IOException("preset class");
        JSONObject data = player.getJSONObject("objdata");
        JSONArray plants = data.getJSONArray("p"), levels = data.getJSONArray("psla");
        Set<Integer> ids = new HashSet<Integer>(), graded = new HashSet<Integer>();
        for (int i=0;i<plants.length();++i) ids.add(plants.getInt(i));
        for (int i=0;i<levels.length();++i) {
            JSONObject level=levels.getJSONObject(i);
            if (level.getInt("icl")!=1 || !graded.add(level.getInt("icpi"))) throw new IOException("preset tier");
        }
        if (ids.size()!=109 || !ids.equals(graded)) throw new IOException("preset roster");
    }

    static JSONObject decode(File source, File json) throws Exception {
        codec("decodeAuto", source, json);
        return new JSONObject(new String(read(json), "UTF-8"));
    }

    // Reuse the APK's own RTON/crypto implementation. Its API is suspending;
    // runBlocking waits for completion instead of passing a null continuation.
    static void codec(final String operation, final File input, final File output) throws Exception {
        final Class<?> continuation = Class.forName("kotlin.coroutines.Continuation");
        Class<?> function = Class.forName("kotlin.jvm.functions.Function2");
        Class<?> coroutineContext = Class.forName("kotlin.coroutines.CoroutineContext");
        final Object rton = Class.forName("io.github.dreammooncai.pvz2tool.pop.rton.RTON").getConstructor().newInstance();
        final Method convert = rton.getClass().getMethod(operation, File.class, File.class, continuation);
        Object block = Proxy.newProxyInstance(function.getClassLoader(), new Class<?>[]{function}, new InvocationHandler() {
            public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
                if ("invoke".equals(method.getName())) {
                    try { return convert.invoke(rton, input, output, args[1]); }
                    catch (InvocationTargetException e) { throw e.getCause(); }
                }
                if ("toString".equals(method.getName())) return "PresetCodec";
                if ("hashCode".equals(method.getName())) return System.identityHashCode(proxy);
                if ("equals".equals(method.getName())) return proxy == args[0];
                throw new UnsupportedOperationException(method.getName());
            }
        });
        Method run = Class.forName("kotlinx.coroutines.BuildersKt").getMethod("runBlocking$default", coroutineContext, function, int.class, Object.class);
        try { run.invoke(null, null, block, 1, null); }
        catch (InvocationTargetException e) { throw new IOException("codec " + operation, e.getCause()); }
        if (!output.isFile() || output.length()==0 || output.length()>LIMIT) throw new IOException("codec output");
    }

    static boolean same(Object a,Object b) throws JSONException {
        if (a==JSONObject.NULL || b==JSONObject.NULL) return a==b;
        if (a instanceof JSONObject && b instanceof JSONObject) {
            JSONObject x=(JSONObject)a,y=(JSONObject)b;
            if(x.length()!=y.length())return false;
            Iterator<String> keys=x.keys();while(keys.hasNext()){String k=keys.next();if(!y.has(k)||!same(x.get(k),y.get(k)))return false;}
            return true;
        }
        if(a instanceof JSONArray && b instanceof JSONArray){JSONArray x=(JSONArray)a,y=(JSONArray)b;if(x.length()!=y.length())return false;for(int i=0;i<x.length();++i)if(!same(x.get(i),y.get(i)))return false;return true;}
        if(a instanceof Number && b instanceof Number)return new BigDecimal(a.toString()).compareTo(new BigDecimal(b.toString()))==0;
        return a!=null && a.equals(b);
    }
    static byte[] read(File file) throws IOException {InputStream in=new FileInputStream(file);try{return read(in);}finally{in.close();}}
    static byte[] read(InputStream in) throws IOException {ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buffer=new byte[8192];int n;while((n=in.read(buffer))!=-1){if(out.size()+n>LIMIT)throw new IOException("size");out.write(buffer,0,n);}return out.toByteArray();}
    static void write(File file,byte[] data) throws IOException {FileOutputStream out=new FileOutputStream(file);try{out.write(data);out.getFD().sync();}finally{out.close();}}
    static void atomicMarker(File marker,String uid) throws IOException {File temp=new File(marker.getPath()+".tmp");try{write(temp,(SOURCE_SHA+"\n"+uid+"\n").getBytes("UTF-8"));if(!temp.renameTo(marker))throw new IOException("marker");}finally{if(temp.exists())temp.delete();}}
    static String sha(byte[] bytes) throws Exception {byte[] digest=MessageDigest.getInstance("SHA-256").digest(bytes);StringBuilder out=new StringBuilder();for(byte b:digest)out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();}
    static void clean(File folder) {File[] files=folder.listFiles();if(files!=null)for(File f:files)if(f.isFile())f.delete();folder.delete();}
}
