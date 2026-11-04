"""Build the corrected native training button state and decoration layout."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v49')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
