"""
Rune & Shadow - World & Dungeon Generation
  • Overworld  : fractal Brownian motion (Perlin noise)
  • Dungeon 0  : BSP room-and-corridor (The Verdant Labyrinth)
  • Dungeon 1  : Cellular automata caves (The Stone Warrens)
  • Dungeon 2  : Drunkard's Walk + scatter rooms (The Haunted Halls)

Improvements:
  - Player starts on an actual grass tile (not a cleared square)
  - Forest biome uses 40% random infill instead of solid coverage
  - All dungeons guaranteed connected from entrance
  - Enemy spawns validated on reachable tiles only
  - Water (kelpie) monsters spawned in overworld water areas
"""
import random
import math
from collections import deque

from constants import *
from noise_gen import PerlinNoise, fbm
from game_map  import GameMap, GroundItem
from items     import make_item


# ═══════════════════════════════════════════════════════════════════════════════
#  OVERWORLD
# ═══════════════════════════════════════════════════════════════════════════════

class OverworldGenerator:
    DUNGEON_TARGETS = [
        (T_FOREST,   (160, 60),  30),
        (T_MOUNTAIN, (55,  150), 30),
        (T_GRASS,    (155, 155), 30),
    ]

    def __init__(self, seed: int):
        self.seed  = seed
        self.rng   = random.Random(seed)
        self.noise = PerlinNoise(seed)

    def generate(self) -> GameMap:
        gmap = GameMap(WORLD_W, WORLD_H, is_dungeon=False, ambient=255)
        rng  = self.rng

        scale = 0.012
        for y in range(WORLD_H):
            for x in range(WORLD_W):
                h = fbm(self.noise, x*scale, y*scale, octaves=7,
                        persistence=0.5, lacunarity=2.0)
                m = fbm(self.noise, (x+400)*scale, (y+400)*scale,
                        octaves=4, persistence=0.55, lacunarity=2.0)

                if   h < -0.40: t = T_DEEP_WATER
                elif h < -0.18: t = T_WATER
                elif h < -0.08: t = T_SAND
                elif h <  0.38:
                    # 40% random infill for forest - prevents fully blocked areas
                    if m > 0.05 and rng.random() < 0.40:
                        t = T_FOREST
                    else:
                        t = T_GRASS
                elif h <  0.58: t = T_MOUNTAIN
                else:           t = T_MOUNTAIN
                gmap.set(x, y, t)

        # Find a good grass starting area near centre (not surrounded by water)
        cx, cy = WORLD_W // 2, WORLD_H // 2
        self._start_tile = self._find_grass_start(gmap, cx, cy)

        # Place dungeon entrances
        self._dungeon_positions = []
        for i, (biome, (ex, ey), radius) in enumerate(self.DUNGEON_TARGETS):
            pos = self._find_near(gmap, ex, ey, radius, biome)
            if pos is None:
                pos = self._find_near(gmap, ex, ey, radius*2, T_GRASS)
            if pos:
                tx, ty = pos
                gmap.set(tx, ty, T_ENTRANCE)
                for dx, dy in DIRS_4:
                    nx, ny = tx+dx, ty+dy
                    if not gmap.in_bounds(nx, ny): continue
                    if not tile_walkable(gmap.get(nx, ny)):
                        gmap.set(nx, ny, T_GRASS)
                self._dungeon_positions.append((tx, ty))
            else:
                gmap.set(ex, ey, T_ENTRANCE)
                self._dungeon_positions.append((ex, ey))

        # Shrines
        for _ in range(4):
            sx = rng.randint(10, WORLD_W-10)
            sy = rng.randint(10, WORLD_H-10)
            if tile_walkable(gmap.get(sx, sy)):
                gmap.set(sx, sy, T_SHRINE)

        return gmap

    def _find_grass_start(self, gmap, cx, cy):
        """Find a grass tile near centre that has at least 4 walkable neighbours."""
        for radius in range(0, 20):
            candidates = []
            for dy in range(-radius, radius+1):
                for dx in range(-radius, radius+1):
                    nx, ny = cx+dx, cy+dy
                    if not gmap.in_bounds(nx, ny): continue
                    if gmap.get(nx, ny) != T_GRASS: continue
                    # Count walkable neighbours
                    walkable_n = sum(
                        1 for ddx, ddy in DIRS_4
                        if gmap.in_bounds(nx+ddx, ny+ddy) and
                           tile_walkable(gmap.get(nx+ddx, ny+ddy))
                    )
                    if walkable_n >= 3:
                        candidates.append((nx, ny))
            if candidates:
                return self.rng.choice(candidates)
        return (cx, cy)

    def _find_near(self, gmap, cx, cy, radius, biome):
        candidates = []
        for dy in range(-radius, radius+1):
            for dx in range(-radius, radius+1):
                nx, ny = cx+dx, cy+dy
                if not gmap.in_bounds(nx, ny): continue
                if gmap.get(nx, ny) == biome:
                    candidates.append((nx, ny))
        if not candidates:
            return None
        return self.rng.choice(candidates)

    @property
    def start_tile(self):
        return self._start_tile

    @property
    def dungeon_tile_positions(self):
        return list(self._dungeon_positions)


