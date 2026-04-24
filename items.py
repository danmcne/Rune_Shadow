"""
Rune & Shadow - Items & Inventory
Item definitions, inventory class, and drop-table logic.
"""
import random
from constants import *


# ─── Item Definition ──────────────────────────────────────────────────────────
class Item:
    def __init__(self, iid, name, itype, color,
                 value=0, stackable=False, description=""):
        self.iid         = iid          # unique string id
        self.name        = name
        self.itype       = itype        # IT_* constant
        self.color       = color
        self.value       = value        # gold value
        self.stackable   = stackable
        self.description = description
        # weapon / tool specific
        self.damage      = 0
        self.attack_range= 36           # pixels; melee reach
        self.cooldown    = 20           # frames between attacks
        self.tool_tag    = None         # 'axe'/'pickaxe' for tile destruction
        # ranged
        self.ammo_type   = None
        self.proj_speed  = 0
        self.proj_color  = WHITE
        # magic
        self.mana_cost   = 0
        self.spell_effect= None         # string tag for spell
        # consumable
        self.hp_restore  = 0
        self.mp_restore  = 0
        # light
        self.light_radius= 0            # tiles; 0 = no light
        # armor
        self.defense     = 0

    def clone(self):
        import copy
        return copy.copy(self)

    def __repr__(self):
        return f"<Item {self.iid}>"


def _weapon(iid, name, damage, attack_range, cooldown, color, value=10,
            tool_tag=None, desc=""):
    it = Item(iid, name, IT_WEAPON, color, value=value, description=desc)
    it.damage       = damage
    it.attack_range = attack_range
    it.cooldown     = cooldown
    it.tool_tag     = tool_tag
    return it


def _ranged(iid, name, damage, ammo_type, proj_speed, proj_color,
            cooldown, color, value=15, desc=""):
    it = Item(iid, name, IT_RANGED, color, value=value, description=desc)
    it.damage     = damage
    it.ammo_type  = ammo_type
    it.proj_speed = proj_speed
    it.proj_color = proj_color
    it.cooldown   = cooldown
    return it


def _magic(iid, name, damage, mana_cost, spell_effect, proj_speed,
           proj_color, cooldown, color, value=20, desc=""):
    it = Item(iid, name, IT_MAGIC, color, value=value, description=desc)
    it.damage      = damage
    it.mana_cost   = mana_cost
    it.spell_effect= spell_effect
    it.proj_speed  = proj_speed
    it.proj_color  = proj_color
    it.cooldown    = cooldown
    return it


def _consumable(iid, name, hp, mp, color, value=5, stack=True, desc=""):
    it = Item(iid, name, IT_CONSUMABLE, color, value=value,
              stackable=stack, description=desc)
    it.hp_restore = hp
    it.mp_restore = mp
    return it


def _ingredient(iid, name, color, value=3, desc=""):
    return Item(iid, name, IT_INGREDIENT, color, value=value,
                stackable=True, description=desc)


def _ammo(iid, name, color, value=1, desc=""):
    return Item(iid, name, IT_AMMO, color, value=value,
                stackable=True, description=desc)


def _light(iid, name, light_radius, color, value=8, desc=""):
    it = Item(iid, name, IT_LIGHT, color, value=value, description=desc)
    it.light_radius = light_radius
    return it


def _currency(iid, name, color, value=1):
    return Item(iid, name, IT_CURRENCY, color, value=value, stackable=True)


# ─── Master Item Registry ─────────────────────────────────────────────────────
ITEMS = {}

def _reg(it):
    ITEMS[it.iid] = it
    return it

# Weapons
KNIFE   = _reg(_weapon('knife',    "Knife",     8,  36, 18, LIGHT_GRAY,  5,
                        desc="A quick, short blade. Fast attacks."))
STAFF   = _reg(_weapon('staff',    "Staff",     5,  20, 25, (120,80,200),8,
                        desc="A carved staff. Channels magical energy."))
AXE     = _reg(_weapon('axe',      "Wood Axe",  12, 40, 28, BROWN,      20,
                        tool_tag='axe',
                        desc="Cuts trees. Solid melee weapon."))
PICKAXE = _reg(_weapon('pickaxe',  "Pickaxe",   10, 40, 30, GRAY,       18,
                        tool_tag='pickaxe',
                        desc="Breaks stone walls and mountain rock."))
SWORD   = _reg(_weapon('sword',    "Sword",     18, 48, 22, LIGHT_GRAY, 50,
                        desc="A trusty iron sword. Balanced and powerful."))
SPEAR   = _reg(_weapon('spear',    "Spear",     14, 60, 24, (200,200,180),35,
                        desc="Long reach. Hits two tiles ahead."))

