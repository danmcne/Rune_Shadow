"""
Rune & Shadow - Entities
Player, Enemy subclasses, Projectiles, and attack-effect visuals.

v2 improvements:
  - Player can swim in T_WATER at half speed (blue tint)
  - Player uses mouse position for ranged/magic aiming with autoaim
  - Enemy AI: aggro_type (sight/attack/passive), flee_hp_pct, deaggro_distance
  - Enemy AI: fight_to_death flag
  - Most enemies invisible in darkness; ghosts/glowing mobs always visible
  - Mob names drawn above sprites
  - Kelpie: water monster that swims (inverse of player - lives in water)
  - Variable mob speeds; some faster, some slower than player
"""
import math
import random
import pygame

from constants import *
from animation import Animator, State, Dir, FACING_TO_DIR
from items import (Inventory, make_item, roll_drops,
                   KNIFE, STAFF, SLING, CANDLE, SPELL_BASIC, STONE)


# ─── Small font for entity labels ─────────────────────────────────────────────
_label_fonts = {}
def _label_font(size=11):
    if size not in _label_fonts:
        _label_fonts[size] = pygame.font.SysFont("monospace", size, bold=True)
    return _label_fonts[size]


# ═══════════════════════════════════════════════════════════════════════════════
#  Base Entity
# ═══════════════════════════════════════════════════════════════════════════════

class Entity:
    SIZE = ENTITY_SIZE

    def __init__(self, x: float, y: float, color,
                 hp: int, entity_type: str = 'unknown'):
        self.x     = float(x)
        self.y     = float(y)
        self.color = color
        self.hp    = hp
        self.max_hp= hp
        self.alive = True
        self.speed = 1.5
        self.facing= DIR_RIGHT

        self.entity_type = entity_type
        self.animator    = Animator(entity_type)

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.SIZE, self.SIZE)

    @property
    def cx(self): return self.x + self.SIZE / 2
    @property
    def cy(self): return self.y + self.SIZE / 2

    def dist_to(self, other) -> float:
        return math.hypot(self.cx - other.cx, self.cy - other.cy)

    def try_move(self, dx: float, dy: float, gmap,
                 ghost: bool = False, water_walker: bool = False) -> None:
        sz = self.SIZE
        if dx != 0:
            nx = self.x + dx
            if ghost or not self._tile_hit(nx, self.y, sz, gmap, water_walker):
                self.x = nx
        if dy != 0:
            ny = self.y + dy
            if ghost or not self._tile_hit(self.x, ny, sz, gmap, water_walker):
                self.y = ny

    def _tile_hit(self, x, y, sz, gmap, water_walker=False) -> bool:
        ts      = TILE_SIZE
        corners = [(x, y), (x+sz-1, y), (x, y+sz-1), (x+sz-1, y+sz-1)]
        for cx, cy in corners:
            tx, ty = int(cx // ts), int(cy // ts)
            t = gmap.get(tx, ty)
            if water_walker:
                # Water walkers can swim but can't walk on land tiles
                # Actually kelpies are amphibious: treat land as walkable too
                if not (tile_walkable(t) or tile_swimmable(t)):
                    return True
            else:
                if not tile_walkable(t):
                    return True
        mw = gmap.width  * ts
        mh = gmap.height * ts
        if x < 0 or y < 0 or x + sz > mw or y + sz > mh:
            return True
        return False

    def take_damage(self, amount: int) -> int:
        actual = max(1, amount)
        self.hp -= actual
        if self.hp <= 0:
            self.hp    = 0
            self.alive = False
            self.animator.trigger_dead()
        else:
            self.animator.trigger_hurt()
        return actual

    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int,
             asset_mgr=None):
        sx = int(self.x) - cam_x
        sy = int(self.y) - cam_y
        s  = self.SIZE
        if sx + s < 0 or sx > surf.get_width(): return
        if sy + s < 0 or sy > surf.get_height(): return

        sprite = None
        if asset_mgr is not None:
            sprite = asset_mgr.get_entity_surface(self.animator)

        if sprite is not None:
            surf.blit(sprite, (sx, sy))
        else:
            pygame.draw.rect(surf, self.color, (sx, sy, s, s))
            pygame.draw.rect(surf, (0, 0, 0),  (sx, sy, s, s), 1)


# ═══════════════════════════════════════════════════════════════════════════════
#  Player
# ═══════════════════════════════════════════════════════════════════════════════

