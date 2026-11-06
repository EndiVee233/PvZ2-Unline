package com.popcap.pvz2cthd;
import java.io.*;
import java.util.*;
import org.json.*;

/** Device-side codec test using public/synthetic fixtures only; never game saves. */
public final class PresetImporterTest {
    static void require(boolean ok,String what){if(!ok)throw new AssertionError(what);}
    public static void main(String[] args) throws Exception {
        File root=new File(args[0]);
        require(root.getName().equals("preset-public-unit-v86"),"fixture root");
        require(root.isDirectory()||root.mkdirs(),"mkdir");
        File preset=new File(root,"public-preset.dat"), save=new File(root,"pp.dat"), marker=new File(root,"import.marker");
        require(PresetProfileImporter.SOURCE_SHA.equals(PresetProfileImporter.sha(PresetProfileImporter.read(preset))),"public hash");
        JSONObject template=PresetProfileImporter.decode(preset,new File(root,"source.json"));
        PresetProfileImporter.validatePreset(template.getJSONArray("objects").getJSONObject(0));
        JSONObject original=new JSONObject(template.toString());
        JSONArray objects=original.getJSONArray("objects");
        JSONObject first=objects.getJSONObject(0);
        first.put("uid","1.0.7e860001");first.getJSONObject("objdata").put("n","SYNTHETIC ONE");
        first.getJSONObject("objdata").put("syntheticGuard",9007199254740993L);
        JSONObject second=new JSONObject(first.toString());second.put("uid","1.0.0000002a");second.getJSONObject("objdata").put("n","SYNTHETIC TWO");
        second.getJSONObject("objdata").getJSONArray("psla").getJSONObject(0).put("icl",4);objects.put(second);
        File json=new File(root,"existing.json");PresetProfileImporter.write(json,original.toString().getBytes("UTF-8"));
        PresetProfileImporter.codec("encodeAndEncrypt",json,save);
        File bak=new File(root,"pp.dat.bak");byte[] sentinel={1,3,7,9};PresetProfileImporter.write(bak,sentinel);
        marker.delete();
        require(PresetProfileImporter.importProfile(save,marker,preset,root),"first import");
        JSONObject after=PresetProfileImporter.decode(save,new File(root,"after.json"));
        JSONArray got=after.getJSONArray("objects");require(got.length()==3,"one player added");
        require(PresetProfileImporter.same(first,got.getJSONObject(0))&&PresetProfileImporter.same(second,got.getJSONObject(1)),"old profiles preserved");
        JSONObject added=got.getJSONObject(2);require(added.getString("uid").equals("1.0.7e860002"),"collision avoided");
        PresetProfileImporter.validatePreset(added);
        require(added.getJSONObject("objdata").getString("n").endsWith(" TEST"),"independent name");
        require(Arrays.equals(sentinel,PresetProfileImporter.read(bak)),"existing native backup preserved");
        byte[] once=PresetProfileImporter.read(save);
        require(!PresetProfileImporter.importProfile(save,marker,preset,root),"marker idempotency");
        require(Arrays.equals(once,PresetProfileImporter.read(save)),"no second write");
        marker.delete();require(!PresetProfileImporter.importProfile(save,marker,preset,root),"interrupted marker recovery");
        require(Arrays.equals(once,PresetProfileImporter.read(save))&&marker.isFile(),"no duplicate/reset");
        File corrupt=new File(root,"corrupt.dat"),badMarker=new File(root,"bad.marker");badMarker.delete();
        PresetProfileImporter.write(corrupt,new byte[]{5,4,3});boolean failed=false;
        try{PresetProfileImporter.importProfile(corrupt,badMarker,preset,root);}catch(Exception expected){failed=true;}
        require(failed&&!badMarker.exists()&&Arrays.equals(new byte[]{5,4,3},PresetProfileImporter.read(corrupt)),"corrupt source unchanged");
        require(!PresetProfileImporter.importProfile(new File(root,"absent.dat"),badMarker,preset,root),"no fresh-save replacement");
        System.out.println("PRESET_UNIT_OK public=109 tiers=1 existing_preserved=2 uid_collision=passed repeat=passed marker_recovery=passed backup_preserved=passed corruption=passed");
    }
}
