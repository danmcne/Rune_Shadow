"""
Rune & Shadow - Game  (v2)
Camera, main game loop, state transitions, interaction, save/load, cheats.

New in v2:
  - Proper grass-based player start position
  - Pause menu: Resume / New Game / Save & Quit / Quit (no save)
  - Save & Load (JSON-based lightweight serialisation)
  - Difficulty selection (Easy / Normal / Hard) — damage multiplier
  - Cheat codes: GODMODE MAXHP MAXMANA GIVEALL NOCLIP RESPAWN
  - Chest loot using tiered loot tables (common / uncommon / rare)
  - Kelpie water-monsters spawned in overworld lakes
  - Mob respawn queue processed each frame
  - Dropped item lifetime (items disappear after ~2 min)
  - Enemy brightness passed through so dark-dungeon visibility works
  - Inventory drop (__DROP__ signal) spawns GroundItem at player feet
  - Mouse-position aim for ranged/magic (via player.set_mouse_world)
"""
import sys
import json
import os
import random
import math
import pygame

from constants  import *
from generation import OverworldGenerator, build_dungeon
from game_map   import GameMap, GroundItem
from entities   import Player, spawn_enemy, Projectile
from items      import make_item, ITEMS, CHEST_LOOT_COMMON, CHEST_LOOT_UNCOMMON, CHEST_LOOT_RARE
from asset_manager import AssetManager
from ui import (HUD, InventoryScreen,
                draw_main_menu, draw_game_over, draw_paused, draw_win,
                draw_text)

SAVE_FILE = "rune_shadow_save.json"


# ═══════════════════════════════════════════════════════════════════════════════
#  Camera
# ═══════════════════════════════════════════════════════════════════════════════

class Camera:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0

    def follow(self, player, map_w_px: int, map_h_px: int):
        target_x = player.x - SCREEN_WIDTH // 2
        target_y = player.y - VIEWPORT_H   // 2
        self.x  += (target_x - self.x) * 0.12
        self.y  += (target_y - self.y) * 0.12
        self.x   = max(0, min(self.x, map_w_px - SCREEN_WIDTH))
        self.y   = max(0, min(self.y, map_h_px - VIEWPORT_H))

    def snap(self, player, map_w_px: int, map_h_px: int):
        self.x = player.x - SCREEN_WIDTH // 2
        self.y = player.y - VIEWPORT_H   // 2
        self.x = max(0, min(self.x, map_w_px - SCREEN_WIDTH))
        self.y = max(0, min(self.y, map_h_px - VIEWPORT_H))

    @property
    def ix(self): return int(self.x)
    @property
    def iy(self): return int(self.y)


# ═══════════════════════════════════════════════════════════════════════════════
#  Message Log
# ═══════════════════════════════════════════════════════════════════════════════

class MessageLog:
    def __init__(self):
        self._msgs: list = []   # [text, color, timer]

    def add(self, text: str, color=WHITE):
        if text.startswith("__DROP__"):   # internal signal — don't display
            return
        self._msgs.append([text, color, MSG_DURATION])
        if len(self._msgs) > MSG_MAX * 2:
            self._msgs = self._msgs[-MSG_MAX:]

    def update(self):
        self._msgs = [[t, c, tm - 1] for t, c, tm in self._msgs if tm > 1]

    def recent(self, n: int = 6):
        return [(t, c) for t, c, _ in self._msgs[-n:]]


# ═══════════════════════════════════════════════════════════════════════════════
#  Cheat Engine
# ═══════════════════════════════════════════════════════════════════════════════

CHEAT_CODES = {
    "GODMODE":  "god",     # toggle invincibility
    "MAXHP":    "maxhp",   # full HP restore
    "MAXMANA":  "maxmana", # full mana restore
    "GIVEALL":  "giveall", # give every item x5
    "NOCLIP":   "noclip",  # toggle noclip (ghost through walls)
    "RESPAWN":  "respawn", # respawn all entities on current map
    "LEVELUP":  "levelup", # +20 max HP and mana
    "FULLCLEAR":"fullclear",# kill all enemies on map
}

