#!/usr/bin/env python3
"""PX4 Drone Simulator launcher.

Shows a small dialog to pick world + optimization preset + Gazebo-GUI toggle,
then writes .drone_launch.env (PX4_GZ_WORLD / HEADLESS / LAUNCHER_WORLD_FILE /
CAM_*) and a patched .<world>.sdf for run_all.sh to use. Exit 0 = launch,
1 = cancel.

GUI vs terminal: a Tk/ttk dialog is used when a display is available, otherwise
a plain terminal menu (SSH / Docker-without-X / CI). Both share the same
backend. WSLg note: the GUI uses ttk + BMP symbols only -- NO astral-plane
emoji (U+1F300+), which silently hang Tk under WSLg. mission_control.py proves
this exact recipe renders fine here.
"""
import os, sys, re, glob

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(ROOT, ".drone_launch.env")

# preset -> (shadows, physics_hz, solver_iters, cam_w, cam_h, cam_hz)
PRESETS = {
    "Full (Potato PC)":    (False, 250, 16, 640, 480, 15),
    "Mild":                (False, 500, 30, 960, 720, 20),
    "None (Full Quality)": (True, 1000, 50, 1280, 960, 30),
}
NICE = {"forest": "Forest", "farmland": "Tomato Farmland", "row_crops": "Mixed Vegetables"}
HZ_OPTS, IT_OPTS = [250, 500, 1000], [16, 30, 50]
CAM_OPTS = [(640, 480, 15), (960, 720, 20), (1280, 960, 30)]


def discover_worlds():
    seen, out = set(), []
    for d in (os.path.join(ROOT, "custom_worlds"), os.path.join(os.path.expanduser("~"), "custom_worlds")):
        for p in sorted(glob.glob(os.path.join(d, "*.sdf"))):
            stem = os.path.splitext(os.path.basename(p))[0]
            if stem not in seen:
                seen.add(stem); out.append((stem, p))
    out.sort(key=lambda w: (w[0] != "forest", w[0]))   # forest first
    return out


def patch_world_sdf(text, shadows_on, physics_hz, solver_iters):
    step = round(1.0 / physics_hz, 6)
    block = (f'    <physics type="ode">\n'
             f'      <max_step_size>{step}</max_step_size>\n'
             f'      <real_time_factor>1.0</real_time_factor>\n'
             f'      <real_time_update_rate>{physics_hz}</real_time_update_rate>\n'
             f'      <ode><solver><type>quick</type><iters>{solver_iters}</iters><sor>1.3</sor></solver></ode>\n'
             f'    </physics>')
    if re.search(r"<physics[^>]*>.*?</physics>", text, re.S):
        text = re.sub(r"<physics[^>]*>.*?</physics>", block, text, count=1, flags=re.S)
    else:
        text = re.sub(r"(<world[^>]*>)", r"\1\n" + block, text, count=1)
    sval = "true" if shadows_on else "false"
    text = re.sub(r"(<light[^>]*>.*?</light>)",
                  lambda m: re.sub(r"<cast_shadows>\s*(?:true|false)\s*</cast_shadows>",
                                   f"<cast_shadows>{sval}</cast_shadows>", m.group(1)),
                  text, flags=re.S)
    return text


def write_outputs(cfg):
    text = open(cfg["world_path"]).read()
    patched = patch_world_sdf(text, cfg["shadows"], cfg["physics_hz"], cfg["solver_iters"])
    world_out = os.path.join(ROOT, f".{cfg['world_name']}.sdf")
    open(world_out, "w", newline="\n").write(patched)
    with open(ENV_FILE, "w", newline="\n") as f:
        f.write(f'export PX4_GZ_WORLD="{cfg["world_name"]}"\n')
        f.write(f'export HEADLESS="{"" if cfg["show_gui"] else "1"}"\n')
        f.write(f'export LAUNCHER_WORLD_FILE="{world_out}"\n')
        f.write(f'export CAM_W="{cfg["cam"][0]}"\nexport CAM_H="{cfg["cam"][1]}"\nexport CAM_HZ="{cfg["cam"][2]}"\n')
    return world_out


def summarize(cfg):
    print(f"\n  world={cfg['world_name']}  shadows={'on' if cfg['shadows'] else 'off'}  "
          f"physics={cfg['physics_hz']}Hz  solver={cfg['solver_iters']}  "
          f"camera={cfg['cam'][0]}x{cfg['cam'][1]}@{cfg['cam'][2]}  "
          f"gazebo_gui={'yes' if cfg['show_gui'] else 'no'}\n  Launching...\n")


# --------------------------------------------------------------------------- #
# Terminal menu (fallback / no display)
# --------------------------------------------------------------------------- #
def _ask(prompt, options, default=0):
    if not sys.stdin.isatty():
        return default
    for i, o in enumerate(options, 1):
        print(f"  {i}) {o}" + ("   [default]" if i - 1 == default else ""))
    while True:
        raw = input(f"{prompt} [{default + 1}]: ").strip()
        if raw == "":
            return default
        if raw.lower() in ("q", "quit", "cancel"):
            print("Cancelled."); sys.exit(1)
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print("  ? enter a number, or q to cancel")


