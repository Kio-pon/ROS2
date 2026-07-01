#!/usr/bin/env python3
"""
PX4 Drone Mission Control — a single-window ground station for PX4 SITL + ROS 2.

This node is the one and only offboard controller you should run at a time. It
unifies three things into one Tkinter window:

  1. QGroundControl toggle  - launch / kill the QGC AppImage from the GUI.
  2. Live keyboard flight    - hold W/A/S/D, U/O, J/L to fly by velocity setpoints.
  3. Mission / batch builder  - click "+ Add Step" to assemble a flight plan
                                (Take Off -> Go To -> Move -> Yaw -> Hover -> Land),
                                run / pause / stop it, and save / load it as JSON.

It speaks PX4's uORB topics over micro-XRCE-DDS using px4_msgs, exactly like the
other nodes in this package:

    IN : /fmu/in/offboard_control_mode  (OffboardControlMode)
         /fmu/in/trajectory_setpoint    (TrajectorySetpoint)
         /fmu/in/vehicle_command        (VehicleCommand)
    OUT: /fmu/out/vehicle_local_position_v1 (VehicleLocalPosition)
         /fmu/out/vehicle_status_v4         (VehicleStatus)

Frames: PX4 local frame is NED (x=North, y=East, z=Down; altitude = -z).
"Forward / Right / Up" in the mission builder are relative to the drone's current
heading at the moment the step starts.

Run it (after building the workspace):
    ros2 run drone_controller mission_control
or use the bundled launcher:  ./run_mission_control.sh
"""

from __future__ import annotations

import json
import math
import os
import shutil
import signal
import subprocess
import threading
import time
import queue
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# --- ROS 2 imports (guarded so a missing environment gives a clear message) ----
try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import (
        QoSProfile,
        ReliabilityPolicy,
        DurabilityPolicy,
        HistoryPolicy,
        qos_profile_sensor_data,
    )
    from px4_msgs.msg import (
        OffboardControlMode,
        TrajectorySetpoint,
        VehicleCommand,
        VehicleLocalPosition,
        VehicleStatus,
    )
    from sensor_msgs.msg import Image as ROSImage
except ImportError as exc:  # pragma: no cover - only triggers outside a sourced ROS env
    import sys

    sys.stderr.write(
        "\n[mission_control] Could not import ROS 2 / px4_msgs:\n"
        f"    {exc}\n\n"
        "Source your workspace first, e.g.:\n"
        "    source /opt/ros/jazzy/setup.bash\n"
        "    source ~/px4_ros2_ws/install/setup.bash\n\n"
    )
    raise

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from PIL import Image as PILImage, ImageTk
    _HAVE_PIL = True
except ImportError:
    _HAVE_PIL = False


# =============================================================================
# Constants & tunables
# =============================================================================

TOPIC_OFFBOARD_MODE = "/fmu/in/offboard_control_mode"
TOPIC_TRAJECTORY = "/fmu/in/trajectory_setpoint"
TOPIC_VEHICLE_CMD = "/fmu/in/vehicle_command"
TOPIC_LOCAL_POS = "/fmu/out/vehicle_local_position_v1"
TOPIC_STATUS = "/fmu/out/vehicle_status_v4"

CONTROL_RATE_HZ = 20.0          # setpoint / heartbeat stream rate
NAV_STATE_OFFBOARD = 14         # VehicleStatus.NAVIGATION_STATE_OFFBOARD
ARMING_STATE_ARMED = 2          # VehicleStatus.ARMING_STATE_ARMED

# Mission completion tolerances
H_TOL = 0.35                    # horizontal position tolerance (m)
V_TOL = 0.30                    # vertical position tolerance (m)
YAW_TOL = math.radians(6.0)     # yaw tolerance (rad)
HOLD_TICKS = 6                  # consecutive in-tolerance checks before "reached"
STEP_TIMEOUT_S = 60.0           # per-step safety timeout
LINK_TIMEOUT_S = 5.0            # telemetry considered stale after this

# Live keyboard tuning (matches drone_keyboard_teleop conventions)
KB_SPEED = 1.5                  # m/s commanded while a translation key is held
KB_YAW_RATE = 0.8               # rad/s commanded while a yaw key is held
KB_AUTOREPEAT_GRACE_MS = 60     # debounce X11 key-repeat release events

# Human-readable PX4 navigation states (unknown values fall back to the number)
NAV_STATE_NAMES = {
    0: "MANUAL",
    1: "ALTCTL",
    2: "POSCTL",
    3: "AUTO_MISSION",
    4: "AUTO_LOITER",
    5: "AUTO_RTL",
    10: "ACRO",
    14: "OFFBOARD",
    15: "STAB",
    17: "AUTO_TAKEOFF",
    18: "AUTO_LAND",
    19: "AUTO_FOLLOW",
    20: "AUTO_PRECLAND",
    21: "ORBIT",
    22: "AUTO_VTOL_TAKEOFF",
}

# Candidate QGroundControl locations (first existing one wins). $QGC_PATH overrides.
QGC_CANDIDATES = [
    "~/Downloads/QGroundControl.AppImage",
    "~/Downloads/QGroundControl-x86_64.AppImage",
    "~/QGroundControl.AppImage",
    "~/Apps/QGroundControl.AppImage",
]

# Dark theme palette (modern, GitHub-dark inspired)
BG = "#0d1117"
PANEL = "#161b22"
ACCENT = "#58a6ff"
OK = "#3fb950"
WARN = "#d29922"
DANGER = "#f85149"
TEXT = "#e6edf3"
MUTED = "#8b949e"


def wrap_pi(angle: float) -> float:
    """Wrap an angle to [-pi, pi]."""
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


# =============================================================================
# Mission model
# =============================================================================

class StepType(str, Enum):
    ARM = "ARM"
    DISARM = "DISARM"
    TAKEOFF = "TAKEOFF"
    MOVE = "MOVE"        # relative to heading: forward / right / up (m)
    GOTO = "GOTO"        # absolute NED: north / east / altitude (m)
    YAW = "YAW"          # heading in degrees (absolute or relative)
    HOVER = "HOVER"      # hold position for N seconds
    LAND = "LAND"
    RTL = "RTL"


