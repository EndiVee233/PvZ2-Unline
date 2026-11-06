"""Preserve captured shop plants and allow position changes only."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v82')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
