"""
Rune & Shadow - Constants
All game-wide constants, tile definitions, colors, and configuration.
"""

# ─── Screen ───────────────────────────────────────────────────────────────────
SCREEN_WIDTH  = 1024
SCREEN_HEIGHT = 768
FPS           = 60
TITLE         = "Rune & Shadow"

# ─── Tile ─────────────────────────────────────────────────────────────────────
TILE_SIZE     = 32
WORLD_W       = 220
WORLD_H       = 220

DUN_W         = 64
DUN_H         = 52

# ─── Tile Type IDs ────────────────────────────────────────────────────────────
T_DEEP_WATER  = 0
T_WATER       = 1
T_SAND        = 2
T_GRASS       = 3
T_FOREST      = 4
T_MOUNTAIN    = 5
T_ENTRANCE    = 6
T_FLOOR       = 7
T_WALL        = 8
T_DOOR        = 9
T_STAIRS_UP   = 10
T_STAIRS_DOWN = 11
T_CHEST       = 12
T_PATH        = 13
T_CAVE_FLOOR  = 14
T_CAVE_WALL   = 15
T_VINE_WALL   = 16
T_SHRINE      = 17

# ─── Tile Properties ──────────────────────────────────────────────────────────
TILE_DATA = {
    T_DEEP_WATER:  ((30,  60, 180), False, False, None),
    T_WATER:       ((65, 105, 225), False, False, None),  # swimmable via entity override
    T_SAND:        ((238,214,175), True,  False, None),
    T_GRASS:       ((34, 139,  34), True,  False, None),
    T_FOREST:      ((0,   80,   0), False, True,  'axe'),
    T_MOUNTAIN:    ((110,110, 110), False, True,  'pickaxe'),
    T_ENTRANCE:    ((80,  40,  20), True,  False, None),
    T_FLOOR:       ((190,170,130), True,  False, None),
    T_WALL:        ((90,  70,  55), False, True,  'pickaxe'),
    T_DOOR:        ((160,100,  50), True,  True,  None),
    T_STAIRS_UP:   ((255,215,   0), True,  False, None),
    T_STAIRS_DOWN: ((200,160,   0), True,  False, None),
    T_CHEST:       ((200,140,  30), False, False, None),
    T_PATH:        ((160,140, 100), True,  False, None),
    T_CAVE_FLOOR:  ((75,  65,  55), True,  False, None),
    T_CAVE_WALL:   ((45,  38,  32), False, True,  'pickaxe'),
    T_VINE_WALL:   ((30,  90,  20), False, True,  'axe'),
    T_SHRINE:      ((200,200, 255), True,  False, None),
}

def tile_color(t):       return TILE_DATA.get(t, (50,50,50))[0]
def tile_walkable(t):    return TILE_DATA.get(t, (50,50,50, True))[1]
def tile_swimmable(t):   return t == T_WATER
def tile_opaque(t):      return TILE_DATA.get(t, (50,50,50))[2]
def tile_tool(t):        return TILE_DATA.get(t, (50,50,50, None, None))[3]

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

COL_STONE     = (170,160,150)
COL_MAGIC     = (100,200,255)
COL_FIRE      = (255,120,  30)
COL_WEB       = (230,230,200)
COL_ARROW     = (200,160, 80)
COL_BONE      = (230,220,200)
COL_WATER_BOLT= (60, 160, 240)

# ─── Game States ──────────────────────────────────────────────────────────────
ST_MENU      = 'menu'
ST_PLAY      = 'play'
ST_INVENTORY = 'inventory'
ST_GAMEOVER  = 'gameover'
ST_PAUSED    = 'paused'
ST_WIN       = 'win'

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
OVERWORLD_AMBIENT   = 255
DUNGEON1_AMBIENT    = 60
DUNGEON2_AMBIENT    = 20
DUNGEON3_AMBIENT    = 10

# ─── Dungeon Registry ─────────────────────────────────────────────────────────
DUNGEONS = {
    0: {
        'name':     'The Verdant Labyrinth',
        'style':    'bsp',
        'ambient':  DUNGEON1_AMBIENT,
        'enemies':  ['slime','spider','bat'],
        'boss':     'giant_spider',
        'floor':    T_FLOOR,
        'wall':     T_VINE_WALL,
        'theme_col': (60,120,40),
    },
    1: {
        'name':     'The Stone Warrens',
        'style':    'cave',
        'ambient':  DUNGEON2_AMBIENT,
        'enemies':  ['bat','goblin','troll'],
        'boss':     'troll',
        'floor':    T_CAVE_FLOOR,
        'wall':     T_CAVE_WALL,
        'theme_col': (80,70,60),
    },
    2: {
        'name':     'The Haunted Halls',
        'style':    'drunk',
        'ambient':  DUNGEON3_AMBIENT,
        'enemies':  ['skeleton','ghost','bat'],
        'boss':     'skeleton',
        'floor':    T_FLOOR,
        'wall':     T_WALL,
        'theme_col': (60,50,90),
    },
}

# ─── UI ───────────────────────────────────────────────────────────────────────
HUD_H         = 90
VIEWPORT_H    = SCREEN_HEIGHT - HUD_H
HOTBAR_SLOTS  = 8
MSG_MAX       = 6
MSG_DURATION  = 240

# ─── Player speed & sizes ─────────────────────────────────────────────────────
PLAYER_SPEED     = 3.0
SWIM_SPEED_MULT  = 0.5
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

# ─── Respawn & Item Decay ─────────────────────────────────────────────────────
OVERWORLD_MOB_RESPAWN_FRAMES = 18000
ITEM_RESPAWN_FRAMES          = 9000
DROPPED_ITEM_LIFETIME_FRAMES = 7200

# ─── Autoaim ─────────────────────────────────────────────────────────────────
AUTOAIM_RADIUS = 150
