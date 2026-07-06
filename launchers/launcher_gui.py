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
WORKSPACE_ROOT = os.path.dirname(ROOT) if os.path.basename(ROOT) == "launchers" else ROOT
ENV_FILE = os.path.join(ROOT, ".drone_launch.env")

# preset -> (shadows, physics_hz, solver_iters, cam_w, cam_h, cam_hz)
PRESETS = {
    "None (Full Quality)": (True, 1000, 50, 1280, 960, 60),
    "Mild":                (False, 500, 30, 960, 720, 30),
    "Full (Potato PC)":    (False, 250, 16, 640, 480, 15),
}
NICE = {
    "forest": "Forest",
    "farmland": "Tomato Farmland",
    "row_crops": "Mixed Vegetables",
    "wheat_field": "Pakistani Farmland (Wheat)",
    "powerline": "Powerline Transmission"
}
HZ_OPTS, IT_OPTS = [250, 500, 1000], [16, 30, 50]
CAM_OPTS = [(640, 480, 15), (960, 720, 30), (1280, 960, 60)]


def discover_worlds():
    seen, out = set(), []
    for d in (os.path.join(WORKSPACE_ROOT, "custom_worlds"), os.path.join(os.path.expanduser("~"), "custom_worlds")):
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
    import subprocess
    gen_script = os.path.join(ROOT, f"gen_{cfg['world_name']}.py")
    if os.path.exists(gen_script):
        density = cfg.get("density", "medium")
        print(f"Regenerating {cfg['world_name']} with density={density}...")
        subprocess.run([sys.executable, gen_script, "--density", density], check=True)

    text = open(cfg["world_path"]).read()
    patched = patch_world_sdf(text, cfg["shadows"], cfg["physics_hz"], cfg["solver_iters"])
    world_out = os.path.join(ROOT, f".{cfg['world_name']}.sdf")
    open(world_out, "w", newline="\n").write(patched)
    with open(ENV_FILE, "w", newline="\n") as f:
        f.write(f'export PX4_GZ_WORLD="{cfg["world_name"]}"\n')
        f.write(f'export DENSITY="{cfg.get("density", "medium")}"\n')
        f.write(f'export HEADLESS="{"" if cfg["show_gui"] else "1"}"\n')
        f.write(f'export LAUNCHER_WORLD_FILE="{world_out}"\n')
        f.write(f'export PX4_SIM_MODEL="{cfg.get("sim_model", "gz_x500_mono_cam")}"\n')
        f.write(f'export PX4_SYS_AUTOSTART="{cfg.get("autostart", "4010")}"\n')
        f.write(f'export CAM_W="{cfg["cam"][0]}"\nexport CAM_H="{cfg["cam"][1]}"\nexport CAM_HZ="{cfg["cam"][2]}"\n')
    return world_out


