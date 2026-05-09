"""
Rune & Shadow - Constants  v5
All game-wide constants, tile definitions, colours, and configuration.

v5:
  - T_CHEST_OPEN: opened (looted) chest tile — walkable, visible, attackable
  - Haunted-town map keys (MAP_EAST_TOWN … MAP_WEST_TOWN)
  - Castle dungeon IDs 9–12 with Dragons as boss
  - Rare item / spell categories
  - DEAD_BODY_LIFETIME_FRAMES, GHOST speed, mimic chance constant
"""

# ─── Screen ───────────────────────────────────────────────────────────────────
SCREEN_WIDTH  = 1024
SCREEN_HEIGHT = 768
FPS           = 60
TITLE         = "Rune & Shadow"

# ─── Tile ─────────────────────────────────────────────────────────────────────
TILE_SIZE  = 32
WORLD_W    = 160   # biome maps
WORLD_H    = 160
TOWN_W     = 80    # starting town map
TOWN_H     = 80
DUN_W      = 64
DUN_H      = 52
HAUNT_W    = 100   # haunted fortress-town maps
HAUNT_H    = 100

# ─── Tile Type IDs ────────────────────────────────────────────────────────────
T_DEEP_WATER     = 0
T_WATER          = 1
T_SAND           = 2
T_GRASS          = 3
T_FOREST         = 4
T_MOUNTAIN       = 5
T_ENTRANCE       = 6
T_FLOOR          = 7
T_WALL           = 8
T_DOOR           = 9
T_STAIRS_UP      = 10
T_STAIRS_DOWN    = 11
T_CHEST          = 12
T_PATH           = 13
T_CAVE_FLOOR     = 14
T_CAVE_WALL      = 15
T_VINE_WALL      = 16
T_SHRINE         = 17
T_SNOW           = 18
T_ICE            = 19
T_BUILDING_WALL  = 20
T_BUILDING_FLOOR = 21
T_GATE_N         = 22
T_GATE_S         = 23
T_GATE_E         = 24
T_GATE_W         = 25
T_WELL           = 26
T_SWAMP          = 27   # slow walkable (swamp murk)
T_CACTUS         = 28   # blocking desert plant
T_ICE_WALL       = 29   # tundra dungeon wall
T_CHEST_OPEN     = 30   # looted chest – walkable, still visible, can be attacked (does nothing)

GATE_TILES = {T_GATE_N, T_GATE_S, T_GATE_E, T_GATE_W}

# ─── Tile Properties ──────────────────────────────────────────────────────────
# (color, walkable, opaque, destructible tag, slow?)
TILE_DATA = {
    T_DEEP_WATER:     ((30,  60, 180), False, False, None,       False),
    T_WATER:          ((65, 105, 225), False, False, None,       False),
    T_SAND:           ((238,214,175), True,  False, None,        False),
    T_GRASS:          ((34, 139,  34), True,  False, None,       False),
    T_FOREST:         ((0,   80,   0), False, True,  'axe',      False),
    T_MOUNTAIN:       ((110,110, 110), False, True,  'pickaxe',  False),
    T_ENTRANCE:       ((80,  40,  20), True,  False, None,       False),
    T_FLOOR:          ((190,170,130), True,  False, None,        False),
    T_WALL:           ((90,  70,  55), False, True,  'pickaxe',  False),
    T_DOOR:           ((160,100,  50), True,  True,  None,       False),
    T_STAIRS_UP:      ((255,215,   0), True,  False, None,       False),
    T_STAIRS_DOWN:    ((200,160,   0), True,  False, None,       False),
    T_CHEST:          ((200,140,  30), False, False, None,       False),
    T_PATH:           ((160,140, 100), True,  False, None,       False),
    T_CAVE_FLOOR:     ((75,  65,  55), True,  False, None,       False),
    T_CAVE_WALL:      ((45,  38,  32), False, True,  'pickaxe',  False),
    T_VINE_WALL:      ((30,  90,  20), False, True,  'axe',      False),
    T_SHRINE:         ((200,200, 255), True,  False, None,       False),
    T_SNOW:           ((220,235, 255), True,  False, None,       False),
    T_ICE:            ((160,200, 240), False, False, None,       False),
    T_BUILDING_WALL:  ((100, 80,  60), False, True,  None,       False),
    T_BUILDING_FLOOR: ((180,160,130), True,  False, None,        False),
    T_GATE_N:         ((255,200,  80), True,  False, None,       False),
    T_GATE_S:         ((255,200,  80), True,  False, None,       False),
    T_GATE_E:         ((255,200,  80), True,  False, None,       False),
    T_GATE_W:         ((255,200,  80), True,  False, None,       False),
    T_WELL:           ((80, 120, 180), False, False, None,       False),
    T_SWAMP:          ((60,  90,  50), True,  False, None,       True),
    T_CACTUS:         ((40, 130,  40), False, False, 'axe',      False),
    T_ICE_WALL:       ((130,170, 210), False, True,  'pickaxe',  False),
    T_CHEST_OPEN:     ((120,  85,  15), False, False, None,      False),  # non-walkable opened chest
}

