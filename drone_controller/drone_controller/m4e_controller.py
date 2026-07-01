#!/usr/bin/env python3
# =============================================================================
# m4e Drone Controller GUI  —  ROS 2 (PX4) + Tkinter
# =============================================================================
# Features
#   * Pilot Mode    : fly with the keyboard (WASD + climb/yaw), body-frame
#                     velocity setpoints streamed at 20 Hz over offboard.
#   * Lens select   : Wide 84° / Med 35° / Tele 15°. Click to start a live
#                     1 Hz feed from that camera; only one lens streams at a time.
#   * Gimbal        : Pan / Roll / Tilt sliders (rad → Gazebo JointPositionCtrl).
#   * Flight buttons: Arm / Disarm / Takeoff / Land / Hold / RTL / Kill.
#   * Telemetry HUD : armed state, flight mode, position, velocity, battery.
#
# Threading model:
#   ROS callbacks ONLY write data into the node (stream lock protects sub).
#   ALL Tkinter widget access happens on the main thread via root.after().
# =============================================================================

import math
import threading
import time

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

from px4_msgs.msg import (
    VehicleCommand,
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleStatus,
    VehicleLocalPosition,
    BatteryStatus,
)
from sensor_msgs.msg import CompressedImage, Image
from std_msgs.msg import Float64, String
from PIL import Image as PILImage, ImageTk
import io
import subprocess


# --- Theme -------------------------------------------------------------------
BG      = "#1e1e2e"
BG2     = "#181825"
PANEL   = "#11111b"
FG      = "#cdd6f4"
ACCENT  = "#89b4fa"
GREEN   = "#a6e3a1"
RED     = "#f38ba8"
YELLOW  = "#f9e2af"
SUBTLE  = "#6c7086"

LENSES = {
    "wide":        "Wide  84°",
    "medium_tele": "Med   35°",
    "tele":        "Tele  15°",
}

JOINTS = {
    "pan":  {"lo": -1.047198, "hi":  1.047198, "topic": "/drone/gimbal/cmd/pan"},
    "roll": {"lo": -0.820305, "hi":  0.820305, "topic": "/drone/gimbal/cmd/roll"},
    "tilt": {"lo": -1.570796, "hi":  0.610865, "topic": "/drone/gimbal/cmd/tilt"},
}

# Zoom slider: log-scale 1× – 168×; breakpoints select the active camera lens.
_LOG_ZOOM_MAX  = math.log(168.0)
_ZOOM_BREAKS   = [(3.0, "wide"), (7.0, "medium_tele"), (float("inf"), "tele")]

def _slider_to_zoom(s: float) -> float:
    return math.exp(float(s) * _LOG_ZOOM_MAX)

def _zoom_to_lens(z: float) -> str:
    for threshold, name in _ZOOM_BREAKS:
        if z < threshold:
            return name
    return "tele"

PILOT_SPEED         = 3.0
PILOT_YAW_RATE      = 0.6
CONTROL_HZ          = 20.0
DEFAULT_TAKEOFF_ALT = 5.0


