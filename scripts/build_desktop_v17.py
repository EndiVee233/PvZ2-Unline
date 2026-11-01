"""Package the v17 desktop candidate over the verified v16r10; no device operations."""
from pathlib import Path
import hashlib,json,shutil,zipfile
from build_desktop_hover import add_native_hover

ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'work/launch-fix/PvZ2-v16r10-currency-exchange.apk'
out=ROOT/'work/desktop-v17'
sha=lambda b:hashlib.sha256(b).hexdigest()
assert hashlib.file_digest(base.open('rb'),'sha256').hexdigest()=='53d7806ab8fa7a81596f7ed5b9572eeede5876e0c10ad3838bc2caaca16ed338'
prior=json.loads((ROOT/'docs/recovery/exchange-v16-patches.json').read_text(encoding='utf8'))
changes=[]
with zipfile.ZipFile(base) as src:
    lib=bytearray(src.read('lib/armeabi/libSrc.so'))
    for item in prior['exchanges']:
        currency=item['spend_currency'];amount=item['receive']
        key=f'V16_{currency}_{amount}_D'
        old=prior['native_patches'][-1]['strings'][key]
        text=f"获得{amount} {'金币' if item['receive_currency']=='coin' else '钻石'}"
        before=(old+'\0').encode('utf-32le');after=(text+'\0').encode('utf-32le')
        assert len(after)<=len(before) and lib.count(before)==1
        offset=lib.index(before);lib[offset:offset+len(before)]=after+bytes(len(before)-len(after))
        changes.append(dict(key=key,offset=hex(offset),before=old,after=text))
    lib,hover=add_native_hover(lib)
    (out/'libSrc.so').write_bytes(lib)
    replacements={
        'classes.dex':(out/'input-dex/classes.dex').read_bytes(),
        'lib/armeabi/libSrc.so':bytes(lib),
        'lib/armeabi/libRestart.so':(out/'glshim/libRestart.so').read_bytes(),
    }
    with zipfile.ZipFile(out/'unsigned.apk','w',allowZip64=True) as dst:
        for item in src.infolist():
            if item.filename.startswith('META-INF/'):continue
            if item.filename in replacements:dst.writestr(item,replacements[item.filename])
            else:
                with src.open(item) as a,dst.open(item,'w') as b:shutil.copyfileobj(a,b,1024*1024)
record=dict(base=str(base),candidate=True,device_verified=False,
    user_requested_no_runtime_verification=True,
    changed_payloads={k:sha(v) for k,v in replacements.items()},
    fee_calculation_retained_percent=10,shop_text=changes,native_hover=hover,
    prefetch=json.loads((out/'index/prefetch-index.json').read_text(encoding='utf8')),
    worker_pool=dict(min_threads=2,max_threads=4,lifetime='process',priority='demand before background',
        same_texture_prefetch_promoted=True,background_inflight_textures=1,
        low_disk_reserve_bytes=256*1024*1024),
    source_hashes={p:sha((ROOT/p).read_bytes()) for p in [
        'src/glshim/glshim.cpp','src/glshim/decode_pool.inc','scripts/build_desktop_hover.py',
        'scripts/index_texture_prefetch.py']},
    prefetch_index_sha256=sha((out/'index/prefetch_index.inc').read_bytes()))
(ROOT/'docs/recovery/desktop-v17-build.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(changed=list(replacements),textures=record['prefetch']['texture_count'],device_verified=False),indent=2))