# Ranged weapons
SLING   = _reg(_ranged('sling',   "Sling",      6, 'stone',  5, COL_STONE, 22,
                        BROWN, 5,
                        desc="Hurls stones at enemies. Needs stone ammo."))
BOW     = _reg(_ranged('bow',     "Short Bow",  12, 'arrow', 7, COL_ARROW, 20,
                        BROWN, 30,
                        desc="Fires arrows. More power than a sling."))

# Magic weapons / spell books
SPELL_FIRE = _reg(_magic('spell_fire', "Fireball Tome", 22, 20,
                          'fireball', 6, COL_FIRE, 30,
                          ORANGE, 40,
                          desc="Casts a ball of fire. Burns enemies."))
SPELL_FROST= _reg(_magic('spell_frost',"Frost Shard",   15, 15,
                          'frost',    5, (160,220,255), 28,
                          (140,200,255), 35,
                          desc="Fires a shard of ice that slows enemies."))
SPELL_BOLT = _reg(_magic('spell_bolt', "Lightning Bolt", 28, 25,
                          'lightning', 9, YELLOW, 35,
                          YELLOW, 60,
                          desc="Powerful bolt. High mana cost."))
# Starting magic (staff fires this)
SPELL_BASIC= _reg(_magic('spell_basic',"Arcane Bolt",   12, 10,
                          'arcane',   5, COL_MAGIC, 28,
                          CYAN, 15,
                          desc="Basic magical bolt from the staff."))

# Ammo
STONE  = _reg(_ammo('stone', "Stone",         COL_STONE, 1))
ARROW  = _reg(_ammo('arrow', "Arrow",         COL_ARROW, 2))

# Consumables
MUSHROOM = _reg(_consumable('mushroom', "Red Mushroom",  15, 0,  RED,    4, True,
                              desc="Restores a little health."))
BLUE_FLOWER=_reg(_consumable('blue_flower',"Blue Flower", 0,  20, (100,130,255), 5, True,
                              desc="Restores mana."))
BREAD    = _reg(_consumable('bread',   "Hard Bread",    10, 0,  (220,200,150),3,True,
                              desc="Stale but filling. Restores HP."))
HERB     = _reg(_consumable('herb',    "Green Herb",     8, 5,  GREEN,  3, True,
                              desc="Mild healing herb."))
POTION   = _reg(_consumable('potion',  "Health Potion", 40, 0,  RED,   15, True,
                              desc="Strong healing draught."))
MANA_POT = _reg(_consumable('mana_pot',"Mana Potion",    0, 35, BLUE,  15, True,
                              desc="Restores mana."))
MEAT     = _reg(_consumable('meat',    "Raw Meat",      20, 0, (220,100,80), 6, True,
                              desc="From a slain wolf. Restores health."))

# Ingredients (used for potions / future crafting)
GOO       = _reg(_ingredient('goo',    "Slime Goo",     COL_SLIME, 2,
                               desc="Sticky slime residue."))
SILK      = _reg(_ingredient('silk',   "Spider Silk",   WHITE,     4,
                               desc="Strong, light spider silk."))
SPIDER_EYE= _reg(_ingredient('spider_eye',"Spider Eye", RED,       6,
                               desc="Used in potions of detection."))
BONE      = _reg(_ingredient('bone',   "Bone",          COL_SKELETON, 2,
                               desc="Can be made into tools or arrows."))
FEATHER   = _reg(_ingredient('feather',"Feather",       WHITE,     2,
                               desc="Light feather. Used in arrow fletching."))
MAGIC_DUST= _reg(_ingredient('magic_dust',"Magic Dust", CYAN,      8,
                               desc="Rare dust from spectral creatures."))
HIDE      = _reg(_ingredient('hide',   "Thick Hide",    BROWN,     5,
                               desc="Tough animal hide. Used in armour."))
MANA_CRYS = _reg(_ingredient('mana_crys',"Mana Crystal",BLUE,     12,
                               desc="Crystallised mana. Valuable."))

# Lights
CANDLE  = _reg(_light('candle',  "Candle",   4, YELLOW, 5,
                       desc="Provides a small circle of light in darkness."))
LANTERN = _reg(_light('lantern', "Lantern",  7, ORANGE, 20,
                       desc="Casts a warm glow. Better than a candle."))
TORCH   = _reg(_light('torch',   "Torch",    5, ORANGE, 8,
                       desc="A burning torch. Good light source."))

# Currency
COIN    = _reg(_currency('coin',  "Coin",        GOLD, 1))
GEM     = _reg(_currency('gem',   "Small Gem",   CYAN, 10))
BIG_GEM = _reg(_currency('big_gem',"Large Gem",  (255,100,200), 30))

# Misc
ROPE       = _reg(Item('rope',  "Rope",        IT_TOOL,  BROWN, value=8,
                        description="Can be used to cross gaps or bind things."))
