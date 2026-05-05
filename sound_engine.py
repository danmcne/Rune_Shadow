"""
Rune & Shadow – Sound Engine v4
Harmony-driven procedural music generation.

Two-level architecture
----------------------
  Slow layer  : chord progressions per area (changes every bar)
  Fast layer  : three voices (bass / melody / counter) that are
                chord-aware and follow a shared metric beat grid

Key ideas
---------
  * All three voices share the same bar clock → they always lock rhythmically
  * Rhythm patterns are (dur_beats, is_note) tuples summing to the time
    signature's beat count.  Rests are first-class citizens.
  * Note selection is chord-driven: strong beats get chord tones, weak beats
    allow passing/scale tones, smooth (stepwise) motion is preferred.
  * 16 bars are rendered as a single mixed PCM buffer and looped.  Phrase-level
    variation (texture, density) gives perceptual forward motion.
  * Biome identity comes from chord quality + scale mode + BPM + timbre.

SFX are synthesised on-demand and cached; unchanged from v3.
"""

import math, array, random
import pygame

SAMPLE_RATE = 22050
CHANNELS    = 2
BIT_DEPTH   = -16
BUFFER_SIZE = 512

def _db(db): return 10 ** (db / 20)
MUSIC_VOL = _db(-24)
SFX_BASE  = _db(-12)

_inited = False

def init():
    global _inited
    if _inited: return
    try:
        pygame.mixer.pre_init(SAMPLE_RATE, BIT_DEPTH, CHANNELS, BUFFER_SIZE)
        pygame.mixer.init()
        pygame.mixer.set_num_channels(16)
        _inited = True
    except Exception as e:
        print(f"[Sound] init failed: {e}")

def _dh(*args):
    h = 5381
    for a in args:
        for c in str(a): h = ((h << 5) + h) ^ ord(c)
    return h & 0x7FFFFFFF


# ── Pitch helpers ─────────────────────────────────────────────────────────────
REST = None

_NOTE_NAMES = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

def midi(name, oct_):
    return 12 * (oct_ + 1) + _NOTE_NAMES[name.upper()]

def freq(n):
    return 440.0 * (2.0 ** ((n - 69) / 12.0))

CHORD_IVLS = {
    'maj':  [0, 4, 7],
    'min':  [0, 3, 7],
    'dom7': [0, 4, 7, 10],
    'min7': [0, 3, 7, 10],
    'maj7': [0, 4, 7, 11],
    'dim':  [0, 3, 6],
    'dim7': [0, 3, 6, 9],
    'sus4': [0, 5, 7],
    'aug':  [0, 4, 8],
}

MAJOR      = [0, 2, 4, 5, 7, 9, 11]
NAT_MINOR  = [0, 2, 3, 5, 7, 8, 10]
HARM_MINOR = [0, 2, 3, 5, 7, 8, 11]
DORIAN     = [0, 2, 3, 5, 7, 9, 10]
PHRYGIAN   = [0, 1, 3, 5, 7, 8, 10]

def _chord_pool(root, quality, lo, hi):
    ivs = CHORD_IVLS.get(quality, [0, 4, 7])
    pcs = {(root + iv) % 12 for iv in ivs}
    return [n for n in range(lo, hi + 1) if n % 12 in pcs]

def _scale_pool(key, scale_ivs, lo, hi):
    pcs = {(key + iv) % 12 for iv in scale_ivs}
    return [n for n in range(lo, hi + 1) if n % 12 in pcs]

def _nearest(pool, target):
    if not pool: return target
    return min(pool, key=lambda n: abs(n - target))

def _stepwise(pool, prev, rng, step_prob=0.68):
    """Pick from pool preferring pitches within 3 semitones of prev."""
    if not pool: return prev
    near = [n for n in pool if 0 < abs(n - prev) <= 3]
    if near and rng.random() < step_prob:
        return rng.choice(near)
    return rng.choice(pool)


# ── Waveform synthesis ────────────────────────────────────────────────────────
def _wave(ph, kind):
    if kind == 'square':   return 1.0 if ph < 0.5 else -1.0
    if kind == 'pulse':    return 1.0 if ph < 0.25 else -1.0
    if kind == 'triangle': return 4.0 * abs(ph - 0.5) - 1.0
    if kind == 'sawtooth': return 2.0 * ph - 1.0
    return math.sin(2 * math.pi * ph)

