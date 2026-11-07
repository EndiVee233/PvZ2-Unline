"""Build the PvP art alignment update from the exact v101 candidate."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from zipfile import ZipFile

from prepare_offline_pvp_art_alignment import prepare
from rebuild_bootstrap_dex import rebuild_bootstrap

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "work/pvp-v101/PvZ2-v101-pvp-scene-candidate.apk"
OUT = ROOT / "work/pvp-v102"
TOOLS = Path("K:/pvz2-tools/android-build-tools/android-14")
ART = "assets/reconstruction/zombie2-pvp.rsb.smf"
DEX = "classes8.dex"


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build(base, out, base_hash, prepare_art, marker_from, marker_to, apk_name):
    assert sha256(base) == base_hash
    out.mkdir(parents=True, exist_ok=True)
    unsigned = out / "unsigned.apk"
    aligned = out / "aligned.apk"
    final = out / apk_name
    with ZipFile(base) as source:
        old = source.read(ART)
        art, changes = prepare_art(old)
        old_hash = hashlib.sha256(old).hexdigest()
        new_hash = hashlib.sha256(art).hexdigest()
        method = ".method private static isPvpResourcePredecessor(Ljava/lang/String;)Z\n    .registers 2"
        label = marker_to.strip(".-").replace("-", "_") + "_previous"
        predecessor = f"""

    const-string v0, "{old_hash}"
    invoke-virtual {{v0, p0}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :{label}
    const/4 v0, 0x1
    return v0
    :{label}"""
        replacements = {
            old_hash: new_hash,
            method: method + predecessor,
            marker_from + old_hash[:12]: marker_to + new_hash[:12],
        }
        if len(old) != len(art):
            replacements[hex(len(old))] = hex(len(art))
        dex = rebuild_bootstrap(source.read(DEX), out / "bootstrap", replacements, ROOT / "tools/apktool.jar")
        with ZipFile(unsigned, "w", allowZip64=True) as target:
            for item in source.infolist():
                if item.filename.startswith("META-INF/"):
                    continue
                if item.filename in (ART, DEX):
                    target.writestr(item, art if item.filename == ART else dex)
                else:
                    with source.open(item) as src, target.open(item, "w") as dst:
                        shutil.copyfileobj(src, dst, 1048576)

    align = str(TOOLS / "zipalign.exe")
    signer = ["java", "-jar", str(TOOLS / "lib/apksigner.jar")]
    subprocess.run([align, "-f", "4", str(unsigned), str(aligned)], check=True)
    subprocess.run([
        *signer, "sign", "--ks", str(ROOT / "work/keys/recovered-debug.keystore"),
        "--ks-pass", "pass:android", "--key-pass", "pass:android", "--ks-key-alias", "androiddebugkey",
        "--out", str(final), str(aligned),
    ], check=True)
    subprocess.run([*signer, "verify", str(final)], check=True)
    subprocess.run([align, "-c", "4", str(final)], check=True)
    with ZipFile(base) as original, ZipFile(final) as candidate:
        def payloads(archive):
            return {i.filename: (i.file_size, i.CRC) for i in archive.infolist() if not i.filename.startswith("META-INF/")}

        before, after = payloads(original), payloads(candidate)
        assert before.keys() == after.keys()
        assert {name for name in before if before[name] != after[name]} == {ART, DEX}
        assert candidate.read(ART) == art and candidate.read(DEX) == dex
    build = {
        "apk": str(final.relative_to(ROOT)),
        "sha256": sha256(final),
        "size": final.stat().st_size,
        "resource_sha256": new_hash,
        "changes": changes,
        "runtime_game_verified": False,
    }
    (out / "build.json").write_text(json.dumps(build, indent=2) + "\n", encoding="utf8")
    print(json.dumps(build, indent=2))


if __name__ == "__main__":
    build(
        BASE, OUT, "78e4290ad387410ee7d73b3726a112043013637b6911c617d2f129698aababc5",
        prepare, ".pvp-extra-art-v101-", ".pvp-art-alignment-v102-", "PvZ2-v102-pvp-art-alignment.apk",
    )
