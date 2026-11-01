import java.nio.file.*;
import java.io.*;
import com.android.tools.smali.dexlib2.*;
import com.android.tools.smali.dexlib2.dexbacked.*;
import com.android.tools.smali.baksmali.*;
import com.android.tools.smali.dexlib2.writer.builder.*;
import com.android.tools.smali.dexlib2.writer.io.*;
import brut.androlib.src.SmaliBuilder;
import brut.directory.ExtFile;
public class RepairDex {
 public static void main(String[] args) throws Exception {
  Opcodes op = new Opcodes(21, -1);
  if(args[0].equals("decode")) {
   byte[] bytes=Files.readAllBytes(Paths.get(args[1]));
   DexBackedDexFile dex=new DexBackedDexFile(op, bytes, 0);
   Baksmali.disassembleDexFile(dex,new File(args[2]),2,new BaksmaliOptions());
  } else {
   DexBuilder builder=new DexBuilder(op);
   File dir=new File(args[1]);
   SmaliBuilder sb=new SmaliBuilder(new ExtFile(dir),new File(args[2]),21);
   Files.walk(dir.toPath()).filter(p->p.toString().endsWith(".smali")).forEach(p->sb.buildFile(dir.toPath().relativize(p).toString(),builder));
   builder.writeTo(new FileDataStore(new File(args[2])));
  }
 }
}
