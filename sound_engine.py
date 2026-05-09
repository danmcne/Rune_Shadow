"""
Rune & Shadow – Sound Engine v5
Motif-driven, harmony-aware, biome-specific procedural composition.

Architecture
------------
  Layer 1 – Biome style profile: motif family, rhythm character, bass behaviour
  Layer 2 – Harmonic functions: T / Pre-Dominant / Dominant realized per section
  Layer 3 – Motif engine: reusable melodic cells with phrase-level transformation
  Layer 4 – Voice rendering: chord-aware note selection with weighted beat positions
  Layer 5 – DSP: low-pass filter + subtle velocity variation

Key changes from v4
-------------------
  * Motif system: melody follows recurring interval+rhythm cells, transformed
    at phrase boundaries (transpose, invert, truncate, augment)
  * Beat hierarchy: 4/4 weights [1.0, 0.4, 0.7, 0.5] – strong beats prefer
    chord tones, weak beats allow scale/passing tones
  * Biome-specific composition rules: each area has its own rhythmic personality,
    motif pool, texture density, and bass behaviour
  * Simple IIR low-pass filter applied per-voice to reduce harshness
  * Subtle velocity variation per note for humanisation
  * Loop mutation: alternate cadence every second 16-bar repeat
"""

import math, array, random
import pygame

SAMPLE_RATE = 22050
CHANNELS    = 2
BIT_DEPTH   = -16
BUFFER_SIZE = 512

