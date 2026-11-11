package com.popcap.pvz2cthd;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.*;
import android.text.InputType;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Toast;
import java.io.*;
import java.math.BigDecimal;
import java.util.*;

/** UI and document provider bridge. Game calls are queued to its own GL thread. */
public final class PresetEditor {
    static final int OPEN=20801,SAVE=20802;
    static final Handler UI=new Handler(Looper.getMainLooper());
    static final ArrayDeque<int[]> COMMANDS=new ArrayDeque<>();
    static boolean loaded,failed;static PvpPresetDocument document, imported, newPreset;
    static PvpPresetDocument.Catalogue catalogue;
    static byte[] pendingExport;
    static PvpLevelStorage storage;
    private static File importedFile, documentFile;
    private static int lastMusicSample;
    static native int command(int cmd,int[] data);
    static native int[] poll();
    static native int musicSample();
    static Activity activity() throws Exception {
        return (Activity)Class.forName("com.popcap.SexyAppFramework.SexyAppFrameworkActivity").getMethod("instance").invoke(null);
    }
    public static void frame(){
        if(failed)return;
        try{
            if(!loaded){
                System.loadLibrary("PresetEditor");
                Activity current=activity();
                boolean network=options(current).getBoolean("network_enabled",false);
                command(5,new int[]{network?1:0});
                UI.post(()->{
                    SpeedFeedback.preload(current);
                    GithubPresetCatalog.refresh(current,network);
                });
                loaded=true;
            }
            int[] next; synchronized(COMMANDS){next=COMMANDS.poll();}
            if(next!=null){int result=command(next[0],Arrays.copyOfRange(next,1,next.length));
                if(next[0]==10){
                    if(result!=0&&next[1]!=0){int token=next[1];UI.post(()->GateUnlockAudio.duckApplied(token));}
                }else if(result==0)UI.post(()->message("暂时不能打开或修改预设，请退出当前关卡后从开始界面的设置重试。"));}
            int sample=musicSample();
            if(sample!=lastMusicSample){
                lastMusicSample=sample;
                Activity current=activity();
                UI.post(()->PvpMusic.update(current,sample));
            }
            final int[] event=poll();
            if(event!=null&&event.length>0){
                if(event[0]==17&&event.length==2){
                    Activity current=activity();
                    UI.post(()->GateUnlockAudio.play(current,event[1]));
                }else if(event[0]==18&&event.length==3){
                    Activity current=activity();
                    UI.post(()->SpeedFeedback.play(current,event[1],event[2]));
                }else UI.post(()->handle(event));
            }
        }catch(Throwable e){failed=true;android.util.Log.e("PvpPresetEditor","bridge failed",e);}
    }
    static void send(int cmd,int... data){int[] p=new int[data.length+1];p[0]=cmd;System.arraycopy(data,0,p,1,data.length);
        synchronized(COMMANDS){COMMANDS.add(p);}}
    static SharedPreferences options(Activity a){return a.getSharedPreferences("pvp-preset-options",0);}
    static void message(String text){
        try{Toast.makeText(activity(),text,Toast.LENGTH_LONG).show();}
        catch(Exception e){android.util.Log.e("PvpPresetEditor",text,e);}
    }
    static void init(Activity a)throws Exception{
        if(catalogue==null)catalogue=new PvpPresetDocument.Catalogue(new String(PvpPresetDocument.read(a.getAssets().open("pvp-presets/catalogue.json")),"UTF-8"));
        if(storage==null)storage=new PvpLevelStorage(a);
    }
    static void handle(int[] e){try{Activity a=activity();init(a);
        int event=e[0];
        if((event>=21&&event<=24)||(event>=41&&event<=44)){
            document=event>=41?imported:(newPreset==null?new PvpPresetDocument():newPreset);
            if(document==null)throw new IOException("请重新打开预设文件");
            documentFile=event>=41?importedFile:null;
            imported=null;importedFile=null;newPreset=null;
            document.tierMask=1<<(event-(event>=41?41:21));
            send(1,document.nativeData());
            return;
        }
        switch(event){
        case 3:
            imported=null;importedFile=null;
            Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT);
            i.setType("*/*");i.addCategory(Intent.CATEGORY_OPENABLE);
            a.startActivityForResult(i,OPEN);
            break;
        case 4:
            GithubPresetCatalog.reloadLocal(a,options(a).getBoolean("network_enabled",false));
            openLibrary(a);
            break;
        case 12:document=null;documentFile=null;break;
        case 11:save(a,e);break;
        case 13:message("当前阵容无法保存。请检查每格只有一株植物，并放下正在拖动的植物。");break;
        case 14:
            if(newPreset==null)newPreset=new PvpPresetDocument();
            editDetails(a,newPreset);
            break;
        case 15:
            if(imported==null)throw new IOException("请重新打开预设文件");
            editDetails(a,imported);
            break;
        case 16:
            document=null;documentFile=null;
            GithubPresetCatalog.reloadLocal(a,options(a).getBoolean("network_enabled",false));
            message("关卡已保存到 pvp_level，可在「本机关卡」打开或导出。");
            break;
        case 19:ReleaseUpdater.check(a);break;
        case 20:newPreset=null;break;
        case 31:case 32:
            options(a).edit().putBoolean("network_enabled",event==31).apply();
            send(7);
            GithubPresetCatalog.refresh(a,event==31);
            break;
        }
    }catch(Exception x){android.util.Log.e("PvpPresetEditor","UI event",x);message("操作失败："+x.getMessage());}}
    private static EditText field(Activity a,LinearLayout layout,String hint,String initial,int inputType){
        EditText input=new EditText(a);
        input.setSingleLine(true);
        input.setInputType(inputType);
        input.setHint(hint);
        input.setText(initial);
        layout.addView(input);
        return input;
    }
    static void editDetails(Activity a,PvpPresetDocument draft){
        LinearLayout form=new LinearLayout(a);
        form.setOrientation(LinearLayout.VERTICAL);
        int pad=Math.round(20*a.getResources().getDisplayMetrics().density);
        form.setPadding(pad,0,pad,0);
        EditText name=field(a,form,"名字（留空为通用阵容）",draft.name,InputType.TYPE_CLASS_TEXT);
        EditText cups=field(a,form,"奖杯（留空自动分配）",Objects.toString(draft.trophies,""),InputType.TYPE_CLASS_NUMBER);
        CheckBox special=new CheckBox(a);
        special.setText("特殊敌人（需填写名字、奖杯和概率）");
        special.setChecked(draft.special);
        form.addView(special);
        String current=draft.appearance==null?"":BigDecimal.valueOf(draft.appearance,2).stripTrailingZeros().toPlainString();
        EditText chance=field(a,form,"出现概率 %（仅特殊敌人生效）",current,InputType.TYPE_CLASS_NUMBER|InputType.TYPE_NUMBER_FLAG_DECIMAL);
        chance.setEnabled(draft.special);
        special.setOnCheckedChangeListener((button,checked)->chance.setEnabled(checked));
        ScrollView scroll=new ScrollView(a);
        scroll.addView(form);
        AlertDialog dialog=new AlertDialog.Builder(a).setTitle("关卡资料").setView(scroll)
            .setNegativeButton("取消",null).setPositiveButton("确定",null).create();
        dialog.setOnShowListener(ignored->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view->{
            String title;
            Integer trophyCount=null,appearance=null;
            try{title=PvpPresetDocument.validName(name.getText().toString());}
            catch(IOException bad){name.setError(bad.getMessage());return;}
            String trophyText=cups.getText().toString().trim();
            if(!trophyText.isEmpty())try{
                trophyCount=Integer.parseInt(trophyText);
                if(trophyCount<0||trophyCount>99999)throw new NumberFormatException();
            }catch(NumberFormatException bad){cups.setError("奖杯须为0～99999");return;}
            String chanceText=chance.getText().toString().trim();
            if(!chanceText.isEmpty())try{appearance=PvpPresetDocument.probability(chanceText);}
            catch(IOException bad){chance.setError(bad.getMessage());return;}
            draft.name=title;
            draft.trophies=trophyCount;
            draft.special=special.isChecked();
            draft.appearance=appearance;
            if(draft.special&&!draft.effectiveSpecial())message("关卡资料不完整，此阵容会按普通邻居处理。");
            dialog.dismiss();
        }));
        dialog.show();
    }
    static void prepareImport(InputStream stream,File localFile)throws Exception{
        imported=PvpPresetDocument.parseForEdit(PvpPresetDocument.read(stream),catalogue);
        importedFile=localFile;
        if(imported.omittedPlants!=0)message("已从编辑草坪移除 "+imported.omittedPlants+" 株禁用植物。保存后才会更新文件。");
        send(6);
    }
    static void openLibrary(Activity a){
        File[] files=storage.localLevels();
        if(files.length==0){message("pvp_level 中还没有本机关卡。");return;}
        String[] labels=new String[files.length];
        for(int i=0;i<files.length;i++)labels[i]=files[i].getName();
        new AlertDialog.Builder(a).setTitle("本机关卡").setItems(labels,(dialog,position)->{
            File file=files[position];
            new AlertDialog.Builder(a).setTitle(file.getName())
                .setItems(new String[]{"打开编辑","导出副本"},(actions,action)->{
                    try{
                        if(action==0)prepareImport(new FileInputStream(file),file);
                        else export(a,file);
                    }catch(Exception e){message("文件操作失败："+e.getMessage());}
                }).setNegativeButton("取消",null).show();
        }).setNegativeButton("取消",null).show();
    }
    static void save(Activity a,int[] event)throws Exception{
        if(document==null)throw new IOException("编辑会话已丢失");document.update(event);
        documentFile=storage.saveLocal(documentFile,document.encode(catalogue));
        android.util.Log.i("PvpPresetEditor","Preset level saved in pvp_level");
        send(3);
    }
    static void export(Activity a,File file)throws Exception{
        byte[] contents=PvpPresetDocument.read(new FileInputStream(file));
        if(PvpPresetDocument.parseForEdit(contents,catalogue).omittedPlants!=0)
            throw new IOException("该关卡含禁用植物，请先打开编辑并保存");
        pendingExport=contents;
        Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT);i.addCategory(Intent.CATEGORY_OPENABLE);i.setType("application/json");i.putExtra(Intent.EXTRA_TITLE,file.getName());
        try{
            a.startActivityForResult(i,SAVE);
        }catch(Exception x){pendingExport=null;message("系统导出窗口不可用，关卡仍可从「本机关卡」打开。");}
    }
    public static boolean onActivityResult(Activity a,int request,int result,Intent intent){
        if(ReleaseUpdater.onActivityResult(a,request))return true;
        if(request!=OPEN&&request!=SAVE)return false;
        try{init(a);if(result!=Activity.RESULT_OK||intent==null||intent.getData()==null){if(request==SAVE)pendingExport=null;return true;}
            Uri uri=intent.getData();if(request==OPEN){prepareImport(a.getContentResolver().openInputStream(uri),null);}
            else{byte[] encoded=pendingExport;pendingExport=null;
                if(encoded==null)throw new IOException("请从「本机关卡」重新导出");
                try(OutputStream out=a.getContentResolver().openOutputStream(uri,"wt")){if(out==null)throw new IOException("文件不可写");out.write(encoded);out.flush();}
                android.util.Log.i("PvpPresetEditor","Preset document exported");
                message("预设文件已导出，可使用系统文件管理器分享或再次导入。");}
        }catch(Exception x){android.util.Log.e("PvpPresetEditor","document",x);message("文件操作失败："+x.getMessage());}return true;
    }
}