def tile_color(t):      return TILE_DATA.get(t, (50,50,50))[0]
def tile_walkable(t):   return TILE_DATA.get(t, (50,50,50,False))[1]
def tile_swimmable(t):  return t in (T_WATER, T_ICE)
def tile_opaque(t):     return TILE_DATA.get(t, (50,50,50,False,False))[2]
def tile_tool(t):       return TILE_DATA.get(t, (50,50,50,False,False,None))[3]
def tile_slow(t):       return TILE_DATA.get(t, (50,50,50,False,False,None,False))[4]

# ─── Colors ───────────────────────────────────────────────────────────────────
BLACK       = (0,   0,   0)
WHITE       = (255,255, 255)
RED         = (220,  50,  50)
DARK_RED    = (140,  20,  20)
GREEN       = (50, 200,  50)
BLUE        = (50, 100, 200)
YELLOW      = (255,220,   0)
PURPLE      = (160,  50, 210)
ORANGE      = (255,140,   0)
CYAN        = (0,  200, 200)
DARK_GRAY   = (40,  40,  40)
GRAY        = (128,128, 128)
LIGHT_GRAY  = (200,200, 200)
BROWN       = (139, 90,  43)
PINK        = (255,180, 200)
GOLD        = (255,200,   0)
DARK_GREEN  = (0,   80,   0)
ICE_BLUE    = (160,200, 240)
SAND_COL    = (238,214,175)

# Entity colours
COL_PLAYER    = (80, 140, 255)
COL_SLIME     = (80, 200,  80)
COL_BAT       = (140,  60, 180)
COL_SPIDER    = (120,  70,  20)
COL_GOBLIN    = (180,  80,  40)
COL_SKELETON  = (230,230, 210)
COL_GHOST     = (160,200, 240)
COL_TROLL     = (80, 130,  60)
COL_WOLF      = (160,130, 100)
COL_BIG_SPIDER= (160,  30,  30)
COL_KELPIE    = (20,  90, 160)
COL_YETI      = (200,220, 240)
COL_ICE_WRAITH= (180,220, 255)
COL_SCORPION  = (200,160,  60)
COL_MUMMY     = (200,180,140)
COL_SWAMP_TOAD= (80, 120,  50)
COL_WILL_O    = (100,200, 180)
COL_MIMIC     = (160,100,  20)
COL_DRAGON    = (160,  30,  10)

# Projectile colours
COL_STONE     = (170,160,150)
COL_MAGIC     = (100,200,255)
COL_FIRE      = (255,120,  30)
COL_WEB       = (230,230,200)
COL_ARROW     = (200,160, 80)
COL_BONE      = (230,220,200)
COL_WATER_BOLT= (60, 160, 240)
COL_ICE_BOLT  = (180,230,255)
COL_POISON    = (120,200,  80)
COL_FIREBALL  = (255, 80,   0)

