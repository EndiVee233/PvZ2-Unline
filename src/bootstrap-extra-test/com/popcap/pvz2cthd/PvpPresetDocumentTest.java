package com.popcap.pvz2cthd;
import java.io.*;
import java.nio.file.*;
import java.util.*;
public final class PvpPresetDocumentTest {
    static void check(boolean yes){if(!yes)throw new AssertionError();}
    public static void main(String[] args)throws Exception{
        PvpPresetDocument.Catalogue c=new PvpPresetDocument.Catalogue(new String(Files.readAllBytes(Paths.get(args[0])),"UTF-8"));
        PvpPresetDocument d=new PvpPresetDocument();d.name="混阶测试";d.trophies=37;d.tierMask=5;
        int pea=c.names.get("peashooter")[0];d.plants.add(new int[]{pea,0,0,1});d.plants.add(new int[]{pea,1,0,3});
        byte[] encoded=d.encode(c);PvpPresetDocument back=PvpPresetDocument.parse(encoded,c);
        check(back.name.equals(d.name)&&back.trophies==37&&back.tierMask==5&&Arrays.equals(d.nativeData(),back.nativeData()));
        int[] event=new int[11];event[0]=11;System.arraycopy(d.nativeData(),0,event,1,10);back.update(event);check(Arrays.equals(encoded,back.encode(c)));
        String source=new String(encoded,"UTF-8");
        String[] bad={source.replace("\"version\": 2","\"version\": 3"),source.replace("\"level\": 3","\"level\": 5"),source.replace("\"row\": 1","\"row\": 0"),source.replace("\"row\": 1","\"row\": 5"),source.replace("peashooter","unknown_plant"),source.replace("\"奖杯\": 37","\"奖杯\": 3.5"),source.replace("\"tierMask\": 5","\"tierMask\": 0"),"["+source+"]",source+source};
        for(String s:bad){check(!s.equals(source));boolean failed=false;try{PvpPresetDocument.parse(s.getBytes("UTF-8"),c);}catch(Exception expected){failed=true;}check(failed);}
        boolean failed=false;try{PvpPresetDocument.read(new ByteArrayInputStream(new byte[65537]));}catch(IOException expected){failed=true;}check(failed);
        d.name="";d.trophies=null;d.special=true;d.appearance=null;
        back=PvpPresetDocument.parse(d.encode(c),c);
        check(back.name.isEmpty()&&back.trophies==null&&back.matchingTrophies()==10&&!back.effectiveSpecial());
        d.name="彩蛋";d.trophies=0;d.appearance=PvpPresetDocument.probability("3.25");
        back=PvpPresetDocument.parse(d.encode(c),c);
        check(back.effectiveSpecial()&&back.appearance==325&&back.matchingTrophies()==0);
        check(!PvpPresetDocument.parse(new String(d.encode(c),"UTF-8")
            .replace("\"出现概率\": 3.25","\"出现概率\": null").getBytes("UTF-8"),c).effectiveSpecial());
        byte[] legacy=source.replace("\"version\": 2","\"version\": 1")
            .replace("\"名字\"","\"name\"").replace("\"奖杯\"","\"trophies\"").replace("\"阵容\"","\"plants\"").getBytes("UTF-8");
        check(PvpPresetDocument.parse(legacy,c).trophies==37);
        if(!c.forbidden.isEmpty()){
            int sunflower=c.names.get("sunflower")[0];
            check(c.forbidden.contains(sunflower)&&!c.forbidden.contains(pea));
            byte[] old=source.replaceFirst("peashooter","sunflower").getBytes("UTF-8");
            PvpPresetDocument cleaned=PvpPresetDocument.parseForEdit(old,c);
            check(cleaned.omittedPlants==1&&cleaned.plants.size()==1&&cleaned.plants.get(0)[3]==3);
            check(PvpPresetDocument.parse(cleaned.encode(c),c).plants.size()==1);
            failed=false;try{PvpPresetDocument.parse(old,c);}catch(IOException expected){failed=true;}check(failed);
        }
        System.out.println("PASS: single-stage format, mixed ranks, optional metadata, special fallback, legacy import and validation");
    }
}
