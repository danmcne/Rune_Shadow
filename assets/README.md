# Rune & Shadow — Asset Specification
### Guide for artists and developers

---

## Quick Setup

```bash
# Install pygame, then generate coloured-block placeholders
pip install pygame
python create_placeholder_assets.py

# Optional: regenerate cleanly
python create_placeholder_assets.py --clean
```

Placeholders are real PNG files — drop real art in the same paths to override.

---

## Folder Structure

```
assets/
├── tiles/          Tile ground textures          (32 × 32 px)
├── entities/       Character & mob sprites
│   ├── player/
│   ├── slime/
│   ├── bat/
│   ├── spider/
│   ├── goblin/
│   ├── skeleton/
│   ├── ghost/
│   ├── troll/
│   ├── wolf/
│   └── giant_spider/
├── items/          Inventory / hotbar icons      (32 × 32 px)
├── projectiles/    Bullets, arrows, spells       (12 × 12 px default)
├── fx/             Attack flashes, explosions    (32 × 32 px default)
└── ui/             HUD panels, slot borders, etc.
```

---

## Tile Sprites

**Path:** `assets/tiles/<name>.png`  
**Size:** 32 × 32 pixels  
**Format:** PNG (RGBA preferred for alpha edges)

| Tile ID constant | Filename        | Description          |
|-----------------|-----------------|----------------------|
| T_DEEP_WATER    | deep_water.png  | Dark deep ocean      |
| T_WATER         | water.png       | Shallow water        |
| T_SAND          | sand.png        | Beach / riverbank    |
| T_GRASS         | grass.png       | Open field           |
| T_FOREST        | forest.png      | Dense trees (solid)  |
| T_MOUNTAIN      | mountain.png    | Rocky mountain (solid)|
| T_ENTRANCE      | entrance.png    | Dungeon doorway      |
| T_FLOOR         | floor.png       | Stone dungeon floor  |
| T_WALL          | wall.png        | Stone dungeon wall   |
| T_DOOR          | door.png        | Opened door          |
| T_STAIRS_UP     | stairs_up.png   | Exit dungeon stairs  |
| T_STAIRS_DOWN   | stairs_down.png | Go deeper stairs     |
| T_CHEST         | chest.png       | Treasure chest       |
| T_PATH          | path.png        | Dirt road            |
| T_CAVE_FLOOR    | cave_floor.png  | Dark cave floor      |
| T_CAVE_WALL     | cave_wall.png   | Cave rock wall       |
| T_VINE_WALL     | vine_wall.png   | Overgrown wall       |
| T_SHRINE        | shrine.png      | Healing shrine       |

**Tips:**
- Tiles tile seamlessly — ensure edges match.
- Dungeon tiles should work overlaid with a dark alpha layer (the lighting system draws a black vignette on top).
- Include a subtle highlight pixel at top-left and shadow at bottom-right for depth.

---

## Entity Sprites

**Path:** `assets/entities/<entity_type>/<state>_<dir>_<frame>.png`  
**Size:** 26 × 26 pixels (scaled automatically if different)  
**Format:** PNG with transparency (RGBA)

### Entity Types

| Folder         | In-game name    | Notes                      |
|----------------|-----------------|---------------------------|
| player         | The Hero        | 4-directional, all states  |
| slime          | Slime           | Simple blob                |
| bat            | Bat             | Small, erratic             |
| spider         | Spider          | 8-legged                   |
| goblin         | Goblin          | Humanoid, green-ish        |
| skeleton       | Skeleton        | Undead warrior             |
| ghost          | Ghost           | Semi-transparent (code applies alpha automatically for now) |
| troll          | Troll           | Large and slow             |
| wolf           | Wolf            | Fast quadruped             |
| giant_spider   | Giant Spider    | Boss — drawn at 2× size    |

### Animation States

| State   | Frames | Ticks/frame | Loops? | Notes                       |
|---------|--------|-------------|--------|-----------------------------|
| idle    | 4      | 14          | yes    | Breathing / blinking        |
| walk    | 4      | 7           | yes    | Movement cycle              |
| attack  | 3      | 5           | no     | Snaps back to idle after    |
| hurt    | 2      | 4           | no     | Red flash                   |
| dead    | 4      | 8           | no     | Freezes on last frame       |

### Directions

| Tag | Meaning       | Arrow key |
|-----|---------------|-----------|
| n   | North (up)    | ↑         |
| s   | South (down)  | ↓         |
| e   | East  (right) | →         |
| w   | West  (left)  | ←         |

### Filename Examples

```
assets/entities/player/idle_s_0.png   ← player facing south, idle frame 0
assets/entities/player/walk_e_2.png   ← player walking east, frame 2
assets/entities/player/attack_n_1.png ← player attacking north, frame 1
assets/entities/goblin/hurt_w_0.png   ← goblin hurt, facing west
assets/entities/wolf/dead_s_3.png     ← wolf death last frame
```

### Total Files per Entity Type

  5 states × 4 directions × 2–4 frames = **~ 64–80 PNG files**

### Fallback Chain

If a specific frame is missing, the engine tries in order:
1. Exact: `walk_e_2.png`
2. First frame: `walk_e_0.png`
3. Idle: `idle_s_0.png`
4. Procedural coloured block

