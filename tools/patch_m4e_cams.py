#!/usr/bin/env python3
"""Set the m4e camera resolution + frame rate from the launcher preset.

    python3 patch_m4e_cams.py <width> <height> <hz> [model.sdf]

Only the three <sensor type="camera"> blocks are touched (width/height/update_rate)
- the IMU/magnetometer/navsat/lidar update rates are left alone. Quality tiers are
driven by the launcher (potato 640x480@15, mild 960x720@30, full 1280x960@60).
Idempotent: re-running with the same values is a no-op.
"""
import re, sys, os

def patch(path, w, h, hz):
    s = open(path).read()

    def fix(m):
        blk = m.group(0)
        blk = re.sub(r"<width>\d+</width>", f"<width>{w}</width>", blk)
        blk = re.sub(r"<height>\d+</height>", f"<height>{h}</height>", blk)
        blk = re.sub(r"<update_rate>\d+</update_rate>", f"<update_rate>{hz}</update_rate>", blk)
        return blk

    new = re.sub(r'<sensor[^>]*type="camera">.*?</sensor>', fix, s, flags=re.S)
    n = len(re.findall(r'<sensor[^>]*type="camera">', s))
    open(path, "w").write(new)
    return n

if __name__ == "__main__":
    w, h, hz = sys.argv[1], sys.argv[2], sys.argv[3]
    path = sys.argv[4] if len(sys.argv) > 4 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "custom_models", "m4e", "model.sdf")
    n = patch(path, w, h, hz)
    print(f"patched {n} m4e camera(s) -> {w}x{h}@{hz}Hz")
    # self-check: IMU rate (250) must be untouched, cameras must be hz
    s = open(path).read()
    assert "<update_rate>250</update_rate>" in s, "IMU update_rate got clobbered!"
    assert s.count(f"<update_rate>{hz}</update_rate>") >= n, "camera rate not applied"
