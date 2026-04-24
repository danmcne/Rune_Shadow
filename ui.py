"""
Rune & Shadow - UI
HUD, inventory overlay, message log, main menu, game-over screen.

v2 improvements:
  - Main menu: New Game / Load Game / Quit + difficulty selector
  - Pause menu: Resume / New Game / Save & Quit
  - Inventory: separate Equip vs Use actions, drop item (D key)
  - Cheat-code input display in pause/play
"""
import pygame
from constants import *
from items import ITEMS


# ─── Font cache ───────────────────────────────────────────────────────────────
_fonts = {}

def font(size: int) -> pygame.font.Font:
    if size not in _fonts:
        _fonts[size] = pygame.font.SysFont("monospace", size, bold=False)
    return _fonts[size]


def draw_text(surf, text, x, y, size=16, color=WHITE, shadow=True):
    f = font(size)
    if shadow:
        s = f.render(text, True, BLACK)
        surf.blit(s, (x+1, y+1))
    surf.blit(f.render(text, True, color), (x, y))


def draw_bar(surf, x, y, w, h, value, max_val, fg_col, bg_col=DARK_GRAY,
             label=""):
    pygame.draw.rect(surf, bg_col, (x, y, w, h))
    filled = int(w * max(0, value) / max(1, max_val))
    pygame.draw.rect(surf, fg_col, (x, y, filled, h))
    pygame.draw.rect(surf, WHITE, (x, y, w, h), 1)
    if label:
        draw_text(surf, label, x+4, y+1, size=13, shadow=False)


# ═══════════════════════════════════════════════════════════════════════════════
#  HUD (bottom strip)
# ═══════════════════════════════════════════════════════════════════════════════

