#!/bin/bash
# Boot PX4 SITL + Gazebo + the micro-XRCE-DDS agent, then open the
# Mission Control ground station GUI (ros2 run drone_controller mission_control).
#
# This is the one-stop launcher. QGroundControl is launched from inside the GUI,
# so it is intentionally not started here.

echo "================================================="
echo "Cleaning up any old simulator or ROS 2 processes..."
echo "================================================="
pkill -9 -f px4 || true
pkill -9 -f MicroXRCEAgent || true
pkill -9 -f ruby || true
pkill -9 -f gz || true
sleep 1

# 1. Start the Micro-XRCE-DDS Agent in the background
echo "Starting DDS Agent..."
MicroXRCEAgent udp4 -p 8888 > ~/dds_agent.log 2>&1 &

# 2. Set environment variables for Grass World & GUI
export PX4_SYS_AUTOSTART=4001
export PX4_SIM_MODEL=gz_x500
export PX4_GZ_WORLD=lawn
unset HEADLESS
unset PX4_GZ_MODEL_NAME

# 3. Launch PX4 SITL + Gazebo in the background (daemon mode)
echo "Launching PX4 SITL and Gazebo Simulator (Grass & Sky)..."
cd ~/PX4-Autopilot
./build/px4_sitl_default/bin/px4 -d > ~/px4.log 2>&1 &
sleep 3

# 4. Bypass GCS / RC safety checks so offboard control is allowed
echo "Configuring flight safety parameters..."
./build/px4_sitl_default/bin/px4-param set NAV_DLL_ACT 0 > /dev/null 2>&1
./build/px4_sitl_default/bin/px4-param set COM_RC_IN_MODE 1 > /dev/null 2>&1

# 5. Wait for the simulator and EKF2 filter to align (GPS lock)
echo "Waiting 12 seconds for the simulator to boot and EKF to align..."
for i in {12..1}; do
    echo -n "$i... "
    sleep 1
done
echo -e "\nInitialization complete!"

# 6. Build the package so the mission_control entry point is registered.
#    (Safe to run every time; colcon is fast for a pure-Python package.
#     Failures here are non-fatal in case you build the workspace elsewhere.)
echo "Building drone_controller (registers the mission_control command)..."
source /opt/ros/jazzy/setup.bash
if [ -d ~/px4_ros2_ws ]; then
    ( cd ~/px4_ros2_ws && colcon build --packages-select drone_controller --symlink-install ) || \
        echo "WARN: colcon build skipped/failed - assuming the workspace is already built."
fi

# 7. Launch the Mission Control GUI
echo "Starting Mission Control GUI..."
source ~/px4_ros2_ws/install/setup.bash
ros2 run drone_controller mission_control
