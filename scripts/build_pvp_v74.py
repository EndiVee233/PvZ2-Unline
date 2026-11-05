"""Restore residential NPC map records, panels and native request routing."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v74')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