def _env(i, n, atk=0.018, rel=0.14):
    an = max(1, int(n * atk))
    rn = max(1, int(n * rel))
    if i < an:     return i / an
    if i > n - rn: return max(0.0, (n - i) / rn)
    return 1.0

def _render_note(note, dur_s, kind, vol):
    n = max(1, int(SAMPLE_RATE * dur_s))
    out = array.array('h')
    if note is REST:
        out.extend([0] * (n * 2))
        return out
    f = freq(note)
    for i in range(n):
        s = _wave((f * i / SAMPLE_RATE) % 1.0, kind) * _env(i, n) * vol
        v = max(-32767, min(32767, int(s * 32767)))
        out.append(v); out.append(v)
    return out

def _mix_into(dst, src, offset):
    end = min(len(dst), offset + len(src))
    for i in range(offset, end):
        dst[i] = max(-32767, min(32767, dst[i] + src[i - offset]))


# ── Rhythm patterns ───────────────────────────────────────────────────────────
# Each pattern is a list of (duration_beats, is_note) tuples.
# Sum of durations = time-signature numerator (4 for 4/4, 3 for 3/4).
# is_note=True → pitch; is_note=False → rest.

N, R = True, False

RHYTHM_4 = {
    'bass': [
        [(4, N)],
        [(2, N), (2, N)],
        [(2, N), (1, N), (1, N)],
        [(1, N), (1, N), (2, N)],
        [(3, N), (1, N)],
        [(1, N), (1, R), (1, N), (1, R)],
        [(2, N), (1, R), (1, N)],
    ],
    'melody': [
        [(1, N), (1, N), (1, N), (1, N)],
        [(1, N), (1, N), (2, N)],
        [(2, N), (1, N), (1, N)],
        [(1, N), (1, R), (1, N), (1, N)],
        [(1, R), (1, N), (1, N), (1, N)],
        [(1, N), (1, N), (1, R), (1, N)],
        [(1, N), (1, N), (2, R)],
        [(2, R), (1, N), (1, N)],
        [(0.5, N), (0.5, N), (0.5, N), (0.5, N), (1, N), (1, N)],
        [(1.5, N), (0.5, N), (1, N), (1, N)],
    ],
    'counter': [
        [(4, R)],
        [(4, N)],
        [(2, R), (2, N)],
        [(2, N), (2, R)],
        [(1, R), (1, N), (1, R), (1, N)],
        [(1, R), (1, N), (2, N)],
        [(2, R), (0.5, N), (0.5, N), (1, N)],
    ],
}

RHYTHM_3 = {
    'bass': [
        [(3, N)],
        [(2, N), (1, N)],
        [(1, N), (2, N)],
        [(1, N), (1, R), (1, N)],
    ],
    'melody': [
        [(1, N), (1, N), (1, N)],
        [(2, N), (1, N)],
        [(1, N), (2, N)],
        [(1, R), (1, N), (1, N)],
        [(1, N), (1, R), (1, N)],
        [(1, N), (0.5, N), (0.5, N), (1, N)],
        [(2, R), (1, N)],
        [(3, R)],
    ],
    'counter': [
        [(3, R)],
        [(3, N)],
        [(1, R), (2, N)],
        [(1, R), (1, N), (1, N)],
        [(2, N), (1, R)],
    ],
}


# ── Song definitions ──────────────────────────────────────────────────────────
def _song(bpm, meter, key, scale, prog,
          bass_r=(36, 55), mel_r=(55, 79), cnt_r=(62, 84),
          bw='square', mw='triangle', cw='pulse',
          bv=0.55, mv=0.42, cv=0.27):
    return dict(bpm=bpm, meter=meter, key=key, scale=scale, prog=prog,
                bass_r=bass_r, mel_r=mel_r, cnt_r=cnt_r,
                bw=bw, mw=mw, cw=cw, bv=bv, mv=mv, cv=cv)

