"""Keep residential opponents and acknowledge local own-base edit sessions."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v75')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
