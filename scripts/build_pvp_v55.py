"""Correct own-base display, Dave scouting and PvP return decorations."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v55')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
