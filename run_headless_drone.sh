#!/bin/bash
# A utility script to launch the Micro-XRCE-DDS Agent and the PX4 SITL simulation in headless mode.

echo "================================================="
echo "Starting Headless PX4 SITL Drone & DDS Agent..."
echo "================================================="

# Clean up any existing instances
echo "Stopping any stale PX4, Gazebo, or DDS Agent processes..."
pkill -9 -f px4 || true
pkill -9 -f MicroXRCEAgent || true
pkill -9 -f ruby || true
pkill -9 -f gz || true
sleep 1

# 1. Start the Micro-XRCE-DDS Agent in the background
echo "Starting Micro-XRCE-DDS Agent on UDP port 8888..."
MicroXRCEAgent udp4 -p 8888 > ~/dds_agent.log 2>&1 &
AGENT_PID=$!

# 2. Launch PX4 SITL with Gazebo GUI
echo "Launching PX4 SITL and spawning x500 model..."
unset HEADLESS
export PX4_SYS_AUTOSTART=4001
export PX4_SIM_MODEL=gz_x500
export PX4_GZ_WORLD=lawn
export GZ_CONFIG_PATH="/usr/share/gz:${GZ_CONFIG_PATH:-}"
unset PX4_GZ_MODEL_NAME

cd ~/PX4-Autopilot
./build/px4_sitl_default/bin/px4