def _db(db): return 10 ** (db / 20)
MUSIC_VOL = _db(-23)
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
_NOTE_NAMES = {'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}

def midi(name, oct_): return 12*(oct_+1) + _NOTE_NAMES[name.upper()]
def freq(n):          return 440.0 * (2.0**((n-69)/12.0))

CHORD_IVLS = {
    'maj':  [0,4,7], 'min':  [0,3,7],  'dom7': [0,4,7,10],
    'min7': [0,3,7,10], 'maj7':[0,4,7,11], 'dim': [0,3,6],
    'dim7': [0,3,6,9],  'sus4': [0,5,7],   'aug':  [0,4,8],
}

MAJOR      = [0,2,4,5,7,9,11]
NAT_MINOR  = [0,2,3,5,7,8,10]
HARM_MINOR = [0,2,3,5,7,8,11]
DORIAN     = [0,2,3,5,7,9,10]
PHRYGIAN   = [0,1,3,5,7,8,10]

def _chord_pool(root, quality, lo, hi):
    pcs = {(root+iv)%12 for iv in CHORD_IVLS.get(quality,[0,4,7])}
    return [n for n in range(lo, hi+1) if n%12 in pcs]

def _scale_pool(key, scale_ivs, lo, hi):
    pcs = {(key+iv)%12 for iv in scale_ivs}
    return [n for n in range(lo, hi+1) if n%12 in pcs]

def _nearest(pool, target):
    if not pool: return target
    return min(pool, key=lambda n: abs(n-target))

def _stepwise(pool, prev, rng, step_prob=0.65):
    if not pool: return prev
    near = [n for n in pool if 0 < abs(n-prev) <= 3]
    if near and rng.random() < step_prob: return rng.choice(near)
    return rng.choice(pool)


# ── Motif library ─────────────────────────────────────────────────────────────
# Each motif: (interval_steps, beat_durations)
#   interval_steps : semitone offsets from prev note (contour)
#   beat_durations : positive=note, negative=rest; sum of abs = beats of motif
#   Motifs are designed to fit in 2 bars (8 beats in 4/4, 6 in 3/4).

MOTIFS = {
    # Bright / upward
    'step_up':    ([+2,+2,+1,+2],    [1, 1, 1, 2]),
    'fanfare':    ([+4,+3,+2,+1],    [0.5,0.5,1, 2]),
    'arch':       ([+2,+3,-2,-1],    [0.5,0.5,1, 2]),
    # Questioning / descending
    'step_down':  ([-2,-1,-2,-1],    [1, 1, 1, 2]),
    'falling':    ([-3,-2,+1,-1],    [0.5,0.5,2,-1]),
    'question':   ([+2,+1,+3, 0],    [1, 1,-1, 2]),
    # Circular / ornamental
    'turn':       ([+1,-2,+1,+2],    [0.5,0.5,0.5,1.5]),
    'ornament':   ([+1,-1, 0,+2,-1], [0.25,0.25,0.5,0.5,0.5]),
    # Tense / chromatic
    'tension':    ([+1,-1,+2,-1],    [0.5,0.5,0.5,1.5]),
    'chromatic':  ([+1,+1,-1,-1],    [0.5,0.5,0.5,0.5,1]),
    # Stable / cadential
    'cadence':    ([+2,+1,-2,-3],    [1, 1, 1, 2]),
    'drone':      ([ 0,+2, 0,-2],    [1.5,0.5,1.5,0.5]),
    # Waltz-friendly (fit 3/4 = 6 beats)
    'waltz_up':   ([+2,+2,-1],       [1, 2, 3]),
    'waltz_turn': ([+1,-1,+2,-1],    [1, 1, 1, 3]),
    'waltz_fall': ([-2,-1,+1],       [2, 1, 3]),
}

# Biome composition profiles
BIOME_PROF = {
    'town':    dict(motifs=['step_up','arch','turn','cadence'],
                   rhythm='regular', drone_bass=False,
                   syncopate=False, sparse=False,  chromatic=False),
    'east':    dict(motifs=['fanfare','step_up','arch','turn'],
                   rhythm='energetic', drone_bass=False,
                   syncopate=False, sparse=False,  chromatic=False),
    'north':   dict(motifs=['waltz_up','waltz_turn','waltz_fall','step_down'],
                   rhythm='waltz',   drone_bass=False,
                   syncopate=False, sparse=True,   chromatic=False),
    'south':   dict(motifs=['ornament','turn','drone','tension'],
                   rhythm='syncopated', drone_bass=True,
                   syncopate=True,  sparse=False,  chromatic=False),
    'west':    dict(motifs=['drone','tension','step_down','question'],
                   rhythm='sparse',  drone_bass=True,
                   syncopate=True,  sparse=True,   chromatic=False),
    'haunt':   dict(motifs=['tension','chromatic','question','waltz_fall'],
                   rhythm='asymmetric', drone_bass=False,
                   syncopate=True,  sparse=True,   chromatic=True),
    'dungeon': dict(motifs=['tension','drone','step_down','falling'],
                   rhythm='heavy',   drone_bass=True,
                   syncopate=False, sparse=False,  chromatic=True),
    'castle':  dict(motifs=['fanfare','cadence','tension','arch'],
                   rhythm='march',   drone_bass=False,
                   syncopate=False, sparse=False,  chromatic=True),
}

# Beat-position weights for 4/4 and 3/4
# Higher weight → prefer chord tones; lower → allow scale/passing
BEAT_W_44 = {0.0:1.0, 1.0:0.4, 2.0:0.7, 3.0:0.5}
BEAT_W_34 = {0.0:1.0, 1.0:0.5, 2.0:0.4}

def _beat_weight(beat_pos, meter):
    table = BEAT_W_44 if meter==4 else BEAT_W_34
    # Find nearest integer beat
    floor_beat = float(int(beat_pos)) % meter
    return table.get(floor_beat, 0.4)


# ── Rhythm pattern libraries (unchanged from v4 – still used for bass/counter) ─
N, R = True, False

RHYTHM_4 = {
    'bass': [
        [(4,N)], [(2,N),(2,N)], [(2,N),(1,N),(1,N)],
        [(1,N),(1,N),(2,N)], [(3,N),(1,N)],
        [(1,N),(1,R),(1,N),(1,R)], [(2,N),(1,R),(1,N)],
    ],
    'counter': [
        [(4,R)], [(4,N)], [(2,R),(2,N)], [(2,N),(2,R)],
        [(1,R),(1,N),(1,R),(1,N)], [(1,R),(1,N),(2,N)],
        [(2,R),(0.5,N),(0.5,N),(1,N)],
    ],
}
RHYTHM_3 = {
    'bass':    [[(3,N)],[(2,N),(1,N)],[(1,N),(2,N)],[(1,N),(1,R),(1,N)]],
    'counter': [[(3,R)],[(3,N)],[(1,R),(2,N)],[(1,R),(1,N),(1,N)],[(2,N),(1,R)]],
}


# ── Song definitions ──────────────────────────────────────────────────────────
def _song(bpm,meter,key,scale,prog,
          bass_r=(36,55),mel_r=(55,79),cnt_r=(62,84),
          bw='square',mw='triangle',cw='pulse',bv=0.55,mv=0.42,cv=0.27):
    return dict(bpm=bpm,meter=meter,key=key,scale=scale,prog=prog,
                bass_r=bass_r,mel_r=mel_r,cnt_r=cnt_r,
                bw=bw,mw=mw,cw=cw,bv=bv,mv=mv,cv=cv)

SONGS = {
    'town':    _song(118,4,midi('C',4),MAJOR,
                    [(0,'maj'),(0,'maj'),(7,'maj'),(7,'maj'),
                     (9,'min'),(9,'min'),(5,'maj'),(7,'maj')],
                    bw='square',mw='triangle',cw='pulse',bv=0.52,mv=0.42,cv=0.26),
    'east':    _song(132,4,midi('G',3),NAT_MINOR,
                    [(0,'min'),(0,'min'),(10,'maj'),(10,'maj'),
                     (8,'maj'),(8,'maj'),(10,'maj'),(7,'maj')],
                    bw='square',mw='triangle',cw='pulse',bv=0.54,mv=0.43,cv=0.26),
    'north':   _song(102,3,midi('A',3),NAT_MINOR,
                    [(0,'min'),(0,'min'),(7,'min'),(7,'min'),
                     (10,'maj'),(5,'maj'),(7,'min'),(0,'min')],
                    bw='square',mw='sine',cw='triangle',bv=0.48,mv=0.39,cv=0.22,
                    bass_r=(36,52),mel_r=(52,76),cnt_r=(60,81)),
    'south':   _song(105,4,midi('D',3),PHRYGIAN,
                    [(0,'min'),(0,'min'),(1,'maj'),(1,'maj'),
                     (0,'min'),(1,'maj'),(10,'min'),(0,'min')],
                    bw='sawtooth',mw='triangle',cw='pulse',bv=0.52,mv=0.41,cv=0.27),
    'west':    _song(88,4,midi('E',3),DORIAN,
                    [(0,'min'),(0,'min'),(5,'min'),(5,'min'),
                     (7,'maj'),(7,'maj'),(5,'min'),(0,'min')],
                    bw='square',mw='sine',cw='triangle',bv=0.55,mv=0.39,cv=0.23,
                    bass_r=(33,50),mel_r=(50,74),cnt_r=(57,79)),
    'haunt':   _song(76,3,midi('C',3),NAT_MINOR,
                    [(0,'min'),(0,'min'),(8,'maj'),(8,'maj'),
                     (10,'maj'),(10,'maj'),(7,'dom7'),(7,'dom7')],
                    bw='sawtooth',mw='triangle',cw='pulse',bv=0.50,mv=0.37,cv=0.20,
                    bass_r=(33,50),mel_r=(48,72),cnt_r=(55,77)),
    'dungeon': _song(70,4,midi('F',3),NAT_MINOR,
                    [(0,'min'),(0,'min'),(8,'maj'),(8,'maj'),
                     (10,'maj'),(10,'maj'),(5,'min'),(7,'dom7')],
                    bw='square',mw='sawtooth',cw='pulse',bv=0.58,mv=0.37,cv=0.21,
                    bass_r=(29,48),mel_r=(45,69),cnt_r=(52,74)),
    'castle':  _song(80,4,midi('D',3),HARM_MINOR,
                    [(0,'min'),(0,'min'),(5,'min'),(5,'min'),
                     (7,'maj'),(7,'maj'),(0,'min'),(7,'dom7')],
                    bw='sawtooth',mw='square',cw='triangle',bv=0.55,mv=0.39,cv=0.24,
                    bass_r=(33,52),mel_r=(50,74),cnt_r=(57,81)),
}

MAP_TO_SONG = {
    'town':'town','east':'east','north':'north','south':'south','west':'west',
    'east_town':'haunt','north_town':'haunt','south_town':'haunt','west_town':'haunt',
}
DUNGEON_SONG = {**{i:'dungeon' for i in range(9)}, **{i:'castle' for i in range(9,13)}}

# Phrase plan for 16-bar loop (4 phrases × 4 bars)
PHRASE_PLAN = [
    {'cnt_rest':False,'mel_sparse':False,'mel_busy':False},
    {'cnt_rest':True, 'mel_sparse':False,'mel_busy':False},
    {'cnt_rest':False,'mel_sparse':False,'mel_busy':True},
    {'cnt_rest':False,'mel_sparse':True, 'mel_busy':False},
]


# ── Waveform & DSP ────────────────────────────────────────────────────────────
def _wave(ph, kind):
    if kind=='square':   return 1.0 if ph<0.5 else -1.0
    if kind=='pulse':    return 1.0 if ph<0.25 else -1.0
    if kind=='triangle': return 4.0*abs(ph-0.5)-1.0
    if kind=='sawtooth': return 2.0*ph-1.0
    return math.sin(2*math.pi*ph)

def _env(i, n, atk=0.018, rel=0.14):
    an=max(1,int(n*atk)); rn=max(1,int(n*rel))
    if i<an: return i/an
    if i>n-rn: return max(0.0,(n-i)/rn)
    return 1.0

def _render_note(note, dur_s, kind, vol, velocity=1.0):
    n = max(1, int(SAMPLE_RATE*dur_s))
    out = array.array('h')
    if note is REST:
        out.extend([0]*(n*2)); return out
    f = freq(note); eff_vol = vol * velocity
    for i in range(n):
        s = _wave((f*i/SAMPLE_RATE)%1.0, kind) * _env(i,n) * eff_vol
        v = max(-32767,min(32767,int(s*32767)))
        out.append(v); out.append(v)
    return out

def _lowpass(buf, alpha=0.30):
    """Simple one-pole IIR low-pass filter. alpha=0.3 is gentle but audible."""
    out = array.array('h', buf)
    pl = pr = 0
    for i in range(0, len(out), 2):
        out[i]   = pl = int(pl + alpha*(out[i]  -pl))
        out[i+1] = pr = int(pr + alpha*(out[i+1]-pr))
    return out

def _mix_into(dst, src, offset):
    end = min(len(dst), offset+len(src))
    for i in range(offset, end):
        dst[i] = max(-32767,min(32767,dst[i]+src[i-offset]))


# ── Motif application ─────────────────────────────────────────────────────────
def _apply_motif(motif_key, start_note, ctones, stones, scale_ivs, key,
                 song, phrase_idx, rng, lo, hi):
    """
    Realise a motif as a list of (note, dur_s, velocity) triples.
    Interval steps are constrained to chord or scale tones by beat weight.
    """
    ivs, durs = MOTIFS[motif_key]
    beat_s  = 60.0 / song['bpm']
    meter   = song['meter']
    profile = BIOME_PROF.get(
        next((k for k in BIOME_PROF if song is SONGS.get(k)), 'town'), {})
    chromatic_ok = profile.get('chromatic', False)

    notes = []
    cur   = start_note
    beat_pos = 0.0
    for i, (iv, dur) in enumerate(zip(ivs, durs)):
        is_rest = dur < 0
        dur_s   = abs(dur) * beat_s
        if is_rest:
            notes.append((REST, dur_s, 0.8))
        else:
            # Raw target by interval
            raw = cur + iv
            raw = max(lo, min(hi, raw))
            # Beat weight decides how strictly we snap to chord tones
            bw  = _beat_weight(beat_pos, meter)
            if bw >= 0.7:
                pool = ctones or stones
            elif bw >= 0.5:
                pool = ctones + [n for n in stones if n not in ctones]
            else:
                pool = stones if stones else ctones
            # Snap to nearest in pool
            note = _nearest(pool, raw) if pool else raw
            # Chromatic passing tones on very weak beats for dark biomes
            if chromatic_ok and bw < 0.45 and rng.random() < 0.25:
                note = max(lo, min(hi, raw))  # allow raw chromatic
            # Keep within octave of prev for smoothness
            if abs(note-cur) > 9 and pool:
                note = _stepwise(pool, cur, rng, 0.80)
            cur = note
            velocity = 0.75 + bw*0.3 + rng.random()*0.05
            notes.append((note, dur_s, velocity))
        beat_pos += abs(dur)
    return notes

def _transform_motif(motif_key, phrase_idx, rng):
    """Return a (possibly modified) motif key for the next phrase."""
    transforms = ['same','transpose_up','transpose_down','invert','truncate']
    t = rng.choice(transforms)
    ivs, durs = MOTIFS[motif_key]
    if t=='same':           return motif_key, ivs, durs
    if t=='invert':         return motif_key+'_inv', [-iv for iv in ivs], durs
    if t=='truncate':       half=max(1,len(ivs)//2); return motif_key+'_tr', ivs[:half], durs[:half]
    if t=='transpose_up':   return motif_key, [iv+2 for iv in ivs], durs
    if t=='transpose_down': return motif_key, [iv-2 for iv in ivs], durs
    return motif_key, ivs, durs

def _register_motif(key, ivs, durs):
    """Register a transformed motif variant into the global table (temp)."""
    MOTIFS[key] = (ivs, durs)
    return key


# ── Song renderer ─────────────────────────────────────────────────────────────
def _render_song(song_key, seed=0):
    song   = SONGS[song_key]
    bpm    = song['bpm']
    meter  = song['meter']
    beat_s = 60.0/bpm; bar_s=beat_s*meter
    prog   = song['prog']; key=song['key']; scale=song['scale']
    n_bars = 16
    prof   = BIOME_PROF.get(song_key, BIOME_PROF['town'])

    total_smp = int(SAMPLE_RATE*bar_s*n_bars)
    out = array.array('h',[0]*(total_smp*2))

    rng = random.Random(seed ^ _dh(song_key))
    rl  = RHYTHM_4 if meter==4 else RHYTHM_3

    # ── BASS voice ────────────────────────────────────────────────────────────
    lo,hi = song['bass_r']
    bvol  = song['bv']*MUSIC_VOL
    drone_bass = prof.get('drone_bass',False)
    prev_b = (lo+hi)//2; arr_pos=0
    bass_buf = array.array('h',[0]*(total_smp*2))
    for bar_idx in range(n_bars):
        chord_off,chord_qual = prog[bar_idx%len(prog)]
        chord_root = key+chord_off
        ctones = _chord_pool(chord_root,chord_qual,lo,hi)
        if not ctones: ctones=[prev_b]
        pattern = rng.choice(rl['bass'][:2] if drone_bass else rl['bass'])
        beat_pos=0.0
        for dur_beats,is_note in pattern:
            dur_s=dur_beats*beat_s; n_smp=int(SAMPLE_RATE*dur_s)
            if is_note:
                if beat_pos==0.0 or drone_bass:
                    roots=[n for n in ctones if n%12==chord_root%12]
                    note = rng.choice(roots) if roots else _nearest(ctones,lo+5)
                else:
                    fifth_pc=(chord_root+7)%12
                    fifths=[n for n in ctones if n%12==fifth_pc]
                    note=rng.choice(fifths if fifths else ctones)
                prev_b=note
            else: note=REST
            nb=_render_note(note,dur_s,song['bw'],bvol,
                            0.85+rng.random()*0.15 if note is not REST else 0.8)
            _mix_into(bass_buf,nb,arr_pos); arr_pos+=len(nb); beat_pos+=dur_beats
    bass_buf=_lowpass(bass_buf,0.25)
    _mix_into(out,bass_buf,0)

    # ── MELODY voice (motif-driven) ────────────────────────────────────────────
    lo,hi=song['mel_r']; mvol=song['mv']*MUSIC_VOL
    motif_pool = prof.get('motifs',['step_up','turn','cadence'])
    # Filter to motifs compatible with meter
    if meter==3:
        motif_pool=[m for m in motif_pool if m.startswith('waltz')] or ['waltz_up','waltz_turn']
    else:
        motif_pool=[m for m in motif_pool if not m.startswith('waltz')]
    if not motif_pool: motif_pool=['step_up','turn']

    cur_motif_key = rng.choice(motif_pool)
    cur_motif_ivs, cur_motif_durs = MOTIFS[cur_motif_key]
    prev_m=(lo+hi)//2; arr_pos=0
    mel_buf=array.array('h',[0]*(total_smp*2))

    for bar_idx in range(n_bars):
        chord_off,chord_qual=prog[bar_idx%len(prog)]
        chord_root=key+chord_off
        ctones=_chord_pool(chord_root,chord_qual,lo,hi)
        stones=_scale_pool(key,scale,lo,hi)
        if not ctones: ctones=stones or [prev_m]
        if not stones: stones=ctones
        ph=PHRASE_PLAN[bar_idx//4 % len(PHRASE_PLAN)]
        if ph.get('cnt_rest') and not ph.get('mel_busy'): pass

        # At phrase start, optionally transform motif
        if bar_idx%4==0 and bar_idx>0:
            _, cur_motif_ivs, cur_motif_durs = _transform_motif(cur_motif_key,bar_idx//4,rng)

        # Apply motif for this bar
        temp_song_key = song_key   # for profile lookup
        temp_song = song
        notes = _apply_motif_raw(cur_motif_ivs, cur_motif_durs, prev_m,
                                  ctones, stones, bpm, meter, lo, hi,
                                  song['mw'], mvol, rng,
                                  prof.get('chromatic',False))
        for note,dur_s,vel in notes:
            nb=_render_note(note,dur_s,song['mw'],mvol,vel)
            if arr_pos+len(nb)<=len(mel_buf):
                _mix_into(mel_buf,nb,arr_pos)
            arr_pos+=len(nb)
            if note is not REST: prev_m=note
    mel_buf=_lowpass(mel_buf,0.35)
    _mix_into(out,mel_buf,0)

    # ── COUNTER voice ─────────────────────────────────────────────────────────
    lo,hi=song['cnt_r']; cvol=song['cv']*MUSIC_VOL
    prev_c=(lo+hi)//2; arr_pos=0
    cnt_buf=array.array('h',[0]*(total_smp*2))
    for bar_idx in range(n_bars):
        chord_off,chord_qual=prog[bar_idx%len(prog)]
        chord_root=key+chord_off
        ctones=_chord_pool(chord_root,chord_qual,lo,hi)
        if not ctones: ctones=[prev_c]
        ph=PHRASE_PLAN[bar_idx//4 % len(PHRASE_PLAN)]
        if ph['cnt_rest']:
            arr_pos+=int(SAMPLE_RATE*bar_s)*2; continue
        # Extra rest tendency mid-phrase
        if bar_idx%4!=0 and rng.random()<0.40:
            rest_pats=[p for p in rl['counter'] if all(not n for _,n in p)]
            pattern=rng.choice(rest_pats if rest_pats else rl['counter'])
        else:
            pattern=rng.choice(rl['counter'])
        beat_pos=0.0
        for dur_beats,is_note in pattern:
            dur_s=dur_beats*beat_s
            if is_note:
                upper=[n for n in ctones if n>=prev_c-2]
                note=_stepwise(upper if upper else ctones,prev_c,rng,0.55)
                prev_c=note
            else: note=REST
            nb=_render_note(note,dur_s,song['cw'],cvol,
                            0.70+rng.random()*0.20 if note is not REST else 0.7)
            _mix_into(cnt_buf,nb,arr_pos); arr_pos+=len(nb); beat_pos+=dur_beats
    cnt_buf=_lowpass(cnt_buf,0.28)
    _mix_into(out,cnt_buf,0)

    return bytes(out)


def _apply_motif_raw(ivs, durs, start_note, ctones, stones, bpm, meter,
                     lo, hi, kind, vol, rng, chromatic_ok):
    """Inner motif realiser that returns (note, dur_s, velocity) list."""
    beat_s=60.0/bpm; cur=start_note; notes=[]
    beat_pos=0.0
    # Compute how many beats the motif covers vs bar length
    motif_beats=sum(abs(d) for d in durs)
    bar_beats=float(meter)
    # If motif is shorter than a bar, repeat to fill; if longer, truncate
    full_ivs=[]; full_durs=[]
    b=0.0
    reps=0
    while b<bar_beats-0.01 and reps<4:
        for iv,dur in zip(ivs,durs):
            if b+abs(dur)>bar_beats+0.01: break
            full_ivs.append(iv); full_durs.append(dur); b+=abs(dur)
        reps+=1
    # Pad remaining with a rest if needed
    remaining=bar_beats-b
    if remaining>0.05: full_durs.append(-remaining); full_ivs.append(0)

    for iv,dur in zip(full_ivs,full_durs):
        is_rest=dur<0; dur_s=abs(dur)*beat_s
        if is_rest:
            notes.append((REST,dur_s,0.8))
        else:
            raw=max(lo,min(hi,cur+iv))
            bw=_beat_weight(beat_pos,meter)
            if bw>=0.7:   pool=ctones or stones
            elif bw>=0.5: pool=ctones+[n for n in stones if n not in ctones]
            else:         pool=stones if stones else ctones
            note=_nearest(pool,raw) if pool else raw
            if chromatic_ok and bw<0.45 and rng.random()<0.25:
                note=max(lo,min(hi,raw))
            if abs(note-cur)>9 and pool:
                note=_stepwise(pool,cur,rng,0.80)
            cur=note
            vel=0.72+bw*0.28+rng.random()*0.05
            notes.append((note,dur_s,vel))
        beat_pos+=abs(dur)
    return notes


# ── Sound cache & playback ────────────────────────────────────────────────────
_snd_cache={}; _sfx_cache={}; _cur_song=None; CH_MUSIC=0

def _get_song_sound(sk):
    if sk in _snd_cache: return _snd_cache[sk]
    if not _inited: return None
    snd=pygame.mixer.Sound(buffer=_render_song(sk))
    _snd_cache[sk]=snd; return snd

def play_area_music(map_key,dungeon_id=-1):
    global _cur_song
    if not _inited: return
    sk=DUNGEON_SONG.get(dungeon_id,'dungeon') if dungeon_id>=0 else MAP_TO_SONG.get(map_key,'dungeon')
    if sk==_cur_song: return
    _cur_song=sk; snd=_get_song_sound(sk)
    if snd is None: return
    pygame.mixer.Channel(CH_MUSIC).fadeout(700)
    pygame.mixer.Channel(CH_MUSIC).play(snd,loops=-1,fade_ms=1000)

def stop_music(fade_ms=600):
    if not _inited: return
    pygame.mixer.Channel(CH_MUSIC).fadeout(fade_ms)

def set_music_volume(v):
    if not _inited: return
    pygame.mixer.Channel(CH_MUSIC).set_volume(max(0.0,min(1.0,v)))


# ── SFX ───────────────────────────────────────────────────────────────────────
def _mk_sfx(key):
    SR=SAMPLE_RATE; sv=SFX_BASE*3.5
    def noise(n,vol=sv*0.7):
        r=random.Random(_dh(key,'n')); out=array.array('h')
        for i in range(n):
            e=1.0-i/n
            v=max(-32767,min(32767,int((r.random()*2-1)*e*vol*32767)))
            out.append(v); out.append(v)
        return out
    def sweep(f0,f1,dur,wv='square',vol=sv*0.5):
        n=int(SR*dur); out=array.array('h')
        for i in range(n):
            f=f0+(f1-f0)*(i/n); ph=(f*i/SR)%1.0
            e=max(0.0,1.0-i/n)
            v=max(-32767,min(32767,int(_wave(ph,wv)*e*vol*32767)))
            out.append(v); out.append(v)
        return out
    def beep(f,dur,wv='square',vol=sv*0.5):
        nm=int(round(69+12*math.log2(f/440)))
        return _render_note(nm,dur,wv,vol)
    def cat(*bufs):
        out=array.array('h')
        for b in bufs: out.extend(b)
        return out
    sfx={
        'hit_melee':    lambda:cat(noise(int(SR*.03)),sweep(200,80,.07,'square')),
        'hit_ranged':   lambda:sweep(600,200,.08,'triangle'),
        'spell_cast':   lambda:cat(sweep(300,1200,.12,'sine',sv*.30),sweep(1200,400,.10,'triangle',sv*.25)),
        'area_blast':   lambda:cat(noise(int(SR*.06),sv),sweep(300,60,.25,'sawtooth',sv*.60)),
        'player_hurt':  lambda:cat(noise(int(SR*.04),sv*.7),sweep(400,150,.08,'square',sv*.40)),
        'player_dead':  lambda:cat(sweep(440,110,.25,'square',sv*.50),sweep(110,55,.30,'sawtooth',sv*.45)),
        'gate_travel':  lambda:cat(sweep(200,1600,.15,'triangle',sv*.45),noise(int(SR*.04),sv*.40),sweep(1600,300,.15,'triangle',sv*.40)),
        'chest_open':   lambda:cat(sweep(440,880,.08,'square',sv*.35),sweep(880,1320,.08,'triangle',sv*.30)),
        'chest_smash':  lambda:cat(noise(int(SR*.05),sv*.9),sweep(300,100,.10,'sawtooth',sv*.45)),
        'shrine':       lambda:cat(beep(523,.10,'triangle',sv*.35),beep(659,.10,'triangle',sv*.35),beep(784,.10,'triangle',sv*.35),beep(1046,.20,'sine',sv*.35)),
        'pickup':       lambda:cat(sweep(660,880,.05,'square',sv*.30),sweep(880,1100,.05,'triangle',sv*.25)),
        'stairs_down':  lambda:sweep(440,220,.20,'square',sv*.35),
        'stairs_up':    lambda:sweep(220,440,.20,'triangle',sv*.35),
        'berserk':      lambda:cat(sweep(200,1600,.10,'sawtooth',sv*.55),sweep(1600,200,.08,'sawtooth',sv*.50)),
        'mimic_reveal': lambda:cat(noise(int(SR*.04),sv),sweep(600,200,.12,'sawtooth',sv*.55),sweep(200,1000,.10,'square',sv*.50)),
        'slime_atk':    lambda:sweep(120,60,.12,'sine',sv*.35),
        'bat_atk':      lambda:sweep(900,600,.08,'triangle',sv*.30),
        'spider_atk':   lambda:cat(noise(int(SR*.025),sv*.5),sweep(400,200,.06,'square',sv*.35)),
        'goblin_atk':   lambda:sweep(300,150,.10,'sawtooth',sv*.38),
        'skeleton_atk': lambda:cat(noise(int(SR*.02),sv*.5),sweep(250,180,.07,'square',sv*.35)),
        'ghost_atk':    lambda:sweep(800,300,.15,'sine',sv*.28),
        'troll_atk':    lambda:cat(noise(int(SR*.05),sv*.8),sweep(150,60,.12,'square',sv*.45)),
        'yeti_atk':     lambda:cat(noise(int(SR*.04),sv*.7),sweep(200,80,.12,'square',sv*.45)),
        'dragon_atk':   lambda:cat(sweep(100,800,.08,'sawtooth',sv*.60),noise(int(SR*.06),sv*.90),sweep(800,100,.12,'sawtooth',sv*.55)),
    }
    fn=sfx.get(key); return fn() if fn else noise(int(SR*.05))

def _get_sfx(key):
    if not _inited: return None
    if key not in _sfx_cache:
        _sfx_cache[key]=pygame.mixer.Sound(buffer=bytes(_mk_sfx(key)))
    return _sfx_cache[key]

def play_sfx(key,volume=1.0):
    if not _inited: return
    snd=_get_sfx(key)
    if snd is None: return
    ch=pygame.mixer.find_channel(True)
    if ch: ch.set_volume(min(1.0,volume)); ch.play(snd)

ENEMY_ATTACK_SFX={
    'slime':'slime_atk','bat':'bat_atk','spider':'spider_atk','giant_spider':'spider_atk',
    'goblin':'goblin_atk','skeleton':'skeleton_atk','ghost':'ghost_atk','troll':'troll_atk',
    'yeti':'yeti_atk','ice_wraith':'ghost_atk','scorpion':'spider_atk','mummy':'skeleton_atk',
    'swamp_toad':'slime_atk','will_o':'ghost_atk','mimic':'mimic_reveal',
    'dragon':'dragon_atk','frost_dragon':'dragon_atk','sand_dragon':'dragon_atk','swamp_dragon':'dragon_atk',
    'wolf':'goblin_atk',
}

def preload_all():
    if not _inited: return
    for sk in SONGS: _get_song_sound(sk)
    for k in (['hit_melee','hit_ranged','spell_cast','area_blast','player_hurt','player_dead',
                'gate_travel','chest_open','chest_smash','shrine','pickup','stairs_down',
                'stairs_up','berserk','mimic_reveal']+list(set(ENEMY_ATTACK_SFX.values()))):
        _get_sfx(k)
