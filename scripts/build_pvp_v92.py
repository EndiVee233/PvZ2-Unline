"""Fix the queued-upgrade background and completed-upgrade caption reset."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v92')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
