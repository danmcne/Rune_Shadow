"""
Rune & Shadow - Placeholder Asset Generator
============================================
Run this script ONCE to populate the assets/ folder with coloured-block
PNG files that look identical to the current procedural rendering.

When an artist delivers real sprites, simply drop them into the same paths
and the game will automatically use them — no code changes needed.

Usage:
    python create_placeholder_assets.py

Options:
    --clean     Delete existing assets/ folder first
    --quiet     Suppress per-file output
"""

import sys
import os
import shutil
import argparse
from pathlib import Path

import pygame

# Make sure we can import our own modules regardless of cwd
sys.path.insert(0, str(Path(__file__).parent))
from constants import *
from items import ITEMS
from animation import State, Dir, _STATE_CONFIG

# ─── Configuration ────────────────────────────────────────────────────────────
TILE_SZ   = TILE_SIZE       # 32 — tile sprites
ENTITY_SZ = ENTITY_SIZE     # 26 — entity sprites  (must match AssetManager.entity_size)
ICON_SZ   = 32              # item icon sprites
PROJ_SZ   = 12              # projectile sprites

BASE = Path(__file__).parent / 'assets'

ENTITY_TYPES = {
    'player':       COL_PLAYER,
    'slime':        COL_SLIME,
    'bat':          COL_BAT,
    'spider':       COL_SPIDER,
    'goblin':       COL_GOBLIN,
    'skeleton':     COL_SKELETON,
    'ghost':        COL_GHOST,
    'troll':        COL_TROLL,
    'wolf':         COL_WOLF,
    'giant_spider': COL_BIG_SPIDER,
}

PROJECTILE_TYPES = {
    'stone':     COL_STONE,
    'arrow':     COL_ARROW,
    'fireball':  COL_FIRE,
    'frost':     (160, 220, 255),
    'lightning': YELLOW,
    'arcane':    COL_MAGIC,
    'bone':      COL_BONE,
    'web':       (230, 230, 200),
}

