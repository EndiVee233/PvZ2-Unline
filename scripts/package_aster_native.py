"""Carry a rebuilt shared engine into accepted Aster assets/Java/ABI shims."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
from zipfile import ZipFile
from build_aster_arm64_game import ROOT,copy_compressed_entry
from build_aster_save_path_fix import manifest_version


def package(source,native,output,sdk,architecture,build_number,old_build,bridge,bootstrap=None):
    output.mkdir(parents=True,exist_ok=True)
    unsigned=output/'unsigned.apk';aligned=output/'aligned.apk'
    final=output/f'PvZ2-Unline-Aster-v{build_number}-{architecture}.apk'
    if source.resolve() in (unsigned.resolve(),aligned.resolve(),final.resolve()):
        raise ValueError('Input/output overlap')
    data=native.read_bytes()
    bridge_data=bridge.read_bytes()
    bootstrap_data=bootstrap.read_bytes() if bootstrap else None
    if bootstrap:
        warmup=json.loads((bootstrap.parent/'warmup-validation.json').read_text())
        if warmup['dex_sha256']!=hashlib.sha256(bootstrap_data).hexdigest():
            raise ValueError('Bootstrap validation does not match DEX')
        if warmup['only_original_class_changed']!='com/popcap/pvz2cthd/BootActivity.smali' or not warmup['same_dex_classloader']:
            raise ValueError('Unexpected bootstrap modification')
    binding=json.loads((bridge.parent/'bridge-binding.json').read_text())
    if binding['native_sha256']!=hashlib.sha256(data).hexdigest() or binding['bridge_sha256']!=hashlib.sha256(bridge_data).hexdigest():
        raise ValueError('JNI bridge was not built for this engine')
    if binding.get('arm_jni_cases_passed')!=12:raise ValueError('Engine/bridge JNI integration checks are missing')
    if b'com.popcap.pvz2cthd.reconstruction' in data or b'/data/data/com.pvz2unline.aster/' not in data:
        raise ValueError('Engine paths are not compiled for Aster')
    member='lib/armeabi/libSrc.so' if architecture=='ARM32' else 'assets/guest_libs/libSrc_a32.so'
    bridge_member='lib/armeabi/libPresetEditor.so' if architecture=='ARM32' else 'assets/guest_libs/libPresetEditor_a32.so'
    with ZipFile(source) as src,ZipFile(unsigned,'w') as dst:
        if bootstrap and warmup['source_dex_sha256']!=hashlib.sha256(src.read('classes8.dex')).hexdigest():
            raise ValueError('Bootstrap was built from a different Java baseline')
        for info in src.infolist():
            if re.fullmatch(r'META-INF/(MANIFEST\.MF|[^/]+\.(SF|RSA|DSA|EC))',info.filename,re.I):continue
            if info.filename==member:dst.writestr(info,data)
            elif info.filename==bridge_member:dst.writestr(info,bridge_data)
            elif bootstrap and info.filename=='classes8.dex':dst.writestr(info,bootstrap_data)
            elif info.filename=='AndroidManifest.xml':
                dst.writestr(info,manifest_version(src.read(info),build_number,old_build))
            else:copy_compressed_entry(src,info,dst)
    tools=sdk/'build-tools/34.0.0'
    subprocess.run([tools/'zipalign.exe','-p','-f','4',unsigned,aligned],check=True)
    signer=['java','-jar',tools/'lib/apksigner.jar']
    subprocess.run([*signer,'sign','--ks',ROOT/'work/keys/recovered-debug.keystore',
                    '--ks-pass','pass:android','--ks-key-alias','androiddebugkey','--out',final,aligned],check=True)
    subprocess.run([*signer,'verify',final],check=True)
    with ZipFile(source) as a,ZipFile(final) as b:
        assert b.read(member)==data
        assert b.read(bridge_member)==bridge_data
        changed=[]
        for i in a.infolist():
            if i.filename.startswith('META-INF/'):continue
            j=b.getinfo(i.filename)
            if (i.CRC,i.file_size)!=(j.CRC,j.file_size):changed.append(i.filename)
        allowed={member,bridge_member,'AndroidManifest.xml'}
        if bootstrap:
            allowed.add('classes8.dex');assert b.read('classes8.dex')==bootstrap_data
        assert 'AndroidManifest.xml' in changed and set(changed)<=allowed,changed
    report=dict(apk=str(final),architecture=architecture,version=build_number,
                native_sha256=hashlib.sha256(data).hexdigest(),
                bridge_sha256=hashlib.sha256(bridge_data).hexdigest(),
                unchanged_assets=True,unchanged_java_except_bootstrap=bool(bootstrap),
                unchanged_assets_and_java=not bool(bootstrap),runtime_verified=False)
    if bootstrap:report['bootstrap_sha256']=hashlib.sha256(bootstrap_data).hexdigest()
    (output/'package-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','native','output','sdk'):p.add_argument(name,type=Path)
    p.add_argument('--architecture',choices=('ARM32','ARM64'),required=True)
    p.add_argument('--build-number',type=int,required=True);p.add_argument('--old-build',type=int,required=True)
    p.add_argument('--bridge',type=Path,required=True)
    p.add_argument('--bootstrap',type=Path)
    package(**vars(p.parse_args()))