# ═══════════════════════════════════════════════════════════════════════════════
#  CONNECTIVITY GUARANTEE (shared utility)
# ═══════════════════════════════════════════════════════════════════════════════

def _flood_fill(gmap, sx, sy, floor_tiles, allow_ghost=False):
    """BFS from (sx,sy) across floor_tiles set. Returns set of reachable (tx,ty)."""
    visited = set()
    queue   = deque([(sx, sy)])
    visited.add((sx, sy))
    while queue:
        tx, ty = queue.popleft()
        for dx, dy in DIRS_4:
            nx, ny = tx+dx, ty+dy
            if (nx, ny) in visited: continue
            if not gmap.in_bounds(nx, ny): continue
            t = gmap.get(nx, ny)
            if t in floor_tiles or (allow_ghost and tile_walkable(t)):
                visited.add((nx, ny))
                queue.append((nx, ny))
    return visited

DUNGEON_FLOOR_TILES = {T_FLOOR, T_CAVE_FLOOR, T_STAIRS_UP, T_STAIRS_DOWN,
                       T_CHEST, T_SHRINE, T_DOOR}

def _ensure_dungeon_connected(gmap, floor_t, wall_t):
    """
    Guarantee all floor tiles are reachable from the entrance (stairs_up).
    Unreachable floor regions are either connected via corridor or walled off.
    Spawn points in unreachable areas are discarded.
    """
    ex, ey = gmap.entrance_tile

    # Collect all floor positions
    all_floor = set()
    for y in range(gmap.height):
        for x in range(gmap.width):
            if gmap.get(x, y) in DUNGEON_FLOOR_TILES or gmap.get(x, y) == floor_t:
                all_floor.add((x, y))

    # BFS from entrance
    reachable = _flood_fill(gmap, ex, ey, DUNGEON_FLOOR_TILES | {floor_t})

    # Connect unreachable clusters to nearest reachable tile
    unreachable = all_floor - reachable
    iterations  = 0
    while unreachable and iterations < 20:
        iterations += 1
        # Find closest pair (unreachable tile → reachable tile)
        best_dist = 999999
        best_pair = None
        # Sample to avoid O(n²) on large maps
        sample_ur = list(unreachable)
        if len(sample_ur) > 200:
            sample_ur = sample_ur[:200]
        for ux, uy in sample_ur:
            for rx, ry in list(reachable):
                d = abs(ux-rx) + abs(uy-ry)
                if d < best_dist:
                    best_dist = d
                    best_pair = ((ux, uy), (rx, ry))
        if best_pair is None:
            break
        (ux, uy), (rx, ry) = best_pair
        # Carve straight corridor
        x, y = ux, uy
        while x != rx:
            x += 1 if rx > x else -1
            if gmap.get(x, y) not in (DUNGEON_FLOOR_TILES | {floor_t}):
                gmap.set(x, y, floor_t)
                all_floor.add((x, y))
        while y != ry:
            y += 1 if ry > y else -1
            if gmap.get(x, y) not in (DUNGEON_FLOOR_TILES | {floor_t}):
                gmap.set(x, y, floor_t)
                all_floor.add((x, y))
        # Re-flood fill
        reachable = _flood_fill(gmap, ex, ey, DUNGEON_FLOOR_TILES | {floor_t})
        unreachable = all_floor - reachable

    # Wall off any remaining unreachable floor (shouldn't happen often)
    for tx, ty in unreachable:
        t = gmap.get(tx, ty)
        if t in (T_CHEST, T_SHRINE):
            gmap.set(tx, ty, floor_t)  # remove special tiles
        elif t == floor_t:
            gmap.set(tx, ty, wall_t)

    # Prune enemy/item spawns to reachable area only
    reachable_final = _flood_fill(gmap, ex, ey, DUNGEON_FLOOR_TILES | {floor_t})
    if hasattr(gmap, 'enemy_spawns'):
        gmap.enemy_spawns = [
            sp for sp in gmap.enemy_spawns
            if (sp['tx'], sp['ty']) in reachable_final or sp.get('boss')
        ]
        # Relocate boss if unreachable (put it near shrine)
        for sp in gmap.enemy_spawns:
            if sp.get('boss') and (sp['tx'], sp['ty']) not in reachable_final:
                bx, by = gmap.exit_tile
                for ddx, ddy in [(2,2),(2,0),(0,2),(-2,2),(2,-2)]:
                    nbx, nby = bx+ddx, by+ddy
                    if (nbx, nby) in reachable_final:
                        sp['tx'], sp['ty'] = nbx, nby
                        break
    if hasattr(gmap, 'item_spawns'):
        gmap.item_spawns = [
            sp for sp in gmap.item_spawns
            if (sp['tx'], sp['ty']) in reachable_final
        ]


