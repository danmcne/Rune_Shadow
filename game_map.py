"""
Rune & Shadow - Game Map
Stores the tile grid plus lists of entities and ground-items for one level.
"""
import pygame
from constants import *
from items import Item


class GroundItem:
    """An item lying on the ground at tile (tx, ty)."""
    def __init__(self, item: Item, tx: int, ty: int, count: int = 1,
                 lifetime: int = None):
        self.item    = item
        self.count   = count
        self.x       = tx * TILE_SIZE + TILE_SIZE // 2 - 8
        self.y       = ty * TILE_SIZE + TILE_SIZE // 2 - 8
        self.tx      = tx
        self.ty      = ty
        self._bob    = 0
        # None = permanent; integer = frames until disappear
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
        # Flicker when about to expire
        if self.lifetime is not None and self.lifetime < 300:
            if (self.lifetime // 10) % 2 == 0:
                pygame.draw.rect(surf, (255,255,255,100), rect, 2)


class GameMap:
    """
    Holds a 2-D tile grid plus all entities and ground items
    that currently live on this map.
    """

    def __init__(self, width: int, height: int, is_dungeon: bool = False,
                 dungeon_id: int = -1, ambient: int = 255):
        self.width      = width
        self.height     = height
        self.is_dungeon = is_dungeon
        self.dungeon_id = dungeon_id
        self.ambient    = ambient

        self._tiles: list = [[T_GRASS] * width for _ in range(height)]

        self.entities: list  = []
        self.ground_items: list = []

        self.entrance_tile = (0, 0)
        self.exit_tile     = (0, 0)
        self.chest_opened: set = set()
        self.ow_entrance   = (0, 0)

        # Respawn queue: list of [frames_remaining, spawn_descriptor_dict]
        self.respawn_queue: list = []

        # Item respawn queue: list of [frames_remaining, {iid, count, tx, ty}]
        self.item_respawn_queue: list = []

    # ── Tile access ──────────────────────────────────────────────────────────
    def get(self, tx: int, ty: int) -> int:
        if 0 <= tx < self.width and 0 <= ty < self.height:
            return self._tiles[ty][tx]
        return T_WALL

    def set(self, tx: int, ty: int, tile: int):
        if 0 <= tx < self.width and 0 <= ty < self.height:
            self._tiles[ty][tx] = tile

    def walkable(self, tx: int, ty: int) -> bool:
        return tile_walkable(self.get(tx, ty))

    def swimmable(self, tx: int, ty: int) -> bool:
        return tile_swimmable(self.get(tx, ty))

    def in_bounds(self, tx: int, ty: int) -> bool:
        return 0 <= tx < self.width and 0 <= ty < self.height

    # ── Tile fill helpers ────────────────────────────────────────────────────
    def fill(self, tile: int):
        for y in range(self.height):
            for x in range(self.width):
                self._tiles[y][x] = tile

    def fill_rect(self, x1, y1, x2, y2, tile: int):
        for y in range(max(0, y1), min(self.height, y2 + 1)):
            for x in range(max(0, x1), min(self.width, x2 + 1)):
                self._tiles[y][x] = tile

    # ── Pixel helpers ────────────────────────────────────────────────────────
    def px_walkable(self, px: float, py: float) -> bool:
        return self.walkable(int(px // TILE_SIZE), int(py // TILE_SIZE))

    # ── Draw ─────────────────────────────────────────────────────────────────
    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int,
             player_px: float, player_py: float, light_radius_tiles: int,
             asset_mgr=None):
        vw = surf.get_width()
        vh = surf.get_height()

        tx_start = max(0, cam_x // TILE_SIZE)
        ty_start = max(0, cam_y // TILE_SIZE)
        tx_end   = min(self.width,  (cam_x + vw) // TILE_SIZE + 2)
        ty_end   = min(self.height, (cam_y + vh) // TILE_SIZE + 2)

        pcx = player_px + ENTITY_SIZE // 2
        pcy = player_py + ENTITY_SIZE // 2

        tint_surf = None

        for ty in range(ty_start, ty_end):
            for tx in range(tx_start, tx_end):
                t  = self._tiles[ty][tx]
                sx = tx * TILE_SIZE - cam_x
                sy = ty * TILE_SIZE - cam_y

                brightness = 255

                if self.is_dungeon and self.ambient < 255:
                    dist = (((tx * TILE_SIZE + 16) - pcx) ** 2 +
                            ((ty * TILE_SIZE + 16) - pcy) ** 2) ** 0.5
                    max_dist = light_radius_tiles * TILE_SIZE
                    brightness = self.ambient
                    if dist < max_dist:
                        ratio      = 1.0 - dist / max_dist
                        brightness = min(255, int(self.ambient +
                                                  ratio * (255 - self.ambient)))
                    if brightness < 10:
                        pygame.draw.rect(surf, (0, 0, 0),
                                         (sx, sy, TILE_SIZE, TILE_SIZE))
                        continue

                sprite = asset_mgr.get_tile(t) if asset_mgr else None

                if sprite is not None:
                    surf.blit(sprite, (sx, sy))
                    if brightness < 255:
                        if tint_surf is None:
                            tint_surf = pygame.Surface((TILE_SIZE, TILE_SIZE),
                                                        pygame.SRCALPHA)
                        b = brightness
                        tint_surf.fill((b, b, b, 255))
                        surf.blit(tint_surf, (sx, sy),
                                  special_flags=pygame.BLEND_RGBA_MULT)
                else:
                    col    = tile_color(t)
                    factor = brightness / 255
                    col    = (int(col[0]*factor), int(col[1]*factor),
                              int(col[2]*factor))
                    pygame.draw.rect(surf, col, (sx, sy, TILE_SIZE, TILE_SIZE))
                    if brightness > 40:
                        pygame.draw.rect(surf, (0,0,0,20),
                                         (sx, sy, TILE_SIZE, TILE_SIZE), 1)

        # Ground items
        for gi in self.ground_items:
            gi.draw(surf, cam_x, cam_y)

    # ── Brightness helper (for entity visibility checks) ────────────────────
    def get_brightness_at(self, px: float, py: float,
                          player_px: float, player_py: float,
                          light_radius_tiles: int) -> int:
        """Return perceived brightness (0-255) at a pixel position."""
        if not self.is_dungeon or self.ambient >= 255:
            return 255
        pcx = player_px + ENTITY_SIZE // 2
        pcy = player_py + ENTITY_SIZE // 2
        dist = ((px - pcx) ** 2 + (py - pcy) ** 2) ** 0.5
        max_dist = light_radius_tiles * TILE_SIZE
        if dist >= max_dist:
            return self.ambient
        ratio = 1.0 - dist / max_dist
        return min(255, int(self.ambient + ratio * (255 - self.ambient)))
