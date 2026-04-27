"""
Rune & Shadow - Generation v3
  Town, four biomes (Forest/Tundra/Desert/Swamp), multi-level dungeons.
  All dungeons guaranteed connected. Forest uses 40% infill.
  Player starts in the centre of town.
"""
import random
import math
from collections import deque

from constants import *
from noise_gen import PerlinNoise, fbm
from game_map  import GameMap, GroundItem
from items     import make_item


# ═══════════════════════════════════════════════════════════════════════════════
#  TOWN GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

class TownGenerator:
    """Procedurally generates a walled town with streets, buildings, and gates."""

    ROAD_COLS = [15, 30, 50, 65]   # x positions of vertical roads
    ROAD_ROWS = [15, 30, 50, 65]   # y positions of horizontal roads
    ROAD_W    = 3                   # tiles wide

    def __init__(self, seed: int):
        self.seed = seed
        self.rng  = random.Random(seed ^ 0xABCD1234)

    def generate(self) -> GameMap:
        W, H = TOWN_W, TOWN_H
        rng  = self.rng
        gmap = GameMap(W, H, is_dungeon=False, map_key=MAP_TOWN, ambient=255)

        # Background – grassy
        gmap.fill(T_GRASS)

        # ── Perimeter wall ────────────────────────────────────────────────────
        for x in range(W):
            gmap.set(x, 0,   T_BUILDING_WALL)
            gmap.set(x, H-1, T_BUILDING_WALL)
        for y in range(H):
            gmap.set(0,   y, T_BUILDING_WALL)
            gmap.set(W-1, y, T_BUILDING_WALL)

        # ── Gates (gaps in perimeter wall) ────────────────────────────────────
        cx, cy = W//2, H//2
        # N gate
        gmap.set(cx-1, 0, T_PATH); gmap.set(cx, 0, T_GATE_N); gmap.set(cx+1, 0, T_PATH)
        # S gate
        gmap.set(cx-1,H-1,T_PATH); gmap.set(cx,H-1,T_GATE_S); gmap.set(cx+1,H-1,T_PATH)
        # E gate
        gmap.set(W-1,cy-1,T_PATH); gmap.set(W-1,cy,T_GATE_E); gmap.set(W-1,cy+1,T_PATH)
        # W gate
        gmap.set(0,cy-1,T_PATH);   gmap.set(0,cy,T_GATE_W);   gmap.set(0,cy+1,T_PATH)

        # ── Main roads (cross through town centre) ────────────────────────────
        for y in range(1, H-1):
            for ox in (-1, 0, 1):
                gmap.set(cx + ox, y, T_PATH)
        for x in range(1, W-1):
            for oy in (-1, 0, 1):
                gmap.set(x, cy + oy, T_PATH)

        # ── Secondary roads ───────────────────────────────────────────────────
        for ry in [cy//2, cy + cy//2]:
            for x in range(1, W-1):
                if gmap.get(x, ry) == T_GRASS:
                    gmap.set(x, ry, T_PATH)
        for rx in [cx//2, cx + cx//2]:
            for y in range(1, H-1):
                if gmap.get(rx, y) == T_GRASS:
                    gmap.set(rx, y, T_PATH)

        # ── Central plaza ─────────────────────────────────────────────────────
        plaza_r = 5
        for dy in range(-plaza_r, plaza_r+1):
            for dx in range(-plaza_r, plaza_r+1):
                px, py = cx+dx, cy+dy
                if gmap.in_bounds(px, py):
                    gmap.set(px, py, T_PATH)
        gmap.set(cx, cy, T_SHRINE)     # shrine in the very centre
        gmap.set(cx+3, cy, T_WELL)     # well nearby
        gmap.set(cx-3, cy, T_WELL)

        # ── Buildings in each quadrant ────────────────────────────────────────
        quadrants = [
            (2,   2,   cx-5, cy-5),   # NW
            (cx+4, 2,   W-2,  cy-5),   # NE
            (2,   cy+4, cx-5, H-2),    # SW
            (cx+4, cy+4, W-2,  H-2),   # SE
        ]
        for qx1, qy1, qx2, qy2 in quadrants:
            self._fill_quadrant_with_buildings(gmap, qx1, qy1, qx2, qy2, rng)

        # ── Some trees / decorations outside buildings ─────────────────────────
        for _ in range(30):
            tx = rng.randint(2, W-3)
            ty = rng.randint(2, H-3)
            if gmap.get(tx, ty) == T_GRASS:
                if rng.random() < 0.6:
                    gmap.set(tx, ty, T_FOREST)

        # Record gate positions for game logic
        gmap.gate_n = (cx, 0)
        gmap.gate_s = (cx, H-1)
        gmap.gate_e = (W-1, cy)
        gmap.gate_w = (0, cy)

        # Player start – centre of plaza
        self._start_tile = (cx, cy + 2)   # just south of shrine
        return gmap

    def _fill_quadrant_with_buildings(self, gmap, x1, y1, x2, y2, rng):
        """Try to fit several non-overlapping buildings in a rectangular area."""
        attempts = 0
        placed   = []
        while attempts < 30:
            attempts += 1
            rw = rng.randint(5, min(12, x2-x1-1))
            rh = rng.randint(4, min(9,  y2-y1-1))
            rx = rng.randint(x1, max(x1, x2-rw))
            ry = rng.randint(y1, max(y1, y2-rh))
            # Check overlap with existing buildings (+1 gap)
            overlap = any(
                rx-1 < bx+bw and rx+rw+1 > bx and ry-1 < by+bh and ry+rh+1 > by
                for bx, by, bw, bh in placed
            )
            if not overlap and x2 > rx+rw and y2 > ry+rh:
                self._place_building(gmap, rx, ry, rw, rh, rng)
                placed.append((rx, ry, rw, rh))
                if len(placed) >= 4:
                    break

    def _place_building(self, gmap, rx, ry, rw, rh, rng):
        # Outer walls
        for y in range(ry, ry+rh):
            for x in range(rx, rx+rw):
                gmap.set(x, y, T_BUILDING_WALL)
        # Interior floor
        for y in range(ry+1, ry+rh-1):
            for x in range(rx+1, rx+rw-1):
                gmap.set(x, y, T_BUILDING_FLOOR)
        # Door in a random wall
        wall = rng.choice(['N','S','E','W'])
        if wall == 'N' and rw > 2:
            gmap.set(rx + rng.randint(1, rw-2), ry, T_DOOR)
        elif wall == 'S' and rw > 2:
            gmap.set(rx + rng.randint(1, rw-2), ry+rh-1, T_DOOR)
        elif wall == 'E' and rh > 2:
            gmap.set(rx+rw-1, ry + rng.randint(1, rh-2), T_DOOR)
        elif wall == 'W' and rh > 2:
            gmap.set(rx, ry + rng.randint(1, rh-2), T_DOOR)
        else:
            gmap.set(rx+1, ry, T_DOOR)   # fallback

        # Maybe a chest inside
        if rng.random() < 0.3 and rw > 3 and rh > 3:
            gmap.set(rx + rng.randint(1, rw-2),
                     ry + rng.randint(1, rh-2), T_CHEST)

    @property
    def start_tile(self):
        return self._start_tile


# ═══════════════════════════════════════════════════════════════════════════════
#  BIOME GENERATORS
# ═══════════════════════════════════════════════════════════════════════════════

class BiomeGenerator:
    """Base class for biome (overworld) generation."""
    SCALE       = 0.014
    DUNGEON_IDS : list = []
    MAP_KEY     : str  = MAP_EAST

    def __init__(self, seed: int):
        self.seed  = seed
        self.rng   = random.Random(seed ^ hash(self.MAP_KEY))
        self.noise = PerlinNoise(seed ^ hash(self.MAP_KEY))

    def generate(self) -> GameMap:
        W, H = WORLD_W, WORLD_H
        gmap = GameMap(W, H, is_dungeon=False, map_key=self.MAP_KEY, ambient=255)
        rng  = self.rng
        noise= self.noise

        for y in range(H):
            for x in range(W):
                h = fbm(noise, x*self.SCALE, y*self.SCALE,
                        octaves=7, persistence=0.5, lacunarity=2.0)
                m = fbm(noise, (x+400)*self.SCALE, (y+400)*self.SCALE,
                        octaves=4, persistence=0.55, lacunarity=2.0)
                gmap.set(x, y, self._tile(h, m, rng))

        # Gate back to town on the appropriate edge
        self._place_return_gate(gmap)

        # Dungeon entrances
        self._dungeon_positions = []
        for dun_id in self.DUNGEON_IDS:
            cfg = DUNGEONS[dun_id]
            pos = self._find_walkable_near(gmap, W//2, H//2, 60, rng)
            if pos:
                tx, ty = pos
                gmap.set(tx, ty, T_ENTRANCE)
                # Clear adjacent tiles so entrance is reachable
                for dx, dy in DIRS_4:
                    nx, ny = tx+dx, ty+dy
                    if gmap.in_bounds(nx, ny) and not tile_walkable(gmap.get(nx, ny)):
                        gmap.set(nx, ny, self._base_floor())
                self._dungeon_positions.append((tx, ty, dun_id))

        # Shrines
        for _ in range(2):
            pos = self._find_walkable_near(gmap, W//2, H//2, 80, rng)
            if pos:
                gmap.set(pos[0], pos[1], T_SHRINE)

        return gmap

    def _tile(self, h, m, rng) -> int:
        raise NotImplementedError

    def _base_floor(self) -> int:
        return T_GRASS

    def _place_return_gate(self, gmap):
        raise NotImplementedError

    def _find_walkable_near(self, gmap, cx, cy, radius, rng):
        candidates = []
        for dy in range(-radius, radius+1):
            for dx in range(-radius, radius+1):
                nx, ny = cx+dx, cy+dy
                if gmap.in_bounds(nx, ny) and tile_walkable(gmap.get(nx, ny)):
                    candidates.append((nx, ny))
        return rng.choice(candidates) if candidates else None

    @property
    def dungeon_positions(self):
        return list(self._dungeon_positions)


class ForestBiome(BiomeGenerator):
    MAP_KEY     = MAP_EAST
    DUNGEON_IDS = [0, 1, 2]

    def _tile(self, h, m, rng):
        if   h < -0.40: return T_DEEP_WATER
        elif h < -0.18: return T_WATER
        elif h < -0.08: return T_SAND
        elif h <  0.38:
            if m > 0.05 and rng.random() < 0.40: return T_FOREST
            return T_GRASS
        elif h <  0.58: return T_MOUNTAIN
        return T_MOUNTAIN

    def _base_floor(self): return T_GRASS

    def _place_return_gate(self, gmap):
        W, H = gmap.width, gmap.height
        cy = H // 2
        # West edge gate back to town
        for y in range(cy-1, cy+2):
            gmap.set(0, y, T_GATE_W)
        gmap.gate_w = (0, cy)


class TundraBiome(BiomeGenerator):
    MAP_KEY     = MAP_NORTH
    DUNGEON_IDS = [3, 4]

    def _tile(self, h, m, rng):
        if   h < -0.30: return T_ICE          # frozen lakes (swimmable)
        elif h < -0.08: return T_SNOW
        elif h <  0.35:
            if m > 0.10 and rng.random() < 0.30: return T_MOUNTAIN
            return T_SNOW
        elif h <  0.55: return T_MOUNTAIN
        return T_MOUNTAIN

    def _base_floor(self): return T_SNOW

    def _place_return_gate(self, gmap):
        H = gmap.height
        cx = gmap.width // 2
        # South edge gate back to town
        for x in range(cx-1, cx+2):
            gmap.set(x, H-1, T_GATE_S)
        gmap.gate_s = (cx, H-1)


class DesertBiome(BiomeGenerator):
    MAP_KEY     = MAP_SOUTH
    DUNGEON_IDS = [5, 6]

    def _tile(self, h, m, rng):
        if   h < -0.35: return T_WATER        # oasis
        elif h < -0.20: return T_SAND
        elif h <  0.40:
            if m > 0.20 and rng.random() < 0.15: return T_CACTUS
            return T_SAND
        elif h <  0.55: return T_MOUNTAIN      # rocky dunes/outcrops
        return T_MOUNTAIN

    def _base_floor(self): return T_SAND

    def _place_return_gate(self, gmap):
        cx = gmap.width // 2
        # North edge gate back to town
        for x in range(cx-1, cx+2):
            gmap.set(x, 0, T_GATE_N)
        gmap.gate_n = (cx, 0)


class SwampBiome(BiomeGenerator):
    MAP_KEY     = MAP_WEST
    DUNGEON_IDS = [7, 8]

    def _tile(self, h, m, rng):
        if   h < -0.50: return T_DEEP_WATER
        elif h < -0.20: return T_WATER
        elif h < -0.05: return T_SWAMP         # slow-walkable murk
        elif h <  0.35:
            if m > 0.00 and rng.random() < 0.55: return T_FOREST
            return T_GRASS
        elif h <  0.50: return T_MOUNTAIN
        return T_MOUNTAIN

    def _base_floor(self): return T_GRASS

    def _place_return_gate(self, gmap):
        W = gmap.width
        cy = gmap.height // 2
        # East edge gate back to town
        for y in range(cy-1, cy+2):
            gmap.set(W-1, y, T_GATE_E)
        gmap.gate_e = (W-1, cy)


_BIOME_CLASSES = {
    MAP_EAST:  ForestBiome,
    MAP_NORTH: TundraBiome,
    MAP_SOUTH: DesertBiome,
    MAP_WEST:  SwampBiome,
}

def build_biome(seed: int, map_key: str) -> GameMap:
    cls = _BIOME_CLASSES[map_key]
    return cls(seed)


# ═══════════════════════════════════════════════════════════════════════════════
#  CONNECTIVITY (shared)
# ═══════════════════════════════════════════════════════════════════════════════

DUNGEON_FLOOR_TILES = {T_FLOOR, T_CAVE_FLOOR, T_STAIRS_UP, T_STAIRS_DOWN,
                       T_CHEST, T_SHRINE, T_DOOR}

def _flood_fill(gmap, sx, sy, passable_tiles):
    visited = set()
    queue   = deque([(sx, sy)])
    visited.add((sx, sy))
    while queue:
        tx, ty = queue.popleft()
        for dx, dy in DIRS_4:
            nx, ny = tx+dx, ty+dy
            if (nx, ny) in visited: continue
            if not gmap.in_bounds(nx, ny): continue
            if gmap.get(nx, ny) in passable_tiles:
                visited.add((nx, ny))
                queue.append((nx, ny))
    return visited


def _ensure_connected(gmap, floor_t, wall_t):
    ex, ey = gmap.entrance_tile
    all_floor = {(x, y)
                 for y in range(gmap.height) for x in range(gmap.width)
                 if gmap.get(x, y) in DUNGEON_FLOOR_TILES or gmap.get(x, y) == floor_t}

    passable = DUNGEON_FLOOR_TILES | {floor_t}
    reachable = _flood_fill(gmap, ex, ey, passable)
    unreachable = all_floor - reachable

    for _ in range(20):
        if not unreachable: break
        best_dist, best_pair = 999999, None
        sample = list(unreachable)[:200]
        for ux, uy in sample:
            for rx, ry in list(reachable):
                d = abs(ux-rx)+abs(uy-ry)
                if d < best_dist:
                    best_dist = d; best_pair = ((ux,uy),(rx,ry))
        if not best_pair: break
        (ux,uy),(rx,ry) = best_pair
        x,y = ux,uy
        while x != rx:
            x += 1 if rx>x else -1
            if gmap.get(x,y) not in passable: gmap.set(x,y,floor_t)
            all_floor.add((x,y))
        while y != ry:
            y += 1 if ry>y else -1
            if gmap.get(x,y) not in passable: gmap.set(x,y,floor_t)
            all_floor.add((x,y))
        reachable = _flood_fill(gmap, ex, ey, passable)
        unreachable = all_floor - reachable

    # Wall off anything still unreachable
    for tx, ty in unreachable:
        gmap.set(tx, ty, wall_t)

    # Prune spawns to reachable
    final = _flood_fill(gmap, ex, ey, passable)
    if hasattr(gmap, 'enemy_spawns'):
        gmap.enemy_spawns = [
            sp for sp in gmap.enemy_spawns
            if (sp['tx'], sp['ty']) in final or sp.get('boss')
        ]
        for sp in gmap.enemy_spawns:
            if sp.get('boss') and (sp['tx'], sp['ty']) not in final:
                for dx, dy in [(2,2),(0,2),(2,0),(-2,2),(2,-2),(-2,-2)]:
                    nbx = sp['tx']+dx; nby = sp['ty']+dy
                    if (nbx,nby) in final:
                        sp['tx'],sp['ty'] = nbx,nby; break
    if hasattr(gmap, 'item_spawns'):
        gmap.item_spawns = [
            sp for sp in gmap.item_spawns
            if (sp['tx'], sp['ty']) in final
        ]


# ═══════════════════════════════════════════════════════════════════════════════
#  DUNGEON GENERATORS
# ═══════════════════════════════════════════════════════════════════════════════

class _Rect:
    def __init__(self, x, y, w, h):
        self.x,self.y,self.w,self.h = x,y,w,h
    def centre(self):  return self.x+self.w//2, self.y+self.h//2
    def rand_pt(self,rng): return (rng.randint(self.x+1,self.x+self.w-2),
                                   rng.randint(self.y+1,self.y+self.h-2))


def _bsp_split(rect, rng, min_size=8, depth=0, max_depth=5):
    if depth >= max_depth or rect.w < min_size*2 or rect.h < min_size*2:
        return [rect]
    sv = rect.w > rect.h if rect.w != rect.h else rng.random() < 0.5
    if sv:
        s = rng.randint(min_size, rect.w-min_size)
        a = _Rect(rect.x, rect.y, s, rect.h)
        b = _Rect(rect.x+s, rect.y, rect.w-s, rect.h)
    else:
        s = rng.randint(min_size, rect.h-min_size)
        a = _Rect(rect.x, rect.y, rect.w, s)
        b = _Rect(rect.x, rect.y+s, rect.w, rect.h-s)
    return _bsp_split(a,rng,min_size,depth+1,max_depth) + \
           _bsp_split(b,rng,min_size,depth+1,max_depth)


def _carve_room(gmap, rect, rng, floor_t):
    rx = rect.x + rng.randint(1,2); ry = rect.y + rng.randint(1,2)
    rw = max(4, rect.w - rng.randint(3,5)); rh = max(4, rect.h - rng.randint(3,5))
    gmap.fill_rect(rx, ry, rx+rw-1, ry+rh-1, floor_t)
    return _Rect(rx, ry, rw, rh)


def _corridor(gmap, x1,y1,x2,y2, floor_t, rng):
    if rng.random()<0.5:
        for x in range(min(x1,x2),max(x1,x2)+1): gmap.set(x,y1,floor_t)
        for y in range(min(y1,y2),max(y1,y2)+1): gmap.set(x2,y,floor_t)
    else:
        for y in range(min(y1,y2),max(y1,y2)+1): gmap.set(x1,y,floor_t)
        for x in range(min(x1,x2),max(x1,x2)+1): gmap.set(x,y2,floor_t)


def _bsp_dungeon(seed, dun_id, level=0):
    cfg  = DUNGEONS[dun_id]
    rng  = random.Random(seed ^ (dun_id*0xDEAD + level*0xBEEF))
    W,H  = DUN_W, DUN_H
    ft   = cfg['floor']; wt = cfg['wall']
    is_deep = level > 0

    gmap = GameMap(W, H, is_dungeon=True, dungeon_id=dun_id,
                   dungeon_level=level, ambient=max(10, cfg['ambient']-level*15),
                   map_key=f"{dun_id}_{level}")
    gmap.fill(wt)

    leaves = _bsp_split(_Rect(1,1,W-2,H-2), rng, min_size=8,
                        max_depth=5 if is_deep else 4)
    rooms  = [_carve_room(gmap, leaf, rng, ft) for leaf in leaves]

    for i in range(len(rooms)-1):
        cx1,cy1 = rooms[i].centre(); cx2,cy2 = rooms[i+1].centre()
        _corridor(gmap, cx1,cy1,cx2,cy2, ft, rng)
    for _ in range(len(rooms)//4):
        i,j = rng.randint(0,len(rooms)-1), rng.randint(0,len(rooms)-1)
        if i!=j:
            cx1,cy1 = rooms[i].centre(); cx2,cy2 = rooms[j].centre()
            _corridor(gmap, cx1,cy1,cx2,cy2, ft, rng)

    ex,ey = rooms[0].rand_pt(rng)
    gmap.set(ex,ey, T_STAIRS_UP)
    gmap.entrance_tile = (ex,ey)

    # Stairs down to next level (if not the deepest)
    has_deeper = level < cfg['levels']-1
    bx,by = rooms[-1].rand_pt(rng)
    if has_deeper:
        gmap.set(bx,by, T_STAIRS_DOWN)
        gmap.stairs_down_tile = (bx,by)
    else:
        gmap.set(bx,by, T_SHRINE)
    gmap.exit_tile = (bx,by)

    # Chests
    chest_rooms = rng.sample(rooms[1:-1], min(len(rooms)//4+1, len(rooms)-2))
    for cr in chest_rooms:
        gmap.set(*cr.rand_pt(rng), T_CHEST)

    _populate_dungeon(gmap, rooms[1:], dun_id, level, rng)
    _ensure_connected(gmap, ft, wt)
    return gmap


def _cave_dungeon(seed, dun_id, level=0):
    cfg = DUNGEONS[dun_id]
    rng = random.Random(seed ^ (dun_id*0xCAFE + level*0xF00D))
    W,H = DUN_W, DUN_H
    ft  = cfg['floor']; wt = cfg['wall']
    is_deep = level > 0

    gmap = GameMap(W, H, is_dungeon=True, dungeon_id=dun_id,
                   dungeon_level=level, ambient=max(10, cfg['ambient']-level*15),
                   map_key=f"{dun_id}_{level}")

    # Run CA up to 3 times until we get a big-enough largest component
    for _attempt in range(3):
        _rng2 = random.Random(seed ^ (dun_id*0xCAFE + level*0xF00D + _attempt*999))
        grid = [[1 if _rng2.random()<(0.58 if is_deep else 0.52) else 0
                 for _ in range(W)] for _ in range(H)]
        for x in range(W): grid[0][x]=grid[H-1][x]=1
        for y in range(H): grid[y][0]=grid[y][W-1]=1
        for _ in range(4):
            new_g = [[1]*W for _ in range(H)]
            for y in range(1,H-1):
                for x in range(1,W-1):
                    walls = sum(grid[y+dy][x+dx] for dy in (-1,0,1) for dx in (-1,0,1))
                    new_g[y][x] = 1 if walls>=5 else 0
            grid = new_g

        # Find the LARGEST connected component (not just from centre)
        all_seen = set()
        largest = set()
        for sy in range(1,H-1):
            for sx in range(1,W-1):
                if not grid[sy][sx] and (sx,sy) not in all_seen:
                    comp = set(); q = deque([(sx,sy)]); comp.add((sx,sy))
                    while q:
                        tx,ty = q.popleft()
                        for ddx,ddy in DIRS_4:
                            nx,ny=tx+ddx,ty+ddy
                            if (nx,ny) not in comp and 0<nx<W-1 and 0<ny<H-1 and not grid[ny][nx]:
                                comp.add((nx,ny)); q.append((nx,ny))
                    all_seen |= comp
                    if len(comp) > len(largest): largest = comp
        if len(largest) >= 80:
            break   # good enough

    visited = largest

    # Apply grid to map, walling off non-largest-component floor
    for y in range(H):
        for x in range(W):
            if grid[y][x] or (x,y) not in visited:
                gmap.set(x,y,wt)
            else:
                gmap.set(x,y,ft)

    reachable = sorted(visited, key=lambda p: rng.random())   # random order
    ex,ey = reachable[0]
    gmap.set(ex,ey,T_STAIRS_UP); gmap.entrance_tile=(ex,ey)

    reachable.sort(key=lambda p:(p[0]-ex)**2+(p[1]-ey)**2, reverse=True)
    bx,by=reachable[0]
    has_deeper = level < cfg['levels']-1
    if has_deeper:
        gmap.set(bx,by,T_STAIRS_DOWN); gmap.stairs_down_tile=(bx,by)
    else:
        gmap.set(bx,by,T_SHRINE)
    gmap.exit_tile=(bx,by)

    if len(reachable) >= 10:
        spots = rng.sample(reachable[len(reachable)//4:3*len(reachable)//4],
                           min(5, max(1, len(reachable)//10)))
        for cpx,cpy in spots: gmap.set(cpx,cpy,T_CHEST)

    fake_rooms = [_Rect(max(0,p[0]-2),max(0,p[1]-2),5,5)
                  for p in rng.sample(reachable, min(10,len(reachable)))]
    _populate_dungeon(gmap, fake_rooms, dun_id, level, rng)
    _ensure_connected(gmap, ft, wt)
    return gmap


def _drunk_dungeon(seed, dun_id, level=0):
    cfg = DUNGEONS[dun_id]
    rng = random.Random(seed ^ (dun_id*0xF00B + level*0xD00D))
    W,H = DUN_W, DUN_H
    ft  = cfg['floor']; wt = cfg['wall']
    is_deep = level > 0

    gmap = GameMap(W, H, is_dungeon=True, dungeon_id=dun_id,
                   dungeon_level=level, ambient=max(10, cfg['ambient']-level*15),
                   map_key=f"{dun_id}_{level}")
    gmap.fill(wt)

    sx,sy = W//2, H//2
    wx,wy = sx,sy
    floor_cells=set()
    gmap.set(wx,wy,ft); floor_cells.add((wx,wy))
    steps = W*H//(2 if is_deep else 3)
    for _ in range(steps):
        wx=max(2,min(W-3,wx+rng.choice([-1,0,1])))
        wy=max(2,min(H-3,wy+rng.choice([-1,0,1])))
        gmap.set(wx,wy,ft); floor_cells.add((wx,wy))
        if rng.random()<0.25:
            ndx,ndy=rng.choice(DIRS_4)
            nx,ny=wx+ndx,wy+ndy
            if 1<nx<W-2 and 1<ny<H-2:
                gmap.set(nx,ny,ft); floor_cells.add((nx,ny))

    rooms=[]
    for _ in range(10 if is_deep else 8):
        rw=rng.randint(4,9); rh=rng.randint(4,8)
        rx=rng.randint(2,W-rw-2); ry=rng.randint(2,H-rh-2)
        rcx=rx+rw//2; rcy=ry+rh//2
        gmap.fill_rect(rx,ry,rx+rw-1,ry+rh-1,ft)
        for dx in range(rw):
            for dy in range(rh): floor_cells.add((rx+dx,ry+dy))
        _corridor(gmap,rcx,rcy,sx,sy,ft,rng)
        for x in range(min(rcx,sx),max(rcx,sx)+1): floor_cells.add((x,rcy))
        for y in range(min(rcy,sy),max(rcy,sy)+1): floor_cells.add((rcx,y))
        rooms.append(_Rect(rx,ry,rw,rh))

    gmap.set(sx,sy,T_STAIRS_UP); gmap.entrance_tile=(sx,sy)
    reachable=sorted(floor_cells,key=lambda p:(p[0]-sx)**2+(p[1]-sy)**2,reverse=True)
    bx,by=reachable[0]
    has_deeper = level < cfg['levels']-1
    if has_deeper:
        gmap.set(bx,by,T_STAIRS_DOWN); gmap.stairs_down_tile=(bx,by)
    else:
        gmap.set(bx,by,T_SHRINE)
    gmap.exit_tile=(bx,by)

    spots=rng.sample(reachable[10:],min(4,max(1,len(reachable)-10)))
    for cpx,cpy in spots: gmap.set(cpx,cpy,T_CHEST)

    _populate_dungeon(gmap, rooms, dun_id, level, rng)
    _ensure_connected(gmap, ft, wt)
    return gmap


# ─── Enemy population ─────────────────────────────────────────────────────────

def _populate_dungeon(gmap, rooms, dun_id, level, rng):
    cfg   = DUNGEONS[dun_id]
    etypes= cfg['enemies']
    scale = 1 + level * 0.5   # deeper = more enemies

    gmap.enemy_spawns = []
    gmap.item_spawns  = []

    for i, room in enumerate(rooms):
        if i == 0: continue
        n = rng.randint(1, max(1, int(3 * scale)))
        for _ in range(n):
            ex = rng.randint(room.x+1, max(room.x+1, room.x+room.w-2))
            ey = rng.randint(room.y+1, max(room.y+1, room.y+room.h-2))
            gmap.enemy_spawns.append({'type': rng.choice(etypes),
                                      'tx': ex, 'ty': ey})
        if rng.random() < 0.4:
            ix = rng.randint(room.x+1, max(room.x+1, room.x+room.w-2))
            iy = rng.randint(room.y+1, max(room.y+1, room.y+room.h-2))
            iid = rng.choice(['mushroom','herb','coin','coin','blue_flower',
                               'potion','mana_pot','arrow','stone'])
            gmap.item_spawns.append({'iid': iid, 'count': rng.randint(1,3),
                                     'tx': ix, 'ty': iy})

    # Boss near shrine/stairs_down
    bx,by = gmap.exit_tile
    boss_type = cfg['boss']
    # Only place boss on deepest level
    if level == cfg['levels'] - 1:
        placed = False
        for ddx,ddy in [(2,0),(0,2),(-2,0),(0,-2),(2,2),(-2,2),(2,-2),(-2,-2)]:
            nbx,nby = bx+ddx, by+ddy
            if gmap.in_bounds(nbx,nby):
                t = gmap.get(nbx,nby)
                if t in (cfg['floor'], T_FLOOR, T_CAVE_FLOOR):
                    gmap.enemy_spawns.append({'type': boss_type,
                                              'tx': nbx, 'ty': nby,
                                              'boss': True, 'level': level})
                    placed = True; break
        if not placed:
            gmap.enemy_spawns.append({'type': boss_type,
                                      'tx': bx+2, 'ty': by+2,
                                      'boss': True, 'level': level})


# ─── Factory functions ────────────────────────────────────────────────────────

def build_dungeon_level(seed: int, dun_id: int, level: int = 0) -> GameMap:
    style = DUNGEONS[dun_id]['style']
    if style == 'bsp':   return _bsp_dungeon(seed, dun_id, level)
    if style == 'cave':  return _cave_dungeon(seed, dun_id, level)
    if style == 'drunk': return _drunk_dungeon(seed, dun_id, level)
    raise ValueError(f"Unknown style: {style!r}")


# Legacy alias used by old code
def build_dungeon(seed, dun_id):
    return build_dungeon_level(seed, dun_id, 0)


def build_town(seed: int) -> tuple:
    """Returns (GameMap, start_tile)."""
    gen  = TownGenerator(seed)
    gmap = gen.generate()
    return gmap, gen.start_tile


def build_biome_map(seed: int, map_key: str) -> GameMap:
    cls  = _BIOME_CLASSES[map_key]
    gen  = cls(seed)
    gmap = gen.generate()
    gmap.biome_dungeon_positions = gen.dungeon_positions
    return gmap
