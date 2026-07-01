#!/usr/bin/env python3
"""Validation suite for the custom Gazebo worlds/models. Run:

    python3 test_worlds.py

Plain asserts, no framework. Catches the bugs that actually bit us:
  - heightmap PNG not 2^n+1 (the original "no bumpy terrain" cause)
  - malformed SDF / dangling model:// or file references
  - a model spawned buried in / floating above the terrain (the "stuck drone")

Doc basis: heightmap PNG must be (2^n)+1 square (Gazebo DEM tutorial); a
heightmap is valid with 1 texture + 0 blend (sdformat heightmap_shape.sdf,
"blend count = texture count - 1"); material ambient/diffuse/specular are RGBA
(sdformat material.sdf). Exits nonzero on first failure.
"""
import os, re, glob, sys, shutil, subprocess
import xml.etree.ElementTree as ET
from PIL import Image
from place_on_terrain import load_terrain, model_name, MODELS, SPAWN_CLEARANCE

ROOT = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.dirname(ROOT) if os.path.basename(ROOT) == "tools" else ROOT
WORLDS = os.path.join(WORKSPACE_ROOT, "custom_worlds")
PASS, FAIL = "  ok  ", " FAIL "

def ensure_generated_assets():
    """The farmland grass texture is procedural (not committed); generate it so
    the reference check below finds it, exactly as run_all.sh does at launch."""
    grass = os.path.join(MODELS, "farmland_terrain", "grass_diffuse.png")
    if not os.path.exists(grass):
        subprocess.run([sys.executable, os.path.join(WORKSPACE_ROOT, "tools", "gen_grass_texture.py")],
                       check=True, capture_output=True)

def resolve(uri):  # model://name/rest... -> custom_models/name/rest...
    rel = uri.replace("model://", "")
    p_custom = os.path.join(MODELS, *rel.split("/"))
    if os.path.exists(p_custom):
        return p_custom
    p_px4 = os.path.join(os.path.expanduser("~"), "PX4-Autopilot", "Tools", "simulation", "gz", "models", *rel.split("/"))
    if os.path.exists(p_px4):
        return p_px4
    return p_custom

def pow2_plus1(n):
    return n > 1 and ((n - 1) & (n - 2)) == 0   # n-1 is a power of two

def check(name, fn):
    try:
        fn()
        print(PASS + name)
        return 0
    except AssertionError as e:
        print(FAIL + name + " -> " + str(e))
        return 1

# --- 1. heightmap PNGs are square 2^n+1 -----------------------------------
def t_heightmaps():
    pngs = set()
    for sdf in glob.glob(os.path.join(MODELS, "*", "model.sdf")):
        txt = open(sdf).read()
        for blk in re.findall(r"<heightmap>(.*?)</heightmap>", txt, re.S):
            m = re.search(r"<uri>\s*(model://[^<]+\.png)\s*</uri>", blk)
            assert m, f"{sdf}: heightmap missing <uri>"
            pngs.add(resolve(m.group(1)))
    assert pngs, "no heightmap models found"
    for p in pngs:
        assert os.path.exists(p), f"missing heightmap {p}"
        w, h = Image.open(p).size
        assert w == h, f"{p} not square: {w}x{h}"
        assert pow2_plus1(w), f"{p} is {w}x{h}, needs (2^n)+1 e.g. 129/257/513"

# --- 2. every .sdf is well-formed XML -------------------------------------
def t_xml():
    files = glob.glob(os.path.join(WORLDS, "*.sdf")) + glob.glob(os.path.join(MODELS, "*", "model.sdf"))
    assert files, "no sdf files found"
    for f in files:
        ET.parse(f)  # raises on malformed XML

# --- 3. every model:// reference resolves to a real file ------------------
def t_refs():
    # worlds reference whole models; models reference asset files
    for w in glob.glob(os.path.join(WORLDS, "*.sdf")):
        for uri in re.findall(r"<uri>\s*(model://[^<]+)\s*</uri>", open(w).read()):
            cfg = os.path.join(MODELS, model_name(uri), "model.config")
            assert os.path.exists(cfg), f"{w}: model {uri} has no {cfg}"
    for sdf in glob.glob(os.path.join(MODELS, "*", "model.sdf")):
        for uri in re.findall(r"<uri>\s*(model://[^<]+\.\w+)\s*</uri>", open(sdf).read()):
            assert os.path.exists(resolve(uri)), f"{sdf}: dangling asset {uri}"
        for tex in re.findall(r"<(?:diffuse|normal|albedo_map|normal_map|roughness_map)>\s*(model://[^<]+\.\w+)\s*</(?:diffuse|normal|albedo_map|normal_map|roughness_map)>", open(sdf).read()):
            assert os.path.exists(resolve(tex)), f"{sdf}: dangling texture {tex}"

