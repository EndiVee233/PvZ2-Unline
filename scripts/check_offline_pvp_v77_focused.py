"""Business entrances plus the already accepted residence/editor lifecycle."""
import sys,importlib
from check_offline_pvp_v76_focused import Definitions

if __name__=='__main__':
 sys.meta_path.insert(0,Definitions())
 checks=importlib.import_module('check_offline_pvp_v77_arm')
 checks.check_businesses()
 previous=importlib.import_module('check_offline_pvp_v76_arm')
 previous.check_lifecycle();previous.check_defense();previous.check_residences()
