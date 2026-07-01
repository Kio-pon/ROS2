#!/usr/bin/env python3
"""Generate custom_worlds/wheat_field.sdf: Pakistani farmland with wheat patches.

Creates a realistic farmland scene with:
- Green grass terrain (wheat_terrain)
- Wheat patches in a grid layout (density: sparse/medium/dense)
- Irrigation canal/river along one edge
- Barn in the distance
- Blue sky

Usage:
    python3 gen_wheat_field.py                  # default (medium density)
    python3 gen_wheat_field.py --density sparse
    python3 gen_wheat_field.py --density dense
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import place_on_terrain as pot

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_SCRIPT_DIR)
ROOT = _PARENT_DIR if os.path.isdir(os.path.join(_PARENT_DIR, "custom_worlds")) else _SCRIPT_DIR
OUT = os.path.join(ROOT, "custom_worlds", "wheat_field.sdf")

# Density presets: (patch_rows, patch_cols, plants_per_row, plants_per_col)
DENSITY = {
    "sparse": (2, 1, 10, 10),    # 1 block of 200 plants
    "medium": (3, 2, 10, 10),    # 6 blocks = 600 plants
    "dense":  (4, 2, 10, 10),    # 8 blocks = 800 plants
}

PLANT_SPACING = 0.1    # m between plants within a patch
PATCH_SPACING = 0.2    # m gap between patches (user requested 0.2m)

# Scenery positions
RIVER_POSE = "0 -12 0.5 0 0 0"         # canal along the south side
BARN_POSE  = "-45 30 0.5 0 0 0.3"      # barn far to the northwest
HAY_BALES = [
    (15, -8, 0.6),
    (-12, 10, 2.1),
    (20, 15, 4.3),
]

HEAD = """<?xml version="1.0" ?>
<sdf version="1.9">
  <world name="wheat_field">
    <physics type="ode">
      <max_step_size>0.004</max_step_size>
      <real_time_factor>1.0</real_time_factor>
      <real_time_update_rate>250</real_time_update_rate>
      <ode><solver><type>quick</type><iters>16</iters><sor>1.3</sor></solver></ode>
    </physics>
    <spherical_coordinates>
      <surface_model>EARTH_WGS84</surface_model>
      <world_frame_orientation>ENU</world_frame_orientation>
      <latitude_deg>47.397971</latitude_deg>
      <longitude_deg>8.546164</longitude_deg>
      <elevation>0</elevation>
    </spherical_coordinates>

    <!-- Blue sky -->
    <scene>
      <ambient>0.6 0.6 0.65 1</ambient>
      <background>0.4 0.65 0.9 1</background>
      <sky>
        <clouds><speed>3</speed></clouds>
      </sky>
    </scene>

    <light type="directional" name="sun">
      <cast_shadows>false</cast_shadows>
      <pose>0 0 100 0 0 0</pose>
      <diffuse>1 1 0.95 1</diffuse>
      <specular>0.4 0.4 0.35 1</specular>
      <direction>-0.4 0.3 -0.9</direction>
    </light>

    <!-- Green grass terrain -->
    <include>
      <uri>model://wheat_terrain</uri>
    </include>

    <!-- Irrigation canal / river -->
    <include>
      <name>river</name>
      <uri>model://river</uri>
      <pose>{river_pose}</pose>
    </include>

    <!-- Distant barn -->
    <include>
      <name>barn</name>
      <uri>model://barn</uri>
      <pose>{barn_pose}</pose>
    </include>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--density", choices=["sparse", "medium", "dense"], default="medium")
    args = parser.parse_args()

    patch_rows, patch_cols, pr_size, pc_size = DENSITY[args.density]

    patch_stride_x = (pr_size - 1) * PLANT_SPACING + PATCH_SPACING
    patch_stride_y = (pc_size - 1) * PLANT_SPACING + PATCH_SPACING

    total_x = (patch_rows - 1) * patch_stride_x + (pr_size - 1) * PLANT_SPACING
    total_y = (patch_cols - 1) * patch_stride_y + (pc_size - 1) * PLANT_SPACING

    x0 = -total_x / 2
    y0 = -total_y / 2

    head = HEAD.format(river_pose=RIVER_POSE, barn_pose=BARN_POSE)
    parts = [head]

    # Hay bales
    parts.append("\n    <!-- Hay bales scattered around -->\n")
    for j, (bx, by, byaw) in enumerate(HAY_BALES):
        parts.append(f'    <include><name>hay_bale_{j}</name><uri>model://hay_bale</uri>'
                     f'<pose>{bx} {by} 0 0 0 {byaw}</pose></include>\n')

    parts.append(f"\n    <!-- Wheat field: {args.density} density ({patch_rows}x{patch_cols} patches) -->\n")
    i = 0
    for pr in range(patch_rows):
        for pc in range(patch_cols):
            patch_x0 = x0 + pr * patch_stride_x
            patch_y0 = y0 + pc * patch_stride_y

            for r in range(pr_size):
                for c in range(pc_size):
                    x = round(patch_x0 + r * PLANT_SPACING, 3)
                    y = round(patch_y0 + c * PLANT_SPACING, 3)
                    yaw = (i * 1.7) % 6.28
                    parts.append(f'    <include><name>wheat_{i}</name><uri>model://wheat_plant</uri>'
                                 f'<pose>{x} {y} 0 0 0 {yaw:.2f}</pose></include>\n')
                    i += 1

    parts.append("  </world>\n</sdf>\n")
    open(OUT, "w").write("".join(parts))
    total_tris = i * 48  # 48 tris per low-poly plant
    print(f"wrote {OUT}: {i} wheat plants (~{total_tris/1e3:.0f}K tris), density={args.density}")
    pot.snap(OUT)


if __name__ == "__main__":
    main()
