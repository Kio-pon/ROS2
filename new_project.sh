#!/bin/bash
# A utility script to automate creating a new ROS 2 Python package and symlinking it to the Windows editor folder.
set -e

# Display help message
if [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    echo "Usage: ./new_project.sh <project_name>"
    echo "Usage: ./new_project.sh --name <project_name>"
    exit 0
fi

# Extract project name (supports either name directly or with the --name flag)
PROJECT_NAME=$1
if [ "$1" == "--name" ]; then
    PROJECT_NAME=$2
fi

# Ensure name is provided
if [ -z "$PROJECT_NAME" ]; then
    echo "Error: Please specify a project name."
    echo "Usage: ./new_project.sh <project_name>"
    exit 1
fi

echo "================================================="
echo "Creating ROS 2 package: $PROJECT_NAME..."
echo "================================================="

# Source ROS 2 Jazzy environment
source /opt/ros/jazzy/setup.bash

# 1. Create the package in WSL workspace source folder
cd ~/px4_ros2_ws/src
ros2 pkg create --build-type ament_python "$PROJECT_NAME" --dependencies rclpy

# 2. Move it to the Windows mounted folder
echo "Moving package to Windows side..."
mv ~/px4_ros2_ws/src/"$PROJECT_NAME" /mnt/c/Users/Student/ROS/

# 3. Create a symbolic link pointing from WSL to Windows
echo "Creating symlink back to WSL..."
ln -s /mnt/c/Users/Student/ROS/"$PROJECT_NAME" ~/px4_ros2_ws/src/"$PROJECT_NAME"

echo ""
echo "================================================="
echo "🎉 SUCCESS: Package '$PROJECT_NAME' is ready!"
echo "-------------------------------------------------"
echo "1. Look at the Antigravity editor to write code."
echo "2. Compile it in WSL using:"
echo "   cd ~/px4_ros2_ws && colcon build"
echo "================================================="
