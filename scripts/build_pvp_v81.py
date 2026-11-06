"""Restore isolated owned-shop garrison editing and atomic formation saves."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v81')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
