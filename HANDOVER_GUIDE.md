# 🚁 Drone Simulator — Operator Handover Guide

**Read this top to bottom once. If you follow it in order, it cannot go wrong.**

This is the complete runbook for the containerized **PX4 + ROS 2 Jazzy + Gazebo
Harmonic** drone simulator. Anyone handed this image can get a flying, camera-
streaming drone on their own Linux machine by copy-pasting the commands below.

---

## 0. What you are getting (and what works)

One Docker image that contains the **entire** stack — you install nothing else:

| Component | Inside the image? | Works? |
|---|:--:|---|
| PX4 SITL (flight firmware, pinned commit) | ✅ | Yes |
| ROS 2 Jazzy + Gazebo Harmonic | ✅ | Yes — Gazebo opens as a **native window** |
| Micro-XRCE-DDS Agent (PX4 ↔ ROS 2 link) | ✅ | Yes |
| `drone_controller` package + **Mission Control GUI** (Tkinter) | ✅ | Yes — native window: arm, take off, missions, keyboard |
| **Live camera feed** (Gazebo camera → ROS 2 → GUI) | ✅ | Yes — all bridge + image libs baked in |
| QGroundControl | ❌ (run on host) | Yes — **see §7**, connects automatically via host networking |

> **The golden rule:** graphics are shown as **real windows on your screen**
> (native X11 + GPU). There is **no browser, no VNC**. If you expected a web page,
> you have the wrong/old setup.

---

## 1. Prerequisites (host machine — Linux)

Run these checks first. All three must succeed.

```bash
docker --version            # need Docker Engine
docker compose version      # need the Compose v2 plugin
echo "$DISPLAY"             # must print something like  :0   (you're on a desktop)
```

**If you have an NVIDIA GPU** (recommended for smooth Gazebo), also install the
[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
and verify:

```bash
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi   # must print your GPU
```

Intel/AMD GPUs and laptops with no GPU also work (the default path uses `/dev/dri`
or falls back to software rendering — slower but functional).

---

## 2. Get the code

```bash
git clone https://github.com/Kio-pon/ROS2.git
cd ROS2
```

---

## 3. One-time configuration (30 seconds)

```bash
# (a) Tell the container which user to be, so files & the screen "just work".
id -u    # if this is NOT 1000, open .env and set UID/GID to these two numbers
id -g

# (b) Allow the container to draw on your screen (run once each login session):
xhost +local:
```

> You only edit `.env` if your `id -u` isn't 1000. Most first users on a Linux box
> are 1000, so usually you do nothing here.

---

## 4. Build the image (first time only, ~10–20 min)

The first build compiles PX4 from source — this is normal and only happens once.

```bash
# Intel / AMD / no GPU:
docker compose build

# NVIDIA GPU:
docker compose -f docker-compose.yml -f docker-compose.nvidia.yml build
```

✅ **Checkpoint:** the build ends with `naming to docker.io/library/px4-drone-sim:latest`.

---

## 5. Run the simulator (this is the part you do every day)

> 💡 For NVIDIA, add `-f docker-compose.yml -f docker-compose.nvidia.yml` to **every**
> `docker compose` command below. To avoid typing it, run once:
> `export COMPOSE_FILE=docker-compose.yml:docker-compose.nvidia.yml`

```bash
# 1. Start the container in the background
docker compose up -d

# 2. Launch the full simulation (sim + camera bridge + Mission Control GUI)
docker compose exec drone-sim ~/launchers/run_all.sh
```

✅ **What you should see, in order (give it ~20–30 s):**
1. A **Gazebo** window with a green lawn, sky, and a quadcopter.
2. The **Mission Control** window (dark theme: telemetry, buttons, mission list, camera panel).
3. In Mission Control, top-right shows **`LINK: OK`** once telemetry connects.

### Fly it
- Click **ARM**, then **TAKEOFF (2.5m)** — the drone lifts off in Gazebo.
- **Live Camera Feed** panel → click **Show Camera** → you see the drone's view (it
  says `Live (1280x960)`). If it doesn't, the panel tells you exactly why — see §8.
- Build a mission: **+ Add Step** (Take Off → Move → Hover → Land) then **▶ Run mission**.
- Keyboard flight: **Enable keyboard control**, click the window, hold `W/A/S/D`, `U/O`, `J/L`.

### Stop
```bash
docker compose down
```

---

## 6. The launcher scripts (what to run when)

All live in `~/launchers/` inside the container. Run as
`docker compose exec drone-sim ~/launchers/<script>`.

| Script | What it does | Use it when |
|---|---|---|
| `run_all.sh` | Sim + camera bridge + **Mission Control GUI** | **The main one.** Normal demo/dev. |
| `run_camera_proof.sh` | Sim + camera bridge + saves frames to `~/farmevo_proof/` | Verify the camera pipeline alone. |
| `run_headless_drone.sh` | Sim only, **no GUI** | Automated tests / CI / low-power boxes. |
| `run_mission_control.sh` | Mission Control GUI against an already-running sim | Restart just the GUI. |
| `run_teleop.sh` / `run_flight.sh` | Keyboard teleop / scripted autonomous flight | Older standalone demos. |

