package com.popcap.pvz2cthd;

import org.json.*;
import java.io.*;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Versioned, data-only interchange. Never accepts paths, scripts or resource URLs. */
public final class PvpPresetDocument {
    public static final int MAX_BYTES=65536;
    public String name="";
    public Integer trophies, appearance;
    public boolean special;
    public int tierMask=1;
    int omittedPlants;
    public final ArrayList<int[]> plants=new ArrayList<>();
    public static final class Catalogue {
        final HashMap<String,int[]> names=new HashMap<>();
        final HashMap<Integer,String> ids=new HashMap<>();
        final HashSet<Integer> forbidden=new HashSet<>();
        public Catalogue(String json) throws Exception {
            JSONArray all=new JSONArray(json);
            for(int i=0;i<all.length();i++) {JSONObject p=all.getJSONObject(i);
                int id=p.getInt("id");String name=p.getString("name");
                names.put(name,new int[]{id,p.getInt("maxLevel")});ids.put(id,name);
                if(!p.optBoolean("allowed",true))forbidden.add(id);
            }
        }
    }
    public static byte[] read(InputStream stream) throws IOException {
        if(stream==null)throw new IOException("无法打开文件");
        try(InputStream in=stream;ByteArrayOutputStream out=new ByteArrayOutputStream()) {
            byte[] buf=new byte[4096];int n;
            while((n=in.read(buf))!=-1){if(out.size()+n>MAX_BYTES)throw new IOException("文件超过64KB限制");out.write(buf,0,n);}
            return out.toByteArray();
        }
    }
    static int integer(JSONObject o,String key,int min,int max) throws Exception {
        Object v=o.get(key);if(!(v instanceof Number)||((Number)v).doubleValue()!=((Number)v).intValue())throw new IOException(key+"必须是整数");
        int n=((Number)v).intValue();if(n<min||n>max)throw new IOException(key+"超出范围");return n;
    }
    static String validName(String value) throws IOException {
        String name=value.trim();
        if(name.codePointCount(0,name.length())>39)throw new IOException("名字最多39字");
        for(int i=0;i<name.length();){
            int ch=name.codePointAt(i);
            if(Character.isISOControl(ch)||(ch>=0xd800&&ch<=0xdfff))
                throw new IOException("名字不能包含控制字符");
            i+=Character.charCount(ch);
        }
        return name;
    }
    static int probability(String text) throws IOException {
        try {
            int value=new BigDecimal(text).movePointRight(2).intValueExact();
            if(value>=0&&value<=10000)return value;
        } catch(ArithmeticException | NumberFormatException ignored) {}
        throw new IOException("出现概率须为0～100，最多两位小数");
    }
    public boolean effectiveSpecial(){
        return special&&!name.isEmpty()&&trophies!=null&&appearance!=null;
    }
    public int matchingTrophies(){
        if(trophies!=null)return trophies;
        int score=plants.size()*2;
        for(int[] plant:plants)score+=(plant[3]-1)*3;
        return Math.min(150,score);
    }
    static void checkDepth(byte[] bytes) throws IOException {
        int depth=0;boolean quoted=false,escaped=false;
        for(byte ch:bytes){
            if(quoted){
                if(escaped)escaped=false;
                else if(ch=='\\')escaped=true;
                else if(ch=='"')quoted=false;
            }else if(ch=='"')quoted=true;
            else if(ch=='['||ch=='{'){
                if(++depth>16)throw new IOException("JSON嵌套过深");
            }else if(ch==']'||ch=='}'){
                if(--depth<0)throw new IOException("JSON括号不匹配");
            }
        }
        if(depth!=0||quoted)throw new IOException("JSON不完整");
    }
    public static PvpPresetDocument parse(byte[] bytes,Catalogue c) throws Exception {
        return parse(bytes,c,false);
    }
    static PvpPresetDocument parseForEdit(byte[] bytes,Catalogue c) throws Exception {
        return parse(bytes,c,true);
    }
    private static PvpPresetDocument parse(byte[] bytes,Catalogue c,boolean omitForbidden) throws Exception {
        if(bytes.length>MAX_BYTES)throw new IOException("文件过大");
        checkDepth(bytes);
        JSONTokener input=new JSONTokener(new String(bytes,StandardCharsets.UTF_8));
        Object value=input.nextValue();
        if(!(value instanceof JSONObject)||input.nextClean()!=0)throw new IOException("一个文件只允许一个PVP关卡");
        JSONObject root=(JSONObject)value;
        if(!"pvz2-offline-pvp".equals(root.getString("format")))throw new IOException("不是支持的PVP预设文件");
        int version=integer(root,"version",1,2);
        if(integer(root,"columns",9,9)!=9||integer(root,"rows",5,5)!=5)throw new IOException("草坪尺寸不受支持");
        PvpPresetDocument d=new PvpPresetDocument();
        String nameKey=version==1?"name":"名字",cupsKey=version==1?"trophies":"奖杯";
        if(!root.isNull(nameKey)) {
            Object name=root.get(nameKey);
            if(!(name instanceof String))throw new IOException("名字必须是文字");
            d.name=validName((String)name);
        }
        if(!root.isNull(cupsKey)&&!"".equals(root.get(cupsKey)))d.trophies=integer(root,cupsKey,0,99999);
        if(version==2){
            d.special=Boolean.TRUE.equals(root.opt("特殊值"));
            Object chance=root.opt("出现概率");
            if(chance instanceof Number){
                try{d.appearance=probability(chance.toString());}catch(IOException ignored){}
            }
        }
        d.tierMask=integer(root,"tierMask",1,15);
        JSONArray a=root.getJSONArray(version==1?"plants":"阵容");if(a.length()>45)throw new IOException("植物不能超过45株");
        boolean[] occupied=new boolean[45];
        for(int i=0;i<a.length();i++){JSONObject p=a.getJSONObject(i);int[] spec=c.names.get(p.getString("type"));
            if(spec==null)throw new IOException("未知植物："+p.getString("type"));
            int row=integer(p,"row",0,4),col=integer(p,"column",0,8),level=integer(p,"level",1,spec[1]);
            if(occupied[row*9+col])throw new IOException("同一格有重复植物");occupied[row*9+col]=true;
            if(c.forbidden.contains(spec[0])){
                if(!omitForbidden)throw new IOException("预设禁止使用此植物："+p.getString("type"));
                d.omittedPlants++;
                continue;
            }
            d.plants.add(new int[]{spec[0],row,col,level});d.tierMask|=1<<(level-1);
        }return d;
    }
    public int[] nativeData(){int[] out=new int[2+4*plants.size()];out[0]=tierMask;out[1]=plants.size();
        for(int i=0;i<plants.size();i++)System.arraycopy(plants.get(i),0,out,2+i*4,4);return out;}
    public void update(int[] event) throws IOException {
        if(event.length<3||event[0]!=11||event[2]<0||event[2]>45||event.length!=3+4*event[2])throw new IOException("阵容导出不完整");
        tierMask=event[1];plants.clear();for(int i=0;i<event[2];i++)plants.add(Arrays.copyOfRange(event,3+i*4,7+i*4));
    }
    public byte[] encode(Catalogue c) throws Exception {
        JSONObject r=new JSONObject();r.put("format","pvz2-offline-pvp");r.put("version",2);
        r.put("名字",name);r.put("奖杯",trophies==null?JSONObject.NULL:trophies);r.put("特殊值",special);
        r.put("出现概率",appearance==null?JSONObject.NULL:BigDecimal.valueOf(appearance,2));
        r.put("columns",9);r.put("rows",5);r.put("tierMask",tierMask);JSONArray a=new JSONArray();
        for(int[] p:plants){String alias=c.ids.get(p[0]);if(alias==null)throw new IOException("无法导出未知植物");
            if(c.forbidden.contains(p[0]))throw new IOException("预设禁止使用此植物："+alias);
            JSONObject v=new JSONObject();v.put("type",alias);v.put("row",p[1]);v.put("column",p[2]);v.put("level",p[3]);a.put(v);}
        r.put("阵容",a);byte[] out=(r.toString(2)+"\n").getBytes("UTF-8");parse(out,c);return out;
    }
}
