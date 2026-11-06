"""Isolate the original first-defense tutorial and acknowledge its local pings."""
import runpy,sys
from pathlib import Path
sys.argv.append("--v97")
runpy.run_path(str(Path(__file__).with_name("build_pvp_v39.py")),run_name="__main__")
