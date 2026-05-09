"""
Rune & Shadow - Game v4
Multi-player (1 or 2), rebindable keybindings, dungeon-ascend-fix,
camera tracks midpoint, settings menu.

Fixes:
  - Ascending from dungeon level N→N-1 returns player to where they descended,
    not to the entrance of level N-1.
  - Dungeon multi-level: descent_pos dict tracks per-(dun_id,from_level) coords.

Two-player:
  - P1: WASD + SPACE/E/I/TAB/X/Q/F/1-8/ESC  (fully rebindable)
  - P2: Numpad 8/4/2/6 + KP0/KPEnter/KP÷/KP*/KP./KP7/KP9  (fully rebindable)
  - Camera follows midpoint between players.
  - Both players must share gate/dungeon transitions.
  - Auto-aim always active (no mouse tracking for either player in 2P).
  - Projectiles hit enemies near any player; enemy attacks nearest player.

Settings menu: accessible from pause. Saves keybindings to JSON alongside save.
"""
import sys, json, os, random, math
import pygame

from constants  import *
from generation import build_town, build_biome_map, build_dungeon_level, build_haunted_town
from game_map   import GameMap, GroundItem
from entities   import Player, Enemy, spawn_enemy, Projectile, Princess, Lorekeeper, Trader, Pet
from items      import make_item, ITEMS, CHEST_LOOT_COMMON, CHEST_LOOT_UNCOMMON, CHEST_LOOT_RARE
from asset_manager import AssetManager
from ui import (HUD, InventoryScreen, SettingsScreen,
                draw_main_menu, draw_game_over, draw_paused, draw_win, draw_text,
                draw_npc_dialog, draw_trader_shop)
import sound_engine


def _det_hash(*args) -> int:
    """Deterministic hash (stable across Python runs, unlike built-in hash())."""
    h = 5381
    for a in args:
        for c in str(a):
            h = ((h << 5) + h) ^ ord(c)
    return h & 0x7FFFFFFF


SAVE_FILE     = "rune_shadow_save.json"
SETTINGS_FILE = "rune_shadow_settings.json"


# ═══════════════════════════════════════════════════════════════════════════════
#  GameSettings  (keybindings + num_players + difficulty)
# ═══════════════════════════════════════════════════════════════════════════════
class GameSettings:
    def __init__(self):
        self.num_players = 1
        self.difficulty  = DIFFICULTY_NORMAL
        # Keybindings stored as {action: pygame_key_int}
        self.keybindings = [self._p1_defaults(), self._p2_defaults()]

    # ─── Defaults ─────────────────────────────────────────────────────────────
    @staticmethod
    def _p1_defaults():
        return {
            'up':          pygame.K_w,
            'down':        pygame.K_s,
            'left':        pygame.K_a,
            'right':       pygame.K_d,
            'attack':      pygame.K_SPACE,
            'interact':    pygame.K_e,
            'inventory':   pygame.K_q,          # Q = inventory (was I)
            'aim_toggle':  pygame.K_TAB,
            'unequip':     pygame.K_x,
            'hotbar_prev': pygame.K_BACKQUOTE,  # ` = prev slot
            'hotbar_next': pygame.K_f,
            'hotbar_1':    pygame.K_1,
            'hotbar_2':    pygame.K_2,
            'hotbar_3':    pygame.K_3,
            'hotbar_4':    pygame.K_4,
            'hotbar_5':    pygame.K_5,
            'hotbar_6':    pygame.K_6,   # slots 6-8 only used in 1P mode
            'hotbar_7':    pygame.K_7,
            'hotbar_8':    pygame.K_8,
            'pause':       pygame.K_ESCAPE,
        }

    @staticmethod
    def _p2_defaults():
        return {
            'up':          pygame.K_i,          # IJKL — separate keyboard zone from WASD
            'down':        pygame.K_k,
            'left':        pygame.K_j,
            'right':       pygame.K_l,
            'attack':      pygame.K_m,
            'interact':    pygame.K_u,
            'inventory':   pygame.K_o,
            'aim_toggle':  None,
            'unequip':     pygame.K_SEMICOLON,
            'hotbar_prev': None,
            'hotbar_next': None,
            'hotbar_1':    pygame.K_6,   # 6-0 → P2 hotbar slots 1-5
            'hotbar_2':    pygame.K_7,
            'hotbar_3':    pygame.K_8,
            'hotbar_4':    pygame.K_9,
            'hotbar_5':    pygame.K_0,
            'hotbar_6':    None,
            'hotbar_7':    None,
            'hotbar_8':    None,
            'pause':       None,
        }

    def save(self):
        data = {
            'num_players': self.num_players,
            'difficulty':  self.difficulty,
            'keybindings': self.keybindings,
        }
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception: pass

    def load(self):
        try:
            with open(SETTINGS_FILE) as f:
                data = json.load(f)
            self.num_players = data.get('num_players', 1)
            self.difficulty  = data.get('difficulty', DIFFICULTY_NORMAL)
            for pi, kb in enumerate(data.get('keybindings', [])):
                if pi < len(self.keybindings):
                    for action, val in kb.items():
                        self.keybindings[pi][action] = val  # val may be None
        except Exception: pass

    def make_input_state(self, key_tracker, pi: int) -> dict:
        """Return {action: bool} for player pi using current keybindings + key tracker."""
        kb = self.keybindings[pi]
        return {action: key_tracker.held(key) for action, key in kb.items()}

    def key_for(self, pi: int, action: str):
        return self.keybindings[pi].get(action)

    def set_key(self, pi: int, action: str, key):
        self.keybindings[pi][action] = key


# ═══════════════════════════════════════════════════════════════════════════════
#  Key Tracker – software N-key-rollover bypass
# ═══════════════════════════════════════════════════════════════════════════════
class KeyTracker:
    """
    Tracks key states via KEYDOWN/KEYUP events rather than get_pressed().

    Why: pygame.key.get_pressed() reads the hardware scancode array, which is
    subject to the keyboard's N-key rollover limit (often 3 keys for non-gaming
    keyboards). With event-based tracking, every KEYDOWN and KEYUP is recorded
    independently, so all 4 directional keys + modifiers register correctly.
    """
    def __init__(self):
        self._held: set = set()

    def press(self, k):   self._held.add(k)
    def release(self, k): self._held.discard(k)
    def held(self, k):    return k in self._held if k is not None else False
    def clear(self):      self._held.clear()


