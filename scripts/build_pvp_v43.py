"""Build the native scouting-to-attack and Evil Dave introduction candidate."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v43')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