# ─── Game States ──────────────────────────────────────────────────────────────
ST_MENU      = 'menu'
ST_PLAY      = 'play'
ST_INVENTORY = 'inventory'
ST_GAMEOVER  = 'gameover'
ST_PAUSED    = 'paused'
ST_WIN       = 'win'
ST_SETTINGS  = 'settings'
ST_DIALOG    = 'dialog'
ST_TRADER    = 'trader'

# ─── Map Keys ─────────────────────────────────────────────────────────────────
MAP_TOWN  = 'town'
MAP_NORTH = 'north'    # tundra biome
MAP_SOUTH = 'south'    # desert biome
MAP_EAST  = 'east'     # forest biome
MAP_WEST  = 'west'     # swamp biome

# Haunted fortress-towns beyond each biome's far edge
MAP_EAST_TOWN  = 'east_town'    # Shadow Grove beyond forest
MAP_NORTH_TOWN = 'north_town'   # Frost Citadel beyond tundra
MAP_SOUTH_TOWN = 'south_town'   # Sunken Fortress beyond desert
MAP_WEST_TOWN  = 'west_town'    # Murk Stronghold beyond swamp

BIOME_MAP_KEYS = {MAP_NORTH, MAP_SOUTH, MAP_EAST, MAP_WEST}
HAUNT_MAP_KEYS = {MAP_EAST_TOWN, MAP_NORTH_TOWN, MAP_SOUTH_TOWN, MAP_WEST_TOWN}

BIOME_NAMES = {
    MAP_NORTH:      'The Frozen Wastes',
    MAP_SOUTH:      'The Sunbaked Reaches',
    MAP_EAST:       'The Verdant Wilds',
    MAP_WEST:       'The Murk Hollows',
    MAP_EAST_TOWN:  'The Shadow Grove',
    MAP_NORTH_TOWN: 'The Frost Citadel',
    MAP_SOUTH_TOWN: 'The Sunken Fortress',
    MAP_WEST_TOWN:  'The Murk Stronghold',
}

# Gate → destination map
GATE_DESTINATIONS = {
    MAP_TOWN: {
        T_GATE_N: MAP_NORTH, T_GATE_S: MAP_SOUTH,
        T_GATE_E: MAP_EAST,  T_GATE_W: MAP_WEST,
    },
    # biomes: return gate + advance gate to haunted town
    MAP_NORTH: {T_GATE_S: MAP_TOWN,  T_GATE_N: MAP_NORTH_TOWN},
    MAP_SOUTH: {T_GATE_N: MAP_TOWN,  T_GATE_S: MAP_SOUTH_TOWN},
    MAP_EAST:  {T_GATE_W: MAP_TOWN,  T_GATE_E: MAP_EAST_TOWN},
    MAP_WEST:  {T_GATE_E: MAP_TOWN,  T_GATE_W: MAP_WEST_TOWN},
    # haunted towns gate back to biome only (castle is entered via dungeon entrance)
    MAP_EAST_TOWN:  {T_GATE_W: MAP_EAST},
    MAP_NORTH_TOWN: {T_GATE_S: MAP_NORTH},
    MAP_SOUTH_TOWN: {T_GATE_N: MAP_SOUTH},
    MAP_WEST_TOWN:  {T_GATE_E: MAP_WEST},
}

# Which gate tile faces a player arriving at a map (for spawn placement)
ARRIVAL_GATE = {
    MAP_NORTH:      T_GATE_S,
    MAP_SOUTH:      T_GATE_N,
    MAP_EAST:       T_GATE_W,
    MAP_WEST:       T_GATE_E,
    MAP_TOWN:       None,          # handled specially per origin gate
    MAP_EAST_TOWN:  T_GATE_W,
    MAP_NORTH_TOWN: T_GATE_S,
    MAP_SOUTH_TOWN: T_GATE_N,
    MAP_WEST_TOWN:  T_GATE_E,
}