# =============================================================================
# ROS 2 node
# =============================================================================
class DroneNode(Node):
    def __init__(self):
        super().__init__("drone_controller_node")

        px4_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        self.cmd_pub     = self.create_publisher(VehicleCommand,       "/fmu/in/vehicle_command",     px4_qos)
        self.offboard_pub= self.create_publisher(OffboardControlMode,  "/fmu/in/offboard_control_mode",px4_qos)
        self.traj_pub    = self.create_publisher(TrajectorySetpoint,   "/fmu/in/trajectory_setpoint", px4_qos)

        self._gimbal_pubs = {
            name: self.create_publisher(Float64, cfg["topic"], 1)
            for name, cfg in JOINTS.items()
        }
        self._cam_select_pub = self.create_publisher(String,  "/drone/camera/select", 1)
        self._zoom_pub       = self.create_publisher(Float64, "/drone/camera/zoom",   1)

        self.create_subscription(VehicleStatus,        "/fmu/out/vehicle_status",         self._status_cb, px4_qos)
        self.create_subscription(VehicleLocalPosition, "/fmu/out/vehicle_local_position",  self._pos_cb,    px4_qos)
        self.create_subscription(BatteryStatus,        "/fmu/out/battery_status",          self._bat_cb,    px4_qos)

        self.connected       = False
        self.armed           = False
        self.flight_mode     = "—"
        self.x = self.y = self.z = 0.0
        self.vx = self.vy = self.vz = 0.0
        self.heading         = 0.0
        self.battery_percent = 0.0
        self.last_status_time= 0.0

        self.offboard_active = False
        self.control_mode    = "velocity"
        self.cmd_fwd = self.cmd_right = self.cmd_up = self.cmd_yaw = 0.0
        self.hold_x  = self.hold_y   = self.hold_z  = 0.0
        self.hold_yaw= 0.0

        self._stream_on_frame = None   # callback set by GUI when a lens is active

        img_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self.create_subscription(
            CompressedImage,
            "/drone/camera/active/image_raw/compressed",
            self._compressed_cb,
            img_qos,
        )

        self.create_timer(1.0 / CONTROL_HZ, self._control_loop)
        self.get_logger().info("DroneNode ready")

    # ---- vehicle commands ---------------------------------------------------
    def _send_cmd(self, command, **params):
        msg = VehicleCommand()
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        for i in range(1, 8):
            setattr(msg, f"param{i}", float(params.get(f"p{i}", 0.0)))
        msg.command          = command
        msg.target_system    = 1
        msg.target_component = 1
        msg.source_system    = 1
        msg.source_component = 1
        msg.from_external    = True
        self.cmd_pub.publish(msg)

    def arm(self):            self._send_cmd(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, p1=1.0)
    def disarm(self):         self._send_cmd(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, p1=0.0)
    def takeoff_cmd(self, a): self._send_cmd(VehicleCommand.VEHICLE_CMD_NAV_TAKEOFF, p7=float(a))
    def land(self):           self._send_cmd(VehicleCommand.VEHICLE_CMD_NAV_LAND)
    def rtl(self):            self._send_cmd(VehicleCommand.VEHICLE_CMD_NAV_RETURN_TO_LAUNCH)
    def kill(self):           self._send_cmd(VehicleCommand.VEHICLE_CMD_DO_FLIGHTTERMINATION, p1=1.0)
    def engage_offboard(self):self._send_cmd(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, p1=1.0, p2=6.0)

    # ---- offboard loop ------------------------------------------------------
    def _control_loop(self):
        if not self.offboard_active:
            return
        ts = int(self.get_clock().now().nanoseconds / 1000)
        ob = OffboardControlMode()
        ob.timestamp = ts
        ob.position  = (self.control_mode == "position")
        ob.velocity  = (self.control_mode == "velocity")
        self.offboard_pub.publish(ob)

        sp  = TrajectorySetpoint()
        sp.timestamp = ts
        nan = float("nan")
        if self.control_mode == "position":
            sp.position = [self.hold_x, self.hold_y, self.hold_z]
            sp.velocity = [nan, nan, nan]
            sp.yaw      = self.hold_yaw
            sp.yawspeed = nan
        else:
            psi = self.heading
            sp.position  = [nan, nan, nan]
            sp.velocity  = [
                self.cmd_fwd * math.cos(psi) - self.cmd_right * math.sin(psi),
                self.cmd_fwd * math.sin(psi) + self.cmd_right * math.cos(psi),
                -self.cmd_up,
            ]
            sp.yaw      = nan
            sp.yawspeed = self.cmd_yaw
        sp.acceleration = [nan, nan, nan]
        sp.jerk         = [nan, nan, nan]
        self.traj_pub.publish(sp)

    def hold_here(self):
        self.hold_x, self.hold_y, self.hold_z = self.x, self.y, self.z
        self.hold_yaw   = self.heading
        self.control_mode = "position"

    # ---- telemetry ----------------------------------------------------------
    def _status_cb(self, msg):
        self.connected        = True
        self.last_status_time = time.time()
        self.armed            = (msg.arming_state == 2)
        self.flight_mode      = self._nav_to_str(msg.nav_state)

    def _pos_cb(self, msg):
        self.x, self.y, self.z   = msg.x, msg.y, msg.z
        self.vx, self.vy, self.vz = msg.vx, msg.vy, msg.vz
        if getattr(msg, "heading_good_for_control", True):
            self.heading = getattr(msg, "heading", self.heading)

    def _bat_cb(self, msg):
        self.battery_percent = msg.remaining * 100.0

    # ---- gimbal -------------------------------------------------------------
    def cmd_gimbal(self, joint: str, radians: float):
        msg      = Float64()
        msg.data = float(radians)
        self._gimbal_pubs[joint].publish(msg)

    def cmd_zoom(self, zoom: float, lens: str) -> None:
        zm = Float64(); zm.data = float(zoom)
        self._zoom_pub.publish(zm)
        sl = String(); sl.data = lens
        self._cam_select_pub.publish(sl)

    # ---- live camera stream (via camera_switcher.py) -----------------------
    def _compressed_cb(self, msg: CompressedImage) -> None:
        if self._stream_on_frame is None:
            return
        try:
            pil = PILImage.open(io.BytesIO(bytes(msg.data))).convert("RGB")
            self._stream_on_frame(np.array(pil))
        except Exception as e:
            self.get_logger().warn(f"compressed decode: {e}")

    def start_stream(self, lens_name: str, on_frame) -> None:
        """Tell camera_switcher to activate this lens; frames arrive via compressed sub."""
        self._stream_on_frame = on_frame
        msg = String()
        msg.data = lens_name
        self._cam_select_pub.publish(msg)

    def stop_stream(self) -> None:
        self._stream_on_frame = None

    @staticmethod
    def _nav_to_str(s):
        return {0:"Manual",1:"Altitude",2:"Position",3:"Mission",
                4:"Loiter",5:"RTL",7:"Offboard",8:"Stabilized",
                10:"Takeoff",11:"Land",14:"RTL"}.get(s, f"Mode {s}")


