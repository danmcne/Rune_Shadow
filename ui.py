"""
Rune & Shadow - UI v4
HUD (1P or 2P bars), InventoryScreen (player name header),
SettingsScreen (rebindable keys), all menus.
"""
import pygame
from constants import *
from items import ITEMS

_fonts = {}
def font(size):
    if size not in _fonts:
        _fonts[size] = pygame.font.SysFont("monospace", size, bold=False)
    return _fonts[size]

def draw_text(surf, text, x, y, size=16, color=WHITE, shadow=True):
    f = font(size)
    if shadow:
        surf.blit(f.render(text, True, BLACK), (x+1, y+1))
    surf.blit(f.render(text, True, color), (x, y))

def draw_bar(surf, x, y, w, h, value, max_val, fg, bg=DARK_GRAY, label=""):
    pygame.draw.rect(surf, bg, (x, y, w, h))
    filled = int(w * max(0, value) / max(1, max_val))
    pygame.draw.rect(surf, fg, (x, y, filled, h))
    pygame.draw.rect(surf, WHITE, (x, y, w, h), 1)
    if label:
        draw_text(surf, label, x+4, y+1, size=12, shadow=False)


# ═══════════════════════════════════════════════════════════════════════════════
#  HUD  (supports 1 or 2 players)
# ═══════════════════════════════════════════════════════════════════════════════
class HUD:
    SLOT_SIZE = 40
    SLOT_PAD  = 3

    def __init__(self):
        self._surf = pygame.Surface((SCREEN_WIDTH, HUD_H))

    def draw(self, screen, players, map_name, messages,
             asset_mgr=None, difficulty=DIFFICULTY_NORMAL,
             cheat_display="", num_players=1):
        s = self._surf
        s.fill((20, 20, 28))
        pygame.draw.line(s, (80, 80, 100), (0, 0), (SCREEN_WIDTH, 0), 2)

        num = min(num_players, len(players))
        # In 2P mode each player gets 5 hotbar slots; 1P gets all 8
        eff_slots = HOTBAR_SLOTS_2P if num > 1 else HOTBAR_SLOTS

        if num == 1:
            self._draw_player_bars(s, players[0], 8, 8, 160)
            status_x = 178
            p = players[0]
            if p.is_swimming:   draw_text(s, "~SWIM~", status_x, 56, 12, CYAN)
            elif p.is_slowed:   draw_text(s, "~SLOW~", status_x, 56, 12, (100,200,100))
            aim_col = YELLOW if p.aim_mode == 'mouse' else CYAN
            draw_text(s, f"AIM:{p.aim_mode[0].upper()}", status_x, 8, 11, aim_col)
            draw_text(s, "[TAB]", status_x, 20, 10, GRAY)
            self._draw_hotbar(s, players[0],
                              SCREEN_WIDTH//2 - (eff_slots*(self.SLOT_SIZE+self.SLOT_PAD))//2,
                              50, label="P1", slots=eff_slots, asset_mgr=asset_mgr)
        else:
            # P1 left, P2 right
            self._draw_player_bars(s, players[0], 4, 4, 140, label=PLAYER_NAMES[0])
            self._draw_player_bars(s, players[1], SCREEN_WIDTH-144, 4, 140,
                                   label=PLAYER_NAMES[1], p2=True)
            # P1 hotbar (5 slots, keys 1-5)
            self._draw_hotbar(s, players[0],
                              SCREEN_WIDTH//5 - (eff_slots*(self.SLOT_SIZE+self.SLOT_PAD))//2,
                              70, label="P1", slots=eff_slots, asset_mgr=asset_mgr)
            # P2 hotbar (5 slots, keys 6-0)
            self._draw_hotbar(s, players[1],
                              4*SCREEN_WIDTH//5 - (eff_slots*(self.SLOT_SIZE+self.SLOT_PAD))//2,
                              70, label="P2", slots=eff_slots, asset_mgr=asset_mgr)

        diff_col = [GREEN, WHITE, RED][difficulty]
        draw_text(s, DIFFICULTY_LABELS[difficulty], SCREEN_WIDTH//2 - 24, 4, 11, diff_col)
        draw_text(s, map_name, SCREEN_WIDTH//2, 16, 14, LIGHT_GRAY)
        if cheat_display:
            draw_text(s, f"[{cheat_display}]", SCREEN_WIDTH//2 - 30, 32, 11, PURPLE)

        # Messages (right side)
        msg_x = SCREEN_WIDTH - 310
        for mi, (msg, col) in enumerate(messages[-4:]):
            draw_text(s, msg, msg_x, 4 + mi * 18, 12, col)

        # Controls footer
        if num == 1:
            ctrl = "SPACE/Click=Attack  E=Interact  Q=Inv  F=Cycle  X=Unequip  ESC=Pause"
        else:
            ctrl = "P1:WASD+Space+E+Q(inv)   P2:IJKL+M(atk)+U(use)+O(inv)   Settings=rebind"
        draw_text(s, ctrl, SCREEN_WIDTH//2 - 300, HUD_H - 14, 11, (120,120,140), False)

        screen.blit(s, (0, VIEWPORT_H))

    def _draw_player_bars(self, s, player, x, y, w, label="", p2=False):
        col_name = ORANGE if p2 else YELLOW
        if label:
            draw_text(s, label, x, y, 11, col_name, False)
            y += 13
        draw_bar(s, x, y,    w, 14, player.hp,   player.max_hp,
                 RED,  label=f"HP {player.hp}/{player.max_hp}")
        draw_bar(s, x, y+16, w, 14, player.mana, player.max_mana,
                 BLUE, label=f"MP {player.mana}/{player.max_mana}")
        draw_text(s, f"G:{player.inventory.gold}", x, y+32, 11, GOLD, False)

    def _draw_hotbar(self, s, player, hb_x, hb_y, label="", slots=None, asset_mgr=None):
        if slots is None:
            slots = HOTBAR_SLOTS
        if label:
            draw_text(s, label, hb_x - 20, hb_y + 10, 11,
                      YELLOW if player.player_idx == 0 else ORANGE, False)
        sz = self.SLOT_SIZE; pad = self.SLOT_PAD
        for i in range(slots):
            iid = player.hotbar[i] if i < len(player.hotbar) else None
            sx  = hb_x + i * (sz + pad)
            sel = (i == player.equipped)
            pygame.draw.rect(s, (30, 30, 45), (sx, hb_y, sz, sz))
            pygame.draw.rect(s, YELLOW if sel else (60, 60, 80), (sx, hb_y, sz, sz), 2)
            if iid and iid in ITEMS:
                it = ITEMS[iid]; isz = sz - 10
                spr = asset_mgr.get_item_icon(iid) if asset_mgr else None
                if spr:
                    scaled = pygame.transform.scale(spr, (isz, isz))
                    s.blit(scaled, (sx + 5, hb_y + 5))
                else:
                    pygame.draw.rect(s, it.color, (sx+5, hb_y+5, isz, isz))
                cnt = player.inventory.count(iid)
                if it.stackable and cnt > 0:
                    draw_text(s, str(cnt), sx+sz-14, hb_y+sz-14, 10, WHITE, False)
            draw_text(s, str(i+1), sx+2, hb_y+2, 10, GRAY, False)

    def _draw_mini_hotbar(self, s, player, hb_x, hb_y, label="", slots=None):
        """Compact single-pixel-height hotbar for P2."""
        if slots is None:
            slots = HOTBAR_SLOTS
        sz = 16; pad = 2
        if label:
            draw_text(s, label, hb_x - 20, hb_y, 10, ORANGE, False)
        for i in range(slots):
            iid = player.hotbar[i] if i < len(player.hotbar) else None
            sx  = hb_x + i * (sz + pad)
            sel = (i == player.equipped)
            pygame.draw.rect(s, (40, 30, 20), (sx, hb_y, sz, sz))
            pygame.draw.rect(s, ORANGE if sel else (80, 60, 30), (sx, hb_y, sz, sz), 1)
            if iid and iid in ITEMS:
                pygame.draw.rect(s, ITEMS[iid].color, (sx+2, hb_y+2, sz-4, sz-4))


# ═══════════════════════════════════════════════════════════════════════════════
#  Inventory Screen  (shows whose inventory at top)
# ═══════════════════════════════════════════════════════════════════════════════
class InventoryScreen:
    COLS = 6; ROWS = 8; SZ = 52; PAD = 6
    PANEL_W = COLS*(52+6)+6+220
    PANEL_H = ROWS*(52+6)+6+90

    def __init__(self):
        self.cursor = 0

    def handle_key(self, event, player, messages):
        inv   = player.inventory
        slots = list(inv.items())
        n     = len(slots)
        k     = event.key

        if k in (pygame.K_ESCAPE, pygame.K_i):
            return True

        if   k == pygame.K_UP:    self.cursor = (self.cursor - self.COLS) % max(1, n)
        elif k == pygame.K_DOWN:  self.cursor = (self.cursor + self.COLS) % max(1, n)
        elif k == pygame.K_LEFT:  self.cursor = (self.cursor - 1) % max(1, n)
        elif k == pygame.K_RIGHT: self.cursor = (self.cursor + 1) % max(1, n)

        elif k in (pygame.K_RETURN, pygame.K_e):
            if 0 <= self.cursor < n:
                item, _ = slots[self.cursor]
                if item.itype == IT_CONSUMABLE:
                    player.use_item(item.iid, messages)
                elif item.itype not in (IT_CURRENCY, IT_INGREDIENT, IT_AMMO):
                    target = next((i for i in range(HOTBAR_SLOTS)
                                   if player.hotbar[i] is None), player.equipped)
                    player.hotbar[target] = item.iid
                    messages.append((f"Equipped {item.name} → slot {target+1}.", YELLOW))
                else:
                    messages.append(("Can't equip that.", GRAY))

        elif k == pygame.K_SPACE:
            if 0 <= self.cursor < n:
                item, _ = slots[self.cursor]
                if item.itype == IT_CONSUMABLE:
                    player.use_item(item.iid, messages)
                else:
                    messages.append(("Press E to equip.", GRAY))

        elif k == pygame.K_u:
            if 0 <= self.cursor < n:
                item, _ = slots[self.cursor]
                cleared = False
                for si in range(HOTBAR_SLOTS):
                    if player.hotbar[si] == item.iid:
                        player.hotbar[si] = None; cleared = True; break
                messages.append(("Unequipped." if cleared else "Not equipped.", GRAY))

        elif k == pygame.K_d:
            if 0 <= self.cursor < n:
                item, _ = slots[self.cursor]
                if item.itype == IT_CURRENCY:
                    messages.append(("Gold drops automatically.", GRAY))
                else:
                    if inv.remove(item.iid, 1):
                        if inv.count(item.iid) == 0:
                            for si in range(HOTBAR_SLOTS):
                                if player.hotbar[si] == item.iid:
                                    player.hotbar[si] = None
                        messages.append((f"__DROP__:{item.iid}", WHITE))
                        messages.append((f"Dropped {item.name}.", ORANGE))
                        self.cursor = min(self.cursor, max(0, len(list(inv.items()))-1))

        elif pygame.K_1 <= k <= pygame.K_8:
            slot = k - pygame.K_1
            if 0 <= self.cursor < n:
                item, _ = slots[self.cursor]
                player.hotbar[slot] = item.iid
                messages.append((f"{item.name} → slot {slot+1}", YELLOW))

        return False

    def draw(self, screen, player, asset_mgr=None, player_idx=0):
        inv   = player.inventory
        slots = list(inv.items())

        ov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        screen.blit(ov, (0, 0))

        px = (SCREEN_WIDTH  - self.PANEL_W) // 2
        py = (SCREEN_HEIGHT - self.PANEL_H) // 2

        pygame.draw.rect(screen, (20, 20, 35), (px, py, self.PANEL_W, self.PANEL_H))
        pygame.draw.rect(screen, (80, 80, 120), (px, py, self.PANEL_W, self.PANEL_H), 2)

        # Player name banner
        p_col  = YELLOW if player_idx == 0 else ORANGE
        banner = f"── {PLAYER_NAMES[player_idx]} INVENTORY ──"
        draw_text(screen, banner, px+8, py+8, 19, p_col)
        draw_text(screen, f"Gold: {inv.gold}", px+8, py+30, 14, GOLD)

        # Item grid
        for i, (item, count) in enumerate(slots):
            col_ = i % self.COLS
            row_ = i // self.COLS
            sx   = px + self.PAD + col_ * (self.SZ + self.PAD)
            sy   = py + 54 + row_ * (self.SZ + self.PAD)
            bg   = (80, 80, 150) if i == self.cursor else (40, 40, 60)
            border = YELLOW if i == self.cursor else (60, 60, 90)
            pygame.draw.rect(screen, bg,     (sx, sy, self.SZ, self.SZ))
            pygame.draw.rect(screen, border, (sx, sy, self.SZ, self.SZ), 2)
            isz  = self.SZ - 16
            spr = asset_mgr.get_item_icon(item.iid) if asset_mgr else None
            if spr:
                scaled = pygame.transform.scale(spr, (isz, isz))
                screen.blit(scaled, (sx + 8, sy + 8))
            else:
                pygame.draw.rect(screen, item.color, (sx+8, sy+8, isz, isz))
            if item.stackable and count > 1:
                draw_text(screen, str(count), sx+self.SZ-20, sy+self.SZ-18, 12, WHITE, False)
            if item.iid in player.hotbar:
                pygame.draw.rect(screen, p_col, (sx, sy, self.SZ, self.SZ), 2)
                draw_text(screen, "E", sx+2, sy+2, 10, p_col, False)

        # Right info panel
        if 0 <= self.cursor < len(slots):
            item, count = slots[self.cursor]
            ix = px + self.COLS*(self.SZ+self.PAD) + 10
            iy = py + 54
            # Large item portrait (sprite or coloured square)
            PORT = 48
            spr = asset_mgr.get_item_icon(item.iid) if asset_mgr else None
            if spr:
                scaled = pygame.transform.scale(spr, (PORT, PORT))
                screen.blit(scaled, (ix, iy))
            else:
                pygame.draw.rect(screen, item.color, (ix, iy, PORT, PORT))
                pygame.draw.rect(screen, WHITE, (ix, iy, PORT, PORT), 1)
            draw_text(screen, item.name,             ix + PORT + 6, iy,     18, WHITE)
            draw_text(screen, f"Type: {item.itype}", ix + PORT + 6, iy+22,  12, LIGHT_GRAY)
            lines = []
            if item.damage:       lines.append(f"Dmg: {item.damage}")
            if item.defense:      lines.append(f"Def: +{item.defense}")
            if item.hp_restore:   lines.append(f"Heal: +{item.hp_restore}")
            if item.mp_restore:   lines.append(f"Mana: +{item.mp_restore}")
            if item.mana_cost:    lines.append(f"Cost: {item.mana_cost}MP")
            if item.light_radius: lines.append(f"Light: {item.light_radius}t")
            if count > 1:         lines.append(f"Qty: x{count}")
            for li, ln in enumerate(lines):
                draw_text(screen, ln, ix, iy + PORT + 6 + li*17, 13, LIGHT_GRAY)
            yo = iy + PORT + 6 + len(lines)*17 + 8
            desc = item.description
            for li in range(0, min(len(desc), 110), 22):
                draw_text(screen, desc[li:li+22], ix, yo + (li//22)*16, 12, GRAY)
            yo += 72
            if item.itype == IT_CONSUMABLE:
                draw_text(screen, "[Enter/Space]=Use", ix, yo,    13, GREEN)
            else:
                draw_text(screen, "[Enter/E]=Equip",   ix, yo,    13, CYAN)
                draw_text(screen, "[U]=Unequip",        ix, yo+16, 13, YELLOW)
            draw_text(screen, "[D]=Drop",               ix, yo+32, 13, ORANGE)

        # Footer controls
        draw_text(screen,
            "[Arrows]=Nav  [E]=Equip  [Space]=Use  [U]=Unequip  [D]=Drop  [1-8]=Slot  [I/ESC]=Close",
            px+4, py+self.PANEL_H-22, 11, (100,100,130), False)


# ═══════════════════════════════════════════════════════════════════════════════
#  Settings Screen  (key rebinding)
# ═══════════════════════════════════════════════════════════════════════════════
class SettingsScreen:
    """Full keybinding editor for both players."""

    PAGE_SIZE = 12   # actions shown per page

    def __init__(self, settings):
        self._settings   = settings
        self._player_tab = 0      # 0 or 1
        self._cursor     = 0
        self._waiting    = False  # True when waiting for a key press to bind
        self._page       = 0

    def handle_event(self, ev):
        if self._waiting:
            if ev.type == pygame.KEYDOWN:
                action = PLAYER_ACTIONS[self._page * self.PAGE_SIZE + self._cursor]
                if ev.key == pygame.K_ESCAPE:
                    self._waiting = False   # cancel bind
                else:
                    self._settings.set_key(self._player_tab, action, ev.key)
                    self._waiting = False
            return None

        if ev.type != pygame.KEYDOWN:
            return None
        k = ev.key

        n_actions = len(PLAYER_ACTIONS)
        n_pages   = (n_actions + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        page_len  = min(self.PAGE_SIZE,
                        n_actions - self._page * self.PAGE_SIZE)

        if k == pygame.K_ESCAPE:
            return 'back'
        elif k == pygame.K_TAB:
            # Switch between player tabs
            if self._settings.num_players > 1:
                self._player_tab = 1 - self._player_tab
                self._cursor = 0; self._page = 0
        elif k == pygame.K_UP:
            self._cursor = (self._cursor - 1) % page_len
        elif k == pygame.K_DOWN:
            self._cursor = (self._cursor + 1) % page_len
        elif k == pygame.K_LEFT:
            self._page   = (self._page - 1) % n_pages
            self._cursor = 0
        elif k == pygame.K_RIGHT:
            self._page   = (self._page + 1) % n_pages
            self._cursor = 0
        elif k == pygame.K_RETURN:
            self._waiting = True
        elif k == pygame.K_DELETE or k == pygame.K_BACKSPACE:
            action = PLAYER_ACTIONS[self._page * self.PAGE_SIZE + self._cursor]
            self._settings.set_key(self._player_tab, action, None)
        elif k == pygame.K_F1:
            # Reset to defaults
            from game import GameSettings
            defaults = [GameSettings._p1_defaults(), GameSettings._p2_defaults()]
            self._settings.keybindings[self._player_tab] = defaults[self._player_tab]

        return None

    def draw(self, screen):
        ov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 180))
        screen.blit(ov, (0, 0))

        pw, ph = 640, 500
        px = SCREEN_WIDTH//2  - pw//2
        py = SCREEN_HEIGHT//2 - ph//2
        pygame.draw.rect(screen, (15, 15, 30), (px, py, pw, ph))
        pygame.draw.rect(screen, (80, 60, 140), (px, py, pw, ph), 2)

        draw_text(screen, "── KEY BINDINGS ──", px + pw//2 - 100, py + 10, 22, YELLOW)

        # Player tabs
        for ti, name in enumerate(PLAYER_NAMES):
            tx  = px + 10 + ti * 150
            col = (YELLOW if ti == self._player_tab else GRAY)
            bg  = (40, 40, 80) if ti == self._player_tab else (20, 20, 40)
            pygame.draw.rect(screen, bg, (tx, py+36, 140, 22))
            pygame.draw.rect(screen, col, (tx, py+36, 140, 22), 1)
            draw_text(screen, name, tx+6, py+38, 14, col, False)
            if self._settings.num_players == 1 and ti == 1:
                draw_text(screen, "(2P only)", tx+6, py+38, 12, DARK_GRAY, False)

        # Column headers
        draw_text(screen, "Action",  px+14, py+64, 13, LIGHT_GRAY, False)
        draw_text(screen, "Key",     px+280, py+64, 13, LIGHT_GRAY, False)

        kb       = self._settings.keybindings[self._player_tab]
        n_acts   = len(PLAYER_ACTIONS)
        n_pages  = (n_acts + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        start    = self._page * self.PAGE_SIZE
        shown    = PLAYER_ACTIONS[start:start + self.PAGE_SIZE]

        for i, action in enumerate(shown):
            ry    = py + 82 + i * 26
            sel   = (i == self._cursor)
            bg    = (50, 50, 90) if sel else (25, 25, 45)
            pygame.draw.rect(screen, bg, (px+8, ry-1, pw-16, 24))

            label     = ACTION_LABELS.get(action, action)
            key_val   = kb.get(action)
            key_name  = (pygame.key.name(key_val).upper()
                         if key_val is not None else "—")
            key_col   = (CYAN if sel else LIGHT_GRAY)

            if self._waiting and sel:
                key_name = "▌ Press a key …"
                key_col  = YELLOW

            draw_text(screen, label,    px+14,  ry+2, 13, WHITE if sel else GRAY, False)
            draw_text(screen, key_name, px+280, ry+2, 13, key_col, False)

        # Page indicator
        draw_text(screen, f"Page {self._page+1}/{n_pages}",
                  px+pw//2-30, py+ph-56, 13, GRAY, False)
        draw_text(screen, "[←/→] page  [↑/↓] select  [Enter] rebind  [Del] clear  [F1] reset  [Tab] switch player  [ESC] back",
                  px+8, py+ph-34, 11, (90,90,110), False)

        # Number-of-players toggle
        np_col = CYAN
        draw_text(screen, f"Players: {self._settings.num_players}  (change on main menu via TAB)",
                  px+pw-280, py+42, 11, np_col, False)


# ═══════════════════════════════════════════════════════════════════════════════
#  Menus
# ═══════════════════════════════════════════════════════════════════════════════

def draw_main_menu(screen, seed_str, cursor, difficulty=DIFFICULTY_NORMAL,
                   has_save=False, num_players=1):
    screen.fill((10, 10, 20))
    draw_text(screen, "RUNE  &  SHADOW", SCREEN_WIDTH//2-180, 90, 52, GOLD)
    draw_text(screen, "A  Roguelike  Adventure", SCREEN_WIDTH//2-140, 150, 20, LIGHT_GRAY)

    opts = ["New Game"] + (["Load Save"] if has_save else []) + ["Quit"]
    for i, opt in enumerate(opts):
        col = YELLOW if i == cursor else LIGHT_GRAY
        draw_text(screen, opt, SCREEN_WIDTH//2-60, 228+i*50, 26, col)
        if i == cursor:
            draw_text(screen, "►", SCREEN_WIDTH//2-88, 228+i*50, 26, YELLOW)

    y_off = 228 + len(opts)*50 + 8

    # Difficulty
    draw_text(screen, "Difficulty:", SCREEN_WIDTH//2-100, y_off, 16, LIGHT_GRAY)
    for di, dlabel in enumerate(DIFFICULTY_LABELS):
        col = [GREEN, WHITE, RED][di]
        bx  = SCREEN_WIDTH//2 - 90 + di*80
        if di == difficulty:
            pygame.draw.rect(screen, col, (bx, y_off+22, 72, 24))
            draw_text(screen, dlabel, bx+6, y_off+24, 14, BLACK, False)
        else:
            pygame.draw.rect(screen, (40,40,50), (bx, y_off+22, 72, 24))
            draw_text(screen, dlabel, bx+6, y_off+24, 14, col, False)
    draw_text(screen, "[←/→]", SCREEN_WIDTH//2-100, y_off+52, 12, GRAY)

    # Players toggle
    y_off2 = y_off + 74
    draw_text(screen, f"Players: {num_players}", SCREEN_WIDTH//2-100, y_off2, 16, CYAN)
    draw_text(screen, "[TAB] to toggle 1P / 2P", SCREEN_WIDTH//2-100, y_off2+20, 13, GRAY)

    # Seed
    draw_text(screen, f"Seed: {seed_str}_", SCREEN_WIDTH//2-100, y_off2+46, 16, CYAN)
    draw_text(screen, "(type numbers)", SCREEN_WIDTH//2-100, y_off2+66, 12, GRAY)

    # Info block
    draw_text(screen, "Start in TOWN. Gates N/S/E/W → different biomes.",
              SCREEN_WIDTH//2-250, 648, 13, (100,120,160))
    draw_text(screen, "P1: WASD+Space+E+I    P2: Numpad (see Settings in pause menu)",
              SCREEN_WIDTH//2-250, 666, 13, (100,100,140))
    draw_text(screen, "Cheats (1P only): F1=GodMode  F2=MaxHP  F3=MaxMana  F4=GiveAll  F5=NoClip  F6=Respawn  F7=LevelUp  F8=FullClear",
              SCREEN_WIDTH//2-340, 684, 11, (80,80,100))


def draw_game_over(screen, score):
    screen.fill((10, 5, 5))
    draw_text(screen, "ALL PLAYERS DEAD", SCREEN_WIDTH//2-190, 190, 52, DARK_RED)
    draw_text(screen, f"Score: {score}", SCREEN_WIDTH//2-60, 290, 28, WHITE)
    draw_text(screen, "Press ENTER to return to menu", SCREEN_WIDTH//2-190, 370, 22, GRAY)


def draw_paused(screen, cursor=0, has_save=True):
    ov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 150))
    screen.blit(ov, (0, 0))
    pw, ph = 360, 320
    px = SCREEN_WIDTH//2  - pw//2
    py = SCREEN_HEIGHT//2 - ph//2
    pygame.draw.rect(screen, (18, 18, 30), (px, py, pw, ph))
    pygame.draw.rect(screen, (100,80,160), (px, py, pw, ph), 2)
    draw_text(screen, "── PAUSED ──", px+pw//2-80, py+14, 24, YELLOW)
    opts = ["Resume", "Settings", "New Game", "Save & Quit", "Quit (no save)"]
    for i, opt in enumerate(opts):
        col = YELLOW if i == cursor else LIGHT_GRAY
        draw_text(screen, opt, px+pw//2-70, py+66+i*48, 20, col)
        if i == cursor:
            draw_text(screen, "►", px+pw//2-94, py+66+i*48, 20, YELLOW)
    draw_text(screen, "[↑/↓] navigate  [Enter] select  [ESC] resume",
              px+10, py+ph-22, 11, (100,100,130), False)


def draw_win(screen, score):
    screen.fill((5, 10, 5))
    draw_text(screen, "VICTORY!", SCREEN_WIDTH//2-110, 180, 60, GOLD)
    draw_text(screen, "The darkness is vanquished.", SCREEN_WIDTH//2-185, 270, 22, WHITE)
    draw_text(screen, f"Score: {score}", SCREEN_WIDTH//2-60, 318, 28, YELLOW)
    draw_text(screen, "Press ENTER to return to menu", SCREEN_WIDTH//2-190, 390, 22, GRAY)