# ─── Directions ───────────────────────────────────────────────────────────────
DIR_UP    = ( 0, -1)
DIR_DOWN  = ( 0,  1)
DIR_LEFT  = (-1,  0)
DIR_RIGHT = ( 1,  0)
DIRS_4    = [DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT]

# ─── Item Type Tags ───────────────────────────────────────────────────────────
IT_WEAPON     = 'weapon'
IT_RANGED     = 'ranged'
IT_AMMO       = 'ammo'
IT_CONSUMABLE = 'consumable'
IT_TOOL       = 'tool'
IT_MAGIC      = 'magic'
IT_INGREDIENT = 'ingredient'
IT_CURRENCY   = 'currency'
IT_LIGHT      = 'light'
IT_ARMOR      = 'armor'

# ─── Combat ───────────────────────────────────────────────────────────────────
PLAYER_IFRAMES    = 45
ATTACK_VIS_FRAMES = 10
PLAYER_START_HP   = 100
PLAYER_START_MANA = 60

# ─── Lighting ─────────────────────────────────────────────────────────────────
OVERWORLD_AMBIENT = 255
HAUNT_AMBIENT     = 70    # haunted towns: dim but navigable
DUNGEON1_AMBIENT  = 60
DUNGEON2_AMBIENT  = 20
DUNGEON3_AMBIENT  = 10

