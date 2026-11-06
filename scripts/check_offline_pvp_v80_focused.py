"""Capture lifecycle plus the accepted free preview/ownership/editor paths."""
import sys,importlib
from check_offline_pvp_v76_focused import Definitions

if __name__=='__main__':
 sys.meta_path.insert(0,Definitions())
 c=importlib.import_module('check_offline_pvp_v80_arm')
 c.check_capture();c.check_scout();c.check_ownership();c.check_businesses()
 previous=importlib.import_module('check_offline_pvp_v76_arm')
 previous.check_lifecycle();previous.check_defense();previous.check_residences()
