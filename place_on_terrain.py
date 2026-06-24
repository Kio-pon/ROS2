#!/usr/bin/env python3
"""Snap every <include>d model in a world file onto the heightmap terrain.

Reads the world's terrain model (the include whose uri contains "terrain"),
loads its heightmap PNG + <size>, then rewrites the z of every other model's
<pose> to the terrain height at that x,y. Run after editing tree/crop layout:

    python3 place_on_terrain.py custom_worlds/forest.sdf

ponytail: nearest-pixel sampling, no bilinear. Fine on smooth terrain; switch
to bilinear if models visibly step on steep gradients.
"""
import re, sys, os
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(ROOT, "custom_models")

# Drone spawn clearance: body origin this far above the ground at the world
# origin, so the x500 sits a few cm over its landing gear instead of being
# dropped from 5 m. ~0.25 m -> legs ~7 cm above ground, then it settles gently.
SPAWN_CLEARANCE = 0.25

def model_name(uri):  # model://forest_terrain/foo.png -> forest_terrain
    return uri.replace("model://", "").split("/")[0]

def make_sampler(png, sx, sy, maxh, pz):
    im = Image.open(png).convert("L")
    W, H = im.size
    px = im.load()
    def height(x, y):
        u = min(max((x + sx / 2) / sx, 0.0), 1.0)
        v = min(max((y + sy / 2) / sy, 0.0), 1.0)
        col = round(u * (W - 1))
        row = round((1 - v) * (H - 1))  # image row 0 = top = +y in world
        return px[col, row] / 255.0 * maxh + pz
    return height

def load_terrain(world_text):
    for blk in re.findall(r"<include>(.*?)</include>", world_text, re.S):
        uri = re.search(r"<uri>\s*(.*?)\s*</uri>", blk)
        if uri and "terrain" in uri.group(1):
            tdir = os.path.join(MODELS, model_name(uri.group(1)))
            sdf = open(os.path.join(tdir, "model.sdf")).read()
            png = re.search(r"<uri>\s*(model://[^<]+\.png)\s*</uri>", sdf).group(1)
            sx, sy, mh = map(float, re.search(r"<size>\s*([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s*</size>", sdf).groups())
            pz = float(re.search(r"<pos>[\d.eE+-]+\s+[\d.eE+-]+\s+([\d.eE+-]+)</pos>", sdf).group(1))
            return make_sampler(os.path.join(MODELS, model_name(png), png.split("/")[-1]), sx, sy, mh, pz)
    raise SystemExit("no terrain include found in world")

def snap(world_path):
    text = open(world_path).read()
    height = load_terrain(text)

    def fix(m):
        blk = m.group(1)
        uri = re.search(r"<uri>\s*(.*?)\s*</uri>", blk)
        if not uri or "terrain" in uri.group(1):
            return m.group(0)
        def repose(p):
            nums = p.group(1).split()
            if len(nums) != 6:
                return p.group(0)
            x, y = float(nums[0]), float(nums[1])
            nums[2] = f"{height(x, y):.3f}"
            return f"<pose>{' '.join(nums)}</pose>"
        blk = re.sub(r"<pose>\s*(.*?)\s*</pose>", repose, blk, flags=re.S)
        return f"<include>{blk}</include>"

    out = re.sub(r"<include>(.*?)</include>", fix, text, flags=re.S)
    open(world_path, "w").write(out)
    print(f"snapped models in {world_path}")

def spawn_z(world_path):
    """Print the drone spawn height for a world: terrain height at the origin
    (0,0) plus SPAWN_CLEARANCE. Falls back to flat-ground clearance if the world
    has no heightmap terrain. Used by run_all.sh to set PX4_GZ_MODEL_POSE."""
    text = open(world_path).read()
    try:
        height = load_terrain(text)
        z = height(0.0, 0.0) + SPAWN_CLEARANCE
    except SystemExit:
        z = SPAWN_CLEARANCE  # flat ground / no terrain include
    print(f"{z:.3f}")


if __name__ == "__main__":
    # self-check: forest origin pixel (175/255*8) ~= 5.49 m
    if "--selfcheck" in sys.argv:
        h = make_sampler(os.path.join(MODELS, "forest_terrain", "bc_terrain_heightmap_257.png"), 200, 200, 8, 0)
        assert abs(h(0, 0) - 5.49) < 0.2, h(0, 0)
        print("ok", h(0, 0))
    elif "--spawn-z" in sys.argv:
        spawn_z(sys.argv[sys.argv.index("--spawn-z") + 1])
    else:
        snap(sys.argv[1])
