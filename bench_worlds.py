#!/usr/bin/env python3
"""Headless performance probe for the worlds. Run:

    python3 bench_worlds.py

Loads each world in the gz server (no GUI), times startup, and reports the
steady-state real-time factor (how much faster than wall-clock the physics
runs - higher is better, >1 means real time to spare). Render FPS still needs a
live GUI run; this measures load + physics, the parts we can see headless.
"""
import os, re, subprocess, time, glob

ROOT = os.path.dirname(os.path.abspath(__file__))
WORLDS = sorted(glob.glob(os.path.join(ROOT, "custom_worlds", "*.sdf")))
ENV = dict(os.environ, GZ_SIM_RESOURCE_PATH=os.path.join(ROOT, "custom_models") + ":" + os.environ.get("GZ_SIM_RESOURCE_PATH", ""))

def bench(world, iters=2000):
    t0 = time.time()
    r = subprocess.run(["gz", "sim", "-s", "-r", "--iterations", str(iters), world, "-v", "1"],
                       capture_output=True, text=True, env=ENV, timeout=180)
    wall = time.time() - t0
    out = r.stdout + r.stderr
    probs = len(re.findall(r"(?i)\b(error|unable|could not|cannot|failed|missing)\b", out))
    rtf = re.findall(r"[Rr]eal[- ]time factor[:\s]+([\d.]+)", out)
    return wall, probs, (rtf[-1] if rtf else "n/a")

if __name__ == "__main__":
    print(f"{'world':<14}{'load+2k steps':<16}{'problems':<10}{'RTF'}")
    for w in WORLDS:
        wall, probs, rtf = bench(w)
        name = os.path.basename(w).replace(".sdf", "")
        flag = "" if probs == 0 else "  <-- CHECK"
        print(f"{name:<14}{wall:>8.1f}s        {probs:<10}{rtf}{flag}")