SONGS = {
    # Town: C major, I-V-vi-IV, cheerful
    'town': _song(
        bpm=118, meter=4, key=midi('C', 4), scale=MAJOR,
        prog=[
            (0, 'maj'),  (0, 'maj'),
            (7, 'maj'),  (7, 'maj'),
            (9, 'min'),  (9, 'min'),
            (5, 'maj'),  (7, 'maj'),
        ],
        bw='square', mw='triangle', cw='pulse',
        bv=0.52, mv=0.42, cv=0.26,
    ),
    # Forest (east): G natural minor, i-VII-VI-V, energetic
    'east': _song(
        bpm=132, meter=4, key=midi('G', 3), scale=NAT_MINOR,
        prog=[
            (0,  'min'),  (0,  'min'),
            (10, 'maj'),  (10, 'maj'),
            (8,  'maj'),  (8,  'maj'),
            (10, 'maj'),  (7,  'maj'),
        ],
        bw='square', mw='triangle', cw='pulse',
        bv=0.54, mv=0.43, cv=0.26,
    ),
    # Snow (north): A minor waltz, sparse
    'north': _song(
        bpm=102, meter=3, key=midi('A', 3), scale=NAT_MINOR,
        prog=[
            (0,  'min'),  (0,  'min'),
            (7,  'min'),  (7,  'min'),
            (10, 'maj'),  (5,  'maj'),
            (7,  'min'),  (0,  'min'),
        ],
        bw='square', mw='sine', cw='triangle',
        bv=0.48, mv=0.39, cv=0.22,
        bass_r=(36, 52), mel_r=(52, 76), cnt_r=(60, 81),
    ),
    # Desert (south): D Phrygian, bII signature
    'south': _song(
        bpm=105, meter=4, key=midi('D', 3), scale=PHRYGIAN,
        prog=[
            (0,  'min'),  (0,  'min'),
            (1,  'maj'),  (1,  'maj'),
            (0,  'min'),  (1,  'maj'),
            (10, 'min'),  (0,  'min'),
        ],
        bw='sawtooth', mw='triangle', cw='pulse',
        bv=0.52, mv=0.41, cv=0.27,
    ),
    # Swamp (west): E Dorian, murky
    'west': _song(
        bpm=88, meter=4, key=midi('E', 3), scale=DORIAN,
        prog=[
            (0,  'min'),  (0,  'min'),
            (5,  'min'),  (5,  'min'),
            (7,  'maj'),  (7,  'maj'),
            (5,  'min'),  (0,  'min'),
        ],
        bw='square', mw='sine', cw='triangle',
        bv=0.55, mv=0.39, cv=0.23,
        bass_r=(33, 50), mel_r=(50, 74), cnt_r=(57, 79),
    ),
    # Haunted towns: C minor waltz, eerie
    'haunt': _song(
        bpm=76, meter=3, key=midi('C', 3), scale=NAT_MINOR,
        prog=[
            (0,  'min'),  (0,  'min'),
            (8,  'maj'),  (8,  'maj'),
            (10, 'maj'),  (10, 'maj'),
            (7,  'dom7'), (7,  'dom7'),
        ],
        bw='sawtooth', mw='triangle', cw='pulse',
        bv=0.50, mv=0.37, cv=0.20,
        bass_r=(33, 50), mel_r=(48, 72), cnt_r=(55, 77),
    ),
    # Dungeons: F minor, oppressive
    'dungeon': _song(
        bpm=70, meter=4, key=midi('F', 3), scale=NAT_MINOR,
        prog=[
            (0,  'min'),  (0,  'min'),
            (8,  'maj'),  (8,  'maj'),
            (10, 'maj'),  (10, 'maj'),
            (5,  'min'),  (7,  'dom7'),
        ],
        bw='square', mw='sawtooth', cw='pulse',
        bv=0.58, mv=0.37, cv=0.21,
        bass_r=(29, 48), mel_r=(45, 69), cnt_r=(52, 74),
    ),
    # Castles: D harmonic minor, regal but unstable
    'castle': _song(
        bpm=80, meter=4, key=midi('D', 3), scale=HARM_MINOR,
        prog=[
            (0,  'min'),  (0,  'min'),
            (5,  'min'),  (5,  'min'),
            (7,  'maj'),  (7,  'maj'),
            (0,  'min'),  (7,  'dom7'),
        ],
        bw='sawtooth', mw='square', cw='triangle',
        bv=0.55, mv=0.39, cv=0.24,
        bass_r=(33, 52), mel_r=(50, 74), cnt_r=(57, 81),
    ),
}

MAP_TO_SONG = {
    'town':       'town',
    'east':       'east',  'north':      'north',
    'south':      'south', 'west':       'west',
    'east_town':  'haunt', 'north_town': 'haunt',
    'south_town': 'haunt', 'west_town':  'haunt',
}
DUNGEON_SONG = {**{i: 'dungeon' for i in range(9)},
                **{i: 'castle'  for i in range(9, 13)}}