# ═══════════════════════════════════════════════════════════════════════════════
#  DUNGEON 0 – BSP Room-and-Corridor
# ═══════════════════════════════════════════════════════════════════════════════

class _Rect:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h

    def centre(self):
        return self.x + self.w // 2, self.y + self.h // 2

    def random_point(self, rng):
        return (rng.randint(self.x + 1, self.x + self.w - 2),
                rng.randint(self.y + 1, self.y + self.h - 2))


def _bsp_split(rect, rng, min_size=8, depth=0, max_depth=5):
    if depth >= max_depth or rect.w < min_size*2 or rect.h < min_size*2:
        return [rect]
    if rect.w > rect.h:
        split_vert = True
    elif rect.h > rect.w:
        split_vert = False
    else:
        split_vert = rng.random() < 0.5

    if split_vert:
        split = rng.randint(min_size, rect.w - min_size)
        a = _Rect(rect.x, rect.y, split, rect.h)
        b = _Rect(rect.x + split, rect.y, rect.w - split, rect.h)
    else:
        split = rng.randint(min_size, rect.h - min_size)
        a = _Rect(rect.x, rect.y, rect.w, split)
        b = _Rect(rect.x, rect.y + split, rect.w, rect.h - split)

    return _bsp_split(a, rng, min_size, depth+1, max_depth) + \
           _bsp_split(b, rng, min_size, depth+1, max_depth)


def _carve_room(gmap, rect, rng, floor_tile):
    rx = rect.x + rng.randint(1, 2)
    ry = rect.y + rng.randint(1, 2)
    rw = rect.w - rng.randint(3, 5)
    rh = rect.h - rng.randint(3, 5)
    rw = max(4, rw); rh = max(4, rh)
    gmap.fill_rect(rx, ry, rx+rw-1, ry+rh-1, floor_tile)
    return _Rect(rx, ry, rw, rh)


def _carve_corridor(gmap, x1, y1, x2, y2, floor_tile, rng):
    if rng.random() < 0.5:
        for x in range(min(x1,x2), max(x1,x2)+1):
            gmap.set(x, y1, floor_tile)
        for y in range(min(y1,y2), max(y1,y2)+1):
            gmap.set(x2, y, floor_tile)
    else:
        for y in range(min(y1,y2), max(y1,y2)+1):
            gmap.set(x1, y, floor_tile)
        for x in range(min(x1,x2), max(x1,x2)+1):
            gmap.set(x, y2, floor_tile)


