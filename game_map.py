"""
Rune & Shadow - GameMap v3
Added: map_key, dungeon_level, gate positions, biome_dungeon_positions.
"""
import pygame
from constants import *
from items import Item


class GroundItem:
    def __init__(self, item: Item, tx: int, ty: int, count: int = 1,
                 lifetime: int = None):
        self.item     = item
        self.count    = count
        self.tx       = tx
        self.ty       = ty
        self.x        = tx * TILE_SIZE + TILE_SIZE // 2 - 8
        self.y        = ty * TILE_SIZE + TILE_SIZE // 2 - 8
        self._bob     = 0
        self.lifetime = lifetime

    def update(self):
        self._bob = (self._bob + 1) % 60
        if self.lifetime is not None:
            self.lifetime -= 1

    @property
    def expired(self):
        return self.lifetime is not None and self.lifetime <= 0

    def draw(self, surf: pygame.Surface, cx: int, cy: int):
        sx = self.x - cx
        sy = self.y - cy + (2 if self._bob < 30 else -2)
        rect = pygame.Rect(sx, sy, 16, 16)
        pygame.draw.rect(surf, self.item.color, rect)
        pygame.draw.rect(surf, WHITE, rect, 1)
        if self.lifetime is not None and self.lifetime < 300:
            if (self.lifetime // 10) % 2 == 0:
                overlay = pygame.Surface((16, 16), pygame.SRCALPHA)
                overlay.fill((255,255,255,80))
                surf.blit(overlay, (sx, sy))


class GameMap:
    def __init__(self, width: int, height: int,
                 is_dungeon: bool = False,
                 dungeon_id: int = -1,
                 dungeon_level: int = 0,
                 ambient: int = 255,
                 map_key: str = ''):
        self.width        = width
        self.height       = height
        self.is_dungeon   = is_dungeon
        self.dungeon_id   = dungeon_id
        self.dungeon_level= dungeon_level
        self.ambient      = ambient
        self.map_key      = map_key

        self._tiles: list = [[T_GRASS] * width for _ in range(height)]

        self.entities: list      = []
        self.ground_items: list  = []
        self.respawn_queue: list = []

        self.entrance_tile    = (0, 0)
        self.exit_tile        = (0, 0)
        self.stairs_down_tile = None
        self.chest_opened: set = set()
        self.boss_killed: bool  = False   # tracks if boss was killed this run
        self.ow_entrance      = (0, 0)    # where on the overworld we came from

        # Gate positions (set by generators)
        self.gate_n = None; self.gate_s = None
        self.gate_e = None; self.gate_w = None

        # For biome maps: list of (tx, ty, dun_id) dungeon entrances
        self.biome_dungeon_positions: list = []

    # ── Tile access ──────────────────────────────────────────────────────────
    def get(self, tx, ty):
        if 0 <= tx < self.width and 0 <= ty < self.height:
            return self._tiles[ty][tx]
        return T_WALL

    def set(self, tx, ty, tile):
        if 0 <= tx < self.width and 0 <= ty < self.height:
            self._tiles[ty][tx] = tile

    def walkable(self, tx, ty):
        return tile_walkable(self.get(tx, ty))

    def swimmable(self, tx, ty):
        return tile_swimmable(self.get(tx, ty))

    def in_bounds(self, tx, ty):
        return 0 <= tx < self.width and 0 <= ty < self.height

    def fill(self, tile):
        for y in range(self.height):
            for x in range(self.width):
                self._tiles[y][x] = tile

    def fill_rect(self, x1, y1, x2, y2, tile):
        for y in range(max(0,y1), min(self.height, y2+1)):
            for x in range(max(0,x1), min(self.width, x2+1)):
                self._tiles[y][x] = tile

    def find_walkable_near(self, cx, cy, radius=5):
        """Return nearest walkable tile to (cx,cy) within radius."""
        for r in range(0, radius+1):
            for dy in range(-r, r+1):
                for dx in range(-r, r+1):
                    nx, ny = cx+dx, cy+dy
                    if self.in_bounds(nx, ny) and self.walkable(nx, ny):
                        return (nx, ny)
        return (cx, cy)

    # ── Draw ─────────────────────────────────────────────────────────────────
    def draw(self, surf, cam_x, cam_y, player_px, player_py,
             light_radius_tiles, asset_mgr=None):
        vw, vh = surf.get_width(), surf.get_height()
        tx_s = max(0, cam_x // TILE_SIZE)
        ty_s = max(0, cam_y // TILE_SIZE)
        tx_e = min(self.width,  (cam_x + vw) // TILE_SIZE + 2)
        ty_e = min(self.height, (cam_y + vh) // TILE_SIZE + 2)

        pcx = player_px + ENTITY_SIZE // 2
        pcy = player_py + ENTITY_SIZE // 2
        tint_surf = None

        for ty in range(ty_s, ty_e):
            for tx in range(tx_s, tx_e):
                t  = self._tiles[ty][tx]
                sx = tx * TILE_SIZE - cam_x
                sy = ty * TILE_SIZE - cam_y

                brightness = 255
                if self.is_dungeon and self.ambient < 255:
                    dist = (((tx*TILE_SIZE+16)-pcx)**2 +
                            ((ty*TILE_SIZE+16)-pcy)**2)**0.5
                    max_dist = light_radius_tiles * TILE_SIZE
                    brightness = self.ambient
                    if dist < max_dist:
                        ratio = 1.0 - dist / max_dist
                        brightness = min(255, int(self.ambient + ratio*(255-self.ambient)))
                    if brightness < 10:
                        pygame.draw.rect(surf,(0,0,0),(sx,sy,TILE_SIZE,TILE_SIZE))
                        continue

                sprite = asset_mgr.get_tile(t) if asset_mgr else None
                if sprite:
                    surf.blit(sprite, (sx, sy))
                    if brightness < 255:
                        if not tint_surf:
                            tint_surf = pygame.Surface((TILE_SIZE,TILE_SIZE), pygame.SRCALPHA)
                        tint_surf.fill((brightness,brightness,brightness,255))
                        surf.blit(tint_surf,(sx,sy),special_flags=pygame.BLEND_RGBA_MULT)
                else:
                    col = tile_color(t)
                    if brightness < 255:
                        f = brightness/255
                        col = (int(col[0]*f), int(col[1]*f), int(col[2]*f))
                    pygame.draw.rect(surf, col, (sx,sy,TILE_SIZE,TILE_SIZE))
                    if brightness > 40:
                        pygame.draw.rect(surf,(0,0,0,20),(sx,sy,TILE_SIZE,TILE_SIZE),1)

                # Gate highlight
                if t in GATE_TILES:
                    s2 = pygame.Surface((TILE_SIZE,TILE_SIZE), pygame.SRCALPHA)
                    s2.fill((255,220,80,60))
                    surf.blit(s2,(sx,sy))

        for gi in self.ground_items:
            gi.draw(surf, cam_x, cam_y)

    def get_brightness_at(self, px, py, player_px, player_py, light_radius_tiles):
        if not self.is_dungeon or self.ambient >= 255:
            return 255
        pcx = player_px + ENTITY_SIZE//2
        pcy = player_py + ENTITY_SIZE//2
        dist = ((px-pcx)**2+(py-pcy)**2)**0.5
        max_dist = light_radius_tiles * TILE_SIZE
        if dist >= max_dist: return self.ambient
        ratio = 1.0 - dist/max_dist
        return min(255, int(self.ambient + ratio*(255-self.ambient)))