# =============================================================================
# Tkinter GUI
# =============================================================================
class DroneGUI:
    def __init__(self, root):
        self.root        = root
        self.root.title("m4e — Powerline Inspection Pilot")
        self.root.geometry("1380x860")
        self.root.configure(bg=BG)
        self.root.minsize(1100, 720)

        self._init_style()

        self.node            = None
        self.cam_photo       = None
        self.active_lens     = None
        self.pilot_on        = False
        self.pressed         = set()
        self._last_frame     = None
        self._switcher_proc  = None

        self._build_ui()
        self._bind_keys()
        self._start_ros()

        self.root.after(200, self._poll_telemetry)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- style --------------------------------------------------------------
    def _init_style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TFrame",  background=BG)
        s.configure("TLabel",  background=BG, foreground=FG)
        s.configure("TButton", background="#313244", foreground=FG,
                    borderwidth=0, focuscolor=BG, padding=6)
        s.map("TButton", background=[("active", "#45475a")])
        s.configure("Accent.TButton", background=ACCENT, foreground=BG2,
                    font=("Segoe UI", 10, "bold"))
        s.map("Accent.TButton",  background=[("active", "#74a0e8")])
        s.configure("Danger.TButton", background=RED, foreground=BG2,
                    font=("Segoe UI", 10, "bold"))
        s.map("Danger.TButton",  background=[("active", "#e07a96")])
        s.configure("Lens.TButton",       background="#313244", foreground=FG,
                    font=("Segoe UI", 10, "bold"), padding=8)
        s.map("Lens.TButton",       background=[("active", "#45475a")])
        s.configure("LensActive.TButton", background=ACCENT, foreground=BG2,
                    font=("Segoe UI", 10, "bold"), padding=8)

    def _section(self, parent, title):
        f = tk.LabelFrame(parent, text=title, bg=BG, fg=ACCENT,
                          font=("Segoe UI", 11, "bold"), bd=2,
                          relief=tk.GROOVE, labelanchor="nw")
        f.pack(fill=tk.X, pady=(0, 10), padx=4)
        return f

    # ---- UI assembly --------------------------------------------------------
    def _build_ui(self):
        pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        left = ttk.Frame(pane, width=400); pane.add(left, weight=0)
        right = ttk.Frame(pane);           pane.add(right, weight=1)

        self._build_connection(left)
        self._build_flight(left)
        self._build_pilot(left)
        self._build_gimbal(left)
        self._build_log(left)
        self._build_camera(right)
        self._build_telemetry(right)

    def _build_connection(self, parent):
        f = self._section(parent, "Connection")
        self.conn_label = tk.Label(f, text="● Connecting to PX4…", bg=BG,
                                   fg=YELLOW, font=("Segoe UI", 11, "bold"))
        self.conn_label.pack(anchor=tk.W, padx=10, pady=(6, 2))
        ttk.Button(f, text="Launch QGroundControl",
                   command=self.launch_qgc).pack(fill=tk.X, padx=10, pady=(2, 8))

    def _build_flight(self, parent):
        f = self._section(parent, "Flight")
        r1 = ttk.Frame(f); r1.pack(fill=tk.X, padx=10, pady=(8, 2))
        ttk.Button(r1, text="ARM",     style="Accent.TButton", command=self.on_arm
                   ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(r1, text="DISARM",  command=self.on_disarm
                   ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        r2 = ttk.Frame(f); r2.pack(fill=tk.X, padx=10, pady=2)
        ttk.Button(r2, text="TAKEOFF", style="Accent.TButton", command=self.on_takeoff
                   ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(r2, text="LAND",    command=self.on_land
                   ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        r3 = ttk.Frame(f); r3.pack(fill=tk.X, padx=10, pady=2)
        ttk.Button(r3, text="HOLD",    command=self.on_hold
                   ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(r3, text="RTL",     command=self.on_rtl
                   ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        tk.Label(f, text="Takeoff altitude (m)", bg=BG, fg=SUBTLE,
                 font=("Segoe UI", 9)).pack(anchor=tk.W, padx=10, pady=(6, 0))
        self.alt_slider = tk.Scale(f, from_=2, to=30, resolution=1,
                                   orient=tk.HORIZONTAL, bg=BG, fg=FG,
                                   highlightthickness=0, troughcolor="#313244")
        self.alt_slider.set(DEFAULT_TAKEOFF_ALT)
        self.alt_slider.pack(fill=tk.X, padx=10)
        ttk.Button(f, text="⛔  KILL (emergency cut)", style="Danger.TButton",
                   command=self.on_kill).pack(fill=tk.X, padx=10, pady=8)

    def _build_pilot(self, parent):
        f = self._section(parent, "Pilot Mode")
        self.pilot_btn = ttk.Button(f, text="▶  Start Pilot Mode",
                                    style="Accent.TButton", command=self.toggle_pilot)
        self.pilot_btn.pack(fill=tk.X, padx=10, pady=(8, 6))
        tk.Label(f,
                 text="W/S  fwd/back    A/D  left/right\n"
                      "R/F  up/down     Q/E  yaw\n"
                      "SPACE  hold position",
                 bg=PANEL, fg=GREEN, justify=tk.LEFT,
                 font=("Consolas", 9), anchor="w"
                 ).pack(fill=tk.X, padx=10, pady=(0, 8), ipady=6, ipadx=6)

    def _build_gimbal(self, parent):
        f = self._section(parent, "Gimbal")
        self._joint_vars   = {}
        self._joint_labels = {}
        for name, cfg in JOINTS.items():
            lo_deg, hi_deg = math.degrees(cfg["lo"]), math.degrees(cfg["hi"])
            row = tk.Frame(f, bg=BG); row.pack(fill=tk.X, padx=10, pady=3)
            tk.Label(row, text=name.upper(), bg=BG, fg=FG,
                     font=("Consolas", 10, "bold"), width=5, anchor="w").pack(side=tk.LEFT)
            val_lbl = tk.Label(row, text=" +0.0°", bg=BG, fg=ACCENT,
                               font=("Consolas", 10), width=7, anchor="e")
            val_lbl.pack(side=tk.RIGHT)
            self._joint_labels[name] = val_lbl
            tk.Label(row, text=f"{lo_deg:.0f}°", bg=BG, fg=SUBTLE,
                     font=("Consolas", 8)).pack(side=tk.LEFT, padx=(4, 0))
            var = tk.DoubleVar(value=0.0)
            self._joint_vars[name] = var
            sty = f"gimbal_{name}.Horizontal.TScale"
            ttk.Style().configure(sty, background=BG, troughcolor="#313244",
                                  sliderlength=16, sliderrelief="flat")
            slider = ttk.Scale(row, from_=lo_deg, to=hi_deg,
                               orient=tk.HORIZONTAL, variable=var,
                               style=sty, length=180)
            slider.pack(side=tk.LEFT, padx=4)
            tk.Label(row, text=f"{hi_deg:.0f}°", bg=BG, fg=SUBTLE,
                     font=("Consolas", 8)).pack(side=tk.LEFT)

            def _moved(val, n=name, lbl=val_lbl):
                deg = float(val)
                lbl.config(text=f"{deg:+.1f}°")
                if self.node:
                    self.node.cmd_gimbal(n, math.radians(deg))
            slider.configure(command=_moved)

        # ── zoom slider ──────────────────────────────────────────────────────
        zoom_row = tk.Frame(f, bg=BG); zoom_row.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(zoom_row, text="ZOOM", bg=BG, fg=FG,
                 font=("Consolas", 10, "bold"), width=5, anchor="w").pack(side=tk.LEFT)
        self._zoom_label = tk.Label(zoom_row, text="  1.0×", bg=BG, fg=ACCENT,
                                    font=("Consolas", 10), width=7, anchor="e")
        self._zoom_label.pack(side=tk.RIGHT)
        tk.Label(zoom_row, text="1×", bg=BG, fg=SUBTLE,
                 font=("Consolas", 8)).pack(side=tk.LEFT, padx=(4, 0))
        self._zoom_var = tk.DoubleVar(value=0.0)
        ttk.Style().configure("zoom.Horizontal.TScale", background=BG,
                              troughcolor="#313244", sliderlength=16, sliderrelief="flat")
        zoom_slider = ttk.Scale(zoom_row, from_=0.0, to=1.0, orient=tk.HORIZONTAL,
                                variable=self._zoom_var, style="zoom.Horizontal.TScale",
                                length=180)
        zoom_slider.pack(side=tk.LEFT, padx=4)
        tk.Label(zoom_row, text="168×", bg=BG, fg=SUBTLE,
                 font=("Consolas", 8)).pack(side=tk.LEFT)

        self._zoom_lens_label = tk.Label(f, bg=BG, fg=SUBTLE,
                                         font=("Consolas", 8), anchor="w")
        self._zoom_lens_label.pack(fill=tk.X, padx=28, pady=(0, 4))
        self._zoom_lens_label.config(text="[Wide 84°]  3×→Med 35°  7×→Tele 15°")

        def _on_zoom(val):
            z    = _slider_to_zoom(val)
            lens = _zoom_to_lens(z)
            self._zoom_label.config(text=f"{z:5.1f}×")
            segs = [("Wide 84°", "wide"), ("Med 35°", "medium_tele"), ("Tele 15°", "tele")]
            self._zoom_lens_label.config(
                text="  ".join(f"[{t}]" if n == lens else f"3×→{t}" if n == "medium_tele"
                               else f"7×→{t}" if n == "tele" else t
                               for t, n in segs))
            if self.node:
                self.node.cmd_zoom(z, lens)
            if lens != self.active_lens:
                self.select_lens(lens)

        zoom_slider.configure(command=_on_zoom)

        ttk.Button(f, text="Home Gimbal", command=self._gimbal_home
                   ).pack(anchor=tk.W, padx=10, pady=(4, 8))

    def _build_log(self, parent):
        f = self._section(parent, "Log")
        self.log_text = scrolledtext.ScrolledText(
            f, bg=PANEL, fg=GREEN, insertbackground=FG,
            font=("Consolas", 9), height=7, bd=0)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    def _build_camera(self, parent):
        # Lens selector — clicking starts the live feed from that lens
        bar = ttk.Frame(parent); bar.pack(fill=tk.X, padx=4, pady=(0, 6))
        tk.Label(bar, text="LENS", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT, padx=(4, 10))
        self.lens_buttons = {}
        for lens, label in LENSES.items():
            b = ttk.Button(bar, text=label, style="Lens.TButton",
                           command=lambda l=lens: self.select_lens(l))
            b.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
            self.lens_buttons[lens] = b

        # Status + Save
        sbar = ttk.Frame(parent); sbar.pack(fill=tk.X, padx=4, pady=(0, 4))
        self.stream_status = tk.Label(sbar, text="Select a lens to start live feed",
                                      bg=BG, fg=SUBTLE, font=("Segoe UI", 9))
        self.stream_status.pack(side=tk.LEFT)
        ttk.Button(sbar, text="Save…", command=self.on_save
                   ).pack(side=tk.RIGHT, padx=4)

        # Live display
        disp = tk.LabelFrame(parent, text="Live Feed", bg=BG, fg=ACCENT,
                             font=("Segoe UI", 11, "bold"))
        disp.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 8))
        self.cam_label = tk.Label(disp, bg="black",
                                  text="Select a lens to start live feed",
                                  fg=SUBTLE, font=("Segoe UI", 14))
        self.cam_label.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def _build_telemetry(self, parent):
        f = tk.LabelFrame(parent, text="Telemetry", bg=BG, fg=ACCENT,
                          font=("Segoe UI", 11, "bold"))
        f.pack(fill=tk.X, padx=4, pady=(0, 4))
        grid = ttk.Frame(f); grid.pack(fill=tk.X, padx=10, pady=8)
        self.telem = {}
        items = [("Armed","—",RED),("Mode","—",FG),("Battery","— %",GREEN),
                 ("X","0.00 m",FG),("Y","0.00 m",FG),("Z","0.00 m",FG),
                 ("VX","0.00",FG),("VY","0.00",FG),("VZ","0.00",FG)]
        for i, (name, val, color) in enumerate(items):
            cell = ttk.Frame(grid)
            cell.grid(row=i//3, column=i%3, sticky="w", padx=8, pady=4)
            tk.Label(cell, text=name, bg=BG, fg=SUBTLE,
                     font=("Segoe UI", 8)).pack(anchor=tk.W)
            lbl = tk.Label(cell, text=val, bg=BG, fg=color,
                           font=("Segoe UI", 13, "bold"))
            lbl.pack(anchor=tk.W)
            self.telem[name] = lbl

    # ---- keyboard -----------------------------------------------------------
    def _bind_keys(self):
        self.root.bind("<KeyPress>",   self._key_down)
        self.root.bind("<KeyRelease>", self._key_up)

    def _key_down(self, e):
        k = e.keysym.lower()
        if k == "space":
            self.on_hold(); return
        if k in ("w","s","a","d","r","f","q","e"):
            self.pressed.add(k); self._update_pilot_cmd()

    def _key_up(self, e):
        k = e.keysym.lower()
        if k in self.pressed:
            self.pressed.discard(k); self._update_pilot_cmd()

    def _update_pilot_cmd(self):
        if not self.node: return
        p = self.pressed
        n = self.node
        n.cmd_fwd   = ((1 if "w" in p else 0) - (1 if "s" in p else 0)) * PILOT_SPEED
        n.cmd_right = ((1 if "d" in p else 0) - (1 if "a" in p else 0)) * PILOT_SPEED
        n.cmd_up    = ((1 if "r" in p else 0) - (1 if "f" in p else 0)) * PILOT_SPEED
        n.cmd_yaw   = ((1 if "q" in p else 0) - (1 if "e" in p else 0)) * PILOT_YAW_RATE
        if self.pilot_on and (n.cmd_fwd or n.cmd_right or n.cmd_up or n.cmd_yaw):
            n.control_mode = "velocity"

    # ---- ROS ----------------------------------------------------------------
    def _start_ros(self):
        rclpy.init()
        self.node = DroneNode()
        self.ros_thread = threading.Thread(target=self._spin, daemon=True)
        self.ros_thread.start()
        self.log("ROS 2 node started — waiting for PX4 /fmu topics…")
        self._start_camera_switcher()

    def _start_camera_switcher(self):
        try:
            self._switcher_proc = subprocess.Popen(
                ["ros2", "run", "drone_controller", "camera_switcher"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.log("camera_switcher started (compressed relay on /drone/camera/active/…)")
        except Exception as e:
            self._switcher_proc = None
            self.log(f"camera_switcher failed to start: {e}")

    def _spin(self):
        try:
            rclpy.spin(self.node)
        except Exception as e:
            self.log(f"ROS spin stopped: {e}")

    # ---- helpers ------------------------------------------------------------
    def log(self, msg):
        ts = time.strftime("%H:%M:%S")
        try:
            self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
            self.log_text.see(tk.END)
        except tk.TclError:
            pass

    def launch_qgc(self):
        try:
            subprocess.Popen(["/home/developer/QGroundControl-x86_64.AppImage",
                              "--appimage-extract-and-run"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             cwd="/home/developer")
            self.log("QGroundControl launched.")
        except Exception as e:
            self.log(f"QGC launch failed: {e}")
            messagebox.showerror("QGC Error", str(e))

    # ---- flight commands ----------------------------------------------------
    def on_arm(self):      self.node.arm();            self.log("ARM sent")
    def on_disarm(self):   self.node.disarm();         self.log("DISARM sent")
    def on_land(self):
        if self.pilot_on: self._stop_pilot()
        self.node.land();  self.log("LAND sent")
    def on_hold(self):     self.node.hold_here();      self.log("HOLD — position locked")
    def on_rtl(self):
        if self.pilot_on: self._stop_pilot()
        self.node.rtl();   self.log("RTL sent")
    def on_takeoff(self):
        alt = self.alt_slider.get()
        n = self.node
        n.hold_x = n.x
        n.hold_y = n.y
        n.hold_z = -float(alt)
        n.hold_yaw = n.heading
        n.control_mode = "position"
        n.offboard_active = True
        self.log(f"Streaming setpoints for takeoff to {alt:.0f} m...")
        self.root.after(500, lambda: (n.engage_offboard(), n.arm(), self.log("TAKEOFF: Offboard engaged + ARMED")))
    def on_kill(self):
        if messagebox.askyesno("Confirm KILL", "Cut motors immediately? The drone will fall."):
            self.node.kill(); self.log("⛔ KILL sent")

    # ---- pilot mode ---------------------------------------------------------
    def toggle_pilot(self):
        if self.pilot_on: self._stop_pilot()
        else:             self._start_pilot()

    def _start_pilot(self):
        n = self.node
        n.cmd_fwd = n.cmd_right = n.cmd_up = n.cmd_yaw = 0.0
        n.hold_here(); n.offboard_active = True
        self.pilot_on = True
        self.pilot_btn.config(text="■  Stop Pilot Mode", style="Danger.TButton")
        self.log("Pilot Mode: streaming setpoints… engaging offboard + arming")
        self.root.after(1200, self._engage_after_stream)

    def _engage_after_stream(self):
        if not self.pilot_on: return
        self.node.engage_offboard(); self.node.arm()
        self.log("Offboard engaged + armed. Use WASD / R-F / Q-E to fly.")

    def _stop_pilot(self):
        self.pilot_on = False; self.pressed.clear()
        n = self.node
        n.cmd_fwd = n.cmd_right = n.cmd_up = n.cmd_yaw = 0.0
        n.hold_here()
        self.pilot_btn.config(text="▶  Start Pilot Mode", style="Accent.TButton")
        self.log("Pilot Mode stopped (holding position).")

    # ---- gimbal -------------------------------------------------------------
    def _gimbal_home(self):
        for name, var in self._joint_vars.items():
            var.set(0.0)
            self._joint_labels[name].config(text=" +0.0°")
            if self.node: self.node.cmd_gimbal(name, 0.0)
        self.log("Gimbal homed.")

    # ---- lens / live feed ---------------------------------------------------
    def select_lens(self, lens):
        self.active_lens = lens
        self._update_lens_buttons()
        self.stream_status.config(
            text=f"Waiting for first frame — {LENSES[lens]}…", fg=YELLOW)
        self.log(f"Lens → {LENSES[lens]}")
        if self.node:
            self.node.start_stream(lens, self._on_stream_frame)

    def _update_lens_buttons(self):
        for l, b in self.lens_buttons.items():
            b.config(style="LensActive.TButton" if l == self.active_lens
                     else "Lens.TButton")

    def _on_stream_frame(self, rgb):
        """ROS spin thread → schedule render on main thread."""
        self._last_frame = rgb
        self.root.after(0, lambda r=rgb: self._display_frame(r))

    def _display_frame(self, rgb):
        ts = time.strftime("%H:%M:%S")
        self.stream_status.config(
            text=f"{LENSES.get(self.active_lens,'')}  "
                 f"{rgb.shape[1]}×{rgb.shape[0]}  {ts}",
            fg=GREEN)
        self._render_frame(rgb)

    def _render_frame(self, rgb):
        lw = max(self.cam_label.winfo_width(),  320)
        lh = max(self.cam_label.winfo_height(), 240)
        h, w = rgb.shape[:2]
        scale = min(lw / w, lh / h)
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        pil = PILImage.fromarray(rgb).resize((nw, nh), PILImage.LANCZOS)
        self.cam_photo = ImageTk.PhotoImage(pil)
        self.cam_label.config(image=self.cam_photo, text="")

    def on_save(self):
        if self._last_frame is None:
            messagebox.showinfo("Save", "No frame received yet."); return
        ts      = time.strftime("%Y%m%d_%H%M%S")
        default = f"m4e_{self.active_lens}_{ts}.png"
        path    = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG image","*.png"),("JPEG image","*.jpg")],
            initialfile=default)
        if not path: return
        try:
            PILImage.fromarray(self._last_frame).save(path)
            self.log(f"Saved → {path}")
        except Exception as e:
            messagebox.showerror("Save error", str(e))

    # ---- telemetry ----------------------------------------------------------
    def _poll_telemetry(self):
        n = self.node
        if n:
            alive = n.connected and (time.time() - n.last_status_time < 2.0)
            self.conn_label.config(
                text="● PX4 connected"   if alive       else
                     "● PX4 signal lost" if n.connected else
                     "● Waiting for PX4…",
                fg=GREEN if alive else YELLOW)
            self.telem["Armed"].config(
                text="ARMED" if n.armed else "DISARMED",
                fg=GREEN    if n.armed else RED)
            self.telem["Mode"].config(text=n.flight_mode)
            self.telem["Battery"].config(text=f"{n.battery_percent:.0f} %")
            self.telem["X"].config(text=f"{n.x:.2f} m")
            self.telem["Y"].config(text=f"{n.y:.2f} m")
            self.telem["Z"].config(text=f"{n.z:.2f} m")
            self.telem["VX"].config(text=f"{n.vx:.2f}")
            self.telem["VY"].config(text=f"{n.vy:.2f}")
            self.telem["VZ"].config(text=f"{n.vz:.2f}")
        self.root.after(200, self._poll_telemetry)

    # ---- shutdown -----------------------------------------------------------
    def _on_close(self):
        try:
            if self.pilot_on: self._stop_pilot()
            if self.node:     self.node.stop_stream()
            if self._switcher_proc:
                self._switcher_proc.terminate()
        finally:
            self.root.after(150, self._destroy)

    def _destroy(self):
        try:
            if self.node: self.node.destroy_node()
            rclpy.shutdown()
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    DroneGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