So you can ship a minimal set (just `idle_s_0.png` per entity) and the game stays playable while art is in progress.

### Minimum Viable Sprite Set (MVP)

For each entity, you need only:
```
idle_s_0.png    (standing still, facing south)
walk_s_0.png    (one walk frame)
```
Everything else falls back automatically.

---

## Item Icons

**Path:** `assets/items/<item_id>.png`  
**Size:** 32 × 32 pixels  
**Format:** PNG, transparent background recommended

| Item ID      | Name              | Item ID      | Name            |
|-------------|-------------------|-------------|-----------------|
| knife       | Knife             | mushroom    | Red Mushroom    |
| staff       | Staff             | blue_flower | Blue Flower     |
| axe         | Wood Axe          | bread       | Hard Bread      |
| pickaxe     | Pickaxe           | herb        | Green Herb      |
| sword       | Sword             | potion      | Health Potion   |
| spear       | Spear             | mana_pot    | Mana Potion     |
| sling       | Sling             | meat        | Raw Meat        |
| bow         | Short Bow         | goo         | Slime Goo       |
| spell_fire  | Fireball Tome     | silk        | Spider Silk     |
| spell_frost | Frost Shard       | spider_eye  | Spider Eye      |
| spell_bolt  | Lightning Bolt    | bone        | Bone            |
| spell_basic | Arcane Bolt       | feather     | Feather         |
| stone       | Stone             | magic_dust  | Magic Dust      |
| arrow       | Arrow             | hide        | Thick Hide      |
| candle      | Candle            | mana_crys   | Mana Crystal    |
| lantern     | Lantern           | coin        | Coin            |
| torch       | Torch             | gem         | Small Gem       |
| rope        | Rope              | big_gem     | Large Gem       |
| boomerang   | Boomerang         | shield      | Shield          |

---

## Projectile Sprites

**Path:** `assets/projectiles/<kind>.png`  
**Size:** 12 × 12 pixels  
**Format:** PNG with transparency

| Filename      | Used by                    |
|--------------|----------------------------|
| stone.png    | Sling                      |
| arrow.png    | Short Bow                  |
| fireball.png | Fireball Tome              |
| frost.png    | Frost Shard Tome           |
| lightning.png| Lightning Bolt Tome        |
| arcane.png   | Staff / Arcane Bolt Tome   |
| bone.png     | Skeleton ranged attack     |
| web.png      | Spider ranged attack       |

**Tip:** Projectiles are drawn centred. For directional arrows, the code passes the velocity direction — you can hook into `Projectile.draw()` to rotate the sprite accordingly (not yet implemented but the hook is `proj.dx, proj.dy`).

---

## FX Sprites

**Path:** `assets/fx/<name>_<frame>.png`  
**Size:** 32 × 32 pixels (can vary — the engine does not auto-scale FX)

| Effect prefix  | Frames | Triggered by              |
|---------------|--------|---------------------------|
| attack_slash  | 3      | Melee weapon swing        |
| hit_spark     | 2      | Projectile impact         |
| fire_burst    | 4      | Fireball explosion        |
| frost_burst   | 3      | Frost impact              |
| magic_ring    | 4      | Arcane / lightning impact |

---

## UI Sprites

**Path:** `assets/ui/<name>.png`

| Filename       | Size              | Used for                    |
|---------------|-------------------|-----------------------------|
| hud_bg.png    | 1024 × 90         | Bottom HUD background strip |
| hotbar_slot.png | 44 × 44         | Inactive hotbar slot        |
| hotbar_sel.png  | 44 × 44         | Selected hotbar slot        |
| heart_full.png | 16 × 16          | *(future)* HP icon bar      |
| mana_full.png  | 16 × 16          | *(future)* MP icon bar      |

---

## Technical Notes

### Pixel Art Style Suggestions
- 32 × 32 base resolution scales well; the game runs at 1024 × 768.
- Use a limited palette per entity (4–8 colours) for a cohesive look.
- Keep outlines to 1 px; use a slightly darker shade of the main body colour.
- Tiles can have 2–3 variants (e.g. `grass_0.png`, `grass_1.png`) — 
  the asset manager will need a small extension to pick randomly per tile coordinate.

### Colour Reference (current procedural palette)
```
Player:       #508CFF     Slime:   #50C850    Bat:    #8C3CB4
Spider:       #784614     Goblin:  #B45028    Skeleton:#E6E6D2
Ghost:        #A0C8F0     Troll:   #508242    Wolf:   #A08264
Giant Spider: #A01E1E
```

### Adding New Entity Types
1. Add the entity class in `entities.py` with the correct `etype` string.
2. Create `assets/entities/<etype>/` with at least `idle_s_0.png`.
3. Add an entry to `ENTITY_TYPES` in `create_placeholder_assets.py`.
4. Add a drop table entry in `items.py → DROP_TABLES`.

### Adding New Items
1. Define the item in `items.py` using `_weapon()`, `_consumable()`, etc.
2. Add a `_reg()` call to put it in `ITEMS`.
3. Add an entry to `_ICON_SHAPES` in `create_placeholder_assets.py`.
4. Run `python create_placeholder_assets.py` to generate the placeholder icon.
5. Drop a real `<item_id>.png` into `assets/items/` when ready.
