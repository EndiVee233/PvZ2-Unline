"""Unique non-FBI guests and a non-producing defensive plant pool."""
import runpy,sys
from pathlib import Path
sys.argv.append("--v96")
runpy.run_path(str(Path(__file__).with_name("build_pvp_v39.py")),run_name="__main__")
