import zipfile,hashlib,json
from pathlib import Path
root=Path.cwd();source=root/'PvZ2-reconstruction-multiuser-v11.apk';target=root/'work/restored-v14/PvZ2-v14-restored-lottery-tutorial.apk'
record=json.loads((root/'docs/recovery/restored-v14-patches.json').read_text(encoding='utf8'))
with zipfile.ZipFile(source) as a,zipfile.ZipFile(target) as b:
 changed=[]
 for i in a.infolist():
  if i.filename.startswith('META-INF/'):continue
  j=b.getinfo(i.filename);assert i.compress_type==j.compress_type
  with a.open(i) as x,b.open(j) as y:
   if hashlib.file_digest(x,'sha256').digest()!=hashlib.file_digest(y,'sha256').digest():changed.append(i.filename)
 assert set(changed)==set(record['library_sha256']),changed
 for name,expected in record['library_sha256'].items():assert hashlib.sha256(b.read(name)).hexdigest()==expected
 assert b.testzip() is None
record.update(output=str(target),apk_sha256=hashlib.file_digest(target.open('rb'),'sha256').hexdigest(),changed_entries=changed,zip_crc_verified=True,other_payloads_identical=True)
(root/'docs/recovery/restored-v14-build.json').write_text(json.dumps(record,indent=2),encoding='utf8');print(record['apk_sha256']);print(changed)
