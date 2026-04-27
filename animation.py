"""
Rune & Shadow - Animation System
====================================
Every living entity owns one Animator instance.

STATES
------
  idle    – standing still, breathing cycle
  walk    – moving in any direction
  attack  – melee / cast swing (non-looping, snaps back to idle)
  hurt    – recoil after taking damage (non-looping)
  dead    – death sequence (non-looping, freezes on last frame)

DIRECTIONS
----------
  n  (up)    s  (down)    e  (right)    w  (left)

SPRITE FILENAME CONVENTION
--------------------------
  assets/entities/<entity_type>/<state>_<dir>_<frame>.png
  e.g.  assets/entities/player/walk_e_0.png
        assets/entities/slime/idle_s_2.png

FALLBACK CHAIN (asset_manager resolves in order)
  1. Exact frame: walk_e_2.png
  2. First frame of same state+dir: walk_e_0.png
  3. Idle first frame: idle_s_0.png
  4. Any single placeholder: idle_s_0.png for any dir
  5. Procedural coloured rect (no file at all)
"""

from constants import DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT

# ─── Direction Tags ────────────────────────────────────────────────────────────
class Dir:
    N = 'n'   # up
    S = 's'   # down
    E = 'e'   # right
    W = 'w'   # left
    ALL = ('n', 's', 'e', 'w')

# Maps a (dx, dy) facing tuple to a direction tag
FACING_TO_DIR: dict = {
    DIR_UP:    Dir.N,
    DIR_DOWN:  Dir.S,
    DIR_RIGHT: Dir.E,
    DIR_LEFT:  Dir.W,
    (0, 0):    Dir.S,   # default when standing still
}

# ─── Animation States ─────────────────────────────────────────────────────────
class State:
    IDLE   = 'idle'
    WALK   = 'walk'
    ATTACK = 'attack'
    HURT   = 'hurt'
    DEAD   = 'dead'
    ALL    = ('idle', 'walk', 'attack', 'hurt', 'dead')

# ─── Frame configuration per state ───────────────────────────────────────────
# ticks_per_frame: how many game frames to show each sprite frame
# length        : how many distinct sprite frames exist
# looping       : False → freezes on last frame then returns to IDLE
_STATE_CONFIG = {
    State.IDLE:   {'ticks': 14, 'length': 4, 'loop': True},
    State.WALK:   {'ticks':  7, 'length': 4, 'loop': True},
    State.ATTACK: {'ticks':  5, 'length': 3, 'loop': False},
    State.HURT:   {'ticks':  4, 'length': 2, 'loop': False},
    State.DEAD:   {'ticks':  8, 'length': 4, 'loop': False},
}


class Animator:
    """
    Tracks animation state for a single entity.

    Usage in Entity.update():
        # entity is moving
        self.animator.push_walk(facing_tuple)
        # entity attacks
        self.animator.trigger_attack()
        # entity is hit
        self.animator.trigger_hurt()
        # entity dies
        self.animator.trigger_dead()
        # call every frame regardless
        self.animator.tick()
    """

    def __init__(self, entity_type: str):
        self.entity_type: str = entity_type
        self._state:     str = State.IDLE
        self._direction: str = Dir.S
        self._frame:     int = 0
        self._timer:     int = 0
        self._locked:    bool = False   # True while non-looping anim plays

    # ── Queries ──────────────────────────────────────────────────────────────
    @property
    def state(self)     -> str: return self._state
    @property
    def direction(self) -> str: return self._direction
    @property
    def frame(self)     -> int: return self._frame

    # ── Triggers ─────────────────────────────────────────────────────────────
    def push_walk(self, facing: tuple):
        """Call when the entity is actively moving."""
        if self._locked:
            return
        self._direction = FACING_TO_DIR.get(facing, Dir.S)
        if self._state != State.WALK:
            self._set_state(State.WALK)

    def push_idle(self, facing: tuple | None = None):
        """Call when the entity stops."""
        if self._locked:
            return
        if facing:
            self._direction = FACING_TO_DIR.get(facing, Dir.S)
        if self._state not in (State.IDLE,):
            self._set_state(State.IDLE)

    def trigger_attack(self, facing: tuple | None = None):
        """Interrupt with attack animation (non-looping)."""
        if facing:
            self._direction = FACING_TO_DIR.get(facing, Dir.S)
        self._set_state(State.ATTACK)
        self._locked = True

    def trigger_hurt(self):
        """Interrupt with hurt flash (non-looping, high priority)."""
        if self._state == State.DEAD:
            return
        self._set_state(State.HURT)
        self._locked = True

    def trigger_dead(self):
        """Play death animation; entity freezes on last frame."""
        self._set_state(State.DEAD)
        self._locked = True

    # ── Per-frame tick ────────────────────────────────────────────────────────
    def tick(self):
        cfg    = _STATE_CONFIG[self._state]
        ticks  = cfg['ticks']
        length = cfg['length']
        loop   = cfg['loop']

        self._timer += 1
        if self._timer >= ticks:
            self._timer = 0
            next_frame  = self._frame + 1
            if next_frame >= length:
                if loop:
                    self._frame = 0
                else:
                    # Hold last frame
                    self._frame = length - 1
                    if self._state != State.DEAD:
                        # Non-dead non-looping anims unlock after finishing
                        self._locked = False
                        self._set_state(State.IDLE)
            else:
                self._frame = next_frame

    # ── Internal ─────────────────────────────────────────────────────────────
    def _set_state(self, state: str):
        if self._state != state:
            self._state = state
            self._frame = 0
            self._timer = 0

    # ── Convenience: key for asset lookup ────────────────────────────────────
    def sprite_key(self) -> tuple:
        """Returns (entity_type, state, direction, frame) for AssetManager."""
        return (self.entity_type, self._state, self._direction, self._frame)

    def fallback_keys(self) -> list:
        """
        Ordered list of sprite keys to try in sequence.
        asset_manager uses these to implement the fallback chain.
        """
        et  = self.entity_type
        st  = self._state
        dr  = self._direction
        frm = self._frame
        return [
            (et, st,          dr,    frm),   # exact
            (et, st,          dr,    0),     # first frame of same state/dir
            (et, State.IDLE,  dr,    0),     # idle first frame, same dir
            (et, State.IDLE,  Dir.S, 0),     # idle south (canonical default)
        ]
