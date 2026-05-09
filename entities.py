"""
Rune & Shadow - Entities v4
v4 changes:
  - Player.update() takes input_state dict instead of raw pygame keys
  - Mouse aim only when aim_mode=='mouse' AND mouse_pos provided
  - Auto-aim uses facing direction as seed when no enemies nearby
  - unequip_slot(), toggle_aim_mode() unchanged
  - All 16 enemy types unchanged
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
        self.x=float(x); self.y=float(y); self.color=color
        self.hp=hp; self.max_hp=hp; self.alive=True
        self.speed=1.5; self.facing=DIR_RIGHT
        self.entity_type=entity_type; self.animator=Animator(entity_type)

    @property
    def rect(self): return pygame.Rect(int(self.x),int(self.y),self.SIZE,self.SIZE)
    @property
    def cx(self): return self.x+self.SIZE/2
    @property
    def cy(self): return self.y+self.SIZE/2

    def dist_to(self, other): return math.hypot(self.cx-other.cx, self.cy-other.cy)

    def try_move(self, dx, dy, gmap, ghost=False, water_walker=False):
        sz=self.SIZE
        # Clamp to map bounds (prevents ghosts wandering off-edge)
        mw = gmap.width  * TILE_SIZE; mh = gmap.height * TILE_SIZE
        if dx!=0:
            nx=max(0, min(self.x+dx, mw-sz-1))
            if ghost or not self._tile_hit(nx,self.y,sz,gmap,water_walker): self.x=nx
        if dy!=0:
            ny=max(0, min(self.y+dy, mh-sz-1))
            if ghost or not self._tile_hit(self.x,ny,sz,gmap,water_walker): self.y=ny

    def _tile_hit(self, x, y, sz, gmap, water_walker=False):
        ts=TILE_SIZE
        for cx_,cy_ in [(x,y),(x+sz-1,y),(x,y+sz-1),(x+sz-1,y+sz-1)]:
            t=gmap.get(int(cx_//ts),int(cy_//ts))
            if water_walker:
                if not(tile_walkable(t) or tile_swimmable(t)): return True
            else:
                if not tile_walkable(t): return True
        mw=gmap.width*ts; mh=gmap.height*ts
        return x<0 or y<0 or x+sz>mw or y+sz>mh

    def take_damage(self, amount):
        actual=max(1,amount); self.hp-=actual
        if self.hp<=0: self.hp=0; self.alive=False; self.animator.trigger_dead()
        else: self.animator.trigger_hurt()
        return actual

    def draw(self, surf, cam_x, cam_y, asset_mgr=None, brightness=255):
        sx=int(self.x)-cam_x; sy=int(self.y)-cam_y; s=self.SIZE
        if sx+s<0 or sx>surf.get_width() or sy+s<0 or sy>surf.get_height(): return
        sprite=asset_mgr.get_entity_surface(self.animator) if asset_mgr else None
        if sprite: surf.blit(sprite,(sx,sy))
        else:
            pygame.draw.rect(surf,self.color,(sx,sy,s,s))
            pygame.draw.rect(surf,BLACK,(sx,sy,s,s),1)


# ═══════════════════════════════════════════════════════════════════════════════
#  Player
# ═══════════════════════════════════════════════════════════════════════════════
class Player(Entity):
    def __init__(self, x, y, player_idx=0):
        super().__init__(x,y,COL_PLAYER,PLAYER_START_HP,'player')
        self.player_idx  = player_idx
        self.speed       = PLAYER_SPEED
        self.mana        = PLAYER_START_MANA
        self.max_mana    = PLAYER_START_MANA
        self.defense     = 0
        self.inventory   = Inventory()
        self.hotbar      = [None]*HOTBAR_SLOTS
        self.equipped    = 0
        self.attack_cooldown=0; self.iframes=0
        self.attack_effect=None; self.light_radius=6
        self.is_swimming=False; self.is_slowed=False
        self.mouse_world_x=x; self.mouse_world_y=y
        self.aim_dir=(1.0,0.0); self.aim_mode='auto'  # default auto; 1P can toggle
        # v5: ghost / death state
        self.is_ghost    = False   # True when dead in 2P mode – can move, not attack
        self.death_x     = None    # pixel coords of death, for body rendering
        self.death_y     = None
        # v5: berserk buff
        self.berserk_frames = 0
        # boomerang: block re-throw while projectile is still in flight
        self._boomerang_in_flight = False
        # charm_spell: persistent flag checked by game._update() regardless of state
        self.charm_cast = False
        self._init_inventory()

    def _init_inventory(self):
        for it,cnt in [(KNIFE,1),(STAFF,1),(SLING,1),(CANDLE,1),(SPELL_BASIC,1)]:
            self.inventory.add(it,cnt)
        self.inventory.add(make_item('stone'),15)
        self.inventory.add(make_item('mushroom'),3)
        self.inventory.add(make_item('herb'),2)
        self.hotbar=['knife','staff','sling','candle','spell_basic',None,None,None]

    def equipped_item(self):
        # First sweep: clear any hotbar slots whose item is no longer owned
        from items import ITEMS as _ITEMS
        for i in range(HOTBAR_SLOTS):
            iid = self.hotbar[i]
            if iid and not self.inventory.has(iid):
                self.hotbar[i] = None
        iid = self.hotbar[self.equipped]
        if iid:
            return _ITEMS.get(iid)
        return None

    def cycle_hotbar(self, d): self.equipped=(self.equipped+d)%HOTBAR_SLOTS
    def unequip_slot(self, slot=None):
        idx=slot if slot is not None else self.equipped; self.hotbar[idx]=None
    def toggle_aim_mode(self):
        self.aim_mode='auto' if self.aim_mode=='mouse' else 'mouse'

    def update_light(self):
        base=3
        from items import ITEMS
        self.defense=0; speed_bonus=0.0
        for iid in self.hotbar:
            if iid and self.inventory.has(iid):   # only count items we actually own
                it=ITEMS.get(iid)
                if it:
                    if it.itype==IT_LIGHT: base=max(base,it.light_radius)
                    if it.itype==IT_ARMOR:
                        self.defense=max(self.defense,it.defense)
                        speed_bonus=max(speed_bonus,getattr(it,'speed_bonus',0.0))
        self.light_radius=base
        self._speed_bonus=speed_bonus

    def set_mouse_world(self, mx, my, cam_x, cam_y):
        self.mouse_world_x=mx+cam_x; self.mouse_world_y=my+cam_y

    def compute_aim(self, enemies, mouse_pos=None, cam_x=0, cam_y=0):
        """Compute aim_dir. mouse_pos=(mx,my) screen coords; None=use facing."""
        if self.aim_mode=='mouse' and mouse_pos is not None:
            self.set_mouse_world(mouse_pos[0],mouse_pos[1],cam_x,cam_y)
            dx=self.mouse_world_x-self.cx; dy=self.mouse_world_y-self.cy
            d=math.hypot(dx,dy)
            if d>0: self.aim_dir=(dx/d,dy/d)
        else:
            # Seed from facing direction for auto mode
            fx,fy=self.facing
            if fx!=0 or fy!=0: self.aim_dir=(float(fx),float(fy))

        # Autoaim snap to nearest enemy in radius (never target Pet or Princess)
        best_e=None
        best_dot=-1.0 if self.aim_mode=='auto' else 0.3
        for e in enemies:
            if isinstance(e, (Pet, Princess)): continue   # skip companions
            if not e.alive: continue
            ed=math.hypot(e.cx-self.cx,e.cy-self.cy)
            if ed>AUTOAIM_RADIUS or ed==0: continue
            edx,edy=(e.cx-self.cx)/ed,(e.cy-self.cy)/ed
            dot=edx*self.aim_dir[0]+edy*self.aim_dir[1]
            if dot>best_dot: best_dot=dot; best_e=e
        if best_e is not None:
            dx2=best_e.cx-self.cx; dy2=best_e.cy-self.cy
            d2=math.hypot(dx2,dy2)
            if d2>0: self.aim_dir=(dx2/d2,dy2/d2)

    def attack(self, gmap, enemies, projectiles, messages):
        if self.attack_cooldown>0: return
        if self.is_ghost: messages.append(("Ghost can't attack!",GRAY)); return
        item=self.equipped_item()
        if item is None: messages.append(("Nothing equipped!",YELLOW)); return
        # Boomerang: block re-throw while in flight
        if getattr(item,'spell',None)=='boomerang' and self._boomerang_in_flight:
            messages.append(("Boomerang is still returning!",YELLOW)); return
        self.animator.trigger_attack(self.facing)
        if   item.itype==IT_WEAPON:     self._melee(item,gmap,enemies,messages)
        elif item.itype==IT_RANGED:     self._ranged(item,projectiles,messages)
        elif item.itype==IT_MAGIC:      self._magic(item,projectiles,messages)
        elif item.itype==IT_CONSUMABLE: self.use_item(item.iid,messages); return
        elif item.itype==IT_LIGHT:      messages.append(("Holding light.",YELLOW)); return
        self.attack_cooldown=item.cooldown if item else 20

    def _melee(self, item, gmap, enemies, messages):
        fx,fy=self.facing; reach=item.attack_range
        ax=self.cx+fx*(self.SIZE//2+4); ay=self.cy+fy*(self.SIZE//2+4)
        atk=pygame.Rect(ax-reach//2,ay-reach//2,reach,reach)
        self.attack_effect=AttackEffect(atk,YELLOW,10)
        hit=False
        berserk_mult = 2.0 if self.berserk_frames > 0 else 1.0
        for e in enemies:
            if isinstance(e, (Pet, Princess)): continue   # never harm companions
            if isinstance(e, Player): continue             # never harm other player
            if e.alive and atk.colliderect(e.rect):
                dmg=max(1,int((item.damage-e.defense)*berserk_mult)); e.take_damage(dmg)
                if hasattr(e,'on_attacked'): e.on_attacked()
                hit=True; messages.append((f"P{self.player_idx+1} hit {e.name} for {dmg}!",WHITE))
        if item.tool_tag:
            tx=int((ax+fx*16)//TILE_SIZE); ty=int((ay+fy*16)//TILE_SIZE)
            if gmap.in_bounds(tx,ty):
                t=gmap.get(tx,ty)
                if tile_tool(t)==item.tool_tag:
                    floor=T_GRASS if not gmap.is_dungeon else T_FLOOR
                    gmap.set(tx,ty,floor); messages.append(("Destroyed!",ORANGE))
        if not hit and not item.tool_tag: messages.append(("Whoosh!",GRAY))

    def _ranged(self, item, projectiles, messages):
        # Boomerang has no ammo requirement — it's the weapon itself
        if getattr(item,'spell',None)=='boomerang':
            proj=Projectile(self.cx,self.cy,self.aim_dir,
                            item.proj_speed,item.damage,item.proj_color,
                            owner='player',spell='boomerang')
            proj.owner_ref=self    # so it can home back
            self._boomerang_in_flight=True
            projectiles.append(proj)
            messages.append((f"P{self.player_idx+1} threw the boomerang!",WHITE))
            return
        if not self.inventory.has(item.ammo_type):
            messages.append((f"No {item.ammo_type}s!",RED)); return
        self.inventory.remove(item.ammo_type,1)
        projectiles.append(Projectile(self.cx,self.cy,self.aim_dir,
                                      item.proj_speed,item.damage,item.proj_color,
                                      owner='player'))
        messages.append((f"P{self.player_idx+1} fired {item.ammo_type}.",WHITE))

    def _magic(self, item, projectiles, messages):
        if self.mana<item.mana_cost: messages.append(("Not enough mana!",BLUE)); return
        self.mana-=item.mana_cost
        projectiles.append(Projectile(self.cx,self.cy,self.aim_dir,
                                      item.proj_speed,item.damage,item.proj_color,
                                      owner='player',spell=item.spell_effect))
        messages.append((f"P{self.player_idx+1} cast {item.name}!",CYAN))

    def use_item(self, iid, messages):
        from items import ITEMS
        it=ITEMS.get(iid)
        if it is None or not self.inventory.has(iid): return False
        if it.itype==IT_CONSUMABLE:
            if it.hp_restore:
                gained=min(it.hp_restore,self.max_hp-self.hp); self.hp+=gained
                messages.append((f"+{gained} HP.",GREEN))
            if it.mp_restore:
                gained=min(it.mp_restore,self.max_mana-self.mana); self.mana+=gained
                messages.append((f"+{gained} MP.",BLUE))
            if iid=='berserk_draught':
                self.berserk_frames=600   # 10 seconds
                messages.append(("BERSERK! Damage x2 for 10s!",RED))
            if iid=='charm_spell':
                # Set a persistent flag on the player — survives state transitions
                self.charm_cast = True
                self.inventory.remove(iid,1); return True
            self.inventory.remove(iid,1); return True
        return False

    def take_damage(self, amount, difficulty=DIFFICULTY_NORMAL):
        if self.iframes>0: return 0
        mult=DIFFICULTY_DMG_MULT.get(difficulty,1.0)
        actual=max(1,int(max(1,amount-self.defense)*mult))
        self.hp-=actual
        if self.hp<=0:
            self.hp=0; self.alive=False
            # Record death location for body marker
            self.death_x=self.x; self.death_y=self.y
            self.is_ghost=True
            self.animator.trigger_dead()
        else: self.animator.trigger_hurt()
        self.iframes=PLAYER_IFRAMES; return actual

    def update(self, input_state: dict, gmap, enemies, projectiles, messages,
               cam_x=0, cam_y=0, mouse_pos=None):
        """
        input_state: dict with boolean values for 'up','down','left','right'.
        Ghost players can move but cannot attack/interact (handled in game.py).
        """
        dx=dy=0.0
        if input_state.get('left'):  dx-=1.0
        if input_state.get('right'): dx+=1.0
        if input_state.get('up'):    dy-=1.0
        if input_state.get('down'):  dy+=1.0
        moving=dx!=0.0 or dy!=0.0

        # Normalise FIRST (so diagonal == orthogonal distance per frame)
        if dx and dy:
            dx *= 0.7071; dy *= 0.7071

        # Apply effective speed (base + armor bonus)
        eff_speed = self.speed + getattr(self,'_speed_bonus',0.0)
        dx *= eff_speed; dy *= eff_speed

        if moving:
            if   dx<0: self.facing=DIR_LEFT
            elif dx>0: self.facing=DIR_RIGHT
            elif dy<0: self.facing=DIR_UP
            else:      self.facing=DIR_DOWN

            ts=TILE_SIZE; sz=self.SIZE
            def corner_tiles(nx,ny):
                return [gmap.get(int(cx_//ts),int(cy_//ts))
                        for cx_,cy_ in [(nx,ny),(nx+sz-1,ny),(nx,ny+sz-1),(nx+sz-1,ny+sz-1)]]

            if self.is_ghost:
                # Ghosts pass through everything (full noclip)
                self.x+=dx; self.y+=dy
                mw=gmap.width*TILE_SIZE; mh=gmap.height*TILE_SIZE
                self.x=max(0,min(self.x,mw-ENTITY_SIZE))
                self.y=max(0,min(self.y,mh-ENTITY_SIZE))
            else:
                nx,ny=self.x+dx,self.y+dy; cts=corner_tiles(nx,ny)
                any_swim=any(tile_swimmable(t) for t in cts)
                all_ok=all(tile_walkable(t) or tile_swimmable(t) for t in cts)
                any_slow=any(tile_slow(t) for t in cts)

                if any_swim and all_ok:
                    self.is_swimming=True
                    dx*=SWIM_SPEED_MULT; dy*=SWIM_SPEED_MULT
                    self._swim_move(dx,dy,gmap)
                else:
                    self.is_swimming=False
                    if any_slow: dx*=SLOW_SPEED_MULT; dy*=SLOW_SPEED_MULT; self.is_slowed=True
                    else: self.is_slowed=False
                    self.try_move(dx,dy,gmap)

            ptx=int(self.cx//TILE_SIZE); pty=int(self.cy//TILE_SIZE)
            if not self.is_ghost:
                self.is_swimming=tile_swimmable(gmap.get(ptx,pty))
            self.animator.push_walk(self.facing)
        else:
            ptx=int(self.cx//TILE_SIZE); pty=int(self.cy//TILE_SIZE)
            if not self.is_ghost:
                self.is_swimming=tile_swimmable(gmap.get(ptx,pty))
                self.is_slowed=tile_slow(gmap.get(ptx,pty))
            self.animator.push_idle(self.facing)

        self.animator.tick()
        if self.attack_cooldown>0: self.attack_cooldown-=1
        if self.iframes>0: self.iframes-=1
        if self.berserk_frames>0: self.berserk_frames-=1
        if self.attack_effect:
            self.attack_effect.update()
            if self.attack_effect.done: self.attack_effect=None
        if self.mana<self.max_mana and random.random()<0.004:
            self.mana=min(self.max_mana,self.mana+1)
        self.update_light()
        if not self.is_ghost:
            self.compute_aim(enemies, mouse_pos=mouse_pos, cam_x=cam_x, cam_y=cam_y)

    def _swim_move(self, dx, dy, gmap):
        ts=TILE_SIZE; sz=self.SIZE; mw=gmap.width*ts; mh=gmap.height*ts
        def ok(x,y):
            for cx_,cy_ in [(x,y),(x+sz-1,y),(x,y+sz-1),(x+sz-1,y+sz-1)]:
                t=gmap.get(int(cx_//ts),int(cy_//ts))
                if not(tile_walkable(t) or tile_swimmable(t)): return False
            return 0<=x and 0<=y and x+sz<=mw and y+sz<=mh
        if dx and ok(self.x+dx,self.y): self.x+=dx
        if dy and ok(self.x,self.y+dy): self.y+=dy

    def draw(self, surf, cam_x, cam_y, asset_mgr=None, brightness=255):
        sx=int(self.x)-cam_x; sy=int(self.y)-cam_y
        # Draw dead body first (stays at death location)
        if self.is_ghost and self.death_x is not None:
            bsx=int(self.death_x)-cam_x; bsy=int(self.death_y)-cam_y
            body_surf=pygame.Surface((self.SIZE,self.SIZE),pygame.SRCALPHA)
            bcol=(150,80,60) if self.player_idx==0 else (180,100,60)
            body_surf.fill((*bcol,160))
            surf.blit(body_surf,(bsx,bsy))
            # Cross / X mark
            pygame.draw.line(surf,(200,50,50),(bsx+4,bsy+4),(bsx+self.SIZE-4,bsy+self.SIZE-4),2)
            pygame.draw.line(surf,(200,50,50),(bsx+self.SIZE-4,bsy+4),(bsx+4,bsy+self.SIZE-4),2)

        # Draw ghost/player sprite
        tint_col=(80,140,255) if self.player_idx==0 else (255,140,80)
        sprite=asset_mgr.get_entity_surface(self.animator) if asset_mgr else None
        if self.is_ghost:
            # Ghost: semi-transparent blue-white silhouette
            ghost_surf=pygame.Surface((self.SIZE,self.SIZE),pygame.SRCALPHA)
            gcol=(180,210,255) if self.player_idx==0 else (255,200,180)
            ghost_surf.fill((*gcol,110))
            surf.blit(ghost_surf,(sx,sy))
            # Label
            f=_label_font(10)
            lbl=f.render(PLAYER_NAMES[self.player_idx]+" [GHOST]",True,(180,210,255))
            surf.blit(lbl,(sx+self.SIZE//2-lbl.get_width()//2,sy-14))
            return

        if sprite:
            spr=sprite.copy()
            if self.player_idx==1:
                spr.fill((80,30,0,60),special_flags=pygame.BLEND_RGBA_ADD)
            if self.is_swimming: spr.fill((0,80,180,60),special_flags=pygame.BLEND_RGBA_ADD)
            elif self.is_slowed: spr.fill((30,80,30,40),special_flags=pygame.BLEND_RGBA_ADD)
            if self.berserk_frames>0 and (self.berserk_frames//4)%2==0:
                spr.fill((150,0,0,80),special_flags=pygame.BLEND_RGBA_ADD)
            if self.iframes>0 and (self.iframes//4)%2==1:
                spr.fill((255,255,255,120),special_flags=pygame.BLEND_RGBA_ADD)
            surf.blit(spr,(sx,sy))
        else:
            col=tint_col
            if self.is_swimming: col=(max(0,col[0]-60),max(0,col[1]-20),min(255,col[2]+80))
            if self.is_slowed: col=(max(0,col[0]-20),min(255,col[1]+40),max(0,col[2]-20))
            if self.berserk_frames>0 and (self.berserk_frames//4)%2==0: col=RED
            if self.iframes>0 and (self.iframes//4)%2==1: col=WHITE
            pygame.draw.rect(surf,col,(sx,sy,self.SIZE,self.SIZE))
            pygame.draw.rect(surf,BLACK,(sx,sy,self.SIZE,self.SIZE),1)
            fx,fy=self.facing
            pygame.draw.rect(surf,BLACK,(sx+self.SIZE//2+fx*(self.SIZE//2-4)-3,
                                          sy+self.SIZE//2+fy*(self.SIZE//2-4)-3,6,6))
        if self.attack_effect: self.attack_effect.draw(surf,cam_x,cam_y,asset_mgr)
        # Aim indicator
        aim_col=YELLOW if self.aim_mode=='mouse' else CYAN
        ax=sx+self.SIZE//2+int(self.aim_dir[0]*14)
        ay=sy+self.SIZE//2+int(self.aim_dir[1]*14)
        pygame.draw.circle(surf,aim_col,(ax,ay),3)
        # Player label
        f=_label_font(10)
        lbl_col=YELLOW if self.player_idx==0 else ORANGE
        if self.berserk_frames>0: lbl_col=RED
        lbl=f.render(PLAYER_NAMES[self.player_idx],True,lbl_col)
        surf.blit(lbl,(sx+self.SIZE//2-lbl.get_width()//2, sy-14))


# ═══════════════════════════════════════════════════════════════════════════════
#  Attack Effect
# ═══════════════════════════════════════════════════════════════════════════════
class AttackEffect:
    def __init__(self,rect,color,duration,fx_name='attack_slash'):
        self.rect=rect;self.color=color;self.duration=duration
        self.timer=duration;self.done=False
    def update(self): self.timer-=1;self.done=(self.timer<=0)
    def draw(self,surf,cam_x,cam_y,asset_mgr=None):
        rx=self.rect.x-cam_x;ry=self.rect.y-cam_y
        alpha=int(200*self.timer/max(1,self.duration))
        r=pygame.Rect(rx,ry,self.rect.w,self.rect.h)
        s=pygame.Surface((r.w,r.h),pygame.SRCALPHA)
        s.fill((*self.color[:3],alpha));surf.blit(s,(r.x,r.y))


# ═══════════════════════════════════════════════════════════════════════════════
#  Projectile
# ═══════════════════════════════════════════════════════════════════════════════
class Projectile:
    SIZE=8
    def __init__(self,x,y,direction,speed,damage,color,owner='player',
                 ammo_type=None,spell=None):
        self.x=float(x)-self.SIZE/2;self.y=float(y)-self.SIZE/2
        self.dx=direction[0]*speed;self.dy=direction[1]*speed
        self.damage=damage;self.color=color;self.owner=owner
        self.ammo_type=ammo_type;self.spell=spell
        self.alive=True;self.lifetime=120
        self.kind=spell if spell else(ammo_type if ammo_type else 'arcane')
        # Boomerang state
        self.owner_ref=None      # set to firing Player instance for boomerangs
        self._boom_hit=False     # True after it has struck once
        self._returning=False    # True while homing back to owner
    @property
    def rect(self): return pygame.Rect(int(self.x),int(self.y),self.SIZE,self.SIZE)
    def update(self,gmap,players,enemies,messages,difficulty=DIFFICULTY_NORMAL):
        if not self.alive: return
        self.lifetime-=1
        if self.lifetime<=0:
            self.alive=False
            if self.spell=='boomerang' and self.owner_ref is not None:
                self.owner_ref._boomerang_in_flight=False
            return

        # ── Boomerang ─────────────────────────────────────────────────────────
        if self.spell=='boomerang':
            owner=self.owner_ref
            if owner is None: self.alive=False; return
            if not self._returning:
                # Outward phase: move forward
                self.x+=self.dx; self.y+=self.dy
                tx=int((self.x+self.SIZE/2)//TILE_SIZE)
                ty=int((self.y+self.SIZE/2)//TILE_SIZE)
                if not tile_walkable(gmap.get(tx,ty)) and not tile_swimmable(gmap.get(tx,ty)):
                    self._start_return(); return
                # One hit only
                if not self._boom_hit:
                    r=self.rect
                    for e in enemies:
                        if e.alive and r.colliderect(e.rect):
                            dmg=e.take_damage(self.damage)
                            if hasattr(e,'on_attacked'): e.on_attacked()
                            messages.append((f"Boomerang hits {e.name} for {dmg}!",WHITE))
                            self._boom_hit=True
                            self._start_return(); return
                # Turn back after ~half flight time
                if self.lifetime < 60:
                    self._start_return()
            else:
                # Return phase: home toward owner
                ox=owner.cx-self.SIZE/2; oy=owner.cy-self.SIZE/2
                dist=math.hypot(ox-self.x, oy-self.y)
                if dist < 10:
                    self.alive=False
                    owner._boomerang_in_flight=False
                    return
                spd=math.hypot(self.dx,self.dy) or 6.0
                self.dx=(ox-self.x)/dist*spd
                self.dy=(oy-self.y)/dist*spd
                self.x+=self.dx; self.y+=self.dy
            return

        # ── Normal projectile ─────────────────────────────────────────────────
        self.x+=self.dx;self.y+=self.dy
        tx=int((self.x+self.SIZE/2)//TILE_SIZE);ty=int((self.y+self.SIZE/2)//TILE_SIZE)
        t=gmap.get(tx,ty)
        if not tile_walkable(t) and not tile_swimmable(t):
            if self.spell in ('area_blast',): self._area_explode(enemies,messages)
            self.alive=False; return
        r=self.rect
        if self.owner=='player':
            for e in enemies:
                if isinstance(e, (Pet, Princess, Player)): continue
                if e.alive and r.colliderect(e.rect):
                    dmg=e.take_damage(self.damage)
                    if hasattr(e,'on_attacked'): e.on_attacked()
                    messages.append((f"Hit {e.name} for {dmg}!",WHITE))
                    self.alive=False
                    if self.spell=='fireball':
                        for e2 in enemies:
                            if e2 is not e and e2.alive and math.hypot(e.cx-e2.cx,e.cy-e2.cy)<TILE_SIZE*1.5:
                                e2.take_damage(self.damage//2)
                    elif self.spell=='area_blast':
                        self._area_explode(enemies,messages)
                    return
        elif self.owner=='enemy':
            for pl in players:
                if pl.alive and not getattr(pl,'is_ghost',False) and r.colliderect(pl.rect):
                    dmg=pl.take_damage(self.damage,difficulty)
                    if dmg>0: messages.append((f"You took {dmg} damage!",RED))
                    self.alive=False; return

    def _start_return(self):
        """Begin return arc — homing takes over from here."""
        self._returning=True
        self.dx=-self.dx*0.4; self.dy=-self.dy*0.4

    def _area_explode(self, enemies, messages):
        """AoE explosion for area_blast spell."""
        blast_r = TILE_SIZE * 3
        for e in enemies:
            if e.alive and math.hypot(e.cx - (self.x+self.SIZE/2),
                                       e.cy - (self.y+self.SIZE/2)) < blast_r:
                dmg = e.take_damage(self.damage)
                if hasattr(e,'on_attacked'): e.on_attacked()
                messages.append((f"BLAST hits {e.name} for {dmg}!",ORANGE))
    def draw(self,surf,cam_x,cam_y,asset_mgr=None):
        sx=int(self.x)-cam_x;sy=int(self.y)-cam_y
        if self.spell=='boomerang':
            # Draw as a spinning arc-shaped oval
            col=self.color if not self._returning else (255,220,80)
            pygame.draw.ellipse(surf,col,(sx-2,sy,self.SIZE+4,self.SIZE//2+2))
            pygame.draw.ellipse(surf,(255,255,200),(sx,sy+2,self.SIZE,2))
        else:
            pygame.draw.rect(surf,self.color,(sx,sy,self.SIZE,self.SIZE))


# ═══════════════════════════════════════════════════════════════════════════════
#  Enemy Base
# ═══════════════════════════════════════════════════════════════════════════════
class Enemy(Entity):
    DETECTION_RANGE=180;ATTACK_RANGE=34;ATTACK_DAMAGE=8;ATTACK_COOL=60
    DEFENSE=0;RANGED_RANGE=0;PROJ_SPEED=4;PROJ_COLOR=RED;PROJ_DAMAGE=6
    AGGRO_TYPE='sight';FLEE_HP_PCT=0.0;DEAGGRO_DIST=0
    FIGHT_TO_DEATH=False;LUMINOUS=False

    def __init__(self,x,y,name,color,hp,speed,etype,is_boss=False):
        super().__init__(x,y,color,hp*(3 if is_boss else 1),etype)
        self.name=name;self.speed=speed;self.etype=etype;self.is_boss=is_boss
        self.defense=self.DEFENSE;self.SIZE=ENTITY_SIZE*2 if is_boss else ENTITY_SIZE
        self.damage=self.ATTACK_DAMAGE          # instance copy for charmed-mob use
        self.attack_range=self.ATTACK_RANGE     # instance copy
        self._state='wander';self._wander_dir=(0.0,0.0);self._wander_timer=0
        self._attack_cool=0;self._stun_timer=0;self._proj_cool=0
        self._rng=random.Random(id(self));self._aggroed=False;self._aggro_src='none'
        self.charmed    = False   # True when player uses charm_spell
        self.charmed_by = None    # Player reference

    def on_attacked(self):
        if self.AGGRO_TYPE in('attack','sight'):
            self._aggroed=True;self._aggro_src='attack';self._state='chase'

    def _nearest_player(self, players):
        """Return nearest *living non-ghost* player; fallback to any player."""
        living=[p for p in players if p.alive and not getattr(p,'is_ghost',False)]
        if not living:
            living=[p for p in players if p.alive]  # all ghosts: still fallback
        if not living: return players[0]
        return min(living, key=lambda p: self.dist_to(p))

    def update(self, players, gmap, projectiles, messages):
        """players is a list of Player instances."""
        if not self.alive: return

        # ── Charmed mob ──────────────────────────────────────────────────────
        if self.charmed:
            owner = self.charmed_by
            # Find nearest hostile enemy to chase
            all_ents = gmap.entities if gmap else []
            foes = [e for e in all_ents
                    if e is not self and e.alive and not getattr(e,'charmed',False)]
            if foes:
                nearest_foe = min(foes, key=lambda e: math.hypot(e.cx-self.cx, e.cy-self.cy))
                dfx = nearest_foe.cx - self.cx; dfy = nearest_foe.cy - self.cy
                dist_foe = math.hypot(dfx, dfy)
                if dist_foe < TILE_SIZE * 6:   # aggro range for charmed mob
                    if dist_foe < self.ATTACK_RANGE:
                        # Attack the foe
                        if self._attack_cool <= 0:
                            nearest_foe.take_damage(self.damage)
                            self._attack_cool = 40
                            messages.append((f"{self.name} hits {nearest_foe.name}!", (180,255,180)))
                    else:
                        self.try_move(dfx/dist_foe*self.speed, dfy/dist_foe*self.speed,
                                      gmap, ghost=self._is_ghost(), water_walker=self._is_water_walker())
                    self.animator.tick(); return
            # No foes nearby — follow owner
            if owner:
                dpx = owner.cx - self.cx; dpy = owner.cy - self.cy
                dist_p = math.hypot(dpx, dpy)
                if dist_p > TILE_SIZE * 2:
                    self.try_move(dpx/dist_p*self.speed*0.7, dpy/dist_p*self.speed*0.7,
                                  gmap, ghost=self._is_ghost(), water_walker=self._is_water_walker())
            if self._attack_cool > 0: self._attack_cool -= 1
            self.animator.tick(); return

        target=self._nearest_player(players)
        dist=self.dist_to(target)
        if self._stun_timer>0:
            self._stun_timer-=1;self._state='stunned'
        else:
            should_aggro=(self.AGGRO_TYPE=='sight' and dist<self.DETECTION_RANGE) or self._aggroed
            low_hp=(self.hp/self.max_hp)<self.FLEE_HP_PCT
            fleeing=low_hp and not self.FIGHT_TO_DEATH and self.FLEE_HP_PCT>0
            if fleeing: self._state='flee'
            elif should_aggro:
                if dist<self.ATTACK_RANGE: self._state='attack'
                else:
                    self._state='chase'
                    if(self.DEAGGRO_DIST>0 and dist>self.DEAGGRO_DIST and
                       not self.FIGHT_TO_DEATH and self._aggro_src=='sight'):
                        self._aggroed=False;self._state='wander'
            else:
                if self._state in('chase','attack'): self._state='wander'
        if self._attack_cool>0: self._attack_cool-=1
        if self._proj_cool>0:   self._proj_cool-=1
        if   self._state=='wander':  self._wander(gmap)
        elif self._state=='chase':   self._chase(target,gmap,projectiles)
        elif self._state=='attack':  self._do_attack(target,gmap,projectiles,messages)
        elif self._state=='flee':    self._flee(target,gmap)
        elif self._state=='stunned': self.animator.push_idle(self.facing)
        self.animator.tick()

    def _wander(self,gmap=None):
        self._wander_timer-=1
        if self._wander_timer<=0:
            angle=self._rng.uniform(0,2*math.pi)
            self._wander_dir=(math.cos(angle),math.sin(angle))
            self._wander_timer=self._rng.randint(40,100)
        dx=self._wander_dir[0]*self.speed*0.4;dy=self._wander_dir[1]*self.speed*0.4
        self.try_move(dx,dy,gmap,ghost=self._is_ghost(),water_walker=self._is_water_walker())
        if abs(dx)>abs(dy): self.facing=DIR_RIGHT if dx>0 else DIR_LEFT
        elif dy!=0: self.facing=DIR_DOWN if dy>0 else DIR_UP
        self.animator.push_walk(self.facing)

    def _chase(self,target,gmap,projectiles):
        dx=target.cx-self.cx;dy=target.cy-self.cy;d=math.hypot(dx,dy)
        if d>0:
            self.try_move(dx/d*self.speed,dy/d*self.speed,gmap,
                          ghost=self._is_ghost(),water_walker=self._is_water_walker())
            self.facing=DIR_RIGHT if dx>0 else(DIR_LEFT if dx<0 else(DIR_DOWN if dy>0 else DIR_UP))
            self.animator.push_walk(self.facing);self._aggroed=True
        if self.RANGED_RANGE and d<self.RANGED_RANGE and self._proj_cool==0:
            self._fire_proj(target,projectiles)

    def _do_attack(self,target,gmap,projectiles,messages):
        self.animator.push_idle(self.facing);self._aggroed=True
        if self._attack_cool==0:
            dmg=target.take_damage(self.ATTACK_DAMAGE)
            if dmg>0: messages.append((f"{self.name} hits for {dmg}!",RED))
            self._attack_cool=self.ATTACK_COOL
            try:
                import sound_engine
                sfx_key=sound_engine.ENEMY_ATTACK_SFX.get(self.etype,'hit_melee')
                sound_engine.play_sfx(sfx_key, volume=0.6)
            except Exception: pass

    def _flee(self,target,gmap,*args):
        dx=self.cx-target.cx;dy=self.cy-target.cy;d=math.hypot(dx,dy)
        if d>0:
            self.try_move(dx/d*self.speed*1.2,dy/d*self.speed*1.2,gmap,
                          ghost=self._is_ghost(),water_walker=self._is_water_walker())
        self.animator.push_walk(self.facing)

    def _fire_proj(self,target,projectiles):
        dx=target.cx-self.cx;dy=target.cy-self.cy;d=math.hypot(dx,dy)
        if d==0: return
        projectiles.append(Projectile(self.cx,self.cy,(dx/d,dy/d),
                                      self.PROJ_SPEED,self.PROJ_DAMAGE,self.PROJ_COLOR,owner='enemy'))
        self._proj_cool=90

    def _is_ghost(self): return False
    def _is_water_walker(self): return False
    def get_drops(self,rng): return roll_drops(self.etype,rng,is_boss=self.is_boss)

    def draw(self,surf,cam_x,cam_y,asset_mgr=None,brightness=255):
        sx=int(self.x)-cam_x;sy=int(self.y)-cam_y;s=self.SIZE
        if sx+s<0 or sx>surf.get_width() or sy+s<0 or sy>surf.get_height(): return
        luminous=self.LUMINOUS or self.is_boss
        if brightness<40 and not luminous: return
        sprite=asset_mgr.get_entity_surface(self.animator) if asset_mgr else None
        alpha=max(80,min(255,brightness*2)) if(luminous and brightness<128) else 255
        if sprite:
            sp=sprite if sprite.get_size()==(s,s) else pygame.transform.scale(sprite,(s,s))
            if alpha<255: sp2=sp.copy();sp2.set_alpha(alpha);surf.blit(sp2,(sx,sy))
            else: surf.blit(sp,(sx,sy))
        else:
            col=tuple(min(255,c+40) for c in self.color) if self.is_boss else self.color
            if alpha<255:
                ss=pygame.Surface((s,s),pygame.SRCALPHA);ss.fill((*col,alpha));surf.blit(ss,(sx,sy))
            else:
                pygame.draw.rect(surf,col,(sx,sy,s,s));pygame.draw.rect(surf,BLACK,(sx,sy,s,s),1)
        bar_w=int(s*self.hp/self.max_hp)
        pygame.draw.rect(surf,DARK_RED,(sx,sy-6,s,4));pygame.draw.rect(surf,GREEN,(sx,sy-6,bar_w,4))
        if brightness>=50 or luminous:
            f=_label_font(10);lbl=f.render(self.name,True,WHITE);shd=f.render(self.name,True,BLACK)
            lx=sx+s//2-lbl.get_width()//2;ly=sy-17
            surf.blit(shd,(lx+1,ly+1));surf.blit(lbl,(lx,ly))


# ═══════════════════════════════════════════════════════════════════════════════
#  Concrete enemies (same as v3, just update() call signature changed above)
# ═══════════════════════════════════════════════════════════════════════════════
class Slime(Enemy):
    DETECTION_RANGE=140;ATTACK_RANGE=30;ATTACK_DAMAGE=6;ATTACK_COOL=70
    AGGRO_TYPE='attack';FLEE_HP_PCT=0.20;LUMINOUS=True
    def __init__(self,x,y,is_boss=False): super().__init__(x,y,"Slime",COL_SLIME,22,1.2,'slime',is_boss)

class Bat(Enemy):
    DETECTION_RANGE=200;ATTACK_RANGE=28;ATTACK_DAMAGE=5;ATTACK_COOL=50;FLEE_HP_PCT=0.15
    def __init__(self,x,y,is_boss=False): super().__init__(x,y,"Bat",COL_BAT,16,2.5,'bat',is_boss)
    def _chase(self,target,gmap,projectiles):
        dx=target.cx-self.cx;dy=target.cy-self.cy;d=math.hypot(dx,dy)
        if d>0:
            angle=math.atan2(dy,dx)+self._rng.uniform(-0.6,0.6)
            self.try_move(math.cos(angle)*self.speed,math.sin(angle)*self.speed,gmap)
        self.animator.push_walk(self.facing);self._aggroed=True

class Spider(Enemy):
    DETECTION_RANGE=160;ATTACK_RANGE=32;ATTACK_DAMAGE=8;ATTACK_COOL=60
    RANGED_RANGE=120;PROJ_SPEED=3;PROJ_COLOR=COL_WEB;PROJ_DAMAGE=5;FIGHT_TO_DEATH=True
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Giant Spider" if is_boss else "Spider",
                         COL_SPIDER,28,1.8,'giant_spider' if is_boss else 'spider',is_boss)

class Goblin(Enemy):
    DETECTION_RANGE=190;ATTACK_RANGE=30;ATTACK_DAMAGE=10;ATTACK_COOL=55;DEAGGRO_DIST=300
    def __init__(self,x,y,is_boss=False): super().__init__(x,y,"Goblin",COL_GOBLIN,32,2.0,'goblin',is_boss)

class Skeleton(Enemy):
    DETECTION_RANGE=170;ATTACK_RANGE=32;ATTACK_DAMAGE=12;ATTACK_COOL=65
    DEFENSE=2;RANGED_RANGE=150;PROJ_SPEED=5;PROJ_COLOR=COL_BONE;PROJ_DAMAGE=8;FIGHT_TO_DEATH=True
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Skeleton Lord" if is_boss else "Skeleton",COL_SKELETON,35,1.6,'skeleton',is_boss)

class Ghost(Enemy):
    DETECTION_RANGE=210;ATTACK_RANGE=28;ATTACK_DAMAGE=9;ATTACK_COOL=55;LUMINOUS=True;FIGHT_TO_DEATH=True
    def __init__(self,x,y,is_boss=False): super().__init__(x,y,"Ghost",COL_GHOST,25,1.4,'ghost',is_boss)
    def _is_ghost(self): return True
    def draw(self,surf,cam_x,cam_y,asset_mgr=None,brightness=255):
        sx=int(self.x)-cam_x;sy=int(self.y)-cam_y;s=self.SIZE
        alpha=max(80,min(200,brightness+80))
        sprite=asset_mgr.get_entity_surface(self.animator) if asset_mgr else None
        if sprite:
            sp=sprite.copy();sp.set_alpha(alpha);surf.blit(sp,(sx,sy))
        else:
            gs=pygame.Surface((s,s),pygame.SRCALPHA);gs.fill((*self.color,alpha))
            surf.blit(gs,(sx,sy));pygame.draw.rect(surf,WHITE,(sx,sy,s,s),1)
        bar_w=int(s*self.hp/self.max_hp)
        pygame.draw.rect(surf,DARK_RED,(sx,sy-6,s,4));pygame.draw.rect(surf,GREEN,(sx,sy-6,bar_w,4))
        f=_label_font(10);lbl=f.render(self.name,True,(200,220,255))
        surf.blit(lbl,(sx+s//2-lbl.get_width()//2,sy-17))

class Troll(Enemy):
    DETECTION_RANGE=150;ATTACK_RANGE=38;ATTACK_DAMAGE=18;ATTACK_COOL=90;DEFENSE=4;FLEE_HP_PCT=0.10;DEAGGRO_DIST=400
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Stone Troll" if is_boss else "Troll",COL_TROLL,70,1.0,'troll',is_boss)

class Wolf(Enemy):
    DETECTION_RANGE=220;ATTACK_RANGE=30;ATTACK_DAMAGE=11;ATTACK_COOL=45;DEAGGRO_DIST=350
    def __init__(self,x,y,is_boss=False): super().__init__(x,y,"Wolf",COL_WOLF,30,3.2,'wolf',is_boss)

class Kelpie(Enemy):
    DETECTION_RANGE=200;ATTACK_RANGE=30;ATTACK_DAMAGE=14;ATTACK_COOL=55
    RANGED_RANGE=160;PROJ_SPEED=5;PROJ_COLOR=COL_WATER_BOLT;PROJ_DAMAGE=10;FIGHT_TO_DEATH=True
    def __init__(self,x,y,is_boss=False): super().__init__(x,y,"Kelpie",COL_KELPIE,45,2.4,'kelpie',is_boss)
    def _is_water_walker(self): return True

class Yeti(Enemy):
    DETECTION_RANGE=170;ATTACK_RANGE=40;ATTACK_DAMAGE=20;ATTACK_COOL=80;DEFENSE=3;FIGHT_TO_DEATH=True
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Elder Yeti" if is_boss else "Yeti",COL_YETI,60,1.3,'yeti',is_boss)

class IceWraith(Enemy):
    DETECTION_RANGE=220;ATTACK_RANGE=30;ATTACK_DAMAGE=10;ATTACK_COOL=50
    RANGED_RANGE=180;PROJ_SPEED=6;PROJ_COLOR=COL_ICE_BOLT;PROJ_DAMAGE=12;LUMINOUS=True;FIGHT_TO_DEATH=True
    def __init__(self,x,y,is_boss=False): super().__init__(x,y,"Ice Wraith",COL_ICE_WRAITH,30,1.8,'ice_wraith',is_boss)
    def _is_ghost(self): return True

class Scorpion(Enemy):
    DETECTION_RANGE=160;ATTACK_RANGE=32;ATTACK_DAMAGE=14;ATTACK_COOL=55
    RANGED_RANGE=140;PROJ_SPEED=5;PROJ_COLOR=COL_POISON;PROJ_DAMAGE=9;FIGHT_TO_DEATH=True
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Giant Scorpion" if is_boss else "Scorpion",COL_SCORPION,38,1.9,'scorpion',is_boss)

class Mummy(Enemy):
    DETECTION_RANGE=150;ATTACK_RANGE=34;ATTACK_DAMAGE=15;ATTACK_COOL=75;DEFENSE=3;AGGRO_TYPE='attack';FIGHT_TO_DEATH=True
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Mummy Lord" if is_boss else "Mummy",COL_MUMMY,50,1.1,'mummy',is_boss)

class SwampToad(Enemy):
    DETECTION_RANGE=140;ATTACK_RANGE=30;ATTACK_DAMAGE=8;ATTACK_COOL=65
    RANGED_RANGE=120;PROJ_SPEED=4;PROJ_COLOR=COL_POISON;PROJ_DAMAGE=6;FLEE_HP_PCT=0.25;AGGRO_TYPE='attack'
    def __init__(self,x,y,is_boss=False): super().__init__(x,y,"Swamp Toad",COL_SWAMP_TOAD,28,1.5,'swamp_toad',is_boss)
    def _is_water_walker(self): return True

class WillOWisp(Enemy):
    DETECTION_RANGE=240;ATTACK_RANGE=24;ATTACK_DAMAGE=7;ATTACK_COOL=45;LUMINOUS=True;FIGHT_TO_DEATH=True
    def __init__(self,x,y,is_boss=False): super().__init__(x,y,"Will-o'-Wisp",COL_WILL_O,20,2.2,'will_o',is_boss)
    def _is_ghost(self): return True
    def draw(self,surf,cam_x,cam_y,asset_mgr=None,brightness=255):
        sx=int(self.x)-cam_x;sy=int(self.y)-cam_y;s=self.SIZE
        pulse=abs(math.sin(pygame.time.get_ticks()*0.003))*80+80
        gs=pygame.Surface((s,s),pygame.SRCALPHA);gs.fill((*self.color,int(pulse)));surf.blit(gs,(sx,sy))
        bar_w=int(s*self.hp/self.max_hp)
        pygame.draw.rect(surf,DARK_RED,(sx,sy-6,s,4));pygame.draw.rect(surf,GREEN,(sx,sy-6,bar_w,4))


# ── Mimic – masquerades as a chest, ambushes the player ──────────────────────
class Mimic(Enemy):
    DETECTION_RANGE=80;ATTACK_RANGE=36;ATTACK_DAMAGE=20;ATTACK_COOL=50
    DEFENSE=4;FIGHT_TO_DEATH=True;AGGRO_TYPE='attack'
    def __init__(self,x,y,is_boss=False):
        super().__init__(x,y,"Mimic",COL_MIMIC,55,1.6,'mimic',is_boss)
    def draw(self,surf,cam_x,cam_y,asset_mgr=None,brightness=255):
        sx=int(self.x)-cam_x;sy=int(self.y)-cam_y;s=self.SIZE
        if sx+s<0 or sx>surf.get_width() or sy+s<0 or sy>surf.get_height(): return
        # Draw as a sinister chest with eyes
        pygame.draw.rect(surf,(180,100,20),(sx,sy,s,s))
        pygame.draw.rect(surf,(120,70,10),(sx,sy+s//2,s,s//2))
        pygame.draw.rect(surf,BLACK,(sx,sy,s,s),2)
        # Eyes
        t=(pygame.time.get_ticks()//500)%2
        eye_col=RED if (self._aggroed or self._state!='wander') else (200,150,50)
        pygame.draw.circle(surf,eye_col,(sx+s//3,sy+s//3+t*2),4)
        pygame.draw.circle(surf,eye_col,(sx+2*s//3,sy+s//3+t*2),4)
        # HP bar
        bar_w=int(s*self.hp/self.max_hp)
        pygame.draw.rect(surf,DARK_RED,(sx,sy-6,s,4));pygame.draw.rect(surf,GREEN,(sx,sy-6,bar_w,4))
        f=_label_font(10);lbl=f.render("Mimic!",True,RED)
        surf.blit(lbl,(sx+s//2-lbl.get_width()//2,sy-17))


# ── Dragon – large (3×3 tile) boss, fire-breath spread attack ────────────────
class Dragon(Enemy):
    DETECTION_RANGE=280;ATTACK_RANGE=50;ATTACK_DAMAGE=30;ATTACK_COOL=90
    DEFENSE=10;FIGHT_TO_DEATH=True;LUMINOUS=True
    RANGED_RANGE=220;PROJ_SPEED=6;PROJ_COLOR=COL_FIREBALL;PROJ_DAMAGE=25
    # Dragon fires THREE fire bolts in a spread when in range
    _SPREAD_ANGLES = [-0.35, 0.0, 0.35]

    def __init__(self,x,y,is_boss=True,variant='dragon'):
        # Color varies by variant
        colors={'dragon':(160,30,10),'frost_dragon':(80,140,200),
                'sand_dragon':(200,150,30),'swamp_dragon':(40,110,50)}
        names={'dragon':'Dragon','frost_dragon':'Frost Dragon',
               'sand_dragon':'Sand Dragon','swamp_dragon':'Swamp Dragon'}
        proj_cols={'dragon':COL_FIREBALL,'frost_dragon':COL_ICE_BOLT,
                   'sand_dragon':(220,180,60),'swamp_dragon':(80,200,60)}
        col=colors.get(variant,(160,30,10))
        nm=names.get(variant,'Dragon')
        pc=proj_cols.get(variant,COL_FIREBALL)
        super().__init__(x,y,nm,col,400 if is_boss else 180,1.0,variant,is_boss)
        self.SIZE=ENTITY_SIZE*3   # 3× tile size – very large
        self.PROJ_COLOR=pc
        self._variant=variant

    def _fire_proj(self,target,projectiles):
        """Fire 3 bolts in a spread pattern."""
        dx=target.cx-self.cx;dy=target.cy-self.cy;d=math.hypot(dx,dy)
        if d==0: return
        base_angle=math.atan2(dy,dx)
        for offset in self._SPREAD_ANGLES:
            angle=base_angle+offset
            proj_dir=(math.cos(angle),math.sin(angle))
            projectiles.append(Projectile(self.cx,self.cy,proj_dir,
                                          self.PROJ_SPEED,self.PROJ_DAMAGE,
                                          self.PROJ_COLOR,owner='enemy'))
        self._proj_cool=self.ATTACK_COOL//2

    def draw(self,surf,cam_x,cam_y,asset_mgr=None,brightness=255):
        sx=int(self.x)-cam_x;sy=int(self.y)-cam_y;s=self.SIZE
        if sx+s<0 or sx>surf.get_width() or sy+s<0 or sy>surf.get_height(): return
        col=self.color if brightness>40 else tuple(max(0,c-80) for c in self.color)
        # Body
        pygame.draw.ellipse(surf,col,(sx,sy+s//4,s,s*3//4))
        # Head
        pygame.draw.ellipse(surf,col,(sx+int(self.facing[0]*(s//3)),
                                       sy+int(self.facing[1]*(s//4)),
                                       s//2,s//2))
        # Wing hints
        pygame.draw.polygon(surf,tuple(max(0,c-30) for c in col),[
            (sx+s//2,sy+s//4),(sx-s//4,sy-s//8),(sx+s//4,sy+s//3)])
        pygame.draw.polygon(surf,tuple(max(0,c-30) for c in col),[
            (sx+s//2,sy+s//4),(sx+s+s//4,sy-s//8),(sx+3*s//4,sy+s//3)])
        pygame.draw.rect(surf,BLACK,(sx,sy,s,s),2)
        # HP bar (wider)
        bar_w=int(s*self.hp/self.max_hp)
        pygame.draw.rect(surf,DARK_RED,(sx,sy-8,s,5))
        pygame.draw.rect(surf,GREEN,(sx,sy-8,bar_w,5))
        f=_label_font(11);lbl=f.render(self.name,True,(255,100,50));shd=f.render(self.name,True,BLACK)
        lx=sx+s//2-lbl.get_width()//2
        surf.blit(shd,(lx+1,sy-20));surf.blit(lbl,(lx,sy-21))


_ENEMY_CLASSES={'slime':'Slime','bat':'Bat','spider':'Spider','goblin':'Goblin',
                'skeleton':'Skeleton','ghost':'Ghost','troll':'Troll','wolf':'Wolf',
                'giant_spider':'Spider','kelpie':'Kelpie','yeti':'Yeti',
                'ice_wraith':'IceWraith','scorpion':'Scorpion','mummy':'Mummy',
                'swamp_toad':'SwampToad','will_o':'WillOWisp',
                'mimic':'Mimic',
                'dragon':'Dragon','frost_dragon':'Dragon',
                'sand_dragon':'Dragon','swamp_dragon':'Dragon'}
_CLS_MAP={'Slime':Slime,'Bat':Bat,'Spider':Spider,'Goblin':Goblin,'Skeleton':Skeleton,
          'Ghost':Ghost,'Troll':Troll,'Wolf':Wolf,'Kelpie':Kelpie,'Yeti':Yeti,
          'IceWraith':IceWraith,'Scorpion':Scorpion,'Mummy':Mummy,
          'SwampToad':SwampToad,'WillOWisp':WillOWisp,
          'Mimic':Mimic,'Dragon':Dragon}

def spawn_enemy(etype,tx,ty,is_boss=False):
    cls_name=_ENEMY_CLASSES.get(etype,'Slime')
    cls=_CLS_MAP[cls_name]
    px=tx*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
    py=ty*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
    if cls is Dragon:
        return Dragon(px,py,is_boss=is_boss,variant=etype)
    return cls(px,py,is_boss=is_boss)


# ── Princess ──────────────────────────────────────────────────────────────────
def _trail_follow_pos(trail, owner, standoff):
    """Return a point `standoff` pixels behind owner in the trail."""
    for cx, cy in reversed(trail):
        if math.hypot(cx-owner.cx, cy-owner.cy) > standoff:
            return cx, cy
    return owner.cx, owner.cy


def _smooth_follow(cx, cy, x, y, trail, owner, vx, vy,
                   speed, ideal_tiles, wangle, result):
    """
    Spring-damper + wander steering for Pet and Princess.
    Returns new (x, y) and stores smoothed velocity + wander angle on result.

    * Spring pulls toward the "ideal ring" at `ideal_tiles` tiles from owner.
    * Wander adds continuous smooth random drift (random-walk angle, no timer).
    * Velocity is smoothed each frame → no jitter or discontinuous jumps.
    """
    import random as _rng_m
    IDEAL  = ideal_tiles * TILE_SIZE
    dist   = math.hypot(owner.cx - cx, owner.cy - cy)

    # ── Spring force toward ideal ring ─────────────────────────────────────
    spring_x = spring_y = 0.0
    if dist > 0.5:
        dx = owner.cx - cx; dy = owner.cy - cy
        d  = math.hypot(dx, dy)
        # signed displacement from ideal ring: positive = too far, negative = too close
        disp = d - IDEAL
        k    = 0.18   # spring stiffness (tune: higher = snappier)
        force = k * disp
        spring_x = (dx/d) * force
        spring_y = (dy/d) * force

    # ── Wander force (smooth random walk in angle space) ──────────────────
    # Angle drifts by a small Gaussian step each frame — no sudden direction flips
    new_wangle = wangle + _rng_m.gauss(0, 0.08)
    wander_strength = speed * 0.25   # wander at 25 % of max speed
    wander_x = math.cos(new_wangle) * wander_strength
    wander_y = math.sin(new_wangle) * wander_strength
    # Scale wander down when far from owner so it doesn't fight the spring
    if dist > IDEAL * 1.5:
        wf = max(0.0, 1.0 - (dist - IDEAL * 1.5) / IDEAL)
        wander_x *= wf; wander_y *= wf

    # ── Desired velocity = spring + wander, clamped to max speed ──────────
    des_x = spring_x + wander_x
    des_y = spring_y + wander_y
    des_spd = math.hypot(des_x, des_y)
    if des_spd > speed:
        des_x = des_x / des_spd * speed
        des_y = des_y / des_spd * speed

    # ── Smooth velocity (low-pass / exponential moving average) ───────────
    ALPHA = 0.22   # smoothing factor; lower = more inertia, less jitter
    new_vx = vx * (1 - ALPHA) + des_x * ALPHA
    new_vy = vy * (1 - ALPHA) + des_y * ALPHA

    # ── Apply and store state ──────────────────────────────────────────────
    result._vx     = new_vx
    result._vy     = new_vy
    result._wangle = new_wangle

    return x + new_vx, y + new_vy


class Princess:
    """A rescued princess that follows the player to the town shrine.
    Enemies treat her like a player target (she has alive, cx, cy, is_ghost).
    """
    SIZE = 20
    NAMES  = {9:"Princess Lyra",10:"Princess Frostine",11:"Princess Sola",12:"Princess Mira"}
    COLORS = {9:(255,180,210),10:(180,220,255),11:(255,220,150),12:(150,220,180)}

    def __init__(self, dungeon_id, x, y):
        self.dungeon_id = dungeon_id
        self.name       = self.NAMES.get(dungeon_id, "Princess")
        self.color      = self.COLORS.get(dungeon_id, (255,180,210))
        self.x          = float(x)
        self.y          = float(y)
        self.hp         = 40
        self.max_hp     = 40
        self.defense    = 0          # needed so melee damage calc works
        self.iframes    = 0
        # Player-compatible flags so enemies can target her
        self.alive      = True
        self.is_ghost   = False
        self.player_idx = -1      # marks her as non-player for some checks
        # state: 'following' → chase player; 'at_shrine' → wait in castle; 'saved'
        self.state      = 'following'
        self.follow_ref = None
        self._trail     = []
        self._vx = self._vy = 0.0   # smoothed velocity for spring-damper
        self._wangle    = 0.0       # wander angle (random-walk)

    @property
    def cx(self): return self.x + self.SIZE / 2
    @property
    def cy(self): return self.y + self.SIZE / 2
    @property
    def rect(self): return pygame.Rect(int(self.x), int(self.y), self.SIZE, self.SIZE)

    def take_damage(self, dmg, difficulty=0):
        """Called by enemies that hit her. Returns actual damage dealt."""
        if self.iframes > 0 or not self.alive: return 0
        self.hp       = max(0, self.hp - max(1, dmg))
        self.iframes  = 90
        if self.hp <= 0:
            self.alive     = False
            self.state     = 'at_shrine'
            self.follow_ref = None
        return dmg

    def dist_to(self, other):
        return math.hypot(other.cx - self.cx, other.cy - self.cy)

    def update(self, players, enemies, gmap=None):
        if self.state != 'following': return
        if self.iframes > 0:
            self.iframes -= 1
            if self.iframes == 0 and not self.alive:
                return

        # Reattach to nearest living non-ghost player
        if self.follow_ref is None or not getattr(self.follow_ref,'alive',False):
            living = [p for p in players
                      if getattr(p,'alive',False) and not getattr(p,'is_ghost',False)
                      and getattr(p,'player_idx',-1) >= 0]
            if living:
                self.follow_ref = min(living,
                    key=lambda p: math.hypot(p.cx-self.cx, p.cy-self.cy))

        owner = self.follow_ref
        if owner and self.alive:
            # Update trail
            last = self._trail[-1] if self._trail else None
            if last is None or math.hypot(owner.cx-last[0], owner.cy-last[1]) > TILE_SIZE*0.5:
                self._trail.append((owner.cx, owner.cy))
                if len(self._trail) > 40: self._trail.pop(0)

            nx, ny = _smooth_follow(
                self.cx, self.cy, self.x, self.y,
                self._trail, owner,
                vx=self._vx, vy=self._vy,
                speed=1.8, ideal_tiles=2.0, wangle=self._wangle,
                result=self)

            # Apply movement with wall collision (only when gmap is available)
            if gmap:
                dx = nx - self.x; dy = ny - self.y
                sz = self.SIZE; ts = TILE_SIZE
                def blocked(x, y):
                    for cx2,cy2 in [(x,y),(x+sz-1,y),(x,y+sz-1),(x+sz-1,y+sz-1)]:
                        t = gmap.get(int(cx2//ts), int(cy2//ts))
                        if not tile_walkable(t) and not tile_swimmable(t): return True
                    return False
                if dx and not blocked(self.x+dx, self.y): self.x += dx
                else: self._vx *= -0.3
                if dy and not blocked(self.x, self.y+dy): self.y += dy
                else: self._vy *= -0.3
            else:
                self.x, self.y = nx, ny

    def draw(self, surf, cam_x, cam_y, asset_mgr=None, brightness=255):
        if not self.alive or self.state != 'following': return
        sx = int(self.x) - cam_x; sy = int(self.y) - cam_y; sz = self.SIZE
        pygame.draw.ellipse(surf, self.color, (sx+3, sy+sz//3, sz-6, sz*2//3))
        pygame.draw.circle(surf, (255,220,185), (sx+sz//2, sy+sz//4), sz//4)
        crown_pts = [(sx+4,sy+sz//4-4),(sx+6,sy+sz//4-9),(sx+sz//2,sy+sz//4-6),
                     (sx+sz-6,sy+sz//4-9),(sx+sz-4,sy+sz//4-4)]
        pygame.draw.polygon(surf, (255,215,0), crown_pts)
        if self.hp < self.max_hp:
            frac = self.hp / self.max_hp
            pygame.draw.rect(surf, RED,   (sx, sy-6, sz, 4))
            pygame.draw.rect(surf, GREEN, (sx, sy-6, int(sz*frac), 4))


# ── Town NPCs ─────────────────────────────────────────────────────────────────
class Pet:
    """Companion entity created from a charmed enemy.
    Copies appearance and stats from the source mob; follows owner via trail,
    attacks only mobs that attacked it or that the player hit.
    Never targeted by player auto-aim or player melee/ranged.
    """
    _GHOST_ETYPES = {'ghost', 'ice_wraith', 'will_o'}

    def __init__(self, source):
        self.etype        = source.etype
        self.name         = f"[Pet] {source.name}"
        self.color        = source.color
        self.SIZE         = source.SIZE
        self.x            = float(source.x)
        self.y            = float(source.y)
        self.hp           = source.hp
        self.max_hp       = source.max_hp
        self.speed        = source.speed              # genuine mob speed
        self.damage       = source.damage
        self.defense      = source.defense
        self.attack_range = source.attack_range
        self._atk_cool_max= source.ATTACK_COOL
        self._cool        = 0
        self.iframes      = 0
        self.alive        = True
        self.is_ghost     = False   # needed for _nearest_player filtering
        self.player_idx   = -1      # marks as non-player in some checks
        self.owner        = None
        self._threats     = set()
        self._target      = None
        self._trail       = []
        self._was_just_hit = False
        self._vx = self._vy = 0.0   # smoothed velocity
        self._wangle      = 0.0     # wander angle
        self._is_ghost_pet = source.etype in self._GHOST_ETYPES
        self.animator     = getattr(source, 'animator', None)

    @property
    def cx(self): return self.x + self.SIZE / 2
    @property
    def cy(self): return self.y + self.SIZE / 2
    @property
    def rect(self): return pygame.Rect(int(self.x), int(self.y), self.SIZE, self.SIZE)

    def dist_to(self, other):
        return math.hypot(other.cx - self.cx, other.cy - self.cy)

    def take_damage(self, dmg, difficulty=0):
        if self.iframes > 0 or not self.alive: return 0
        actual = max(1, dmg - self.defense)
        self.hp = max(0, self.hp - actual)
        self.iframes = 60
        if self.hp <= 0:
            self.alive = False
        # Aggro back on whatever hit us — the game loop adds to threat set
        # by checking _was_just_hit flag
        self._was_just_hit = True
        return actual

    def register_threat(self, enemy):
        """Mark an enemy as a target (it attacked us or the owner)."""
        self._threats.add(id(enemy))

    def update(self, gmap, enemies):
        if not self.alive: return
        if self.iframes > 0: self.iframes -= 1
        if self._cool > 0:   self._cool   -= 1

        owner = self.owner

        # ── Update position trail ──────────────────────────────────────────
        if owner and getattr(owner, 'alive', False):
            last = self._trail[-1] if self._trail else None
            if last is None or math.hypot(owner.cx-last[0], owner.cy-last[1]) > TILE_SIZE*0.5:
                self._trail.append((owner.cx, owner.cy))
                if len(self._trail) > 40:
                    self._trail.pop(0)

        # ── Off-screen check: deaggro and teleport ────────────────────────
        if owner and getattr(owner, 'alive', False):
            dist_owner = math.hypot(owner.cx - self.cx, owner.cy - self.cy)
            if dist_owner > TILE_SIZE * 18:   # off-screen threshold
                self._threats.clear()
                self._target = None
                near = gmap.find_walkable_near(
                    int(owner.cx//TILE_SIZE), int(owner.cy//TILE_SIZE), 3)
                self.x = near[0]*TILE_SIZE + (TILE_SIZE-self.SIZE)//2
                self.y = near[1]*TILE_SIZE + (TILE_SIZE-self.SIZE)//2
                self._trail.clear()
                return

        # ── Pick attack target (registered threats only) ──────────────────
        live_threats = [e for e in enemies
                        if e.alive and id(e) in self._threats
                        and math.hypot(e.cx-self.cx, e.cy-self.cy) < TILE_SIZE*12]
        self._target = min(live_threats, key=lambda e: self.dist_to(e)) if live_threats else None

        # ── Combat ────────────────────────────────────────────────────────
        if self._target:
            dist = self.dist_to(self._target)
            if dist <= self.attack_range:
                if self._cool <= 0:
                    self._target.take_damage(self.damage)
                    if hasattr(self._target, 'on_attacked'):
                        self._target.on_attacked()
                    self._cool = self._atk_cool_max
                    self._threats.add(id(self._target))
                return   # stay in melee position
            else:
                dx = self._target.cx - self.cx; dy = self._target.cy - self.cy
                d  = math.hypot(dx, dy) or 1
                self._move(dx/d * self.speed, dy/d * self.speed, gmap)
            return

        # ── Follow owner (spring-damper steering + wander) ────────────────
        if owner and getattr(owner, 'alive', False):
            # Compute desired position via spring-damper
            nx, ny = _smooth_follow(
                self.cx, self.cy, self.x, self.y,
                self._trail, owner,
                vx=self._vx, vy=self._vy,
                speed=self.speed, ideal_tiles=1.5,
                wangle=self._wangle, result=self)
            # Apply through collision-aware _move
            self._move(nx - self.x, ny - self.y, gmap)

    def _move(self, dx, dy, gmap):
        sz  = self.SIZE
        mw  = gmap.width  * TILE_SIZE
        mh  = gmap.height * TILE_SIZE
        ghost = self._is_ghost_pet
        if dx != 0:
            nx = max(0, min(self.x + dx, mw - sz - 1))
            if ghost or not self._tile_blocked(nx, self.y, sz, gmap):
                self.x = nx
        if dy != 0:
            ny = max(0, min(self.y + dy, mh - sz - 1))
            if ghost or not self._tile_blocked(self.x, ny, sz, gmap):
                self.y = ny

    def _tile_blocked(self, x, y, sz, gmap):
        from constants import TILE_SIZE as TS
        for cx, cy in [(x,y),(x+sz-1,y),(x,y+sz-1),(x+sz-1,y+sz-1)]:
            t = gmap.get(int(cx//TS), int(cy//TS))
            from constants import tile_walkable, tile_swimmable
            if not tile_walkable(t) and not tile_swimmable(t):
                return True
        return False

    def draw(self, surf, cam_x, cam_y, asset_mgr=None, brightness=1.0):
        if not self.alive: return
        sx = int(self.x) - cam_x; sy = int(self.y) - cam_y
        sz = self.SIZE
        # Draw with a green tint to distinguish from hostile mobs
        col = tuple(min(255, int(c*0.7 + 80)) for c in self.color[:3])
        pygame.draw.rect(surf, col, (sx, sy, sz, sz), border_radius=4)
        pygame.draw.rect(surf, (80, 255, 80), (sx-2, sy-2, sz+4, sz+4), 2, border_radius=5)
        # HP bar
        frac = self.hp / self.max_hp
        pygame.draw.rect(surf, RED,   (sx, sy-5, sz, 3))
        pygame.draw.rect(surf, GREEN, (sx, sy-5, int(sz*frac), 3))
        # Name tag
        try:
            fnt = pygame.font.SysFont("monospace", 8)
            lbl = fnt.render(self.etype[:6], True, (200,255,200))
            surf.blit(lbl, (sx, sy+sz+1))
        except Exception: pass


class NPC:
    """Base for non-hostile town characters (Lorekeeper, Trader)."""
    SIZE = ENTITY_SIZE

    def __init__(self, tx, ty, name, color, dialog_pages):
        self.tx      = tx; self.ty = ty
        self.name    = name
        self.color   = color
        self.pages   = dialog_pages   # list of strings
        self.page    = 0
        self.x       = tx * TILE_SIZE + (TILE_SIZE - self.SIZE) // 2
        self.y       = ty * TILE_SIZE + (TILE_SIZE - self.SIZE) // 2

    @property
    def cx(self): return self.x + self.SIZE / 2
    @property
    def cy(self): return self.y + self.SIZE / 2
    @property
    def rect(self): return pygame.Rect(int(self.x), int(self.y), self.SIZE, self.SIZE)

    def next_page(self):
        self.page = (self.page + 1) % len(self.pages)

    def current_text(self): return self.pages[self.page]

    def draw(self, surf, cam_x, cam_y, asset_mgr=None, brightness=255):
        sx = int(self.x) - cam_x; sy = int(self.y) - cam_y
        sz = self.SIZE
        pygame.draw.rect(surf, self.color, (sx, sy, sz, sz), border_radius=4)
        pygame.draw.rect(surf, WHITE,       (sx, sy, sz, sz), 2,  border_radius=4)
        # Name tag
        font = pygame.font.SysFont("monospace", 9, bold=False)
        label = font.render(self.name[:8], True, YELLOW)
        surf.blit(label, (sx - label.get_width()//2 + sz//2, sy - 12))


class Lorekeeper(NPC):
    DIALOG = [
        "Welcome, brave soul!\nI am the Lorekeeper.\nListen well...",
        "Four dragons dwell in\nthe castle dungeons\nbeyond the wilds.",
        "Each holds a princess\ncaptive. Slay the\ndragon to free her.",
        "Lead her safely to\nthe shrine here in\ntown to save her.",
        "If she falls in battle\nshe returns to the\ncastle shrine. Revive\nher there.",
        "Gates: North=Snow,\nSouth=Desert,\nEast=Forest,\nWest=Swamp.",
        "Each biome holds a\nhaunted town. Beyond\nlies the castle.",
        "Save all four and\nthe realm will be\nfree. Good luck!",
    ]

    def __init__(self, tx, ty):
        super().__init__(tx, ty, "Sage", (180, 140, 220), self.DIALOG)


class Trader(NPC):
    # (iid, buy_price, sell_price)  — buy=from trader, sell=to trader
    STOCK = [
        ('sword',      80,  30),
        ('axe',        60,  22),
        ('pickaxe',    55,  20),
        ('knife',      30,  10),
        ('bow',        90,  35),
        ('spear',      70,  25),
        ('shield',     75,  28),
        ('potion',     25,   8),
        ('mana_pot',   30,  10),
        ('bread',      12,   3),
        ('arrow',       5,   2),
        ('stone',       4,   1),
        ('rope',       18,   5),
        ('lantern',    40,  14),
        ('torch',      15,   4),
        ('candle',     10,   3),
        ('charm_spell',350,   0),   # charm — cannot sell back
    ]
    DIALOG = [
        "Greetings! I trade\ngold for goods.",
        "I buy your loot too!\nThough not dragon\ntreasure — too hot!",
        "The Charm Spell is\npricey but powerful.\nOne use per spell.",
    ]

    def __init__(self, tx, ty):
        super().__init__(tx, ty, "Trader", (200, 160, 80), self.DIALOG)