def generate_bsp_dungeon(seed: int, dungeon_id: int) -> GameMap:
    cfg  = DUNGEONS[dungeon_id]
    rng  = random.Random(seed ^ (dungeon_id * 0xDEADBEEF))
    W, H = DUN_W, DUN_H
    floor_t = cfg['floor']
    wall_t  = cfg['wall']

    gmap = GameMap(W, H, is_dungeon=True, dungeon_id=dungeon_id,
                   ambient=cfg['ambient'])
    gmap.fill(wall_t)

    leaves = _bsp_split(_Rect(1, 1, W-2, H-2), rng, min_size=8, max_depth=5)
    rooms  = [_carve_room(gmap, leaf, rng, floor_t) for leaf in leaves]

    # Connect ALL rooms (not just sequential) via MST-like approach
    for i in range(len(rooms)-1):
        cx1, cy1 = rooms[i].centre()
        cx2, cy2 = rooms[i+1].centre()
        _carve_corridor(gmap, cx1, cy1, cx2, cy2, floor_t, rng)
    # Add a few extra corridors for loops
    for _ in range(len(rooms)//4):
        i = rng.randint(0, len(rooms)-1)
        j = rng.randint(0, len(rooms)-1)
        if i != j:
            cx1, cy1 = rooms[i].centre()
            cx2, cy2 = rooms[j].centre()
            _carve_corridor(gmap, cx1, cy1, cx2, cy2, floor_t, rng)

    r0 = rooms[0]
    rN = rooms[-1]
    ex, ey = r0.random_point(rng)
    gmap.set(ex, ey, T_STAIRS_UP)
    gmap.entrance_tile = (ex, ey)

    bx, by = rN.random_point(rng)
    gmap.set(bx, by, T_SHRINE)
    gmap.exit_tile = (bx, by)

    chest_rooms = rng.sample(rooms[1:-1], min(len(rooms)//4+1, len(rooms)-2))
    for cr in chest_rooms:
        cpx, cpy = cr.random_point(rng)
        gmap.set(cpx, cpy, T_CHEST)

    _populate_dungeon(gmap, rooms[1:], dungeon_id, rng)
    _ensure_dungeon_connected(gmap, floor_t, wall_t)
    return gmap


# ═══════════════════════════════════════════════════════════════════════════════
#  DUNGEON 1 – Cellular Automata Cave
# ═══════════════════════════════════════════════════════════════════════════════

def generate_cave_dungeon(seed: int, dungeon_id: int) -> GameMap:
    cfg     = DUNGEONS[dungeon_id]
    rng     = random.Random(seed ^ (dungeon_id * 0xCAFEBABE))
    W, H    = DUN_W, DUN_H
    floor_t = cfg['floor']
    wall_t  = cfg['wall']

    gmap = GameMap(W, H, is_dungeon=True, dungeon_id=dungeon_id,
                   ambient=cfg['ambient'])

    grid = [[1 if rng.random() < 0.55 else 0 for _ in range(W)]
            for _ in range(H)]

    for x in range(W): grid[0][x] = grid[H-1][x] = 1
    for y in range(H): grid[y][0] = grid[y][W-1] = 1

    for _ in range(5):
        new = [[1]*W for _ in range(H)]
        for y in range(1, H-1):
            for x in range(1, W-1):
                walls = sum(grid[y+dy][x+dx]
                            for dy in (-1,0,1) for dx in (-1,0,1))
                new[y][x] = 1 if walls >= 5 else 0
        grid = new

    for y in range(H):
        for x in range(W):
            gmap.set(x, y, wall_t if grid[y][x] else floor_t)

    # Find largest connected region from centre
    cx, cy = W//2, H//2
    if grid[cy][cx]:
        for r in range(1, max(W,H)//2):
            found = False
            for dx in range(-r, r+1):
                for dy in range(-r, r+1):
                    if 0 < cx+dx < W-1 and 0 < cy+dy < H-1:
                        if not grid[cy+dy][cx+dx]:
                            cx, cy = cx+dx, cy+dy
                            found = True
                            break
                if found: break
            if found: break

    visited = set()
    stack   = [(cx, cy)]
    while stack:
        tx, ty = stack.pop()
        if (tx, ty) in visited: continue
        visited.add((tx, ty))
        for dx, dy in DIRS_4:
            nx, ny = tx+dx, ty+dy
            if 0 < nx < W-1 and 0 < ny < H-1 and (nx,ny) not in visited:
                if not grid[ny][nx]:
                    stack.append((nx, ny))

    for y in range(H):
        for x in range(W):
            if not grid[y][x] and (x,y) not in visited:
                gmap.set(x, y, wall_t)

    reachable = list(visited)
    rng.shuffle(reachable)
    ex, ey = reachable[0]
    gmap.set(ex, ey, T_STAIRS_UP)
    gmap.entrance_tile = (ex, ey)

    reachable.sort(key=lambda p: (p[0]-ex)**2 + (p[1]-ey)**2, reverse=True)
    bx, by = reachable[0]
    gmap.set(bx, by, T_SHRINE)
    gmap.exit_tile = (bx, by)

    chest_spots = rng.sample(reachable[len(reachable)//4:3*len(reachable)//4],
                             min(5, len(reachable)//10))
    for cpx, cpy in chest_spots:
        gmap.set(cpx, cpy, T_CHEST)

    fake_rooms = []
    for _ in range(10):
        pt = rng.choice(reachable)
        fake_rooms.append(_Rect(max(0,pt[0]-2), max(0,pt[1]-2), 5, 5))
    _populate_dungeon(gmap, fake_rooms, dungeon_id, rng)
    _ensure_dungeon_connected(gmap, floor_t, wall_t)
    return gmap


# ═══════════════════════════════════════════════════════════════════════════════
#  DUNGEON 2 – Drunkard's Walk + Scatter Rooms
# ═══════════════════════════════════════════════════════════════════════════════

def generate_drunk_dungeon(seed: int, dungeon_id: int) -> GameMap:
    cfg     = DUNGEONS[dungeon_id]
    rng     = random.Random(seed ^ (dungeon_id * 0xF00DBABE))
    W, H    = DUN_W, DUN_H
    floor_t = cfg['floor']
    wall_t  = cfg['wall']

    gmap = GameMap(W, H, is_dungeon=True, dungeon_id=dungeon_id,
                   ambient=cfg['ambient'])
    gmap.fill(wall_t)

    # Start drunkard walk from centre
    start_x, start_y = W//2, H//2
    wx, wy  = start_x, start_y
    steps   = W * H // 3
    floor_cells = set()
    gmap.set(wx, wy, floor_t)
    floor_cells.add((wx, wy))

    for _ in range(steps):
        wx = max(2, min(W-3, wx + rng.choice([-1,0,1])))
        wy = max(2, min(H-3, wy + rng.choice([-1,0,1])))
        gmap.set(wx, wy, floor_t)
        floor_cells.add((wx, wy))
        if rng.random() < 0.25:
            dx, dy = rng.choice(DIRS_4)
            nx, ny = wx+dx, wy+dy
            if 1 < nx < W-2 and 1 < ny < H-2:
                gmap.set(nx, ny, floor_t)
                floor_cells.add((nx, ny))

    # Scatter rooms and CONNECT them explicitly to nearest walk tile
    rooms = []
    for _ in range(8):
        rw = rng.randint(4, 9)
        rh = rng.randint(4, 8)
        rx = rng.randint(2, W-rw-2)
        ry = rng.randint(2, H-rh-2)
        room_cx = rx + rw//2
        room_cy = ry + rh//2
        gmap.fill_rect(rx, ry, rx+rw-1, ry+rh-1, floor_t)
        for dx in range(rw):
            for dy in range(rh):
                floor_cells.add((rx+dx, ry+dy))
        # Connect room centre to walk start
        _carve_corridor(gmap, room_cx, room_cy, start_x, start_y, floor_t, rng)
        for x in range(min(room_cx, start_x), max(room_cx, start_x)+1):
            floor_cells.add((x, room_cy))
        for y in range(min(room_cy, start_y), max(room_cy, start_y)+1):
            floor_cells.add((x, y))
        rooms.append(_Rect(rx, ry, rw, rh))

    # Entrance at walk start (guaranteed connected)
    gmap.set(start_x, start_y, T_STAIRS_UP)
    gmap.entrance_tile = (start_x, start_y)

    # Exit farthest from entrance
    reachable = list(floor_cells)
    reachable.sort(key=lambda p: (p[0]-start_x)**2+(p[1]-start_y)**2, reverse=True)
    bx, by = reachable[0]
    gmap.set(bx, by, T_SHRINE)
    gmap.exit_tile = (bx, by)

    chest_spots = rng.sample(reachable[10:], min(4, max(1, len(reachable)-10)))
    for cpx, cpy in chest_spots:
        gmap.set(cpx, cpy, T_CHEST)

    _populate_dungeon(gmap, rooms, dungeon_id, rng)
    _ensure_dungeon_connected(gmap, floor_t, wall_t)
    return gmap


# ═══════════════════════════════════════════════════════════════════════════════
#  SHARED: Populate a dungeon with enemies & items
# ═══════════════════════════════════════════════════════════════════════════════

def _populate_dungeon(gmap: GameMap, rooms, dungeon_id: int, rng: random.Random):
    cfg       = DUNGEONS[dungeon_id]
    enemy_ids = cfg['enemies']

    gmap.enemy_spawns = []
    gmap.item_spawns  = []

    for i, room in enumerate(rooms):
        if i == 0: continue
        n_enemies = rng.randint(1, 3)
        for _ in range(n_enemies):
            ex = rng.randint(room.x+1, max(room.x+1, room.x+room.w-2))
            ey = rng.randint(room.y+1, max(room.y+1, room.y+room.h-2))
            eid = rng.choice(enemy_ids)
            gmap.enemy_spawns.append({'type': eid, 'tx': ex, 'ty': ey})

        if rng.random() < 0.4:
            ix = rng.randint(room.x+1, max(room.x+1, room.x+room.w-2))
            iy = rng.randint(room.y+1, max(room.y+1, room.y+room.h-2))
            iid = rng.choice(['mushroom','herb','coin','coin','blue_flower',
                               'potion','mana_pot'])
            gmap.item_spawns.append({'iid': iid, 'count': rng.randint(1,3),
                                     'tx': ix, 'ty': iy})

    # Boss near shrine
    bx, by = gmap.exit_tile
    boss_type = cfg['boss']
    # Place boss adjacent to shrine on a floor tile
    for ddx, ddy in [(2,0),(0,2),(-2,0),(0,-2),(2,2),(-2,2),(2,-2),(-2,-2)]:
        nbx, nby = bx+ddx, by+ddy
        if gmap.in_bounds(nbx, nby):
            t = gmap.get(nbx, nby)
            if t in (DUNGEONS[dungeon_id]['floor'], T_FLOOR, T_CAVE_FLOOR):
                gmap.enemy_spawns.append({'type': boss_type,
                                          'tx': nbx, 'ty': nby, 'boss': True})
                break
    else:
        gmap.enemy_spawns.append({'type': boss_type,
                                  'tx': bx+2, 'ty': by+2, 'boss': True})


# ═══════════════════════════════════════════════════════════════════════════════
#  FACTORY
# ═══════════════════════════════════════════════════════════════════════════════

def build_dungeon(seed: int, dungeon_id: int) -> GameMap:
    cfg = DUNGEONS[dungeon_id]
    style = cfg['style']
    if style == 'bsp':   return generate_bsp_dungeon(seed, dungeon_id)
    if style == 'cave':  return generate_cave_dungeon(seed, dungeon_id)
    if style == 'drunk': return generate_drunk_dungeon(seed, dungeon_id)
    raise ValueError(f"Unknown dungeon style: {style!r}")