# ═══════════════════════════════════════════════════════════════════════════════
#  Camera
# ═══════════════════════════════════════════════════════════════════════════════
class Camera:
    def __init__(self): self.x=0.0; self.y=0.0

    def follow(self, targets, mw, mh, prev_positions=None):
        """
        Track midpoint of all targets.
        In 2P: enforce max separation so both stay on-screen.
        Uses "blame the mover" logic — the player who increased separation
        is pulled back; a stationary player is not moved at all.
        prev_positions: list of (px, py) before this frame's moves.
        """
        if not targets: return
        tx = sum(p.x for p in targets)/len(targets)
        ty = sum(p.y for p in targets)/len(targets)
        self.x += (tx-SCREEN_WIDTH//2-self.x)*0.12
        self.y += (ty-VIEWPORT_H//2  -self.y)*0.12
        self.x = max(0, min(self.x, mw-SCREEN_WIDTH))
        self.y = max(0, min(self.y, mh-VIEWPORT_H))

        if len(targets) < 2: return

        ES = ENTITY_SIZE
        for axis, max_sep in (('x', SCREEN_WIDTH-ES*2-4), ('y', VIEWPORT_H-ES*2-4)):
            vals = [getattr(p, axis) for p in targets]
            sep  = max(vals) - min(vals)
            if sep <= max_sep: continue
            excess = sep - max_sep
            # Identify the "low" and "high" player on this axis
            lo_p = min(targets, key=lambda p: getattr(p, axis))
            hi_p = max(targets, key=lambda p: getattr(p, axis))
            if prev_positions:
                prev = {id(p): pv for p, pv in zip(targets, prev_positions)}
                pv_lo = prev[id(lo_p)][0 if axis=='x' else 1]
                pv_hi = prev[id(hi_p)][0 if axis=='x' else 1]
                # How much did each player move to INCREASE separation?
                lo_contrib = max(0, pv_lo - getattr(lo_p, axis))  # lo moved left
                hi_contrib = max(0, getattr(hi_p, axis) - pv_hi)  # hi moved right
                total = lo_contrib + hi_contrib
            else:
                lo_contrib = hi_contrib = total = 0
            if total > 0:
                pull_lo = excess * lo_contrib / total
                pull_hi = excess * hi_contrib / total
            else:
                # Neither moved (or no prev data) — split equally
                pull_lo = pull_hi = excess / 2
            # Apply: push lo rightward, hi leftward
            if axis == 'x':
                lo_p.x += pull_lo; hi_p.x -= pull_hi
            else:
                lo_p.y += pull_lo; hi_p.y -= pull_hi

    def snap(self, targets, mw, mh):
        if not targets: return
        tx=sum(p.x for p in targets)/len(targets)
        ty=sum(p.y for p in targets)/len(targets)
        self.x=max(0,min(tx-SCREEN_WIDTH//2,mw-SCREEN_WIDTH))
        self.y=max(0,min(ty-VIEWPORT_H//2,  mh-VIEWPORT_H))

    @property
    def ix(self): return int(self.x)
    @property
    def iy(self): return int(self.y)


# ═══════════════════════════════════════════════════════════════════════════════
#  Message Log
# ═══════════════════════════════════════════════════════════════════════════════
class MessageLog:
    def __init__(self): self._msgs=[]
    def add(self,text,color=WHITE):
        if text.startswith("__"): return
        self._msgs.append([text,color,MSG_DURATION])
        if len(self._msgs)>MSG_MAX*2: self._msgs=self._msgs[-MSG_MAX:]
    def update(self): self._msgs=[[t,c,tm-1] for t,c,tm in self._msgs if tm>1]
    def recent(self,n=6): return [(t,c) for t,c,_ in self._msgs[-n:]]


# ═══════════════════════════════════════════════════════════════════════════════
#  Cheat Engine (P1 only)
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
#  Cheat Engine (P1 only) — typed code words during gameplay
# ═══════════════════════════════════════════════════════════════════════════════
# Map typed code → internal tag.  Codes are checked case-insensitively.
CHEAT_CODES = {
    'GODMODE':   'god',
    'ANUBIS':    'god',      # 2P-safe godmode (avoids O key)
    'MAXHP':     'maxhp',
    'MAXMANA':   'maxmana',
    'GIVEALL':   'giveall',
    'NOCLIP':    'noclip',
    'RESPAWN':   'respawn',
    'LEVELUP':   'levelup',
    'FULLCLEAR': 'fullclear',
    'TELE':      'teleport',
}
# Max length of any code word — buffer is trimmed to this to avoid unbounded growth
_CHEAT_MAX_LEN = max(len(k) for k in CHEAT_CODES)
class CheatEngine:
    def __init__(self): self.god_mode=False; self.no_clip=False
    @property
    def display(self):
        t=[]
        if self.god_mode: t.append("GOD")
        if self.no_clip:  t.append("NOCLIP")
        return " ".join(t)


# ═══════════════════════════════════════════════════════════════════════════════
#  Main Game
# ═══════════════════════════════════════════════════════════════════════════════
class Game:
    def __init__(self, screen, clock, seed=12345):
        self.screen=screen; self.clock=clock; self.seed=seed
        self._settings    = GameSettings(); self._settings.load()
        self._state       = ST_MENU
        self._menu_cursor = 0; self._pause_cursor = 0
        self._seed_str    = str(seed)
        self._players: list = []
        self._maps: dict    = {}
        self.current_map    = None; self._current_map_name="Town"
        self.camera         = Camera(); self.projectiles=[]
        self.log            = MessageLog()
        self.hud            = HUD()
        self.inv_screen     = InventoryScreen()
        self.settings_screen= SettingsScreen(self._settings)
        self._inv_player    = 0
        self.rng            = random.Random(seed); self._score=0
        self._viewport      = pygame.Surface((SCREEN_WIDTH,VIEWPORT_H))
        self._pending_msgs: list = []
        self._cheats        = CheatEngine()
        self._cheat_buf     = ""
        self.asset_mgr      = AssetManager()
        self._dungeon_maps: dict  = {}
        self._boss_killed: dict   = {}
        self._key_tracker   = KeyTracker()
        self._descent_pos: dict   = {}
        self._prev_state    = ST_MENU
        # ── New gameplay state (initialised here so load-game always finds them) ──
        self._princesses: dict    = {9:None,10:None,11:None,12:None}
        self._princesses_saved: set = set()
        self._mob_kills: int      = 0
        self._town_npcs: list     = []
        self._dialog_npc          = None
        self._trader_npc    = None
        self._trader_cursor: int  = 0
        self._trader_player: int  = 0   # which player is trading
        self._charmed_mobs: list     = [None, None]  # one pet per player

    def run(self):
        sound_engine.init()
        sound_engine.play_area_music(MAP_TOWN)   # start music immediately
        while True:
            self.clock.tick(FPS)
            self._handle_events(); self._update(); self._draw()
            pygame.display.flip()

    # ── Active players (living + all if game over) ──────────────────────────
    @property
    def _active_players(self): return self._players

    # ── Events ───────────────────────────────────────────────────────────────
    def _handle_events(self):
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            # Feed every key event to the software tracker (bypasses hw rollover)
            if ev.type==pygame.KEYDOWN: self._key_tracker.press(ev.key)
            elif ev.type==pygame.KEYUP: self._key_tracker.release(ev.key)
            if   self._state==ST_MENU:      self._ev_menu(ev)
            elif self._state==ST_PLAY:      self._ev_play(ev)
            elif self._state==ST_INVENTORY: self._ev_inv(ev)
            elif self._state==ST_PAUSED:    self._ev_pause(ev)
            elif self._state==ST_SETTINGS:  self._ev_settings(ev)
            elif self._state==ST_DIALOG:    self._ev_dialog(ev)
            elif self._state==ST_TRADER:    self._ev_trader(ev)
            elif self._state in (ST_GAMEOVER,ST_WIN):
                if ev.type==pygame.KEYDOWN and ev.key==pygame.K_RETURN:
                    self._state=ST_MENU

    def _ev_menu(self,ev):
        if ev.type!=pygame.KEYDOWN: return
        has_save=os.path.exists(SAVE_FILE)
        n=3 if has_save else 2
        if ev.key==pygame.K_UP:    self._menu_cursor=(self._menu_cursor-1)%n
        elif ev.key==pygame.K_DOWN: self._menu_cursor=(self._menu_cursor+1)%n
        elif ev.key==pygame.K_LEFT: self._settings.difficulty=(self._settings.difficulty-1)%3
        elif ev.key==pygame.K_RIGHT:self._settings.difficulty=(self._settings.difficulty+1)%3
        elif ev.key==pygame.K_TAB:
            self._settings.num_players=2 if self._settings.num_players==1 else 1
        elif ev.key==pygame.K_RETURN: self._menu_select(has_save)
        elif ev.key==pygame.K_BACKSPACE: self._seed_str=self._seed_str[:-1] or "0"
        elif ev.unicode.isdigit() and len(self._seed_str)<10:
            self._seed_str+=ev.unicode
            try: self.seed=int(self._seed_str)
            except ValueError: pass

    def _menu_select(self,has_save):
        opts=["new"]+(["load"] if has_save else [])+["quit"]
        ch=opts[self._menu_cursor]
        if ch=="new":   self._start_game()
        elif ch=="load":
            if not self._load_game(): self.log.add("Corrupt save.",RED); self._start_game()
        elif ch=="quit": pygame.quit(); sys.exit()

    def _ev_pause(self,ev):
        if ev.type!=pygame.KEYDOWN: return
        N=5
        if ev.key==pygame.K_ESCAPE:  self._state=ST_PLAY
        elif ev.key==pygame.K_UP:    self._pause_cursor=(self._pause_cursor-1)%N
        elif ev.key==pygame.K_DOWN:  self._pause_cursor=(self._pause_cursor+1)%N
        elif ev.key==pygame.K_RETURN: self._pause_select()

    def _pause_select(self):
        c=self._pause_cursor
        # 0=Resume 1=Settings 2=NewGame 3=Save&Quit 4=Quit
        if   c==0: self._state=ST_PLAY
        elif c==1: self._prev_state=ST_PAUSED; self._state=ST_SETTINGS
        elif c==2: self._start_game()
        elif c==3: self._save_game(); pygame.quit(); sys.exit()
        elif c==4: pygame.quit(); sys.exit()

    def _ev_settings(self,ev):
        result=self.settings_screen.handle_event(ev)
        if result=='back':
            self._settings.save(); self._state=self._prev_state

    def _ev_play(self,ev):
        kb_list=self._settings.keybindings
        if ev.type==pygame.KEYDOWN:
            # Typed cheat codes — accumulate printable chars, test suffixes (all player counts)
            if ev.unicode and ev.unicode.isprintable():
                self._cheat_buf = (self._cheat_buf + ev.unicode.upper())[-_CHEAT_MAX_LEN:]
                for code, tag in CHEAT_CODES.items():
                    if self._cheat_buf.endswith(code):
                        self._apply_cheat(tag)
                        self._cheat_buf = ""
                        return

            for pi,p in enumerate(self._players):
                if pi>=self._settings.num_players: break
                kb=kb_list[pi]; k=ev.key
                if   k==kb.get('pause') and pi==0:
                    self._state=ST_PAUSED; self._pause_cursor=0
                    self._key_tracker.clear()
                elif k==kb.get('inventory'):
                    self._inv_player=pi; self._state=ST_INVENTORY
                    self._key_tracker.clear()   # prevent stuck movement keys
                elif k==kb.get('attack'):
                    if not p.is_ghost:
                        p.attack(self.current_map,self.current_map.entities,
                                 self.projectiles,self._pending_msgs)
                        self._check_chest_smash(pi)
                        # Register nearby enemies as threat for this player's pet
                        my_pet = self._charmed_mobs[pi] if pi < len(self._charmed_mobs) else None
                        if my_pet and my_pet.alive:
                            for e in self.current_map.entities:
                                if isinstance(e,Enemy) and e.alive and not isinstance(e,Pet):
                                    if math.hypot(e.cx-p.cx,e.cy-p.cy) < TILE_SIZE*5:
                                        my_pet.register_threat(e)
                        # SFX for melee
                        item=p.equipped_item()
                        if item:
                            from items import IT_WEAPON,IT_RANGED,IT_MAGIC
                            if item.itype==IT_WEAPON:
                                sound_engine.play_sfx('hit_melee')
                            elif item.itype==IT_RANGED:
                                sound_engine.play_sfx('hit_ranged')
                            elif item.itype==IT_MAGIC:
                                sound_engine.play_sfx('spell_cast')
                elif k==kb.get('interact'):
                    if not p.is_ghost:   # ghosts cannot interact
                        self._interact(pi)
                elif k==kb.get('aim_toggle'):
                    p.toggle_aim_mode()
                    self.log.add(f"P{pi+1} aim: {p.aim_mode}",CYAN)
                elif k==kb.get('unequip'):
                    p.unequip_slot(); self.log.add(f"P{pi+1} slot cleared.",GRAY)
                elif k==kb.get('hotbar_prev'): p.cycle_hotbar(-1)
                elif k==kb.get('hotbar_next'): p.cycle_hotbar(1)
                else:
                    for slot in range(HOTBAR_SLOTS):
                        if k==kb.get(f'hotbar_{slot+1}'):
                            p.equipped=slot; break

        elif ev.type==pygame.MOUSEBUTTONDOWN:
            if self._settings.num_players==1 and self._players:
                p=self._players[0]
                if ev.button==1 and not p.is_ghost:
                    p.attack(self.current_map,self.current_map.entities,
                             self.projectiles,self._pending_msgs)
                elif ev.button==4: p.cycle_hotbar(-1)
                elif ev.button==5: p.cycle_hotbar(1)

    def _ev_inv(self,ev):
        if ev.type!=pygame.KEYDOWN: return
        pi=self._inv_player
        p=self._players[pi] if pi<len(self._players) else self._players[0]

        FEED_TYPES = {'bread','meat','mushroom','herb','potion','mana_pot','elixir',
                      'blue_flower','magic_dust'}   # items accepted as food/health

        # F = feed charmed pet companion with selected item
        if ev.key == pygame.K_f:
            pet = self._charmed_mobs[pi] if pi < len(self._charmed_mobs) else None
            if pet and pet.alive and isinstance(pet, Pet):
                slots = list(p.inventory)
                cursor = self.inv_screen.cursor if hasattr(self.inv_screen,'cursor') else 0
                # Try selected slot first, then fall back to first available feed item
                chosen_iid = None
                if 0 <= cursor < len(slots):
                    sel_item, sel_cnt = slots[cursor]
                    if sel_item.iid in FEED_TYPES and sel_cnt > 0:
                        chosen_iid = sel_item.iid
                if chosen_iid is None:
                    for it, cnt in slots:
                        if it.iid in FEED_TYPES and cnt > 0:
                            chosen_iid = it.iid; break
                if chosen_iid:
                    from items import ITEMS as _I
                    p.inventory.remove(chosen_iid, 1)
                    item_def = _I.get(chosen_iid)
                    hp_restore = getattr(item_def,'hp_restore',0) or pet.max_hp//4
                    heal = min(hp_restore, pet.max_hp - pet.hp)
                    pet.hp = min(pet.max_hp, pet.hp + max(heal, hp_restore))
                    name = item_def.name if item_def else chosen_iid
                    self.log.add(f"Fed {pet.etype} {name} (+{max(heal,hp_restore)} HP).", (180,255,180))
                else:
                    self.log.add("Select a food/health item in inventory first!", GRAY)
            else:
                self.log.add("No companion to feed.", GRAY)
            self._state = ST_PLAY; return

        # G = give selected food/health item to nearest following princess
        if ev.key == pygame.K_g:
            from items import ITEMS as _I
            best_pr = None; best_dist = float('inf')
            if self._players:
                p0 = self._players[0]
                for pr in self._princesses.values():
                    if pr and pr.state == 'following' and pr.alive:
                        d = math.hypot(pr.cx-p0.cx, pr.cy-p0.cy)
                        if d < best_dist:
                            best_dist = d; best_pr = pr
            if best_pr:
                slots = list(p.inventory)
                cursor = self.inv_screen.cursor if hasattr(self.inv_screen,'cursor') else 0
                chosen_iid = None
                if 0 <= cursor < len(slots):
                    sel_item, sel_cnt = slots[cursor]
                    if sel_item.iid in FEED_TYPES and sel_cnt > 0:
                        chosen_iid = sel_item.iid
                if chosen_iid is None:
                    for it, cnt in slots:
                        if it.iid in FEED_TYPES and cnt > 0:
                            chosen_iid = it.iid; break
                if chosen_iid:
                    item_def = _I.get(chosen_iid)
                    p.inventory.remove(chosen_iid, 1)
                    hp_restore = getattr(item_def,'hp_restore',0) or 15
                    heal = min(hp_restore, best_pr.max_hp - best_pr.hp)
                    best_pr.hp = min(best_pr.max_hp, best_pr.hp + max(heal, hp_restore))
                    name = item_def.name if item_def else chosen_iid
                    self.log.add(f"Gave {best_pr.name} {name} (+{max(heal,hp_restore)} HP).",
                                 (255,200,220))
                else:
                    self.log.add("Select a food/health item in inventory first!", GRAY)
            else:
                self.log.add("No princess nearby.", GRAY)
            self._state = ST_PLAY; return

        close=self.inv_screen.handle_key(ev,p,self._pending_msgs)
        # Spawn dropped item — process and immediately remove drop messages so
        # they can't fire again on a subsequent keypress (e.g. ESC to close).
        processed = []
        for msg_text,_ in self._pending_msgs:
            if msg_text.startswith("__DROP__:"):
                iid=msg_text.split(":",1)[1]
                if iid in ITEMS:
                    ptx=int(p.cx//TILE_SIZE); pty=int(p.cy//TILE_SIZE)
                    target=self.current_map.find_walkable_near(ptx,pty,3)
                    self.current_map.ground_items.append(
                        GroundItem(make_item(iid),target[0],target[1],1,
                                   lifetime=DROPPED_ITEM_LIFETIME_FRAMES))
                processed.append(msg_text)
        # Strip the processed drop signals; keep human-readable messages
        self._pending_msgs = [(t,c) for t,c in self._pending_msgs
                              if t not in processed]
        # Also close if ESC or the opening player's inventory key is pressed
        kb=self._settings.keybindings[pi]
        if ev.key==kb.get('inventory') or ev.key==pygame.K_ESCAPE:
            close=True
        if close: self._state=ST_PLAY

    def _ev_dialog(self, ev):
        """Dismiss/advance NPC dialog with E, Space, Enter, or Escape."""
        if ev.type != pygame.KEYDOWN: return
        if ev.key in (pygame.K_e, pygame.K_SPACE, pygame.K_RETURN, pygame.K_u,
                      pygame.K_ESCAPE, pygame.K_m):
            if self._dialog_npc:
                self._dialog_npc.next_page()
            if ev.key == pygame.K_ESCAPE:
                self._dialog_npc = None
                self._state = ST_PLAY

    def _ev_trader(self, ev):
        """Handle the trader shop UI."""
        if ev.type != pygame.KEYDOWN: return
        stock = Trader.STOCK
        cursor = self._trader_cursor
        pi = getattr(self, '_trader_player', 0)   # the player who opened the shop
        p  = self._players[pi] if pi < len(self._players) else self._players[0]

        if ev.key == pygame.K_ESCAPE:
            self._trader_npc = None; self._state = ST_PLAY; return
        if ev.key == pygame.K_UP:
            self._trader_cursor = (cursor - 1) % len(stock); return
        if ev.key == pygame.K_DOWN:
            self._trader_cursor = (cursor + 1) % len(stock); return

        if not p: return
        iid, buy_price, sell_price = stock[cursor]
        item_def = ITEMS.get(iid)

        # B = buy from trader
        if ev.key == pygame.K_b:
            if item_def and p.inventory.gold >= buy_price:
                if p.inventory.add(make_item(iid), 1):
                    p.inventory.add_gold(-buy_price)
                    self.log.add(f"Bought {item_def.name} for {buy_price}g.", WHITE)
                else:
                    self.log.add("Inventory full!", RED)
            else:
                self.log.add("Not enough gold!" if item_def else "Unknown item.", RED)

        # S = sell to trader (any non-rare item)
        elif ev.key == pygame.K_s:
            RARE_ITEMS = {'dragon_blade','shadow_staff','area_blast','void_bolt',
                          'swiftboots','iron_armor','dragon_scale'}
            # Find the first owned non-rare item matching cursor iid
            if p.inventory.has(iid) and iid not in RARE_ITEMS and sell_price > 0:
                p.inventory.remove(iid, 1)
                p.inventory.add_gold(sell_price)
                self.log.add(f"Sold {item_def.name} for {sell_price}g.", WHITE)
            else:
                self.log.add("Can't sell that here.", GRAY)

    # ── Cheats ───────────────────────────────────────────────────────────────
    def _apply_cheat(self,tag):
        for p in self._players:
            if tag=="maxhp":   p.hp=p.max_hp
            elif tag=="maxmana": p.mana=p.max_mana
            elif tag=="giveall":
                for iid in ITEMS: p.inventory.add(make_item(iid),5)
            elif tag=="levelup":
                p.max_hp+=20;p.hp=p.max_hp;p.max_mana+=20;p.mana=p.max_mana
        if tag=="god":
            self._cheats.god_mode=not self._cheats.god_mode
            self.log.add(f"GOD {'ON' if self._cheats.god_mode else 'OFF'}",PURPLE)
        elif tag=="noclip":
            self._cheats.no_clip=not self._cheats.no_clip
            self.log.add(f"NOCLIP {'ON' if self._cheats.no_clip else 'OFF'}",PURPLE)
        elif tag=="respawn": self._respawn_map(self.current_map); self.log.add("Respawned!",ORANGE)
        elif tag=="fullclear":
            for e in list(self.current_map.entities): e.hp=0;e.alive=False
            self.log.add("All cleared!",YELLOW)
        elif tag=="teleport":
            # Warp entire party (players + pet + following princesses) back to town
            town_map = self._maps.get(MAP_TOWN)
            if town_map:
                self.current_map = town_map
                self._current_map_name = "Town"
                self.projectiles.clear()
                mid_tx = TOWN_W // 2; mid_ty = TOWN_H // 2
                for i, pl in enumerate(self._players):
                    ox = (i % 2) * 2 - 1   # slight offset per player
                    pt = town_map.find_walkable_near(mid_tx + ox, mid_ty, 4)
                    pl.x = pt[0]*TILE_SIZE; pl.y = pt[1]*TILE_SIZE
                self.camera.snap(self._players, TOWN_W*TILE_SIZE, TOWN_H*TILE_SIZE)
                self._transport_companions(town_map)
                sound_engine.play_area_music(MAP_TOWN)
                self.log.add("TELE: Party warped to town.", PURPLE)
            else:
                self.log.add("No town map loaded yet.", RED)
        elif tag in("maxhp","maxmana"): self.log.add(f"Restored.",GREEN)

    def _respawn_map(self,gmap):
        gmap.entities.clear()
        if gmap.is_dungeon: self._spawn_dungeon_ents(gmap)
        else: self._populate_biome_ents(gmap)

    # ── Interaction ──────────────────────────────────────────────────────────
    #def _interact(self, pi: int):
    #    p=self._players[pi]; gmap=self.current_map
    #    fx,fy=p.facing
    #    tx=int((p.cx+fx*TILE_SIZE*0.6)//TILE_SIZE)
    #    ty=int((p.cy+fy*TILE_SIZE*0.6)//TILE_SIZE)
    #    t=gmap.get(tx,ty)
        
        
    def _interact(self, pi: int):
        p = self._players[pi]
        gmap = self.current_map

        px = int(p.cx // TILE_SIZE)
        py = int(p.cy // TILE_SIZE)
        fx, fy = p.facing

        # Candidate tiles: on, front, and forward diagonals
        candidates = [
            (px, py),                 # current tile
            (px + fx, py + fy),       # directly in front
            (px + fx - fy, py + fy - fx),  # front-left diagonal
            (px + fx + fy, py + fy + fx),  # front-right diagonal
        ]

        for tx, ty in candidates:
            if not gmap.in_bounds(tx, ty):
                continue

            t = gmap.get(tx, ty)

            if t in GATE_TILES:
                self._use_gate(gmap,t,tx,ty)   # shared – all players travel
            elif t==T_ENTRANCE:
                self._enter_dungeon_from_map(gmap,tx,ty)
            elif t==T_STAIRS_UP and gmap.is_dungeon:
                self._ascend_dungeon()
            elif t==T_STAIRS_DOWN and gmap.is_dungeon:
                self._descend_dungeon()
            elif t==T_CHEST and (tx,ty) not in gmap.chest_opened:
                self._open_chest(gmap,tx,ty)
            elif t==T_SHRINE:
                for pl in self._players:
                    pl.hp=pl.max_hp; pl.mana=pl.max_mana
                    if pl.is_ghost:
                        pl.alive=True; pl.is_ghost=False
                        pl.iframes=PLAYER_IFRAMES*2
                self._save_game(); self.log.add("Shrine heals all — saved!",CYAN)
                sound_engine.play_sfx('shrine')
                # Town shrine: save any following princess (alive and following)
                if self.current_map.map_key == MAP_TOWN:
                    for did, princess in list(self._princesses.items()):
                        if princess and princess.state == 'following' and princess.alive:
                            princess.state = 'saved'
                            self._princesses_saved.add(did)
                            self.log.add(f"{princess.name} is SAVED! ♥", (255,140,200))
                            self._score += 500
                    if len(self._princesses_saved) == 4:
                        self._state = ST_WIN
                # Castle shrine inside dungeon: revive princess if at_shrine
                elif self.current_map.is_dungeon:
                    did = self.current_map.dungeon_id
                    princess = self._princesses.get(did)
                    if princess and princess.state == 'at_shrine':
                        princess.state    = 'following'
                        princess.alive    = True          # ← was missing, caused invisible princess
                        princess.hp       = princess.max_hp
                        princess.iframes  = 0
                        princess.x        = p.cx; princess.y = p.cy
                        princess.follow_ref = p
                        princess._trail   = []
                        if princess not in self.current_map.entities:
                            self.current_map.entities.append(princess)
                        self.log.add(f"{princess.name} follows you again!", (255,180,220))
                return   # shrine handled, skip gate/chest checks below

            # Check NPC interaction (only in town)
            if self.current_map.map_key == MAP_TOWN:
                for npc in self._town_npcs:
                    if abs(npc.cx - p.cx) < TILE_SIZE*1.5 and abs(npc.cy - p.cy) < TILE_SIZE*1.5:
                        if isinstance(npc, Trader):
                            self._trader_npc    = npc
                            self._trader_cursor = 0
                            self._trader_player = pi   # remember which player is trading
                            self._state         = ST_TRADER
                        else:
                            self._dialog_npc = npc
                            self._state      = ST_DIALOG
                        return

            # Ground item pickup goes to this player's inventory
            ptx=int(p.cx//TILE_SIZE); pty=int(p.cy//TILE_SIZE)
            remove=[]
            for gi in gmap.ground_items:
                if gi.tx==ptx and gi.ty==pty:
                    if p.inventory.add(gi.item,gi.count):
                        self.log.add(f"P{pi+1} got {gi.item.name} x{gi.count}.",WHITE)
                        sound_engine.play_sfx('pickup')
                        remove.append(gi)
            for gi in remove: gmap.ground_items.remove(gi)

    # ── Gate / Map Travel ────────────────────────────────────────────────────
    def _use_gate(self, gmap, gate_tile, tx, ty):
        mk = gmap.map_key

        # --- Castle gate: haunted town's far gate enters a dungeon directly ---
        # Must be checked BEFORE the GATE_DESTINATIONS lookup, because castle
        # gates are not listed there (they enter a dungeon, not another map).
        if mk in CASTLE_DUNGEON_FOR_HAUNT and gate_tile == HAUNT_CASTLE_GATE.get(mk):
            dun_id = CASTLE_DUNGEON_FOR_HAUNT[mk]
            self._descent_pos[(dun_id, 'surface')] = [(p.x, p.y) for p in self._players]
            self._enter_dungeon(dun_id, 0, mk, 0, 0)
            sound_engine.play_sfx('gate_travel')
            return

        dest_map_key = GATE_DESTINATIONS.get(mk, {}).get(gate_tile)
        if dest_map_key is None:
            self.log.add("No route.", GRAY); return

        dest_map = self._get_or_build_map(dest_map_key)

        # Find which gate on the DESTINATION map leads BACK to us.
        # This is the correct arrival gate regardless of direction of travel.
        arriving_gate = None
        for g, dest in GATE_DESTINATIONS.get(dest_map_key, {}).items():
            if dest == mk:
                arriving_gate = g
                break

        # Collect all matching gate tiles in the destination map
        gate_positions = []
        for gy in range(dest_map.height):
            for gx in range(dest_map.width):
                if dest_map.get(gx, gy) == arriving_gate:
                    gate_positions.append((gx, gy))

        # Place each player on a distinct gate tile (they are always walkable)
        for i, pl in enumerate(self._players):
            idx = min(i, len(gate_positions) - 1) if gate_positions else -1
            if idx >= 0:
                gx, gy = gate_positions[idx]
                pl.x = gx * TILE_SIZE + (TILE_SIZE - ENTITY_SIZE) // 2
                pl.y = gy * TILE_SIZE + (TILE_SIZE - ENTITY_SIZE) // 2
            else:
                near = dest_map.find_walkable_near(dest_map.width//2, dest_map.height//2, 10)
                pl.x = near[0]*TILE_SIZE + (TILE_SIZE-ENTITY_SIZE)//2
                pl.y = near[1]*TILE_SIZE + (TILE_SIZE-ENTITY_SIZE)//2

        self.current_map = dest_map
        self._current_map_name = BIOME_NAMES.get(dest_map_key, dest_map_key.title())
        if dest_map_key == MAP_TOWN: self._current_map_name = "Town"
        self.projectiles.clear()
        self.camera.snap(self._players,
                          dest_map.width*TILE_SIZE, dest_map.height*TILE_SIZE)
        self.log.add(f"Entered {self._current_map_name}.", ORANGE)
        sound_engine.play_sfx('gate_travel')
        sound_engine.play_area_music(dest_map_key)
        self._transport_companions(dest_map)

    def _find_gate_spawn(self, gmap, gate_tile_type):
        for y in range(gmap.height):
            for x in range(gmap.width):
                if gmap.get(x, y) == gate_tile_type:
                    if gmap.walkable(x, y):
                        return (x, y)
                    return gmap.find_walkable_near(x, y, 3)
        return gmap.find_walkable_near(gmap.width // 2, gmap.height // 2, 10)

    def _get_or_build_map(self,map_key):
        if map_key not in self._maps:
            if map_key==MAP_TOWN:
                gmap,_=build_town(self.seed)
                self._populate_town_ents(gmap)
            elif map_key in HAUNT_MAP_KEYS:
                gmap,_=build_haunted_town(self.seed,map_key)
                self._populate_haunt_ents(gmap)
            else:
                gmap=build_biome_map(self.seed,map_key)
                self._populate_biome_ents(gmap)
            self._maps[map_key]=gmap
        return self._maps[map_key]

    def _transport_companions(self, dest_map):
        """Move Pet and following Princesses to dest_map alongside the player."""
        p0 = self._players[0] if self._players else None
        # Transport Pet
        for pi2, pet in enumerate(self._charmed_mobs):
            if pet and pet.alive:
                if pet not in dest_map.entities:
                    dest_map.entities.append(pet)
                if p0:
                    near = dest_map.find_walkable_near(
                        int(p0.cx//TILE_SIZE), int(p0.cy//TILE_SIZE), 4)
                    pet.x = near[0]*TILE_SIZE + (TILE_SIZE-pet.SIZE)//2
                    pet.y = near[1]*TILE_SIZE + (TILE_SIZE-pet.SIZE)//2
                    pet._trail.clear()
                pet._threats.clear()
        # Transport following princesses
        for did, princess in self._princesses.items():
            if princess and princess.state == 'following' and princess.alive:
                if p0:
                    near = dest_map.find_walkable_near(
                        int(p0.cx//TILE_SIZE), int(p0.cy//TILE_SIZE), 5)
                    princess.x = near[0]*TILE_SIZE + (TILE_SIZE-princess.SIZE)//2
                    princess.y = near[1]*TILE_SIZE + (TILE_SIZE-princess.SIZE)//2

    # ── Dungeon Travel ───────────────────────────────────────────────────────
    def _enter_dungeon_from_map(self,gmap,tx,ty):
        dun_id=None
        for dtx,dty,did in getattr(gmap,'biome_dungeon_positions',[]):
            if dtx==tx and dty==ty: dun_id=did; break
        if dun_id is None: self.log.add("Unknown dungeon.",RED); return
        self._descent_pos[(dun_id,'surface')] = [(p.x,p.y) for p in self._players]
        self._enter_dungeon(dun_id,0,gmap.map_key,tx,ty)

    def _enter_dungeon(self,dun_id,level,return_map_key,ow_tx,ow_ty):
        key=(dun_id,level)
        if key not in self._dungeon_maps:
            dmap=build_dungeon_level(self.seed,dun_id,level)
            dmap.ow_entrance=(ow_tx,ow_ty)
            dmap.return_map_key=return_map_key
            self._spawn_dungeon_ents(dmap)
            self._dungeon_maps[key]=dmap
        dmap=self._dungeon_maps[key]
        ex,ey=dmap.entrance_tile
        for i,pl in enumerate(self._players):
            pl.x=(ex+i)*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
            pl.y=ey*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
        self.current_map=dmap
        lvl_str=f" L{level+1}" if DUNGEONS[dun_id]['levels']>1 else ""
        self._current_map_name=DUNGEONS[dun_id]['name']+lvl_str
        self.projectiles.clear()
        self.camera.snap(self._players,dmap.width*TILE_SIZE,dmap.height*TILE_SIZE)
        self.log.add(f"Entered {self._current_map_name}!",ORANGE)
        sound_engine.play_area_music('', dungeon_id=dun_id)
        sound_engine.play_sfx('stairs_down')
        self._transport_companions(dmap)

    def _ascend_dungeon(self):
        dmap=self.current_map; did=dmap.dungeon_id; lvl=dmap.dungeon_level
        if lvl==0:
            ret_key=getattr(dmap,'return_map_key',MAP_EAST)
            ret_map=self._get_or_build_map(ret_key)
            surface_positions=self._descent_pos.get((did,'surface'),None)
            for i,pl in enumerate(self._players):
                if surface_positions and i<len(surface_positions):
                    pl.x,pl.y=surface_positions[i]
                else:
                    # Castle: spawn at the castle gate in the haunted town
                    if ret_key in CASTLE_DUNGEON_FOR_HAUNT.values().__class__.__mro__:
                        pass
                    ox,oy=dmap.ow_entrance
                    pl.x=ox*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
                    pl.y=oy*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
            self.current_map=ret_map
            self._current_map_name=BIOME_NAMES.get(ret_key,ret_key.title())
            if ret_key==MAP_TOWN: self._current_map_name="Town"
        else:
            upper_positions=self._descent_pos.get((did,lvl-1),None)
            upper_key=(did,lvl-1)
            if upper_key not in self._dungeon_maps:
                self._enter_dungeon(did,lvl-1,
                                    getattr(dmap,'return_map_key',MAP_EAST),
                                    *dmap.ow_entrance)
                return
            upper_map=self._dungeon_maps[upper_key]
            for i,pl in enumerate(self._players):
                if upper_positions and i<len(upper_positions):
                    pl.x,pl.y=upper_positions[i]
                else:
                    if upper_map.stairs_down_tile:
                        sdx,sdy=upper_map.stairs_down_tile
                        pl.x=sdx*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
                        pl.y=sdy*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
            self.current_map=upper_map
            self._current_map_name=DUNGEONS[did]['name']+f" L{lvl}"
        self.projectiles.clear()
        self.camera.snap(self._players,self.current_map.width*TILE_SIZE,
                                        self.current_map.height*TILE_SIZE)
        self.log.add("You ascend.",GREEN)
        sound_engine.play_sfx('stairs_up')
        sound_engine.play_area_music(self.current_map.map_key,
            self.current_map.dungeon_id if self.current_map.is_dungeon else -1)
        self._transport_companions(self.current_map)

    def _descend_dungeon(self):
        dmap=self.current_map; did=dmap.dungeon_id; lvl=dmap.dungeon_level
        if lvl+1>=DUNGEONS[did]['levels']: self.log.add("No deeper levels.",GRAY); return
        self._descent_pos[(did,lvl)] = [(p.x,p.y) for p in self._players]
        ret_key=getattr(dmap,'return_map_key',MAP_EAST)
        ox,oy=dmap.ow_entrance
        self._enter_dungeon(did,lvl+1,ret_key,ox,oy)
        sound_engine.play_sfx('stairs_down')

    def _spawn_dungeon_ents(self,dmap):
        boss_killed=self._boss_killed.get((dmap.dungeon_id,dmap.dungeon_level),False)
        for sp in getattr(dmap,'enemy_spawns',[]):
            if sp.get('boss') and boss_killed: continue
            try:
                e=spawn_enemy(sp['type'],sp['tx'],sp['ty'],is_boss=sp.get('boss',False))
                dmap.entities.append(e)
            except Exception as ex:
                print(f"[Spawn] Failed to spawn {sp.get('type')}: {ex}")
        for sp in getattr(dmap,'item_spawns',[]):
            try:
                gi=GroundItem(make_item(sp['iid']),sp['tx'],sp['ty'],sp['count'])
                dmap.ground_items.append(gi)
            except Exception as ex:
                print(f"[Spawn] Failed to spawn item {sp.get('iid')}: {ex}")

    # ── Chest ────────────────────────────────────────────────────────────────
    def _chest_floor_tile(self, gmap, tx, ty):
        """Determine the ground tile to reveal when a chest is removed.
        Look at all 4 adjacent walkable tiles and return the most common type."""
        from collections import Counter
        neighbours = []
        for dx,dy in DIRS_4:
            nx,ny=tx+dx,ty+dy
            if gmap.in_bounds(nx,ny):
                t=gmap.get(nx,ny)
                if tile_walkable(t) and t not in (T_CHEST, T_CHEST_OPEN, T_ENTRANCE):
                    neighbours.append(t)
        if neighbours:
            return Counter(neighbours).most_common(1)[0][0]
        # Fallback
        if gmap.is_dungeon:
            return DUNGEONS[gmap.dungeon_id]['floor']
        return T_PATH if gmap.map_key==MAP_TOWN else T_GRASS

    def _is_mimic(self, gmap, tx, ty):
        """Deterministic mimic check based on map+position+seed."""
        h = _det_hash((self.seed, gmap.map_key, tx, ty)) & 0xFFFFFFFF
        return (h % 100) < int(MIMIC_CHANCE * 100)

    def _open_chest(self, gmap, tx, ty):
        """Interact with chest: loot it (leaves opened chest tile), or trigger mimic."""
        if (tx,ty) in gmap.chest_opened:
            return  # already looted

        # Check for mimic
        if self._is_mimic(gmap, tx, ty) and (tx,ty) not in gmap.mimics_revealed:
            gmap.mimics_revealed.add((tx,ty))
            floor_t = self._chest_floor_tile(gmap, tx, ty)
            gmap.set(tx, ty, floor_t)
            # Spawn mimic
            from entities import spawn_enemy
            gmap.entities.append(spawn_enemy('mimic', tx, ty))
            self.log.add("It's a MIMIC! Run!", RED)
            return

        gmap.chest_opened.add((tx,ty))
        gmap.set(tx, ty, T_CHEST_OPEN)   # leave opened-chest sprite (non-walkable)
        drops=[]
        rng=random.Random(self.seed ^ _det_hash((gmap.map_key, tx, ty)))
        for _ in range(rng.randint(3,6)):
            drops.append((rng.choice(CHEST_LOOT_COMMON), rng.randint(1,4)))
        for _ in range(rng.randint(1,2)):
            drops.append((rng.choice(CHEST_LOOT_UNCOMMON), 1))
        if rng.random()<0.20: drops.append((rng.choice(CHEST_LOOT_RARE), 1))
        for iid,count in drops:
            try:
                it=make_item(iid)
                target=gmap.find_walkable_near(tx,ty,4)
                if target and gmap.walkable(*target):
                    gmap.ground_items.append(
                        GroundItem(it,target[0],target[1],count,
                                   lifetime=DROPPED_ITEM_LIFETIME_FRAMES*4))
                else:
                    nearest=min(self._players,key=lambda p:abs(p.cx//TILE_SIZE-tx)+abs(p.cy//TILE_SIZE-ty))
                    nearest.inventory.add(it,count)
                    self.log.add(f"Got {it.name} x{count}!",GOLD)
            except KeyError: pass
        self.log.add(f"Chest yields {len(drops)} items!",GOLD)
        sound_engine.play_sfx('chest_open')

    def _check_chest_smash(self, pi: int):
        """If the attacking player is facing a chest (open or closed), smash it."""
        p=self._players[pi]; gmap=self.current_map
        fx,fy=p.facing
        tx=int((p.cx+fx*TILE_SIZE*0.7)//TILE_SIZE)
        ty=int((p.cy+fy*TILE_SIZE*0.7)//TILE_SIZE)
        if gmap.in_bounds(tx,ty) and gmap.get(tx,ty) in (T_CHEST, T_CHEST_OPEN):
            self._smash_chest(gmap,tx,ty)

    def _smash_chest(self, gmap, tx, ty):
        """Destroy a chest: opened → just clear to floor (walkable). Unopened → drop items."""
        t=gmap.get(tx,ty)
        if t not in (T_CHEST, T_CHEST_OPEN): return
        floor_t = self._chest_floor_tile(gmap, tx, ty)
        gmap.set(tx, ty, floor_t)
        sound_engine.play_sfx('chest_smash')
        if t == T_CHEST_OPEN or (tx,ty) in gmap.chest_opened:
            self.log.add("Cleared the chest remains.", GRAY)
            return
        # Unopened chest — drop a few items
        gmap.chest_opened.add((tx,ty))
        rng=random.Random(self.seed ^ _det_hash((gmap.map_key, tx, ty, 0xBEEF)))
        drops=[(rng.choice(CHEST_LOOT_COMMON), rng.randint(1,3))]
        if rng.random()<0.4: drops.append((rng.choice(CHEST_LOOT_UNCOMMON),1))
        for iid,count in drops:
            try:
                it=make_item(iid)
                target=gmap.find_walkable_near(tx,ty,3)
                if target: gmap.ground_items.append(
                    GroundItem(it,target[0],target[1],count,
                               lifetime=DROPPED_ITEM_LIFETIME_FRAMES*2))
            except KeyError: pass
        self.log.add("Chest smashed! Fewer items.", ORANGE)

    # ── New Game ─────────────────────────────────────────────────────────────
    def _start_game(self):
        try: self.seed=int(self._seed_str) if self._seed_str else 12345
        except ValueError: self.seed=12345
        self.rng=random.Random(self.seed)
        self.log=MessageLog(); self.projectiles=[]
        self._dungeon_maps={}; self._maps={}; self._boss_killed={}
        self._descent_pos={}; self._pending_msgs=[]; self._score=0
        self._cheats=CheatEngine(); self._pause_cursor=0; self._cheat_buf=""
        self._charmed_mobs = [None, None]
        # Princess / win tracking
        DRAGON_DUNGEON_IDS = [9, 10, 11, 12]
        self._princesses: dict = {did: None for did in DRAGON_DUNGEON_IDS}
        self._princesses_saved: set = set()
        # Level / mob kill tracking
        self._mob_kills: int = 0
        # Town NPCs
        self._town_npcs: list = []
        # Active NPC dialog (None = no dialog open)
        self._dialog_npc = None
        # Active trader UI
        self._trader_npc = None
        self._trader_cursor: int = 0
        # Charmed companion (only 1 at a time)
        self._charmed_mob = None

        # Init sound if not done yet
        sound_engine.init()

        town_map,start_tile=build_town(self.seed)
        self._maps[MAP_TOWN]=town_map
        self._populate_town_ents(town_map)

        stx,sty=start_tile
        num=self._settings.num_players
        self._players=[]
        for i in range(num):
            px=(stx+i)*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
            py=sty*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
            if i > 0:
                candidates=[(stx+dx,sty+dy) for dx in range(-2,3) for dy in range(-2,3)]
                for cx2,cy2 in candidates:
                    if town_map.walkable(cx2,cy2):
                        px=cx2*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
                        py=cy2*TILE_SIZE+(TILE_SIZE-ENTITY_SIZE)//2
                        break
            pl=Player(px,py,player_idx=i)
            pl.aim_mode='auto' if num==2 else 'mouse'
            self._players.append(pl)

        self.current_map=town_map; self._current_map_name="Town"
        self.camera=Camera()
        self.camera.snap(self._players,town_map.width*TILE_SIZE,town_map.height*TILE_SIZE)
        self.inv_screen=InventoryScreen()

        self.log.add("Welcome to Rune & Shadow!",CYAN)
        if num==2:
            self.log.add("2-PLAYER MODE: Both players use auto-aim.",YELLOW)
            self.log.add("P1=WASD+Q(inv)  P2=IJKL+O(inv)  (Settings to rebind)",WHITE)
        else:
            self.log.add("Mouse=Aim  TAB=Toggle  Q=Inv  X=Unequip",WHITE)
            self.log.add("Type GODMODE/NOCLIP/GIVEALL etc. for cheats",GRAY)
        self.log.add("Gates N/S/E/W lead to different biomes.",LIGHT_GRAY)
        self._state=ST_PLAY

        sound_engine.play_area_music(MAP_TOWN)

    def _populate_town_ents(self,gmap):
        rng=random.Random(self.seed ^ 0xB077012)  # fixed seed for town items
        for _ in range(15):
            tx=rng.randint(2,TOWN_W-2);ty=rng.randint(2,TOWN_H-2)
            if not gmap.walkable(tx,ty): continue
            iid=rng.choice(['mushroom','herb','coin','coin','stone','bread','arrow'])
            gmap.ground_items.append(GroundItem(make_item(iid),tx,ty,rng.randint(1,3)))

        # Place Lorekeeper and Trader in town at fixed offsets from centre
        cx, cy = TOWN_W // 2, TOWN_H // 2
        # Find walkable spots near centre
        npc_spots = []
        for dy in range(-4, 5):
            for dx in range(-8, 9):
                tx2, ty2 = cx + dx, cy + dy
                if gmap.walkable(tx2, ty2):
                    npc_spots.append((tx2, ty2))
        # Pick two well-separated spots
        if len(npc_spots) >= 2:
            s1 = npc_spots[len(npc_spots) // 3]
            s2 = npc_spots[2 * len(npc_spots) // 3]
            lk = Lorekeeper(s1[0], s1[1])
            tr = Trader(s2[0], s2[1])
            self._town_npcs = [lk, tr]

    def _populate_biome_ents(self,gmap):
        # Per-map seeded RNG so biome content never depends on load order
        rng=random.Random(self.seed ^ _det_hash(gmap.map_key) ^ 0xB10BE)
        mk=gmap.map_key; W,H=gmap.width,gmap.height
        etype_pools={
            MAP_EAST: ['wolf','wolf','goblin','slime','slime','bat','bat','spider'],
            MAP_NORTH:['yeti','yeti','bat','skeleton','ice_wraith'],
            MAP_SOUTH:['scorpion','scorpion','goblin','mummy','skeleton'],
            MAP_WEST: ['swamp_toad','swamp_toad','slime','spider','will_o','ghost'],
        }
        water_ents={MAP_EAST:'kelpie',MAP_WEST:'swamp_toad',MAP_NORTH:'kelpie',MAP_SOUTH:'kelpie'}
        pool=etype_pools.get(mk,['slime','bat'])
        for _ in range(50):
            tx=rng.randint(5,W-5);ty=rng.randint(5,H-5)
            if not gmap.walkable(tx,ty) or gmap.get(tx,ty) in GATE_TILES: continue
            gmap.entities.append(spawn_enemy(rng.choice(pool),tx,ty))
        water_e=water_ents.get(mk,'kelpie')
        for _ in range(10):
            tx=rng.randint(5,W-5);ty=rng.randint(5,H-5)
            if tile_swimmable(gmap.get(tx,ty)):
                gmap.entities.append(spawn_enemy(water_e,tx,ty))
        for _ in range(25):
            tx=rng.randint(5,W-5);ty=rng.randint(5,H-5)
            if not gmap.walkable(tx,ty): continue
            iid=rng.choice(['mushroom','herb','stone','stone','coin','blue_flower','bread','rope'])
            gmap.ground_items.append(GroundItem(make_item(iid),tx,ty,rng.randint(1,3)))

    def _populate_haunt_ents(self,gmap):
        """Populate a haunted town with undead enemies and some rare items."""
        rng=random.Random(self.seed ^ _det_hash(gmap.map_key) ^ 0xAB0DE)
        mk=gmap.map_key; W,H=gmap.width,gmap.height
        etype_pools={
            MAP_EAST_TOWN:  ['skeleton','ghost','will_o','bat'],
            MAP_NORTH_TOWN: ['skeleton','ice_wraith','yeti','ghost'],
            MAP_SOUTH_TOWN: ['mummy','skeleton','ghost','scorpion'],
            MAP_WEST_TOWN:  ['ghost','will_o','swamp_toad','bat'],
        }
        pool=etype_pools.get(mk,['skeleton','ghost'])
        for _ in range(35):
            tx=rng.randint(2,W-2);ty=rng.randint(2,H-2)
            if not gmap.walkable(tx,ty) or gmap.get(tx,ty) in GATE_TILES: continue
            gmap.entities.append(spawn_enemy(rng.choice(pool),tx,ty))
        # Rare item drops scattered around
        rare_pool=['elixir','mana_crys','big_gem','potion','magic_dust','spell_fire']
        for _ in range(10):
            tx=rng.randint(2,W-2);ty=rng.randint(2,H-2)
            if not gmap.walkable(tx,ty): continue
            try:
                gmap.ground_items.append(
                    GroundItem(make_item(rng.choice(rare_pool)),tx,ty,rng.randint(1,2),
                               lifetime=DROPPED_ITEM_LIFETIME_FRAMES*6))
            except KeyError: pass

    # ── Save / Load ──────────────────────────────────────────────────────────
    def _save_game(self):
        dmap=self.current_map
        players_data=[]
        for p in self._players:
            players_data.append({
                'x':p.x,'y':p.y,'hp':p.hp,'max_hp':p.max_hp,
                'mana':p.mana,'max_mana':p.max_mana,'gold':p.inventory.gold,
                'hotbar':p.hotbar,'aim_mode':p.aim_mode,
                'inventory':{it.iid:cnt for it,cnt in p.inventory._slots},
            })
        # Serialise princess states
        princess_data = {}
        for did, pr in self._princesses.items():
            if pr is None:
                princess_data[str(did)] = None
            else:
                princess_data[str(did)] = {
                    'state': pr.state, 'hp': pr.hp,
                    'x': pr.x, 'y': pr.y,
                }
        data={
            'seed':self.seed,'score':self._score,
            'num_players':self._settings.num_players,
            'players':players_data,
            'map_key':dmap.map_key,
            'dungeon_id':dmap.dungeon_id if dmap.is_dungeon else -1,
            'dungeon_level':dmap.dungeon_level if dmap.is_dungeon else 0,
            'boss_killed':{f"{k[0]}_{k[1]}":v for k,v in self._boss_killed.items()},
            'chest_opened':{mk:list(m.chest_opened) for mk,m in self._maps.items()},
            'dungeon_chests':{f"{k[0]}_{k[1]}":list(v.chest_opened)
                              for k,v in self._dungeon_maps.items()},
            'princess_data': princess_data,
            'princesses_saved': list(self._princesses_saved),
            'mob_kills': self._mob_kills,
            'charmed_etypes': [
                (self._charmed_mobs[i].etype if self._charmed_mobs[i] and self._charmed_mobs[i].alive else None)
                for i in range(2)
            ],
        }
        try:
            with open(SAVE_FILE,'w') as f: json.dump(data,f,indent=2)
            self._settings.save()
            self.log.add("Game saved.",GREEN)
        except Exception as ex: self.log.add(f"Save failed: {ex}",RED)

    def _load_game(self):
        try:
            with open(SAVE_FILE) as f: data=json.load(f)
            self.seed=data['seed']; self._seed_str=str(self.seed)
            self._score=data.get('score',0)
            self._settings.num_players=data.get('num_players',1)
            self.rng=random.Random(self.seed)
            self.log=MessageLog(); self.projectiles=[]
            self._dungeon_maps={}; self._maps={}; self._descent_pos={}
            self._pending_msgs=[]; self._cheats=CheatEngine(); self._cheat_buf=""
            self._boss_killed={tuple(int(x) for x in k.split("_")):v
                               for k,v in data.get('boss_killed',{}).items()}

            town_map,_=build_town(self.seed)
            self._maps[MAP_TOWN]=town_map; self._populate_town_ents(town_map)
            for mk,chests in data.get('chest_opened',{}).items():
                if mk==MAP_TOWN:
                    town_map.chest_opened=set(tuple(c) for c in chests); continue
                try:
                    bmap=build_biome_map(self.seed,mk)
                    bmap.chest_opened=set(tuple(c) for c in chests)
                    self._populate_biome_ents(bmap); self._maps[mk]=bmap
                except Exception: pass
            for ks,chests in data.get('dungeon_chests',{}).items():
                parts=ks.split("_"); did,lvl=int(parts[0]),int(parts[1])
                try:
                    dmap=build_dungeon_level(self.seed,did,lvl)
                    dmap.chest_opened=set(tuple(c) for c in chests)
                    dmap.return_map_key=DUNGEONS[did].get('biome',MAP_EAST)
                    self._spawn_dungeon_ents(dmap); self._dungeon_maps[(did,lvl)]=dmap
                except Exception: pass

            num=self._settings.num_players
            self._players=[]
            for i,pd in enumerate(data.get('players',data.get('player',[data.get('player',{})])
                                           if isinstance(data.get('player'),list) else [data.get('player',{})])):
                if i>=num and num>0: break
                pl=Player(pd.get('x',100),pd.get('y',100),player_idx=i)
                pl.hp=pd.get('hp',100);pl.max_hp=pd.get('max_hp',100)
                pl.mana=pd.get('mana',60);pl.max_mana=pd.get('max_mana',60)
                pl.inventory.gold=pd.get('gold',0)
                pl.hotbar=pd.get('hotbar',[None]*HOTBAR_SLOTS)
                pl.aim_mode=pd.get('aim_mode','auto' if num==2 else 'mouse')
                pl.inventory._slots.clear()
                for iid,cnt in pd.get('inventory',{}).items():
                    if iid in ITEMS: pl.inventory._slots.append([make_item(iid),cnt])
                self._players.append(pl)
            if not self._players:
                self._players=[Player(100,100,0)]

            mk=data.get('map_key',MAP_TOWN); did=data.get('dungeon_id',-1); lvl=data.get('dungeon_level',0)
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
            self.camera.snap(self._players,self.current_map.width*TILE_SIZE,
                                            self.current_map.height*TILE_SIZE)
            self.inv_screen=InventoryScreen()

            # Restore princess states
            self._princesses = {9:None,10:None,11:None,12:None}
            self._princesses_saved = set()
            for did_s, pdata in data.get('princess_data',{}).items():
                did = int(did_s)
                if pdata is None: continue
                pr = Princess(did, pdata.get('x',100), pdata.get('y',100))
                pr.state = pdata.get('state','at_shrine')
                pr.hp    = pdata.get('hp', pr.max_hp)
                pr.alive = (pr.state == 'following')
                self._princesses[did] = pr
            for did in data.get('princesses_saved', []):
                self._princesses_saved.add(int(did))

            # Restore mob kills counter
            self._mob_kills = data.get('mob_kills', 0)

            self._charmed_mobs = [None, None]  # pets not restored on load

            # Re-populate town NPCs
            town_map = self._maps.get(MAP_TOWN)
            if town_map:
                self._populate_town_ents(town_map)

            self.log.add("Save loaded.",CYAN); self._state=ST_PLAY; return True
        except Exception as ex: print(f"Load error: {ex}"); return False

    # ── Update ───────────────────────────────────────────────────────────────
    def _update(self):
        if self._state!=ST_PLAY: return
        gmap=self.current_map; self._pending_msgs=[]
        diff=self._settings.difficulty
        num=self._settings.num_players

        # Snapshot positions BEFORE movement (for camera blame-the-mover logic)
        prev_positions=[(p.x,p.y) for p in self._players[:num]]

        for i,p in enumerate(self._players):
            if i>=num: break
            if self._cheats.god_mode:
                p.hp=p.max_hp; p.mana=p.max_mana
                # Only set iframes when not already invincible — prevents the
                # iframes PLAYER_IFRAMES→PLAYER_IFRAMES-1 transition every
                # frame that was triggering the player_hurt SFX on loop.
                if p.iframes < PLAYER_IFRAMES:
                    p.iframes = PLAYER_IFRAMES
            input_state=self._settings.make_input_state(self._key_tracker,i)
            mouse_pos=(pygame.mouse.get_pos() if p.aim_mode=='mouse' and i==0 else None)
            p.update(input_state,gmap,gmap.entities,self.projectiles,
                     self._pending_msgs,cam_x=self.camera.ix,cam_y=self.camera.iy,
                     mouse_pos=mouse_pos)
            # Noclip override
            if self._cheats.no_clip:
                dx=dy=0.0; spd=PLAYER_SPEED
                if input_state.get('left'):  dx-=1.0
                if input_state.get('right'): dx+=1.0
                if input_state.get('up'):    dy-=1.0
                if input_state.get('down'):  dy+=1.0
                if dx and dy: dx*=0.7071; dy*=0.7071
                p.x+=dx*spd; p.y+=dy*spd
                mw=gmap.width*TILE_SIZE; mh=gmap.height*TILE_SIZE
                p.x=max(0,min(p.x,mw-ENTITY_SIZE)); p.y=max(0,min(p.y,mh-ENTITY_SIZE))

        # Build combined target list: players + following princess + pet companion
        # Enemies aggro on and attack all of these exactly like players
        _targets = list(self._players[:num])
        for _pr in self._princesses.values():
            if _pr and _pr.state == 'following' and _pr.alive:
                _targets.append(_pr)
        for _pet in self._charmed_mobs:
            if _pet and _pet.alive:
                _targets.append(_pet)   # enemies can target either pet

        # Enemies and Pets (pass all targets to enemies; pets update separately)
        for e in list(gmap.entities):
            if isinstance(e, Princess): continue   # handled separately below
            if isinstance(e, Pet):
                if e.alive:
                    foes = [x for x in gmap.entities
                            if isinstance(x, Enemy) and x.alive and not isinstance(x, Pet)]
                    e.update(gmap, foes)
                else:
                    gmap.entities.remove(e)
                    for pi2, pm in enumerate(self._charmed_mobs):
                        if pm is e:
                            self._charmed_mobs[pi2] = None
                            self.log.add(f"P{pi2+1}'s companion has fallen!", (255,100,100))
                continue
            if e.alive:
                e.update(_targets,gmap,self.projectiles,self._pending_msgs)
            else:
                drops=e.get_drops(self.rng)
                tx=int(e.cx//TILE_SIZE); ty=int(e.cy//TILE_SIZE)
                for it in drops:
                    target=gmap.find_walkable_near(tx,ty,2)
                    gmap.ground_items.append(
                        GroundItem(it,target[0],target[1],1,lifetime=DROPPED_ITEM_LIFETIME_FRAMES))
                self._score+=10*(5 if e.is_boss else 1)
                # Killed an enemy — register it was a threat to the pet
                # (no-op since it's dead, but threat already added on attack)
                if e.is_boss and gmap.is_dungeon:
                    self._boss_killed[(gmap.dungeon_id,gmap.dungeon_level)]=True
                    # Level up the nearest player for killing a dungeon boss
                    if self._players:
                        p0 = self._players[0]
                        p0.max_hp   += 20; p0.hp    = p0.max_hp
                        p0.max_mana += 20; p0.mana  = p0.max_mana
                        if len(self._players) > 1:
                            p1 = self._players[1]
                            p1.max_hp   += 20; p1.hp    = p1.max_hp
                            p1.max_mana += 20; p1.mana  = p1.max_mana
                        self.log.add("LEVEL UP! Boss defeated!", (255,215,0))
                    # Dragon boss: spawn princess
                    DRAGON_BOSSES = {9:'dragon',10:'frost_dragon',11:'sand_dragon',12:'swamp_dragon'}
                    if gmap.dungeon_id in DRAGON_BOSSES and e.etype == DRAGON_BOSSES[gmap.dungeon_id]:
                        princess = Princess(gmap.dungeon_id, e.cx, e.cy)
                        if self._players:
                            princess.follow_ref = self._players[0]
                        gmap.entities.append(princess)
                        self._princesses[gmap.dungeon_id] = princess
                        self.log.add(f"{princess.name} is freed! Lead her to the town shrine!",
                                     (255,180,220))
                # Non-boss overworld: count toward 100-mob level up
                if not e.is_boss:
                    self._mob_kills += 1
                    if self._mob_kills % 100 == 0:
                        for p in self._players[:num]:
                            p.max_hp   += 10; p.hp    = p.max_hp
                            p.max_mana += 10; p.mana  = p.max_mana
                        self.log.add(f"LEVEL UP! {self._mob_kills} foes slain!", (255,215,0))
                if not gmap.is_dungeon and not e.is_boss:
                    gmap.respawn_queue.append([OVERWORLD_MOB_RESPAWN_FRAMES,
                                               {'type':e.etype,'tx':tx,'ty':ty}])
                gmap.entities.remove(e)

        # Check for player hurt/dead events to trigger SFX (not in godmode)
        if not self._cheats.god_mode:
            for p in self._players[:num]:
                if p.iframes == PLAYER_IFRAMES - 1:   # just took damage this frame
                    if p.alive:
                        sound_engine.play_sfx('player_hurt')
                    else:
                        sound_engine.play_sfx('player_dead')

        # Projectiles
        for proj in list(self.projectiles):
            proj.update(gmap,self._players[:num],gmap.entities,self._pending_msgs,diff)
            if not proj.alive: self.projectiles.remove(proj)

        # Ground items + coin auto-pickup  (ghosts cannot pick up anything)
        for gi in list(gmap.ground_items):
            gi.update()
            if gi.expired: gmap.ground_items.remove(gi); continue
            for p in self._players[:num]:
                if p.is_ghost: continue   # ghost cannot pick up items
                ptx=int(p.cx//TILE_SIZE); pty=int(p.cy//TILE_SIZE)
                if gi.tx==ptx and gi.ty==pty and gi.item.itype==IT_CURRENCY:
                    p.inventory.gold+=gi.item.value*gi.count
                    self.log.add(f"+{gi.item.value*gi.count} gold!",GOLD)
                    sound_engine.play_sfx('pickup')
                    if gi in gmap.ground_items: gmap.ground_items.remove(gi)
                    break

        self._process_respawns(gmap)

        # ── Process pending internal signals ──────────────────────────────────
        # (Feed and give are handled directly in _ev_inv; no deferred signals needed)

        # Charm spell: spawn a Pet for the casting player (each player has their own slot)
        for p_check in self._players[:num]:
            if getattr(p_check, 'charm_cast', False):
                pi_charm = p_check.player_idx
                p_check.charm_cast = False
                foes = [e for e in gmap.entities
                        if isinstance(e, Enemy) and e.alive
                        and not isinstance(e, Pet)
                        and not e.is_boss]
                if foes:
                    nearest = min(foes, key=lambda e: math.hypot(e.cx-p_check.cx, e.cy-p_check.cy))
                    if math.hypot(nearest.cx-p_check.cx, nearest.cy-p_check.cy) < TILE_SIZE * 6:
                        # Release THIS player's current pet only
                        old_pet = self._charmed_mobs[pi_charm] if pi_charm < len(self._charmed_mobs) else None
                        if old_pet and old_pet.alive:
                            old_pet.alive = False
                        # Spawn new Pet for this player
                        pet = Pet(nearest)
                        pet.owner = p_check
                        nearest.alive = False
                        gmap.entities.append(pet)
                        self._charmed_mobs[pi_charm] = pet
                        self.log.add(f"P{pi_charm+1}: {nearest.name} is charmed!", (200, 80, 255))
                    else:
                        p_check.inventory.add(make_item('charm_spell'), 1)
                        self.log.add("No enemy in charm range — spell returned.", RED)
                else:
                    p_check.inventory.add(make_item('charm_spell'), 1)
                    self.log.add("No enemy nearby — spell returned.", RED)

        # Register threats for pets: any enemy physically close that just hit a pet
        for pi2, pet in enumerate(self._charmed_mobs):
            if pet and pet.alive:
                if getattr(pet, '_was_just_hit', False):
                    pet._was_just_hit = False
                    for e in gmap.entities:
                        if isinstance(e, Enemy) and e.alive and not isinstance(e, Pet):
                            if math.hypot(e.cx-pet.cx, e.cy-pet.cy) < TILE_SIZE * 3:
                                pet.register_threat(e)
                for e in gmap.entities:
                    if isinstance(e, Enemy) and e.alive and not isinstance(e, Pet):
                        if e._aggroed and math.hypot(e.cx-pet.cx, e.cy-pet.cy) < TILE_SIZE*3:
                            pet.register_threat(e)

        # ── Update princess entities ───────────────────────────────────────────
        for did, princess in list(self._princesses.items()):
            if princess is None: continue
            if princess.state == 'following':
                was_alive = princess.alive
                princess.update(self._players[:num], gmap.entities, gmap)
                # Detect the moment she's knocked out → send message
                if was_alive and not princess.alive:
                    self.log.add(f"{princess.name} fell! Activate the castle shrine to revive her.",
                                 (255, 100, 100))
                    sound_engine.play_sfx('player_hurt')

        for text,col in self._pending_msgs:
            if not text.startswith("__"): self.log.add(text,col)
        self.log.update()

        mw=gmap.width*TILE_SIZE; mh=gmap.height*TILE_SIZE
        self.camera.follow(self._players[:num], mw, mh, prev_positions)

        # Game-over: all active players are either dead (not ghost) or both ghost
        active = self._players[:num]
        all_ghosts_or_dead = all(p.is_ghost or not p.alive for p in active)
        any_properly_alive = any(p.alive and not p.is_ghost for p in active)
        if all_ghosts_or_dead and not any_properly_alive and not self._cheats.god_mode:
            # Allow continuation only when exactly one ghost exists (other can revive at shrine)
            ghost_count = sum(1 for p in active if p.is_ghost)
            if ghost_count < len(active):  # at least one real player alive somewhere
                pass  # handled above — this branch won't reach here
            else:
                self._state = ST_GAMEOVER

    def _process_respawns(self,gmap):
        new_q=[]
        for entry in gmap.respawn_queue:
            entry[0]-=1
            if entry[0]<=0:
                sp=entry[1]
                near=any(abs(e.cx//TILE_SIZE-sp['tx'])<3 and
                         abs(e.cy//TILE_SIZE-sp['ty'])<3 for e in gmap.entities)
                if not near and gmap.walkable(sp['tx'],sp['ty']):
                    gmap.entities.append(spawn_enemy(sp['type'],sp['tx'],sp['ty']))
            else: new_q.append(entry)
        gmap.respawn_queue=new_q

    # ── Draw ─────────────────────────────────────────────────────────────────
    def _draw(self):
        self.screen.fill(BLACK)
        if self._state==ST_MENU:
            draw_main_menu(self.screen,self._seed_str,self._menu_cursor,
                           self._settings.difficulty,os.path.exists(SAVE_FILE),
                           self._settings.num_players); return
        if self._state==ST_GAMEOVER: draw_game_over(self.screen,self._score); return
        if self._state==ST_WIN:      draw_win(self.screen,self._score); return

        if self._state in(ST_PLAY,ST_INVENTORY,ST_PAUSED,ST_SETTINGS,ST_DIALOG,ST_TRADER):
            vp=self._viewport; vp.fill((10,10,14))
            cx,cy=self.camera.ix,self.camera.iy; gmap=self.current_map
            p1=self._players[0]
            # Collect extra light sources (P2 onwards)
            extra_lights = [(pl.x, pl.y, pl.light_radius)
                            for pl in self._players[1:] if pl.alive]
            gmap.draw(vp, cx, cy, p1.x, p1.y, p1.light_radius,
                      self.asset_mgr, extra_lights=extra_lights)
            def _best_brightness(ecx, ecy):
                return gmap.get_brightness_at(
                    ecx, ecy, p1.x, p1.y, p1.light_radius,
                    extra_lights=extra_lights)
            for e in gmap.entities:
                b=_best_brightness(e.cx,e.cy)
                e.draw(vp,cx,cy,self.asset_mgr,brightness=b)
                # Green ring around any pet companion
                for _pet in self._charmed_mobs:
                    if e is _pet and e.alive:
                        sx2=int(e.x)-cx; sy2=int(e.y)-cy
                        pygame.draw.rect(vp,(80,255,80),(sx2-2,sy2-2,e.SIZE+4,e.SIZE+4),2)
            for proj in self.projectiles: proj.draw(vp,cx,cy,self.asset_mgr)
            for p in self._players: p.draw(vp,cx,cy,self.asset_mgr)
            # Draw town NPCs
            if gmap.map_key == MAP_TOWN:
                for npc in self._town_npcs:
                    npc.draw(vp, cx, cy, self.asset_mgr)
            # Draw following princesses
            for did, princess in self._princesses.items():
                if princess and princess.state == 'following':
                    princess.draw(vp, cx, cy)
            self.screen.blit(vp,(0,0))
            self.hud.draw(self.screen,self._players,self._current_map_name,
                          self.log.recent(4),self.asset_mgr,
                          self._settings.difficulty,self._cheats.display,
                          self._settings.num_players)
            # Princess status bar
            self._draw_princess_status()
            self._draw_prompts(cx,cy,gmap)

        if self._state==ST_INVENTORY:
            pi=self._inv_player
            p=self._players[pi] if pi<len(self._players) else self._players[0]
            self.inv_screen.draw(self.screen,p,self.asset_mgr,pi)
            pet = self._charmed_mobs[pi] if pi < len(self._charmed_mobs) else None
            if pet and pet.alive and isinstance(pet, Pet):
                draw_text(self.screen,
                    f"[F] Feed {pet.etype}  HP:{pet.hp}/{pet.max_hp}",
                    20, VIEWPORT_H-44, 14, (180,255,180))
            # G hint for princess
            for pr in self._princesses.values():
                if pr and pr.state == 'following' and pr.alive:
                    draw_text(self.screen,
                        f"[G] Give food to {pr.name}  HP:{pr.hp}/{pr.max_hp}",
                        20, VIEWPORT_H-26, 14, (255,200,220))
                    break
        if self._state==ST_PAUSED:
            draw_paused(self.screen,self._pause_cursor,os.path.exists(SAVE_FILE))
        if self._state==ST_SETTINGS:
            self.settings_screen.draw(self.screen)
        if self._state==ST_DIALOG and self._dialog_npc:
            draw_npc_dialog(self.screen, self._dialog_npc)
        if self._state==ST_TRADER and self._trader_npc:
            tp = self._players[getattr(self,'_trader_player',0)] if self._players else None
            draw_trader_shop(self.screen, self._trader_npc, self._trader_cursor,
                             tp.inventory.gold if tp else 0)

    def _draw_princess_status(self):
        """Small princess save tracker in top-right corner."""
        NAMES_SHORT = {9:"Lyra",10:"Frost",11:"Sola",12:"Mira"}
        COLORS      = {9:(255,180,210),10:(180,220,255),11:(255,220,150),12:(150,220,180)}
        x0 = SCREEN_WIDTH - 120; y0 = 8
        draw_text(self.screen, "Princesses:", x0, y0, 11, (200,180,200))
        for i, did in enumerate([9,10,11,12]):
            p = self._princesses.get(did)
            name = NAMES_SHORT[did]
            col  = COLORS[did]
            if did in self._princesses_saved:
                status = "♥ SAVED"; col = (255,215,0)
            elif p is None:
                status = "?"; col = DARK_GRAY
            elif p.state == 'following':
                status = "→ Follow"; col = (180,255,180)
            else:
                status = "✗ castle"; col = (180,100,100)
            draw_text(self.screen, f"{name}: {status}", x0, y0+16+i*14, 11, col)

    def _draw_prompts(self, cam_x, cam_y, gmap):
        # Show prompts near P1 (primary player) for now
        p=self._players[0]; fx,fy=p.facing
        tx=int((p.cx+fx*TILE_SIZE*0.6)//TILE_SIZE)
        ty=int((p.cy+fy*TILE_SIZE*0.6)//TILE_SIZE)
        t=gmap.get(tx,ty)
        sx=tx*TILE_SIZE-cam_x; sy=ty*TILE_SIZE-cam_y-24
        msg=None
        if   t in GATE_TILES:  msg="[E/KPEnter] Travel through gate"
        elif t==T_ENTRANCE:    msg="[E/KPEnter] Enter Dungeon"
        elif t==T_STAIRS_UP and gmap.is_dungeon: msg="[E/KPEnter] Ascend"
        elif t==T_STAIRS_DOWN: msg="[E/KPEnter] Descend deeper"
        elif t==T_CHEST and (tx,ty) not in gmap.chest_opened: msg="[E] Open Chest  [SPACE/ATK] Smash chest"
        elif t==T_CHEST_OPEN:  msg="[SPACE/ATK] Smash opened chest"
        elif t==T_SHRINE:      msg="[E/KPEnter] Shrine (Heal All + Save)"
        # NPC proximity hints
        if self.current_map.map_key == MAP_TOWN and self._players:
            p0 = self._players[0]
            for npc in self._town_npcs:
                if abs(npc.cx - p0.cx) < TILE_SIZE*1.5 and abs(npc.cy - p0.cy) < TILE_SIZE*1.5:
                    npc_type = "Trade (B/S)" if hasattr(npc, 'STOCK') else "Talk"
                    msg = f"[E] {npc.name}: {npc_type}"
                    sx = int(npc.x) - cam_x; sy = int(npc.y) - cam_y - 24
                    break
        for player in self._players:
            ptx=int(player.cx//TILE_SIZE); pty=int(player.cy//TILE_SIZE)
            for gi in gmap.ground_items:
                if gi.tx==ptx and gi.ty==pty and gi.item.itype!=IT_CURRENCY:
                    pn=PLAYER_NAMES[player.player_idx]
                    msg=f"[E] {pn}: Pick up {gi.item.name}"
                    sx=int(player.x)-cam_x; sy=int(player.y)-cam_y-24; break
        if msg: draw_text(self.screen,msg,sx,sy,14,YELLOW)
