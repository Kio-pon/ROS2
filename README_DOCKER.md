# Containerized PX4 + ROS 2 Jazzy + Gazebo Harmonic Simulator

A reproducible, **native-display, GPU-accelerated** simulation environment for the
Autonomous Flight System / Farmevo project. Everything (PX4 SITL, ROS 2 Jazzy,
Gazebo Harmonic, the Micro-XRCE-DDS bridge, the `drone_controller` package and
its Mission Control GUI) is baked into one image. Graphical windows open
**directly on your machine** — there is no browser, no VNC, no virtual desktop.

This is the Tier 0 "standalone environment, runs on a developer workstation"
deliverable from the internship brief: Linux-native, scriptable/headless-capable
for automated test runs, with documented extension points for assets and aircraft.

---

## 1. Why this design

| Concern | Approach |
|---|---|
| **GUI** | Native X11 passthrough — real OS windows, not a streamed browser canvas. |
| **GPU** | Host driver via NVIDIA Container Toolkit, or `/dev/dri` for Intel/AMD. Gazebo gets real acceleration. |
| **Reproducibility** | PX4 and `px4_msgs` are **pinned to the exact commits** the project was built on, so the uORB topic set (`…_v1`/`…_v4`) matches the ROS 2 nodes. |
| **Stability** | Non-root user, no `privileged`, layer-cached build, IPC/host networking for clean DDS + Gazebo transport. |
| **Extensibility** | Bind-mounted folders for custom models, worlds, airframes, and missions — add assets with no rebuild. |

---

## 2. Prerequisites (host machine — Linux recommended)

- **Docker Engine + Compose plugin** (`docker --version`, `docker compose version`).
- An **X server** (any normal Linux desktop has one).
- **NVIDIA GPU (optional but recommended):** install the
  [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
  and verify:
  ```bash
  docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
  ```

No ROS 2, PX4, Gazebo, or Python install is needed on the host.

---

## 3. First-time setup

```bash
# 1. Match the container user to your host user (only if 'id -u' is NOT 1000):
id -u && id -g            # if these aren't 1000, edit UID/GID in .env

# 2. Allow the container to talk to your X server (once per login session):
xhost +local:            # revoke later with: xhost -local:

# 3. Build the image (first build compiles PX4 — ~10-20 min depending on CPU):
docker compose build
```

> On a powerful PC, speed the build up by raising `BUILD_JOBS` in `.env` (e.g. `8`).

---

## 4. Run it

### Intel / AMD GPU or software rendering (default)
```bash
docker compose up -d
docker compose exec drone-sim ~/launchers/run_all.sh
```

### NVIDIA GPU (recommended — full acceleration)
```bash
docker compose -f docker-compose.yml -f docker-compose.nvidia.yml up -d
docker compose -f docker-compose.yml -f docker-compose.nvidia.yml exec drone-sim ~/launchers/run_all.sh
```

`run_all.sh` boots the DDS agent, PX4 SITL + Gazebo with the camera quadcopter,
bridges the camera into ROS 2, and opens the **Mission Control GUI** — all as
native windows on your screen. Arm, take off, fly, build missions, watch the
live camera.

### Stop
```bash
docker compose down
```

### Headless (CI / automated tests — no screen needed)
```bash
docker compose run --rm -e HEADLESS=1 drone-sim ~/launchers/run_headless_drone.sh
```

---

## 5. Change the aircraft / world

Edit `.env` (or pass `-e` at run time). No rebuild required — these are runtime
environment variables:

| Aircraft | `PX4_SYS_AUTOSTART` | `PX4_SIM_MODEL` |
|---|---|---|
| x500 + mono camera (default) | `4010` | `gz_x500_mono_cam` |
| plain x500 (no camera) | `4001` | `gz_x500` |
| x500 + depth camera | `4002` | `gz_x500_depth` |
| x500 + gimbal camera | `4019` | `gz_x500_gimbal` |
| standard VTOL | `4004` | `gz_standard_vtol` |

Worlds shipped with PX4 include `lawn`, `default`, `baylands`, `windy`, `forest` —
set `PX4_GZ_WORLD`.

---

## 6. Extending it (this is the part built for the future)

Everything below is a **bind-mounted folder** in `docker-compose.yml`, so changes
on the host appear instantly in the container.

### Add a 3D model (e.g. a transmission tower, a crop field)
1. Put the model folder (with its `model.sdf` + `model.config`) in `./custom_models/`.
2. It is automatically on `GZ_SIM_RESOURCE_PATH` inside the container.
3. Spawn it into a running sim:
   ```bash
   gz service -s /world/lawn/create --reqtype gz.msgs.EntityFactory \
     --reptype gz.msgs.Boolean --timeout 2000 \
     --req 'sdf_filename: "model://my_tower", pose: {position: {x: 5, y: 0, z: 0}}'
   ```
   …or `<include><uri>model://my_tower</uri></include>` it in a custom world.

### Add a custom world
Drop a `.sdf` in `./custom_worlds/` and set `PX4_GZ_WORLD=<world_name>`.

### Swap in a brand-new drone airframe
1. Put the PX4 airframe init file in `./custom_airframes/`.
2. Add the gz model under `./custom_models/`.
3. Point `PX4_SYS_AUTOSTART` / `PX4_SIM_MODEL` at it.
(For a permanent built-in aircraft, add it to the Dockerfile's PX4 layer instead.)

### Add a new ROS 2 package
Create it alongside `drone_controller/` and add a bind mount + a
`colcon build --packages-select <pkg>` line, mirroring `drone_controller`.

### Live code edit cycle
`./drone_controller` is mounted into the workspace. Edit on the host, then:
```bash
docker compose exec drone-sim bash -lc \
  "cd ~/px4_ros2_ws && colcon build --packages-select drone_controller && \
   source install/setup.bash && ros2 run drone_controller mission_control"
```

---

## 7. Bumping versions

Pinned in `.env` (`PX4_REF`, `PX4MSGS_REF`). To move to the latest upstream:
```bash
# in .env:  PX4_REF=main   PX4MSGS_REF=main
docker compose build
```
Keep PX4 and `px4_msgs` on **matching** versions, or the XRCE-DDS message
definitions will mismatch and telemetry topics won't line up.

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `cannot open display` / no windows | Run `xhost +local:` on the host; confirm `DISPLAY` is set (`echo $DISPLAY`). |
| Gazebo very slow / `llvmpipe` in logs | No GPU acceleration — use the NVIDIA override, or ensure `/dev/dri` exists and you're in the `render` group. |
| Compiler killed during build | Lower `BUILD_JOBS` in `.env` (RAM exhaustion). |
| Files created in mounts owned by root | Set `UID`/`GID` in `.env` to your host `id -u`/`id -g`, then rebuild. |
| No telemetry in Mission Control | Confirm PX4/`px4_msgs` are on matching commits (default `.env` values are a known-good pair). |

---

## 9. Windows / WSLg note

The professional target is a Linux workstation. On Windows it still runs via
Docker Desktop (WSL2 backend): WSLg provides the X server, so set
`DISPLAY=:0` and mount `/mnt/wslg` in addition to `/tmp/.X11-unix`. Host
networking is limited on Docker Desktop — prefer the Linux path for demos.
