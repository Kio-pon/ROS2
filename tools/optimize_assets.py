#!/usr/bin/env python3
"""Shrink oversized model assets without changing geometry. Run:

    python3 optimize_assets.py          # optimize in place, print savings
    python3 optimize_assets.py --check  # verify optimized GLBs still parse

Two jobs:
  1. GLB embedded textures (the tree meshes ship 80+ MB of textures baked into
     the .glb) -> resized to <=MAX_DIM and recompressed. Geometry is untouched:
     triangle count is asserted identical before/after.
  2. Loose textures (.png/.jpg) over MAX_DIM -> downscaled. Heightmaps and the
     procedural soil texture are skipped (size/content matters there).

Pure stdlib + PIL on purpose: the dev box has no blender/meshlab/node, and this
must stay runnable anywhere. Originals remain in git history if you need them.
"""
import json, struct, io, os, sys, glob
from PIL import Image

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.dirname(_SCRIPT_DIR) if os.path.basename(_SCRIPT_DIR) == "tools" else _SCRIPT_DIR
ROOT = os.path.join(_WORKSPACE_ROOT, "custom_models")
MAX_DIM = 512           # cap on any texture's longest edge
JSON_C, BIN_C = 0x4E4F534A, 0x004E4942
SKIP = ("heightmap", "soil_diffuse")   # never resize these loose textures

def _glb_tris(js, bin_bytes=None):
    a = js["accessors"]; t = 0
    for m in js.get("meshes", []):
        for pr in m["primitives"]:
            i = pr.get("indices")
            t += (a[i]["count"] if i is not None else a[pr["attributes"]["POSITION"]]["count"]) // 3
    return t

def _read_glb(path):
    d = open(path, "rb").read()
    _, _, length = struct.unpack("<4sII", d[:12]); off = 12
    js = bin_ = None
    while off < length:
        clen, ctype = struct.unpack("<II", d[off:off+8]); off += 8
        chunk = d[off:off+clen]; off += clen
        if ctype == JSON_C: js = json.loads(chunk)
        elif ctype == BIN_C: bin_ = chunk
    return js, bin_

def optimize_glb(path):
    js, bin_ = _read_glb(path)
    bvs = js["bufferViews"]; before = _glb_tris(js)
    new_img = {}
    for im in js.get("images", []):
        bvi = im["bufferView"]; bv = bvs[bvi]
        o = bv.get("byteOffset", 0); raw = bin_[o:o+bv["byteLength"]]
        img = Image.open(io.BytesIO(raw)); w, h = img.size
        s = min(1.0, MAX_DIM / max(w, h))
        if s >= 1.0:
            new_img[bvi] = raw          # already small: keep bytes, don't re-encode
            continue
        img = img.resize((max(1, int(w*s)), max(1, int(h*s))), Image.LANCZOS)
        buf = io.BytesIO()
        if im.get("mimeType") == "image/jpeg":
            img.convert("RGB").save(buf, "JPEG", quality=85)
        else:
            img.save(buf, "PNG", optimize=True)
        new_img[bvi] = buf.getvalue()
    # repack binary: every bufferView re-emitted 4-byte aligned; non-image
    # views keep their exact bytes so all accessor offsets stay valid.
    out = bytearray()
    for i, bv in enumerate(bvs):
        chunk = new_img.get(i) if i in new_img else bin_[bv.get("byteOffset", 0):bv.get("byteOffset", 0)+bv["byteLength"]]
        while len(out) % 4: out.append(0)
        bv["byteOffset"] = len(out); bv["byteLength"] = len(chunk); out += chunk
    js["buffers"][0]["byteLength"] = len(out)
    nj = json.dumps(js, separators=(",", ":")).encode()
    while len(nj) % 4: nj += b" "
    while len(out) % 4: out.append(0)
    blob = b"glTF" + struct.pack("<II", 2, 12 + 8 + len(nj) + 8 + len(out))
    blob += struct.pack("<II", len(nj), JSON_C) + nj
    blob += struct.pack("<II", len(out), BIN_C) + bytes(out)
    open(path, "wb").write(blob)
    after_js, _ = _read_glb(path)
    assert _glb_tris(after_js) == before, f"{path}: triangle count changed!"
    return before

def optimize_loose():
    saved = 0
    for p in glob.glob(ROOT + "/**/*.png", recursive=True) + glob.glob(ROOT + "/**/*.jpg", recursive=True):
        if any(k in os.path.basename(p).lower() for k in SKIP):
            continue
        img = Image.open(p); w, h = img.size
        if max(w, h) <= MAX_DIM:
            continue
        b0 = os.path.getsize(p); s = MAX_DIM / max(w, h)
        img = img.resize((int(w*s), int(h*s)), Image.LANCZOS)
        if p.lower().endswith(".jpg"):
            img.convert("RGB").save(p, "JPEG", quality=88)
        else:
            img.save(p, "PNG", optimize=True)
        saved += b0 - os.path.getsize(p)
        print(f"  loose {w}x{h}->{img.size}  {p[len(ROOT)+1:]}")
    return saved

def check():
    for p in glob.glob(ROOT + "/**/*.glb", recursive=True):
        js, bin_ = _read_glb(p)
        for im in js.get("images", []):
            bv = js["bufferViews"][im["bufferView"]]
            Image.open(io.BytesIO(bin_[bv.get("byteOffset", 0):bv.get("byteOffset", 0)+bv["byteLength"]])).verify()
        print(f"  ok  {os.path.basename(p)}: {_glb_tris(js):,} tris, {os.path.getsize(p)/1e6:.1f}MB")

if __name__ == "__main__":
    if "--check" in sys.argv:
        check(); sys.exit()
    total0 = total1 = 0
    for p in sorted(glob.glob(ROOT + "/**/*.glb", recursive=True)):
        b0 = os.path.getsize(p); tris = optimize_glb(p); b1 = os.path.getsize(p)
        total0 += b0; total1 += b1
        print(f"  GLB {os.path.basename(p):20} {b0/1e6:6.1f}MB -> {b1/1e6:5.1f}MB  ({tris:,} tris kept)")
    ls = optimize_loose()
    print(f"\nGLB: {total0/1e6:.1f}MB -> {total1/1e6:.1f}MB   loose textures saved {ls/1e6:.1f}MB")
    print(f"total saved: {(total0-total1+ls)/1e6:.1f} MB")