class CheatEngine:
    def __init__(self):
        self._buffer  = ""
        self.god_mode = False
        self.no_clip  = False

    def type_char(self, ch: str):
        self._buffer = (self._buffer + ch.upper())[-12:]

    def check(self) -> str | None:
        for code, tag in CHEAT_CODES.items():
            if self._buffer.endswith(code):
                self._buffer = ""
                return tag
        return None

    @property
    def display(self) -> str:
        tags = []
        if self.god_mode: tags.append("GOD")
        if self.no_clip:  tags.append("NOCLIP")
        return " ".join(tags)


# ═══════════════════════════════════════════════════════════════════════════════
#  Main Game Class
# ═══════════════════════════════════════════════════════════════════════════════

class Game:
    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock,
                 seed: int = 12345):
        self.screen = screen
        self.clock  = clock
        self.seed   = seed

        self._state       = ST_MENU
        self._menu_cursor = 0
        self._pause_cursor= 0
        self._seed_str    = str(seed)
        self._difficulty  = DIFFICULTY_NORMAL

        self.player            = None
        self.overworld         = None
        self.current_map       = None
        self.dungeon_maps: dict  = {}
        self.dungeon_positions: list = []
        self.camera            = Camera()
        self.projectiles: list  = []
        self.log               = MessageLog()
        self.hud               = HUD()
        self.inv_screen        = InventoryScreen()
        self.rng               = random.Random(seed)
        self._score            = 0
        self._current_map_name = "Overworld"
        self._viewport         = pygame.Surface((SCREEN_WIDTH, VIEWPORT_H))
        self._pending_msgs: list = []
        self._cheats           = CheatEngine()
        self.asset_mgr         = AssetManager()

    # ── Public run loop ──────────────────────────────────────────────────────
    def run(self):
        while True:
            self.clock.tick(FPS)
            self._handle_events()
            self._update()
            self._draw()
            pygame.display.flip()

    # ═════════════════════════════════════════════════════════════════════════
    #  Event Handling
    # ═════════════════════════════════════════════════════════════════════════

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if   self._state == ST_MENU:      self._menu_event(event)
            elif self._state == ST_PLAY:      self._play_event(event)
            elif self._state == ST_INVENTORY: self._inv_event(event)
            elif self._state == ST_PAUSED:    self._pause_event(event)
            elif self._state == ST_GAMEOVER:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    self._state = ST_MENU
            elif self._state == ST_WIN:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    self._state = ST_MENU

    # ── Menu ─────────────────────────────────────────────────────────────────
    def _menu_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        has_save   = os.path.exists(SAVE_FILE)
        num_opts   = 3 if has_save else 2   # New / [Load] / Quit

        if event.key == pygame.K_UP:
            self._menu_cursor = (self._menu_cursor - 1) % num_opts
        elif event.key == pygame.K_DOWN:
            self._menu_cursor = (self._menu_cursor + 1) % num_opts
        elif event.key == pygame.K_LEFT:
            self._difficulty = (self._difficulty - 1) % 3
        elif event.key == pygame.K_RIGHT:
            self._difficulty = (self._difficulty + 1) % 3
        elif event.key == pygame.K_RETURN:
            self._menu_select(has_save)
        elif event.key == pygame.K_BACKSPACE:
            self._seed_str = self._seed_str[:-1] or "0"
        elif event.unicode.isdigit() and len(self._seed_str) < 10:
            self._seed_str += event.unicode
            try:   self.seed = int(self._seed_str)
            except ValueError: pass

    def _menu_select(self, has_save: bool):
        options = ["new"]
        if has_save: options.append("load")
        options.append("quit")
        choice = options[self._menu_cursor]
        if choice == "new":
            self._start_game()
        elif choice == "load":
            if not self._load_game():
                self.log.add("Save file corrupt — starting new game.", RED)
                self._start_game()
        elif choice == "quit":
            pygame.quit(); sys.exit()

    # ── Pause ────────────────────────────────────────────────────────────────
    def _pause_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        NUM_PAUSE_OPTS = 4
        if event.key == pygame.K_ESCAPE:
            self._state = ST_PLAY
        elif event.key == pygame.K_UP:
            self._pause_cursor = (self._pause_cursor - 1) % NUM_PAUSE_OPTS
        elif event.key == pygame.K_DOWN:
            self._pause_cursor = (self._pause_cursor + 1) % NUM_PAUSE_OPTS
        elif event.key == pygame.K_RETURN:
            self._pause_select()

    def _pause_select(self):
        # 0=Resume 1=New Game 2=Save & Quit 3=Quit no save
        c = self._pause_cursor
        if c == 0:
            self._state = ST_PLAY
        elif c == 1:
            self._start_game()
        elif c == 2:
            self._save_game()
            pygame.quit(); sys.exit()
        elif c == 3:
            pygame.quit(); sys.exit()

    # ── Play ─────────────────────────────────────────────────────────────────
    def _play_event(self, event):
        if event.type == pygame.KEYDOWN:
            # Feed cheat buffer
            if event.unicode and event.unicode.isalpha():
                self._cheats.type_char(event.unicode)
                tag = self._cheats.check()
                if tag:
                    self._apply_cheat(tag)

            if event.key == pygame.K_ESCAPE:
                self._state       = ST_PAUSED
                self._pause_cursor = 0
            elif event.key == pygame.K_i:
                self._state = ST_INVENTORY
            elif event.key == pygame.K_SPACE:
                self.player.attack(self.current_map,
                                   self.current_map.entities,
                                   self.projectiles,
                                   self._pending_msgs)
            elif event.key == pygame.K_e:
                self._interact()
            elif event.key == pygame.K_q:
                self.player.cycle_hotbar(-1)
            elif event.key == pygame.K_f:
                self.player.cycle_hotbar(1)
            elif pygame.K_1 <= event.key <= pygame.K_8:
                self.player.equipped = event.key - pygame.K_1

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:   # left-click = attack
                self.player.attack(self.current_map,
                                   self.current_map.entities,
                                   self.projectiles,
                                   self._pending_msgs)
            elif event.button == 4:  # scroll up
                self.player.cycle_hotbar(-1)
            elif event.button == 5:  # scroll down
                self.player.cycle_hotbar(1)

    # ── Inventory ─────────────────────────────────────────────────────────────
    def _inv_event(self, event):
        if event.type == pygame.KEYDOWN:
            close = self.inv_screen.handle_key(event, self.player,
                                               self._pending_msgs)
            # Handle drop signal
            for msg_text, col in self._pending_msgs:
                if msg_text.startswith("__DROP__:"):
                    iid = msg_text.split(":", 1)[1]
                    if iid in ITEMS:
                        ptx = int(self.player.cx // TILE_SIZE)
                        pty = int(self.player.cy // TILE_SIZE)
                        gi  = GroundItem(make_item(iid), ptx, pty, 1,
                                         lifetime=DROPPED_ITEM_LIFETIME_FRAMES)
                        self.current_map.ground_items.append(gi)
            if close:
                self._state = ST_PLAY

    # ═════════════════════════════════════════════════════════════════════════
    #  Cheat Application
    # ═════════════════════════════════════════════════════════════════════════

    def _apply_cheat(self, tag: str):
        p = self.player
        if tag == "god":
            self._cheats.god_mode = not self._cheats.god_mode
            self.log.add(f"GOD MODE {'ON' if self._cheats.god_mode else 'OFF'}",
                         PURPLE)
        elif tag == "maxhp":
            p.hp = p.max_hp
            self.log.add("HP fully restored!", GREEN)
        elif tag == "maxmana":
            p.mana = p.max_mana
            self.log.add("Mana fully restored!", BLUE)
        elif tag == "giveall":
            for iid in ITEMS:
                p.inventory.add(make_item(iid), 5)
            self.log.add("All items granted!", GOLD)
        elif tag == "noclip":
            self._cheats.no_clip = not self._cheats.no_clip
            self.log.add(f"NOCLIP {'ON' if self._cheats.no_clip else 'OFF'}",
                         PURPLE)
        elif tag == "respawn":
            self._respawn_all_on_map(self.current_map)
            self.log.add("All entities respawned!", ORANGE)
        elif tag == "levelup":
            p.max_hp   += 20; p.hp   = p.max_hp
            p.max_mana += 20; p.mana = p.max_mana
            self.log.add("Max HP and Mana increased!", GOLD)
        elif tag == "fullclear":
            for e in list(self.current_map.entities):
                e.hp    = 0
                e.alive = False
            self.log.add("All enemies defeated!", YELLOW)

    def _respawn_all_on_map(self, gmap: GameMap):
        if gmap.is_dungeon:
            dun_idx = gmap.dungeon_id
            gmap.entities.clear()
            self._spawn_dungeon_entities(gmap, dun_idx)
        else:
            gmap.entities.clear()
            self._populate_overworld_entities(gmap)

    # ═════════════════════════════════════════════════════════════════════════
    #  Interaction
    # ═════════════════════════════════════════════════════════════════════════

    def _interact(self):
        p    = self.player
        gmap = self.current_map
        fx, fy = p.facing
        tx = int((p.cx + fx * TILE_SIZE * 0.6) // TILE_SIZE)
        ty = int((p.cy + fy * TILE_SIZE * 0.6) // TILE_SIZE)
        t  = gmap.get(tx, ty)

        if t == T_ENTRANCE:
            dun_idx = None
            for i, (dtx, dty) in enumerate(self.dungeon_positions):
                if dtx == tx and dty == ty:
                    dun_idx = i; break
            if dun_idx is not None:
                self._enter_dungeon(dun_idx, tx, ty)

        elif t == T_STAIRS_UP and gmap.is_dungeon:
            self._exit_dungeon()

        elif t == T_CHEST and (tx, ty) not in gmap.chest_opened:
            self._open_chest(gmap, tx, ty)

        elif t == T_SHRINE:
            p.hp   = p.max_hp
            p.mana = p.max_mana
            self._save_game()
            self.log.add("Shrine restores you fully — game saved!", CYAN)

        # Pick up ground items at player tile
        ptx = int(p.cx // TILE_SIZE)
        pty = int(p.cy // TILE_SIZE)
        to_remove = []
        for gi in gmap.ground_items:
            if gi.tx == ptx and gi.ty == pty:
                if p.inventory.add(gi.item, gi.count):
                    self.log.add(f"Picked up {gi.item.name} x{gi.count}.", WHITE)
                    to_remove.append(gi)
        for gi in to_remove:
            gmap.ground_items.remove(gi)

    def _enter_dungeon(self, dun_idx: int, ow_tx: int, ow_ty: int):
        if dun_idx not in self.dungeon_maps:
            dmap = build_dungeon(self.seed, dun_idx)
            dmap.ow_entrance = (ow_tx, ow_ty)
            self._spawn_dungeon_entities(dmap, dun_idx)
            self.dungeon_maps[dun_idx] = dmap

        dmap      = self.dungeon_maps[dun_idx]
        ex, ey    = dmap.entrance_tile
        self.player.x = ex * TILE_SIZE + (TILE_SIZE - ENTITY_SIZE) // 2
        self.player.y = ey * TILE_SIZE + (TILE_SIZE - ENTITY_SIZE) // 2
        self.current_map       = dmap
        self._current_map_name = DUNGEONS[dun_idx]['name']
        self.projectiles.clear()
        self.camera.snap(self.player, dmap.width * TILE_SIZE, dmap.height * TILE_SIZE)
        self.log.add(f"You enter {DUNGEONS[dun_idx]['name']}!", ORANGE)

    def _exit_dungeon(self):
        dmap  = self.current_map
        ox, oy = dmap.ow_entrance
        self.player.x = ox * TILE_SIZE + (TILE_SIZE - ENTITY_SIZE) // 2
        self.player.y = oy * TILE_SIZE + (TILE_SIZE - ENTITY_SIZE) // 2
        self.current_map       = self.overworld
        self._current_map_name = "Overworld"
        self.projectiles.clear()
        self.camera.snap(self.player,
                         self.overworld.width  * TILE_SIZE,
                         self.overworld.height * TILE_SIZE)
        self.log.add("You emerge from the dungeon.", GREEN)

    def _open_chest(self, gmap: GameMap, tx: int, ty: int):
        gmap.chest_opened.add((tx, ty))
        floor_t = DUNGEONS[gmap.dungeon_id]['floor'] if gmap.is_dungeon else T_GRASS
        gmap.set(tx, ty, floor_t)

        # Tiered loot: 3-6 common + 1-2 uncommon + small chance rare
        drops = []
        n_common   = self.rng.randint(3, 6)
        n_uncommon = self.rng.randint(1, 2)
        for _ in range(n_common):
            drops.append((self.rng.choice(CHEST_LOOT_COMMON),
                          self.rng.randint(1, 4)))
        for _ in range(n_uncommon):
            drops.append((self.rng.choice(CHEST_LOOT_UNCOMMON), 1))
        if self.rng.random() < 0.20:
            drops.append((self.rng.choice(CHEST_LOOT_RARE), 1))

        for iid, count in drops:
            try:
                it = make_item(iid)
                # Scatter items around the chest tile
                dtx = tx + self.rng.randint(-1, 1)
                dty = ty + self.rng.randint(-1, 1)
                if not gmap.in_bounds(dtx, dty):
                    dtx, dty = tx, ty
                gmap.ground_items.append(
                    GroundItem(it, dtx, dty, count,
                               lifetime=DROPPED_ITEM_LIFETIME_FRAMES * 4))
            except KeyError:
                pass

        self.log.add(f"Chest contains {len(drops)} items!", GOLD)

    def _spawn_dungeon_entities(self, dmap: GameMap, dun_idx: int):
        for sp in getattr(dmap, 'enemy_spawns', []):
            try:
                e = spawn_enemy(sp['type'], sp['tx'], sp['ty'],
                                is_boss=sp.get('boss', False))
                dmap.entities.append(e)
            except Exception:
                pass
        for sp in getattr(dmap, 'item_spawns', []):
            try:
                it = make_item(sp['iid'])
                gi = GroundItem(it, sp['tx'], sp['ty'], sp['count'])
                dmap.ground_items.append(gi)
            except (KeyError, Exception):
                pass

    # ═════════════════════════════════════════════════════════════════════════
    #  New Game
    # ═════════════════════════════════════════════════════════════════════════

    def _start_game(self):
        try:
            self.seed = int(self._seed_str) if self._seed_str else 12345
        except ValueError:
            self.seed = 12345

        self.rng             = random.Random(self.seed)
        self.log             = MessageLog()
        self.projectiles     = []
        self.dungeon_maps    = {}
        self._pending_msgs   = []
        self._score          = 0
        self._cheats         = CheatEngine()
        self._pause_cursor   = 0

        # Generate overworld
        gen                  = OverworldGenerator(self.seed)
        self.overworld       = gen.generate()
        self.dungeon_positions = gen.dungeon_tile_positions

        # Populate overworld creatures
        self._populate_overworld_entities(self.overworld)

        # Scatter ground items
        self._populate_overworld_items(self.overworld)

        # Player starts on a real grass tile (not a forced clear square)
        stx, sty = gen.start_tile
        px = stx * TILE_SIZE + (TILE_SIZE - ENTITY_SIZE) // 2
        py = sty * TILE_SIZE + (TILE_SIZE - ENTITY_SIZE) // 2
        self.player = Player(px, py)
        # Apply god/noclip state if cheats were already on (shouldn't be on new game, but safe)

        self.current_map       = self.overworld
        self._current_map_name = "Overworld"
        self.camera            = Camera()
        self.camera.snap(self.player,
                         self.overworld.width  * TILE_SIZE,
                         self.overworld.height * TILE_SIZE)
        self.inv_screen = InventoryScreen()

        self.log.add("Welcome to Rune & Shadow!", CYAN)
        self.log.add("SPACE/Click=Attack  Mouse=Aim  E=Interact  I=Inventory", WHITE)
        self.log.add("Cheat codes: type GODMODE MAXHP GIVEALL NOCLIP RESPAWN", GRAY)
        self._state = ST_PLAY

    def _populate_overworld_entities(self, ow: GameMap):
        rng = self.rng
        stx, sty = WORLD_W // 2, WORLD_H // 2

        # Land creatures
        for _ in range(70):
            tx = rng.randint(5, WORLD_W - 5)
            ty = rng.randint(5, WORLD_H - 5)
            if not ow.walkable(tx, ty): continue
            if abs(tx - stx) < 10 and abs(ty - sty) < 10: continue
            etype = rng.choice(['wolf', 'wolf', 'goblin', 'slime', 'slime',
                                 'bat', 'bat', 'spider'])
            e = spawn_enemy(etype, tx, ty)
            ow.entities.append(e)
            # Store original spawn for respawn system
            ow.respawn_queue  # ensure attribute exists

        # Water kelpies
        for _ in range(20):
            tx = rng.randint(5, WORLD_W - 5)
            ty = rng.randint(5, WORLD_H - 5)
            t  = ow.get(tx, ty)
            if t not in (T_WATER,):  continue
            e = spawn_enemy('kelpie', tx, ty)
            ow.entities.append(e)

    def _populate_overworld_items(self, ow: GameMap):
        rng = self.rng
        for _ in range(40):
            tx = rng.randint(5, WORLD_W - 5)
            ty = rng.randint(5, WORLD_H - 5)
            if not ow.walkable(tx, ty): continue
            iid   = rng.choice(['mushroom', 'herb', 'stone', 'stone', 'stone',
                                 'coin', 'blue_flower', 'bread', 'rope'])
            count = rng.randint(1, 3)
            ow.ground_items.append(GroundItem(make_item(iid), tx, ty, count))

    # ═════════════════════════════════════════════════════════════════════════
    #  Save / Load
    # ═════════════════════════════════════════════════════════════════════════

    def _save_game(self):
        """Save minimal game state to JSON."""
        p    = self.player
        data = {
            "seed":       self.seed,
            "difficulty": self._difficulty,
            "score":      self._score,
            "player": {
                "x": p.x, "y": p.y,
                "hp": p.hp, "max_hp": p.max_hp,
                "mana": p.mana, "max_mana": p.max_mana,
                "gold": p.inventory.gold,
                "hotbar": p.hotbar,
                "inventory": {it.iid: cnt
                              for it, cnt in p.inventory._slots},
            },
            "in_dungeon": self.current_map.is_dungeon,
            "dungeon_id": self.current_map.dungeon_id if self.current_map.is_dungeon else -1,
            "chest_opened_ow": [],
            "chests_per_dungeon": {
                str(k): list(v.chest_opened)
                for k, v in self.dungeon_maps.items()
            },
        }
        try:
            with open(SAVE_FILE, "w") as f:
                json.dump(data, f, indent=2)
            self.log.add("Game saved.", GREEN)
        except Exception as ex:
            self.log.add(f"Save failed: {ex}", RED)

    def _load_game(self) -> bool:
        try:
            with open(SAVE_FILE) as f:
                data = json.load(f)

            self.seed        = data["seed"]
            self._seed_str   = str(self.seed)
            self._difficulty = data.get("difficulty", DIFFICULTY_NORMAL)
            self._score      = data.get("score", 0)
            self.rng         = random.Random(self.seed)
            self.log         = MessageLog()
            self.projectiles = []
            self.dungeon_maps = {}
            self._pending_msgs = []
            self._cheats       = CheatEngine()

            # Regenerate world deterministically from seed
            gen                  = OverworldGenerator(self.seed)
            self.overworld       = gen.generate()
            self.dungeon_positions = gen.dungeon_tile_positions
            self._populate_overworld_entities(self.overworld)
            self._populate_overworld_items(self.overworld)

            pd      = data["player"]
            self.player = Player(pd["x"], pd["y"])
            self.player.hp       = pd["hp"]
            self.player.max_hp   = pd["max_hp"]
            self.player.mana     = pd["mana"]
            self.player.max_mana = pd["max_mana"]
            self.player.inventory.gold = pd["gold"]
            self.player.hotbar   = pd["hotbar"]
            # Restore inventory
            self.player.inventory._slots.clear()
            for iid, cnt in pd["inventory"].items():
                if iid in ITEMS:
                    self.player.inventory._slots.append([make_item(iid), cnt])

            # Restore chest states
            for k_str, chest_list in data.get("chests_per_dungeon", {}).items():
                k = int(k_str)
                # Build the dungeon map lazily when player enters; store pending
                # chest_opened data keyed by dungeon id for later application
                if k not in self.dungeon_maps:
                    dmap = build_dungeon(self.seed, k)
                    dmap.chest_opened = set(tuple(c) for c in chest_list)
                    self._spawn_dungeon_entities(dmap, k)
                    dun_entrance = self.dungeon_positions[k] if k < len(self.dungeon_positions) else (0,0)
                    dmap.ow_entrance = dun_entrance
                    self.dungeon_maps[k] = dmap

            in_dungeon = data.get("in_dungeon", False)
            dun_id     = data.get("dungeon_id", -1)
            if in_dungeon and dun_id in self.dungeon_maps:
                self.current_map       = self.dungeon_maps[dun_id]
                self._current_map_name = DUNGEONS[dun_id]['name']
            else:
                self.current_map       = self.overworld
                self._current_map_name = "Overworld"

            self.camera = Camera()
            self.camera.snap(self.player,
                             self.current_map.width  * TILE_SIZE,
                             self.current_map.height * TILE_SIZE)
            self.inv_screen = InventoryScreen()
            self.log.add("Save loaded. Welcome back!", CYAN)
            self._state = ST_PLAY
            return True

        except Exception as ex:
            print(f"Load error: {ex}")
            return False

    # ═════════════════════════════════════════════════════════════════════════
    #  Update
    # ═════════════════════════════════════════════════════════════════════════

    def _update(self):
        if self._state != ST_PLAY:
            return

        gmap   = self.current_map
        player = self.player
        self._pending_msgs = []

        # God mode — keep HP from dropping to 0
        if self._cheats.god_mode:
            player.hp     = player.max_hp
            player.mana   = player.max_mana
            player.iframes = PLAYER_IFRAMES

        keys = pygame.key.get_pressed()
        # Pass noclip flag into player (player.try_move ghost param)
        _orig_ghost = self._cheats.no_clip
        player.update(keys, gmap, gmap.entities, self.projectiles,
                      self._pending_msgs,
                      cam_x=self.camera.ix, cam_y=self.camera.iy)

        # Override movement for noclip — re-apply last movement ignoring collisions
        if _orig_ghost:
            dx = dy = 0.0
            spd = PLAYER_SPEED
            if keys[pygame.K_LEFT]  or keys[pygame.K_a]: dx -= spd
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]: dx += spd
            if keys[pygame.K_UP]    or keys[pygame.K_w]: dy -= spd
            if keys[pygame.K_DOWN]  or keys[pygame.K_s]: dy += spd
            if dx and dy: dx *= 0.7071; dy *= 0.7071
            player.x += dx; player.y += dy
            # Clamp to map
            mw = gmap.width  * TILE_SIZE
            mh = gmap.height * TILE_SIZE
            player.x = max(0, min(player.x, mw - ENTITY_SIZE))
            player.y = max(0, min(player.y, mh - ENTITY_SIZE))

        # Update enemies
        for e in list(gmap.entities):
            if e.alive:
                e.update(player, gmap, self.projectiles, self._pending_msgs)
            else:
                drops = e.get_drops(self.rng)
                tx    = int(e.cx // TILE_SIZE)
                ty    = int(e.cy // TILE_SIZE)
                for it in drops:
                    gi = GroundItem(it, tx, ty, 1,
                                    lifetime=DROPPED_ITEM_LIFETIME_FRAMES)
                    gmap.ground_items.append(gi)
                self._score += 10 * (5 if e.is_boss else 1)
                # Queue respawn for overworld enemies
                if not gmap.is_dungeon and not e.is_boss:
                    gmap.respawn_queue.append([
                        OVERWORLD_MOB_RESPAWN_FRAMES,
                        {'type': e.etype, 'tx': tx, 'ty': ty}
                    ])
                gmap.entities.remove(e)

        # Update projectiles
        for proj in list(self.projectiles):
            proj.update(gmap, player, gmap.entities, self._pending_msgs)
            if not proj.alive:
                self.projectiles.remove(proj)

        # Update ground items (bobbing + lifetime expiry)
        expired = []
        for gi in gmap.ground_items:
            gi.update()
            if gi.expired:
                expired.append(gi)
        for gi in expired:
            gmap.ground_items.remove(gi)

        # Auto-pickup coins at player tile
        ptx = int(player.cx // TILE_SIZE)
        pty = int(player.cy // TILE_SIZE)
        to_remove = []
        for gi in gmap.ground_items:
            if gi.tx == ptx and gi.ty == pty:
                if gi.item.itype == IT_CURRENCY:
                    player.inventory.gold += gi.item.value * gi.count
                    self.log.add(f"+{gi.item.value * gi.count} gold!", GOLD)
                    to_remove.append(gi)
        for gi in to_remove:
            gmap.ground_items.remove(gi)

        # Process respawn queue
        self._process_respawns(gmap)

        # Flush messages (filter out __DROP__ signals — handled in inv_event)
        for text, col in self._pending_msgs:
            if not text.startswith("__DROP__"):
                self.log.add(text, col)
        self.log.update()

        # Camera
        mw = gmap.width  * TILE_SIZE
        mh = gmap.height * TILE_SIZE
        self.camera.follow(player, mw, mh)

        # Death check
        if not player.alive and not self._cheats.god_mode:
            self._state = ST_GAMEOVER

    def _process_respawns(self, gmap: GameMap):
        if not gmap.respawn_queue:
            return
        new_queue = []
        for entry in gmap.respawn_queue:
            entry[0] -= 1
            if entry[0] <= 0:
                sp = entry[1]
                # Only respawn if no entity already near that tile
                near = any(
                    abs(e.cx // TILE_SIZE - sp['tx']) < 3 and
                    abs(e.cy // TILE_SIZE - sp['ty']) < 3
                    for e in gmap.entities
                )
                if not near and gmap.walkable(sp['tx'], sp['ty']):
                    e = spawn_enemy(sp['type'], sp['tx'], sp['ty'])
                    gmap.entities.append(e)
            else:
                new_queue.append(entry)
        gmap.respawn_queue = new_queue

    # ═════════════════════════════════════════════════════════════════════════
    #  Draw
    # ═════════════════════════════════════════════════════════════════════════

    def _draw(self):
        self.screen.fill(BLACK)

        if self._state == ST_MENU:
            has_save = os.path.exists(SAVE_FILE)
            draw_main_menu(self.screen, self._seed_str, self._menu_cursor,
                           self._difficulty, has_save)
            return

        if self._state == ST_GAMEOVER:
            draw_game_over(self.screen, self._score)
            return

        if self._state == ST_WIN:
            draw_win(self.screen, self._score)
            return

        if self._state in (ST_PLAY, ST_INVENTORY, ST_PAUSED):
            vp   = self._viewport
            vp.fill((10, 10, 14))
            cx, cy = self.camera.ix, self.camera.iy
            gmap   = self.current_map

            # Tiles + ground items
            gmap.draw(vp, cx, cy,
                      self.player.x, self.player.y,
                      self.player.light_radius,
                      self.asset_mgr)

            # Entities (with brightness for dark dungeons)
            for e in gmap.entities:
                brightness = gmap.get_brightness_at(
                    e.cx, e.cy, self.player.x, self.player.y,
                    self.player.light_radius)
                e.draw(vp, cx, cy, self.asset_mgr, brightness=brightness)

            # Projectiles
            for proj in self.projectiles:
                proj.draw(vp, cx, cy, self.asset_mgr)

            # Player
            self.player.draw(vp, cx, cy, self.asset_mgr)

            self.screen.blit(vp, (0, 0))

            # HUD
            self.hud.draw(self.screen, self.player,
                          self._current_map_name,
                          self.log.recent(4),
                          self.asset_mgr,
                          self._difficulty,
                          self._cheats.display)

            self._draw_prompts(cx, cy, gmap)

        if self._state == ST_INVENTORY:
            self.inv_screen.draw(self.screen, self.player, self.asset_mgr)

        if self._state == ST_PAUSED:
            draw_paused(self.screen, self._pause_cursor,
                        has_save=os.path.exists(SAVE_FILE))

    def _draw_prompts(self, cam_x: int, cam_y: int, gmap: GameMap):
        p      = self.player
        fx, fy = p.facing
        tx = int((p.cx + fx * TILE_SIZE * 0.6) // TILE_SIZE)
        ty = int((p.cy + fy * TILE_SIZE * 0.6) // TILE_SIZE)
        t  = gmap.get(tx, ty)

        sx = tx * TILE_SIZE - cam_x
        sy = ty * TILE_SIZE - cam_y - 24

        msg = None
        if t == T_ENTRANCE:
            msg = "[E] Enter Dungeon"
        elif t == T_STAIRS_UP and gmap.is_dungeon:
            msg = "[E] Exit Dungeon"
        elif t == T_CHEST and (tx, ty) not in gmap.chest_opened:
            msg = "[E] Open Chest"
        elif t == T_SHRINE:
            msg = "[E] Use Shrine & Save"

        # Ground items at player feet
        ptx = int(p.cx // TILE_SIZE)
        pty = int(p.cy // TILE_SIZE)
        for gi in gmap.ground_items:
            if gi.tx == ptx and gi.ty == pty and gi.item.itype != IT_CURRENCY:
                msg = f"[E] Pick up {gi.item.name}"
                sx  = int(p.x) - cam_x
                sy  = int(p.y) - cam_y - 24
                break

        if msg:
            draw_text(self.screen, msg, sx, sy, 15, YELLOW)
