#!/bin/bash
# A utility script to run TurtleSim and the keyboard teleoperation node in a single terminal.

echo "================================================="
echo "Starting TurtleSim Practice Environment..."
echo "================================================="

# Source ROS 2 setup
source /opt/ros/jazzy/setup.bash

# 1. Start TurtleSim Node in the background
echo "Launching TurtleSim GUI in background..."
ros2 run turtlesim turtlesim_node > /dev/null 2>&1 &
SIM_PID=$!

# Wait for the simulator window to open
sleep 1.5

# 2. Start Keyboard Teleoperation in the foreground
echo "-------------------------------------------------"
echo "Keyboard Controller is active below."
echo "Use the arrow keys to drive the turtle."
echo "Press Ctrl+C inside this terminal to exit both."
echo "-------------------------------------------------"
ros2 run turtlesim turtle_teleop_key

# 3. Clean up the simulator when keyboard control is closed
echo "Cleaning up simulator..."
kill $SIM_PID > /dev/null 2>&1
echo "Done!"