def _yn(prompt, default_no=True):
    if not sys.stdin.isatty():
        return not default_no
    raw = input(f"{prompt} [{'y/N' if default_no else 'Y/n'}]: ").strip().lower()
    if raw in ("q", "quit", "cancel"):
        print("Cancelled."); sys.exit(1)
    return raw.startswith("y") if raw else (not default_no)


def run_terminal(worlds):
    print("\n=== PX4 Drone Simulator Launcher ===  (Enter = default, q = cancel)\n")
    print("Scenery:")
    wn, wp = worlds[_ask("Select world", [NICE.get(s, s.title()) for s, _ in worlds])]
    print("\nOptimization:")
    pnames = list(PRESETS) + ["Custom"]
    pi = _ask("Select preset", pnames)
    if pnames[pi] == "Custom":
        shadows = _yn("\n  Shadows on?")
        hz = HZ_OPTS[_ask("  Physics rate (Hz)", [str(h) for h in HZ_OPTS])]
        it = IT_OPTS[_ask("  Solver iterations", [str(i) for i in IT_OPTS])]
        cam = CAM_OPTS[_ask("  Camera (WxH@Hz)", [f"{w}x{h}@{r}" for w, h, r in CAM_OPTS])]
    else:
        shadows, hz, it, cw, ch, chz = PRESETS[pnames[pi]]; cam = (cw, ch, chz)
    show_gui = _yn("\nShow Gazebo GUI window? (off = faster)")
    return {"world_name": wn, "world_path": wp, "shadows": shadows, "physics_hz": hz,
            "solver_iters": it, "cam": cam, "show_gui": show_gui}


