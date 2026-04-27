"""
Rune & Shadow - Asset Manager
====================================
Central hub for all image assets.  Every call is cached; missing files
produce a transparent / None result so callers can render a fallback.

DIRECTORY LAYOUT
----------------
  assets/
    tiles/          one PNG per tile type  (32 × 32)
    entities/
      <type>/       e.g. player/, slime/, bat/ …
        <state>_<dir>_<frame>.png   e.g. walk_e_0.png, idle_s_3.png
    items/          one PNG per item id   (32 × 32)
    ui/             HUD panels, cursor, etc.
    projectiles/    one PNG per projectile kind (16 × 16 recommended)
    fx/             attack flashes, explosions, sparks …

TILE SPRITE NAMES  (file: assets/tiles/<name>.png)
---------------------------------------------------------------------------
See TILE_SPRITE_NAMES below – it maps every T_* constant to a filename.

ENTITY SPRITE NAMES
---------------------------------------------------------------------------
  <state>_<dir>_<frame>.png
    states  : idle  walk  attack  hurt  dead
    dirs    : n  s  e  w
    frames  : 0, 1, 2, …  (depends on _STATE_CONFIG in animation.py)

ITEM ICON NAMES  (file: assets/items/<item_id>.png)
---------------------------------------------------------------------------
  Use the exact iid string from items.py, e.g. knife.png, spell_fire.png

PROJECTILE NAMES  (file: assets/projectiles/<kind>.png)
---------------------------------------------------------------------------
  stone.png  arrow.png  fireball.png  frost.png  lightning.png
  arcane.png  bone.png  web.png

FX NAMES  (file: assets/fx/<name>_<frame>.png)
---------------------------------------------------------------------------
  attack_slash_0.png … attack_slash_2.png
  hit_spark_0.png … hit_spark_1.png
  fire_burst_0.png … fire_burst_3.png

UI ELEMENTS  (file: assets/ui/<name>.png)
---------------------------------------------------------------------------
  hud_bg.png       background strip for the bottom HUD
  hotbar_slot.png  inactive hotbar slot border
  hotbar_sel.png   selected hotbar slot border
  heart_full.png   (optional icon-based HP display)
  mana_full.png
"""

import pygame
from pathlib import Path
from constants import (
    T_DEEP_WATER, T_WATER, T_SAND, T_GRASS, T_FOREST, T_MOUNTAIN,
    T_ENTRANCE, T_FLOOR, T_WALL, T_DOOR, T_STAIRS_UP, T_STAIRS_DOWN,
    T_CHEST, T_PATH, T_CAVE_FLOOR, T_CAVE_WALL, T_VINE_WALL, T_SHRINE,
    TILE_SIZE, ENTITY_SIZE,
)

ASSET_DIR = Path(__file__).parent / 'assets'

# ─── Tile-ID → PNG filename mapping ─────────────────────────────────────────
TILE_SPRITE_NAMES: dict[int, str] = {
    T_DEEP_WATER:  'deep_water',
    T_WATER:       'water',
    T_SAND:        'sand',
    T_GRASS:       'grass',
    T_FOREST:      'forest',
    T_MOUNTAIN:    'mountain',
    T_ENTRANCE:    'entrance',
    T_FLOOR:       'floor',
    T_WALL:        'wall',
    T_DOOR:        'door',
    T_STAIRS_UP:   'stairs_up',
    T_STAIRS_DOWN: 'stairs_down',
    T_CHEST:       'chest',
    T_PATH:        'path',
    T_CAVE_FLOOR:  'cave_floor',
    T_CAVE_WALL:   'cave_wall',
    T_VINE_WALL:   'vine_wall',
    T_SHRINE:      'shrine',
}

# ─── Projectile / FX identifier → filename ──────────────────────────────────
PROJECTILE_SPRITE_NAMES: dict[str, str] = {
    'stone':     'stone',
    'arrow':     'arrow',
    'fireball':  'fireball',
    'frost':     'frost',
    'lightning': 'lightning',
    'arcane':    'arcane',
    'bone':      'bone',
    'web':       'web',
}


