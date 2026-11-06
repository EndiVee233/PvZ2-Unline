"""Restore local battle summaries and remove the region base-level restriction."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v94')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
