"""Reassemble the small bootstrap DEX with sorted IDs after changing literals."""
from pathlib import Path
import subprocess,os,re,struct,hashlib,zlib

def use_extraction_title_art(source):
 old=r'    \.line 134\n    new-instance v6, Landroid/widget/TextView;\n.*?(?=    \.line 141\n)'
 new=r'''    .line 134
    new-instance v6, Landroid/widget/ImageView;
    invoke-direct {v6, p0}, Landroid/widget/ImageView;-><init>(Landroid/content/Context;)V
    const v7, 0x7f020047
    invoke-virtual {v6, v7}, Landroid/widget/ImageView;->setImageResource(I)V
    sget-object v7, Landroid/widget/ImageView$ScaleType;->FIT_CENTER:Landroid/widget/ImageView$ScaleType;
    invoke-virtual {v6, v7}, Landroid/widget/ImageView;->setScaleType(Landroid/widget/ImageView$ScaleType;)V
    const-string v7, "正在进行第一次解压"
    invoke-virtual {v6, v7}, Landroid/widget/ImageView;->setContentDescription(Ljava/lang/CharSequence;)V
    new-instance v8, Landroid/widget/LinearLayout$LayoutParams;
    const/4 v7, -0x1
    const/high16 v9, 0x42680000    # 58.0f
    mul-float/2addr v9, v0
    float-to-int v9, v9
    invoke-direct {v8, v7, v9}, Landroid/widget/LinearLayout$LayoutParams;-><init>(II)V
    invoke-virtual {v5, v6, v8}, Landroid/widget/LinearLayout;->addView(Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V
    const/16 v7, 0x11

'''
 start=source.index('.method private buildUi()V')
 end=source.index('.end method',start)
 body=source[start:end]
 assert r'\u6b63\u5728\u8fdb\u884c\u9996\u6b21\u89e3\u538b' in body
 body,count=re.subn(old,lambda match:new,body,flags=re.S)
 assert count==1
 return source[:start]+body+source[end:]


def rebuild_bootstrap(original, out, replacements, apktool, *, extraction_art=False):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 (out/'original.dex').write_bytes(original)
 subprocess.run(['javac','-cp',str(apktool),'-d',str(out),str(Path(__file__).with_name('RepairDex.java'))],check=True)
 cp=str(apktool)+os.pathsep+str(out)
 subprocess.run(['java','-Xmx256m','-cp',cp,'RepairDex','decode',str(out/'original.dex'),str(out/'smali')],check=True)
 p=out/'smali/com/popcap/pvz2cthd/BootActivity.smali';s=p.read_text(encoding='utf8')
 # One substitution pass avoids cascading if the new base checksum equals the old target.
 for old in replacements:assert old in s,old
 s=re.sub('|'.join(re.escape(k) for k in replacements),lambda m:replacements[m[0]],s)
 if extraction_art:s=use_extraction_title_art(s)
 p.write_text(s,encoding='utf8')
 target=out/'classes8.dex'
 subprocess.run(['java','-Xmx256m','-cp',cp,'RepairDex','encode',str(out/'smali'),str(target)],check=True)
 b=target.read_bytes();count,off=struct.unpack_from('<II',b,56);strings=[]
 for i in range(count):
  p=struct.unpack_from('<I',b,off+4*i)[0]
  while b[p]&128:p+=1
  p+=1;strings.append(b[p:b.index(0,p)])
 assert all(a<c for a,c in zip(strings,strings[1:])), 'DEX string_ids not strictly sorted'
 assert hashlib.sha1(b[32:]).digest()==b[12:32]
 assert zlib.adler32(b[12:])&0xffffffff==struct.unpack_from('<I',b,8)[0]
 assert struct.unpack_from('<I',b,96)[0]==struct.unpack_from('<I',original,96)[0]
 return b
