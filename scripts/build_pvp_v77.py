"""Restore independent unoccupied business entrances and native details."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v77')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