def summarize(cfg):
    print(f"\n  world={cfg['world_name']}  density={cfg.get('density', 'medium')}  shadows={'on' if cfg['shadows'] else 'off'}  "
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
    print("\nDensity:")
    density = ["sparse", "medium", "dense"][_ask("Select density", ["Sparse", "Medium", "Dense"], default=1)]
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
    print("\nDrone Model:")
    di = _ask("Select drone model", ["DJI Matrice 4E (m4e)", "Standard Camera Drone (x500)", "None (Free Roam)"])
    if di == 0:
        sim_model = "m4e"
        autostart = "4900"
    elif di == 1:
        sim_model = "gz_x500_mono_cam"
        autostart = "4010"
    else:
        sim_model = "none"
        autostart = "none"
    show_gui = _yn("\nShow Gazebo GUI window? (off = faster)")
    return {"world_name": wn, "world_path": wp, "density": density, "shadows": shadows, "physics_hz": hz,
            "solver_iters": it, "cam": cam, "show_gui": show_gui, "sim_model": sim_model, "autostart": autostart}


# --------------------------------------------------------------------------- #
# GUI (ttk; no astral emoji). Raises on no-display so caller falls back.
# --------------------------------------------------------------------------- #
def run_gui(worlds):
    import tkinter as tk

    # modern dark palette (matches mission_control)
    BG, PANEL, INPUT = "#0d1117", "#161b22", "#21262d"
    ACCENT, OK, TEXT, MUTED = "#58a6ff", "#3fb950", "#e6edf3", "#8b949e"
    FONT = ("Ubuntu", 10)
    FONT_BOLD = ("Ubuntu", 10, "bold")
    FONT_H1 = ("Ubuntu", 15, "bold")
    FONT_SMALL = ("Ubuntu", 9)
    FONT_SMALL_BOLD = ("Ubuntu", 9, "bold")

    root = tk.Tk()                       # raises TclError if no display -> caller falls back
    root.title("PX4 Drone Simulator Launcher")
    root.geometry("440x580")             # no manual centering (WSLg offsets it off-screen)
    root.configure(bg=BG)
    result = {"cfg": None}

    frm = tk.Frame(root, bg=BG, padx=16, pady=16)
    frm.pack(fill="both", expand=True)

    tk.Label(frm, text="🛸  PX4 Drone Simulator", font=FONT_H1, bg=BG, fg=TEXT).pack(anchor="w")
    tk.Label(frm, text="Pick a world and how hard to push your GPU", font=FONT_SMALL, bg=BG, fg=MUTED).pack(anchor="w", pady=(0, 14))

    # WORLD
    tk.Label(frm, text="WORLD", font=FONT_SMALL_BOLD, bg=BG, fg=ACCENT).pack(anchor="w")
    world_var = tk.StringVar(value=NICE.get(worlds[0][0], worlds[0][0]))
    world_options = [NICE.get(s, s.title()) for s, _ in worlds]
    world_menu = tk.OptionMenu(frm, world_var, *world_options)
    world_menu.config(bg=INPUT, fg=TEXT, activebackground=INPUT, activeforeground=TEXT,
                      highlightthickness=1, highlightbackground="#30363d", bd=0, font=FONT)
    world_menu["menu"].config(bg=INPUT, fg=TEXT, activebackground=ACCENT, activeforeground=BG, font=FONT)
    world_menu.pack(fill="x", pady=(2, 12))

    # DRONE MODEL
    tk.Label(frm, text="DRONE MODEL", font=FONT_SMALL_BOLD, bg=BG, fg=ACCENT).pack(anchor="w")
    drone_var = tk.StringVar(value="DJI Matrice 4E (m4e)")
    drone_options = ["DJI Matrice 4E (m4e)", "Standard Camera Drone (x500)", "None (Free Roam)"]
    drone_menu = tk.OptionMenu(frm, drone_var, *drone_options)
    drone_menu.config(bg=INPUT, fg=TEXT, activebackground=INPUT, activeforeground=TEXT,
                      highlightthickness=1, highlightbackground="#30363d", bd=0, font=FONT)
    drone_menu["menu"].config(bg=INPUT, fg=TEXT, activebackground=ACCENT, activeforeground=BG, font=FONT)
    drone_menu.pack(fill="x", pady=(2, 12))

    # DENSITY
    tk.Label(frm, text="DENSITY", font=FONT_SMALL_BOLD, bg=BG, fg=ACCENT).pack(anchor="w")
    density_var = tk.StringVar(value="Medium")
    density_options = ["Sparse", "Medium", "Dense"]
    density_menu = tk.OptionMenu(frm, density_var, *density_options)
    density_menu.config(bg=INPUT, fg=TEXT, activebackground=INPUT, activeforeground=TEXT,
                        highlightthickness=1, highlightbackground="#30363d", bd=0, font=FONT)
    density_menu["menu"].config(bg=INPUT, fg=TEXT, activebackground=ACCENT, activeforeground=BG, font=FONT)
    density_menu.pack(fill="x", pady=(2, 12))

    def sync_world(*_):
        try:
            sel_nice = world_var.get()
            sel_stem = sel_nice
            for stem, nice_name in NICE.items():
                if nice_name == sel_nice:
                    sel_stem = stem
                    break
            gen_script = os.path.join(ROOT, f"gen_{sel_stem}.py")
            if os.path.exists(gen_script):
                density_menu.configure(state="normal")
            else:
                density_menu.configure(state="disabled")
                density_var.set("N/A")
        except Exception:
            pass

    world_var.trace_add("write", sync_world)
    # Also reset density to a default when a valid world is selected
    def reset_density(*_):
        try:
            sel_nice = world_var.get()
            sel_stem = sel_nice
            for stem, nice_name in NICE.items():
                if nice_name == sel_nice:
                    sel_stem = stem
                    break
            if os.path.exists(os.path.join(ROOT, f"gen_{sel_stem}.py")):
                if density_var.get() == "N/A":
                    density_var.set("Medium")
        except Exception:
            pass
    world_var.trace_add("write", reset_density)
    sync_world()

    # OPTIMIZATION
    tk.Label(frm, text="OPTIMIZATION", font=FONT_SMALL_BOLD, bg=BG, fg=ACCENT).pack(anchor="w")
    preset_var = tk.StringVar(value=list(PRESETS)[0])
    preset_options = list(PRESETS) + ["Custom"]
    preset_menu = tk.OptionMenu(frm, preset_var, *preset_options)
    preset_menu.config(bg=INPUT, fg=TEXT, activebackground=INPUT, activeforeground=TEXT,
                       highlightthickness=1, highlightbackground="#30363d", bd=0, font=FONT)
    preset_menu["menu"].config(bg=INPUT, fg=TEXT, activebackground=ACCENT, activeforeground=BG, font=FONT)
    preset_menu.pack(fill="x", pady=(2, 12))

    # ADVANCED Frame (Standard tk.LabelFrame styled)
    adv = tk.LabelFrame(frm, text="  ADVANCED (Custom preset)  ", bg=BG, fg=MUTED, font=FONT_SMALL_BOLD,
                        bd=1, highlightthickness=0, relief="solid")
    adv.pack(fill="x", pady=(0, 12), ipady=8, ipadx=8)

    shadow_var = tk.BooleanVar(value=False)
    hz_var = tk.StringVar(value="250")
    it_var = tk.StringVar(value="16")
    cam_var = tk.StringVar(value="640x480@15")

    shadow_cb = tk.Checkbutton(adv, text="Shadows", variable=shadow_var, bg=BG, fg=TEXT,
                               activebackground=BG, activeforeground=TEXT, selectcolor=INPUT, font=FONT)
    shadow_cb.grid(row=0, column=0, columnspan=2, sticky="w", pady=2, padx=4)

    # Physics Hz Dropdown
    tk.Label(adv, text="Physics Hz", bg=BG, fg=TEXT, font=FONT).grid(row=1, column=0, sticky="w", pady=2, padx=4)
    hz_options = [str(h) for h in HZ_OPTS]
    hz_menu = tk.OptionMenu(adv, hz_var, *hz_options)
    hz_menu.config(bg=INPUT, fg=TEXT, activebackground=INPUT, activeforeground=TEXT,
                   highlightthickness=1, highlightbackground="#30363d", bd=0, font=FONT)
    hz_menu["menu"].config(bg=INPUT, fg=TEXT, activebackground=ACCENT, activeforeground=BG, font=FONT)
    hz_menu.grid(row=1, column=1, sticky="e", pady=2, padx=4)

    # Solver Iters Dropdown
    tk.Label(adv, text="Solver iters", bg=BG, fg=TEXT, font=FONT).grid(row=2, column=0, sticky="w", pady=2, padx=4)
    it_options = [str(i) for i in IT_OPTS]
    it_menu = tk.OptionMenu(adv, it_var, *it_options)
    it_menu.config(bg=INPUT, fg=TEXT, activebackground=INPUT, activeforeground=TEXT,
                   highlightthickness=1, highlightbackground="#30363d", bd=0, font=FONT)
    it_menu["menu"].config(bg=INPUT, fg=TEXT, activebackground=ACCENT, activeforeground=BG, font=FONT)
    it_menu.grid(row=2, column=1, sticky="e", pady=2, padx=4)

    # Camera Dropdown
    tk.Label(adv, text="Camera", bg=BG, fg=TEXT, font=FONT).grid(row=3, column=0, sticky="w", pady=2, padx=4)
    cam_options = [f"{w}x{h}@{r}" for w, h, r in CAM_OPTS]
    cam_menu = tk.OptionMenu(adv, cam_var, *cam_options)
    cam_menu.config(bg=INPUT, fg=TEXT, activebackground=INPUT, activeforeground=TEXT,
                    highlightthickness=1, highlightbackground="#30363d", bd=0, font=FONT)
    cam_menu["menu"].config(bg=INPUT, fg=TEXT, activebackground=ACCENT, activeforeground=BG, font=FONT)
    cam_menu.grid(row=3, column=1, sticky="e", pady=2, padx=4)

    adv.columnconfigure(0, weight=1)
    adv_widgets = [shadow_cb, hz_menu, it_menu, cam_menu]

    def sync(*_):
        custom = preset_var.get() == "Custom"
        for w in adv_widgets:
            w.configure(state="normal" if custom else "disabled")
        if not custom:
            sh, hz, it, cw, ch, chz = PRESETS[preset_var.get()]
            shadow_var.set(sh)
            hz_var.set(str(hz))
            it_var.set(str(it))
            cam_var.set(f"{cw}x{ch}@{chz}")

    preset_var.trace_add("write", lambda *args: sync())
    sync()

    gui_var = tk.BooleanVar(value=False)
    gui_cb = tk.Checkbutton(frm, text="Show Gazebo GUI window  (slower on weak GPUs)",
                            variable=gui_var, bg=BG, fg=TEXT, activebackground=BG,
                            activeforeground=TEXT, selectcolor=INPUT, font=FONT)
    gui_cb.pack(anchor="w", pady=(0, 14))

    def on_launch():
        wn, wp = worlds[[NICE.get(s, s.title()) for s, _ in worlds].index(world_var.get())]
        cw, ch, chz = (int(x) for x in re.split(r"[x@]", cam_var.get()))
        
        sel_drone = drone_var.get()
        if "m4e" in sel_drone:
            sim_model = "m4e"
            autostart = "4900"
        elif "x500" in sel_drone:
            sim_model = "gz_x500_mono_cam"
            autostart = "4010"
        else:
            sim_model = "none"
            autostart = "none"
            
        result["cfg"] = {"world_name": wn, "world_path": wp,
                          "shadows": bool(shadow_var.get()), "physics_hz": int(hz_var.get()),
                          "solver_iters": int(it_var.get()), "cam": (cw, ch, chz),
                          "show_gui": bool(gui_var.get()), "density": density_var.get().lower(),
                          "sim_model": sim_model, "autostart": autostart}
        root.destroy()

    bar = tk.Frame(frm, bg=BG)
    bar.pack(fill="x", side="bottom")

    btn_launch = tk.Button(bar, text="▶  Launch", bg=OK, fg=BG, activebackground="#4fd061", activeforeground=BG,
                           font=FONT_BOLD, bd=0, relief="flat", padx=16, pady=8, command=on_launch)
    btn_launch.pack(side="right")

    btn_cancel = tk.Button(bar, text="Cancel", bg=PANEL, fg=MUTED, activebackground="#30363d", activeforeground=TEXT,
                           font=FONT, bd=0, relief="flat", padx=16, pady=8, command=root.destroy)
    btn_cancel.pack(side="right", padx=8)

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