class HUD:
    SLOT_SIZE = 44
    SLOT_PAD  = 4

    def __init__(self):
        self._surf = pygame.Surface((SCREEN_WIDTH, HUD_H))

    def draw(self, screen, player, current_map_name: str, messages: list,
             asset_mgr=None, difficulty: int = DIFFICULTY_NORMAL,
             cheat_display: str = ""):
        s = self._surf
        s.fill((20, 20, 28))

        if asset_mgr:
            hud_bg = asset_mgr.get_ui('hud_bg', SCREEN_WIDTH, HUD_H)
            if hud_bg:
                s.blit(hud_bg, (0, 0))

        pygame.draw.line(s, (80,80,100), (0,0), (SCREEN_WIDTH, 0), 2)

        # HP / Mana bars
        draw_bar(s, 8, 8, 160, 18, player.hp, player.max_hp,
                 RED, label=f"HP {player.hp}/{player.max_hp}")
        draw_bar(s, 8, 32, 160, 18, player.mana, player.max_mana,
                 BLUE, label=f"MP {player.mana}/{player.max_mana}")

        draw_text(s, f"Gold: {player.inventory.gold}", 8, 56, 14, GOLD)

        # Swimming indicator
        if player.is_swimming:
            draw_text(s, "~SWIMMING~", 8, HUD_H-18, 12, CYAN)

        # Difficulty badge
        diff_col = [GREEN, WHITE, RED][difficulty]
        draw_text(s, DIFFICULTY_LABELS[difficulty], SCREEN_WIDTH-80, 6, 12, diff_col)

        draw_text(s, current_map_name, SCREEN_WIDTH//2, 6, 15, LIGHT_GRAY)

        # Cheat code display
        if cheat_display:
            draw_text(s, f"CHEAT: {cheat_display}", SCREEN_WIDTH//2-60, HUD_H-18,
                      13, (200,150,255))

        # Hotbar
        hb_x = 200
        hb_y = 8
        for i in range(HOTBAR_SLOTS):
            iid      = player.hotbar[i]
            sx       = hb_x + i * (self.SLOT_SIZE + self.SLOT_PAD)
            selected = (i == player.equipped)
            col_border = YELLOW if selected else (60, 60, 80)

            slot_bg = None
            if asset_mgr:
                slot_bg = asset_mgr.get_ui(
                    'hotbar_sel' if selected else 'hotbar_slot',
                    self.SLOT_SIZE, self.SLOT_SIZE)
            if slot_bg:
                s.blit(slot_bg, (sx, hb_y))
            else:
                pygame.draw.rect(s, (30, 30, 45),
                                 (sx, hb_y, self.SLOT_SIZE, self.SLOT_SIZE))
                pygame.draw.rect(s, col_border,
                                 (sx, hb_y, self.SLOT_SIZE, self.SLOT_SIZE), 2)

            if iid and iid in ITEMS:
                it  = ITEMS[iid]
                isz = self.SLOT_SIZE - 12
                icon = asset_mgr.get_item_icon(iid) if asset_mgr else None
                if icon:
                    scaled = pygame.transform.scale(icon, (isz, isz))
                    s.blit(scaled, (sx+6, hb_y+6))
                else:
                    pygame.draw.rect(s, it.color, (sx+6, hb_y+6, isz, isz))
                cnt = player.inventory.count(iid)
                if it.stackable and cnt > 0:
                    draw_text(s, str(cnt), sx+self.SLOT_SIZE-16,
                              hb_y+self.SLOT_SIZE-16, 12, WHITE, shadow=False)

            draw_text(s, str(i+1), sx+2, hb_y+2, 11, GRAY, shadow=False)

        # Messages (right side)
        msg_x = SCREEN_WIDTH - 310
        for mi, (msg, col) in enumerate(messages[-4:]):
            draw_text(s, msg, msg_x, 6 + mi * 18, 13, col)

        ctrl = "[SPACE]=Attack  [E]=Interact  [I]=Inv  [Q/F]=Cycle  [ESC]=Pause"
        draw_text(s, ctrl, SCREEN_WIDTH//2 - 255, HUD_H-18, 12, (120,120,140),
                  shadow=False)

        screen.blit(s, (0, VIEWPORT_H))


# ═══════════════════════════════════════════════════════════════════════════════
#  Inventory Screen
# ═══════════════════════════════════════════════════════════════════════════════

class InventoryScreen:
    COLS    = 6
    ROWS    = 8
    SZ      = 52
    PAD     = 6
    PANEL_W = COLS * (SZ + PAD) + PAD + 210
    PANEL_H = ROWS * (SZ + PAD) + PAD + 80

    def __init__(self):
        self.cursor     = 0
        self.hotbar_sel = None

    def handle_key(self, event, player, messages) -> bool:
        """Return True to close inventory."""
        inv   = player.inventory
        slots = list(inv.items())
        n     = len(slots)

        if event.key == pygame.K_ESCAPE or event.key == pygame.K_i:
            return True

        if event.key == pygame.K_UP:
            self.cursor = (self.cursor - self.COLS) % max(1, n)
        elif event.key == pygame.K_DOWN:
            self.cursor = (self.cursor + self.COLS) % max(1, n)
        elif event.key == pygame.K_LEFT:
            self.cursor = (self.cursor - 1) % max(1, n)
        elif event.key == pygame.K_RIGHT:
            self.cursor = (self.cursor + 1) % max(1, n)

        elif event.key == pygame.K_RETURN:
            # ENTER = Use consumable, or Equip weapon/tool/magic/ranged/light
            if 0 <= self.cursor < n:
                item, cnt = slots[self.cursor]
                if item.itype == IT_CONSUMABLE:
                    player.use_item(item.iid, messages)
                else:
                    # Equip to first empty hotbar slot, or replace current
                    target = None
                    for si in range(HOTBAR_SLOTS):
                        if player.hotbar[si] is None:
                            target = si; break
                    if target is None:
                        target = player.equipped
                    player.hotbar[target] = item.iid
                    messages.append((f"Equipped {item.name} → slot {target+1}.", YELLOW))

        elif event.key == pygame.K_SPACE:
            # SPACE = Use consumable only (explicit use vs equip split)
            if 0 <= self.cursor < n:
                item, cnt = slots[self.cursor]
                if item.itype == IT_CONSUMABLE:
                    used = player.use_item(item.iid, messages)
                    if not used:
                        messages.append(("Can't use that right now.", GRAY))
                else:
                    messages.append(("Press Enter to equip, D to drop.", GRAY))

        elif event.key == pygame.K_e:
            # E = Equip to hotbar (explicit equip for non-consumables)
            if 0 <= self.cursor < n:
                item, cnt = slots[self.cursor]
                if item.itype not in (IT_CONSUMABLE, IT_CURRENCY, IT_INGREDIENT):
                    target = None
                    for si in range(HOTBAR_SLOTS):
                        if player.hotbar[si] is None:
                            target = si; break
                    if target is None:
                        target = player.equipped
                    player.hotbar[target] = item.iid
                    messages.append((f"Equipped {item.name} → slot {target+1}.", YELLOW))
                else:
                    messages.append(("Use Enter/Space to use this item.", GRAY))

        elif event.key == pygame.K_d:
            # D = Drop one item to ground (game handles spawning GroundItem)
            if 0 <= self.cursor < n:
                item, cnt = slots[self.cursor]
                if item.itype == IT_CURRENCY:
                    messages.append(("Currency drops automatically.", GRAY))
                else:
                    # Signal via special message tag
                    messages.append(("__DROP__:" + item.iid, WHITE))
                    # Remove from hotbar if equipped
                    for si in range(HOTBAR_SLOTS):
                        if player.hotbar[si] == item.iid and player.inventory.count(item.iid) <= 1:
                            player.hotbar[si] = None
                    inv.remove(item.iid, 1)
                    messages.append((f"Dropped {item.name}.", ORANGE))
                    self.cursor = min(self.cursor, max(0, len(list(inv.items()))-1))

        elif pygame.K_1 <= event.key <= pygame.K_8:
            slot = event.key - pygame.K_1
            if 0 <= self.cursor < n:
                item, _ = slots[self.cursor]
                player.hotbar[slot] = item.iid
                messages.append((f"{item.name} → hotbar {slot+1}", YELLOW))

        return False

    def draw(self, screen, player, asset_mgr=None):
        inv   = player.inventory
        slots = list(inv.items())

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0,0,0,160))
        screen.blit(overlay, (0,0))

        px = (SCREEN_WIDTH  - self.PANEL_W) // 2
        py = (SCREEN_HEIGHT - self.PANEL_H) // 2

        pygame.draw.rect(screen, (20,20,35), (px, py, self.PANEL_W, self.PANEL_H))
        pygame.draw.rect(screen, (80,80,120),(px, py, self.PANEL_W, self.PANEL_H), 2)

        draw_text(screen, "─── INVENTORY ───", px+8, py+8, 20, YELLOW)
        draw_text(screen, f"Gold: {inv.gold}", px+8, py+32, 16, GOLD)

        # Grid
        for i, (item, count) in enumerate(slots):
            col_ = i % self.COLS
            row_ = i // self.COLS
            sx   = px + self.PAD + col_ * (self.SZ + self.PAD)
            sy   = py + 56 + row_ * (self.SZ + self.PAD)
            bg   = (40,40,60) if i != self.cursor else (80,80,150)
            pygame.draw.rect(screen, bg, (sx, sy, self.SZ, self.SZ))
            pygame.draw.rect(screen,
                             YELLOW if i == self.cursor else (60,60,90),
                             (sx, sy, self.SZ, self.SZ), 2)
            isz  = self.SZ - 16
            icon = asset_mgr.get_item_icon(item.iid) if asset_mgr else None
            if icon:
                scaled = pygame.transform.scale(icon, (isz, isz))
                screen.blit(scaled, (sx+8, sy+8))
            else:
                pygame.draw.rect(screen, item.color, (sx+8, sy+8, isz, isz))
            if item.stackable and count > 1:
                draw_text(screen, str(count), sx+self.SZ-20, sy+self.SZ-18,
                          13, WHITE, shadow=False)
            # Mark if equipped in hotbar
            if item.iid in player.hotbar:
                pygame.draw.rect(screen, GOLD, (sx, sy, self.SZ, self.SZ), 2)
                draw_text(screen, "E", sx+2, sy+2, 10, GOLD, shadow=False)

        # Info panel for selected item
        if 0 <= self.cursor < len(slots):
            item, count = slots[self.cursor]
            ix = px + self.COLS * (self.SZ + self.PAD) + 10
            iy = py + 56
            draw_text(screen, item.name,        ix, iy,     18, WHITE)
            draw_text(screen, f"Type: {item.itype}", ix, iy+24, 14, LIGHT_GRAY)
            if item.damage:
                draw_text(screen, f"Damage: {item.damage}", ix, iy+44, 14, RED)
            if item.hp_restore:
                draw_text(screen, f"Heals: +{item.hp_restore} HP", ix, iy+44, 14, GREEN)
            if item.mp_restore:
                draw_text(screen, f"Mana: +{item.mp_restore} MP",  ix, iy+64, 14, BLUE)
            if item.mana_cost:
                draw_text(screen, f"Cost: {item.mana_cost} MP", ix, iy+64, 14, BLUE)
            if item.defense:
                draw_text(screen, f"Defense: +{item.defense}", ix, iy+64, 14, CYAN)
            if item.light_radius:
                draw_text(screen, f"Light: {item.light_radius} tiles",
                          ix, iy+84, 14, YELLOW)
            if count > 1:
                draw_text(screen, f"x{count}", ix, iy+104, 14, LIGHT_GRAY)
            desc = item.description
            line_w = 22
            for li, start in enumerate(range(0, min(len(desc), 110), line_w)):
                draw_text(screen, desc[start:start+line_w],
                          ix, iy+124+li*18, 13, GRAY)

            # Action hints depend on item type
            hint_y = iy + 210
            if item.itype == IT_CONSUMABLE:
                draw_text(screen, "[Enter/Space]=Use", ix, hint_y, 13, GREEN)
            else:
                draw_text(screen, "[Enter/E]=Equip", ix, hint_y, 13, CYAN)
            draw_text(screen, "[D]=Drop",          ix, hint_y+18, 13, ORANGE)

        # Controls footer
        draw_text(screen,
                  "[Arrows]=Navigate  [Enter]=Use/Equip  [E]=Equip  [D]=Drop  [1-8]=Hotbar  [I/ESC]=Close",
                  px+4, py+self.PANEL_H-26, 12, (100,100,130), shadow=False)


