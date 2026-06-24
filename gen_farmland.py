#!/usr/bin/env python3
"""Generate custom_worlds/farmland.sdf: a tomato field on farmland_terrain.

Edit the grid constants and re-run, then z gets fixed by place_on_terrain.py
(this script writes z=0 placeholders). Kept separate from the world file so the
layout is regenerable instead of hand-edited.
"""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "custom_worlds", "farmland.sdf")

ROWS_X = [-7.5, -4.5, -1.5, 1.5, 4.5, 7.5]   # crop rows (m), 3 m apart
PLANTS_Y = range(-8, 9, 2)                     # plant spacing down each row
BALES = [(-25, 25, 0.6), (22, -20, 1.9), (30, 18, 0.2), (-28, -16, 2.7)]

HEAD = """<?xml version="1.0" ?>
<sdf version="1.9">
  <world name="farmland">
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
      <uri>model://farmland_terrain</uri>
    </include>
"""

def main():
    lines = [HEAD, "\n    <!-- Tomato field: rows of crop_tomato plants. z set by place_on_terrain.py -->\n"]
    i = 0
    for x in ROWS_X:
        for y in PLANTS_Y:
            yaw = (i * 1.3) % 6.28  # vary heading so plants don't look cloned
            lines.append(f'    <include><name>tomato_{i}</name><uri>model://crop_tomato</uri>'
                         f'<pose>{x} {y} 0 0 0 {yaw:.2f}</pose></include>\n')
            i += 1
    lines.append("\n    <!-- Hay bales around the field edges -->\n")
    for j, (x, y, yaw) in enumerate(BALES):
        lines.append(f'    <include><name>hay_bale_{j}</name><uri>model://hay_bale</uri>'
                     f'<pose>{x} {y} 0 0 0 {yaw}</pose></include>\n')
    lines.append("  </world>\n</sdf>\n")
    open(OUT, "w").write("".join(lines))
    print(f"wrote {OUT}: {i} tomato plants, {len(BALES)} bales")

if __name__ == "__main__":
    main()
