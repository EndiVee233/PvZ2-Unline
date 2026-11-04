"""Build corrected legacy skill animation geometry and ground-effect sizes."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v58')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