# ═══════════════════════════════════════════════════════════════════════════════
#  Main Menu
# ═══════════════════════════════════════════════════════════════════════════════

def draw_main_menu(screen, seed_str: str, cursor: int,
                   difficulty: int = DIFFICULTY_NORMAL,
                   has_save: bool = False):
    screen.fill((10, 10, 20))

    draw_text(screen, "RUNE  &  SHADOW", SCREEN_WIDTH//2-180, 100, 52, GOLD)
    draw_text(screen, "A  Roguelike  Adventure", SCREEN_WIDTH//2-140, 162, 20, LIGHT_GRAY)

    options = ["New Game"]
    if has_save:
        options.append("Load Save")
    options.append("Quit")

    for i, opt in enumerate(options):
        col = YELLOW if i == cursor else LIGHT_GRAY
        draw_text(screen, opt, SCREEN_WIDTH//2-60, 250+i*52, 28, col)
        if i == cursor:
            draw_text(screen, "►", SCREEN_WIDTH//2-92, 250+i*52, 28, YELLOW)

    y_off = 250 + len(options)*52 + 10

    # Difficulty selector
    draw_text(screen, "Difficulty:", SCREEN_WIDTH//2-100, y_off, 18, LIGHT_GRAY)
    for di, dlabel in enumerate(DIFFICULTY_LABELS):
        col = [GREEN, WHITE, RED][di]
        if di == difficulty:
            pygame.draw.rect(screen, col,
                             (SCREEN_WIDTH//2 - 90 + di*80, y_off+26, 72, 26))
            draw_text(screen, dlabel, SCREEN_WIDTH//2 - 84 + di*80,
                      y_off+28, 15, BLACK, shadow=False)
        else:
            pygame.draw.rect(screen, (40,40,50),
                             (SCREEN_WIDTH//2 - 90 + di*80, y_off+26, 72, 26))
            draw_text(screen, dlabel, SCREEN_WIDTH//2 - 84 + di*80,
                      y_off+28, 15, col, shadow=False)
    draw_text(screen, "[←/→] change difficulty", SCREEN_WIDTH//2 - 100,
              y_off+58, 13, GRAY)

    # Seed entry
    draw_text(screen, f"World Seed: {seed_str}_", SCREEN_WIDTH//2-100, y_off+90, 18, CYAN)
    draw_text(screen, "(Type numbers to change seed)", SCREEN_WIDTH//2-160, y_off+114, 13, GRAY)

    draw_text(screen, "WASD/Arrows: Move   Space: Attack   Mouse: Aim   E: Interact",
              SCREEN_WIDTH//2-245, 680, 14, (100,100,140))
    draw_text(screen, "I: Inventory   Q/F: Cycle Weapon   ESC: Pause",
              SCREEN_WIDTH//2-195, 700, 14, (100,100,140))
    draw_text(screen, "Cheat codes: GODMODE  MAXHP  MAXMANA  GIVEALL  NOCLIP  RESPAWN",
              SCREEN_WIDTH//2-290, 720, 12, (80,80,100))


def draw_game_over(screen, score: int):
    screen.fill((10, 5, 5))
    draw_text(screen, "YOU  DIED", SCREEN_WIDTH//2-130, 200, 60, DARK_RED)
    draw_text(screen, f"Score: {score}", SCREEN_WIDTH//2-60, 300, 28, WHITE)
    draw_text(screen, "Press ENTER to return to menu", SCREEN_WIDTH//2-190, 380, 22, GRAY)


def draw_paused(screen, cursor: int = 0, has_save: bool = True):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0,0,0,150))
    screen.blit(overlay, (0,0))

    pw, ph = 340, 280
    px = SCREEN_WIDTH//2  - pw//2
    py = SCREEN_HEIGHT//2 - ph//2
    pygame.draw.rect(screen, (18,18,30), (px, py, pw, ph))
    pygame.draw.rect(screen, (100,80,160),(px, py, pw, ph), 2)

    draw_text(screen, "── PAUSED ──", px+pw//2-80, py+14, 26, YELLOW)

    options = ["Resume", "New Game", "Save & Quit", "Quit (no save)"]
    for i, opt in enumerate(options):
        col = YELLOW if i == cursor else LIGHT_GRAY
        draw_text(screen, opt, px+pw//2-70, py+70+i*50, 22, col)
        if i == cursor:
            draw_text(screen, "►", px+pw//2-96, py+70+i*50, 22, YELLOW)

    draw_text(screen, "[↑/↓] navigate  [Enter] select  [ESC] resume",
              px+12, py+ph-24, 12, (100,100,130), shadow=False)


def draw_win(screen, score: int):
    screen.fill((5, 10, 5))
    draw_text(screen, "VICTORY!", SCREEN_WIDTH//2-110, 180, 60, GOLD)
    draw_text(screen, "You have conquered the darkness.", SCREEN_WIDTH//2-200, 270, 22, WHITE)
    draw_text(screen, f"Score: {score}", SCREEN_WIDTH//2-60, 320, 28, YELLOW)
    draw_text(screen, "Press ENTER to return to menu", SCREEN_WIDTH//2-190, 400, 22, GRAY)
