#!/bin/bash
# Mission Control with Live Camera Launcher
#
# Boots PX4 SITL + Gazebo with a camera-equipped x500 (airframe 4010,
# gz_x500_mono_cam), bridges the Gazebo camera into ROS 2, and runs the 
# mission_control GUI natively.
#

echo "================================================="
echo "Cleaning up any old simulator / ROS 2 / bridge processes..."
echo "================================================="
pkill -f px4 || true
pkill -f MicroXRCEAgent || true
pkill -f ruby || true
pkill -f gz || true
pkill -f image_bridge || true
pkill -f parameter_bridge || true
pkill -f mission_control || true
sleep 1

# 1. DDS agent
echo "Starting DDS Agent..."
MicroXRCEAgent udp4 -p 8888 > ~/dds_agent.log 2>&1 &

# 2. Aircraft / world — honour environment overrides (set by docker-compose
#    or your shell); fall back to the camera-equipped x500 (airframe 4010).
export PX4_SYS_AUTOSTART="${PX4_SYS_AUTOSTART:-4010}"
export PX4_SIM_MODEL="${PX4_SIM_MODEL:-gz_x500_mono_cam}"
export PX4_GZ_WORLD="${PX4_GZ_WORLD:-forest}"
export GZ_CONFIG_PATH="/usr/share/gz:${GZ_CONFIG_PATH:-}"
unset PX4_GZ_MODEL_NAME
# HEADLESS is left untouched: export HEADLESS=1 for a no-GUI Gazebo run.

# 2b. Make custom scenery available (forest/farmland). Works both in Docker
#     (~/custom_*) and native (alongside this script). PX4's gz_env.sh keeps
#     whatever GZ_SIM_RESOURCE_PATH we set here, so model:// trees resolve.
SELF_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
for d in "$HOME/custom_models" "$SELF_DIR/custom_models"; do
    [ -d "$d" ] && export GZ_SIM_RESOURCE_PATH="$d:${GZ_SIM_RESOURCE_PATH:-}"
done
for d in "$HOME/custom_worlds" "$SELF_DIR/custom_worlds"; do
    [ -d "$d" ] && cp -u "$d"/*.sdf "$HOME/PX4-Autopilot/Tools/simulation/gz/worlds/" 2>/dev/null || true
done

# 3. Launch PX4 SITL + Gazebo
echo "Launching PX4 SITL + Gazebo with a camera drone..."
cd ~/PX4-Autopilot
./build/px4_sitl_default/bin/px4 -d > ~/px4.log 2>&1 &
sleep 3

# 4. Allow offboard / bypass GCS checks
./build/px4_sitl_default/bin/px4-param set NAV_DLL_ACT 0 > /dev/null 2>&1
./build/px4_sitl_default/bin/px4-param set COM_RC_IN_MODE 1 > /dev/null 2>&1

# 5. Wait for the simulator + sensors to come up
echo "Waiting 15 seconds for the simulator and camera sensor to start..."
for i in {15..1}; do echo -n "$i... "; sleep 1; done
echo -e "\nInitialization complete!"

# 6. Sourcing workspace
echo "Sourcing workspace..."
source /opt/ros/jazzy/setup.bash
source ~/px4_ros2_ws/install/setup.bash

# 7. Auto-detect the camera's gz topic
echo "Detecting the camera topic from Gazebo..."
CAM_TOPIC=""
for _ in {1..15}; do
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
echo "Camera topic: $CAM_TOPIC"

# 8. Bridge the Gazebo camera into ROS 2
if ! ros2 pkg prefix ros_gz_image >/dev/null 2>&1; then
    echo "ERROR: ros_gz_image is NOT installed - the live camera feed will be blank."
    echo "       Install it:  sudo apt install ros-jazzy-ros-gz-image"
    echo "       (In the Docker image this is preinstalled, so this should not happen there.)"
fi
echo "Starting ros_gz image bridge on $CAM_TOPIC ..."
ros2 run ros_gz_image image_bridge "$CAM_TOPIC" > ~/image_bridge.log 2>&1 &
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