# ── Phrase plan ───────────────────────────────────────────────────────────────
# 16-bar loop = 4 phrases × 4 bars each.
# Each phrase has a texture instruction for each voice.
PHRASE_PLAN = [
    {'cnt_rest': False, 'mel_sparse': False, 'mel_busy': False},  # full, relaxed
    {'cnt_rest': True,  'mel_sparse': False, 'mel_busy': False},  # bass+mel only
    {'cnt_rest': False, 'mel_sparse': False, 'mel_busy': True},   # full, busier
    {'cnt_rest': False, 'mel_sparse': True,  'mel_busy': False},  # full, sparse mel
]


# ── Song renderer ─────────────────────────────────────────────────────────────
def _render_song(song_key, seed=0):
    """Render 16 bars of song_key → stereo int16 bytes for pygame.mixer.Sound."""
    song   = SONGS[song_key]
    bpm    = song['bpm']
    meter  = song['meter']
    beat_s = 60.0 / bpm
    bar_s  = beat_s * meter
    prog   = song['prog']    # 8-bar progression; indexed mod len(prog)
    key    = song['key']
    scale  = song['scale']
    n_bars = 16

    total_smp = int(SAMPLE_RATE * bar_s * n_bars)
    out = array.array('h', [0] * (total_smp * 2))

    rng      = random.Random(seed ^ _dh(song_key))
    rl_4     = RHYTHM_4
    rl_3     = RHYTHM_3
    rl       = rl_4 if meter == 4 else rl_3

    voice_defs = [
        ('bass', song['bass_r'], song['bw'], song['bv'] * MUSIC_VOL),
        ('mel',  song['mel_r'],  song['mw'], song['mv'] * MUSIC_VOL),
        ('cnt',  song['cnt_r'],  song['cw'], song['cv'] * MUSIC_VOL),
    ]

    for v_name, v_range, v_wave, v_vol in voice_defs:
        lo, hi    = v_range
        prev_note = (lo + hi) // 2
        arr_pos   = 0
        rk        = {'bass': 'bass', 'mel': 'melody', 'cnt': 'counter'}[v_name]
        rhythm_lib = rl[rk]

        for bar_idx in range(n_bars):
            chord_off, chord_qual = prog[bar_idx % len(prog)]
            chord_root = key + chord_off
            ctones = _chord_pool(chord_root, chord_qual, lo, hi)
            stones = _scale_pool(key, scale, lo, hi)
            if not ctones: ctones = stones or [prev_note]
            if not stones: stones = ctones

            phrase_idx = bar_idx // 4
            ph = PHRASE_PLAN[phrase_idx % len(PHRASE_PLAN)]

            # Counter: silent for whole phrase when cnt_rest
            if v_name == 'cnt' and ph['cnt_rest']:
                arr_pos += int(SAMPLE_RATE * bar_s) * 2
                continue

            # Select rhythm pattern
            if v_name == 'mel':
                if ph['mel_busy']:
                    busy = [p for p in rhythm_lib if sum(1 for d, n in p if n) >= (3 if meter == 4 else 2)]
                    pattern = rng.choice(busy if busy else rhythm_lib)
                elif ph['mel_sparse']:
                    sparse = [p for p in rhythm_lib if any(not n for _, n in p)]
                    pattern = rng.choice(sparse if sparse else rhythm_lib)
                else:
                    pattern = rng.choice(rhythm_lib)
            elif v_name == 'cnt':
                # Extra rest tendency in mid-phrase bars
                if bar_idx % 4 != 0 and rng.random() < 0.40:
                    rest_pats = [p for p in rhythm_lib if all(not n for _, n in p)]
                    pattern = rng.choice(rest_pats if rest_pats else rhythm_lib)
                else:
                    pattern = rng.choice(rhythm_lib)
            else:
                # Bass: prefer slower patterns (whole/half notes) ~half the time
                slow = [p for p in rhythm_lib if len(p) <= 2]
                pattern = rng.choice(slow if slow and rng.random() < 0.55 else rhythm_lib)

            beat_pos = 0.0
            for dur_beats, is_note in pattern:
                dur_s = dur_beats * beat_s
                n_smp = int(SAMPLE_RATE * dur_s)

                if not is_note:
                    note = REST
                else:
                    is_strong = (beat_pos == 0.0)

                    if v_name == 'bass':
                        if is_strong:
                            roots = [n for n in ctones if n % 12 == chord_root % 12]
                            note  = rng.choice(roots) if roots else _nearest(ctones, lo + 5)
                        else:
                            fifth_pc = (chord_root + 7) % 12
                            fifths   = [n for n in ctones if n % 12 == fifth_pc]
                            note = rng.choice(fifths if fifths else ctones)

                    elif v_name == 'mel':
                        if is_strong:
                            note = _stepwise(ctones, prev_note, rng, 0.65)
                        else:
                            pool = ctones if rng.random() < 0.55 else stones
                            note = _stepwise(pool, prev_note, rng, 0.70)

                    else:  # counter
                        upper = [n for n in ctones if n >= prev_note - 2]
                        note  = _stepwise(upper if upper else ctones, prev_note, rng, 0.55)

                    prev_note = note

                note_buf = _render_note(note, dur_s, v_wave, v_vol)
                _mix_into(out, note_buf, arr_pos)
                arr_pos  += len(note_buf)
                beat_pos += dur_beats

    return bytes(out)


