#!/bin/bash
set -e

echo "=========================================="
echo "Installing ROS 2 Jazzy on Ubuntu 24.04..."
echo "=========================================="

export DEBIAN_FRONTEND=noninteractive

# 1. Set locale
echo "[1/4] Setting locales..."
apt-get update && apt-get install -y locales
locale-gen en_US en_US.UTF-8
update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

# 2. Add apt repository
echo "[2/4] Adding ROS 2 apt repository..."
apt-get install -y software-properties-common curl
add-apt-repository -y universe
curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" > /etc/apt/sources.list.d/ros2.list

# 3. Install ROS 2 Jazzy Desktop & dev tools
echo "[3/4] Installing ROS 2 Jazzy Desktop and development packages..."
apt-get update
apt-get install -y \
  ros-jazzy-desktop \
  python3-colcon-common-extensions \
  python3-vcstool \
  python3-rosdep \
  ros-jazzy-ament-cmake \
  python3-pip \
  git \
  build-essential \
  cmake

# 4. Initialize rosdep
echo "[4/4] Initializing rosdep..."
if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then
  rosdep init || echo "rosdep already initialized"
fi

echo "=========================================="
echo "ROS 2 Jazzy installation completed!"
echo "=========================================="
