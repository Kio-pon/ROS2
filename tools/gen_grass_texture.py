#!/usr/bin/env python3
"""Generate a tileable green grass diffuse (+ flat normal) for farmland_terrain.

The farmland ground used to reuse forest_terrain's mossy-rock texture, which read
as grey rock, not a field. This writes a seamless grass-green texture so the
farmland looks like a proper green grass field. Re-run to regenerate:

    python3 tools/gen_grass_texture.py

ponytail: procedural noise, no external asset. Tweak BASE/SPECKLE for a
different green, SIZE for resolution. Seamless via wrap-around value noise.
"""
import os, math, random

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "custom_models", "farmland_terrain")
SIZE = 512

# Grass palette: a few greens blended by smooth noise + fine blade speckle.
GREENS = [(86, 125, 51), (74, 110, 44), (102, 140, 62), (64, 96, 40), (120, 150, 70)]


def _smooth_noise(n, cells, seed):
    """Seamless value-noise grid sampled to n x n, values in [0,1]."""
    rng = random.Random(seed)
    g = [[rng.random() for _ in range(cells)] for _ in range(cells)]

    def smooth(t):  # smoothstep
        return t * t * (3 - 2 * t)

    out = [[0.0] * n for _ in range(n)]
    for y in range(n):
        fy = y / n * cells
        y0 = int(fy) % cells
        y1 = (y0 + 1) % cells
        ty = smooth(fy - int(fy))
        for x in range(n):
            fx = x / n * cells
            x0 = int(fx) % cells
            x1 = (x0 + 1) % cells
            tx = smooth(fx - int(fx))
            top = g[y0][x0] * (1 - tx) + g[y0][x1] * tx
            bot = g[y1][x0] * (1 - tx) + g[y1][x1] * tx
            out[y][x] = top * (1 - ty) + bot * ty
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    # Two octaves of seamless noise pick which green; fine speckle adds blades.
    coarse = _smooth_noise(SIZE, 8, seed=1)
    fine = _smooth_noise(SIZE, 32, seed=2)
    rng = random.Random(7)

    img = Image.new("RGB", (SIZE, SIZE))
    px = img.load()
    for y in range(SIZE):
        for x in range(SIZE):
            t = 0.7 * coarse[y][x] + 0.3 * fine[y][x]
            idx = min(int(t * len(GREENS)), len(GREENS) - 1)
            r, g, b = GREENS[idx]
            jitter = rng.randint(-12, 12)  # per-pixel blade speckle
            px[x, y] = (max(0, min(255, r + jitter)),
                        max(0, min(255, g + jitter)),
                        max(0, min(255, b + jitter // 2)))
    img.save(os.path.join(OUT_DIR, "grass_diffuse.png"))

    # Flat normal map (no fake bumps -> grass, not rock).
    flat = Image.new("RGB", (SIZE, SIZE), (128, 128, 255))
    flat.save(os.path.join(OUT_DIR, "grass_normal.png"))
    print(f"wrote grass_diffuse.png + grass_normal.png ({SIZE}x{SIZE}) to {OUT_DIR}")


if __name__ == "__main__":
    main()
