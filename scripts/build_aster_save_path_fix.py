"""Apply the shared v164 PvP persistence fix to an existing signed Aster APK."""
import argparse
import hashlib
from pathlib import Path
import re
import struct
import subprocess
from zipfile import ZipFile
from build_aster_arm64_game import ROOT, copy_compressed_entry
from prepare_aster_save_paths import patch


def manifest_version(data, build_number=164, old_build=163):
    old=f'1.7.5-Unline-Aster-v{old_build}'.encode('utf-16le')
    new=f'1.7.5-Unline-Aster-v{build_number}'.encode('utf-16le')
    if len(new)!=len(old):raise ValueError('Version string length changed')
    if data.count(old)!=1:
        raise ValueError(f'Expected v{old_build} manifest')
    result=bytearray(data.replace(old,new))
    pool=8
    kind,header,size,count,styles,flags,start,_=struct.unpack_from('<HH6I',result,pool)
    if (kind,header,styles,flags)!=(1,28,0,0):
        raise ValueError('Unknown manifest string pool')
    strings=[]
    for i in range(count):
        at=pool+start+struct.unpack_from('<I',result,pool+header+4*i)[0]
        n=struct.unpack_from('<H',result,at)[0]
        strings.append(result[at+2:at+2+2*n].decode('utf-16le'))
    pos=pool+size
    changed=0
    while pos<len(result):
        kind,header,size=struct.unpack_from('<HHI',result,pos)
        if kind==0x102:
            ext=pos+header
            tag,first,stride,n=struct.unpack_from('<IHHH',result,ext+4)
            if strings[tag]=='manifest':
                for i in range(n):
                    at=ext+first+stride*i
                    key=struct.unpack_from('<I',result,at+4)[0]
                    if strings[key]=='versionCode':
                        if result[at+15]!=0x10 or struct.unpack_from('<I',result,at+16)[0]!=1000+old_build:
                            raise ValueError('Unknown version code')
                        struct.pack_into('<I',result,at+16,1000+build_number);changed+=1
        pos+=size
    if changed!=1:raise ValueError('Missing unique version code')
    return bytes(result)


def build(apk,output,sdk,architecture,build_number=164,decode_library=None):
    output.mkdir(parents=True,exist_ok=True)
    member='lib/armeabi/libSrc.so' if architecture=='ARM32' else 'assets/guest_libs/libSrc_a32.so'
    unsigned=output/'unsigned.apk'
    aligned=output/'aligned.apk'
    final=output/f'PvZ2-Unline-Aster-v{build_number}-{architecture}.apk'
    if decode_library and architecture!='ARM32':raise ValueError('ARM decode diagnostics require ARM32')
    if apk.resolve() in (unsigned.resolve(),aligned.resolve(),final.resolve()):
        raise ValueError('Input/output overlap')
    with ZipFile(apk) as source:
        original=source.read(member)
        if hashlib.sha256(original).hexdigest()!='fccf995b666088538a94c8c17893e75935fff3453d2f1cf0d1a1462d27b788bb':
            raise ValueError('Unexpected shared engine baseline')
        native,changed=patch(original)
        if len(changed)!=2:raise ValueError('Expected both unfixed helpers')
        if build_number>=166:
            from prepare_aster_pvp_runtime import patch as patch_runtime
            native,_=patch_runtime(native,sdk/'ndk/27.0.12077973',output/'runtime',refresh_research=build_number>=168)
        resources={}
        if build_number>=167:
            from prepare_aster_tutorial_chain import prepare as prepare_tutorial
            resources=prepare_tutorial(source,output/'tutorial-chain')
        with ZipFile(unsigned,'w') as target:
            for info in source.infolist():
                if re.fullmatch(r'META-INF/(MANIFEST\.MF|[^/]+\.(SF|RSA|DSA|EC))',info.filename,re.I):continue
                if info.filename==member:target.writestr(info,native)
                elif info.filename in resources:target.writestr(info,resources[info.filename])
                elif decode_library and info.filename=='lib/armeabi/libRestart.so':target.writestr(info,decode_library.read_bytes())
                elif info.filename=='AndroidManifest.xml':target.writestr(info,manifest_version(source.read(info),build_number))
                else:copy_compressed_entry(source,info,target)
    tools=sdk/'build-tools/34.0.0'
    subprocess.run([tools/'zipalign.exe','-p','-f','4',unsigned,aligned],check=True)
    signer=['java','-jar',tools/'lib/apksigner.jar']
    subprocess.run([*signer,'sign','--ks',ROOT/'work/keys/recovered-debug.keystore',
                    '--ks-pass','pass:android','--ks-key-alias','androiddebugkey','--out',final,aligned],check=True)
    subprocess.run([*signer,'verify',final],check=True)
    print(final,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('apk','output','sdk'):parser.add_argument(name,type=Path)
    parser.add_argument('--architecture',choices=('ARM32','ARM64'),required=True)
    parser.add_argument('--build-number',type=int,default=164)
    parser.add_argument('--decode-library',type=Path,help='Optional ARM32 diagnostic shim')
    build(**vars(parser.parse_args()))
