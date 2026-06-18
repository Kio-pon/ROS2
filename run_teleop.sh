#!/bin/bash
# A unified script to run the simulator in the background and launch keyboard teleop in the foreground.

echo "================================================="
echo "Cleaning up any old simulator or ROS 2 processes..."
echo "================================================="
pkill -f px4 || true
pkill -f MicroXRCEAgent || true
pkill -f ruby || true
pkill -f gz || true
pkill -f python3 || true
sleep 1

# 1. Start the Micro-XRCE-DDS Agent in the background
echo "Starting DDS Agent..."
MicroXRCEAgent udp4 -p 8888 > ~/dds_agent.log 2>&1 &

# 2. Set environment variables for Grass World & GUI
export PX4_SYS_AUTOSTART=4001
export PX4_SIM_MODEL=gz_x500
export PX4_GZ_WORLD=lawn
export GZ_CONFIG_PATH="/usr/share/gz:${GZ_CONFIG_PATH:-}"
unset HEADLESS
unset PX4_GZ_MODEL_NAME

# 3. Launch PX4 SITL in the background in daemon mode (prevents infinite shell prompt loop in logs)
echo "Launching PX4 SITL and Gazebo Simulator (Grass & Sky)..."
cd ~/PX4-Autopilot
./build/px4_sitl_default/bin/px4 -d > ~/px4.log 2>&1 &
sleep 3

# 4. Bypass Ground Control Station (GCS) and RC safety checks
echo "Configuring flight safety parameters to bypass GCS checks..."
./build/px4_sitl_default/bin/px4-param set NAV_DLL_ACT 0 > /dev/null 2>&1
./build/px4_sitl_default/bin/px4-param set COM_RC_IN_MODE 1 > /dev/null 2>&1

# 5. Wait for the simulator and EKF2 filter to align (GPS lock)
echo "Waiting 12 seconds for the simulator to boot and EKF to align..."
for i in {12..1}; do
    echo -n "$i... "
    sleep 1
done
echo -e "\nInitialization complete!"

# 6. Launch keyboard teleoperation in the foreground
echo "Starting Keyboard Teleop node..."
source ~/px4_ros2_ws/install/setup.bash
ros2 run drone_controller drone_keyboard_teleop
