"""Restore shop battles and atomically save three-star occupation."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v80')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
