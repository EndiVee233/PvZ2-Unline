"""Candidate retains both RSG dictionaries and immutable map animation bytes."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v89')
runpy.run_path(str(Path(__file__).with_name('build_preset_fix_v88.py')),run_name='__main__')