@dataclass
class MissionStep:
    type: StepType
    params: dict = field(default_factory=dict)

    def label(self) -> str:
        p = self.params
        t = self.type
        if t == StepType.TAKEOFF:
            return f"Take off to {p.get('altitude', 2.5):.1f} m"
        if t == StepType.MOVE:
            return (f"Move  fwd {p.get('forward', 0):+.1f}  "
                    f"right {p.get('right', 0):+.1f}  up {p.get('up', 0):+.1f} m")
        if t == StepType.GOTO:
            return (f"Go to  N {p.get('north', 0):+.1f}  "
                    f"E {p.get('east', 0):+.1f}  alt {p.get('altitude', 0):.1f} m")
        if t == StepType.YAW:
            mode = "by" if p.get("relative") else "to"
            return f"Yaw {mode} {p.get('heading', 0):.0f}°"
        if t == StepType.HOVER:
            return f"Hover for {p.get('seconds', 3):.0f} s"
        if t == StepType.ARM:
            return "Arm motors"
        if t == StepType.DISARM:
            return "Disarm motors"
        if t == StepType.LAND:
            return "Land"
        if t == StepType.RTL:
            return "Return to launch (RTL)"
        return str(t)

    def to_dict(self) -> dict:
        return {"type": self.type.value, "params": self.params}

    @staticmethod
    def from_dict(d: dict) -> "MissionStep":
        return MissionStep(StepType(d["type"]), dict(d.get("params", {})))


# =============================================================================
# ROS 2 node: telemetry in, setpoints + commands out
# =============================================================================

class MissionControlNode(Node):
    """Owns the offboard setpoint stream and exposes thread-safe commands."""

    def __init__(self, log_cb):
        super().__init__("mission_control")
        self._log = log_cb

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        # Publishers
        self._pub_mode = self.create_publisher(OffboardControlMode, TOPIC_OFFBOARD_MODE, qos)
        self._pub_traj = self.create_publisher(TrajectorySetpoint, TOPIC_TRAJECTORY, qos)
        self._pub_cmd = self.create_publisher(VehicleCommand, TOPIC_VEHICLE_CMD, qos)

        # Subscribers
        self.create_subscription(VehicleLocalPosition, TOPIC_LOCAL_POS, self._on_local_pos, qos)
        self.create_subscription(VehicleStatus, TOPIC_STATUS, self._on_status, qos)

        # --- Camera ---
        self.camera_sub = None
        self.latest_frame = None
        self.camera_topic = None
        self.create_timer(2.0, self._check_camera_topic)

        # --- Telemetry (each field assigned atomically; readers take a snapshot) ---
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.heading = 0.0
        self.vx = self.vy = self.vz = 0.0
        self.xy_valid = False
        self.z_valid = False
        self.armed = False
        self.nav_state = 0
        self._last_status_t = 0.0
        self._last_pos_t = 0.0

        # --- Setpoint state. Reassigned wholesale so the timer reads it atomically. ---
        # ('idle')                                  -> heartbeat only, no setpoint
        # ('position', n, e, d, yaw)                -> position setpoint
        # ('velocity', vn, ve, vd, yawspeed)        -> velocity setpoint
        self._sp = ("idle",)

        self.create_timer(1.0 / CONTROL_RATE_HZ, self._on_timer)

    # ---- Subscriptions -------------------------------------------------------
    def _on_local_pos(self, msg: VehicleLocalPosition):
        self.x, self.y, self.z = msg.x, msg.y, msg.z
        self.vx, self.vy, self.vz = msg.vx, msg.vy, msg.vz
        self.heading = msg.heading
        self.xy_valid = msg.xy_valid
        self.z_valid = msg.z_valid
        self._last_pos_t = time.monotonic()

    def _on_status(self, msg: VehicleStatus):
        self.armed = msg.arming_state == ARMING_STATE_ARMED
        self.nav_state = msg.nav_state
        self._last_status_t = time.monotonic()

    # ---- Camera --------------------------------------------------------------
    def _check_camera_topic(self):
        if self.camera_sub is not None:
            return
        # 1. Try environment variable first
        env_topic = os.environ.get("CAM_TOPIC")
        if env_topic:
            self.camera_topic = env_topic
            self._log(f"Using camera topic from env: {env_topic}")
            self.camera_sub = self.create_subscription(
                ROSImage, env_topic, self._on_image, qos_profile_sensor_data)
            return

        # 2. Prefer /world/ topic first to avoid matching /robot1/ etc.
        candidates = []
        for name, types in self.get_topic_names_and_types():
            if "sensor_msgs/msg/Image" in types and "depth" not in name.lower():
                candidates.append(name)
        
        if not candidates:
            return
            
        # Prioritize topics containing "world" or "x500_mono_cam"
        match = None
        for c in candidates:
            if "world" in c.lower() or "x500_mono_cam" in c.lower():
                match = c
                break
        if match is None:
            match = candidates[0]
            
        self.camera_topic = match
        self._log(f"Auto-detected camera topic: {match}")
        self.camera_sub = self.create_subscription(
            ROSImage, match, self._on_image, qos_profile_sensor_data)

    def _on_image(self, msg: ROSImage):
        self.latest_frame = msg

    def get_latest_frame_rgb(self):
        msg = self.latest_frame
        if not msg:
            return None
        enc = msg.encoding.lower()
        if enc in ("rgb8", "bgr8"):
            channels = 3
        elif enc in ("mono8", "8uc1"):
            channels = 1
        else:
            return None
        
        row_bytes = msg.width * channels
        data = bytes(msg.data)
        if msg.step != row_bytes:
            data = b"".join(data[r * msg.step: r * msg.step + row_bytes] for r in range(msg.height))
            
        if channels == 1:
            data = bytes(b for v in data for b in (v, v, v))
        elif enc == "bgr8":
            ba = bytearray(data)
            ba[0::3], ba[2::3] = ba[2::3], ba[0::3]
            data = bytes(ba)
        return (msg.width, msg.height, data)

    # ---- Derived telemetry ---------------------------------------------------
    @property
    def altitude(self) -> float:
        return -self.z

    @property
    def ground_speed(self) -> float:
        return math.hypot(self.vx, self.vy)

    def link_ok(self) -> bool:
        return (time.monotonic() - self._last_status_t) < LINK_TIMEOUT_S

    def in_offboard(self) -> bool:
        return self.nav_state == NAV_STATE_OFFBOARD

    # ---- Setpoint commands (called from GUI / executor threads) --------------
    def set_idle(self):
        self._sp = ("idle",)

    def set_position(self, north: float, east: float, down: float, yaw: float):
        self._sp = ("position", float(north), float(east), float(down), float(yaw))

    def set_velocity(self, vn: float, ve: float, vd: float, yawspeed: float):
        self._sp = ("velocity", float(vn), float(ve), float(vd), float(yawspeed))

    # ---- High-level vehicle commands ----------------------------------------
    def _publish_cmd(self, command, p1=0.0, p2=0.0, p3=0.0):
        msg = VehicleCommand()
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        msg.command = command
        msg.param1 = float(p1)
        msg.param2 = float(p2)
        msg.param3 = float(p3)
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        self._pub_cmd.publish(msg)

    def arm(self):
        self._log("Arming motors...")
        self._publish_cmd(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0)

    def disarm(self):
        self._log("Disarming motors...")
        self._publish_cmd(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 0.0)

    def engage_offboard(self):
        self._log("Engaging OFFBOARD mode...")
        self._publish_cmd(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1.0, 6.0)

    def land(self):
        self._log("Landing...")
        self._publish_cmd(VehicleCommand.VEHICLE_CMD_NAV_LAND)

    def rtl(self):
        self._log("Return to launch...")
        self._publish_cmd(VehicleCommand.VEHICLE_CMD_NAV_RETURN_TO_LAUNCH)

    # ---- Stream loop ---------------------------------------------------------
    def _on_timer(self):
        sp = self._sp  # atomic read of the whole tuple
        mode = sp[0]

        # OffboardControlMode heartbeat must match the kind of setpoint we send.
        hb = OffboardControlMode()
        hb.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        hb.position = mode == "position"
        hb.velocity = mode == "velocity"
        hb.acceleration = False
        hb.attitude = False
        hb.body_rate = False

        if mode == "idle":
            # Still publish a (position) heartbeat so a fresh OFFBOARD engage is possible.
            hb.position = True
            self._pub_mode.publish(hb)
            return

        self._pub_mode.publish(hb)

        traj = TrajectorySetpoint()
        traj.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        nan = float("nan")
        if mode == "position":
            _, n, e, d, yaw = sp
            traj.position = [n, e, d]
            traj.velocity = [nan, nan, nan]
            traj.yaw = yaw
            traj.yawspeed = nan
        else:  # velocity
            _, vn, ve, vd, yawspeed = sp
            traj.position = [nan, nan, nan]
            traj.velocity = [vn, ve, vd]
            traj.yaw = nan
            traj.yawspeed = yawspeed
        self._pub_traj.publish(traj)


