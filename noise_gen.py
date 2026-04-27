"""
Rune & Shadow - Noise Generation
Pure-Python 2D Perlin noise (no external dependencies).
"""
import math
import random


def _fade(t: float) -> float:
    """Ken Perlin's smoothstep: 6t^5 - 15t^4 + 10t^3."""
    return t * t * t * (t * (t * 6 - 15) + 10)


def _lerp(a: float, b: float, t: float) -> float:
    return a + t * (b - a)


def _grad2(h: int, x: float, y: float) -> float:
    """Select one of 4 gradient directions."""
    h &= 3
    if h == 0: return  x + y
    if h == 1: return -x + y
    if h == 2: return  x - y
    return             -x - y


class PerlinNoise:
    """Seeded 2-D Perlin noise, output roughly in [-1, 1]."""

    def __init__(self, seed: int = 0):
        rng = random.Random(seed)
        p = list(range(256))
        rng.shuffle(p)
        self._p = p * 2   # doubled to avoid index wrap-around

    def sample(self, x: float, y: float) -> float:
        p  = self._p
        X  = int(math.floor(x)) & 255
        Y  = int(math.floor(y)) & 255
        xf = x - math.floor(x)
        yf = y - math.floor(y)
        u  = _fade(xf)
        v  = _fade(yf)
        A  = p[X]     + Y
        B  = p[X + 1] + Y
        return _lerp(
            _lerp(_grad2(p[A],     xf,     yf),
                  _grad2(p[B],     xf - 1, yf),     u),
            _lerp(_grad2(p[A + 1], xf,     yf - 1),
                  _grad2(p[B + 1], xf - 1, yf - 1), u),
            v
        )


def fbm(noise: PerlinNoise, x: float, y: float,
        octaves: int = 6, persistence: float = 0.5,
        lacunarity: float = 2.0) -> float:
    """
    Fractal Brownian Motion: stack several octaves of Perlin noise.
    Returns a value normalised to roughly [-1, 1].
    """
    value    = 0.0
    amp      = 1.0
    freq     = 1.0
    max_amp  = 0.0
    for _ in range(octaves):
        value   += noise.sample(x * freq, y * freq) * amp
        max_amp += amp
        amp     *= persistence
        freq    *= lacunarity
    return value / max_amp
