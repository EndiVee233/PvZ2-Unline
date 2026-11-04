"""Remove PvP league/rank navigation; keep v58 art as an unaccepted TODO."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v59')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
