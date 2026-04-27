# Rune & Shadow  v3

A top-down roguelike adventure in Python + Pygame.

## Requirements

```
pip install pygame
```

## Running

```
python main.py
```

---

## Controls

| Key / Input | Action |
|---|---|
| WASD / Arrow Keys | Move |
| Mouse position | Aim ranged/magic attacks |
| Left Click / SPACE | Attack |
| E | Interact (gate, dungeon, chest, shrine, pick up item) |
| TAB | Toggle aim mode (Mouse ↔ Auto) |
| Q / F / Scroll Wheel | Cycle hotbar |
| 1–8 | Select hotbar slot |
| X | Unequip current hotbar slot |
| I | Open/close inventory |
| ESC | Pause menu |

### Inventory Controls

| Key | Action |
|---|---|
| Arrow Keys | Navigate |
| Enter / E | **Equip** weapon/tool/magic to hotbar |
| Space / Enter | **Use** consumable (potion etc.) |
| U | **Unequip** item from hotbar |
| D | **Drop** one item to the ground |
| 1–8 | Assign item to hotbar slot |
| I / ESC | Close |

---

## World Structure

You start in the **Town** — a procedurally generated walled settlement with roads, buildings, a central shrine, and four gates:

| Gate | Leads to | Enemies |
|---|---|---|
| North gate | **The Frozen Wastes** (Tundra) | Yeti, Ice Wraith, Skeleton |
| South gate | **The Sunbaked Reaches** (Desert) | Scorpion, Mummy, Goblin |
| East gate | **The Verdant Wilds** (Forest) | Wolf, Goblin, Spider, Slime |
| West gate | **The Murk Hollows** (Swamp) | Swamp Toad, Will-o'-Wisp, Ghost |

Each biome has **2–3 dungeons** with **1–3 levels** each. Deeper dungeon levels are darker, have more enemies, and the boss only appears on the deepest level.

---

## Dungeons

| # | Name | Biome | Levels | Boss |
|---|---|---|---|---|
| 0 | The Verdant Labyrinth | East | 1 | Giant Spider |
| 1 | The Stone Warrens | East | 2 | Stone Troll |
| 2 | The Haunted Halls | East | 2 | Skeleton Lord |
| 3 | The Frozen Vaults | North | 2 | Elder Yeti |
| 4 | The Ice Queen's Lair | North | 3 | Ice Wraith |
| 5 | The Sunken Tombs | South | 2 | Mummy Lord |
| 6 | The Scorched Crypts | South | 3 | Giant Scorpion |
| 7 | The Murk Warrens | West | 2 | Stone Troll |
| 8 | The Bog of Shadows | West | 3 | Ghost |

- **[E] near dungeon entrance** to enter
- **[E] on stairs up** to ascend / exit
- **[E] on stairs down** to descend to next level
- **[E] on shrine** to heal fully and save

---

## Cheat Codes

Type these at any time during play (no UI prompt needed — just type):

| Code | Effect |
|---|---|
| `GODMODE` | Toggle invincibility + infinite mana |
| `MAXHP` | Restore HP to full |
| `MAXMANA` | Restore mana to full |
| `GIVEALL` | Add 5 of every item to inventory |
| `NOCLIP` | Toggle ghost mode (walk through walls) |
| `RESPAWN` | Respawn all enemies on current map |
| `LEVELUP` | +20 max HP and mana |
| `FULLCLEAR` | Kill all enemies on current map |

---

## What's New in v3

### Bug Fixes
1. **Drop no longer duplicates** — item is removed from inventory *before* the GroundItem is created
2. **Chest loot on walkable tiles** — drops scatter to nearest walkable tile; fallback goes directly to inventory
3. **Boss never respawns after load** — `boss_killed[(dun_id, level)]` is persisted in the save file
4. **Unequip** — press **U** in inventory or **X** in play to clear a hotbar slot
5. **Cave dungeons always connected** — generator now finds the *largest* component (not centre-adjacent), retries up to 3x for adequate size

### New Features
6. **Town start** — player begins in a procedural walled town with roads, buildings, and a central shrine
7. **Four biomes** — Forest (East), Tundra (North), Desert (South), Swamp (West); each with unique tiles, enemies, and dungeons
8. **Multi-level dungeons** — 9 dungeons total with 1–3 levels; stairs up/down; boss only on deepest level; ambient darkness increases per level
9. **Aim mode toggle** — TAB switches between Mouse aim and Auto-aim; indicator dot changes colour (yellow = mouse, cyan = auto)
10. **Swamp slow tiles** — T_SWAMP reduces player speed to 60%; shown with green tint
11. **6 new enemies** — Yeti, Ice Wraith, Scorpion, Mummy, Swamp Toad, Will-o'-Wisp
12. **Goblin drops axe** (8% chance); **Troll drops pickaxe** (25% chance)
13. **Boss guaranteed drops** — each boss type has a fixed loot table (e.g. Troll → pickaxe + gems; Giant Spider → lantern + frost spell)

---

## File Structure

```
main.py                   Entry point
game.py                   Main loop, multi-map world, save/load, cheats
entities.py               Player, 16 enemy types, Projectile
generation.py             TownGenerator, 4 BiomeGenerators, 3 DungeonGenerators
game_map.py               GameMap, GroundItem (lifetime + respawn)
items.py                  Item definitions, Inventory, drop/boss tables
ui.py                     HUD, Inventory screen, all menus
constants.py              Tiles, colours, biomes, dungeon registry
asset_manager.py          Sprite/placeholder art loading
animation.py              Animator state machine
noise_gen.py              Perlin noise for world generation
create_placeholder_assets.py  Generates placeholder art if /assets missing
```