# ─── Dungeon Registry ─────────────────────────────────────────────────────────
DUNGEONS = {
    # ── East (Forest) biome ──────────────────────────────────────────────────
    0: {'name': 'The Verdant Labyrinth', 'biome': MAP_EAST,  'levels': 1,
        'style': 'bsp',   'ambient': DUNGEON1_AMBIENT,
        'enemies': ['slime','spider','bat'],  'boss': 'giant_spider',
        'floor': T_FLOOR,      'wall': T_VINE_WALL, 'theme_col': (60,120,40)},
    1: {'name': 'The Stone Warrens',     'biome': MAP_EAST,  'levels': 2,
        'style': 'cave',  'ambient': DUNGEON2_AMBIENT,
        'enemies': ['bat','goblin','troll'], 'boss': 'troll',
        'floor': T_CAVE_FLOOR, 'wall': T_CAVE_WALL, 'theme_col': (80,70,60)},
    2: {'name': 'The Haunted Halls',     'biome': MAP_EAST,  'levels': 2,
        'style': 'drunk', 'ambient': DUNGEON3_AMBIENT,
        'enemies': ['skeleton','ghost','bat'], 'boss': 'skeleton',
        'floor': T_FLOOR,      'wall': T_WALL,      'theme_col': (60,50,90)},
    # ── North (Tundra) biome ─────────────────────────────────────────────────
    3: {'name': 'The Frozen Vaults',     'biome': MAP_NORTH, 'levels': 2,
        'style': 'cave',  'ambient': DUNGEON2_AMBIENT,
        'enemies': ['yeti','bat','skeleton'], 'boss': 'yeti',
        'floor': T_CAVE_FLOOR, 'wall': T_ICE_WALL,  'theme_col': (120,160,200)},
    4: {'name': "The Ice Queen's Lair",  'biome': MAP_NORTH, 'levels': 3,
        'style': 'bsp',   'ambient': DUNGEON3_AMBIENT,
        'enemies': ['ice_wraith','yeti','skeleton'], 'boss': 'ice_wraith',
        'floor': T_FLOOR,      'wall': T_ICE_WALL,  'theme_col': (140,180,220)},
    # ── South (Desert) biome ─────────────────────────────────────────────────
    5: {'name': 'The Sunken Tombs',      'biome': MAP_SOUTH, 'levels': 2,
        'style': 'bsp',   'ambient': DUNGEON2_AMBIENT,
        'enemies': ['scorpion','mummy','skeleton'], 'boss': 'mummy',
        'floor': T_FLOOR,      'wall': T_WALL,      'theme_col': (180,140,80)},
    6: {'name': 'The Scorched Crypts',   'biome': MAP_SOUTH, 'levels': 3,
        'style': 'drunk', 'ambient': DUNGEON3_AMBIENT,
        'enemies': ['scorpion','goblin','ghost'], 'boss': 'scorpion',
        'floor': T_CAVE_FLOOR, 'wall': T_CAVE_WALL, 'theme_col': (160,120,60)},
    # ── West (Swamp) biome ───────────────────────────────────────────────────
    7: {'name': 'The Murk Warrens',      'biome': MAP_WEST,  'levels': 2,
        'style': 'cave',  'ambient': DUNGEON2_AMBIENT,
        'enemies': ['swamp_toad','spider','slime'], 'boss': 'troll',
        'floor': T_CAVE_FLOOR, 'wall': T_VINE_WALL, 'theme_col': (50,90,40)},
    8: {'name': 'The Bog of Shadows',    'biome': MAP_WEST,  'levels': 3,
        'style': 'drunk', 'ambient': DUNGEON3_AMBIENT,
        'enemies': ['will_o','ghost','swamp_toad'], 'boss': 'ghost',
        'floor': T_FLOOR,      'wall': T_WALL,      'theme_col': (40,70,50)},
    # ── Castle dungeons (accessed from haunted towns, dragon bosses) ─────────
    9:  {'name': 'The Dark Keep',        'biome': MAP_EAST_TOWN,  'levels': 5,
         'style': 'bsp',   'ambient': DUNGEON3_AMBIENT,
         'enemies': ['skeleton','ghost','will_o','bat'], 'boss': 'dragon',
         'floor': T_FLOOR,      'wall': T_VINE_WALL,  'theme_col': (40,55,35)},
    10: {'name': 'The Frost Citadel',    'biome': MAP_NORTH_TOWN, 'levels': 5,
         'style': 'bsp',   'ambient': DUNGEON3_AMBIENT,
         'enemies': ['ice_wraith','yeti','skeleton'],  'boss': 'frost_dragon',
         'floor': T_CAVE_FLOOR, 'wall': T_ICE_WALL,   'theme_col': (90,130,170)},
    11: {'name': 'The Sunken Temple',    'biome': MAP_SOUTH_TOWN, 'levels': 5,
         'style': 'cave',  'ambient': DUNGEON3_AMBIENT,
         'enemies': ['mummy','scorpion','ghost'],      'boss': 'sand_dragon',
         'floor': T_FLOOR,      'wall': T_WALL,        'theme_col': (160,120,60)},
    12: {'name': 'The Murk Fortress',    'biome': MAP_WEST_TOWN,  'levels': 5,
         'style': 'drunk', 'ambient': DUNGEON3_AMBIENT,
         'enemies': ['ghost','will_o','swamp_toad','bat'], 'boss': 'swamp_dragon',
         'floor': T_CAVE_FLOOR, 'wall': T_CAVE_WALL,  'theme_col': (35,55,40)},
}

BIOME_DUNGEONS = {
    MAP_EAST:       [0, 1, 2],
    MAP_NORTH:      [3, 4],
    MAP_SOUTH:      [5, 6],
    MAP_WEST:       [7, 8],
    # Haunted towns have NO dungeon entrances (T_ENTRANCE) –
    # their castles are accessed via a gate on the far wall.
}

# Castle dungeon accessed via gate from haunted town (not T_ENTRANCE)
CASTLE_DUNGEON_FOR_HAUNT = {
    MAP_EAST_TOWN:  9,
    MAP_NORTH_TOWN: 10,
    MAP_SOUTH_TOWN: 11,
    MAP_WEST_TOWN:  12,
}

