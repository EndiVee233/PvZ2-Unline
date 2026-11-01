import zipfile,hashlib,json
from pathlib import Path
root=Path.cwd();old=root/'work/restored-v14/PvZ2-v14-restored-lottery-tutorial.apk';new=root/'work/tutorial-v15/PvZ2-v15-skip-return-guide.apk'
patch=json.loads((root/'docs/recovery/tutorial-v15-patches.json').read_text());changed=[]
with zipfile.ZipFile(old) as a,zipfile.ZipFile(new) as b:
 for i in a.infolist():
  if i.filename.startswith('META-INF/'):continue
  j=b.getinfo(i.filename);assert i.compress_type==j.compress_type
  with a.open(i) as x,b.open(j) as y:
   if hashlib.file_digest(x,'sha256').digest()!=hashlib.file_digest(y,'sha256').digest():changed.append(i.filename)
 assert changed==['lib/armeabi/libSrc.so'];assert hashlib.sha256(b.read(changed[0])).hexdigest()==patch['patched_native_sha256'];assert b.testzip() is None
record=dict(changed_entries_from_v14=changed,all_other_payloads_identical=True,sha256=hashlib.file_digest(new.open('rb'),'sha256').hexdigest(),output=str(new),device_verified=False)
(root/'docs/recovery/tutorial-v15-build.json').write_text(json.dumps(record,indent=2),encoding='utf8');print(json.dumps(record,indent=2))
