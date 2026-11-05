"""Correct native image lookup offsets and exercise the real type getter."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v70')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
