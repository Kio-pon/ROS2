#!/usr/bin/env python3
"""Generate custom_worlds/forest.sdf: a forest with spruce and fir trees.

Creates a forest scene on forest_terrain.
Supports density levels: sparse, medium, dense.
"""
import os, sys, argparse, random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import place_on_terrain as pot

# Resolve the output directory: works whether the script lives in the repo root
# (native) or in ~/launchers/ (Docker) — custom_worlds is always one level up
# from launchers/ or alongside the script in the repo root.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_SCRIPT_DIR)
ROOT = _PARENT_DIR if os.path.isdir(os.path.join(_PARENT_DIR, "custom_worlds")) else _SCRIPT_DIR
OUT = os.path.join(ROOT, "custom_worlds", "forest.sdf")

# Grid dimensions for tree placement: (cells_x, cells_y)
GRID_CONFIG = {
    "sparse": (4, 4),   # 16 potential trees
    "medium": (6, 6),   # 36 potential trees
    "dense": (9, 9),    # 81 potential trees
}

HEAD = """<?xml version="1.0" ?>
<sdf version="1.9">
  <world name="forest">
    <physics type="ode">
      <max_step_size>0.004</max_step_size>
      <real_time_factor>1.0</real_time_factor>
      <real_time_update_rate>250</real_time_update_rate>
      <ode>
        <solver>
          <type>quick</type>
          <iters>16</iters>
          <sor>1.3</sor>
        </solver>
      </ode>
    </physics>
    <spherical_coordinates>
      <surface_model>EARTH_WGS84</surface_model>
      <world_frame_orientation>ENU</world_frame_orientation>
      <latitude_deg>47.397971</latitude_deg>
      <longitude_deg>8.546164</longitude_deg>
      <elevation>0</elevation>
    </spherical_coordinates>
    <light type="directional" name="sun">
      <cast_shadows>false</cast_shadows>
      <pose>0 0 100 0 0 0</pose>
      <diffuse>1 1 1 1</diffuse>
      <specular>0.4 0.4 0.4 1</specular>
      <direction>-0.4 0.3 -0.9</direction>
    </light>
    <include>
      <uri>model://forest_terrain</uri>
    </include>
"""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--density", choices=["sparse", "medium", "dense"], default="medium")
    args = parser.parse_args()

    # Deterministic placement
    random.seed(12345)

    nx, ny = GRID_CONFIG[args.density]
    
    # Area to distribute trees: -30 to 30 in both x and y
    min_x, max_x = -30.0, 30.0
    min_y, max_y = -30.0, 30.0
    
    step_x = (max_x - min_x) / nx
    step_y = (max_y - min_y) / ny

    parts = [HEAD, f"\n    <!-- Forest: {args.density} density -->\n"]
    
    i = 0
    for ix in range(nx):
        for iy in range(ny):
            # Calculate base coordinate of the cell center
            cx = min_x + (ix + 0.5) * step_x
            cy = min_y + (iy + 0.5) * step_y
            
            # Skip the center cell slightly to ensure the drone doesn't spawn exactly inside a trunk
            if abs(cx) < 3.0 and abs(cy) < 3.0:
                continue
                
            # Add some jitter to make it look natural
            jx = random.uniform(-step_x * 0.35, step_x * 0.35)
            jy = random.uniform(-step_y * 0.35, step_y * 0.35)
            
            x = round(cx + jx, 3)
            y = round(cy + jy, 3)
            yaw = round(random.uniform(0, 6.28), 2)
            
            # Alternate tree types
            tree_type = "spruce_tree" if (i % 5 < 3) else "fir_tree"
            
            parts.append(f'    <include><name>{tree_type}_{i}</name><uri>model://{tree_type}</uri>'
                         f'<pose>{x} {y} 0 0 0 {yaw}</pose></include>\n')
            i += 1
            
    parts.append("  </world>\n</sdf>\n")
    
    open(OUT, "w").write("".join(parts))
    print(f"wrote {OUT}: {i} trees, density={args.density}")
    pot.snap(OUT)

if __name__ == "__main__":
    main()