# --------------------------------------------------------------------------- #
# GUI (ttk; no astral emoji). Raises on no-display so caller falls back.
# --------------------------------------------------------------------------- #
def run_gui(worlds):
    import tkinter as tk
    from tkinter import ttk

    # modern dark palette (matches mission_control)
    BG, PANEL, INPUT = "#0d1117", "#161b22", "#21262d"
    ACCENT, OK, TEXT, MUTED = "#58a6ff", "#3fb950", "#e6edf3", "#8b949e"
    FONT = "Ubuntu"

    root = tk.Tk()                       # raises TclError if no display -> caller falls back
    root.title("PX4 Drone Simulator Launcher")
    root.geometry("440x520")             # no manual centering (WSLg offsets it off-screen)
    root.configure(bg=BG)
    result = {"cfg": None}

    st = ttk.Style(); st.theme_use("clam")
    st.configure(".", background=BG, foreground=TEXT, font=(FONT, 10))
    st.configure("TFrame", background=BG)
    st.configure("Card.TFrame", background=PANEL)
    st.configure("TLabel", background=BG, foreground=TEXT)
    st.configure("Card.TLabel", background=PANEL, foreground=TEXT)
    st.configure("H1.TLabel", background=BG, foreground=TEXT, font=(FONT, 15, "bold"))
    st.configure("Dim.TLabel", background=BG, foreground=MUTED, font=(FONT, 9))
    st.configure("Sec.TLabel", background=BG, foreground=ACCENT, font=(FONT, 9, "bold"))
    st.configure("TCombobox", fieldbackground=INPUT, background=INPUT, foreground=TEXT,
                 arrowcolor=TEXT, bordercolor="#30363d", selectbackground=INPUT, selectforeground=TEXT)
    st.map("TCombobox", fieldbackground=[("readonly", INPUT)], foreground=[("readonly", TEXT)])
    st.configure("TCheckbutton", background=BG, foreground=TEXT)
    st.map("TCheckbutton", background=[("active", BG)])
    st.configure("TLabelframe", background=BG, foreground=MUTED, bordercolor="#30363d")
    st.configure("TLabelframe.Label", background=BG, foreground=MUTED, font=(FONT, 9, "bold"))
    st.configure("Launch.TButton", background=OK, foreground=BG, font=(FONT, 11, "bold"), borderwidth=0, padding=8)
    st.map("Launch.TButton", background=[("active", "#4fd061")])
    st.configure("Ghost.TButton", background=PANEL, foreground=MUTED, borderwidth=0, padding=8)
    st.map("Ghost.TButton", background=[("active", "#30363d")])
    for o, v in (("background", INPUT), ("foreground", TEXT), ("selectBackground", ACCENT), ("selectForeground", BG)):
        root.option_add(f"*TCombobox*Listbox.{o}", v)

    frm = ttk.Frame(root, padding=16)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text="\U0001F6F8  PX4 Drone Simulator", style="H1.TLabel").pack(anchor="w")
    ttk.Label(frm, text="Pick a world and how hard to push your GPU", style="Dim.TLabel").pack(anchor="w", pady=(0, 14))

    ttk.Label(frm, text="WORLD", style="Sec.TLabel").pack(anchor="w")
    world_var = tk.StringVar(value=NICE.get(worlds[0][0], worlds[0][0]))
    ttk.Combobox(frm, textvariable=world_var, state="readonly",
                 values=[NICE.get(s, s.title()) for s, _ in worlds]).pack(fill="x", pady=(2, 12))

    ttk.Label(frm, text="OPTIMIZATION", style="Sec.TLabel").pack(anchor="w")
    preset_var = tk.StringVar(value=list(PRESETS)[0])
    preset_cb = ttk.Combobox(frm, textvariable=preset_var, state="readonly",
                             values=list(PRESETS) + ["Custom"])
    preset_cb.pack(fill="x", pady=(2, 12))

    adv = ttk.LabelFrame(frm, text="  ADVANCED (Custom preset)  ", padding=10)
    adv.pack(fill="x", pady=(0, 12))
    shadow_var = tk.BooleanVar(value=False)
    hz_var = tk.StringVar(value="250"); it_var = tk.StringVar(value="16")
    cam_var = tk.StringVar(value="640x480@15")
    shadow_cb = ttk.Checkbutton(adv, text="Shadows", variable=shadow_var)
    shadow_cb.grid(row=0, column=0, columnspan=2, sticky="w", pady=2)
    ttk.Label(adv, text="Physics Hz", style="TLabel").grid(row=1, column=0, sticky="w", pady=2)
    hz_cb = ttk.Combobox(adv, textvariable=hz_var, state="readonly", width=12, values=[str(h) for h in HZ_OPTS])
    hz_cb.grid(row=1, column=1, sticky="e")
    ttk.Label(adv, text="Solver iters", style="TLabel").grid(row=2, column=0, sticky="w", pady=2)
    it_cb = ttk.Combobox(adv, textvariable=it_var, state="readonly", width=12, values=[str(i) for i in IT_OPTS])
    it_cb.grid(row=2, column=1, sticky="e")
    ttk.Label(adv, text="Camera", style="TLabel").grid(row=3, column=0, sticky="w", pady=2)
    cam_cb = ttk.Combobox(adv, textvariable=cam_var, state="readonly", width=12,
                          values=[f"{w}x{h}@{r}" for w, h, r in CAM_OPTS])
    cam_cb.grid(row=3, column=1, sticky="e")
    adv.columnconfigure(0, weight=1)
    adv_widgets = [shadow_cb, hz_cb, it_cb, cam_cb]

    def sync(*_):
        custom = preset_var.get() == "Custom"
        for w in adv_widgets:
            w.configure(state="normal" if custom else "disabled")
        if not custom:
            sh, hz, it, cw, ch, chz = PRESETS[preset_var.get()]
            shadow_var.set(sh); hz_var.set(str(hz)); it_var.set(str(it)); cam_var.set(f"{cw}x{ch}@{chz}")
    preset_cb.bind("<<ComboboxSelected>>", sync)
    sync()

    gui_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(frm, text="Show Gazebo GUI window  (slower on weak GPUs)",
                    variable=gui_var).pack(anchor="w", pady=(0, 14))

    def on_launch():
        wn, wp = worlds[[NICE.get(s, s.title()) for s, _ in worlds].index(world_var.get())]
        cw, ch, chz = (int(x) for x in re.split(r"[x@]", cam_var.get()))
        result["cfg"] = {"world_name": wn, "world_path": wp,
                         "shadows": bool(shadow_var.get()), "physics_hz": int(hz_var.get()),
                         "solver_iters": int(it_var.get()), "cam": (cw, ch, chz),
                         "show_gui": bool(gui_var.get())}
        root.destroy()

    bar = ttk.Frame(frm); bar.pack(fill="x", side="bottom")
    ttk.Button(bar, text="▶  Launch", style="Launch.TButton", command=on_launch).pack(side="right")
    ttk.Button(bar, text="Cancel", style="Ghost.TButton", command=root.destroy).pack(side="right", padx=8)

    root.mainloop()
    return result["cfg"]


def main():
    worlds = discover_worlds()
    if not worlds:
        print("ERROR: no worlds found in custom_worlds/", file=sys.stderr); sys.exit(1)

    cfg = None
    if os.environ.get("DISPLAY") and "--no-gui" not in sys.argv:
        try:
            cfg = run_gui(worlds)          # None if user cancelled
            if cfg is None:
                print("Cancelled."); sys.exit(1)
        except Exception as e:
            print(f"(GUI unavailable: {e} -- using terminal menu)")
            cfg = None
    if cfg is None:
        cfg = run_terminal(worlds)         # exits 1 itself on cancel

    write_outputs(cfg)
    summarize(cfg)
    sys.exit(0)


if __name__ == "__main__":
    main()
