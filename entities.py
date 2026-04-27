"""
Rune & Shadow - Entities v3
Player, Enemy subclasses, Projectiles.

v3 fixes & additions:
  - Aim mode toggle (TAB): mouse-aim vs pure autoaim
  - Unequip hotbar slot (U key in inventory or X in play)
  - Drop fix: item removed BEFORE GroundItem created (no duplication)
  - Swamp tiles slow the player
  - New biome enemies: Yeti, IceWraith, Scorpion, Mummy, SwampToad, WillOWisp
  - Boss drops use is_boss flag passed to roll_drops
"""
import math
import random
import pygame

from constants import *
from animation import Animator, State, Dir, FACING_TO_DIR
from items import (Inventory, make_item, roll_drops,
                   KNIFE, STAFF, SLING, CANDLE, SPELL_BASIC, STONE)

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

    def __init__(self, x, y, color, hp, entity_type='unknown'):
        self.x = float(x); self.y = float(y)
        self.color = color; self.hp = hp; self.max_hp = hp
        self.alive = True; self.speed = 1.5; self.facing = DIR_RIGHT
        self.entity_type = entity_type
        self.animator    = Animator(entity_type)

    @property
    def rect(self): return pygame.Rect(int(self.x), int(self.y), self.SIZE, self.SIZE)
    @property
    def cx(self): return self.x + self.SIZE / 2
    @property
    def cy(self): return self.y + self.SIZE / 2

    def dist_to(self, other):
        return math.hypot(self.cx - other.cx, self.cy - other.cy)

    def try_move(self, dx, dy, gmap, ghost=False, water_walker=False):
        sz = self.SIZE
        if dx != 0:
            nx = self.x + dx
            if ghost or not self._tile_hit(nx, self.y, sz, gmap, water_walker):
                self.x = nx
        if dy != 0:
            ny = self.y + dy
            if ghost or not self._tile_hit(self.x, ny, sz, gmap, water_walker):
                self.y = ny

    def _tile_hit(self, x, y, sz, gmap, water_walker=False):
        ts = TILE_SIZE
        for cx_, cy_ in [(x,y),(x+sz-1,y),(x,y+sz-1),(x+sz-1,y+sz-1)]:
            t = gmap.get(int(cx_//ts), int(cy_//ts))
            if water_walker:
                if not (tile_walkable(t) or tile_swimmable(t)): return True
            else:
                if not tile_walkable(t): return True
        mw = gmap.width*ts; mh = gmap.height*ts
        return x<0 or y<0 or x+sz>mw or y+sz>mh

    def take_damage(self, amount):
        actual = max(1, amount)
        self.hp -= actual
        if self.hp <= 0:
            self.hp = 0; self.alive = False
            self.animator.trigger_dead()
        else:
            self.animator.trigger_hurt()
        return actual

    def draw(self, surf, cam_x, cam_y, asset_mgr=None):
        sx = int(self.x)-cam_x; sy = int(self.y)-cam_y; s = self.SIZE
        if sx+s<0 or sx>surf.get_width() or sy+s<0 or sy>surf.get_height(): return
        sprite = asset_mgr.get_entity_surface(self.animator) if asset_mgr else None
        if sprite:
            surf.blit(sprite, (sx, sy))
        else:
            pygame.draw.rect(surf, self.color, (sx,sy,s,s))
            pygame.draw.rect(surf, BLACK, (sx,sy,s,s), 1)


# ═══════════════════════════════════════════════════════════════════════════════
#  Player
# ═══════════════════════════════════════════════════════════════════════════════

class Player(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, COL_PLAYER, PLAYER_START_HP, 'player')
        self.speed    = PLAYER_SPEED
        self.mana     = PLAYER_START_MANA
        self.max_mana = PLAYER_START_MANA
        self.defense  = 0

        self.inventory = Inventory()
        self.hotbar    = [None] * HOTBAR_SLOTS
        self.equipped  = 0

        self.attack_cooldown = 0
        self.iframes         = 0
        self.attack_effect   = None
        self.light_radius    = 6
        self.is_swimming     = False
        self.is_slowed       = False

        # Aim
        self.mouse_world_x = x; self.mouse_world_y = y
        self.aim_dir  = (1.0, 0.0)
        self.aim_mode = 'mouse'   # 'mouse' or 'auto'

        self._init_inventory()

    def _init_inventory(self):
        for it, cnt in [(KNIFE,1),(STAFF,1),(SLING,1),(CANDLE,1),(SPELL_BASIC,1)]:
            self.inventory.add(it, cnt)
        self.inventory.add(make_item('stone'), 15)
        self.inventory.add(make_item('mushroom'), 3)
        self.inventory.add(make_item('herb'), 2)
        self.hotbar = ['knife','staff','sling','candle','spell_basic',None,None,None]

    def equipped_item(self):
        iid = self.hotbar[self.equipped]
        if iid and self.inventory.has(iid):
            from items import ITEMS
            return ITEMS.get(iid)
        return None

    def cycle_hotbar(self, d):
        self.equipped = (self.equipped + d) % HOTBAR_SLOTS

    def unequip_slot(self, slot=None):
        """Clear a hotbar slot (default: current)."""
        idx = slot if slot is not None else self.equipped
        self.hotbar[idx] = None

    def update_light(self):
        base = 3
        from items import ITEMS
        for iid in self.hotbar:
            if iid:
                it = ITEMS.get(iid)
                if it and it.itype == IT_LIGHT:
                    base = max(base, it.light_radius)
        self.light_radius = base

    def toggle_aim_mode(self):
        self.aim_mode = 'auto' if self.aim_mode == 'mouse' else 'mouse'

    def set_mouse_world(self, mx, my, cam_x, cam_y):
        self.mouse_world_x = mx + cam_x
        self.mouse_world_y = my + cam_y

    def compute_aim(self, enemies):
        if self.aim_mode == 'mouse':
            dx = self.mouse_world_x - self.cx
            dy = self.mouse_world_y - self.cy
            d  = math.hypot(dx, dy)
            if d > 0:
                self.aim_dir = (dx/d, dy/d)
        # Autoaim snap: always try within radius
        best_e = None; best_dot = 0.3 if self.aim_mode == 'mouse' else -1.0
        for e in enemies:
            if not e.alive: continue
            ed = math.hypot(e.cx-self.cx, e.cy-self.cy)
            if ed > AUTOAIM_RADIUS: continue
            if ed == 0: continue
            edx,edy = (e.cx-self.cx)/ed, (e.cy-self.cy)/ed
            dot = edx*self.aim_dir[0] + edy*self.aim_dir[1]
            if dot > best_dot:
                best_dot = dot; best_e = e
        if best_e is not None:
            dx2 = best_e.cx-self.cx; dy2 = best_e.cy-self.cy
            d2  = math.hypot(dx2,dy2)
            if d2 > 0:
                self.aim_dir = (dx2/d2, dy2/d2)

    def attack(self, gmap, enemies, projectiles, messages):
        if self.attack_cooldown > 0: return
        item = self.equipped_item()
        if item is None:
            messages.append(("Nothing equipped!", YELLOW)); return
        self.animator.trigger_attack(self.facing)
        if item.itype == IT_WEAPON:
            self._melee(item, gmap, enemies, messages)
        elif item.itype == IT_RANGED:
            self._ranged(item, projectiles, messages)
        elif item.itype == IT_MAGIC:
            self._magic(item, projectiles, messages)
        elif item.itype == IT_LIGHT:
            messages.append(("You hold up the light.", YELLOW)); return
        self.attack_cooldown = item.cooldown if item else 20

    def _melee(self, item, gmap, enemies, messages):
        fx,fy = self.facing
        reach = item.attack_range
        ax = self.cx + fx*(self.SIZE//2+4)
        ay = self.cy + fy*(self.SIZE//2+4)
        atk = pygame.Rect(ax-reach//2, ay-reach//2, reach, reach)
        self.attack_effect = AttackEffect(atk, YELLOW, 10)
        hit = False
        for e in enemies:
            if e.alive and atk.colliderect(e.rect):
                dmg = max(1, item.damage - e.defense)
                e.take_damage(dmg)
                if hasattr(e,'on_attacked'): e.on_attacked()
                hit = True
                messages.append((f"Hit {e.name} for {dmg}!", WHITE))
        if item.tool_tag:
            tx = int((ax+fx*16)//TILE_SIZE); ty = int((ay+fy*16)//TILE_SIZE)
            if gmap.in_bounds(tx,ty):
                t = gmap.get(tx,ty)
                if tile_tool(t)==item.tool_tag:
                    floor = T_GRASS if not gmap.is_dungeon else T_FLOOR
                    gmap.set(tx,ty,floor)
                    messages.append(("Destroyed!", ORANGE))
        if not hit and not item.tool_tag:
            messages.append(("Whoosh!", GRAY))

    def _ranged(self, item, projectiles, messages):
        if not self.inventory.has(item.ammo_type):
            messages.append((f"No {item.ammo_type}s!", RED)); return
        self.inventory.remove(item.ammo_type,1)
        projectiles.append(Projectile(self.cx,self.cy,self.aim_dir,
                                      item.proj_speed,item.damage,item.proj_color,
                                      owner='player',ammo_type=item.ammo_type))
        messages.append((f"Fired {item.ammo_type}.",WHITE))

    def _magic(self, item, projectiles, messages):
        if self.mana < item.mana_cost:
            messages.append(("Not enough mana!",BLUE)); return
        self.mana -= item.mana_cost
        projectiles.append(Projectile(self.cx,self.cy,self.aim_dir,
                                      item.proj_speed,item.damage,item.proj_color,
                                      owner='player',spell=item.spell_effect))
        messages.append((f"Cast {item.name}!",CYAN))

    def use_item(self, iid, messages):
        from items import ITEMS
        it = ITEMS.get(iid)
        if it is None or not self.inventory.has(iid): return False
        if it.itype == IT_CONSUMABLE:
            if it.hp_restore:
                gained = min(it.hp_restore, self.max_hp-self.hp)
                self.hp += gained
                messages.append((f"+{gained} HP.",GREEN))
            if it.mp_restore:
                gained = min(it.mp_restore, self.max_mana-self.mana)
                self.mana += gained
                messages.append((f"+{gained} MP.",BLUE))
            self.inventory.remove(iid,1)
            return True
        return False

    def take_damage(self, amount, difficulty=DIFFICULTY_NORMAL):
        if self.iframes > 0: return 0
        mult   = DIFFICULTY_DMG_MULT.get(difficulty, 1.0)
        actual = max(1, int(max(1, amount-self.defense) * mult))
        self.hp -= actual
        if self.hp <= 0:
            self.hp=0; self.alive=False; self.animator.trigger_dead()
        else:
            self.animator.trigger_hurt()
        self.iframes = PLAYER_IFRAMES
        return actual

    def update(self, keys, gmap, enemies, projectiles, messages,
               cam_x=0, cam_y=0):
        dx=dy=0.0
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: dx -= self.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: dx += self.speed
        if keys[pygame.K_UP]    or keys[pygame.K_w]: dy -= self.speed
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: dy += self.speed
        moving = dx!=0 or dy!=0

        if moving:
            if   dx<0: self.facing=DIR_LEFT
            elif dx>0: self.facing=DIR_RIGHT
            elif dy<0: self.facing=DIR_UP
            else:      self.facing=DIR_DOWN
            if dx and dy: dx*=0.7071; dy*=0.7071

            ts = TILE_SIZE; sz = self.SIZE
            def corner_tiles(nx,ny):
                return [gmap.get(int(cx_//ts),int(cy_//ts))
                        for cx_,cy_ in [(nx,ny),(nx+sz-1,ny),(nx,ny+sz-1),(nx+sz-1,ny+sz-1)]]

            nx,ny = self.x+dx, self.y+dy
            cts   = corner_tiles(nx,ny)
            any_swim  = any(tile_swimmable(t) for t in cts)
            all_ok    = all(tile_walkable(t) or tile_swimmable(t) for t in cts)
            any_slow  = any(tile_slow(t) for t in cts)

            if any_swim and all_ok:
                self.is_swimming = True
                dx *= SWIM_SPEED_MULT; dy *= SWIM_SPEED_MULT
                self._swim_move(dx, dy, gmap)
            else:
                self.is_swimming = False
                if any_slow:
                    dx *= SLOW_SPEED_MULT; dy *= SLOW_SPEED_MULT
                    self.is_slowed = True
                else:
                    self.is_slowed = False
                self.try_move(dx,dy,gmap)

            ptx=int(self.cx//TILE_SIZE); pty=int(self.cy//TILE_SIZE)
            self.is_swimming = tile_swimmable(gmap.get(ptx,pty))
            self.animator.push_walk(self.facing)
        else:
            ptx=int(self.cx//TILE_SIZE); pty=int(self.cy//TILE_SIZE)
            self.is_swimming = tile_swimmable(gmap.get(ptx,pty))
            self.is_slowed   = tile_slow(gmap.get(ptx,pty))
            self.animator.push_idle(self.facing)

        self.animator.tick()
        if self.attack_cooldown>0: self.attack_cooldown-=1
        if self.iframes>0:         self.iframes-=1
        if self.attack_effect:
            self.attack_effect.update()
            if self.attack_effect.done: self.attack_effect=None
        if self.mana < self.max_mana and random.random()<0.004:
            self.mana = min(self.max_mana, self.mana+1)
        self.update_light()
        mx,my = pygame.mouse.get_pos()
        self.set_mouse_world(mx,my,cam_x,cam_y)
        self.compute_aim(enemies)

    def _swim_move(self, dx, dy, gmap):
        ts=TILE_SIZE; sz=self.SIZE
        mw=gmap.width*ts; mh=gmap.height*ts
        def ok(x,y):
            for cx_,cy_ in [(x,y),(x+sz-1,y),(x,y+sz-1),(x+sz-1,y+sz-1)]:
                t=gmap.get(int(cx_//ts),int(cy_//ts))
                if not (tile_walkable(t) or tile_swimmable(t)): return False
            return 0<=x and 0<=y and x+sz<=mw and y+sz<=mh
        if dx and ok(self.x+dx, self.y): self.x+=dx
        if dy and ok(self.x, self.y+dy): self.y+=dy

    def draw(self, surf, cam_x, cam_y, asset_mgr=None):
        sx=int(self.x)-cam_x; sy=int(self.y)-cam_y
        sprite = asset_mgr.get_entity_surface(self.animator) if asset_mgr else None
        if sprite:
            spr = sprite.copy()
            if self.is_swimming:
                spr.fill((0,80,180,60),special_flags=pygame.BLEND_RGBA_ADD)
            elif self.is_slowed:
                spr.fill((30,80,30,40),special_flags=pygame.BLEND_RGBA_ADD)
            if self.iframes>0 and (self.iframes//4)%2==1:
                spr.fill((255,255,255,120),special_flags=pygame.BLEND_RGBA_ADD)
            surf.blit(spr,(sx,sy))
        else:
            col = WHITE if (self.iframes>0 and (self.iframes//4)%2==1) else self.color
            if self.is_swimming: col=(max(0,col[0]-60),max(0,col[1]-20),min(255,col[2]+80))
            if self.is_slowed:   col=(max(0,col[0]-20),min(255,col[1]+40),max(0,col[2]-20))
            pygame.draw.rect(surf,col,(sx,sy,self.SIZE,self.SIZE))
            pygame.draw.rect(surf,BLACK,(sx,sy,self.SIZE,self.SIZE),1)
            fx,fy=self.facing
            ix=sx+self.SIZE//2+fx*(self.SIZE//2-4)-3
            iy=sy+self.SIZE//2+fy*(self.SIZE//2-4)-3
            pygame.draw.rect(surf,BLACK,(ix,iy,6,6))
        if self.attack_effect:
            self.attack_effect.draw(surf,cam_x,cam_y,asset_mgr)
        # Aim indicator
        ax=sx+self.SIZE//2+int(self.aim_dir[0]*14)
        ay=sy+self.SIZE//2+int(self.aim_dir[1]*14)
        col_aim = YELLOW if self.aim_mode=='mouse' else CYAN
        pygame.draw.circle(surf,col_aim,(ax,ay),3)


# ═══════════════════════════════════════════════════════════════════════════════
#  Attack Effect
# ═══════════════════════════════════════════════════════════════════════════════

class AttackEffect:
    def __init__(self, rect, color, duration, fx_name='attack_slash'):
        self.rect=rect; self.color=color; self.duration=duration
        self.timer=duration; self.done=False; self.fx_name=fx_name
    def update(self):
        self.timer-=1
        if self.timer<=0: self.done=True
    def draw(self, surf, cam_x, cam_y, asset_mgr=None):
        rx=self.rect.x-cam_x; ry=self.rect.y-cam_y
        alpha=int(200*self.timer/max(1,self.duration))
        r=pygame.Rect(rx,ry,self.rect.w,self.rect.h)
        s=pygame.Surface((r.w,r.h),pygame.SRCALPHA)
        s.fill((*self.color[:3],alpha))
        surf.blit(s,(r.x,r.y))


# ═══════════════════════════════════════════════════════════════════════════════
#  Projectile
# ═══════════════════════════════════════════════════════════════════════════════

class Projectile:
    SIZE=8
    def __init__(self,x,y,direction,speed,damage,color,owner='player',
                 ammo_type=None,spell=None):
        self.x=float(x)-self.SIZE/2; self.y=float(y)-self.SIZE/2
        self.dx=direction[0]*speed; self.dy=direction[1]*speed
        self.damage=damage; self.color=color; self.owner=owner
        self.ammo_type=ammo_type; self.spell=spell
        self.alive=True; self.lifetime=120
        self.kind=spell if spell else (ammo_type if ammo_type else 'arcane')
    @property
    def rect(self): return pygame.Rect(int(self.x),int(self.y),self.SIZE,self.SIZE)
    def update(self, gmap, player, enemies, messages):
        if not self.alive: return
        self.lifetime-=1
        if self.lifetime<=0: self.alive=False; return
        self.x+=self.dx; self.y+=self.dy
        tx=int((self.x+self.SIZE/2)//TILE_SIZE); ty=int((self.y+self.SIZE/2)//TILE_SIZE)
        t=gmap.get(tx,ty)
        if not tile_walkable(t) and not tile_swimmable(t): self.alive=False; return
        r=self.rect
        if self.owner=='player':
            for e in enemies:
                if e.alive and r.colliderect(e.rect):
                    dmg=e.take_damage(self.damage)
                    if hasattr(e,'on_attacked'): e.on_attacked()
                    messages.append((f"Hit {e.name} for {dmg}!",WHITE))
                    self.alive=False
                    if self.spell=='fireball':
                        for e2 in enemies:
                            if e2 is not e and e2.alive and math.hypot(e.cx-e2.cx,e.cy-e2.cy)<TILE_SIZE*1.5:
                                e2.take_damage(self.damage//2)
                    return
        elif self.owner=='enemy':
            if r.colliderect(player.rect):
                dmg=player.take_damage(self.damage)
                if dmg>0: messages.append((f"You took {dmg} damage!",RED))
                self.alive=False
    def draw(self, surf, cam_x, cam_y, asset_mgr=None):
        sx=int(self.x)-cam_x; sy=int(self.y)-cam_y
        pygame.draw.rect(surf,self.color,(sx,sy,self.SIZE,self.SIZE))


# ═══════════════════════════════════════════════════════════════════════════════
#  Enemy Base
# ═══════════════════════════════════════════════════════════════════════════════

class Enemy(Entity):
    DETECTION_RANGE=180; ATTACK_RANGE=34; ATTACK_DAMAGE=8; ATTACK_COOL=60
    DEFENSE=0; RANGED_RANGE=0; PROJ_SPEED=4; PROJ_COLOR=RED; PROJ_DAMAGE=6
    AGGRO_TYPE='sight'; FLEE_HP_PCT=0.0; DEAGGRO_DIST=0
    FIGHT_TO_DEATH=False; LUMINOUS=False

    def __init__(self, x, y, name, color, hp, speed, etype, is_boss=False):
        super().__init__(x,y,color,hp*(3 if is_boss else 1),etype)
        self.name=name; self.speed=speed; self.etype=etype
        self.is_boss=is_boss; self.defense=self.DEFENSE
        self.SIZE=ENTITY_SIZE*2 if is_boss else ENTITY_SIZE
        self._state='wander'; self._wander_dir=(0.0,0.0); self._wander_timer=0
        self._attack_cool=0; self._stun_timer=0; self._proj_cool=0
        self._rng=random.Random(id(self))
        self._aggroed=False; self._aggro_src='none'

    def on_attacked(self):
        if self.AGGRO_TYPE in ('attack','sight'):
            self._aggroed=True; self._aggro_src='attack'; self._state='chase'

    def update(self, player, gmap, projectiles, messages):
        if not self.alive: return
        dist=self.dist_to(player)
        if self._stun_timer>0:
            self._stun_timer-=1; self._state='stunned'
        else:
            should_aggro=(self.AGGRO_TYPE=='sight' and dist<self.DETECTION_RANGE) or self._aggroed
            low_hp=(self.hp/self.max_hp)<self.FLEE_HP_PCT
            fleeing=low_hp and not self.FIGHT_TO_DEATH and self.FLEE_HP_PCT>0
            if fleeing:
                self._state='flee'
            elif should_aggro:
                if dist<self.ATTACK_RANGE: self._state='attack'
                else:
                    self._state='chase'
                    if self.DEAGGRO_DIST>0 and dist>self.DEAGGRO_DIST and not self.FIGHT_TO_DEATH and self._aggro_src=='sight':
                        self._aggroed=False; self._state='wander'
            else:
                if self._state in ('chase','attack'): self._state='wander'
        if self._attack_cool>0: self._attack_cool-=1
        if self._proj_cool>0:   self._proj_cool-=1
        {'wander':self._wander,'chase':self._chase,'attack':self._do_attack,
         'flee':self._flee,'stunned':lambda *a:self.animator.push_idle(self.facing)
        }.get(self._state,self._wander)(player,gmap,projectiles,messages) \
        if self._state in ('chase','attack','flee','stunned') else \
        self._wander(gmap)
        self.animator.tick()

    def _wander(self, gmap=None):
        self._wander_timer-=1
        if self._wander_timer<=0:
            angle=self._rng.uniform(0,2*math.pi)
            self._wander_dir=(math.cos(angle),math.sin(angle))
            self._wander_timer=self._rng.randint(40,100)
        dx=self._wander_dir[0]*self.speed*0.4; dy=self._wander_dir[1]*self.speed*0.4
        self.try_move(dx,dy,gmap,ghost=self._is_ghost(),water_walker=self._is_water_walker())
        if abs(dx)>abs(dy): self.facing=DIR_RIGHT if dx>0 else DIR_LEFT
        elif dy!=0: self.facing=DIR_DOWN if dy>0 else DIR_UP
        self.animator.push_walk(self.facing)

    def _chase(self, player, gmap, projectiles, messages=None):
        dx=player.cx-self.cx; dy=player.cy-self.cy; d=math.hypot(dx,dy)
        if d>0:
            self.try_move(dx/d*self.speed,dy/d*self.speed,gmap,
                          ghost=self._is_ghost(),water_walker=self._is_water_walker())
            self.facing=DIR_RIGHT if dx>0 else (DIR_LEFT if dx<0 else (DIR_DOWN if dy>0 else DIR_UP))
            self.animator.push_walk(self.facing)
            self._aggroed=True
        if self.RANGED_RANGE and d<self.RANGED_RANGE and self._proj_cool==0:
            self._fire_proj(player,projectiles)

    def _do_attack(self, player, gmap, projectiles, messages):
        self.animator.push_idle(self.facing); self._aggroed=True
        if self._attack_cool==0:
            dmg=player.take_damage(self.ATTACK_DAMAGE)
            if dmg>0: messages.append((f"{self.name} hits you for {dmg}!",RED))
            self._attack_cool=self.ATTACK_COOL

    def _flee(self, player, gmap, projectiles=None, messages=None):
        dx=self.cx-player.cx; dy=self.cy-player.cy; d=math.hypot(dx,dy)
        if d>0:
            self.try_move(dx/d*self.speed*1.2,dy/d*self.speed*1.2,gmap,
                          ghost=self._is_ghost(),water_walker=self._is_water_walker())
        self.animator.push_walk(self.facing)

    def _fire_proj(self, player, projectiles):
        dx=player.cx-self.cx; dy=player.cy-self.cy; d=math.hypot(dx,dy)
        if d==0: return
        projectiles.append(Projectile(self.cx,self.cy,(dx/d,dy/d),
                                      self.PROJ_SPEED,self.PROJ_DAMAGE,
                                      self.PROJ_COLOR,owner='enemy'))
        self._proj_cool=90

    def _is_ghost(self): return False
    def _is_water_walker(self): return False

    def get_drops(self, rng):
        return roll_drops(self.etype, rng, is_boss=self.is_boss)

    def draw(self, surf, cam_x, cam_y, asset_mgr=None, brightness=255):
        sx=int(self.x)-cam_x; sy=int(self.y)-cam_y; s=self.SIZE
        if sx+s<0 or sx>surf.get_width() or sy+s<0 or sy>surf.get_height(): return
        luminous=self.LUMINOUS or self.is_boss
        if brightness<40 and not luminous: return
        sprite=asset_mgr.get_entity_surface(self.animator) if asset_mgr else None
        alpha=max(80,min(255,brightness*2)) if (luminous and brightness<128) else 255
        if sprite:
            sp=sprite if sprite.get_size()==(s,s) else pygame.transform.scale(sprite,(s,s))
            if alpha<255: sp2=sp.copy(); sp2.set_alpha(alpha); surf.blit(sp2,(sx,sy))
            else: surf.blit(sp,(sx,sy))
        else:
            col=tuple(min(255,c+40) for c in self.color) if self.is_boss else self.color
            if alpha<255:
                ss=pygame.Surface((s,s),pygame.SRCALPHA); ss.fill((*col,alpha)); surf.blit(ss,(sx,sy))
            else:
                pygame.draw.rect(surf,col,(sx,sy,s,s))
                pygame.draw.rect(surf,BLACK,(sx,sy,s,s),1)
        bar_w=int(s*self.hp/self.max_hp)
        pygame.draw.rect(surf,DARK_RED,(sx,sy-6,s,4))
        pygame.draw.rect(surf,GREEN,(sx,sy-6,bar_w,4))
        if brightness>=50 or luminous:
            f=_label_font(10)
            lbl=f.render(self.name,True,WHITE); shd=f.render(self.name,True,BLACK)
            lx=sx+s//2-lbl.get_width()//2; ly=sy-17
            surf.blit(shd,(lx+1,ly+1)); surf.blit(lbl,(lx,ly))


# ═══════════════════════════════════════════════════════════════════════════════
#  Concrete Enemies – original biome
# ═══════════════════════════════════════════════════════════════════════════════

class Slime(Enemy):
    DETECTION_RANGE=140; ATTACK_RANGE=30; ATTACK_DAMAGE=6; ATTACK_COOL=70
    AGGRO_TYPE='attack'; FLEE_HP_PCT=0.20; LUMINOUS=True
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Slime",COL_SLIME,22,1.2,'slime',is_boss)

class Bat(Enemy):
    DETECTION_RANGE=200; ATTACK_RANGE=28; ATTACK_DAMAGE=5; ATTACK_COOL=50
    FLEE_HP_PCT=0.15
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Bat",COL_BAT,16,2.5,'bat',is_boss)
    def _chase(self,player,gmap,projectiles,messages=None):
        dx=player.cx-self.cx; dy=player.cy-self.cy; d=math.hypot(dx,dy)
        if d>0:
            angle=math.atan2(dy,dx)+self._rng.uniform(-0.6,0.6)
            self.try_move(math.cos(angle)*self.speed,math.sin(angle)*self.speed,gmap)
        self.animator.push_walk(self.facing); self._aggroed=True

class Spider(Enemy):
    DETECTION_RANGE=160; ATTACK_RANGE=32; ATTACK_DAMAGE=8; ATTACK_COOL=60
    RANGED_RANGE=120; PROJ_SPEED=3; PROJ_COLOR=COL_WEB; PROJ_DAMAGE=5
    FIGHT_TO_DEATH=True
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Giant Spider" if is_boss else "Spider",
                         COL_SPIDER,28,1.8,'giant_spider' if is_boss else 'spider',is_boss)

class Goblin(Enemy):
    DETECTION_RANGE=190; ATTACK_RANGE=30; ATTACK_DAMAGE=10; ATTACK_COOL=55
    DEAGGRO_DIST=300
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Goblin",COL_GOBLIN,32,2.0,'goblin',is_boss)

class Skeleton(Enemy):
    DETECTION_RANGE=170; ATTACK_RANGE=32; ATTACK_DAMAGE=12; ATTACK_COOL=65
    DEFENSE=2; RANGED_RANGE=150; PROJ_SPEED=5; PROJ_COLOR=COL_BONE; PROJ_DAMAGE=8
    FIGHT_TO_DEATH=True
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Skeleton Lord" if is_boss else "Skeleton",
                         COL_SKELETON,35,1.6,'skeleton',is_boss)

class Ghost(Enemy):
    DETECTION_RANGE=210; ATTACK_RANGE=28; ATTACK_DAMAGE=9; ATTACK_COOL=55
    LUMINOUS=True; FIGHT_TO_DEATH=True
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Ghost",COL_GHOST,25,1.4,'ghost',is_boss)
    def _is_ghost(self): return True
    def draw(self, surf, cam_x, cam_y, asset_mgr=None, brightness=255):
        sx=int(self.x)-cam_x; sy=int(self.y)-cam_y; s=self.SIZE
        alpha=max(80,min(200,brightness+80))
        sprite=asset_mgr.get_entity_surface(self.animator) if asset_mgr else None
        if sprite:
            sp=sprite.copy(); sp.set_alpha(alpha); surf.blit(sp,(sx,sy))
        else:
            gs=pygame.Surface((s,s),pygame.SRCALPHA); gs.fill((*self.color,alpha))
            surf.blit(gs,(sx,sy)); pygame.draw.rect(surf,WHITE,(sx,sy,s,s),1)
        bar_w=int(s*self.hp/self.max_hp)
        pygame.draw.rect(surf,DARK_RED,(sx,sy-6,s,4))
        pygame.draw.rect(surf,GREEN,(sx,sy-6,bar_w,4))
        f=_label_font(10); lbl=f.render(self.name,True,(200,220,255))
        surf.blit(lbl,(sx+s//2-lbl.get_width()//2,sy-17))

class Troll(Enemy):
    DETECTION_RANGE=150; ATTACK_RANGE=38; ATTACK_DAMAGE=18; ATTACK_COOL=90
    DEFENSE=4; FLEE_HP_PCT=0.10; DEAGGRO_DIST=400
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Stone Troll" if is_boss else "Troll",
                         COL_TROLL,70,1.0,'troll',is_boss)

class Wolf(Enemy):
    DETECTION_RANGE=220; ATTACK_RANGE=30; ATTACK_DAMAGE=11; ATTACK_COOL=45
    DEAGGRO_DIST=350
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Wolf",COL_WOLF,30,3.2,'wolf',is_boss)

class Kelpie(Enemy):
    DETECTION_RANGE=200; ATTACK_RANGE=30; ATTACK_DAMAGE=14; ATTACK_COOL=55
    RANGED_RANGE=160; PROJ_SPEED=5; PROJ_COLOR=COL_WATER_BOLT; PROJ_DAMAGE=10
    FIGHT_TO_DEATH=True
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Kelpie",COL_KELPIE,45,2.4,'kelpie',is_boss)
    def _is_water_walker(self): return True

# ═══════════════════════════════════════════════════════════════════════════════
#  New Biome Enemies
# ═══════════════════════════════════════════════════════════════════════════════

class Yeti(Enemy):
    DETECTION_RANGE=170; ATTACK_RANGE=40; ATTACK_DAMAGE=20; ATTACK_COOL=80
    DEFENSE=3; FIGHT_TO_DEATH=True
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Elder Yeti" if is_boss else "Yeti",
                         COL_YETI,60,1.3,'yeti',is_boss)

class IceWraith(Enemy):
    DETECTION_RANGE=220; ATTACK_RANGE=30; ATTACK_DAMAGE=10; ATTACK_COOL=50
    RANGED_RANGE=180; PROJ_SPEED=6; PROJ_COLOR=COL_ICE_BOLT; PROJ_DAMAGE=12
    LUMINOUS=True; FIGHT_TO_DEATH=True
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Ice Wraith",COL_ICE_WRAITH,30,1.8,'ice_wraith',is_boss)
    def _is_ghost(self): return True

class Scorpion(Enemy):
    DETECTION_RANGE=160; ATTACK_RANGE=32; ATTACK_DAMAGE=14; ATTACK_COOL=55
    RANGED_RANGE=140; PROJ_SPEED=5; PROJ_COLOR=COL_POISON; PROJ_DAMAGE=9
    FIGHT_TO_DEATH=True
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Giant Scorpion" if is_boss else "Scorpion",
                         COL_SCORPION,38,1.9,'scorpion',is_boss)

class Mummy(Enemy):
    DETECTION_RANGE=150; ATTACK_RANGE=34; ATTACK_DAMAGE=15; ATTACK_COOL=75
    DEFENSE=3; AGGRO_TYPE='attack'; FIGHT_TO_DEATH=True
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Mummy Lord" if is_boss else "Mummy",
                         COL_MUMMY,50,1.1,'mummy',is_boss)

class SwampToad(Enemy):
    DETECTION_RANGE=140; ATTACK_RANGE=30; ATTACK_DAMAGE=8; ATTACK_COOL=65
    RANGED_RANGE=120; PROJ_SPEED=4; PROJ_COLOR=COL_POISON; PROJ_DAMAGE=6
    FLEE_HP_PCT=0.25; AGGRO_TYPE='attack'
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Swamp Toad",COL_SWAMP_TOAD,28,1.5,'swamp_toad',is_boss)
    def _is_water_walker(self): return True

class WillOWisp(Enemy):
    DETECTION_RANGE=240; ATTACK_RANGE=24; ATTACK_DAMAGE=7; ATTACK_COOL=45
    LUMINOUS=True; FIGHT_TO_DEATH=True
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Will-o'-Wisp",COL_WILL_O,20,2.2,'will_o',is_boss)
    def _is_ghost(self): return True
    def draw(self, surf, cam_x, cam_y, asset_mgr=None, brightness=255):
        sx=int(self.x)-cam_x; sy=int(self.y)-cam_y; s=self.SIZE
        pulse=abs(math.sin(pygame.time.get_ticks()*0.003))*80+80
        gs=pygame.Surface((s,s),pygame.SRCALPHA)
        gs.fill((*self.color,int(pulse))); surf.blit(gs,(sx,sy))
        bar_w=int(s*self.hp/self.max_hp)
        pygame.draw.rect(surf,DARK_RED,(sx,sy-6,s,4))
        pygame.draw.rect(surf,GREEN,(sx,sy-6,bar_w,4))


# ─── Factory ──────────────────────────────────────────────────────────────────
_ENEMY_CLASSES = {
    'slime':'Slime','bat':'Bat','spider':'Spider','goblin':'Goblin',
    'skeleton':'Skeleton','ghost':'Ghost','troll':'Troll','wolf':'Wolf',
    'giant_spider':'Spider','kelpie':'Kelpie',
    'yeti':'Yeti','ice_wraith':'IceWraith','scorpion':'Scorpion',
    'mummy':'Mummy','swamp_toad':'SwampToad','will_o':'WillOWisp',
}
_CLS_MAP = {
    'Slime':Slime,'Bat':Bat,'Spider':Spider,'Goblin':Goblin,'Skeleton':Skeleton,
    'Ghost':Ghost,'Troll':Troll,'Wolf':Wolf,'Kelpie':Kelpie,'Yeti':Yeti,
    'IceWraith':IceWraith,'Scorpion':Scorpion,'Mummy':Mummy,
    'SwampToad':SwampToad,'WillOWisp':WillOWisp,
}

def spawn_enemy(etype, tx, ty, is_boss=False):
    cls_name = _ENEMY_CLASSES.get(etype, 'Slime')
    cls = _CLS_MAP[cls_name]
    px = tx*TILE_SIZE + (TILE_SIZE-ENTITY_SIZE)//2
    py = ty*TILE_SIZE + (TILE_SIZE-ENTITY_SIZE)//2
    return cls(px, py, is_boss=is_boss)
