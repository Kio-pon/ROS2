# ROS 2 Jazzy + PX4 SITL Drone Controller & Simulation

A unified ROS 2 Jazzy and PX4 SITL drone simulation framework featuring autonomous flight controllers, live video streaming, keyboard teleoperation, and a Tkinter-based Ground Control / Mission Control GUI.

---

## 🛠️ System Overview

The project connects ROS 2 Jazzy to the PX4 Autopilot SITL simulator (Gazebo Harmonic) via the **Micro-XRCE-DDS** bridge:

```
+-------------------------------------------------------+
|                 Gazebo 3D Simulation                  |
+-------------------------------------------------------+
        | (camera frames)              ^ (physics & control)
        v                              |
+-----------------------+      +-----------------------+
|  ros_gz image_bridge  |      |   PX4 Autopilot SITL  |
+-----------------------+      +-----------------------+
        |                              ^
        v (ROS 2 Image)                | (uORB messages)
+-------------------------------------------------------+
|                 micro-XRCE-DDS Agent                  |
+-------------------------------------------------------+
        |                              ^
        v (ROS 2 Topics)               | (ROS 2 Topics)
+-------------------------------------------------------+
|                   Mission Control GUI                 |
|             (drone_controller ROS 2 Package)          |
+-------------------------------------------------------+
```

---

## 📋 Prerequisites & Installation

Follow these steps to set up the environment on **Ubuntu 24.04**:

### 1. Install ROS 2 Jazzy Desktop
Follow the instructions in `setup/setup_ros2_jazzy.sh` or run:
```bash
sudo ./setup/setup_ros2_jazzy.sh
```

### 2. Install GUI and Image Processing Dependencies
Install Python's Tkinter and Pillow library:
```bash
sudo apt update
sudo apt install -y python3-tk python3-pil python3-pil.imagetk
```

### 3. Install ROS 2 Packages
```bash
sudo apt install -y ros-jazzy-ros-gz-image ros-jazzy-joy
```

### 4. Setup PX4 Autopilot & DDS Agent
Run the setup script to clone PX4 Autopilot, run the PX4 setup scripts, compile the SITL target, and build the DDS Agent:
```bash
./setup/setup_px4_sitl.sh
```

---

## 🚀 How to Run the Simulation

The project includes several unified launcher scripts inside the `launchers/` directory. For convenience, you can launch the complete simulation directly from the root using `./run_all.sh`.

### 1. Complete Simulation with Live Camera & Mission Control (Recommended)
This boots the DDS Agent, launches Gazebo with a camera-equipped quadcopter, bridges the Gazebo camera into ROS 2, and starts the Ground Station GUI:
```bash
./run_all.sh
```

### 2. Interactive Mission Control GUI (Standard Drone)
Boots the simulation with a standard quadcopter and opens the Tkinter Ground Station:
```bash
./launchers/run_mission_control.sh
```

### 3. Autonomous Flight Mission
Runs a pre-programmed autonomous flight script (`autonomous_mission.py`):
```bash
./launchers/run_flight.sh
```

### 4. Keyboard Teleoperation
Launches keyboard-based flight controls:
```bash
./launchers/run_teleop.sh
```

### 5. Headless Mode (CLI only)
Runs the simulation in headless mode (no Gazebo UI) to save system resources:
```bash
./launchers/run_headless_drone.sh
```

---

## 📁 File Structure

- **`drone_controller/`**: Core ROS 2 Python package containing flight controllers, Ground Station GUI (`mission_control`), keyboard teleoperation, and camera proofing scripts.
- **`launchers/`**: Clean folder containing simulator, headless, teleoperation, and autopilot launcher scripts.
- **`tools/`**: Development and validation utilities (world generators, snappers, asset optimizers, and test suites).
- **`practice/`**: Practice code (loops, tuples, dictionaries, turtlesim launchers) and ROS 2 exercises.
- **`docs/`**: PDFs and Markdown study guides for ROS 2 and PX4 SITL.
- **`setup_*.sh`**: System-level installation and configuration automation scripts.
