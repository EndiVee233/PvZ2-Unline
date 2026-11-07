"""Build the first real-combat local NPC home-retaliation candidate."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v98')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
