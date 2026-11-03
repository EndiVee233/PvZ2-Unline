"""Build v40 with local redemption's native request-dialog cleanup."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v40')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
