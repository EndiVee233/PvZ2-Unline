"""Omit two standalone PvP card/counter flashes; retain skills and readiness."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v53')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
