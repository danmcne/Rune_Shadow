# Rune & Shadow  v2

A top-down roguelike adventure in Python + Pygame.

## Requirements

```
pip install pygame
```

## Running

```
python main.py
```

## Controls

| Key / Input | Action |
|---|---|
| WASD / Arrow Keys | Move |
| Mouse position | Aim ranged / magic attacks |
| Left Click / SPACE | Attack |
| E | Interact (dungeon, chest, shrine, pick up item) |
| Q / F / Scroll Wheel | Cycle hotbar |
| 1–8 | Select hotbar slot |
| I | Open / close inventory |
| ESC | Pause menu |

### Inventory Controls

| Key | Action |
|---|---|
| Arrow Keys | Navigate items |
| Enter or E | **Equip** to hotbar (weapons/tools/magic/light) |
| Space or Enter | **Use** consumables (potions etc.) |
| D | **Drop** one item to the ground |
| 1–8 | Assign item to hotbar slot |
| I / ESC | Close inventory |

## Cheat Codes

Type these letter codes at any time during play (no UI, just type):

| Code | Effect |
|---|---|
| `GODMODE` | Toggle invincibility + infinite mana |
| `MAXHP` | Restore HP to full |
| `MAXMANA` | Restore mana to full |
| `GIVEALL` | Add 5 of every item to inventory |
| `NOCLIP` | Toggle ghost mode (walk through walls) |
| `RESPAWN` | Respawn all enemies on current map |
| `LEVELUP` | +20 max HP and mana |
| `FULLCLEAR` | Instantly kill all enemies on current map |

## What's New in v2

### Gameplay
1. **Pause menu** — Resume / New Game / Save & Quit / Quit (no save)
2. **Save & Load** — JSON save file; autosaved at shrines
3. **Difficulty levels** — Easy (50% damage taken), Normal, Hard (150%)
4. **Drop items** — Press D in inventory to drop items to the ground
5. **Equip vs Use** — Enter/E equips weapons; Space uses consumables
6. **Cheat codes** — Full cheat suite for testing

### World Generation
7. **Safe player start** — Player spawns on a real grass tile with open neighbours (never surrounded by water)
8. **Forest infill** — Trees use 40% random infill instead of solid walls; forests are now passable
9. **Connected dungeons** — All dungeon generators guarantee full connectivity from entrance; unreachable areas are carved open or walled off; enemy spawns are validated to reachable tiles only
10. **Chest loot** — Chests now drop tiered loot (common + uncommon + rare chance) with items scattered around the chest

### Combat & Enemies
11. **Swimming** — Player can enter T_WATER tiles at half speed; shown with blue tint
12. **Kelpie** — New water monster that lives in rivers and lakes; fires water bolts
13. **Variable mob speed** — Wolves (3.2) are faster than player (3.0); trolls (1.0) are slower
14. **Aggro types** — Sight aggro (wolf, goblin…), Attack aggro (slime, spider…), passive planned
15. **Flee behaviour** — Slimes flee at 20% HP; bats flee at 15%; trolls barely flee
16. **De-aggro** — Goblins and wolves give up the chase if you outrun them
17. **Fight to death** — Spiders, skeletons, ghosts, kelpies never stop
18. **Ghosts** — Pass through walls; always partially visible in darkness; glow faintly
19. **Dark dungeons** — Most enemies invisible below brightness threshold; luminous enemies (slime, ghost) always visible
20. **Mouse aim** — Ranged and magic attacks fire toward mouse cursor; autoaim snaps to nearest enemy within 150px
21. **Mob names** — All enemies display their name above their sprite

### Items & Respawn
22. **Mob respawn** — Overworld enemies respawn after ~5 minutes
23. **Item respawn** — Dropped/consumed overworld items respawn after ~2.5 min
24. **Item decay** — Dropped items (from kills, chests) disappear after ~2 minutes (flicker warning)

## File Structure

```
main.py                  — Entry point
game.py                  — Main loop, camera, save/load, cheats
entities.py              — Player, Enemy subclasses, Projectile
generation.py            — Overworld (Perlin) + 3 dungeon generators
game_map.py              — Tile grid, GroundItem, respawn queues
items.py                 — Item definitions, Inventory, drop tables
ui.py                    — HUD, menus, inventory screen
constants.py             — All constants, tile types, colors
asset_manager.py         — Sprite / placeholder art loading
animation.py             — Animator state machine
noise_gen.py             — Perlin noise for world gen
create_placeholder_assets.py  — Generates placeholder sprites if no assets folder
```