# ═══════════════════════════════════════════════════════════════════════════════
class AssetManager:
    """
    Loads, scales, and caches all game images.

    All getters return  pygame.Surface | None.
    A None result means "no asset found — caller should draw a fallback".

    Sizes
    -----
      tile_size    : expected size for tile sprites  (default TILE_SIZE = 32)
      entity_size  : expected size for entity sprites (default ENTITY_SIZE = 26)
      icon_size    : expected size for item icons     (default 32)
      proj_size    : expected size for projectile sprites (default 12)
    """

    def __init__(self,
                 tile_size:   int = TILE_SIZE,
                 entity_size: int = ENTITY_SIZE,
                 icon_size:   int = 32,
                 proj_size:   int = 12):
        self.tile_size   = tile_size
        self.entity_size = entity_size
        self.icon_size   = icon_size
        self.proj_size   = proj_size

        # Caches: key → Surface or False (False = known-missing, skip re-check)
        self._tile_cache:   dict = {}
        self._entity_cache: dict = {}
        self._item_cache:   dict = {}
        self._proj_cache:   dict = {}
        self._fx_cache:     dict = {}
        self._ui_cache:     dict = {}

        self._missing_logged: set = set()   # suppress repeated warnings

    # ─────────────────────────────────────────────────────────────────────────
    #  Public API
    # ─────────────────────────────────────────────────────────────────────────

    def get_tile(self, tile_id: int) -> 'pygame.Surface | None':
        """
        Return a tile sprite or None.
        File: assets/tiles/<name>.png   (expected 32 × 32)
        """
        if tile_id in self._tile_cache:
            return self._tile_cache[tile_id] or None
        name = TILE_SPRITE_NAMES.get(tile_id)
        if not name:
            self._tile_cache[tile_id] = False
            return None
        path = ASSET_DIR / 'tiles' / f'{name}.png'
        surf = self._load_and_scale(path, self.tile_size, self.tile_size)
        self._tile_cache[tile_id] = surf or False
        return surf

    def get_entity_frame(self, entity_type: str, state: str,
                         direction: str, frame: int) -> 'pygame.Surface | None':
        """
        Return one animation frame sprite or None.
        File: assets/entities/<entity_type>/<state>_<dir>_<frame>.png
        """
        key = (entity_type, state, direction, frame)
        if key in self._entity_cache:
            return self._entity_cache[key] or None
        path = (ASSET_DIR / 'entities' / entity_type /
                f'{state}_{direction}_{frame}.png')
        surf = self._load_and_scale(path, self.entity_size, self.entity_size)
        self._entity_cache[key] = surf or False
        return surf

    def get_entity_surface(self, animator) -> 'pygame.Surface | None':
        """
        Walk the animator's fallback chain and return the first surface found,
        or None if no sprite exists for this entity type at all.
        """
        for key in animator.fallback_keys():
            surf = self.get_entity_frame(*key)
            if surf is not None:
                return surf
        return None

    def get_item_icon(self, item_id: str) -> 'pygame.Surface | None':
        """
        Return an item icon or None.
        File: assets/items/<item_id>.png   (expected 32 × 32)
        """
        if item_id in self._item_cache:
            return self._item_cache[item_id] or None
        path = ASSET_DIR / 'items' / f'{item_id}.png'
        surf = self._load_and_scale(path, self.icon_size, self.icon_size)
        self._item_cache[item_id] = surf or False
        return surf

    def get_projectile(self, kind: str) -> 'pygame.Surface | None':
        """
        Return a projectile sprite or None.
        File: assets/projectiles/<kind>.png  (expected 12 × 12)
        """
        if kind in self._proj_cache:
            return self._proj_cache[kind] or None
        fname = PROJECTILE_SPRITE_NAMES.get(kind, kind)
        path  = ASSET_DIR / 'projectiles' / f'{fname}.png'
        surf  = self._load_and_scale(path, self.proj_size, self.proj_size)
        self._proj_cache[kind] = surf or False
        return surf

    def get_fx_frame(self, fx_name: str, frame: int) -> 'pygame.Surface | None':
        """
        Return one frame of an effect animation or None.
        File: assets/fx/<fx_name>_<frame>.png
        """
        key = (fx_name, frame)
        if key in self._fx_cache:
            return self._fx_cache[key] or None
        path = ASSET_DIR / 'fx' / f'{fx_name}_{frame}.png'
        surf = self._load(path)   # fx are not auto-scaled; artist controls size
        self._fx_cache[key] = surf or False
        return surf

    def get_ui(self, name: str, w: int = 0, h: int = 0) -> 'pygame.Surface | None':
        """
        Return a UI element sprite or None.
        File: assets/ui/<name>.png
        Optionally scale to (w, h) if both > 0.
        """
        cache_key = (name, w, h)
        if cache_key in self._ui_cache:
            return self._ui_cache[cache_key] or None
        path = ASSET_DIR / 'ui' / f'{name}.png'
        surf = self._load(path)
        if surf and w > 0 and h > 0:
            surf = pygame.transform.scale(surf, (w, h))
        self._ui_cache[cache_key] = surf or False
        return surf

    def invalidate_entity(self, entity_type: str):
        """
        Remove all cached frames for one entity type.
        Call this if you hot-reload sprites at runtime.
        """
        keys = [k for k in self._entity_cache if k[0] == entity_type]
        for k in keys:
            del self._entity_cache[k]

    def invalidate_all(self):
        """Clear every cache (e.g. after loading a new asset pack)."""
        self._tile_cache.clear()
        self._entity_cache.clear()
        self._item_cache.clear()
        self._proj_cache.clear()
        self._fx_cache.clear()
        self._ui_cache.clear()

    # ─────────────────────────────────────────────────────────────────────────
    #  Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _load(self, path: Path) -> 'pygame.Surface | None':
        """Load a PNG, converting to per-pixel alpha.  Returns None on any error."""
        if not path.exists():
            return None
        try:
            surf = pygame.image.load(str(path))
            return surf.convert_alpha()
        except pygame.error as exc:
            tag = str(path)
            if tag not in self._missing_logged:
                self._missing_logged.add(tag)
                print(f"[AssetManager] WARNING: could not load {path}: {exc}")
            return None

    def _load_and_scale(self, path: Path,
                        w: int, h: int) -> 'pygame.Surface | None':
        """Load a PNG and scale it to (w, h) if needed."""
        surf = self._load(path)
        if surf is None:
            return None
        if surf.get_size() != (w, h):
            surf = pygame.transform.scale(surf, (w, h))
        return surf
