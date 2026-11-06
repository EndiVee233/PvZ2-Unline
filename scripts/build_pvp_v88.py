"""Full rebuild with independent resource indexes and all accepted PvP features."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v88')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
