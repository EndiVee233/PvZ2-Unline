"""Build v42 with the dedicated PvP coin-bank request handled locally."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v42')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
