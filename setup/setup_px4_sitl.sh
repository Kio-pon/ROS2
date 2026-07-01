#!/bin/bash
set -e

echo "=========================================="
echo "Setting up PX4 Autopilot & Dependencies..."
echo "=========================================="

export DEBIAN_FRONTEND=noninteractive

# 1. Clone PX4 Autopilot if not already present
cd ~
if [ ! -d "PX4-Autopilot" ]; then
  echo "[1/5] Cloning PX4-Autopilot repository..."
  git clone https://github.com/PX4/PX4-Autopilot.git --recursive
else
  echo "[1/5] PX4-Autopilot already cloned."
fi

# 2. Run the Ubuntu setup script non-interactively
echo "[2/5] Running PX4 Ubuntu setup script..."
# Force non-interactive for apt-get inside ubuntu.sh
export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring
bash ~/PX4-Autopilot/Tools/setup/ubuntu.sh --no-nuttx

# 3. Build PX4 SITL (DONT_RUN=1 to compile only, using -j2 for memory safety)
echo "[3/5] Compiling PX4 SITL..."
cd ~/PX4-Autopilot
rm -rf build/
# We limit parallel make jobs to 2 to avoid memory depletion on i3
DONT_RUN=1 make -j2 px4_sitl

# 4. Clone and compile Micro-XRCE-DDS-Agent
echo "[4/5] Setting up Micro-XRCE-DDS Agent..."
cd ~
if [ ! -d "Micro-XRCE-DDS-Agent" ]; then
  git clone https://github.com/eProsima/Micro-XRCE-DDS-Agent.git
else
  echo "Micro-XRCE-DDS-Agent already cloned."
fi
cd Micro-XRCE-DDS-Agent
mkdir -p build && cd build
cmake ..
make -j2
sudo make install
sudo ldconfig /usr/local/lib/

# 5. Create ROS 2 workspace, clone px4_msgs, and build
echo "[5/5] Creating and building ROS 2 workspace..."
mkdir -p ~/px4_ros2_ws/src
cd ~/px4_ros2_ws/src
if [ ! -d "px4_msgs" ]; then
  git clone https://github.com/PX4/px4_msgs.git
else
  echo "px4_msgs already cloned."
fi
cd ~/px4_ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install

# Source setups in .bashrc if not already present
if ! grep -q "source /opt/ros/jazzy/setup.bash" ~/.bashrc; then
  echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
fi
if ! grep -q "source ~/px4_ros2_ws/install/local_setup.bash" ~/.bashrc; then
  echo "source ~/px4_ros2_ws/install/local_setup.bash" >> ~/.bashrc
fi

echo "=========================================="
echo "PX4 Autopilot & DDS Agent setup completed!"
echo "=========================================="
