#!/bin/bash
# Mission Control with Live Camera Launcher
#
# Boots PX4 SITL + Gazebo with a camera-equipped x500 (airframe 4010,
# gz_x500_mono_cam), bridges the Gazebo camera into ROS 2, and runs the 
# mission_control GUI natively.
#

echo "================================================="
echo "  PX4 Drone Simulator — Starting Launcher..."
echo "================================================="

# Locate the script's own directory (works in Docker and native)
SELF_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
WORKSPACE_DIR="$SELF_DIR"
if [ "$(basename "$SELF_DIR")" = "launchers" ]; then
    WORKSPACE_DIR="$(dirname "$SELF_DIR")"
fi

# ── 0. Handle options and launch GUI ─────────────────────────────────────
SKIP_GUI=0
for arg in "$@"; do
    if [ "$arg" = "--skip-gui" ] || [ "$arg" = "--no-gui" ]; then
        SKIP_GUI=1
    fi
done

LAUNCHER="$SELF_DIR/launcher_gui.py"
[ ! -f "$LAUNCHER" ] && LAUNCHER="$HOME/launchers/launcher_gui.py"
[ ! -f "$LAUNCHER" ] && LAUNCHER="$HOME/launcher_gui.py"

if [ "$SKIP_GUI" -eq 0 ]; then
    if [ -f "$LAUNCHER" ]; then
        python3 "$LAUNCHER"
        if [ $? -ne 0 ]; then
            echo "Launch cancelled by user."
            exit 0
        fi
    else
        echo "WARN: launcher_gui.py not found — using defaults."
    fi
else
    echo "Skipping launcher GUI (using pre-configured or default settings)."
fi

# ── 1. Cleanup old processes ─────────────────────────────────────────────
echo "Cleaning up any old simulator / ROS 2 / bridge processes..."
# Kill everything — use SIGKILL directly to bypass permission issues
for name in px4 MicroXRCEAgent gz image_bridge parameter_bridge mission_control; do
    pgrep -f "$name" | while read pid; do
        kill -9 "$pid" 2>/dev/null || true
    done
done
# Wait until gz is REALLY gone so PX4 starts on a clean Gazebo instance
for _ in $(seq 1 20); do
    pgrep -f "gz sim" >/dev/null 2>&1 || break
    sleep 0.5
done
sleep 1

# ── 2. Source launcher settings (or use defaults) ────────────────────────
ENV_FILE="$SELF_DIR/.drone_launch.env"
[ ! -f "$ENV_FILE" ] && ENV_FILE="$HOME/.drone_launch.env"
[ ! -f "$ENV_FILE" ] && ENV_FILE="$HOME/launchers/.drone_launch.env"

if [ -f "$ENV_FILE" ]; then
    echo "Loading launcher settings from $ENV_FILE..."
    source "$ENV_FILE"
    
    # Path translation: if the patched world path is a Windows path (e.g. C:\Users\...),
    # translate it to a WSL path so copy commands can find it.
    if [[ "$LAUNCHER_WORLD_FILE" =~ ^[A-Za-z]:\\ ]]; then
        LAUNCHER_WORLD_FILE=$(echo "$LAUNCHER_WORLD_FILE" | sed -e 's/\\/\//g' -e 's/^\([A-Za-z]\):/\/mnt\/\L\1/')
    fi
    
    cat "$ENV_FILE"
    echo "Translated world path: $LAUNCHER_WORLD_FILE"
fi

# Aircraft / world — honour launcher settings, then env overrides, then defaults
export PX4_SYS_AUTOSTART="${PX4_SYS_AUTOSTART:-4010}"
export PX4_SIM_MODEL="${PX4_SIM_MODEL:-gz_x500_mono_cam}"
export PX4_GZ_WORLD="${PX4_GZ_WORLD:-forest}"

