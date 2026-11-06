"""Expose the shipped all-one preset as a separate local player."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v86')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
