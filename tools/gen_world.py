#!/usr/bin/env python3
"""
Generate a Gazebo world (.sdf) by repeating model includes.

Two layouts, one script:
  - scatter(): random placement  -> forest (trees packed in)
  - rows():    grid placement     -> farmland (crops in straight rows)

The worlds carry NO system <plugin> lines (PX4 injects those via server.config)
and a <spherical_coordinates> block so PX4 gets a GPS home, matching PX4's own
stock worlds.

Usage:
    python gen_world.py forest      # -> custom_worlds/forest.sdf
    python gen_world.py farmland    # -> custom_worlds/farmland.sdf
    python gen_world.py --selfcheck # generate to a string and assert it's valid
"""
from __future__ import annotations
import math, os, random, sys, xml.dom.minidom as minidom

# PX4 default home (Zurich) — keeps EKF/GPS happy.
LAT, LON = 47.397971, 8.546164
HERE = os.path.dirname(os.path.abspath(__file__))
WORLDS = os.path.join(HERE, "..", "custom_worlds")


def scatter(model, n, half, clear=4.0, zmin=0.0, seed=0, scale=None):
    """n models randomly within a [-half, half] square, leaving a clear radius
    around the origin (drone spawn point)."""
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        x = rng.uniform(-half, half)
        y = rng.uniform(-half, half)
        if math.hypot(x, y) < clear:
            continue
        out.append((model, x, y, zmin, rng.uniform(0, 2 * math.pi), scale))
    return out


def rows(model, n_rows, per_row, row_gap, plant_gap, z=0.0, scale=None):
    """Crops on a grid: rows along Y, plants along X. Centered on origin."""
    out = []
    x0 = -(per_row - 1) * plant_gap / 2.0
    y0 = -(n_rows - 1) * row_gap / 2.0
    for r in range(n_rows):
        for p in range(per_row):
            out.append((model, x0 + p * plant_gap, y0 + r * row_gap, z, 0.0, scale))
    return out


def world_sdf(name, ground, placements):
    inc = []
    for i, (model, x, y, z, yaw, scale) in enumerate(placements):
        s = f"\n        <scale>{scale} {scale} {scale}</scale>" if scale else ""
        inc.append(
            f"""    <include>
      <name>{model}_{i}</name>
      <uri>model://{model}</uri>
      <pose>{x:.3f} {y:.3f} {z:.3f} 0 0 {yaw:.3f}</pose>{s}
    </include>"""
        )
    return f"""<?xml version="1.0" ?>
<sdf version="1.9">
  <world name="{name}">
    <!-- no system plugins here: PX4 adds Physics/Sensors/etc via server.config -->
    <spherical_coordinates>
      <surface_model>EARTH_WGS84</surface_model>
      <world_frame_orientation>ENU</world_frame_orientation>
      <latitude_deg>{LAT}</latitude_deg>
      <longitude_deg>{LON}</longitude_deg>
      <elevation>0</elevation>
    </spherical_coordinates>
    <light type="directional" name="sun">
      <cast_shadows>true</cast_shadows>
      <pose>0 0 100 0 0 0</pose>
      <diffuse>1 1 1 1</diffuse>
      <specular>0.4 0.4 0.4 1</specular>
      <direction>-0.4 0.3 -0.9</direction>
    </light>
    <include>
      <uri>model://{ground}</uri>
    </include>
{chr(10).join(inc)}
  </world>
</sdf>
"""


def build_forest():
    trees = (scatter("spruce_tree", 25, half=30, seed=1)
             + scatter("fir_tree", 15, half=30, seed=2))
    return world_sdf("forest", "forest_terrain", trees)


def build_farmland():
    # ponytail: placeholder layout; crop model name wired in Phase 2.
    crops = rows("crop_corn", n_rows=12, per_row=30, row_gap=0.75, plant_gap=0.5)
    return world_sdf("farmland", "forest_terrain", crops)


BUILDERS = {"forest": build_forest, "farmland": build_farmland}


def _write(name, text):
    os.makedirs(WORLDS, exist_ok=True)
    path = os.path.abspath(os.path.join(WORLDS, f"{name}.sdf"))
    with open(path, "w", newline="\n") as f:
        f.write(text)
    return path


def _selfcheck():
    for name, build in BUILDERS.items():
        text = build()
        dom = minidom.parseString(text)  # raises if malformed XML
        n_inc = len(dom.getElementsByTagName("include"))
        assert n_inc >= 2, f"{name}: expected ground + models, got {n_inc} includes"
        assert dom.getElementsByTagName("plugin") == [], f"{name}: must have no <plugin>"
    print("gen_world selfcheck OK")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "--selfcheck"
    if arg == "--selfcheck":
        _selfcheck()
    elif arg in BUILDERS:
        print("wrote", _write(arg, BUILDERS[arg]()))
    else:
        sys.exit(f"usage: gen_world.py [{'|'.join(BUILDERS)}|--selfcheck]")