# =============================================================================
# Mission executor: sequences steps in a worker thread
# =============================================================================

class MissionExecutor(threading.Thread):
    """Runs a list of MissionSteps without blocking the GUI or the ROS stream."""

    def __init__(self, node: MissionControlNode, steps, log_cb, progress_cb, done_cb):
        super().__init__(daemon=True)
        self.node = node
        self.steps = steps
        self._log = log_cb
        self._progress = progress_cb      # progress_cb(index, state)  state in {running, done, fail}
        self._done = done_cb              # done_cb(success: bool, message: str)
        # NOTE: do not name these `_stop` — that shadows threading.Thread._stop()
        # and breaks is_alive(). Suffix avoids the collision.
        self._stop_evt = threading.Event()
        self._pause_evt = threading.Event()
        # The yaw we last commanded, so translation steps keep facing the same way.
        self._yaw_sp = 0.0

    # ---- External controls ---------------------------------------------------
    def stop(self):
        self._stop_evt.set()

    def pause(self):
        self._pause_evt.set()

    def resume(self):
        self._pause_evt.clear()

    # ---- Helpers -------------------------------------------------------------
    def _sleep(self, seconds: float) -> bool:
        """Sleep in small slices; return False if asked to stop."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self._stop_evt.is_set():
                return False
            time.sleep(0.02)
        return not self._stop_evt.is_set()

    def _wait_paused(self):
        while self._pause_evt.is_set() and not self._stop_evt.is_set():
            time.sleep(0.05)

    def _ensure_offboard(self) -> bool:
        """Stream a hold setpoint, switch to OFFBOARD and arm if needed."""
        n = self.node
        if not n.link_ok():
            self._log("No telemetry link - is the simulator + DDS agent running?")
            return False

        # Hold at the current spot while we warm up the stream.
        self._yaw_sp = n.heading
        n.set_position(n.x, n.y, n.z, self._yaw_sp)

        if n.in_offboard() and n.armed:
            return True

        # PX4 needs a brief setpoint stream before it will accept OFFBOARD.
        if not self._sleep(1.2):
            return False
        n.engage_offboard()
        if not self._sleep(0.3):
            return False
        n.arm()

        # Wait for confirmation.
        deadline = time.monotonic() + 6.0
        while time.monotonic() < deadline:
            if self._stop_evt.is_set():
                return False
            if n.in_offboard() and n.armed:
                return True
            time.sleep(0.05)
        self._log("WARN: timed out waiting for OFFBOARD + armed; continuing anyway.")
        return True

    def _fly_to(self, n_t: float, e_t: float, d_t: float, yaw_t: float) -> bool:
        """Command a position setpoint and wait until it is reached (or times out)."""
        self._yaw_sp = yaw_t
        self.node.set_position(n_t, e_t, d_t, yaw_t)
        deadline = time.monotonic() + STEP_TIMEOUT_S
        in_tol = 0
        while True:
            if self._stop_evt.is_set():
                return False
            self._wait_paused()
            nd = self.node
            dh = math.hypot(nd.x - n_t, nd.y - e_t)
            dv = abs(nd.z - d_t)
            dyaw = abs(wrap_pi(nd.heading - yaw_t))
            if dh < H_TOL and dv < V_TOL and dyaw < YAW_TOL:
                in_tol += 1
                if in_tol >= HOLD_TICKS:
                    return True
            else:
                in_tol = 0
            if time.monotonic() > deadline:
                self._log(f"WARN: step timed out "
                          f"(dh={dh:.2f} dv={dv:.2f} dyaw={math.degrees(dyaw):.0f}°); moving on.")
                return True
            time.sleep(0.05)

    def _wait_disarm(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._stop_evt.is_set():
                return False
            if not self.node.armed:
                return True
            time.sleep(0.1)
        return True

    # ---- Per-step execution --------------------------------------------------
    def _run_step(self, step: MissionStep) -> bool:
        n = self.node
        p = step.params
        t = step.type

        if t == StepType.ARM:
            if not self._ensure_offboard():
                return False
            return True

        if t == StepType.DISARM:
            n.disarm()
            return self._sleep(1.0)

        if t == StepType.TAKEOFF:
            if not self._ensure_offboard():
                return False
            alt = float(p.get("altitude", 2.5))
            return self._fly_to(n.x, n.y, -alt, self._yaw_sp)

        if t == StepType.MOVE:
            if not self._ensure_offboard():
                return False
            fwd = float(p.get("forward", 0.0))
            right = float(p.get("right", 0.0))
            up = float(p.get("up", 0.0))
            h = self._yaw_sp  # face the way we are already commanded to face
            dn = fwd * math.cos(h) - right * math.sin(h)
            de = fwd * math.sin(h) + right * math.cos(h)
            return self._fly_to(n.x + dn, n.y + de, n.z - up, h)

        if t == StepType.GOTO:
            if not self._ensure_offboard():
                return False
            north = float(p.get("north", 0.0))
            east = float(p.get("east", 0.0))
            alt = float(p.get("altitude", 0.0))
            return self._fly_to(north, east, -alt, self._yaw_sp)

        if t == StepType.YAW:
            if not self._ensure_offboard():
                return False
            deg = float(p.get("heading", 0.0))
            if p.get("relative"):
                target = wrap_pi(self._yaw_sp + math.radians(deg))
            else:
                target = wrap_pi(math.radians(deg))
            # Yaw in place at the current position.
            return self._fly_to(n.x, n.y, n.z, target)

        if t == StepType.HOVER:
            secs = float(p.get("seconds", 3.0))
            # Keep streaming the current hold position while we wait.
            n.set_position(n.x, n.y, n.z, self._yaw_sp)
            return self._sleep(secs)

        if t == StepType.LAND:
            n.land()
            if not self._sleep(0.5):
                return False
            n.set_idle()  # PX4 owns the descent now; stop fighting it with setpoints
            self._wait_disarm(30.0)
            return not self._stop_evt.is_set()

        if t == StepType.RTL:
            n.rtl()
            if not self._sleep(0.5):
                return False
            n.set_idle()
            self._wait_disarm(60.0)
            return not self._stop_evt.is_set()

        self._log(f"Unknown step type: {t}")
        return True

    # ---- Thread body ---------------------------------------------------------
    def run(self):
        success = True
        message = "Mission complete."
        try:
            for i, step in enumerate(self.steps):
                if self._stop_evt.is_set():
                    success, message = False, "Mission stopped."
                    break
                self._wait_paused()
                self._log(f"[{i + 1}/{len(self.steps)}] {step.label()}")
                self._progress(i, "running")
                ok = self._run_step(step)
                if self._stop_evt.is_set():
                    self._progress(i, "fail")
                    success, message = False, "Mission stopped."
                    break
                if not ok:
                    self._progress(i, "fail")
                    success, message = False, f"Step {i + 1} failed."
                    break
                self._progress(i, "done")
            else:
                # Loop finished without break -> safe-state the stream.
                self.node.set_idle()
        except Exception as exc:  # never let a worker thread die silently
            success, message = False, f"Mission error: {exc}"
            self._log(message)
            self.node.set_idle()
        finally:
            self._done(success, message)


# =============================================================================
# Step editor dialog
# =============================================================================

class StepDialog(tk.Toplevel):
    """Modal dialog to create or edit a single MissionStep."""

    # field spec per type: (key, label, default)
    FIELDS = {
        StepType.TAKEOFF: [("altitude", "Altitude (m)", 2.5)],
        StepType.MOVE: [("forward", "Forward + / Back - (m)", 0.0),
                        ("right", "Right + / Left - (m)", 0.0),
                        ("up", "Up + / Down - (m)", 0.0)],
        StepType.GOTO: [("north", "North (m)", 0.0),
                        ("east", "East (m)", 0.0),
                        ("altitude", "Altitude (m)", 2.5)],
        StepType.YAW: [("heading", "Heading (deg)", 0.0)],
        StepType.HOVER: [("seconds", "Duration (s)", 3.0)],
        StepType.ARM: [],
        StepType.DISARM: [],
        StepType.LAND: [],
        StepType.RTL: [],
    }

    def __init__(self, parent, step: Optional[MissionStep] = None):
        super().__init__(parent)
        self.title("Edit step" if step else "Add step")
        self.configure(bg=PANEL)
        self.resizable(False, False)
        self.result: Optional[MissionStep] = None
        self._entries = {}
        self._relative_var = tk.BooleanVar(value=bool(step.params.get("relative")) if step else False)

        self.transient(parent)
        self.grab_set()

        tk.Label(self, text="Action", bg=PANEL, fg=ACCENT,
                 font=("Helvetica", 10, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        self._type_var = tk.StringVar(value=(step.type.value if step else StepType.TAKEOFF.value))
        self._type_combo = ttk.Combobox(
            self, textvariable=self._type_var, state="readonly",
            values=[t.value for t in StepType], width=18)
        self._type_combo.grid(row=0, column=1, sticky="w", padx=12, pady=(12, 4))
        self._type_combo.bind("<<ComboboxSelected>>", lambda _e: self._rebuild_fields())

        self._fields_frame = tk.Frame(self, bg=PANEL)
        self._fields_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=4)

        btns = tk.Frame(self, bg=PANEL)
        btns.grid(row=2, column=0, columnspan=2, pady=12)
        ttk.Button(btns, text="OK", command=self._on_ok).pack(side="left", padx=6)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="left", padx=6)

        self._initial = step
        self._rebuild_fields()
        self.bind("<Return>", lambda _e: self._on_ok())
        self.bind("<Escape>", lambda _e: self.destroy())

    def _rebuild_fields(self):
        for w in self._fields_frame.winfo_children():
            w.destroy()
        self._entries.clear()

        t = StepType(self._type_var.get())
        specs = self.FIELDS.get(t, [])
        for r, (key, label, default) in enumerate(specs):
            tk.Label(self._fields_frame, text=label, bg=PANEL, fg=TEXT,
                     font=("Helvetica", 10)).grid(row=r, column=0, sticky="w", padx=12, pady=4)
            var = tk.StringVar()
            init = (self._initial.params.get(key, default)
                    if self._initial and self._initial.type == t else default)
            var.set(str(init))
            ent = ttk.Entry(self._fields_frame, textvariable=var, width=12)
            ent.grid(row=r, column=1, sticky="w", padx=12, pady=4)
            self._entries[key] = var

        if t == StepType.YAW:
            tk.Checkbutton(
                self._fields_frame, text="Relative (turn by, not turn to)",
                variable=self._relative_var, bg=PANEL, fg=TEXT, selectcolor=BG,
                activebackground=PANEL, activeforeground=TEXT,
            ).grid(row=len(specs), column=0, columnspan=2, sticky="w", padx=12, pady=4)

        if not specs:
            tk.Label(self._fields_frame, text="(no parameters)", bg=PANEL, fg=MUTED,
                     font=("Helvetica", 9, "italic")).grid(row=0, column=0, padx=12, pady=8)

    def _on_ok(self):
        t = StepType(self._type_var.get())
        params = {}
        try:
            for key, var in self._entries.items():
                params[key] = float(var.get())
        except ValueError:
            messagebox.showerror("Invalid value", "All fields must be numbers.", parent=self)
            return
        if t == StepType.YAW:
            params["relative"] = self._relative_var.get()
        self.result = MissionStep(t, params)
        self.destroy()


# =============================================================================
# Main application window
# =============================================================================

class MissionControlApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PX4 Drone Mission Control")
        self.root.geometry("950x660")
        self.root.configure(bg=BG)

        self.log_queue: "queue.Queue[str]" = queue.Queue()
        self.steps: list[MissionStep] = []
        self.executor: Optional[MissionExecutor] = None
        self.qgc_proc: Optional[subprocess.Popen] = None

        # Live-keyboard state
        self.keyboard_active = False
        self._keys_down: set[str] = set()
        self._pending_release: dict[str, str] = {}  # key -> after() id
        self.camera_follow_active = True

        self._build_styles()
        self._build_layout()

        # Start ROS in the background.
        self.node: Optional[MissionControlNode] = None
        self._ros_stop = threading.Event()
        self._ros_thread = threading.Thread(target=self._ros_spin, daemon=True)
        self._ros_thread.start()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_log()
        self._refresh_telemetry()

    # ---- Styling -------------------------------------------------------------
    def _build_styles(self):
        FONT = "Ubuntu"  # modern sans on Ubuntu; Tk falls back if absent
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", font=(FONT, 9, "bold"), padding=6,
                        background="#21262d", foreground=TEXT, borderwidth=0)
        style.map("TButton",
                  background=[("active", "#30363d"), ("pressed", ACCENT)],
                  foreground=[("pressed", BG)])
        style.configure("TEntry", fieldbackground="#21262d", foreground=TEXT,
                        bordercolor="#30363d", insertcolor=TEXT, padding=3)
        style.configure("TCombobox", fieldbackground="#21262d", background="#21262d",
                        foreground=TEXT, arrowcolor=TEXT, bordercolor="#30363d")
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL,
                        foreground=TEXT, rowheight=24, font=(FONT, 9), borderwidth=0)
        style.configure("Treeview.Heading", font=(FONT, 9, "bold"),
                        background="#21262d", foreground=MUTED, relief="flat")
        style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", BG)])

    def _section(self, parent, title):
        frame = tk.LabelFrame(parent, text=title, bg=PANEL, fg=ACCENT,
                              font=("Helvetica", 10, "bold"), labelanchor="nw", bd=2)
        return frame

    # ---- Layout --------------------------------------------------------------
    def _build_layout(self):
        header = tk.Frame(self.root, bg="#010409", height=40)
        header.pack(fill="x")
        tk.Label(header, text="\U0001F6F8  PX4 Drone Mission Control",
                 font=("Helvetica", 14, "bold"), fg=TEXT, bg="#010409").pack(side="left", padx=12, pady=6)
        self.lbl_link = tk.Label(header, text="LINK: —", font=("Helvetica", 10, "bold"),
                                 fg=MUTED, bg="#010409")
        self.lbl_link.pack(side="right", padx=12)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=6, pady=6)

        left = tk.Frame(body, bg=BG, width=340)
        left.pack(side="left", fill="y", padx=(0, 6))
        left.pack_propagate(False)
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        self._build_telemetry(left)
        self._build_manual(left)
        self._build_keyboard(left)
        self._build_camera(left)
        self._build_qgc(left)
        self._build_mission(right)
        self._build_log(right)

    def _build_telemetry(self, parent):
        sec = self._section(parent, "Telemetry")
        sec.pack(fill="x", pady=(0, 4))
        grid = tk.Frame(sec, bg=PANEL)
        grid.pack(fill="x", padx=6, pady=4)

        self.tele = {}
        rows = [("status", "Status"), ("mode", "Flight mode"), ("alt", "Altitude"),
                ("north", "North (X)"), ("east", "East (Y)"),
                ("heading", "Heading"), ("speed", "Ground speed")]
        for r, (key, label) in enumerate(rows):
            tk.Label(grid, text=label, bg=PANEL, fg=MUTED, font=("Helvetica", 9),
                     anchor="w", width=12).grid(row=r, column=0, sticky="w", pady=1)
            val = tk.Label(grid, text="—", bg=PANEL, fg=TEXT,
                           font=("Consolas", 10, "bold"), anchor="w")
            val.grid(row=r, column=1, sticky="w", pady=1)
            self.tele[key] = val

    def _build_manual(self, parent):
        sec = self._section(parent, "Manual commands")
        sec.pack(fill="x", pady=4)
        grid = tk.Frame(sec, bg=PANEL)
        grid.pack(fill="x", padx=4, pady=4)
        buttons = [
            ("ARM", DANGER, lambda: self._guard(self._cmd_arm)),
            ("DISARM", "#6c757d", lambda: self._guard(lambda: self.node.disarm())),
            ("TAKEOFF 2.5m", OK, lambda: self._guard(self._cmd_takeoff)),
            ("LAND", WARN, lambda: self._guard(self._cmd_land)),
            ("RTL", "#f4a261", lambda: self._guard(self._cmd_rtl)),
            ("HOLD / STOP", "#457b9d", lambda: self._guard(self._cmd_hold)),
        ]
        for i, (text, color, cmd) in enumerate(buttons):
            b = tk.Button(grid, text=text, command=cmd, bg=color, fg="white",
                          activebackground=color, font=("Helvetica", 9, "bold"),
                          relief="flat", bd=0, padx=2, pady=4)
            b.grid(row=i // 2, column=i % 2, sticky="ew", padx=2, pady=2)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        # Camera tracking follow toggle (span both columns)
        self.cam_follow_btn = tk.Button(
            grid, text="Camera Track: ON (Follow)",
            command=self._toggle_camera_follow,
            bg=ACCENT, fg="white", activebackground=ACCENT,
            font=("Helvetica", 9, "bold"), relief="flat", bd=0, padx=2, pady=4
        )
        self.cam_follow_btn.grid(row=3, column=0, columnspan=2, sticky="ew", padx=2, pady=(6, 2))

    def _toggle_camera_follow(self):
        self.camera_follow_active = not self.camera_follow_active
        model_name = os.environ.get("PX4_SIM_MODEL", "gz_x500_mono_cam")
        if model_name.startswith("gz_"):
            model_instance = model_name[3:] + "_0"
        else:
            model_instance = model_name + "_0"
            
        if self.camera_follow_active:
            cmd = [
                "gz", "topic", "-t", "/gui/track",
                "-m", "gz.msgs.CameraTrack",
                "-p", f"track_mode: FOLLOW, follow_target: {{name: '{model_instance}'}}, follow_offset: {{x: -2.0, y: -2.0, z: 2.0}}, follow_pgain: 1.0, track_pgain: 1.0"
            ]
            self.cam_follow_btn.config(text="Camera Track: ON (Follow)", bg=ACCENT, activebackground=ACCENT)
            self.log(f"Enabling Gazebo camera follow for {model_instance}...")
        else:
            cmd = [
                "gz", "topic", "-t", "/gui/track",
                "-m", "gz.msgs.CameraTrack",
                "-p", "track_mode: NONE"
            ]
            self.cam_follow_btn.config(text="Camera Track: OFF (Free Movement)", bg="#45475a", activebackground="#45475a")
            self.log("Disabling Gazebo camera follow (free movement active)...")
            
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            self.log(f"Failed to set camera tracking: {exc}")

    def _build_keyboard(self, parent):
        sec = self._section(parent, "Live keyboard flight")
        sec.pack(fill="x", pady=4)
        self.kb_btn = tk.Button(sec, text="Enable keyboard control  (OFF)",
                                command=self._toggle_keyboard, bg="#6c757d", fg="white",
                                font=("Helvetica", 9, "bold"), relief="flat", pady=4)
        self.kb_btn.pack(fill="x", padx=4, pady=(4, 2))
        hint = ("W/S forward·back   A/D left·right\n"
                "U/O up·down   J/L yaw   Space = stop\n"
                "Hold a key to move; release to stop.")
        tk.Label(sec, text=hint, bg=PANEL, fg=MUTED, justify="left",
                 font=("Consolas", 8)).pack(anchor="w", padx=6, pady=(0, 4))

    def _build_camera(self, parent):
        sec = self._section(parent, "Live Camera Feed")
        sec.pack(fill="x", pady=4)
        
        row = tk.Frame(sec, bg=PANEL)
        row.pack(fill="x", padx=4, pady=(4, 2))
        
        self.cam_btn = tk.Button(row, text="Show Camera", command=self._toggle_camera,
                                 bg=OK, fg="white", font=("Helvetica", 9, "bold"),
                                 relief="flat", pady=2, width=12)
        self.cam_btn.pack(side="left")
        
        self.cam_lbl = tk.Label(row, text="Waiting for feed...", bg=PANEL, fg=MUTED, font=("Helvetica", 8))
        self.cam_lbl.pack(side="left", padx=6)
        
        self.cam_canvas = tk.Canvas(sec, bg="#000000", height=0, highlightthickness=0)
        self.camera_active = False
        self._photo_image = None

    def _toggle_camera(self):
        self.camera_active = not self.camera_active
        if self.camera_active:
            self.cam_btn.config(text="Hide Camera", bg=WARN)
            self.cam_canvas.pack(fill="x", padx=4, pady=(0, 4))
            self.cam_canvas.config(height=200)
            self._update_camera_frame()
        else:
            self.cam_btn.config(text="Show Camera", bg=OK)
            self.cam_canvas.pack_forget()

    def _update_camera_frame(self):
        if not self.camera_active:
            return
            
        n = self.node
        # Distinguish failure modes so it's obvious WHICH part is missing
        # (this is the cross-machine "blank feed" diagnostic).
        if not _HAVE_PIL:
            self.cam_lbl.config(text="Install python3-pil.imagetk", fg=WARN)
        elif n is None:
            self.cam_lbl.config(text="Starting...", fg=MUTED)
        elif n.camera_topic is None:
            self.cam_lbl.config(text="No camera topic - is the image bridge running?", fg=WARN)
        elif n.latest_frame is None:
            self.cam_lbl.config(text="Topic found, no frames yet (GPU/render?)", fg=WARN)
        else:
            frame_data = n.get_latest_frame_rgb()
            if frame_data:
                w, h, rgb = frame_data
                img = PILImage.frombytes("RGB", (w, h), rgb)
                target_w = 320
                target_h = int(h * (target_w / w))
                img = img.resize((target_w, target_h))

                self.cam_canvas.config(height=target_h)
                self._photo_image = ImageTk.PhotoImage(img)
                self.cam_canvas.create_image(target_w // 2, target_h // 2,
                                             anchor="center", image=self._photo_image)
                self.cam_lbl.config(text=f"Live ({w}x{h})", fg=OK)
            else:
                self.cam_lbl.config(text="Unsupported encoding", fg=WARN)

        self.root.after(33, self._update_camera_frame)

    def _build_qgc(self, parent):
        sec = self._section(parent, "QGroundControl")
        sec.pack(fill="x", pady=4)
        row = tk.Frame(sec, bg=PANEL)
        row.pack(fill="x", padx=4, pady=4)
        tk.Label(row, text="Path", bg=PANEL, fg=MUTED, font=("Helvetica", 9)).pack(side="left")
        self.qgc_path_var = tk.StringVar(value=self._detect_qgc())
        ttk.Entry(row, textvariable=self.qgc_path_var).pack(side="left", fill="x", expand=True, padx=4)
        self.qgc_btn = tk.Button(sec, text="Launch QGroundControl", command=self._toggle_qgc,
                                 bg=OK, fg="white", font=("Helvetica", 9, "bold"),
                                 relief="flat", pady=4)
        self.qgc_btn.pack(fill="x", padx=4, pady=(0, 4))

    def _build_mission(self, parent):
        sec = self._section(parent, "Mission / batch builder")
        sec.pack(fill="both", expand=True, pady=(0, 4))

        bar = tk.Frame(sec, bg=PANEL)
        bar.pack(fill="x", padx=4, pady=(4, 2))
        for text, cmd in [("+ Add Step", self._add_step), ("Edit", self._edit_step),
                          ("Delete", self._delete_step), ("▲ Up", lambda: self._move_step(-1)),
                          ("▼ Down", lambda: self._move_step(1)), ("Clear", self._clear_steps)]:
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        ttk.Button(bar, text="Load", command=self._load_mission).pack(side="right", padx=2)
        ttk.Button(bar, text="Save", command=self._save_mission).pack(side="right", padx=2)

        self.tree = ttk.Treeview(sec, columns=("step",), show="tree", selectmode="browse", height=8)
        self.tree.column("#0", width=30, anchor="center", stretch=False)
        self.tree.column("step", anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=2)
        self.tree.tag_configure("running", background="#3d5a40")
        self.tree.tag_configure("done", background="#264653")
        self.tree.tag_configure("fail", background="#5a2a2a")
        self.tree.bind("<Double-1>", lambda _e: self._edit_step())

        run_bar = tk.Frame(sec, bg=PANEL)
        run_bar.pack(fill="x", padx=4, pady=(2, 6))
        self.run_btn = tk.Button(run_bar, text="▶ Run mission", command=self._run_mission,
                                 bg=OK, fg="white", font=("Helvetica", 10, "bold"),
                                 relief="flat", pady=6)
        self.run_btn.pack(side="left", fill="x", expand=True, padx=2)
        self.pause_btn = tk.Button(run_bar, text="❚❚ Pause", command=self._toggle_pause,
                                   bg="#457b9d", fg="white", font=("Helvetica", 10, "bold"),
                                   relief="flat", pady=6, state="disabled")
        self.pause_btn.pack(side="left", fill="x", expand=True, padx=2)
        self.stop_btn = tk.Button(run_bar, text="■ Stop", command=self._stop_mission,
                                  bg=DANGER, fg="white", font=("Helvetica", 10, "bold"),
                                  relief="flat", pady=6, state="disabled")
        self.stop_btn.pack(side="left", fill="x", expand=True, padx=2)

    def _build_log(self, parent):
        sec = self._section(parent, "Log")
        sec.pack(fill="both", expand=True)
        self.log_text = tk.Text(sec, height=6, bg="#15151c", fg="#c8d3e0",
                                font=("Consolas", 8), relief="flat", wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)
        self.log_text.configure(state="disabled")

    # ---- ROS lifecycle -------------------------------------------------------
    def _ros_spin(self):
        rclpy.init()
        self.node = MissionControlNode(self.log)
        self.log("ROS 2 node started. Waiting for telemetry...")
        try:
            while rclpy.ok() and not self._ros_stop.is_set():
                rclpy.spin_once(self.node, timeout_sec=0.1)
        except Exception as exc:  # pragma: no cover
            self.log(f"ROS spin error: {exc}")
        finally:
            if self.node is not None:
                self.node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()

    # ---- Logging -------------------------------------------------------------
    def log(self, message: str):
        """Thread-safe: any thread may call this."""
        self.log_queue.put(f"[{time.strftime('%H:%M:%S')}] {message}")

    def _poll_log(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                self.log_text.configure(state="normal")
                self.log_text.insert("end", line + "\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(120, self._poll_log)

    # ---- Telemetry refresh ---------------------------------------------------
    def _refresh_telemetry(self):
        n = self.node
        if n is not None:
            link = n.link_ok()
            self.lbl_link.config(text="LINK: OK" if link else "LINK: NO SIGNAL",
                                 fg=OK if link else DANGER)
            self.tele["status"].config(text="ARMED" if n.armed else "DISARMED",
                                       fg=OK if n.armed else WARN)
            self.tele["mode"].config(text=NAV_STATE_NAMES.get(n.nav_state, str(n.nav_state)))
            self.tele["alt"].config(text=f"{n.altitude:6.2f} m")
            self.tele["north"].config(text=f"{n.x:6.2f} m")
            self.tele["east"].config(text=f"{n.y:6.2f} m")
            self.tele["heading"].config(text=f"{math.degrees(n.heading):6.1f}°")
            self.tele["speed"].config(text=f"{n.ground_speed:5.2f} m/s")
        # Live keyboard: recompute the velocity setpoint from currently-held keys.
        if self.keyboard_active and n is not None:
            self._apply_keyboard_velocity()
        self.root.after(100, self._refresh_telemetry)

    # ---- Guard ---------------------------------------------------------------
    def _guard(self, fn):
        if self.node is None:
            self.log("Node not ready yet.")
            return
        if self.executor and self.executor.is_alive():
            self.log("A mission is running - stop it before sending manual commands.")
            return
        fn()

    # ---- Manual command helpers ---------------------------------------------
    def _cmd_arm(self):
        self.node.set_position(self.node.x, self.node.y, self.node.z, self.node.heading)
        self.node.engage_offboard()
        self.root.after(400, self.node.arm)

    def _cmd_takeoff(self):
        n = self.node
        n.set_position(n.x, n.y, n.z, n.heading)
        n.engage_offboard()

        def _arm_then_climb():
            n.arm()
            self.root.after(600, lambda: n.set_position(n.x, n.y, -2.5, n.heading))
        self.root.after(400, _arm_then_climb)

    def _cmd_land(self):
        self.node.land()
        self.root.after(600, self.node.set_idle)

    def _cmd_rtl(self):
        self.node.rtl()
        self.root.after(600, self.node.set_idle)

    def _cmd_hold(self):
        n = self.node
        n.set_position(n.x, n.y, n.z, n.heading)
        self.log("Holding position.")

    # ---- Live keyboard -------------------------------------------------------
    def _toggle_keyboard(self):
        if self.node is None:
            self.log("Node not ready yet.")
            return
        if self.executor and self.executor.is_alive():
            self.log("Cannot use keyboard while a mission is running.")
            return
        self.keyboard_active = not self.keyboard_active
        if self.keyboard_active:
            self.kb_btn.config(text="Disable keyboard control  (ON)", bg=OK)
            self.log("Keyboard control ON - arming + OFFBOARD. Click the window, then fly.")
            n = self.node
            n.set_velocity(0.0, 0.0, 0.0, 0.0)
            n.engage_offboard()
            self.root.after(400, n.arm)
            self.root.bind("<KeyPress>", self._on_key_press)
            self.root.bind("<KeyRelease>", self._on_key_release)
            self.root.focus_set()
        else:
            self.kb_btn.config(text="Enable keyboard control  (OFF)", bg="#6c757d")
            self.root.unbind("<KeyPress>")
            self.root.unbind("<KeyRelease>")
            self._keys_down.clear()
            if self.node:
                self.node.set_position(self.node.x, self.node.y, self.node.z, self.node.heading)
            self.log("Keyboard control OFF - holding position.")

    def _on_key_press(self, event):
        key = event.keysym.lower()
        # Cancel a pending release from X11 auto-repeat.
        if key in self._pending_release:
            self.root.after_cancel(self._pending_release.pop(key))
        if key == "space":
            self._keys_down.clear()
            self.log("STOP - velocities zeroed.")
            return
        self._keys_down.add(key)

    def _on_key_release(self, event):
        key = event.keysym.lower()
        # Defer the actual release; if it is auto-repeat a press will cancel it.
        if key in self._pending_release:
            self.root.after_cancel(self._pending_release[key])

        def _release():
            self._keys_down.discard(key)
            self._pending_release.pop(key, None)
        self._pending_release[key] = self.root.after(KB_AUTOREPEAT_GRACE_MS, _release)

    def _apply_keyboard_velocity(self):
        k = self._keys_down
        fwd = (KB_SPEED if "w" in k else 0.0) - (KB_SPEED if "s" in k else 0.0)
        right = (KB_SPEED if "d" in k else 0.0) - (KB_SPEED if "a" in k else 0.0)
        up = (KB_SPEED if "u" in k else 0.0) - (KB_SPEED if "o" in k else 0.0)
        yaw_rate = (KB_YAW_RATE if "l" in k else 0.0) - (KB_YAW_RATE if "j" in k else 0.0)

        # Rotate body forward/right into world NED using current heading
        # (same FRD->NED transform the MOVE mission step uses).
        h = self.node.heading
        vn = fwd * math.cos(h) - right * math.sin(h)
        ve = fwd * math.sin(h) + right * math.cos(h)
        vd = -up
        self.node.set_velocity(vn, ve, vd, yaw_rate)

    # ---- QGroundControl ------------------------------------------------------
    def _detect_qgc(self) -> str:
        env = os.environ.get("QGC_PATH")
        if env and os.path.exists(os.path.expanduser(env)):
            return os.path.expanduser(env)
        for c in QGC_CANDIDATES:
            p = os.path.expanduser(c)
            if os.path.exists(p):
                return p
        for name in ("qgroundcontrol", "QGroundControl"):
            found = shutil.which(name)
            if found:
                return found
        return os.path.expanduser(QGC_CANDIDATES[0])

    def _toggle_qgc(self):
        if self.qgc_proc and self.qgc_proc.poll() is None:
            self.log("Stopping QGroundControl...")
            try:
                os.killpg(os.getpgid(self.qgc_proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                self.qgc_proc.terminate()
            self.qgc_proc = None
            self.qgc_btn.config(text="Launch QGroundControl", bg=OK)
            return

        path = os.path.expanduser(self.qgc_path_var.get().strip())
        if not os.path.exists(path):
            messagebox.showerror(
                "QGroundControl not found",
                f"No file at:\n{path}\n\n"
                "Download the AppImage, 'chmod +x' it, and point this field at it "
                "(or set the QGC_PATH environment variable).",
                parent=self.root)
            return
        try:
            if not os.access(path, os.X_OK):
                os.chmod(path, 0o755)
            self.qgc_proc = subprocess.Popen(
                [path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True)
            self.log(f"Launched QGroundControl ({os.path.basename(path)}).")
            self.qgc_btn.config(text="Stop QGroundControl", bg=WARN)
        except Exception as exc:
            messagebox.showerror("Launch failed", str(exc), parent=self.root)

    # ---- Mission list management --------------------------------------------
    def _redraw_tree(self):
        sel = self.tree.selection()
        sel_index = self.tree.index(sel[0]) if sel else None
        self.tree.delete(*self.tree.get_children())
        for i, step in enumerate(self.steps):
            self.tree.insert("", "end", iid=str(i), text=str(i + 1), values=(step.label(),))
        if sel_index is not None and self.steps:
            iid = str(min(sel_index, len(self.steps) - 1))
            self.tree.selection_set(iid)
            self.tree.focus(iid)

    def _selected_index(self) -> Optional[int]:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add_step(self):
        dlg = StepDialog(self.root)
        self.root.wait_window(dlg)
        if dlg.result:
            idx = self._selected_index()
            if idx is None:
                self.steps.append(dlg.result)
            else:
                self.steps.insert(idx + 1, dlg.result)
            self._redraw_tree()

    def _edit_step(self):
        idx = self._selected_index()
        if idx is None:
            return
        dlg = StepDialog(self.root, self.steps[idx])
        self.root.wait_window(dlg)
        if dlg.result:
            self.steps[idx] = dlg.result
            self._redraw_tree()

    def _delete_step(self):
        idx = self._selected_index()
        if idx is not None:
            del self.steps[idx]
            self._redraw_tree()

    def _move_step(self, delta: int):
        idx = self._selected_index()
        if idx is None:
            return
        new = idx + delta
        if 0 <= new < len(self.steps):
            self.steps[idx], self.steps[new] = self.steps[new], self.steps[idx]
            self._redraw_tree()
            self.tree.selection_set(str(new))

    def _clear_steps(self):
        if self.steps and messagebox.askyesno("Clear mission", "Remove all steps?", parent=self.root):
            self.steps.clear()
            self._redraw_tree()

    def _save_mission(self):
        if not self.steps:
            self.log("Nothing to save - the mission is empty.")
            return
        path = filedialog.asksaveasfilename(
            title="Save mission", defaultextension=".json",
            filetypes=[("Mission JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        data = {"version": 1, "steps": [s.to_dict() for s in self.steps]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.log(f"Saved {len(self.steps)} steps to {path}")

    def _load_mission(self):
        path = filedialog.askopenfilename(
            title="Load mission",
            filetypes=[("Mission JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.steps = [MissionStep.from_dict(d) for d in data["steps"]]
            self._redraw_tree()
            self.log(f"Loaded {len(self.steps)} steps from {path}")
        except Exception as exc:
            messagebox.showerror("Load failed", str(exc), parent=self.root)

    # ---- Mission run/pause/stop ---------------------------------------------
    def _set_progress(self, index: int, state: str):
        def apply():
            iid = str(index)
            if self.tree.exists(iid):
                self.tree.item(iid, tags=(state,))
        self.root.after(0, apply)

    def _run_mission(self):
        if self.node is None:
            self.log("Node not ready.")
            return
        if self.executor and self.executor.is_alive():
            return
        if not self.steps:
            self.log("Add at least one step first.")
            return
        if self.keyboard_active:
            self._toggle_keyboard()  # turn keyboard off before flying a mission
        if not self.node.link_ok():
            if not messagebox.askyesno(
                    "No telemetry", "No link to the drone yet. Run the mission anyway?",
                    parent=self.root):
                return
        for i in range(len(self.steps)):
            self._set_progress(i, "")
        self.log("=== Mission started ===")
        self.executor = MissionExecutor(
            self.node, list(self.steps), self.log, self._set_progress, self._on_mission_done)
        self.executor.start()
        self.run_btn.config(state="disabled")
        self.pause_btn.config(state="normal", text="❚❚ Pause")
        self.stop_btn.config(state="normal")

    def _toggle_pause(self):
        if not (self.executor and self.executor.is_alive()):
            return
        if self.executor._pause_evt.is_set():
            self.executor.resume()
            self.pause_btn.config(text="❚❚ Pause")
            self.log("Mission resumed.")
        else:
            self.executor.pause()
            self.pause_btn.config(text="▶ Resume")
            self.log("Mission paused (holding position).")

    def _stop_mission(self):
        if self.executor and self.executor.is_alive():
            self.executor.stop()
            self.log("Stopping mission...")

    def _on_mission_done(self, success: bool, message: str):
        def finish():
            self.log(f"=== {message} ===")
            self.run_btn.config(state="normal")
            self.pause_btn.config(state="disabled", text="❚❚ Pause")
            self.stop_btn.config(state="disabled")
        self.root.after(0, finish)

    # ---- Shutdown ------------------------------------------------------------
    def _on_close(self):
        try:
            if self.executor and self.executor.is_alive():
                self.executor.stop()
                self.executor.join(timeout=2.0)
            if self.node is not None:
                self.node.set_idle()
            if self.qgc_proc and self.qgc_proc.poll() is None:
                try:
                    os.killpg(os.getpgid(self.qgc_proc.pid), signal.SIGTERM)
                except OSError:
                    self.qgc_proc.terminate()
        finally:
            self._ros_stop.set()
            self._ros_thread.join(timeout=2.0)
            self.root.destroy()


def main(args=None):
    root = tk.Tk()
    MissionControlApp(root)
    print("\n[mission_control] GUI is running - the window should be open on your "
          "screen.\n[mission_control] This terminal stays busy until you close the "
          "window (or press Ctrl+C).\n", flush=True)
    root.mainloop()
    print("[mission_control] GUI closed.", flush=True)


if __name__ == "__main__":
    main()
