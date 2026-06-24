#!/usr/bin/env python3
"""Generate custom_worlds/row_crops.sdf: a mixed vegetable field on soil_terrain.

Separate beds of different crops (chard / zucchini / artichoke), each spaced to
its plant size, with a centre dirt path. Edit BEDS and re-run; z is then fixed by
place_on_terrain.py (this writes z=0 placeholders).

ponytail: plant count is the perf knob. Each bed is (model, x0, x1, row_step,
plant_step). Widen the steps or drop a bed for a weaker GPU.
"""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "custom_worlds", "row_crops.sdf")
Y0, Y1 = -6.0, 6.0
BALES = [(-11, 7, 0.5), (11, -7, 1.2)]

# (crop model, x_start, x_end, row spacing, in-row spacing)
BEDS = [
    ("crop_chard",     -9.0, -6.0, 0.75, 0.6),   # leafy low rows (dense)
    ("crop_zucchini",  -4.5, -1.5, 1.5,  1.5),   # sprawling, wider spacing
    # centre dirt path runs through x in (-1.5, 1.5)
    ("crop_artichoke",  1.5,  4.5, 1.5,  1.6),   # tall bushy
    ("crop_chard",      5.5,  9.0, 0.75, 0.6),
]

HEAD = """<?xml version="1.0" ?>
<sdf version="1.9">
  <world name="row_crops">
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
      <uri>model://soil_terrain</uri>
    </include>
"""

def frange(a, b, step):
    out, v = [], a
    while v <= b + 1e-9:
        out.append(round(v, 2)); v += step
    return out

def main():
    parts = [HEAD, "\n    <!-- Mixed vegetable beds (chard / zucchini / artichoke), centre dirt path. z via place_on_terrain.py -->\n"]
    i = 0
    for model, x0, x1, rstep, pstep in BEDS:
        for x in frange(x0, x1, rstep):
            for y in frange(Y0, Y1, pstep):
                yaw = (i * 0.7) % 6.28
                parts.append(f'    <include><name>{model}_{i}</name><uri>model://{model}</uri>'
                             f'<pose>{x} {y} 0 0 0 {yaw:.2f}</pose></include>\n')
                i += 1
    parts.append("\n    <!-- hay bales at the edge -->\n")
    for j, (x, y, yaw) in enumerate(BALES):
        parts.append(f'    <include><name>hay_bale_{j}</name><uri>model://hay_bale</uri>'
                     f'<pose>{x} {y} 0 0 0 {yaw}</pose></include>\n')
    parts.append("  </world>\n</sdf>\n")
    open(OUT, "w").write("".join(parts))
    print(f"wrote {OUT}: {i} plants across {len(BEDS)} beds, {len(BALES)} bales")

if __name__ == "__main__":
    main()
