"""Restore troop sales and the reported missing PvP art on v99 gameplay."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v101')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
