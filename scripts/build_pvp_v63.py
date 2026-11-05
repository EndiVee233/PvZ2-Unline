"""Restore local zombie evolution transactions, timers and native grades."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v63')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
