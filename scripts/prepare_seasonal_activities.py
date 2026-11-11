"""Configure map events and the standalone Endless entry."""
from prepare_offline_neighbor_catalog import Bundle, decode, extract
from prepare_opening_tutorial_resources import update_level


ACTIVITIES = 'PACKAGES\\ACTIVITYCONFIG.RTON'
DAILY_LEVELS = 'PACKAGES\\LEVELOFTHEDAYCONFIG.RTON'
MAP_LAYOUTS = tuple('PACKAGES\\UI_' + platform + '.RTON'
                    for platform in ('IPAD', 'IPHONE', 'IPHONE5', 'IPHONESTRETCH'))


def update_activities(document):
    activity, = document['objects']
    assert activity['objclass'] == 'ActivityConfig'
    config = activity['objdata']
    config['ScrollBarBark']['IsActivated'] = False
    config['ScrollBarBark']['BarkTextContent'] = []
    # The inherited package already keeps the event hub and the other
    # Spring Festival sub-events open. The separate 财神 encounter expired.
    assert config['SpringBossActivatedData']['EventEndDate'] == 20150809
    config['SpringBossActivatedData']['EventEndDate'] = config['RedPackActivedDate']['EndDate']


def update_anniversary(document):
    config, = document['objects']
    levels, = (row for row in config['objdata']['TheDayItemList'] if row['DayName'] == 'birthz')
    assert len(levels['LevelName']) == 7 and levels['End'] == 20151029
    # Keep the original campaign key (Start) and the player's recorded wins.
    levels['End'] = 20601115


def retire_activities(document):
    activity, = document['objects']
    assert activity['objclass'] == 'ActivityConfig'
    config = activity['objdata']
    config['ScrollBarBark']['IsActivated'] = False
    config['ScrollBarBark']['BarkTextContent'] = []
    for name in ('ActivityCentreDate', 'TwoYearData',
                 'LanternRiddlesActivatedDate', 'RedPackActivedDate'):
        config[name]['EndDate'] = 0
        if 'IsActivated' in config[name]:
            config[name]['IsActivated'] = False
        if 'EntryCloseDate' in config[name]:
            config[name]['EntryCloseDate'] = 0
    for name in ('SpringBossActivatedData', 'SpringGiftActivatedData',
                 'ChristmasAccessoryData', 'GoldenEggData', 'ChristmasProtectData',
                 'ChristmasLotteryData'):
        config[name]['EventEndDate'] = 0
    config['ConsumptionActivedData']['IsActivated'] = False


def configure_endless_button(document):
    objects = document['objects']
    endless, = (sheet for sheet in objects
                if 'UIWorldMapDailyAchievementButton' in sheet.get('aliases', ()))
    plants, = (sheet for sheet in objects
               if 'UIWorldMapPlantLevelUpButton' in sheet.get('aliases', ()))
    plant_offset = plants['objdata']['PositionOffset']
    endless['objdata'].update(
        Class='WorldMap_BossFightButton',
        Parent='UIScreen',
        ParentAnchor='BottomRight',
        Anchor='BottomRight',
        SizeFromImage='IMAGE_UI_HUD_WORLDMAP_TINY_ICON_ACTIVITY1_0',
        PositionOffset={'x': plant_offset['x'], 'y': round(plant_offset['y'] * 0.60)},
    )


def prepare(resource, *, retire=False, standalone_endless=False):
    bundle = Bundle(resource)
    changes = {
        ACTIVITIES: update_level(bundle, ACTIVITIES, retire_activities if retire else update_activities),
    }
    if not retire:
        changes[DAILY_LEVELS] = update_level(bundle, DAILY_LEVELS, update_anniversary)
    if standalone_endless:
        for path in MAP_LAYOUTS:
            changes[path] = update_level(bundle, path, configure_endless_button)
    result = bundle.build()
    installed = Bundle(result)
    for path, document in changes.items():
        assert decode(extract(installed, path)) == document
    return result
