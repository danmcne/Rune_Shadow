"""
Rune & Shadow - Game v3
Multi-map world: Town + 4 biomes (N/S/E/W) + multi-level dungeons.
All fixes applied:
  - Drop no longer duplicates items (remove first, then spawn GroundItem)
  - Chest loot goes to nearest walkable tile or directly to inventory
  - Boss never respawns on load (boss_killed flag persisted per dungeon)
  - Unequip: X key in play, or U in inventory
  - Aim mode toggle: TAB key
  - Save tracks boss_killed per dungeon
  - Multi-level dungeons with stairs down
  - Gate travel between town and biomes
"""
import sys, json, os, random, math
import pygame

from constants  import *
from generation import build_town, build_biome_map, build_dungeon_level, build_dungeon
from game_map   import GameMap, GroundItem
from entities   import Player, spawn_enemy, Projectile
from items      import make_item, ITEMS, CHEST_LOOT_COMMON, CHEST_LOOT_UNCOMMON, CHEST_LOOT_RARE
from asset_manager import AssetManager
from ui import (HUD, InventoryScreen,
                draw_main_menu, draw_game_over, draw_paused, draw_win, draw_text)

SAVE_FILE = "rune_shadow_save.json"


# ═══════════════════════════════════════════════════════════════════════════════
#  Camera
# ═══════════════════════════════════════════════════════════════════════════════
class Camera:
    def __init__(self): self.x=0.0; self.y=0.0
    def follow(self, player, mw, mh):
        tx=player.x-SCREEN_WIDTH//2; ty=player.y-VIEWPORT_H//2
        self.x+=(tx-self.x)*0.12; self.y+=(ty-self.y)*0.12
        self.x=max(0,min(self.x,mw-SCREEN_WIDTH)); self.y=max(0,min(self.y,mh-VIEWPORT_H))
    def snap(self, player, mw, mh):
        self.x=max(0,min(player.x-SCREEN_WIDTH//2, mw-SCREEN_WIDTH))
        self.y=max(0,min(player.y-VIEWPORT_H//2,   mh-VIEWPORT_H))
    @property
    def ix(self): return int(self.x)
    @property
    def iy(self): return int(self.y)


# ═══════════════════════════════════════════════════════════════════════════════
#  Message Log
# ═══════════════════════════════════════════════════════════════════════════════
class MessageLog:
    def __init__(self): self._msgs=[]
    def add(self, text, color=WHITE):
        if text.startswith("__"): return
        self._msgs.append([text,color,MSG_DURATION])
        if len(self._msgs)>MSG_MAX*2: self._msgs=self._msgs[-MSG_MAX:]
    def update(self): self._msgs=[[t,c,tm-1] for t,c,tm in self._msgs if tm>1]
    def recent(self, n=6): return [(t,c) for t,c,_ in self._msgs[-n:]]


# ═══════════════════════════════════════════════════════════════════════════════
#  Cheat Engine
# ═══════════════════════════════════════════════════════════════════════════════
CHEAT_CODES = {
    "GODMODE":"god","MAXHP":"maxhp","MAXMANA":"maxmana","GIVEALL":"giveall",
    "NOCLIP":"noclip","RESPAWN":"respawn","LEVELUP":"levelup","FULLCLEAR":"fullclear",
}
class CheatEngine:
    def __init__(self): self._buf=""; self.god_mode=False; self.no_clip=False
    def type_char(self,ch): self._buf=(self._buf+ch.upper())[-12:]
    def check(self):
        for code,tag in CHEAT_CODES.items():
            if self._buf.endswith(code): self._buf=""; return tag
        return None
    @property
    def display(self):
        t=[]
        if self.god_mode: t.append("GOD")
        if self.no_clip:  t.append("NOCLIP")
        return " ".join(t)


# ═══════════════════════════════════════════════════════════════════════════════
#  Game
# ═══════════════════════════════════════════════════════════════════════════════
class Game:
    def __init__(self, screen, clock, seed=12345):
        self.screen=screen; self.clock=clock; self.seed=seed
        self._state=ST_MENU; self._menu_cursor=0; self._pause_cursor=0
        self._seed_str=str(seed); self._difficulty=DIFFICULTY_NORMAL
        self.player=None; self._maps={}   # map_key -> GameMap
        self.current_map=None; self._current_map_name="Town"
        self.camera=Camera(); self.projectiles=[]; self.log=MessageLog()
        self.hud=HUD(); self.inv_screen=InventoryScreen()
        self.rng=random.Random(seed); self._score=0
        self._viewport=pygame.Surface((SCREEN_WIDTH,VIEWPORT_H))
        self._pending_msgs=[]; self._cheats=CheatEngine()
        self.asset_mgr=AssetManager()
        # Dungeon level maps: (dun_id, level) -> GameMap
        self._dungeon_maps={}
        # boss_killed: dun_id -> bool  (persisted in save)
        self._boss_killed={}

    def run(self):
        while True:
            self.clock.tick(FPS)
            self._handle_events(); self._update(); self._draw()
            pygame.display.flip()

    # ── Events ───────────────────────────────────────────────────────────────
    def _handle_events(self):
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            if   self._state==ST_MENU:      self._ev_menu(ev)
            elif self._state==ST_PLAY:      self._ev_play(ev)
            elif self._state==ST_INVENTORY: self._ev_inv(ev)
            elif self._state==ST_PAUSED:    self._ev_pause(ev)
            elif self._state in (ST_GAMEOVER,ST_WIN):
                if ev.type==pygame.KEYDOWN and ev.key==pygame.K_RETURN:
                    self._state=ST_MENU

    def _ev_menu(self, ev):
        if ev.type!=pygame.KEYDOWN: return
        has_save=os.path.exists(SAVE_FILE)
        n=3 if has_save else 2
        if ev.key==pygame.K_UP:    self._menu_cursor=(self._menu_cursor-1)%n
        elif ev.key==pygame.K_DOWN: self._menu_cursor=(self._menu_cursor+1)%n
        elif ev.key==pygame.K_LEFT: self._difficulty=(self._difficulty-1)%3
        elif ev.key==pygame.K_RIGHT:self._difficulty=(self._difficulty+1)%3
        elif ev.key==pygame.K_RETURN: self._menu_select(has_save)
        elif ev.key==pygame.K_BACKSPACE: self._seed_str=self._seed_str[:-1] or "0"
        elif ev.unicode.isdigit() and len(self._seed_str)<10:
            self._seed_str+=ev.unicode
            try: self.seed=int(self._seed_str)
            except ValueError: pass

    def _menu_select(self, has_save):
        opts=["new"]+( ["load"] if has_save else [])+["quit"]
        ch=opts[self._menu_cursor]
        if ch=="new":   self._start_game()
        elif ch=="load":
            if not self._load_game(): self.log.add("Corrupt save — new game.",RED); self._start_game()
        elif ch=="quit": pygame.quit(); sys.exit()

    def _ev_pause(self, ev):
        if ev.type!=pygame.KEYDOWN: return
        N=4
        if ev.key==pygame.K_ESCAPE:  self._state=ST_PLAY
        elif ev.key==pygame.K_UP:    self._pause_cursor=(self._pause_cursor-1)%N
        elif ev.key==pygame.K_DOWN:  self._pause_cursor=(self._pause_cursor+1)%N
        elif ev.key==pygame.K_RETURN: self._pause_select()

    def _pause_select(self):
        c=self._pause_cursor
        if c==0: self._state=ST_PLAY
        elif c==1: self._start_game()
        elif c==2: self._save_game(); pygame.quit(); sys.exit()
        elif c==3: pygame.quit(); sys.exit()

    def _ev_play(self, ev):
        if ev.type==pygame.KEYDOWN:
            if ev.unicode and ev.unicode.isalpha():
                self._cheats.type_char(ev.unicode)
                tag=self._cheats.check()
                if tag: self._apply_cheat(tag)
            if ev.key==pygame.K_ESCAPE:
                self._state=ST_PAUSED; self._pause_cursor=0
            elif ev.key==pygame.K_i: self._state=ST_INVENTORY
            elif ev.key==pygame.K_SPACE:
                self.player.attack(self.current_map,self.current_map.entities,
                                   self.projectiles,self._pending_msgs)
            elif ev.key==pygame.K_e: self._interact()
            elif ev.key==pygame.K_q: self.player.cycle_hotbar(-1)
            elif ev.key==pygame.K_f: self.player.cycle_hotbar(1)
            elif ev.key==pygame.K_TAB: self.player.toggle_aim_mode(); self.log.add(f"Aim: {self.player.aim_mode}",CYAN)
            elif ev.key==pygame.K_x: self.player.unequip_slot(); self.log.add("Slot cleared.",GRAY)
            elif pygame.K_1<=ev.key<=pygame.K_8: self.player.equipped=ev.key-pygame.K_1
        elif ev.type==pygame.MOUSEBUTTONDOWN:
            if ev.button==1:
                self.player.attack(self.current_map,self.current_map.entities,
                                   self.projectiles,self._pending_msgs)
            elif ev.button==4: self.player.cycle_hotbar(-1)
            elif ev.button==5: self.player.cycle_hotbar(1)

    def _ev_inv(self, ev):
        if ev.type!=pygame.KEYDOWN: return
        close=self.inv_screen.handle_key(ev,self.player,self._pending_msgs)
        # Handle drop: item already removed in handle_key; now spawn GroundItem
        for msg_text,_ in self._pending_msgs:
            if msg_text.startswith("__DROP__:"):
                iid=msg_text.split(":",1)[1]
                if iid in ITEMS:
                    ptx=int(self.player.cx//TILE_SIZE); pty=int(self.player.cy//TILE_SIZE)
                    # Find nearest walkable tile
                    target=self.current_map.find_walkable_near(ptx,pty,3)
                    gi=GroundItem(make_item(iid),target[0],target[1],1,
                                  lifetime=DROPPED_ITEM_LIFETIME_FRAMES)
                    self.current_map.ground_items.append(gi)
        if close: self._state=ST_PLAY

    # ── Cheats ───────────────────────────────────────────────────────────────
    def _apply_cheat(self, tag):
        p=self.player
        if tag=="god":
            self._cheats.god_mode=not self._cheats.god_mode
            self.log.add(f"GOD MODE {'ON' if self._cheats.god_mode else 'OFF'}",PURPLE)
        elif tag=="maxhp":   p.hp=p.max_hp; self.log.add("HP restored!",GREEN)
        elif tag=="maxmana": p.mana=p.max_mana; self.log.add("Mana restored!",BLUE)
        elif tag=="giveall":
            for iid in ITEMS: p.inventory.add(make_item(iid),5)
            self.log.add("All items!",GOLD)
        elif tag=="noclip":
            self._cheats.no_clip=not self._cheats.no_clip
            self.log.add(f"NOCLIP {'ON' if self._cheats.no_clip else 'OFF'}",PURPLE)
        elif tag=="respawn": self._respawn_map(self.current_map); self.log.add("Respawned!",ORANGE)
        elif tag=="levelup": p.max_hp+=20;p.hp=p.max_hp;p.max_mana+=20;p.mana=p.max_mana; self.log.add("+20 HP/MP",GOLD)
        elif tag=="fullclear":
            for e in list(self.current_map.entities): e.hp=0; e.alive=False
            self.log.add("All cleared!",YELLOW)

    def _respawn_map(self, gmap):
        gmap.entities.clear()
        if gmap.is_dungeon: self._spawn_dungeon_ents(gmap)
        else: self._populate_biome_ents(gmap)

    # ── Interaction ──────────────────────────────────────────────────────────
    def _interact(self):
        p=self.player; gmap=self.current_map
        fx,fy=p.facing
        tx=int((p.cx+fx*TILE_SIZE*0.6)//TILE_SIZE)
        ty=int((p.cy+fy*TILE_SIZE*0.6)//TILE_SIZE)
        t=gmap.get(tx,ty)

        if t in GATE_TILES:
            self._use_gate(gmap,t,tx,ty)
        elif t==T_ENTRANCE:
            self._enter_dungeon_from_map(gmap,tx,ty)
        elif t==T_STAIRS_UP and gmap.is_dungeon:
            self._ascend_dungeon()
        elif t==T_STAIRS_DOWN and gmap.is_dungeon:
            self._descend_dungeon()
        elif t==T_CHEST and (tx,ty) not in gmap.chest_opened:
            self._open_chest(gmap,tx,ty)
        elif t==T_SHRINE:
            p.hp=p.max_hp; p.mana=p.max_mana
            self._save_game(); self.log.add("Shrine heals you — saved!",CYAN)

        # Ground item pickup at player tile
        ptx=int(p.cx//TILE_SIZE); pty=int(p.cy//TILE_SIZE)
        remove=[]
        for gi in gmap.ground_items:
            if gi.tx==ptx and gi.ty==pty:
                if p.inventory.add(gi.item,gi.count):
                    self.log.add(f"Picked up {gi.item.name} x{gi.count}.",WHITE)
                    remove.append(gi)
        for gi in remove: gmap.ground_items.remove(gi)

    def _use_gate(self, gmap, gate_tile, tx, ty):
        mk=gmap.map_key
        dest_map_key=GATE_DESTINATIONS.get(mk,{}).get(gate_tile)
        if dest_map_key is None:
            self.log.add("Nowhere to go.",GRAY); return
        dest_map=self._get_or_build_map(dest_map_key)
        # Place player near the matching return gate
        return_gate={MAP_NORTH:T_GATE_S,MAP_SOUTH:T_GATE_N,
                     MAP_EAST:T_GATE_W, MAP_WEST:T_GATE_E,
                     MAP_TOWN:{ T_GATE_N:T_GATE_S,T_GATE_S:T_GATE_N,
                                T_GATE_E:T_GATE_W,T_GATE_W:T_GATE_E}.get(gate_tile)
                    }.get(dest_map_key)
        spawn_tx,spawn_ty=self._find_gate_spawn(dest_map,return_gate)
        self.player.x=spawn_tx*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
        self.player.y=spawn_ty*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
        self.current_map=dest_map
        self._current_map_name=BIOME_NAMES.get(dest_map_key,dest_map_key.title())
        if dest_map_key==MAP_TOWN: self._current_map_name="Town"
        self.projectiles.clear()
        self.camera.snap(self.player,dest_map.width*TILE_SIZE,dest_map.height*TILE_SIZE)
        self.log.add(f"Entered {self._current_map_name}.",ORANGE)

    def _find_gate_spawn(self, gmap, gate_tile_type):
        """Find a walkable tile 2 steps inside from the gate."""
        for y in range(gmap.height):
            for x in range(gmap.width):
                if gmap.get(x,y)==gate_tile_type:
                    # Step inward depending on gate direction
                    offsets={T_GATE_N:(0,2),T_GATE_S:(0,-2),
                             T_GATE_E:(-2,0),T_GATE_W:(2,0)}
                    dx,dy=offsets.get(gate_tile_type,(0,0))
                    nx,ny=x+dx,y+dy
                    if gmap.in_bounds(nx,ny) and gmap.walkable(nx,ny):
                        return (nx,ny)
                    # fallback: find any walkable nearby
                    return gmap.find_walkable_near(x,y,5)
        # fallback to centre
        return gmap.find_walkable_near(gmap.width//2,gmap.height//2,10)

    def _get_or_build_map(self, map_key):
        if map_key not in self._maps:
            if map_key==MAP_TOWN:
                gmap,_=build_town(self.seed)
                self._populate_town_ents(gmap)
                self._maps[map_key]=gmap
            else:
                gmap=build_biome_map(self.seed,map_key)
                self._populate_biome_ents(gmap)
                self._maps[map_key]=gmap
        return self._maps[map_key]

    # ── Dungeon travel ───────────────────────────────────────────────────────
    def _enter_dungeon_from_map(self, gmap, tx, ty):
        dun_id=None
        for dtx,dty,did in getattr(gmap,'biome_dungeon_positions',[]):
            if dtx==tx and dty==ty: dun_id=did; break
        if dun_id is None:
            self.log.add("Unknown dungeon.",RED); return
        self._enter_dungeon(dun_id,0,gmap.map_key,tx,ty)

    def _enter_dungeon(self, dun_id, level, return_map_key, ow_tx, ow_ty):
        key=(dun_id,level)
        if key not in self._dungeon_maps:
            dmap=build_dungeon_level(self.seed,dun_id,level)
            dmap.ow_entrance=(ow_tx,ow_ty)
            dmap.return_map_key=return_map_key
            # Don't spawn boss if already killed
            self._spawn_dungeon_ents(dmap)
            self._dungeon_maps[key]=dmap
        dmap=self._dungeon_maps[key]
        ex,ey=dmap.entrance_tile
        self.player.x=ex*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
        self.player.y=ey*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
        self.current_map=dmap
        lvl_str=f" (L{level+1})" if DUNGEONS[dun_id]['levels']>1 else ""
        self._current_map_name=DUNGEONS[dun_id]['name']+lvl_str
        self.projectiles.clear()
        self.camera.snap(self.player,dmap.width*TILE_SIZE,dmap.height*TILE_SIZE)
        self.log.add(f"You enter {self._current_map_name}!",ORANGE)

    def _ascend_dungeon(self):
        dmap=self.current_map
        did=dmap.dungeon_id; lvl=dmap.dungeon_level
        if lvl==0:
            # Exit to overworld/biome
            ret_key=getattr(dmap,'return_map_key',MAP_EAST)
            ret_map=self._get_or_build_map(ret_key)
            ox,oy=dmap.ow_entrance
            self.player.x=ox*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
            self.player.y=oy*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
            self.current_map=ret_map
            self._current_map_name=BIOME_NAMES.get(ret_key,ret_key.title())
        else:
            # Go up one level
            self._enter_dungeon(did,lvl-1,
                                getattr(dmap,'return_map_key',MAP_EAST),
                                *dmap.ow_entrance)
            return
        self.projectiles.clear()
        self.camera.snap(self.player,self.current_map.width*TILE_SIZE,
                                     self.current_map.height*TILE_SIZE)
        self.log.add("You emerge.",GREEN)

    def _descend_dungeon(self):
        dmap=self.current_map
        did=dmap.dungeon_id; lvl=dmap.dungeon_level
        next_lvl=lvl+1
        if next_lvl>=DUNGEONS[did]['levels']:
            self.log.add("No deeper levels.",GRAY); return
        ret_key=getattr(dmap,'return_map_key',MAP_EAST)
        ox,oy=dmap.ow_entrance
        self._enter_dungeon(did,next_lvl,ret_key,ox,oy)

    def _spawn_dungeon_ents(self, dmap):
        boss_killed=self._boss_killed.get((dmap.dungeon_id,dmap.dungeon_level),False)
        for sp in getattr(dmap,'enemy_spawns',[]):
            if sp.get('boss') and boss_killed: continue   # skip dead boss
            try:
                e=spawn_enemy(sp['type'],sp['tx'],sp['ty'],is_boss=sp.get('boss',False))
                dmap.entities.append(e)
            except Exception: pass
        for sp in getattr(dmap,'item_spawns',[]):
            try:
                gi=GroundItem(make_item(sp['iid']),sp['tx'],sp['ty'],sp['count'])
                dmap.ground_items.append(gi)
            except Exception: pass

    # ── Chest ────────────────────────────────────────────────────────────────
    def _open_chest(self, gmap, tx, ty):
        gmap.chest_opened.add((tx,ty))
        floor_t=(DUNGEONS[gmap.dungeon_id]['floor'] if gmap.is_dungeon else T_GRASS)
        gmap.set(tx,ty,floor_t)
        drops=[]
        for _ in range(self.rng.randint(3,6)):
            drops.append((self.rng.choice(CHEST_LOOT_COMMON),self.rng.randint(1,4)))
        for _ in range(self.rng.randint(1,2)):
            drops.append((self.rng.choice(CHEST_LOOT_UNCOMMON),1))
        if self.rng.random()<0.20:
            drops.append((self.rng.choice(CHEST_LOOT_RARE),1))

        player=self.player
        for iid,count in drops:
            try:
                it=make_item(iid)
                # Find a walkable tile near the chest
                target=gmap.find_walkable_near(tx,ty,4)
                if target and gmap.walkable(*target):
                    gmap.ground_items.append(
                        GroundItem(it,target[0],target[1],count,
                                   lifetime=DROPPED_ITEM_LIFETIME_FRAMES*4))
                else:
                    # Fallback: directly to inventory
                    player.inventory.add(it,count)
                    self.log.add(f"Got {it.name} x{count}!",GOLD)
            except KeyError: pass
        self.log.add(f"Chest yields {len(drops)} items!",GOLD)

    # ── New Game ─────────────────────────────────────────────────────────────
    def _start_game(self):
        try: self.seed=int(self._seed_str) if self._seed_str else 12345
        except ValueError: self.seed=12345
        self.rng=random.Random(self.seed)
        self.log=MessageLog(); self.projectiles=[]
        self._dungeon_maps={}; self._maps={}; self._boss_killed={}
        self._pending_msgs=[]; self._score=0
        self._cheats=CheatEngine(); self._pause_cursor=0

        # Build starting town
        town_map,start_tile=build_town(self.seed)
        self._maps[MAP_TOWN]=town_map
        self._populate_town_ents(town_map)

        stx,sty=start_tile
        px=stx*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
        py=sty*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
        self.player=Player(px,py)

        self.current_map=town_map; self._current_map_name="Town"
        self.camera=Camera()
        self.camera.snap(self.player,town_map.width*TILE_SIZE,town_map.height*TILE_SIZE)
        self.inv_screen=InventoryScreen()

        self.log.add("Welcome to Rune & Shadow!",CYAN)
        self.log.add("E=Interact/Gate  TAB=Toggle aim  X=Unequip  I=Inventory",WHITE)
        self.log.add("Gates N/S/E/W lead to different biomes.",LIGHT_GRAY)
        self._state=ST_PLAY

    def _populate_town_ents(self, gmap):
        rng=self.rng
        # A few friendly wandering NPCs (use bat/slime as placeholder – no aggro)
        # Just scatter some items for now; town is a safe hub
        for _ in range(15):
            tx=rng.randint(2,TOWN_W-2); ty=rng.randint(2,TOWN_H-2)
            if not gmap.walkable(tx,ty): continue
            iid=rng.choice(['mushroom','herb','coin','coin','stone','bread','arrow'])
            gmap.ground_items.append(GroundItem(make_item(iid),tx,ty,rng.randint(1,3)))

    def _populate_biome_ents(self, gmap):
        rng=self.rng
        mk=gmap.map_key
        W,H=gmap.width,gmap.height

        etype_pools={
            MAP_EAST: ['wolf','wolf','goblin','slime','slime','bat','bat','spider'],
            MAP_NORTH:['yeti','yeti','bat','skeleton','ice_wraith'],
            MAP_SOUTH:['scorpion','scorpion','goblin','mummy','skeleton'],
            MAP_WEST: ['swamp_toad','swamp_toad','slime','spider','will_o','ghost'],
        }
        water_ents={MAP_EAST:'kelpie',MAP_WEST:'swamp_toad',
                    MAP_NORTH:'kelpie',MAP_SOUTH:'kelpie'}
        pool=etype_pools.get(mk,['slime','bat'])

        for _ in range(50):
            tx=rng.randint(5,W-5); ty=rng.randint(5,H-5)
            if not gmap.walkable(tx,ty): continue
            # Don't spawn near gate tiles
            t=gmap.get(tx,ty)
            if t in GATE_TILES: continue
            e=spawn_enemy(rng.choice(pool),tx,ty)
            gmap.entities.append(e)

        # Water enemies
        water_e=water_ents.get(mk,'kelpie')
        for _ in range(10):
            tx=rng.randint(5,W-5); ty=rng.randint(5,H-5)
            if tile_swimmable(gmap.get(tx,ty)):
                gmap.entities.append(spawn_enemy(water_e,tx,ty))

        # Ground items
        for _ in range(25):
            tx=rng.randint(5,W-5); ty=rng.randint(5,H-5)
            if not gmap.walkable(tx,ty): continue
            iid=rng.choice(['mushroom','herb','stone','stone','coin','blue_flower','bread','rope'])
            gmap.ground_items.append(GroundItem(make_item(iid),tx,ty,rng.randint(1,3)))

    # ── Save / Load ──────────────────────────────────────────────────────────
    def _save_game(self):
        p=self.player
        dmap=self.current_map
        data={
            "seed":self.seed,"difficulty":self._difficulty,"score":self._score,
            "player":{
                "x":p.x,"y":p.y,"hp":p.hp,"max_hp":p.max_hp,
                "mana":p.mana,"max_mana":p.max_mana,"gold":p.inventory.gold,
                "hotbar":p.hotbar,
                "inventory":{it.iid:cnt for it,cnt in p.inventory._slots},
                "aim_mode":p.aim_mode,
            },
            "map_key":dmap.map_key,
            "dungeon_id":dmap.dungeon_id if dmap.is_dungeon else -1,
            "dungeon_level":dmap.dungeon_level if dmap.is_dungeon else 0,
            "boss_killed":{f"{k[0]}_{k[1]}":v for k,v in self._boss_killed.items()},
            "chest_opened":{mk:list(m.chest_opened) for mk,m in self._maps.items()},
            "dungeon_chests":{f"{k[0]}_{k[1]}":list(v.chest_opened)
                              for k,v in self._dungeon_maps.items()},
        }
        try:
            with open(SAVE_FILE,"w") as f: json.dump(data,f,indent=2)
            self.log.add("Game saved.",GREEN)
        except Exception as ex: self.log.add(f"Save failed: {ex}",RED)

    def _load_game(self):
        try:
            with open(SAVE_FILE) as f: data=json.load(f)
            self.seed=data["seed"]; self._seed_str=str(self.seed)
            self._difficulty=data.get("difficulty",DIFFICULTY_NORMAL)
            self._score=data.get("score",0)
            self.rng=random.Random(self.seed)
            self.log=MessageLog(); self.projectiles=[]
            self._dungeon_maps={}; self._maps={}
            self._pending_msgs=[]; self._cheats=CheatEngine()

            # Restore boss kills
            self._boss_killed={}
            for ks,v in data.get("boss_killed",{}).items():
                parts=ks.split("_"); self._boss_killed[(int(parts[0]),int(parts[1]))]=v

            # Rebuild town and any biome maps in save
            town_map,_=build_town(self.seed)
            self._maps[MAP_TOWN]=town_map
            self._populate_town_ents(town_map)

            for mk in data.get("chest_opened",{}).keys():
                if mk==MAP_TOWN: continue
                try:
                    bmap=build_biome_map(self.seed,mk)
                    bmap.chest_opened=set(tuple(c) for c in data["chest_opened"].get(mk,[]))
                    self._populate_biome_ents(bmap)
                    self._maps[mk]=bmap
                except Exception: pass

            self._maps[MAP_TOWN].chest_opened=set(
                tuple(c) for c in data.get("chest_opened",{}).get(MAP_TOWN,[]))

            # Restore dungeon maps
            for ks,chests in data.get("dungeon_chests",{}).items():
                parts=ks.split("_"); did,lvl=int(parts[0]),int(parts[1])
                try:
                    dmap=build_dungeon_level(self.seed,did,lvl)
                    dmap.chest_opened=set(tuple(c) for c in chests)
                    dmap.return_map_key=DUNGEONS[did].get('biome',MAP_EAST)
                    self._spawn_dungeon_ents(dmap)
                    self._dungeon_maps[(did,lvl)]=dmap
                except Exception: pass

            pd=data["player"]
            self.player=Player(pd["x"],pd["y"])
            self.player.hp=pd["hp"]; self.player.max_hp=pd["max_hp"]
            self.player.mana=pd["mana"]; self.player.max_mana=pd["max_mana"]
            self.player.inventory.gold=pd["gold"]
            self.player.hotbar=pd["hotbar"]
            self.player.aim_mode=pd.get("aim_mode","mouse")
            self.player.inventory._slots.clear()
            for iid,cnt in pd["inventory"].items():
                if iid in ITEMS:
                    self.player.inventory._slots.append([make_item(iid),cnt])

            mk=data.get("map_key",MAP_TOWN)
            did=data.get("dungeon_id",-1)
            lvl=data.get("dungeon_level",0)
            if did>=0 and (did,lvl) in self._dungeon_maps:
                self.current_map=self._dungeon_maps[(did,lvl)]
                self._current_map_name=DUNGEONS[did]['name']
            elif mk in self._maps:
                self.current_map=self._maps[mk]
                self._current_map_name=BIOME_NAMES.get(mk,mk.title())
                if mk==MAP_TOWN: self._current_map_name="Town"
            else:
                self.current_map=town_map; self._current_map_name="Town"

            self.camera=Camera()
            self.camera.snap(self.player,self.current_map.width*TILE_SIZE,
                                          self.current_map.height*TILE_SIZE)
            self.inv_screen=InventoryScreen()
            self.log.add("Save loaded. Welcome back!",CYAN)
            self._state=ST_PLAY; return True
        except Exception as ex:
            print(f"Load error: {ex}"); return False

    # ── Update ───────────────────────────────────────────────────────────────
    def _update(self):
        if self._state!=ST_PLAY: return
        gmap=self.current_map; player=self.player; self._pending_msgs=[]

        if self._cheats.god_mode:
            player.hp=player.max_hp; player.mana=player.max_mana
            player.iframes=PLAYER_IFRAMES

        keys=pygame.key.get_pressed()
        player.update(keys,gmap,gmap.entities,self.projectiles,self._pending_msgs,
                      cam_x=self.camera.ix,cam_y=self.camera.iy)

        if self._cheats.no_clip:
            dx=dy=0.0; spd=PLAYER_SPEED
            if keys[pygame.K_LEFT]  or keys[pygame.K_a]: dx-=spd
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]: dx+=spd
            if keys[pygame.K_UP]    or keys[pygame.K_w]: dy-=spd
            if keys[pygame.K_DOWN]  or keys[pygame.K_s]: dy+=spd
            if dx and dy: dx*=0.7071; dy*=0.7071
            player.x+=dx; player.y+=dy
            mw=gmap.width*TILE_SIZE; mh=gmap.height*TILE_SIZE
            player.x=max(0,min(player.x,mw-ENTITY_SIZE))
            player.y=max(0,min(player.y,mh-ENTITY_SIZE))

        # Enemies
        for e in list(gmap.entities):
            if e.alive:
                e.update(player,gmap,self.projectiles,self._pending_msgs)
            else:
                drops=e.get_drops(self.rng)
                tx=int(e.cx//TILE_SIZE); ty=int(e.cy//TILE_SIZE)
                for it in drops:
                    target=gmap.find_walkable_near(tx,ty,2)
                    gmap.ground_items.append(
                        GroundItem(it,target[0],target[1],1,
                                   lifetime=DROPPED_ITEM_LIFETIME_FRAMES))
                self._score+=10*(5 if e.is_boss else 1)
                # Track boss kill
                if e.is_boss and gmap.is_dungeon:
                    self._boss_killed[(gmap.dungeon_id,gmap.dungeon_level)]=True
                # Respawn queue (overworld non-bosses only)
                if not gmap.is_dungeon and not e.is_boss:
                    gmap.respawn_queue.append([OVERWORLD_MOB_RESPAWN_FRAMES,
                                               {'type':e.etype,'tx':tx,'ty':ty}])
                gmap.entities.remove(e)

        # Projectiles
        for proj in list(self.projectiles):
            proj.update(gmap,player,gmap.entities,self._pending_msgs)
            if not proj.alive: self.projectiles.remove(proj)

        # Ground items
        expired=[gi for gi in gmap.ground_items if gi.update() or gi.expired]
        for gi in expired: gmap.ground_items.remove(gi)

        # Auto-coin pickup
        ptx=int(player.cx//TILE_SIZE); pty=int(player.cy//TILE_SIZE)
        coins=[gi for gi in gmap.ground_items
               if gi.tx==ptx and gi.ty==pty and gi.item.itype==IT_CURRENCY]
        for gi in coins:
            player.inventory.gold+=gi.item.value*gi.count
            self.log.add(f"+{gi.item.value*gi.count} gold!",GOLD)
            gmap.ground_items.remove(gi)

        # Respawns
        self._process_respawns(gmap)

        # Flush messages (skip internal signals)
        for text,col in self._pending_msgs:
            if not text.startswith("__"):
                self.log.add(text,col)
        self.log.update()

        mw=gmap.width*TILE_SIZE; mh=gmap.height*TILE_SIZE
        self.camera.follow(player,mw,mh)

        if not player.alive and not self._cheats.god_mode:
            self._state=ST_GAMEOVER

    def _process_respawns(self, gmap):
        new_q=[]
        for entry in gmap.respawn_queue:
            entry[0]-=1
            if entry[0]<=0:
                sp=entry[1]
                near=any(abs(e.cx//TILE_SIZE-sp['tx'])<3 and
                         abs(e.cy//TILE_SIZE-sp['ty'])<3 for e in gmap.entities)
                if not near and gmap.walkable(sp['tx'],sp['ty']):
                    gmap.entities.append(spawn_enemy(sp['type'],sp['tx'],sp['ty']))
            else:
                new_q.append(entry)
        gmap.respawn_queue=new_q

    # ── Draw ─────────────────────────────────────────────────────────────────
    def _draw(self):
        self.screen.fill(BLACK)
        if self._state==ST_MENU:
            draw_main_menu(self.screen,self._seed_str,self._menu_cursor,
                           self._difficulty,os.path.exists(SAVE_FILE)); return
        if self._state==ST_GAMEOVER:
            draw_game_over(self.screen,self._score); return
        if self._state==ST_WIN:
            draw_win(self.screen,self._score); return

        if self._state in (ST_PLAY,ST_INVENTORY,ST_PAUSED):
            vp=self._viewport; vp.fill((10,10,14))
            cx,cy=self.camera.ix,self.camera.iy; gmap=self.current_map
            gmap.draw(vp,cx,cy,self.player.x,self.player.y,
                      self.player.light_radius,self.asset_mgr)
            for e in gmap.entities:
                b=gmap.get_brightness_at(e.cx,e.cy,self.player.x,self.player.y,
                                         self.player.light_radius)
                e.draw(vp,cx,cy,self.asset_mgr,brightness=b)
            for proj in self.projectiles: proj.draw(vp,cx,cy,self.asset_mgr)
            self.player.draw(vp,cx,cy,self.asset_mgr)
            self.screen.blit(vp,(0,0))
            self.hud.draw(self.screen,self.player,self._current_map_name,
                          self.log.recent(4),self.asset_mgr,self._difficulty,
                          self._cheats.display)
            self._draw_prompts(cx,cy,gmap)

        if self._state==ST_INVENTORY:
            self.inv_screen.draw(self.screen,self.player,self.asset_mgr)
        if self._state==ST_PAUSED:
            draw_paused(self.screen,self._pause_cursor,os.path.exists(SAVE_FILE))

    def _draw_prompts(self, cam_x, cam_y, gmap):
        p=self.player; fx,fy=p.facing
        tx=int((p.cx+fx*TILE_SIZE*0.6)//TILE_SIZE)
        ty=int((p.cy+fy*TILE_SIZE*0.6)//TILE_SIZE)
        t=gmap.get(tx,ty)
        sx=tx*TILE_SIZE-cam_x; sy=ty*TILE_SIZE-cam_y-24
        msg=None
        if   t in GATE_TILES:    msg=f"[E] Travel through gate"
        elif t==T_ENTRANCE:      msg="[E] Enter Dungeon"
        elif t==T_STAIRS_UP and gmap.is_dungeon: msg="[E] Ascend"
        elif t==T_STAIRS_DOWN:   msg="[E] Descend deeper"
        elif t==T_CHEST and (tx,ty) not in gmap.chest_opened: msg="[E] Open Chest"
        elif t==T_SHRINE:        msg="[E] Shrine (Heal + Save)"
        ptx=int(p.cx//TILE_SIZE); pty=int(p.cy//TILE_SIZE)
        for gi in gmap.ground_items:
            if gi.tx==ptx and gi.ty==pty and gi.item.itype!=IT_CURRENCY:
                msg=f"[E] Pick up {gi.item.name}"
                sx=int(p.x)-cam_x; sy=int(p.y)-cam_y-24; break
        if msg: draw_text(self.screen,msg,sx,sy,15,YELLOW)