# ── Sound cache & playback ────────────────────────────────────────────────────
_snd_cache = {}
_sfx_cache = {}
_cur_song  = None
CH_MUSIC   = 0

def _get_song_sound(sk):
    if sk in _snd_cache: return _snd_cache[sk]
    if not _inited: return None
    snd = pygame.mixer.Sound(buffer=_render_song(sk))
    _snd_cache[sk] = snd
    return snd

def play_area_music(map_key, dungeon_id=-1):
    global _cur_song
    if not _inited: return
    sk = DUNGEON_SONG.get(dungeon_id, 'dungeon') if dungeon_id >= 0 else MAP_TO_SONG.get(map_key, 'dungeon')
    if sk == _cur_song: return
    _cur_song = sk
    snd = _get_song_sound(sk)
    if snd is None: return
    pygame.mixer.Channel(CH_MUSIC).fadeout(700)
    pygame.mixer.Channel(CH_MUSIC).play(snd, loops=-1, fade_ms=1000)

def stop_music(fade_ms=600):
    if not _inited: return
    pygame.mixer.Channel(CH_MUSIC).fadeout(fade_ms)

def set_music_volume(v):
    if not _inited: return
    pygame.mixer.Channel(CH_MUSIC).set_volume(max(0.0, min(1.0, v)))


