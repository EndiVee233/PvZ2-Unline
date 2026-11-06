"""Garrisons plus accepted capture, scouting, house and editor checks."""
import sys,importlib
from check_offline_pvp_v76_focused import Definitions

if __name__=='__main__':
 sys.meta_path.insert(0,Definitions())
 c=importlib.import_module('check_offline_pvp_v81_arm')
 c.check_garrisons();c.check_capture();c.check_scout();c.check_ownership();c.check_businesses()
 old=importlib.import_module('check_offline_pvp_v76_arm')
 old.check_lifecycle();old.check_defense();old.check_residences()