FX_TYPES = {
    'attack_slash': (YELLOW, 3),
    'hit_spark':    (ORANGE, 2),
    'fire_burst':   (COL_FIRE, 4),
    'frost_burst':  ((160, 220, 255), 3),
    'magic_ring':   (COL_MAGIC, 4),
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def save(surf: pygame.Surface, path: Path, quiet: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surf, str(path))
    if not quiet:
        print(f"  wrote {path.relative_to(BASE.parent)}")


# ─── Tile sprites ─────────────────────────────────────────────────────────────

def _checkerboard(col_a, col_b, sz=TILE_SZ, check=8) -> pygame.Surface:
    """Two-colour checkerboard — makes tiles look less flat."""
    s = pygame.Surface((sz, sz))
    for y in range(0, sz, check):
        for x in range(0, sz, check):
            use_b = ((x // check) + (y // check)) % 2
            pygame.draw.rect(s, col_b if use_b else col_a,
                             (x, y, check, check))
    pygame.draw.rect(s, tuple(max(0, c-20) for c in col_a), (0, 0, sz, sz), 1)
    return s


def _solid_tile(col, sz=TILE_SZ) -> pygame.Surface:
    s = pygame.Surface((sz, sz))
    s.fill(col)
    pygame.draw.rect(s, tuple(max(0, c-30) for c in col), (0, 0, sz, sz), 1)
    return s


def _tile_with_detail(col, detail_col, detail_fn, sz=TILE_SZ) -> pygame.Surface:
    s = _solid_tile(col, sz)
    detail_fn(s, detail_col, sz)
    return s


def _grass_detail(s, col, sz):
    import random; rng = random.Random(42)
    for _ in range(6):
        x = rng.randint(4, sz-6)
        y = rng.randint(4, sz-6)
        pygame.draw.line(s, col, (x, y), (x-1, y-4), 1)
        pygame.draw.line(s, col, (x+3, y+1), (x+2, y-3), 1)


def _water_detail(s, col, sz):
    for y in range(6, sz-4, 8):
        pygame.draw.line(s, col, (4, y), (sz-4, y), 1)
        pygame.draw.line(s, col, (4, y+4), (sz//2, y+4), 1)


def _mountain_detail(s, col, sz):
    pygame.draw.polygon(s, col, [(sz//2, 4), (sz-6, sz-4), (6, sz-4)])
    pygame.draw.polygon(s, tuple(max(0,c-30) for c in col),
                        [(sz//2, 4), (sz-6, sz-4), (6, sz-4)], 2)


def _tree_detail(s, col, sz):
    trunk = tuple(max(0, c-40) for c in col)
    pygame.draw.rect(s, trunk, (sz//2-3, sz//2, 6, sz//2-2))
    pygame.draw.polygon(s, col, [(sz//2, 4), (sz-4, sz//2+4), (4, sz//2+4)])


def _chest_detail(s, col, sz):
    lighter = tuple(min(255, c+60) for c in col)
    pygame.draw.rect(s, lighter, (4, 4, sz-8, sz-8))
    pygame.draw.rect(s, (60,30,10), (4, sz//2-2, sz-8, 4))
    pygame.draw.rect(s, GOLD, (sz//2-3, sz//2-5, 6, 10))


def _shrine_detail(s, col, sz):
    lighter = (220, 220, 255)
    pygame.draw.polygon(s, lighter,
                        [(sz//2, 3), (sz-4, sz-4), (4, sz-4)])
    for i, c in enumerate([(200,200,255),(180,180,255),(160,160,255)]):
        pygame.draw.circle(s, c, (sz//2, sz//2), 6-i*2)


def make_tile_sprites(quiet: bool):
    print("\n[Tiles]")
    out = ensure(BASE / 'tiles')

    tile_makers = {
        T_DEEP_WATER:  lambda: _checkerboard((20,50,160),(30,65,185)),
        T_WATER:       lambda: _tile_with_detail((65,105,225),(90,140,255),_water_detail),
        T_SAND:        lambda: _checkerboard((238,214,175),(220,195,155)),
        T_GRASS:       lambda: _tile_with_detail((34,139,34),(55,170,55),_grass_detail),
        T_FOREST:      lambda: _tile_with_detail((0,80,0),(20,110,20),_tree_detail),
        T_MOUNTAIN:    lambda: _tile_with_detail((110,110,110),(140,140,140),_mountain_detail),
        T_ENTRANCE:    lambda: _solid_tile((80,40,20)),
        T_FLOOR:       lambda: _checkerboard((190,170,130),(175,155,115)),
        T_WALL:        lambda: _checkerboard((90,70,55),(70,52,38)),
        T_DOOR:        lambda: _solid_tile((160,100,50)),
        T_STAIRS_UP:   lambda: _tile_with_detail((190,170,130),(255,215,0),
                                lambda s,c,sz: pygame.draw.polygon(s,c,
                                    [(sz//2,5),(sz-6,sz-5),(6,sz-5)])),
        T_STAIRS_DOWN: lambda: _solid_tile((200,160,0)),
        T_CHEST:       lambda: _tile_with_detail((200,140,30),GOLD,_chest_detail),
        T_PATH:        lambda: _checkerboard((160,140,100),(145,125,85)),
        T_CAVE_FLOOR:  lambda: _checkerboard((75,65,55),(60,52,44)),
        T_CAVE_WALL:   lambda: _checkerboard((45,38,32),(35,28,24)),
        T_VINE_WALL:   lambda: _tile_with_detail((30,90,20),(20,70,15),_tree_detail),
        T_SHRINE:      lambda: _tile_with_detail((200,200,255),(220,220,255),_shrine_detail),
    }

    from asset_manager import TILE_SPRITE_NAMES
    for tid, name in TILE_SPRITE_NAMES.items():
        surf = tile_makers.get(tid, lambda: _solid_tile((128,128,128)))()
        save(surf, out / f'{name}.png', quiet)


# ─── Entity sprites ───────────────────────────────────────────────────────────

def _dir_indicator(s: pygame.Surface, direction: str, sz: int):
    """Draw a small dot on the "face" side to show direction."""
    offsets = {
        Dir.N: (sz//2, 4),
        Dir.S: (sz//2, sz-5),
        Dir.E: (sz-5,  sz//2),
        Dir.W: (5,     sz//2),
    }
    cx, cy = offsets.get(direction, (sz//2, sz-5))
    pygame.draw.circle(s, (0, 0, 0), (cx, cy), 3)
    pygame.draw.circle(s, WHITE,     (cx, cy), 2)


def _make_entity_frame(base_col, state: str, direction: str,
                       frame: int, is_ghost: bool = False,
                       sz: int = ENTITY_SZ) -> pygame.Surface:
    """Generate one coloured-block placeholder frame for an entity."""
    s = pygame.Surface((sz, sz), pygame.SRCALPHA)

    alpha = 180 if is_ghost else 255

    # State-based colour tints
    tint = base_col
    if state == State.HURT:
        tint = tuple(min(255, c + 80) if i == 0 else max(0, c - 40)
                     for i, c in enumerate(base_col))   # red flash
    elif state == State.ATTACK:
        tint = tuple(min(255, c + 50) for c in base_col)   # slightly brighter
    elif state == State.DEAD:
        # Desaturate
        avg = sum(base_col) // 3
        tint = tuple((c + avg) // 2 for c in base_col)

    # Animation bobbing (walk frames offset vertically)
    bob = 0
    if state == State.WALK:
        bob = [0, -1, 0, 1][frame % 4]

    r = pygame.Rect(1, 1 + bob, sz - 2, sz - 2 - abs(bob))
    pygame.draw.rect(s, (*tint, alpha), r, border_radius=4)
    pygame.draw.rect(s, (0, 0, 0, alpha), r, 1, border_radius=4)

    # Attack arc indicator
    if state == State.ATTACK:
        offsets = {Dir.N:(sz//2,2), Dir.S:(sz//2,sz-3),
                   Dir.E:(sz-3,sz//2), Dir.W:(2,sz//2)}
        ax, ay = offsets.get(direction, (sz//2, sz-3))
        pygame.draw.line(s, (255,255,200,220), (sz//2, sz//2), (ax, ay), 3)

    _dir_indicator(s, direction, sz)
    return s


def make_entity_sprites(quiet: bool):
    print("\n[Entities]")
    for etype, col in ENTITY_TYPES.items():
        out     = ensure(BASE / 'entities' / etype)
        is_ghost = (etype == 'ghost')
        for state in State.ALL:
            cfg    = _STATE_CONFIG[state]
            length = cfg['length']
            for direction in Dir.ALL:
                for frame in range(length):
                    surf = _make_entity_frame(col, state, direction, frame,
                                              is_ghost=is_ghost)
                    fname = f'{state}_{direction}_{frame}.png'
                    save(surf, out / fname, quiet)


# ─── Item icons ───────────────────────────────────────────────────────────────

def _make_icon(col, sz=ICON_SZ, shape='square') -> pygame.Surface:
    s = pygame.Surface((sz, sz), pygame.SRCALPHA)
    lighter = tuple(min(255, c+60) for c in col)
    darker  = tuple(max(0,   c-40) for c in col)
    if shape == 'diamond':
        pts = [(sz//2, 3), (sz-3, sz//2), (sz//2, sz-3), (3, sz//2)]
        pygame.draw.polygon(s, col, pts)
        pygame.draw.polygon(s, darker, pts, 2)
    elif shape == 'circle':
        pygame.draw.circle(s, col,     (sz//2, sz//2), sz//2-2)
        pygame.draw.circle(s, darker,  (sz//2, sz//2), sz//2-2, 2)
        pygame.draw.circle(s, lighter, (sz//2-3, sz//2-3), sz//6)
    elif shape == 'blade':
        pygame.draw.polygon(s, col, [(sz//2,3),(sz-4,sz-4),(sz//2,sz-8),(4,sz-4)])
        pygame.draw.polygon(s, darker, [(sz//2,3),(sz-4,sz-4),(sz//2,sz-8),(4,sz-4)], 2)
        pygame.draw.line(s, lighter, (sz//2, 6), (sz//2, sz-6), 2)
    elif shape == 'staff':
        pygame.draw.line(s, col, (sz//4, sz-4), (3*sz//4, 4), 4)
        pygame.draw.circle(s, lighter, (3*sz//4, 4), 5)
    elif shape == 'scroll':
        pygame.draw.rect(s, col, (5, 4, sz-10, sz-8), border_radius=3)
        pygame.draw.rect(s, darker, (5,4,sz-10,sz-8), 1, border_radius=3)
        for y in range(10, sz-8, 5):
            pygame.draw.line(s, darker, (8, y), (sz-8, y), 1)
    elif shape == 'potion':
        pygame.draw.rect(s, col, (sz//2-3, 4, 6, 6))
        pygame.draw.ellipse(s, col, (4, 10, sz-8, sz-14))
        pygame.draw.ellipse(s, darker, (4,10,sz-8,sz-14), 2)
        pygame.draw.circle(s, lighter, (sz//3, sz//2+2), 4)
    else:
        pygame.draw.rect(s, col, (4,4,sz-8,sz-8), border_radius=3)
        pygame.draw.rect(s, darker, (4,4,sz-8,sz-8), 1, border_radius=3)
        pygame.draw.rect(s, lighter, (6,6,sz//3,sz//3))
    return s


_ICON_SHAPES = {
    'knife':      (LIGHT_GRAY,  'blade'),
    'staff':      ((120,80,200),'staff'),
    'axe':        (BROWN,       'blade'),
    'pickaxe':    (GRAY,        'blade'),
    'sword':      (LIGHT_GRAY,  'blade'),
    'spear':      ((200,200,180),'blade'),
    'sling':      (BROWN,       'square'),
    'bow':        (BROWN,       'staff'),
    'spell_fire': (ORANGE,      'scroll'),
    'spell_frost':((140,200,255),'scroll'),
    'spell_bolt': (YELLOW,      'scroll'),
    'spell_basic':(CYAN,        'scroll'),
    'stone':      (COL_STONE,   'circle'),
    'arrow':      (COL_ARROW,   'blade'),
    'mushroom':   (RED,         'circle'),
    'blue_flower':((100,130,255),'circle'),
    'bread':      ((220,200,150),'square'),
    'herb':       (GREEN,       'circle'),
    'potion':     (RED,         'potion'),
    'mana_pot':   (BLUE,        'potion'),
    'meat':       ((220,100,80),'square'),
    'goo':        (COL_SLIME,   'circle'),
    'silk':       (WHITE,       'square'),
    'spider_eye': (RED,         'circle'),
    'bone':       (COL_SKELETON,'blade'),
    'feather':    (WHITE,       'blade'),
    'magic_dust': (CYAN,        'diamond'),
    'hide':       (BROWN,       'square'),
    'mana_crys':  (BLUE,        'diamond'),
    'candle':     (YELLOW,      'potion'),
    'lantern':    (ORANGE,      'potion'),
    'torch':      (ORANGE,      'staff'),
    'coin':       (GOLD,        'circle'),
    'gem':        (CYAN,        'diamond'),
    'big_gem':    ((255,100,200),'diamond'),
    'rope':       (BROWN,       'square'),
    'boomerang':  ((200,160,80),'blade'),
    'shield':     (GRAY,        'square'),
}


def make_item_icons(quiet: bool):
    print("\n[Item Icons]")
    out = ensure(BASE / 'items')
    for iid in ITEMS:
        col, shape = _ICON_SHAPES.get(iid, (LIGHT_GRAY, 'square'))
        surf = _make_icon(col, ICON_SZ, shape)
        save(surf, out / f'{iid}.png', quiet)


# ─── Projectile sprites ───────────────────────────────────────────────────────

def make_projectile_sprites(quiet: bool):
    print("\n[Projectiles]")
    out = ensure(BASE / 'projectiles')
    for kind, col in PROJECTILE_TYPES.items():
        s = pygame.Surface((PROJ_SZ, PROJ_SZ), pygame.SRCALPHA)
        pygame.draw.ellipse(s, col, (0, 0, PROJ_SZ, PROJ_SZ))
        pygame.draw.ellipse(s, tuple(min(255,c+80) for c in col),
                            (2, 2, PROJ_SZ-4, PROJ_SZ-4))
        save(s, out / f'{kind}.png', quiet)


# ─── FX sprites ───────────────────────────────────────────────────────────────

def make_fx_sprites(quiet: bool):
    print("\n[FX]")
    out = ensure(BASE / 'fx')
    for name, (col, n_frames) in FX_TYPES.items():
        for frame in range(n_frames):
            sz    = 32
            alpha = int(240 * (1 - frame / max(1, n_frames - 1)))
            radius= 4 + frame * 6
            s     = pygame.Surface((sz, sz), pygame.SRCALPHA)
            pygame.draw.circle(s, (*col, alpha), (sz//2, sz//2),
                               min(radius, sz//2 - 1))
            save(s, out / f'{name}_{frame}.png', quiet)


# ─── UI sprites ───────────────────────────────────────────────────────────────

def make_ui_sprites(quiet: bool):
    print("\n[UI]")
    out = ensure(BASE / 'ui')

    def flat(w, h, col, border=None):
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        s.fill((*col, 200))
        if border:
            pygame.draw.rect(s, (*border, 255), (0,0,w,h), 2)
        return s

    pieces = {
        'hud_bg':      flat(SCREEN_WIDTH, HUD_H, (20,20,28), (80,80,100)),
        'hotbar_slot': flat(44, 44, (30,30,45), (60,60,90)),
        'hotbar_sel':  flat(44, 44, (50,50,90), YELLOW),
    }
    for name, surf in pieces.items():
        save(surf, out / f'{name}.png', quiet)


# ═══════════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Generate placeholder PNG assets for Rune & Shadow.')
    parser.add_argument('--clean', action='store_true',
                        help='Delete existing assets/ folder first')
    parser.add_argument('--quiet', action='store_true',
                        help='Suppress per-file output')
    args = parser.parse_args()

    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
    pygame.init()
    pygame.display.set_mode((1, 1))

    if args.clean and BASE.exists():
        print(f"Removing {BASE} …")
        shutil.rmtree(BASE)

    print(f"Writing placeholder assets to  {BASE}/")
    make_tile_sprites(args.quiet)
    make_entity_sprites(args.quiet)
    make_item_icons(args.quiet)
    make_projectile_sprites(args.quiet)
    make_fx_sprites(args.quiet)
    make_ui_sprites(args.quiet)

    # Count files
    total = sum(1 for _ in BASE.rglob('*.png'))
    print(f"\n✓ Done — {total} PNG files written to assets/")
    print("  Drop in real art to replace any placeholder.")
    pygame.quit()


if __name__ == '__main__':
    main()
