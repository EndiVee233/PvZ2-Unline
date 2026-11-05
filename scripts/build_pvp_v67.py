"""Project saved Dave progress into the actual map-title formatter fields."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v67')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