# ── 3. Handle Free Roam (No Drone) Mode ──────────────────────────────────
if [ "$PX4_SIM_MODEL" = "none" ]; then
    echo "================================================="
    echo "  Free Roam Mode (No Drone) — Starting Gazebo..."
    echo "================================================="
    
    # Generate textures/world scenery if needed
    for base in "$WORKSPACE_DIR" "$HOME"; do
        GEN="$base/tools/gen_grass_texture.py"
        GRASS="$base/custom_models/farmland_terrain/grass_diffuse.png"
        if [ -f "$GEN" ] && [ ! -f "$GRASS" ]; then
            echo "Generating farmland grass texture..."
            python3 "$GEN" >/dev/null 2>&1
        fi
    done
    
    for d in "$HOME/custom_models" "$WORKSPACE_DIR/custom_models"; do
        [ -d "$d" ] && export GZ_SIM_RESOURCE_PATH="$d:${GZ_SIM_RESOURCE_PATH:-}"
    done
    
    GEN_SCRIPT="$SELF_DIR/gen_$PX4_GZ_WORLD.py"
    if [ -f "$GEN_SCRIPT" ]; then
        echo "Regenerating $PX4_GZ_WORLD with density=${DENSITY:-medium}..."
        python3 "$GEN_SCRIPT" --density "${DENSITY:-medium}"
    fi
    
    # We launch Gazebo with the patched world file
    WORLD_FILE="$LAUNCHER_WORLD_FILE"
    if [ -z "$WORLD_FILE" ] || [ ! -f "$WORLD_FILE" ]; then
        WORLD_FILE="$HOME/custom_worlds/$PX4_GZ_WORLD.sdf"
        [ ! -f "$WORLD_FILE" ] && WORLD_FILE="$WORKSPACE_DIR/custom_worlds/$PX4_GZ_WORLD.sdf"
    fi
    
    echo "Launching Gazebo with world: $WORLD_FILE..."
    if [ -n "$HEADLESS" ]; then
        gz sim -s -r "$WORLD_FILE"
    else
        gz sim -r "$WORLD_FILE"
    fi
    
    echo "Gazebo closed. Exiting."
    exit 0
fi

# DDS agent (only started for active drones)
echo "Starting DDS Agent..."
MicroXRCEAgent udp4 -p 8888 > ~/dds_agent.log 2>&1 &