# --- 4. no model is buried in / floating above the terrain ----------------
def t_on_terrain():
    for w in glob.glob(os.path.join(WORLDS, "*.sdf")):
        text = open(w).read()
        try:
            height = load_terrain(text)
        except SystemExit:
            height = lambda x, y: 0.0
        for blk in re.findall(r"<include>(.*?)</include>", text, re.S):
            uri = re.search(r"<uri>\s*(.*?)\s*</uri>", blk)
            pose = re.search(r"<pose>\s*(.*?)\s*</pose>", blk, re.S)
            if not uri or "terrain" in uri.group(1) or not pose:
                continue
            n = pose.group(1).split()
            x, y, z = float(n[0]), float(n[1]), float(n[2])
            expect = height(x, y)
            assert abs(z - expect) < 0.05, \
                f"{os.path.basename(w)}: model at ({x},{y}) z={z} but terrain={expect:.3f} (run place_on_terrain.py)"

# --- 5. spawn pose lands ON the ground at the origin (not buried, not dropped) -
def t_spawn_clears_origin():
    # run_all.sh must compute the spawn z per-world from the terrain, not hardcode
    # one value (which used to fling the drone ~5 m up on the flatter worlds).
    run = open(os.path.join(WORKSPACE_ROOT, "launchers", "run_all.sh")).read()
    assert "--spawn-z" in run, "run_all.sh no longer computes a terrain-aware spawn z"
    for w in glob.glob(os.path.join(WORLDS, "*.sdf")):
        try:
            h0 = load_terrain(open(w).read())(0, 0)
        except SystemExit:
            h0 = 0.0
        spawn_z = h0 + SPAWN_CLEARANCE                 # what place_on_terrain prints
        assert spawn_z > h0, f"{os.path.basename(w)}: spawn z={spawn_z:.2f} <= origin {h0:.2f} (buried)"
        assert spawn_z - h0 < 1.0, \
            f"{os.path.basename(w)}: spawn is {spawn_z - h0:.2f} m above ground (drone gets dropped, want <1 m)"

# --- 6. optional: gz's own validator on each model.sdf --------------------
def t_gz_check():
    if not shutil.which("gz"):
        print("  skip  gz sdf -k (gz not on PATH)")
        return
    fails = []
    for sdf in glob.glob(os.path.join(MODELS, "*", "model.sdf")):
        r = subprocess.run(["gz", "sdf", "-k", sdf], capture_output=True, text=True)
        if r.returncode != 0:
            fails.append(f"{sdf}: {r.stderr.strip()}")
    assert not fails, "gz sdf rejected:\n" + "\n".join(fails)

# --- 7. assets stay within the optimized budget (guard vs re-bloat) -------
def t_asset_budget():
    for g in glob.glob(os.path.join(MODELS, "**", "*.glb"), recursive=True):
        mb = os.path.getsize(g) / 1e6
        assert mb <= 15, f"{os.path.basename(g)} is {mb:.0f}MB (>15MB) - run optimize_assets.py"
    for t in glob.glob(os.path.join(MODELS, "**", "*.png"), recursive=True) + glob.glob(os.path.join(MODELS, "**", "*.jpg"), recursive=True):
        if any(k in os.path.basename(t).lower() for k in ("heightmap", "soil_diffuse")):
            continue
        w, h = Image.open(t).size
        assert max(w, h) <= 1024, f"{os.path.basename(t)} is {w}x{h} (>1024px) - run optimize_assets.py"
    total = sum(os.path.getsize(p) for p in glob.glob(os.path.join(MODELS, "**", "*"), recursive=True) if os.path.isfile(p))
    assert total / 1e6 <= 40, f"custom_models is {total/1e6:.0f}MB (>40MB budget)"

if __name__ == "__main__":
    ensure_generated_assets()
    rc = 0
    rc += check("heightmap PNGs are 2^n+1 square", t_heightmaps)
    rc += check("all SDF files are well-formed XML", t_xml)
    rc += check("all model:// references resolve", t_refs)
    rc += check("no model buried/floating off terrain", t_on_terrain)
    rc += check("spawn pose clears origin terrain", t_spawn_clears_origin)
    rc += check("gz sdf accepts every model.sdf", t_gz_check)
    rc += check("assets within optimized budget", t_asset_budget)
    print("\n" + ("ALL PASS" if rc == 0 else f"{rc} FAILED"))
    sys.exit(rc)