BOOMERANG  = _reg(_weapon('boomerang',"Boomerang",10,200,35,(200,160,80),25,
                           desc="Flies out and returns. Hits twice!"))
SHIELD     = _reg(Item('shield',"Shield",       IT_ARMOR, GRAY, value=30,
                        description="Reduces incoming damage by 5."))
_s = ITEMS['shield']; _s.defense = 5


# ─── Drop Table ───────────────────────────────────────────────────────────────
# Format: [(item_id, probability), ...]  probabilities need not sum to 1 (each rolled independently)
DROP_TABLES = {
    'slime':        [('goo', 0.60), ('mushroom', 0.30), ('herb', 0.15)],
    'bat':          [('feather', 0.25)],
    'spider':       [('silk', 0.60), ('spider_eye', 0.25), ('mushroom', 0.10)],
    'goblin':       [('coin', 0.80), ('coin', 0.50), ('herb', 0.20),
                     ('gem', 0.08), ('knife', 0.04)],
    'skeleton':     [('bone', 0.70), ('bone', 0.40), ('arrow', 0.40),
                     ('coin', 0.30)],
    'ghost':        [('magic_dust', 0.55), ('mana_crys', 0.25),
                     ('blue_flower', 0.15)],
    'troll':        [('coin', 0.70), ('coin', 0.50), ('big_gem', 0.15),
                     ('hide', 0.50), ('mushroom', 0.30)],
    'wolf':         [('hide', 0.80), ('meat', 0.65), ('feather', 0.10)],
    'giant_spider': [('spider_eye', 1.0), ('silk', 1.0), ('silk', 1.0),
                     ('gem', 0.80), ('big_gem', 0.50), ('lantern', 0.40)],
    'kelpie':       [('gem', 0.50), ('mana_crys', 0.40), ('herb', 0.30),
                     ('big_gem', 0.15)],
}

# Chest loot pools by quality tier
CHEST_LOOT_COMMON = ['potion','mana_pot','coin','coin','coin','gem',
                     'mushroom','arrow','stone','herb','silk','magic_dust',
                     'bread','feather','rope']
CHEST_LOOT_UNCOMMON = ['sword','axe','pickaxe','bow','spear','lantern',
                        'spell_fire','spell_frost','spell_bolt','shield',
                        'big_gem','mana_crys']
CHEST_LOOT_RARE = ['boomerang','sword','bow','spell_bolt','big_gem','lantern']


def roll_drops(enemy_type: str, rng: random.Random) -> list:
    """Return a list of Item instances dropped by an enemy."""
    drops = []
    table = DROP_TABLES.get(enemy_type, [])
    for iid, prob in table:
        if rng.random() < prob:
            drops.append(make_item(iid))
    return drops


def make_item(iid: str) -> Item:
    """Clone a fresh copy of the named item."""
    base = ITEMS.get(iid)
    if base is None:
        raise KeyError(f"Unknown item id: {iid!r}")
    return base.clone()


# ─── Inventory ────────────────────────────────────────────────────────────────
class Inventory:
    MAX_STACKS = 48   # total unique stacks

    def __init__(self):
        # Each slot: [Item, count]
        self._slots: list = []
        self.gold: int = 0

    # ── Queries ──────────────────────────────────────────────────────────────
    def count(self, iid: str) -> int:
        return sum(c for it, c in self._slots if it.iid == iid)

    def has(self, iid: str, n: int = 1) -> bool:
        return self.count(iid) >= n

    def items(self):
        """Iterator over (item, count) pairs."""
        return iter(self._slots)

    def __len__(self):
        return len(self._slots)

    # ── Mutations ────────────────────────────────────────────────────────────
    def add(self, item: Item, count: int = 1) -> bool:
        """Returns True if added successfully."""
        if item.stackable:
            for slot in self._slots:
                if slot[0].iid == item.iid:
                    slot[1] += count
                    return True
        if len(self._slots) >= self.MAX_STACKS:
            return False
        self._slots.append([item, count])
        return True

    def remove(self, iid: str, count: int = 1) -> bool:
        """Remove `count` of item. Returns False if not enough."""
        for i, (it, c) in enumerate(self._slots):
            if it.iid == iid:
                if c < count:
                    return False
                self._slots[i][1] -= count
                if self._slots[i][1] <= 0:
                    self._slots.pop(i)
                return True
        return False

    def slot_at(self, idx: int):
        """Return (item, count) at slot index, or None."""
        if 0 <= idx < len(self._slots):
            return self._slots[idx]
        return None

    def add_gold(self, amount: int):
        self.gold += amount

    def spend_gold(self, amount: int) -> bool:
        if self.gold < amount:
            return False
        self.gold -= amount
        return True
