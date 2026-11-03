"""Build v41 with direct local star-coin purchases and the native gem balance."""
import runpy,sys
from pathlib import Path
sys.argv.append('--v41')
runpy.run_path(str(Path(__file__).with_name('build_pvp_v39.py')),run_name='__main__')