class Player(Entity):
    def __init__(self, x: float, y: float):
        super().__init__(x, y, COL_PLAYER, PLAYER_START_HP, 'player')
        self.speed      = PLAYER_SPEED
        self.mana       = PLAYER_START_MANA
        self.max_mana   = PLAYER_START_MANA
        self.defense    = 0

        self.inventory  = Inventory()
        self.hotbar     = [None] * HOTBAR_SLOTS
        self.equipped   = 0

        self.attack_cooldown = 0
        self.iframes         = 0
        self.attack_effect   = None
        self.light_radius    = 6

        # Swimming
        self.is_swimming = False

        # Mouse aim (world coords)
        self.mouse_world_x = x
        self.mouse_world_y = y
        # Computed aim direction (unit vector)
        self.aim_dir = (1.0, 0.0)

        self._init_inventory()

    def _init_inventory(self):
        inv = self.inventory
        for it, cnt in [
            (KNIFE,             1), (STAFF,       1), (SLING,  1),
            (CANDLE,            1), (SPELL_BASIC, 1),
            (make_item('stone'), 15),
            (make_item('mushroom'), 3),
            (make_item('herb'),  2),
        ]:
            inv.add(it, cnt)
        self.hotbar = ['knife','staff','sling','candle','spell_basic',
                       None, None, None]

    def equipped_item(self):
        iid = self.hotbar[self.equipped]
        if iid and self.inventory.has(iid):
            from items import ITEMS
            return ITEMS.get(iid)
        return None

    def cycle_hotbar(self, direction: int):
        self.equipped = (self.equipped + direction) % HOTBAR_SLOTS

    def update_light(self):
        base = 3
        for iid in self.hotbar:
            if iid is None: continue
            from items import ITEMS
            it = ITEMS.get(iid)
            if it and it.itype == IT_LIGHT:
                base = max(base, it.light_radius)
        self.light_radius = base

    def set_mouse_world(self, mx: int, my: int, cam_x: int, cam_y: int):
        """Call each frame with the current screen mouse position."""
        self.mouse_world_x = mx + cam_x
        self.mouse_world_y = my + cam_y

    def compute_aim(self, enemies: list):
        """
        Compute aim_dir from player centre to mouse world pos.
        If an enemy is within AUTOAIM_RADIUS and roughly in the aim direction, snap to it.
        """
        dx = self.mouse_world_x - self.cx
        dy = self.mouse_world_y - self.cy
        d  = math.hypot(dx, dy)
        if d > 0:
            self.aim_dir = (dx/d, dy/d)
        # Autoaim: find nearest living enemy within radius
        best_e   = None
        best_dot = 0.3   # minimum dot product (angle tolerance)
        for e in enemies:
            if not e.alive: continue
            ed = math.hypot(e.cx - self.cx, e.cy - self.cy)
            if ed > AUTOAIM_RADIUS: continue
            if ed == 0: continue
            edx, edy = (e.cx - self.cx)/ed, (e.cy - self.cy)/ed
            dot = edx * self.aim_dir[0] + edy * self.aim_dir[1]
            if dot > best_dot:
                best_dot = dot
                best_e   = e
        if best_e is not None:
            dx2 = best_e.cx - self.cx
            dy2 = best_e.cy - self.cy
            d2  = math.hypot(dx2, dy2)
            if d2 > 0:
                self.aim_dir = (dx2/d2, dy2/d2)

    def attack(self, gmap, enemies: list, projectiles: list, messages: list):
        if self.attack_cooldown > 0:
            return
        item = self.equipped_item()
        if item is None:
            messages.append(("Nothing equipped!", YELLOW))
            return

        self.animator.trigger_attack(self.facing)

        if item.itype == IT_WEAPON:
            self._melee_attack(item, gmap, enemies, messages)
        elif item.itype == IT_RANGED:
            self._ranged_attack(item, gmap, projectiles, messages, enemies)
        elif item.itype == IT_MAGIC:
            self._magic_attack(item, gmap, projectiles, messages, enemies)
        elif item.itype == IT_LIGHT:
            messages.append(("You hold up the light.", YELLOW))
            return

        self.attack_cooldown = item.cooldown if item else 20

    def _melee_attack(self, item, gmap, enemies, messages):
        fx, fy = self.facing
        reach  = item.attack_range
        ax = self.cx + fx * (self.SIZE // 2 + 4)
        ay = self.cy + fy * (self.SIZE // 2 + 4)
        atk_rect = pygame.Rect(ax - reach//2, ay - reach//2, reach, reach)

        self.attack_effect = AttackEffect(atk_rect, YELLOW, 10)
        hit_any = False
        for e in enemies:
            if e.alive and atk_rect.colliderect(e.rect):
                dmg = max(1, item.damage - e.defense)
                e.take_damage(dmg)
                # Notify enemy it was attacked (for passive-aggro enemies)
                if hasattr(e, 'on_attacked'):
                    e.on_attacked()
                hit_any = True
                messages.append((f"Hit {e.name} for {dmg} dmg!", WHITE))

        if item.tool_tag:
            tx = int((ax + fx*16) // TILE_SIZE)
            ty = int((ay + fy*16) // TILE_SIZE)
            if gmap.in_bounds(tx, ty):
                t = gmap.get(tx, ty)
                if tile_tool(t) == item.tool_tag:
                    gmap.set(tx, ty, T_GRASS if not gmap.is_dungeon
                             else DUNGEONS[gmap.dungeon_id]['floor'])
                    messages.append(("Destroyed!", ORANGE))

        if not hit_any and not item.tool_tag:
            messages.append(("Whoosh... missed.", GRAY))

    def _ranged_attack(self, item, gmap, projectiles, messages, enemies):
        if not self.inventory.has(item.ammo_type):
            messages.append((f"No {item.ammo_type}s left!", RED))
            return
        self.inventory.remove(item.ammo_type, 1)
        # Use mouse aim direction
        direction = self.aim_dir
        proj = Projectile(self.cx, self.cy, direction,
                          item.proj_speed, item.damage, item.proj_color,
                          owner='player', ammo_type=item.ammo_type)
        projectiles.append(proj)
        messages.append((f"Fired {item.ammo_type}.", WHITE))

    def _magic_attack(self, item, gmap, projectiles, messages, enemies):
        if self.mana < item.mana_cost:
            messages.append(("Not enough mana!", BLUE))
            return
        self.mana -= item.mana_cost
        direction = self.aim_dir
        proj = Projectile(self.cx, self.cy, direction,
                          item.proj_speed, item.damage, item.proj_color,
                          owner='player', spell=item.spell_effect)
        projectiles.append(proj)
        messages.append((f"Cast {item.name}!", CYAN))

    def use_item(self, iid: str, messages: list) -> bool:
        from items import ITEMS
        it = ITEMS.get(iid)
        if it is None or not self.inventory.has(iid):
            return False
        if it.itype == IT_CONSUMABLE:
            if it.hp_restore:
                gained = min(it.hp_restore, self.max_hp - self.hp)
                self.hp += gained
                messages.append((f"Restored {gained} HP.", GREEN))
            if it.mp_restore:
                gained = min(it.mp_restore, self.max_mana - self.mana)
                self.mana += gained
                messages.append((f"Restored {gained} MP.", BLUE))
            self.inventory.remove(iid, 1)
            return True
        return False

    def take_damage(self, amount: int, difficulty: int = DIFFICULTY_NORMAL) -> int:
        if self.iframes > 0:
            return 0
        mult   = DIFFICULTY_DMG_MULT.get(difficulty, 1.0)
        scaled = max(1, amount - self.defense)
        actual = max(1, int(scaled * mult))
        self.hp -= actual
        if self.hp <= 0:
            self.hp    = 0
            self.alive = False
            self.animator.trigger_dead()
        else:
            self.animator.trigger_hurt()
        self.iframes = PLAYER_IFRAMES
        return actual

    def update(self, keys, gmap, enemies, projectiles, messages,
               cam_x: int = 0, cam_y: int = 0):
        dx = dy = 0.0
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: dx -= self.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: dx += self.speed
        if keys[pygame.K_UP]    or keys[pygame.K_w]: dy -= self.speed
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: dy += self.speed

        moving = (dx != 0 or dy != 0)

        if moving:
            if   dx < 0: self.facing = DIR_LEFT
            elif dx > 0: self.facing = DIR_RIGHT
            elif dy < 0: self.facing = DIR_UP
            else:        self.facing = DIR_DOWN
            if dx and dy:
                dx *= 0.7071; dy *= 0.7071

            # Check if destination is water (swimmable) → allow but slow
            new_x = self.x + dx
            new_y = self.y + dy
            sz    = self.SIZE
            ts    = TILE_SIZE
            corner_tiles = [
                gmap.get(int(new_x // ts),       int(new_y // ts)),
                gmap.get(int((new_x+sz-1) // ts), int(new_y // ts)),
                gmap.get(int(new_x // ts),        int((new_y+sz-1) // ts)),
                gmap.get(int((new_x+sz-1) // ts), int((new_y+sz-1) // ts)),
            ]
            all_swimmable = all(tile_swimmable(t) or tile_walkable(t)
                                for t in corner_tiles)
            any_swimmable = any(tile_swimmable(t) for t in corner_tiles)

            if any_swimmable and all_swimmable:
                # Can enter water at half speed
                dx *= SWIM_SPEED_MULT
                dy *= SWIM_SPEED_MULT
                self.is_swimming = True
                self._try_move_swim(dx, dy, gmap)
            else:
                self.is_swimming = False
                self.try_move(dx, dy, gmap)

            # Check current tile for swimming status
            ptx = int(self.cx // TILE_SIZE)
            pty = int(self.cy // TILE_SIZE)
            self.is_swimming = tile_swimmable(gmap.get(ptx, pty))

            self.animator.push_walk(self.facing)
        else:
            ptx = int(self.cx // TILE_SIZE)
            pty = int(self.cy // TILE_SIZE)
            self.is_swimming = tile_swimmable(gmap.get(ptx, pty))
            self.animator.push_idle(self.facing)

        self.animator.tick()

        if self.attack_cooldown > 0: self.attack_cooldown -= 1
        if self.iframes         > 0: self.iframes         -= 1
        if self.attack_effect:
            self.attack_effect.update()
            if self.attack_effect.done:
                self.attack_effect = None

        if self.mana < self.max_mana and random.random() < 0.004:
            self.mana = min(self.max_mana, self.mana + 1)

        self.update_light()

        # Update mouse aim
        mx, my = pygame.mouse.get_pos()
        self.set_mouse_world(mx, my, cam_x, cam_y)
        self.compute_aim(enemies)

    def _try_move_swim(self, dx, dy, gmap):
        """Move allowing water tiles."""
        sz = self.SIZE
        ts = TILE_SIZE
        mw = gmap.width  * ts
        mh = gmap.height * ts

        def swimmable_or_walkable(x, y):
            corners = [(x, y), (x+sz-1, y), (x, y+sz-1), (x+sz-1, y+sz-1)]
            for cx_, cy_ in corners:
                t = gmap.get(int(cx_ // ts), int(cy_ // ts))
                if not (tile_walkable(t) or tile_swimmable(t)):
                    return False
            return (0 <= x and 0 <= y and x+sz <= mw and y+sz <= mh)

        if dx != 0:
            nx = self.x + dx
            if swimmable_or_walkable(nx, self.y):
                self.x = nx
        if dy != 0:
            ny = self.y + dy
            if swimmable_or_walkable(self.x, ny):
                self.y = ny

    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int,
             asset_mgr=None):
        sx = int(self.x) - cam_x
        sy = int(self.y) - cam_y

        sprite = None
        if asset_mgr is not None:
            sprite = asset_mgr.get_entity_surface(self.animator)

        if sprite is not None:
            spr = sprite.copy()
            if self.is_swimming:
                # Apply blue tint when swimming
                spr.fill((0, 80, 180, 60), special_flags=pygame.BLEND_RGBA_ADD)
            if self.iframes > 0 and (self.iframes // 4) % 2 == 1:
                spr.fill((255,255,255,120), special_flags=pygame.BLEND_RGBA_ADD)
            surf.blit(spr, (sx, sy))
        else:
            col = WHITE if (self.iframes > 0 and
                            (self.iframes//4) % 2 == 1) else self.color
            if self.is_swimming:
                col = (max(0,col[0]-60), max(0,col[1]-20), min(255,col[2]+80))
            pygame.draw.rect(surf, col, (sx, sy, self.SIZE, self.SIZE))
            pygame.draw.rect(surf, (0,0,0), (sx, sy, self.SIZE, self.SIZE), 1)
            fx, fy = self.facing
            ix = sx + self.SIZE//2 + fx*(self.SIZE//2-4) - 3
            iy = sy + self.SIZE//2 + fy*(self.SIZE//2-4) - 3
            pygame.draw.rect(surf, (0,0,0), (ix, iy, 6, 6))

        if self.attack_effect:
            self.attack_effect.draw(surf, cam_x, cam_y, asset_mgr)

        # Aim indicator (small dot in aim direction)
        if not self.is_swimming:
            ax = sx + self.SIZE//2 + int(self.aim_dir[0]*14)
            ay = sy + self.SIZE//2 + int(self.aim_dir[1]*14)
            pygame.draw.circle(surf, YELLOW, (ax, ay), 3)


# ═══════════════════════════════════════════════════════════════════════════════
#  Attack Effect (visual only)
# ═══════════════════════════════════════════════════════════════════════════════

_FX_FRAMES = {
    'attack_slash': 3,
    'hit_spark':    2,
    'fire_burst':   4,
    'frost_burst':  3,
    'magic_ring':   4,
}


class AttackEffect:
    def __init__(self, rect: pygame.Rect, color, duration: int,
                 fx_name: str = 'attack_slash'):
        self.rect     = rect
        self.color    = color
        self.duration = duration
        self.timer    = duration
        self.done     = False
        self.fx_name  = fx_name
        self._frame   = 0

    def update(self):
        self.timer -= 1
        total = _FX_FRAMES.get(self.fx_name, 3)
        self._frame = int((1 - self.timer / max(1, self.duration)) * total)
        if self.timer <= 0:
            self.done = True

    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int,
             asset_mgr=None):
        frame = min(self._frame, _FX_FRAMES.get(self.fx_name, 3) - 1)
        rx    = self.rect.x - cam_x
        ry    = self.rect.y - cam_y

        sprite = None
        if asset_mgr is not None:
            sprite = asset_mgr.get_fx_frame(self.fx_name, frame)

        if sprite is not None:
            bx = rx + self.rect.w//2 - sprite.get_width()//2
            by = ry + self.rect.h//2 - sprite.get_height()//2
            surf.blit(sprite, (bx, by))
        else:
            alpha = int(200 * self.timer / max(1, self.duration))
            r     = pygame.Rect(rx, ry, self.rect.w, self.rect.h)
            s     = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
            s.fill((*self.color[:3], alpha))
            surf.blit(s, (r.x, r.y))


# ═══════════════════════════════════════════════════════════════════════════════
#  Projectile
# ═══════════════════════════════════════════════════════════════════════════════

class Projectile:
    SIZE = 8

    def __init__(self, x, y, direction, speed, damage, color,
                 owner='player', ammo_type=None, spell=None):
        self.x         = float(x) - self.SIZE / 2
        self.y         = float(y) - self.SIZE / 2
        self.dx        = direction[0] * speed
        self.dy        = direction[1] * speed
        self.speed     = speed
        self.damage    = damage
        self.color     = color
        self.owner     = owner
        self.ammo_type = ammo_type
        self.spell     = spell
        self.alive     = True
        self.lifetime  = 120
        self.kind = spell if spell else (ammo_type if ammo_type else 'arcane')

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.SIZE, self.SIZE)

    def update(self, gmap, player, enemies: list, messages: list):
        if not self.alive: return
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.alive = False
            return
        self.x += self.dx
        self.y += self.dy
        tx = int((self.x + self.SIZE/2) // TILE_SIZE)
        ty = int((self.y + self.SIZE/2) // TILE_SIZE)
        t  = gmap.get(tx, ty)
        # Projectiles stop at walls; they can travel over water/walkable tiles
        if not tile_walkable(t) and not tile_swimmable(t):
            self.alive = False
            return
        r = self.rect
        if self.owner == 'player':
            for e in enemies:
                if e.alive and r.colliderect(e.rect):
                    dmg = e.take_damage(self.damage)
                    if hasattr(e, 'on_attacked'):
                        e.on_attacked()
                    messages.append((f"Hit {e.name} for {dmg}!", WHITE))
                    self.alive = False
                    if self.spell == 'fireball':
                        for e2 in enemies:
                            if e2 is not e and e2.alive:
                                if math.hypot(e.cx-e2.cx,
                                              e.cy-e2.cy) < TILE_SIZE*1.5:
                                    e2.take_damage(self.damage // 2)
                    return
        elif self.owner == 'enemy':
            if r.colliderect(player.rect):
                dmg = player.take_damage(self.damage)
                if dmg > 0:
                    messages.append((f"You took {dmg} damage!", RED))
                self.alive = False

    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int,
             asset_mgr=None):
        sx = int(self.x) - cam_x
        sy = int(self.y) - cam_y

        sprite = None
        if asset_mgr is not None:
            sprite = asset_mgr.get_projectile(self.kind)

        if sprite is not None:
            surf.blit(sprite, (sx, sy))
        else:
            pygame.draw.rect(surf, self.color, (sx, sy, self.SIZE, self.SIZE))


# ═══════════════════════════════════════════════════════════════════════════════
#  Enemy Base
# ═══════════════════════════════════════════════════════════════════════════════

class Enemy(Entity):
    DETECTION_RANGE = 180
    ATTACK_RANGE    = 34
    ATTACK_DAMAGE   = 8
    ATTACK_COOL     = 60
    DEFENSE         = 0
    RANGED_RANGE    = 0
    PROJ_SPEED      = 4
    PROJ_COLOR      = RED
    PROJ_DAMAGE     = 6

    # Behavior flags
    AGGRO_TYPE      = 'sight'   # 'sight' | 'attack' | 'passive'
    FLEE_HP_PCT     = 0.0       # flee when HP < this fraction
    DEAGGRO_DIST    = 0         # distance to give up chase (0=never)
    FIGHT_TO_DEATH  = False     # ignore flee/deaggro if True
    LUMINOUS        = False     # visible in darkness regardless of lighting

    def __init__(self, x, y, name, color, hp, speed,
                 etype: str, is_boss: bool = False):
        super().__init__(x, y, color, hp * (3 if is_boss else 1), etype)
        self.name    = name
        self.speed   = speed
        self.etype   = etype
        self.is_boss = is_boss
        self.defense = self.DEFENSE
        self.SIZE    = ENTITY_SIZE * 2 if is_boss else ENTITY_SIZE

        self._state         = 'wander'
        self._wander_dir    = (0.0, 0.0)
        self._wander_timer  = 0
        self._attack_cool   = 0
        self._stun_timer    = 0
        self._proj_cool     = 0
        self._rng           = random.Random(id(self))
        self._aggroed       = False    # Whether enemy is currently aggroed
        self._aggro_src     = 'none'   # 'sight' or 'attack'

    def on_attacked(self):
        """Called when this enemy is hit. Triggers aggro for passive-aggro types."""
        if self.AGGRO_TYPE in ('attack', 'sight'):
            self._aggroed = True
            self._aggro_src = 'attack'
            self._state = 'chase'

    def update(self, player: 'Player', gmap,
               projectiles: list, messages: list):
        if not self.alive: return

        dist = self.dist_to(player)

        # Determine aggro state
        if self._stun_timer > 0:
            self._stun_timer -= 1
            self._state = 'stunned'
        else:
            should_aggro = False
            if self.AGGRO_TYPE == 'sight' and dist < self.DETECTION_RANGE:
                should_aggro = True
            elif self._aggroed:
                should_aggro = True

            low_hp = (self.hp / self.max_hp) < self.FLEE_HP_PCT
            fleeing = low_hp and not self.FIGHT_TO_DEATH and self.FLEE_HP_PCT > 0

            if fleeing:
                self._state = 'flee'
            elif should_aggro:
                if dist < self.ATTACK_RANGE:
                    self._state = 'attack'
                else:
                    self._state = 'chase'
                    # De-aggro if beyond range and not fight-to-death
                    if (self.DEAGGRO_DIST > 0 and
                            dist > self.DEAGGRO_DIST and
                            not self.FIGHT_TO_DEATH and
                            self._aggro_src == 'sight'):
                        self._aggroed = False
                        self._state = 'wander'
            else:
                if self._state in ('chase', 'attack'):
                    self._state = 'wander'

        if self._attack_cool > 0: self._attack_cool -= 1
        if self._proj_cool   > 0: self._proj_cool   -= 1

        if   self._state == 'wander':  self._do_wander(gmap)
        elif self._state == 'chase':   self._do_chase(player, gmap, projectiles)
        elif self._state == 'attack':  self._do_attack(player, gmap,
                                                        projectiles, messages)
        elif self._state == 'flee':    self._do_flee(player, gmap)
        elif self._state == 'stunned': self.animator.push_idle(self.facing)

        self.animator.tick()

    def _do_wander(self, gmap):
        self._wander_timer -= 1
        if self._wander_timer <= 0:
            angle = self._rng.uniform(0, 2*math.pi)
            self._wander_dir   = (math.cos(angle), math.sin(angle))
            self._wander_timer = self._rng.randint(40, 100)
        dx = self._wander_dir[0] * self.speed * 0.4
        dy = self._wander_dir[1] * self.speed * 0.4
        self.try_move(dx, dy, gmap, ghost=self._is_ghost(),
                      water_walker=self._is_water_walker())
        if abs(dx) > abs(dy):
            self.facing = DIR_RIGHT if dx > 0 else DIR_LEFT
        elif dy != 0:
            self.facing = DIR_DOWN if dy > 0 else DIR_UP
        self.animator.push_walk(self.facing)

    def _do_chase(self, player, gmap, projectiles):
        dx = player.cx - self.cx
        dy = player.cy - self.cy
        d  = math.hypot(dx, dy)
        if d > 0:
            self.try_move(dx/d * self.speed, dy/d * self.speed,
                          gmap, ghost=self._is_ghost(),
                          water_walker=self._is_water_walker())
            if abs(dx) > abs(dy):
                self.facing = DIR_RIGHT if dx > 0 else DIR_LEFT
            else:
                self.facing = DIR_DOWN if dy > 0 else DIR_UP
            self.animator.push_walk(self.facing)
            self._aggroed = True

        if self.RANGED_RANGE and d < self.RANGED_RANGE and self._proj_cool == 0:
            self._fire_proj(player, projectiles)

    def _do_attack(self, player, gmap, projectiles, messages):
        self.animator.push_idle(self.facing)
        self._aggroed = True
        if self._attack_cool == 0:
            dmg = player.take_damage(self.ATTACK_DAMAGE)
            if dmg > 0:
                messages.append((f"{self.name} hits you for {dmg}!", RED))
            self._attack_cool = self.ATTACK_COOL

    def _do_flee(self, player, gmap):
        """Run away from player."""
        dx = self.cx - player.cx
        dy = self.cy - player.cy
        d  = math.hypot(dx, dy)
        if d > 0:
            self.try_move(dx/d * self.speed * 1.2, dy/d * self.speed * 1.2,
                          gmap, ghost=self._is_ghost(),
                          water_walker=self._is_water_walker())
        self.animator.push_walk(self.facing)

    def _fire_proj(self, player, projectiles):
        dx = player.cx - self.cx
        dy = player.cy - self.cy
        d  = math.hypot(dx, dy)
        if d == 0: return
        proj = Projectile(self.cx, self.cy, (dx/d, dy/d),
                          self.PROJ_SPEED, self.PROJ_DAMAGE,
                          self.PROJ_COLOR, owner='enemy')
        projectiles.append(proj)
        self._proj_cool = 90

    def _is_ghost(self): return False
    def _is_water_walker(self): return False

    def get_drops(self, rng) -> list:
        drops = roll_drops(self.etype, rng)
        if self.is_boss:
            drops += roll_drops(self.etype, rng)
        return drops

    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int,
             asset_mgr=None, brightness: int = 255):
        """Draw with optional brightness parameter (for dark dungeons)."""
        sx = int(self.x) - cam_x
        sy = int(self.y) - cam_y
        s  = self.SIZE
        if sx + s < 0 or sx > surf.get_width(): return
        if sy + s < 0 or sy > surf.get_height(): return

        # Visibility check in dark areas
        luminous = self.LUMINOUS or self.is_boss
        if brightness < 40 and not luminous:
            return   # invisible in darkness

        sprite = None
        if asset_mgr is not None:
            sprite = asset_mgr.get_entity_surface(self.animator)

        alpha = 255
        if luminous and brightness < 128:
            # Luminous entities glow even in darkness but dimly
            alpha = max(80, brightness * 2)

        if sprite is not None:
            if sprite.get_size() != (s, s):
                sprite = pygame.transform.scale(sprite, (s, s))
            if alpha < 255:
                spr = sprite.copy()
                spr.set_alpha(alpha)
                surf.blit(spr, (sx, sy))
            else:
                surf.blit(sprite, (sx, sy))
        else:
            col = tuple(min(255, c+40) for c in self.color) \
                  if self.is_boss else self.color
            if alpha < 255:
                s_surf = pygame.Surface((s, s), pygame.SRCALPHA)
                s_surf.fill((*col, alpha))
                surf.blit(s_surf, (sx, sy))
            else:
                pygame.draw.rect(surf, col,   (sx, sy, s, s))
                pygame.draw.rect(surf, BLACK, (sx, sy, s, s), 1)

        # HP bar
        bar_w = int(s * self.hp / self.max_hp)
        pygame.draw.rect(surf, DARK_RED, (sx, sy-6, s, 4))
        pygame.draw.rect(surf, GREEN,    (sx, sy-6, bar_w, 4))

        # Name label (only in reasonably lit areas)
        if brightness >= 50 or luminous:
            f = _label_font(10)
            label = f.render(self.name, True, WHITE)
            shadow = f.render(self.name, True, BLACK)
            lx = sx + s//2 - label.get_width()//2
            ly = sy - 17
            surf.blit(shadow, (lx+1, ly+1))
            surf.blit(label, (lx, ly))


# ═══════════════════════════════════════════════════════════════════════════════
#  Enemy Subclasses
# ═══════════════════════════════════════════════════════════════════════════════

class Slime(Enemy):
    DETECTION_RANGE = 140
    ATTACK_RANGE    = 30
    ATTACK_DAMAGE   = 6
    ATTACK_COOL     = 70
    AGGRO_TYPE      = 'attack'   # only aggros when hit
    FLEE_HP_PCT     = 0.20       # flees at 20% HP
    LUMINOUS        = True       # glowing slime - visible in dark!

    def __init__(self, x, y, is_boss=False):
        super().__init__(x, y, "Slime", COL_SLIME, 22, 1.2, 'slime', is_boss)

    def _do_chase(self, player, gmap, projectiles):
        dx = player.cx - self.cx
        dy = player.cy - self.cy
        d  = math.hypot(dx, dy)
        if d > 0:
            perp   = (-dy/d, dx/d)
            wobble = math.sin(pygame.time.get_ticks() * 0.005) * 0.4
            self.try_move((dx/d + perp[0]*wobble) * self.speed,
                          (dy/d + perp[1]*wobble) * self.speed, gmap)
        self.animator.push_walk(self.facing)
        self._aggroed = True


class Bat(Enemy):
    DETECTION_RANGE = 200
    ATTACK_RANGE    = 28
    ATTACK_DAMAGE   = 5
    ATTACK_COOL     = 50
    FLEE_HP_PCT     = 0.15   # bats flee at low HP

    def __init__(self, x, y, is_boss=False):
        super().__init__(x, y, "Bat", COL_BAT, 16, 2.5, 'bat', is_boss)

    def _do_chase(self, player, gmap, projectiles):
        dx = player.cx - self.cx
        dy = player.cy - self.cy
        d  = math.hypot(dx, dy)
        if d > 0:
            angle = math.atan2(dy, dx) + self._rng.uniform(-0.6, 0.6)
            self.try_move(math.cos(angle)*self.speed,
                          math.sin(angle)*self.speed, gmap)
        self.animator.push_walk(self.facing)
        self._aggroed = True


class Spider(Enemy):
    DETECTION_RANGE = 160
    ATTACK_RANGE    = 32
    ATTACK_DAMAGE   = 8
    ATTACK_COOL     = 60
    RANGED_RANGE    = 120
    PROJ_SPEED      = 3
    PROJ_COLOR      = COL_WEB
    PROJ_DAMAGE     = 5
    FIGHT_TO_DEATH  = True   # spiders never back down

    def __init__(self, x, y, is_boss=False):
        super().__init__(x, y, "Spider", COL_SPIDER, 28, 1.8, 'spider', is_boss)
        if is_boss:
            self.name        = "Giant Spider"
            self.entity_type = 'giant_spider'
            self.animator    = Animator('giant_spider')


class Goblin(Enemy):
    DETECTION_RANGE = 190
    ATTACK_RANGE    = 30
    ATTACK_DAMAGE   = 10
    ATTACK_COOL     = 55
    DEAGGRO_DIST    = 300   # gives up if player escapes

    def __init__(self, x, y, is_boss=False):
        super().__init__(x, y, "Goblin", COL_GOBLIN, 32, 2.0, 'goblin', is_boss)


class Skeleton(Enemy):
    DETECTION_RANGE = 170
    ATTACK_RANGE    = 32
    ATTACK_DAMAGE   = 12
    ATTACK_COOL     = 65
    DEFENSE         = 2
    RANGED_RANGE    = 150
    PROJ_SPEED      = 5
    PROJ_COLOR      = COL_BONE
    PROJ_DAMAGE     = 8
    FIGHT_TO_DEATH  = True

    def __init__(self, x, y, is_boss=False):
        super().__init__(x, y, "Skeleton", COL_SKELETON, 35, 1.6,
                         'skeleton', is_boss)
        if is_boss: self.name = "Skeleton Lord"


class Ghost(Enemy):
    DETECTION_RANGE = 210
    ATTACK_RANGE    = 28
    ATTACK_DAMAGE   = 9
    ATTACK_COOL     = 55
    LUMINOUS        = True   # ghosts glow in darkness
    FIGHT_TO_DEATH  = True

    def __init__(self, x, y, is_boss=False):
        super().__init__(x, y, "Ghost", COL_GHOST, 25, 1.4, 'ghost', is_boss)

    def _is_ghost(self): return True

    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int,
             asset_mgr=None, brightness: int = 255):
        sx = int(self.x) - cam_x
        sy = int(self.y) - cam_y
        s  = self.SIZE

        sprite = None
        if asset_mgr is not None:
            sprite = asset_mgr.get_entity_surface(self.animator)

        # Ghosts are always at least partially visible
        ghost_alpha = max(80, min(200, brightness + 80))

        if sprite is not None:
            ghost_surf = sprite.copy()
            if sprite.get_size() != (s, s):
                ghost_surf = pygame.transform.scale(ghost_surf, (s, s))
            ghost_surf.set_alpha(ghost_alpha)
            surf.blit(ghost_surf, (sx, sy))
        else:
            gs = pygame.Surface((s, s), pygame.SRCALPHA)
            gs.fill((*self.color, ghost_alpha))
            surf.blit(gs, (sx, sy))
            pygame.draw.rect(surf, WHITE, (sx, sy, s, s), 1)

        bar_w = int(s * self.hp / self.max_hp)
        pygame.draw.rect(surf, DARK_RED, (sx, sy-6, s, 4))
        pygame.draw.rect(surf, GREEN,    (sx, sy-6, bar_w, 4))

        # Name
        f = _label_font(10)
        label = f.render(self.name, True, (200,220,255))
        lx = sx + s//2 - label.get_width()//2
        surf.blit(label, (lx, sy - 17))


class Troll(Enemy):
    DETECTION_RANGE = 150
    ATTACK_RANGE    = 38
    ATTACK_DAMAGE   = 18
    ATTACK_COOL     = 90
    DEFENSE         = 4
    FLEE_HP_PCT     = 0.10   # trolls barely flee
    DEAGGRO_DIST    = 400

    def __init__(self, x, y, is_boss=False):
        super().__init__(x, y, "Troll", COL_TROLL, 70, 1.0, 'troll', is_boss)
        if is_boss: self.name = "Stone Troll"


class Wolf(Enemy):
    DETECTION_RANGE = 220
    ATTACK_RANGE    = 30
    ATTACK_DAMAGE   = 11
    ATTACK_COOL     = 45
    DEAGGRO_DIST    = 350   # wolves give up if you outrun them

    def __init__(self, x, y, is_boss=False):
        super().__init__(x, y, "Wolf", COL_WOLF, 30, 3.2, 'wolf', is_boss)
        # Wolves are faster than player!


class Kelpie(Enemy):
    """Water monster - lives in rivers and lakes. Amphibious."""
    DETECTION_RANGE = 200
    ATTACK_RANGE    = 30
    ATTACK_DAMAGE   = 14
    ATTACK_COOL     = 55
    RANGED_RANGE    = 160
    PROJ_SPEED      = 5
    PROJ_COLOR      = COL_WATER_BOLT
    PROJ_DAMAGE     = 10
    FIGHT_TO_DEATH  = True

    def __init__(self, x, y, is_boss=False):
        super().__init__(x, y, "Kelpie", COL_KELPIE, 45, 2.4, 'kelpie', is_boss)

    def _is_water_walker(self): return True

    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int,
             asset_mgr=None, brightness: int = 255):
        # Kelpie is always visible near water
        super().draw(surf, cam_x, cam_y, asset_mgr, brightness=max(brightness, 80))


# ─── Factory ──────────────────────────────────────────────────────────────────
_ENEMY_CLASSES = {
    'slime':        Slime,
    'bat':          Bat,
    'spider':       Spider,
    'goblin':       Goblin,
    'skeleton':     Skeleton,
    'ghost':        Ghost,
    'troll':        Troll,
    'wolf':         Wolf,
    'giant_spider': Spider,
    'kelpie':       Kelpie,
}

def spawn_enemy(etype: str, tx: int, ty: int,
                is_boss: bool = False) -> Enemy:
    cls = _ENEMY_CLASSES.get(etype, Slime)
    px  = tx * TILE_SIZE + (TILE_SIZE - ENTITY_SIZE) // 2
    py  = ty * TILE_SIZE + (TILE_SIZE - ENTITY_SIZE) // 2
    return cls(px, py, is_boss=is_boss)