Headless example (no screen needed at all):
```bash
docker compose run --rm -e HEADLESS=1 drone-sim ~/launchers/run_headless_drone.sh
```

---

## 7. QGroundControl — yes, it works

The image stays lean, so QGC is **not** inside it. Because the container uses
**host networking**, PX4's MAVLink stream is on your host — so just run QGC on the
host and it connects automatically:

1. Download `QGroundControl.AppImage` on the host, `chmod +x` it.
2. Start the sim (`docker compose exec drone-sim ~/launchers/run_all.sh`).
3. Run `./QGroundControl.AppImage` on the host → it shows **“Ready to Fly”** and the drone.

You can fly from QGC and Mission Control at the same time.

> The "QGroundControl" button **inside** the Mission Control GUI is for the
> non-Docker (bare-metal) setup; in Docker, use the host QGC method above.

---

## 8. TROUBLESHOOTING — by symptom

### A. Build fails
| Symptom | Fix |
|---|---|
| `compiler killed` / build dies near PX4 | Out of RAM — lower `BUILD_JOBS` in `.env` (e.g. `2`) and rebuild. |
| `failed to solve` / network errors | Check internet/proxy; rerun `docker compose build`. |

### B. No windows appear / `cannot open display`
1. On the host: `xhost +local:` (must be re-run after each logout/reboot).
2. `echo $DISPLAY` on the host must be non-empty (you must be on a graphical desktop, not pure SSH).
3. Confirm the socket is mounted: `docker compose exec drone-sim ls /tmp/.X11-unix` (should list `X0`).
4. Over SSH? Use `ssh -X`, or run on the machine directly.

### C. Gazebo opens but is extremely slow / choppy
- You're on software rendering. Use the **NVIDIA** compose override, or ensure
  `/dev/dri` exists on the host (`ls /dev/dri`) for Intel/AMD.
- Confirm GPU inside container: `docker compose exec drone-sim glxinfo | grep "OpenGL renderer"`
  (should name your GPU, not `llvmpipe`).

### D. Live camera panel is blank — **the panel now tells you which part failed:**
| Panel message | Meaning | Fix |
|---|---|---|
| `Install python3-pil.imagetk` | image library missing | Shouldn't happen in Docker; if bare-metal: `sudo apt install python3-pil.imagetk`. |
| `No camera topic - is the image bridge running?` | the gz→ROS bridge isn't publishing | Check `docker compose exec drone-sim cat ~/image_bridge.log`; make sure you used a **camera** airframe (`PX4_SIM_MODEL=gz_x500_mono_cam`). |
| `Topic found, no frames yet (GPU/render?)` | bridge ok, camera sensor not rendering | GPU/offscreen-render issue — use the NVIDIA override or check §C. |
| `Live (1280x960)` | ✅ working | — |

> This is exactly the bug you hit before (blank feed on a second PC): that machine
> was missing the bridge/image libraries. In Docker they're always present, and the
> panel above now names the cause if anything is ever off.

### E. Mission Control shows `LINK: NO SIGNAL`
- The DDS agent or PX4 didn't come up. Re-run `~/launchers/run_all.sh` (it cleans up first).
- Check `docker compose exec drone-sim cat ~/px4.log` and `~/dds_agent.log`.
- Version mismatch? The image pins PX4 + `px4_msgs` to a matching pair; don't change
  one without the other (see `.env` `PX4_REF` / `PX4MSGS_REF`).

### F. QGroundControl won't connect
- Confirm the container is using host networking (it is by default). On Docker
  Desktop (Mac/Windows) host networking is limited — use a real Linux host for demos.
- Make sure PX4 is actually running (`~/px4.log`).

### G. Permission-denied on files in `missions/`, `custom_models/`…
- The container user UID/GID doesn't match yours. Set `UID`/`GID` in `.env` to your
  `id -u`/`id -g`, then `docker compose build` again.

---

## 9. Developing / changing things

### Edit the GUI or control code (live)
`./drone_controller` is mounted into the container, so edit on the host, then:
```bash
docker compose exec drone-sim bash -lc \
  "cd ~/px4_ros2_ws && colcon build --packages-select drone_controller && \
   source install/setup.bash && ros2 run drone_controller mission_control"
```

### Change the aircraft / world (no rebuild)
Edit `.env` (table of airframes is in `README_DOCKER.md`) — e.g. plain x500:
`PX4_SYS_AUTOSTART=4001`, `PX4_SIM_MODEL=gz_x500`, then `docker compose up -d` again.

### Add a 3D model / world / new drone
Drop files into `custom_models/`, `custom_worlds/`, `custom_airframes/` (all mounted).
Full instructions in **`README_DOCKER.md` §6**.

---

## 10. Pre-flight checklist (tick before a demo)

- [ ] `docker compose version` works
- [ ] `xhost +local:` run this session
- [ ] `docker compose build` finished cleanly
- [ ] `docker compose up -d` then `~/launchers/run_all.sh`
- [ ] Gazebo window + Mission Control window both visible
- [ ] `LINK: OK` in Mission Control
- [ ] ARM → TAKEOFF lifts the drone
- [ ] Camera panel shows `Live (1280x960)`
- [ ] (optional) QGroundControl on host shows "Ready to Fly"

If every box ticks, you're ready to show it. 🚀
