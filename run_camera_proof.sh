#!/bin/bash
# Phase 1 / Task 1.2 — camera proof-of-life.
#
# Boots PX4 SITL + Gazebo with a camera-equipped x500 (airframe 4010,
# gz_x500_mono_cam), bridges the Gazebo camera into ROS 2, and runs an external
# ROS 2 node (camera_proof) that proves frames are flowing out of the renderer.
#
# Pipeline:  Gazebo camera --gz--> ros_gz_image image_bridge --ROS2--> camera_proof
#
# To also satisfy the "takes off" part of the proof, run the mission GUI in a
# second terminal while this is streaming:  ros2 run drone_controller mission_control

echo "================================================="
echo "Cleaning up any old simulator / ROS 2 / bridge processes..."
echo "================================================="
pkill -9 -f px4 || true
pkill -9 -f MicroXRCEAgent || true
pkill -9 -f ruby || true
pkill -9 -f gz || true
pkill -9 -f image_bridge || true
pkill -9 -f parameter_bridge || true
pkill -9 -f camera_proof || true
sleep 1

# 1. DDS agent
echo "Starting DDS Agent..."
MicroXRCEAgent udp4 -p 8888 > ~/dds_agent.log 2>&1 &

# 2. Camera-equipped airframe (4010 = gz_x500_mono_cam: 1280x960, 30 Hz, ~100deg FOV)
export PX4_SYS_AUTOSTART=4010
export PX4_SIM_MODEL=gz_x500_mono_cam
export PX4_GZ_WORLD=lawn
unset HEADLESS
unset PX4_GZ_MODEL_NAME

# 3. Launch PX4 SITL + Gazebo
echo "Launching PX4 SITL + Gazebo with a camera drone..."
cd ~/PX4-Autopilot
./build/px4_sitl_default/bin/px4 -d > ~/px4.log 2>&1 &
sleep 3

# 4. Allow offboard / bypass GCS checks (so you can take off via mission_control)
./build/px4_sitl_default/bin/px4-param set NAV_DLL_ACT 0 > /dev/null 2>&1
./build/px4_sitl_default/bin/px4-param set COM_RC_IN_MODE 1 > /dev/null 2>&1

# 5. Wait for the simulator + sensors to come up
echo "Waiting 12 seconds for the simulator and camera sensor to start..."
for i in {12..1}; do echo -n "$i... "; sleep 1; done
echo -e "\nInitialization complete!"

# 6. Build the package (registers the camera_proof entry point)
echo "Building drone_controller..."
source /opt/ros/jazzy/setup.bash
if [ -d ~/px4_ros2_ws ]; then
    ( cd ~/px4_ros2_ws && colcon build --packages-select drone_controller --symlink-install ) || \
        echo "WARN: colcon build skipped/failed - assuming already built."
fi
source ~/px4_ros2_ws/install/setup.bash

# 7. Auto-detect the camera's gz topic by MESSAGE TYPE (robust to gz naming).
#    A mono_cam airframe publishes exactly one gz.msgs.Image topic.
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
    echo "Set it manually:  ros2 run ros_gz_image image_bridge <topic>"
    exit 1
fi
echo "Camera topic: $CAM_TOPIC"

# 8. Bridge the Gazebo camera into ROS 2 (publishes a ROS Image on the same name)
echo "Starting ros_gz image bridge..."
ros2 run ros_gz_image image_bridge "$CAM_TOPIC" > ~/image_bridge.log 2>&1 &
sleep 2

# 9. Run the external proof-of-life node (foreground)
echo "Starting camera_proof node (Ctrl+C to stop)..."
echo "   Frames are saved under ~/farmevo_proof/"
ros2 run drone_controller camera_proof --ros-args -p topic:="$CAM_TOPIC"
