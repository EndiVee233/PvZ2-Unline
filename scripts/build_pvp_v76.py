"""Finish local defense boards before saved exit and repeated editor entry."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v76')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
