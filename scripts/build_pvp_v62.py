"""Restore unlocked lab roster entries and observe the original evolution UI."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v62')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
