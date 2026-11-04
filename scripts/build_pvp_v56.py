"""Start Dave combat from the native zero-id reason-1 preview button."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v56')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