# Ensure rootfs/etc is a symlink to build/px4_sitl_default/etc and not a real directory
# that breaks PX4 startup.
PX4_PATH="$HOME/PX4-Autopilot"
ROOTFS_ETC="$PX4_PATH/build/px4_sitl_default/rootfs/etc"
BUILD_ETC="$PX4_PATH/build/px4_sitl_default/etc"
if [ -d "$ROOTFS_ETC" ] && [ ! -L "$ROOTFS_ETC" ]; then
    echo "Healing rootfs/etc directory (replacing real directory with symlink)..."
    if [ -d "$ROOTFS_ETC/init.d-posix/airframes" ]; then
        mkdir -p "$BUILD_ETC/init.d-posix/airframes"
        cp -rn "$ROOTFS_ETC/init.d-posix/airframes"/* "$BUILD_ETC/init.d-posix/airframes/" 2>/dev/null || true
    fi
    rm -rf "$ROOTFS_ETC"
fi

if [ ! -e "$ROOTFS_ETC" ]; then
    echo "Creating symlink for rootfs/etc..."
    ln -sf "$BUILD_ETC" "$ROOTFS_ETC"
fi

# Auto-heal/setup custom PX4 airframe and symlinks if they are missing inside the container/host
if [ "$PX4_SIM_MODEL" = "m4e" ]; then
    ROOTFS_AF="$PX4_PATH/build/px4_sitl_default/rootfs/etc/init.d-posix/airframes/4900_gz_m4e"
    NEED_BUILD=0; [ ! -f "$ROOTFS_AF" ] && NEED_BUILD=1
    # ALWAYS refresh the airframe from source so edits (rotor geometry, params)
    # actually reach the running PX4 - the old "copy only if missing" skipped
    # updates and left a stale airframe in rootfs. Copying into rootfs is what
    # PX4 reads at startup, so no rebuild is needed for a param change.
    echo "Staging DJI Matrice 4E airframe inside PX4..."
    mkdir -p "$PX4_PATH/ROMFS/px4fmu_common/init.d-posix/airframes" "$(dirname "$ROOTFS_AF")"
    cp "$WORKSPACE_DIR/custom_airframes/4900_gz_m4e" "$PX4_PATH/ROMFS/px4fmu_common/init.d-posix/airframes/4900_gz_m4e"
    cp "$WORKSPACE_DIR/custom_airframes/4900_gz_m4e" "$ROOTFS_AF"
    if [ "$NEED_BUILD" -eq 1 ]; then
        echo "First-time airframe registration — compiling PX4 SITL target..."
        (cd "$PX4_PATH" && make px4_sitl_default)
    fi

    if [ ! -d "$PX4_PATH/Tools/simulation/gz/models/m4e" ]; then
        echo "Creating DJI model symlink inside PX4..."
        mkdir -p "$PX4_PATH/Tools/simulation/gz/models"
        ln -sf "$WORKSPACE_DIR/custom_models/m4e" "$PX4_PATH/Tools/simulation/gz/models/m4e"
    fi

    # Camera quality/fps from the launcher preset (potato 640x480@15 / mild
    # 960x720@30 / full 1280x960@60). Only the 3 camera sensors are patched; the
    # cams are always_on=false + lazy-bridged, so gz renders only the ONE feed
    # mission_control is actually viewing (one camera on, the others idle).
    if [ -f "$WORKSPACE_DIR/tools/patch_m4e_cams.py" ]; then
        python3 "$WORKSPACE_DIR/tools/patch_m4e_cams.py" "${CAM_W:-1280}" "${CAM_H:-960}" "${CAM_HZ:-30}"
    fi
fi

# Spawn pose: drop the drone right ONTO the ground (a few cm up), not 5 m above
# it. The ground height at the origin depends on the world's heightmap terrain
# (forest ~5.5 m, farmland ~1.0 m, row_crops ~0.7 m), so a single hardcoded z
# used to fling the drone metres into the air on the flatter worlds. Compute it
# from the chosen world; fall back to the old forest value only if that fails.
if [ -z "$PX4_GZ_MODEL_POSE" ]; then
    SPAWN_WORLD_SDF=""
    if [ -n "$LAUNCHER_WORLD_FILE" ] && [ -f "$LAUNCHER_WORLD_FILE" ]; then
        SPAWN_WORLD_SDF="$LAUNCHER_WORLD_FILE"
    else
        for d in "$SELF_DIR/custom_worlds" "$HOME/custom_worlds"; do
            [ -f "$d/$PX4_GZ_WORLD.sdf" ] && SPAWN_WORLD_SDF="$d/$PX4_GZ_WORLD.sdf" && break
        done
    fi
    SPAWN_Z=""
    if [ -n "$SPAWN_WORLD_SDF" ] && [ -f "$WORKSPACE_DIR/tools/place_on_terrain.py" ]; then
        SPAWN_Z=$(python3 "$WORKSPACE_DIR/tools/place_on_terrain.py" --spawn-z "$SPAWN_WORLD_SDF" 2>/dev/null)
    fi
    if [ -z "$SPAWN_Z" ]; then
        # Per-world safe fallback spawn heights (used when place_on_terrain.py fails)
        case "$PX4_GZ_WORLD" in
            forest)      SPAWN_Z=5.8  ;;   # forest heightmap peak at origin
            farmland)    SPAWN_Z=1.2  ;;   # farmland_terrain is mostly flat
            row_crops)   SPAWN_Z=1.0  ;;   # soil_terrain is flat
            wheat_field) SPAWN_Z=1.0  ;;   # wheat_terrain is flat
            powerline)   SPAWN_Z=1.0  ;;   # flat ground plane
            *)           SPAWN_Z=1.5  ;;   # generic safe default
        esac
    fi
    export PX4_GZ_MODEL_POSE="-10.0,0.0,$SPAWN_Z"
    echo "Spawn pose: -10.0,0.0,$SPAWN_Z  (ground-level for world '$PX4_GZ_WORLD')"
fi
export GZ_CONFIG_PATH="/usr/share/gz:${GZ_CONFIG_PATH:-}"
unset PX4_GZ_MODEL_NAME
# NOTE: use ${VAR-default} (no colon) so an explicit empty HEADLESS="" from the
# launcher (= "show Gazebo GUI") is preserved; only default to headless when UNSET.
export HEADLESS="${HEADLESS-1}"

# Grass texture for the farmland ground is procedural (kept out of git as a
# binary); generate it on first run if it isn't there yet.
for base in "$WORKSPACE_DIR" "$HOME"; do
    GEN="$base/tools/gen_grass_texture.py"
    GRASS="$base/custom_models/farmland_terrain/grass_diffuse.png"
    if [ -f "$GEN" ] && [ ! -f "$GRASS" ]; then
        echo "Generating farmland grass texture..."
        python3 "$GEN" >/dev/null 2>&1 || echo "WARN: could not generate grass texture (PIL missing?)"
    fi
done

# Make custom scenery available (works both in Docker and native)
for d in "$HOME/custom_models" "$WORKSPACE_DIR/custom_models"; do
    [ -d "$d" ] && export GZ_SIM_RESOURCE_PATH="$d:${GZ_SIM_RESOURCE_PATH:-}"
done

# Regenerate the world based on the selected density
GEN_SCRIPT="$SELF_DIR/gen_$PX4_GZ_WORLD.py"
if [ -f "$GEN_SCRIPT" ]; then
    echo "Regenerating $PX4_GZ_WORLD with density=${DENSITY:-medium}..."
    python3 "$GEN_SCRIPT" --density "${DENSITY:-medium}"
fi

for d in "$HOME/custom_worlds" "$WORKSPACE_DIR/custom_worlds"; do
    [ -d "$d" ] && cp -u "$d"/*.sdf "$HOME/PX4-Autopilot/Tools/simulation/gz/worlds/" 2>/dev/null || true
done

# Copy the launcher's patched world file into PX4's worlds directory
if [ -n "$LAUNCHER_WORLD_FILE" ] && [ -f "$LAUNCHER_WORLD_FILE" ]; then
    echo "Installing patched world: $LAUNCHER_WORLD_FILE as $PX4_GZ_WORLD.sdf"
    cp -f "$LAUNCHER_WORLD_FILE" "$HOME/PX4-Autopilot/Tools/simulation/gz/worlds/$PX4_GZ_WORLD.sdf" 2>/dev/null || true
fi

# 2c. Right-size the drone camera (biggest GPU cost: it renders offscreen every
#     frame). Idempotent — replaces whatever values are there. Defaults are the
#     potato-PC profile; the launcher overrides CAM_* per optimization preset.
CAM_MODEL="$HOME/PX4-Autopilot/Tools/simulation/gz/models/mono_cam/model.sdf"
if [ -f "$CAM_MODEL" ]; then
    sed -i -E \
        -e "s#<width>[0-9]+</width>#<width>${CAM_W:-640}</width>#" \
        -e "s#<height>[0-9]+</height>#<height>${CAM_H:-480}</height>#" \
        -e "s#<update_rate>[0-9]+</update_rate>#<update_rate>${CAM_HZ:-20}</update_rate>#" \
        -e "s#<far>[0-9.]+</far>#<far>500</far>#" \
        "$CAM_MODEL"
    echo "Camera set to ${CAM_W:-640}x${CAM_H:-480}@${CAM_HZ:-20}Hz (far clip 500m)"
fi

# 3. Launch PX4 SITL + Gazebo
echo "Launching PX4 SITL + Gazebo with a camera drone..."
cd ~/PX4-Autopilot
./build/px4_sitl_default/bin/px4 -d > ~/px4.log 2>&1 &
sleep 3

# 4. SITL arming/control config — let QGC and mission_control arm & fly
#    autonomously (offboard) with NO RC/joystick, and stop SITL-only failsafes
#    from blocking arming. COM_RC_IN_MODE 4 = stick input disabled, which clears
#    the "No manual control input" arming refusal.
P=./build/px4_sitl_default/bin/px4-param
$P set NAV_DLL_ACT  0 > /dev/null 2>&1   # datalink loss: no failsafe
$P set NAV_RCL_ACT  0 > /dev/null 2>&1   # RC loss: no failsafe
$P set COM_RC_IN_MODE 4 > /dev/null 2>&1 # stick input disabled (autonomous/offboard)
$P set COM_RCL_EXCEPT 4 > /dev/null 2>&1 # allow offboard with no RC
$P set COM_ARM_WO_GPS 1 > /dev/null 2>&1 # arm without GPS lock
# Heading/EKF: a stationary SITL drone gets "Preflight Fail: no heading reference"
# because the EKF rejects the simulated magnetometer. Force mag heading and skip
# the field-strength gate so a yaw reference is available -> arming works.
$P set EKF2_MAG_CHECK 0 > /dev/null 2>&1  # don't reject mag on field-strength mismatch
$P set EKF2_MAG_TYPE  2 > /dev/null 2>&1  # use magnetometer for heading
$P set CBRK_SUPPLY_CHK 894281 > /dev/null 2>&1 # bypass power/battery check

# 5. Wait for the simulator + sensors to come up (wait for the drone model to spawn in Gazebo)
echo "Waiting for the drone simulator to start and model to spawn..."
SPAWNED=0
for i in {1..60}; do
    if gz topic -l 2>/dev/null | grep -qE "x500|m4e"; then
        SPAWNED=1
        break
    fi
    echo -n "."
    sleep 1
done
echo ""
if [ "$SPAWNED" -eq 1 ]; then
    echo "Drone model detected! Simulator initialized."
    sleep 2
else
    echo "WARN: Simulator initialization timed out after 60s (continuing anyway...)"
fi

# 6. Sourcing workspace
echo "Sourcing workspace..."
source /opt/ros/jazzy/setup.bash
source ~/px4_ros2_ws/install/setup.bash

# 7. Auto-detect the camera's gz topic
echo "Detecting the camera topic from Gazebo..."
CAM_TOPIC=""
for _ in {1..30}; do
    for t in $(gz topic -l 2>/dev/null | grep -iE 'image|camera'); do
        case "$t" in *camera_info*|*depth*) continue ;; esac
        if gz topic -i -t "$t" 2>/dev/null | grep -q 'gz.msgs.Image'; then
            CAM_TOPIC="$t"; break
        fi
    done
    [ -n "$CAM_TOPIC" ] && break
    sleep 1
done
if [ -z "$CAM_TOPIC" ]; then
    echo "ERROR: could not find a gz.msgs.Image topic. Topics seen:"
    gz topic -l 2>/dev/null | grep -iE 'image|camera' || echo "   (none - is the camera model spawned?)"
    exit 1
fi
export CAM_TOPIC
echo "Camera topic: $CAM_TOPIC"

# 8. Bridge the Gazebo camera into ROS 2
if ! ros2 pkg prefix ros_gz_image >/dev/null 2>&1; then
    echo "ERROR: ros_gz_image is NOT installed - the live camera feed will be blank."
    echo "       Install it:  sudo apt install ros-jazzy-ros-gz-image"
    echo "       (In the Docker image this is preinstalled, so this should not happen there.)"
fi
if [ "$PX4_SIM_MODEL" = "m4e" ]; then
    echo "Starting ros_gz_bridge parameter bridge using launchers/bridge.yaml (with auto-restart)..."
    (
      while true; do
        ros2 run ros_gz_bridge parameter_bridge --ros-args -p config_file:="$WORKSPACE_DIR/launchers/bridge.yaml" >> ~/image_bridge.log 2>&1
        echo "[parameter_bridge] exited with $? — restarting in 2s..." >> ~/image_bridge.log
        sleep 2
      done
    ) &
else
    echo "Starting ros_gz image bridge on $CAM_TOPIC (with auto-restart)..."
    (
      while true; do
        ros2 run ros_gz_image image_bridge "$CAM_TOPIC" >> ~/image_bridge.log 2>&1
        echo "[image_bridge] exited with $? — restarting in 2s..." >> ~/image_bridge.log
        sleep 2
      done
    ) &
fi
sleep 3
# Confirm the camera actually reached ROS 2 (catches the cross-machine blank-feed issue)
if ros2 topic list 2>/dev/null | grep -qF "$CAM_TOPIC"; then
    echo "OK: camera is live in ROS 2 -> $CAM_TOPIC"
else
    echo "WARN: camera topic not visible in ROS 2 yet. See ~/image_bridge.log."
    echo "      The Mission Control GUI will keep retrying and show the reason in the camera panel."
fi

# 9. Run the Mission Control GUI
echo "Starting Mission Control GUI..."
ros2 run drone_controller mission_control
