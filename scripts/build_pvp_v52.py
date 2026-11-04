"""Build surviving-zombie recall and the native garden army display."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v52')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