# Which gate direction is the RETURN gate (back to biome) for each haunted town
HAUNT_RETURN_GATE = {
    MAP_EAST_TOWN:  T_GATE_W,
    MAP_NORTH_TOWN: T_GATE_S,
    MAP_SOUTH_TOWN: T_GATE_N,
    MAP_WEST_TOWN:  T_GATE_E,
}
# Which gate direction is the CASTLE gate (forward into the castle) for each haunted town
HAUNT_CASTLE_GATE = {
    MAP_EAST_TOWN:  T_GATE_E,
    MAP_NORTH_TOWN: T_GATE_N,
    MAP_SOUTH_TOWN: T_GATE_S,
    MAP_WEST_TOWN:  T_GATE_W,
}

# ─── UI ───────────────────────────────────────────────────────────────────────
HUD_H        = 135
VIEWPORT_H   = SCREEN_HEIGHT - HUD_H
HOTBAR_SLOTS    = 8   # single-player
HOTBAR_SLOTS_2P = 5   # per player in 2P (P1 keys 1-5, P2 keys 6-0)
MSG_MAX      = 6
MSG_DURATION = 240

# ─── Player speed & sizes ─────────────────────────────────────────────────────
PLAYER_SPEED     = 3.0
SWIM_SPEED_MULT  = 0.5
SLOW_SPEED_MULT  = 0.6
ENTITY_SIZE      = 26

# ─── Difficulty ───────────────────────────────────────────────────────────────
DIFFICULTY_EASY   = 0
DIFFICULTY_NORMAL = 1
DIFFICULTY_HARD   = 2
DIFFICULTY_LABELS = ['Easy', 'Normal', 'Hard']
DIFFICULTY_DMG_MULT = {
    DIFFICULTY_EASY:   0.5,
    DIFFICULTY_NORMAL: 1.0,
    DIFFICULTY_HARD:   1.5,
}

# ─── Respawn & Timers ─────────────────────────────────────────────────────────
OVERWORLD_MOB_RESPAWN_FRAMES = 18000
ITEM_RESPAWN_FRAMES          = 18000
DROPPED_ITEM_LIFETIME_FRAMES = 7200
DEAD_BODY_LIFETIME_FRAMES    = 3600   # ~60 s before body fades away

# ─── Autoaim ─────────────────────────────────────────────────────────────────
AUTOAIM_RADIUS = 150

# ─── Mimic ───────────────────────────────────────────────────────────────────
MIMIC_CHANCE = 0.12   # 12 % of chests are mimics (checked deterministically)

# ─── v5 Additions ─────────────────────────────────────────────────────────────
ST_SETTINGS  = 'settings'

PLAYER_ACTIONS = [
    'up','down','left','right',
    'attack','interact','inventory',
    'aim_toggle','unequip',
    'hotbar_prev','hotbar_next',
    'hotbar_1','hotbar_2','hotbar_3','hotbar_4','hotbar_5',
    'hotbar_6','hotbar_7','hotbar_8',
    'pause',
]

ACTION_LABELS = {
    'up':'Move Up','down':'Move Down','left':'Move Left','right':'Move Right',
    'attack':'Attack','interact':'Interact / Gate',
    'inventory':'Open Inventory','aim_toggle':'Toggle Aim',
    'unequip':'Unequip Slot','hotbar_prev':'Prev Hotbar','hotbar_next':'Next Hotbar',
    'hotbar_1':'Hotbar 1','hotbar_2':'Hotbar 2','hotbar_3':'Hotbar 3',
    'hotbar_4':'Hotbar 4','hotbar_5':'Hotbar 5',
    'hotbar_6':'Hotbar 6 (P2 slot 1)','hotbar_7':'Hotbar 7 (P2 slot 2)',
    'hotbar_8':'Hotbar 8 (P2 slot 3)',
    'pause':'Pause / Menu',
}

PLAYER_NAMES = ["Player 1","Player 2"]