# ── SFX (unchanged from v3) ───────────────────────────────────────────────────
def _mk_sfx(key):
    SR = SAMPLE_RATE
    sv = SFX_BASE * 3.5

    def noise(n, vol=sv * 0.7):
        r = random.Random(_dh(key, 'n')); out = array.array('h')
        for i in range(n):
            e = 1.0 - i / n
            v = max(-32767, min(32767, int((r.random() * 2 - 1) * e * vol * 32767)))
            out.append(v); out.append(v)
        return out

    def sweep(f0, f1, dur, wv='square', vol=sv * 0.5):
        n = int(SR * dur); out = array.array('h')
        for i in range(n):
            f  = f0 + (f1 - f0) * (i / n)
            ph = (f * i / SR) % 1.0
            e  = max(0.0, 1.0 - i / n)
            v  = max(-32767, min(32767, int(_wave(ph, wv) * e * vol * 32767)))
            out.append(v); out.append(v)
        return out

    def beep(f, dur, wv='square', vol=sv * 0.5):
        n_midi = int(round(69 + 12 * math.log2(f / 440)))
        return _render_note(n_midi, dur, wv, vol)

    def cat(*bufs):
        out = array.array('h')
        for b in bufs: out.extend(b)
        return out

    sfx = {
        'hit_melee':    lambda: cat(noise(int(SR*.03)),      sweep(200, 80,   .07, 'square')),
        'hit_ranged':   lambda: sweep(600, 200, .08, 'triangle'),
        'spell_cast':   lambda: cat(sweep(300,1200,.12,'sine',sv*.30), sweep(1200,400,.10,'triangle',sv*.25)),
        'area_blast':   lambda: cat(noise(int(SR*.06),sv),   sweep(300, 60,   .25, 'sawtooth', sv*.60)),
        'player_hurt':  lambda: cat(noise(int(SR*.04),sv*.7),sweep(400,150,   .08, 'square',   sv*.40)),
        'player_dead':  lambda: cat(sweep(440,110,.25,'square',sv*.50), sweep(110,55,.30,'sawtooth',sv*.45)),
        'gate_travel':  lambda: cat(sweep(200,1600,.15,'triangle',sv*.45),noise(int(SR*.04),sv*.40),sweep(1600,300,.15,'triangle',sv*.40)),
        'chest_open':   lambda: cat(sweep(440,880,.08,'square',sv*.35),  sweep(880,1320,.08,'triangle',sv*.30)),
        'chest_smash':  lambda: cat(noise(int(SR*.05),sv*.9), sweep(300,100,.10,'sawtooth',sv*.45)),
        'shrine':       lambda: cat(beep(523,.10,'triangle',sv*.35),beep(659,.10,'triangle',sv*.35),
                                    beep(784,.10,'triangle',sv*.35),beep(1046,.20,'sine',sv*.35)),
        'pickup':       lambda: cat(sweep(660,880,.05,'square',sv*.30),  sweep(880,1100,.05,'triangle',sv*.25)),
        'stairs_down':  lambda: sweep(440, 220, .20, 'square',   sv*.35),
        'stairs_up':    lambda: sweep(220, 440, .20, 'triangle', sv*.35),
        'berserk':      lambda: cat(sweep(200,1600,.10,'sawtooth',sv*.55),sweep(1600,200,.08,'sawtooth',sv*.50)),
        'mimic_reveal': lambda: cat(noise(int(SR*.04),sv),sweep(600,200,.12,'sawtooth',sv*.55),sweep(200,1000,.10,'square',sv*.50)),
        'slime_atk':    lambda: sweep(120, 60,  .12, 'sine',     sv*.35),
        'bat_atk':      lambda: sweep(900, 600, .08, 'triangle', sv*.30),
        'spider_atk':   lambda: cat(noise(int(SR*.025),sv*.5), sweep(400,200,.06,'square',sv*.35)),
        'goblin_atk':   lambda: sweep(300, 150, .10, 'sawtooth', sv*.38),
        'skeleton_atk': lambda: cat(noise(int(SR*.02),sv*.5), sweep(250,180,.07,'square',sv*.35)),
        'ghost_atk':    lambda: sweep(800, 300, .15, 'sine',     sv*.28),
        'troll_atk':    lambda: cat(noise(int(SR*.05),sv*.8), sweep(150,60,.12,'square',sv*.45)),
        'yeti_atk':     lambda: cat(noise(int(SR*.04),sv*.7), sweep(200,80,.12,'square',sv*.45)),
        'dragon_atk':   lambda: cat(sweep(100,800,.08,'sawtooth',sv*.60),noise(int(SR*.06),sv*.90),sweep(800,100,.12,'sawtooth',sv*.55)),
    }
    fn = sfx.get(key)
    return fn() if fn else noise(int(SR * .05))

def _get_sfx(key):
    if not _inited: return None
    if key not in _sfx_cache:
        _sfx_cache[key] = pygame.mixer.Sound(buffer=bytes(_mk_sfx(key)))
    return _sfx_cache[key]

def play_sfx(key, volume=1.0):
    if not _inited: return
    snd = _get_sfx(key)
    if snd is None: return
    ch = pygame.mixer.find_channel(True)
    if ch:
        ch.set_volume(min(1.0, volume))
        ch.play(snd)

ENEMY_ATTACK_SFX = {
    'slime':'slime_atk','bat':'bat_atk','spider':'spider_atk','giant_spider':'spider_atk',
    'goblin':'goblin_atk','skeleton':'skeleton_atk','ghost':'ghost_atk','troll':'troll_atk',
    'yeti':'yeti_atk','ice_wraith':'ghost_atk','scorpion':'spider_atk','mummy':'skeleton_atk',
    'swamp_toad':'slime_atk','will_o':'ghost_atk','mimic':'mimic_reveal',
    'dragon':'dragon_atk','frost_dragon':'dragon_atk','sand_dragon':'dragon_atk','swamp_dragon':'dragon_atk',
}

def preload_all():
    if not _inited: return
    for sk in SONGS: _get_song_sound(sk)
    for k in (['hit_melee','hit_ranged','spell_cast','area_blast','player_hurt','player_dead',
               'gate_travel','chest_open','chest_smash','shrine','pickup','stairs_down',
               'stairs_up','berserk','mimic_reveal'] + list(set(ENEMY_ATTACK_SFX.values()))):
        _get_sfx(k)
