"""Guard against using Ghidra image-base-adjusted function labels as offsets."""
from check_offline_pvp_v69_arm import OUT
from pathlib import Path
import struct,json

original=Path('work/libSrc_orig.so').read_bytes()
def target(site):
 word=struct.unpack_from('<I',original,site)[0];assert word>>24==0xeb
 delta=word&0xffffff
 if delta&0x800000:delta-=1<<24
 return site+8+4*delta
assert target(0x109eb2c)==0x11b5b5c and target(0x109eb40)==0x11ba888
assert struct.unpack_from('<I',original,0x11b5b5c)[0]==0xe92d4878
assert struct.unpack_from('<I',original,0x11ba888)[0]==0xe92d4ff0
source=Path('src/offline-pvp/star_display.h').read_text(encoding='utf8')
assert '0x11c5b5c' not in source and '0x11ca888' not in source
report=dict(native_offsets_match_original_draw_calls=True,real_type_getter_executed_in_star_checks=True,
 wrong_image_base_adjusted_entries_rejected=True,previous_star_counter_draw_and_scene_checks=True,
 previous_v68_regressions=True,runtime_game_verified=False)
(OUT/'v70-arm-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
