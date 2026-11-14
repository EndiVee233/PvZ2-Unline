"""Stage the continuous tutorial resource fix and matching bootstrap/plan."""
from hashlib import sha256
from pathlib import Path
import json
import re

from build_aster_rgba_background_pilot import ASSET, PLAN, create_plan
from prepare_opening_tutorial_resources import prepare_chain
from rebuild_bootstrap_dex import rebuild_bootstrap

ROOT=Path(__file__).resolve().parents[1]


def prepare(archive, output):
    output.mkdir(parents=True, exist_ok=True)
    original=archive.read(ASSET)
    current=prepare_chain(original)
    old_hash=sha256(original).hexdigest();new_hash=sha256(current).hexdigest()
    plan=create_plan(current,output)
    # The background converter reads its source digest/size from this plan.
    # Also update the fallback overlay's verification, not just its data.
    dex=archive.read('classes8.dex')
    source_work=output/'boot-inspect'
    # Decode once for guarded selection of the overlay's size literal. The
    # source DEX is then rebuilt through the shared sorted-ID assembler.
    import os,subprocess
    source_work.mkdir(exist_ok=True)
    (source_work/'original.dex').write_bytes(dex)
    apktool=ROOT/'tools/apktool.jar'
    subprocess.run(['javac','-cp',apktool,'-d',source_work,ROOT/'scripts/RepairDex.java'],check=True)
    cp=str(apktool)+os.pathsep+str(source_work)
    subprocess.run(['java','-Xmx256m','-cp',cp,'RepairDex','decode',source_work/'original.dex',source_work/'smali'],check=True)
    text=(source_work/'smali/com/popcap/pvz2cthd/BootActivity.smali').read_text(encoding='utf8')
    method=re.search(r'\.method private applyOriginalSpeedResource\(\)V.*?\.end method',text,re.S)[0]
    fallback_hashes=re.findall(r'const-string(?:/jumbo)? \w+, "([0-9a-f]{64})"',method)
    assert len(fallback_hashes)==2, 'Unknown fallback verifier'
    fallback_hash=fallback_hashes[0]
    assert fallback_hash in (old_hash,'dac3e5e476020ee5e5d7faa2628752bf3e116aabebe0b68e9614f699ae134bb8'), 'Unknown fallback resource digest'
    old_literal,=re.findall(r'const-wide/32 \w+, (0x[0-9a-f]+)',method)
    assert int(old_literal,16) in (len(original),25387008), 'Unknown fallback resource size'
    new_method=method.replace(fallback_hash,new_hash).replace(old_literal,f'0x{len(current):x}')
    new_method=re.sub(r'"\.offline-pvp-v59-[0-9a-f]{12}"',
                      '".offline-tutorial-v167-'+new_hash[:12]+'"',new_method)
    # Field constants may also contain the digest; change them in the same
    # assembly pass rather than assuming there is only one occurrence.
    outside=text.replace(method,'')
    replacements={method:new_method}
    if fallback_hash in outside:replacements[fallback_hash]=new_hash
    updated=rebuild_bootstrap(dex,output/'boot',replacements,apktool)
    report=dict(source_sha256=old_hash,target_sha256=new_hash,
                source_size=len(original),target_size=len(current),
                plan_size=len(plan),bootstrap_updated=True,runtime_accepted=False)
    (output/'tutorial-chain-patch.json').write_text(json.dumps(report,indent=2)+'\n')
    return {ASSET:current,PLAN:plan,'classes8.dex':updated}
