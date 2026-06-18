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

# 2. Camera-equipped airframe (4010 = gz_x500_mono_cam)
export PX4_SYS_AUTOSTART=4010
export PX4_SIM_MODEL=gz_x500_mono_cam
export PX4_GZ_WORLD=lawn
export GZ_CONFIG_PATH="/usr/share/gz:${GZ_CONFIG_PATH:-}"
# export HEADLESS=1
unset HEADLESS
unset PX4_GZ_MODEL_NAME

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
echo "Starting ros_gz image bridge..."
ros2 run ros_gz_image image_bridge "$CAM_TOPIC" > ~/image_bridge.log 2>&1 &
sleep 2

# 9. Run the Mission Control GUI
echo "Starting Mission Control GUI..."
ros2 run drone_controller mission_control
