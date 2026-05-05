# Rune & Shadow  v9

A top-down roguelike inspired by **Runescape, Zelda, and Minecraft**.
The world is procedurally generated (deterministic by seed), curated through
gates and named dungeons, and extends outward with progressively harder content.
1–2 player co-op, rebindable controls, no permadeath.

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

### Player 1 (default)

| Key | Action |
|---|---|
| W A S D | Move |
| SPACE or Left-click | Attack / Smash chest |
| E | Interact / Use gate / Pick up |
| Q | Open own inventory |
| TAB | Toggle aim mode (Mouse ↔ Auto) |
| X | Unequip current hotbar slot |
| ` / F / Scroll | Cycle hotbar |
| 1–5 | Select hotbar slot (1P: 1–8 available) |
| ESC | Pause menu |

### Player 2 (default)

| Key | Action |
|---|---|
| I J K L | Move (Up / Left / Down / Right) |
| M | Attack / Smash chest |
| U | Interact / Use gate / Pick up |
| O | Open own inventory |
| ; | Unequip slot |
| 6 7 8 9 0 | Select hotbar slot 1–5 |

> All keys are fully rebindable in **Pause → Settings**.

**Why WASD vs IJKL?**  Each player occupies a distinct keyboard zone, which
eliminates the hardware key-rollover (ghosting) problem that prevents
simultaneous diagonal movement when both players share the same zone.

### Inventory

| Key | Action |
|---|---|
| Arrow Keys | Navigate |
| Enter / E | **Equip** to hotbar |
| Space | **Use** consumable |
| U | **Unequip** from hotbar |
| D | **Drop** item to ground |
| 1–8 | Assign to hotbar slot |
| Q / ESC | Close |

---

## World Structure

You start in the **Town** — a walled settlement with roads, buildings, a shrine,
wells, and four named gates.

### Biomes (first layer)

| Gate | Leads to | Enemies |
|---|---|---|
| North | **The Frozen Wastes** (Tundra) | Yeti, Ice Wraith, Skeleton, Bat |
| South | **The Sunbaked Reaches** (Desert) | Scorpion, Mummy, Goblin, Skeleton |
| East  | **The Verdant Wilds** (Forest) | Wolf, Goblin, Spider, Slime, Bat |
| West  | **The Murk Hollows** (Swamp) | Swamp Toad, Will-o'-Wisp, Ghost, Spider |

Each biome has a **far gate** leading to the haunted town layer.

### Haunted Towns (second layer)

| Biome Far Gate | Haunted Town | Castle Dungeon |
|---|---|---|
| Forest East | The Shadow Grove | The Dark Keep (5 lvls, **Dragon**) |
| Tundra North | The Frost Citadel | The Frost Citadel dungeon (5 lvls, **Frost Dragon**) |
| Desert South | The Sunken Fortress | The Sunken Temple (5 lvls, **Sand Dragon**) |
| Swamp West | The Murk Stronghold | The Murk Fortress (5 lvls, **Swamp Dragon**) |

Haunted towns use dim ambient lighting (partially dark) and are densely packed
using a **Voronoi neighbourhood** layout — far more cramped than the starting
town. Each haunted town has two gates: one returns to the biome, the far gate
enters the castle dungeon.

---

## Dungeons

| # | Name | Biome | Levels | Boss |
|---|---|---|---|---|
| 0 | The Verdant Labyrinth | East  | 1 | Giant Spider |
| 1 | The Stone Warrens     | East  | 2 | Stone Troll |
| 2 | The Haunted Halls     | East  | 2 | Skeleton Lord |
| 3 | The Frozen Vaults     | North | 2 | Elder Yeti |
| 4 | The Ice Queen's Lair  | North | 3 | Ice Wraith |
| 5 | The Sunken Tombs      | South | 2 | Mummy Lord |
| 6 | The Scorched Crypts   | South | 3 | Giant Scorpion |
| 7 | The Murk Warrens      | West  | 2 | Stone Troll |
| 8 | The Bog of Shadows    | West  | 3 | Ghost |
| 9 | The Dark Keep         | Shadow Grove   | 5 | **Dragon** |
| 10 | The Frost Citadel    | Frost Citadel  | 5 | **Frost Dragon** |
| 11 | The Sunken Temple    | Sunken Fortress| 5 | **Sand Dragon** |
| 12 | The Murk Fortress    | Murk Stronghold| 5 | **Swamp Dragon** |

Dragons are very large (3-tile wide), fire spread projectile attacks,
and have 400 HP. Killing one drops a **Dragon Blade**, **Dragon Scales**,
and a rare spell.

---

## Chests

- **[E] Interact**: Loot the chest normally. Leaves a visible **opened chest**
  sprite on the ground (walkable). Items scatter nearby.
- **[SPACE / ATTACK] Smash**: Destroy the chest violently — fewer items drop,
  no mimic check. The underlying floor tile is chosen by looking at adjacent
  ground types (so smashing a chest inside a building reveals building floor,
  not grass).
- **Mimics**: ~12% of chests are Mimics. Interacting triggers an ambush.
  Attacking/smashing bypasses the mimic check.
- Opened chests can also be smashed (but yield nothing).

---

## Two-Player Co-op

- Camera tracks the **midpoint** between players.
- Both players use **auto-aim** (no mouse in 2P).
- Each player gets **5 hotbar slots** in 2P mode.
- When one player dies they become a **ghost**: can move freely through walls
  but cannot attack or interact. A **body marker** is left at the death site.
- If the living player reaches a **shrine**, both players are fully healed and
  the ghost is **revived**.
- Game ends when both players are completely gone (no ghosts either).

---

## Rare Items

| Item | Type | Effect |
|---|---|---|
| Dragon Blade | Weapon | 45 damage, fast, drops from dragons |
| Shadow Staff  | Weapon | 22 damage, void energy |
| Thunder Orb   | Spell  | Area-blast: explodes and hits all nearby enemies |
| Void Bolt     | Spell  | Single-target 50 damage |
| Swift Boots   | Armour | +1.2 move speed while in hotbar |
| Iron Armour   | Armour | -8 damage taken while in hotbar |
| Elixir of Life| Consumable | Restore 80 HP + 50 MP |
| Berserker Draught | Consumable | 2× attack damage for 10 s (glows red) |
| Dragon Scale  | Ingredient | Rare crafting material |

---

## Cheat Codes (single-player only — type during play)

Just type the code word while playing — no need to press Enter.

| Code | Effect |
|---|---|
| **GODMODE** | Toggle God Mode (invincibility + infinite mana) |
| **MAXHP** | Restore HP to full |
| **MAXMANA** | Restore mana to full |
| **GIVEALL** | Give all items (5 of each) |
| **NOCLIP** | Toggle No-Clip (ghost movement) |
| **RESPAWN** | Respawn all enemies on current map |
| **LEVELUP** | Level up (+20 max HP and mana) |
| **FULLCLEAR** | Kill all enemies on current map |

Codes are case-insensitive and detected from a rolling character buffer,
so they work even while moving (WASD keys are filtered as movement, not letters).

---

## Design Philosophy

Rune & Shadow is a **roguelike-inspired open-world RPG**:

- **Procedurally generated** terrain (seeded, deterministic) — same seed always
  produces the same world.
- **Curated structure** — named gates, towns, and dungeons provide a sense of
  place and progression.
- **No permadeath** — death in 2P becomes ghosthood; shrines revive. Save at
  any shrine.
- **Achievements + win condition** (future) — kill all four Dragon bosses and
  rescue the imprisoned princes/princesses.
- **Infinite-feeling world** — each biome layer leads to another, content
  scaling with depth (more enemies, harder monsters, rarer drops).

---

## File Structure

```
main.py                     Entry point
game.py                     Main loop, 2P input, ghost mechanic, save/load, cheats
entities.py                 Player (ghost mode), 16 enemies + Mimic + Dragon
generation.py               Town, HauntedTown (Voronoi), 4 Biomes, 3 Dungeon styles
game_map.py                 GameMap, GroundItem, mimic tracking
items.py                    Item definitions, rare items, drop tables, Inventory
ui.py                       HUD (1P/2P), Inventory, Settings, menus
constants.py                Tiles, colours, biomes, dungeon registry, map graph
asset_manager.py            Sprite loading
animation.py                Animator state machine
noise_gen.py                Perlin noise
create_placeholder_assets.py Generates placeholder art if /assets missing
```

## v9 Changes from v8

1. **New control scheme** — P1 uses WASD+Q(inv)+Space+E; P2 uses IJKL+M+U+O.
   Each player occupies a separate keyboard zone to eliminate hardware
   key-ghosting/rollover that caused diagonal movement to drop when both
   players were on the same key area (numpad).  Fully rebindable.
2. **Independent axis movement** — dx/dy accumulation never uses `elif` chains,
   so all four directions register independently.  Diagonal normalization
   (×0.7071) was already present and is retained.
3. **Event-based key tracker** — `KeyTracker` (KEYDOWN/KEYUP events rather than
   `get_pressed()`) bypasses hardware rollover limits on all axes simultaneously.
4. **Typed cheat codes** — F-key cheats replaced with type-in codes
   (GODMODE, MAXHP, MAXMANA, GIVEALL, NOCLIP, RESPAWN, LEVELUP, FULLCLEAR).
   OS function-key capture is no longer an issue.
5. **Castle gate "no route" fix** — haunted-town castle gates now correctly
   enter the castle dungeon instead of showing "No route."  Root cause: the
   GATE_DESTINATIONS guard ran before the castle-gate special-case check.
6. **5-slot hotbar in 2P mode** — each player uses 5 slots in multiplayer
   (P1: keys 1–5, P2: keys 6–0).  1P retains all 8 slots.
7. **No godmode music** — toggling god mode does not change or trigger music.


A top-down roguelike inspired by **Runescape, Zelda, and Minecraft**.
The world is procedurally generated (deterministic by seed), curated through
gates and named dungeons, and extends outward with progressively harder content.
1–2 player co-op, rebindable controls, no permadeath.

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

### Player 1 (default)

| Key | Action |
|---|---|
| W A S D | Move |
| SPACE or Left-click | Attack / Smash chest |
| E | Interact / Use gate / Pick up |
| I | Open own inventory |
| TAB | Toggle aim mode (Mouse ↔ Auto) |
| X | Unequip current hotbar slot |
| Q / F / Scroll | Cycle hotbar |
| 1–8 | Select hotbar slot |
| ESC | Pause menu |

### Player 2 (default, requires numpad)

| Key | Action |
|---|---|
| KP 8 4 5 6 | Move |
| KP 0 | Attack / Smash chest |
| KP Enter | Interact |
| KP ÷ | Open own inventory |
| KP . | Unequip slot |
| KP 7 / KP 9 | Cycle hotbar |
| KP 1–3 | Select hotbar slot |

> All keys are fully rebindable in **Pause → Settings**.

### Inventory

| Key | Action |
|---|---|
| Arrow Keys | Navigate |
| Enter / E | **Equip** to hotbar |
| Space | **Use** consumable |
| U | **Unequip** from hotbar |
| D | **Drop** item to ground |
| 1–8 | Assign to hotbar slot |
| I / ESC | Close |

---

## World Structure

You start in the **Town** — a walled settlement with roads, buildings, a shrine,
wells, and four named gates.

### Biomes (first layer)

| Gate | Leads to | Enemies |
|---|---|---|
| North | **The Frozen Wastes** (Tundra) | Yeti, Ice Wraith, Skeleton, Bat |
| South | **The Sunbaked Reaches** (Desert) | Scorpion, Mummy, Goblin, Skeleton |
| East  | **The Verdant Wilds** (Forest) | Wolf, Goblin, Spider, Slime, Bat |
| West  | **The Murk Hollows** (Swamp) | Swamp Toad, Will-o'-Wisp, Ghost, Spider |

Each biome has a **far gate** leading to the haunted town layer.

### Haunted Towns (second layer)

| Biome Far Gate | Haunted Town | Castle Dungeon |
|---|---|---|
| Forest East | The Shadow Grove | The Dark Keep (5 lvls, **Dragon**) |
| Tundra North | The Frost Citadel | The Frost Citadel dungeon (5 lvls, **Frost Dragon**) |
| Desert South | The Sunken Fortress | The Sunken Temple (5 lvls, **Sand Dragon**) |
| Swamp West | The Murk Stronghold | The Murk Fortress (5 lvls, **Swamp Dragon**) |

Haunted towns use dim ambient lighting (partially dark) and are densely packed
using a **Voronoi neighbourhood** layout — far more cramped than the starting
town. Each town has a single dungeon entrance to its castle.

---

## Dungeons

| # | Name | Biome | Levels | Boss |
|---|---|---|---|---|
| 0 | The Verdant Labyrinth | East  | 1 | Giant Spider |
| 1 | The Stone Warrens     | East  | 2 | Stone Troll |
| 2 | The Haunted Halls     | East  | 2 | Skeleton Lord |
| 3 | The Frozen Vaults     | North | 2 | Elder Yeti |
| 4 | The Ice Queen's Lair  | North | 3 | Ice Wraith |
| 5 | The Sunken Tombs      | South | 2 | Mummy Lord |
| 6 | The Scorched Crypts   | South | 3 | Giant Scorpion |
| 7 | The Murk Warrens      | West  | 2 | Stone Troll |
| 8 | The Bog of Shadows    | West  | 3 | Ghost |
| 9 | The Dark Keep         | Shadow Grove   | 5 | **Dragon** |
| 10 | The Frost Citadel    | Frost Citadel  | 5 | **Frost Dragon** |
| 11 | The Sunken Temple    | Sunken Fortress| 5 | **Sand Dragon** |
| 12 | The Murk Fortress    | Murk Stronghold| 5 | **Swamp Dragon** |

Dragons are very large (3-tile wide), fire spread projectile attacks,
and have 400 HP. Killing one drops a **Dragon Blade**, **Dragon Scales**,
and a rare spell.

---

## Chests

- **[E] Interact**: Loot the chest normally. Leaves a visible **opened chest**
  sprite on the ground (walkable). Items scatter nearby.
- **[SPACE / ATTACK] Smash**: Destroy the chest violently — fewer items drop,
  no mimic check. The underlying floor tile is chosen by looking at adjacent
  ground types (so smashing a chest inside a building reveals building floor,
  not grass).
- **Mimics**: ~12% of chests are Mimics. Interacting triggers an ambush.
  Attacking/smashing bypasses the mimic check.
- Opened chests can also be smashed (but yield nothing).

---

## Two-Player Co-op

- Camera tracks the **midpoint** between players.
- Both players use **auto-aim** (no mouse in 2P).
- When one player dies they become a **ghost**: can move freely through walls
  but cannot attack or interact. A **body marker** is left at the death site.
- If the living player reaches a **shrine**, both players are fully healed and
  the ghost is **revived**.
- Game ends when both players are completely gone (no ghosts either).

---

## Rare Items

| Item | Type | Effect |
|---|---|---|
| Dragon Blade | Weapon | 45 damage, fast, drops from dragons |
| Shadow Staff  | Weapon | 22 damage, void energy |
| Thunder Orb   | Spell  | Area-blast: explodes and hits all nearby enemies |
| Void Bolt     | Spell  | Single-target 50 damage |
| Swift Boots   | Armour | +1.2 move speed while in hotbar |
| Iron Armour   | Armour | -8 damage taken while in hotbar |
| Elixir of Life| Consumable | Restore 80 HP + 50 MP |
| Berserker Draught | Consumable | 2× attack damage for 10 s (glows red) |
| Dragon Scale  | Ingredient | Rare crafting material |

---

## Cheat Codes (single-player only — press F-key during play)

| Key | Effect |
|---|---|
| **F1** | Toggle God Mode (invincibility + infinite mana) |
| **F2** | Restore HP to full |
| **F3** | Restore mana to full |
| **F4** | Give all items (5 of each) |
| **F5** | Toggle No-Clip (ghost movement) |
| **F6** | Respawn all enemies on current map |
| **F7** | Level up (+20 max HP and mana) |
| **F8** | Full clear (kill all enemies on current map) |

Cheats are F-key based (not typed codes) to avoid conflicts with movement keys.

---

## Design Philosophy

Rune & Shadow is a **roguelike-inspired open-world RPG**:

- **Procedurally generated** terrain (seeded, deterministic) — same seed always
  produces the same world.
- **Curated structure** — named gates, towns, and dungeons provide a sense of
  place and progression.
- **No permadeath** — death in 2P becomes ghosthood; shrines revive. Save at
  any shrine.
- **Achievements + win condition** (future) — kill all four Dragon bosses and
  rescue the imprisoned princes/princesses.
- **Infinite-feeling world** — each biome layer leads to another, content
  scaling with depth (more enemies, harder monsters, rarer drops).

---

## File Structure

```
main.py                     Entry point
game.py                     Main loop, 2P input, ghost mechanic, save/load, cheats
entities.py                 Player (ghost mode), 16 enemies + Mimic + Dragon
generation.py               Town, HauntedTown (Voronoi), 4 Biomes, 3 Dungeon styles
game_map.py                 GameMap, GroundItem, mimic tracking
items.py                    Item definitions, rare items, drop tables, Inventory
ui.py                       HUD (1P/2P), Inventory, Settings, menus
constants.py                Tiles, colours, biomes, dungeon registry, map graph
asset_manager.py            Sprite loading
animation.py                Animator state machine
noise_gen.py                Perlin noise
create_placeholder_assets.py Generates placeholder art if /assets missing
```

## v5 Changes from v4

1. **Seeded biome generation** — biome entities now use per-map seeded RNGs; the same seed always produces the same world regardless of map-load order.
2. **Ghost player mechanic** — dead 2P player becomes a ghost (transparent, moves freely, cannot attack); leaves body marker; revived at shrines.
3. **P2 safe spawn** — Player 2 spawns directly on a gate tile, guaranteed walkable.
4. **Improved chests** — interact to loot (leaves opened sprite), attack to smash (fewer items, correct floor under chest).
5. **Mimic chests** — 12% of chests are Mimics; interacting spawns an enemy ambush.
6. **Haunted towns** — four new map areas (one per biome), using Voronoi neighbourhood layout, dim lighting, tougher enemies.
7. **Castle dungeons** — four 5-level castles accessed from haunted towns, each with a Dragon boss.
8. **Dragon enemies** — 3-tile wide boss, spread fire-breath attack, 400 HP, guaranteed rare drops.
9. **Rare items** — Dragon Blade, Shadow Staff, Thunder Orb (AoE), Void Bolt, Swift Boots, Iron Armour, Elixir, Berserker Draught.
10. **Berserk buff** — Berserker Draught doubles melee damage for 10 s (player glows red).
11. **Biome far gates** — each biome now has a second gate on its far side leading to the haunted town layer.
