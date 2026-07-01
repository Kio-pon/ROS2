# PX4 + ROS 2 Jazzy: Drone Study Guide

> **How to use this guide:** Follow the video section by section. Every command here targets **ROS 2 Jazzy on Ubuntu 24.04**. Where the video says `humble`, use `jazzy`. The PX4 SITL setup and micro XRCE-DDS agent installation are identical across ROS versions. The px4_msgs package builds the same way on Jazzy.

---

## Part 1: Drone Fundamentals

### 1.1 What Is a Drone?

PX4's official definition: a drone is an unmanned robotic vehicle that can be controlled manually or autonomously.

The four main categories are:

| Abbreviation | Full Name | Example |
|---|---|---|
| UAV | Unmanned Aerial Vehicle | Quadcopter, fixed-wing |
| UGV | Unmanned Ground Vehicle | Curiosity rover, AMR |
| USV | Unmanned Surface Vehicle | Water patrol boat |
| UUV | Unmanned Underwater Vehicle | Submarine drone |

UAV sub-types you will see in PX4:

- **Multi-rotor:** quadcopter, hexacopter. Most common for beginners.
- **Fixed-wing:** airplane-style. Better range, less hover ability.
- **Single-rotor:** helicopter design.
- **Fixed-wing hybrid VTOL:** takes off vertically, flies like a plane. VTOL stands for Vertical Takeoff and Landing.

---

### 1.2 What Is an Autopilot?

An autopilot is a flight stack software running on a real-time operating system on flight controller hardware.

**Flight stack** means guidance, navigation, and control algorithms. PX4 is a flight stack.

**Why use an autopilot at all?** Three reasons:

1. **Stabilization is built in.** If you wire four motors to a frame with no firmware, the drone will crash the moment it lifts. PX4 runs PID loops constantly to keep the drone level. You send `takeoff` and PX4 calculates rotor speeds, pitch, roll, throttle.

2. **Safety features come pre-built.** PX4 has fail-safe logic. If your connection drops, the drone can return home or land. Without this, a lost drone flies away or crashes into something.

3. **Common tasks are automated.** Send `land` once. PX4 descends at a constant velocity, detects ground impact, and disarms the motors. You write zero code for that.

The self-driving car analogy works here: manual control is you driving, autopilot is the car doing it on its own.

---

### 1.3 Common Misconceptions Cleared

**PX4 is not the same as Pixhawk.**

- PX4 is firmware (software).
- Pixhawk is an open hardware standard for building flight controllers.
- Companies like Holybro and CUAV build flight controllers using the Pixhawk standard.
- PX4 runs on Pixhawk-based boards. It also runs on your laptop via SITL.

Think of it like Arduino. Arduino is an open-source hardware standard. Many companies make Arduino-compatible boards. Pixhawk is that standard for flight controllers.

**PX4 is not the same as ArduPilot.**

Both are flight stack firmwares. PX4 pairs with QGroundControl. ArduPilot pairs with Mission Planner. PX4 has deep native integration with ROS 2, which is why this workshop uses it.

**GCS, QGroundControl, and Mission Planner are all software.**

- GCS stands for Ground Control Station. It is any ground-based software that lets you monitor and command a drone.
- QGroundControl is one specific GCS application. Run it on Windows, Linux, Mac, or Android.
- QGroundControl communicates with PX4 over a protocol called MAVLink.
- You also use QGroundControl to flash PX4 firmware onto a flight controller.
- Mission Planner is a different GCS, used mainly with ArduPilot.

**UAS = UAV + GCS.** Unmanned Aerial System includes both the drone and the ground software controlling it.

---

### 1.4 SITL vs HITL

**SITL (Software In The Loop)**

The entire PX4 firmware runs on your laptop alongside the physics simulation. No external hardware. Good for developing and testing logic. This is what the video uses and what you will use today.

**HITL (Hardware In The Loop)**

PX4 firmware runs on a real flight controller board (a Pixhawk board, for example) connected to your laptop. The physics still simulate on your laptop. Use HITL when you need to test real-time performance and sensor load on the actual hardware.

For this guide, you only need SITL. No Pixhawk board required.

---

## Part 2: The Technology Stack

### 2.1 Three Tools You Will Use

| Tool | Role |
|---|---|
| PX4 Autopilot | Flight control firmware. Runs in SITL on your laptop. |
| ROS 2 Jazzy | High-level robot programming framework. You write your logic here. |
| micro XRCE-DDS Agent | Communication bridge between PX4 and ROS 2. |

---

### 2.2 How PX4 and ROS 2 Talk to Each Other

PX4 uses its own internal message system called uORB. ROS 2 uses its own message system. These two cannot talk directly.

The micro XRCE-DDS agent sits between them and translates. Here is the flow:

```
Your ROS 2 Node
     |
     | publishes to ROS 2 topic
     v
micro XRCE-DDS Agent
     |
     | translates ROS 2 msg → uORB msg
     v
PX4 Autopilot (running SITL in Gazebo)
     |
     | sends sensor data back as uORB
     v
micro XRCE-DDS Agent
     |
     | translates uORB msg → ROS 2 msg
     v
Your ROS 2 subscriber
```

PX4 runs the DDS **client**. ROS 2 runs the DDS **agent**. They connect over UDP by default.

**What is DDS?** Data Distribution Service. It is the networking architecture that ROS 2 is built on. micro XRCE-DDS is a lightweight version of that for chips with limited resources, like a flight controller.

---

### 2.3 Companion Computer

A companion computer is the high-level processing board mounted on the drone alongside the flight controller. On a physical drone, a Raspberry Pi is a common companion computer. The Raspberry Pi runs ROS 2 and sends high-level commands to the Pixhawk.

In SITL, your laptop is both the companion computer and the flight controller. The PX4 firmware and your ROS 2 code run on the same machine.

---

## Part 3: Environment Setup

### 3.1 Install ROS 2 Jazzy

The video installs Humble on Ubuntu 22.04. You install **Jazzy on Ubuntu 24.04** instead.

```bash
# Set locale
sudo apt update && sudo apt install locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

# Add the ROS 2 repository
sudo apt install software-properties-common
sudo add-apt-repository universe
sudo apt update && sudo apt install curl -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) \
  signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
  http://packages.ros.org/ros2/ubuntu \
  $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | \
  sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# Install Jazzy
sudo apt update && sudo apt upgrade
sudo apt install ros-jazzy-desktop

# Source automatically on every terminal
echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

Test it:

```bash
ros2
```

You should see the ros2 help menu.

---

### 3.2 Install PX4 Dependencies

```bash
sudo apt update
sudo apt install -y \
  python3-pip \
  python3-colcon-common-extensions \
  python3-vcstool \
  python3-rosdep \
  ros-jazzy-ament-cmake
```

---

### 3.3 Clone and Build PX4 Autopilot

Go to your home directory and clone PX4:

```bash
cd ~
git clone https://github.com/PX4/PX4-Autopilot.git --recursive
```

Run the setup script to install PX4 dependencies:

```bash
bash ~/PX4-Autopilot/Tools/setup/ubuntu.sh
```

Restart your terminal after this step.

Now build PX4 SITL with Gazebo. The drone model used in the video is the X500:

```bash
cd ~/PX4-Autopilot
make px4_sitl gz_x500
```

**Note on Gazebo:** The video refers to `gzx500`. This already targets the new Gazebo (Gazebo Harmonic), not Gazebo Classic. Jazzy uses Gazebo Harmonic natively, so this command works as-is. The `gz_` prefix in PX4 targets signals Gazebo Harmonic.

The first build takes several minutes. When it finishes, Gazebo opens and the X500 drone appears. The terminal shows:

```
INFO  [commander] Ready for takeoff!
```

**Test manual commands in that same terminal:**

```bash
# Arm the motors
commander arm

# Take off (hovers at 2.5 m)
commander takeoff

# Land
commander land

# Disarm (only works after landing)
commander disarm
```

**Never close Gazebo with the X button.** Press Ctrl+C in the PX4 terminal instead. Closing through the GUI leaves background Gazebo processes running and the next launch will fail.

---

### 3.4 Install and Launch QGroundControl

QGroundControl is not ROS-specific. The install steps are the same regardless of your ROS version.

```bash
# Install dependencies
sudo apt install -y gstreamer1.0-plugins-bad \
  gstreamer1.0-libav \
  gstreamer1.0-gl \
  libfuse2 \
  libxcb-xinerama0 \
  libxkbcommon-x11-0

# Make it executable (after downloading the AppImage)
chmod +x ~/Downloads/QGroundControl.AppImage

# Run it
~/Downloads/QGroundControl.AppImage
```

Download the AppImage from: `https://docs.qgroundcontrol.com/master/en/getting_started/download_and_install.html`

Once PX4 SITL runs and QGroundControl opens, they connect automatically over UDP. QGroundControl shows **Ready to fly** in the top bar.

From QGroundControl you can:

- Right-click on the map and send Go to location commands.
- Use the Takeoff, Land, and Return buttons.
- Orbit a point on the map.
- Flash firmware to a real Pixhawk board (not needed for SITL).

---

### 3.5 Install micro XRCE-DDS Agent

The agent is independent of ROS. Build it from source:

```bash
cd ~
git clone https://github.com/eProsima/Micro-XRCE-DDS-Agent.git
cd Micro-XRCE-DDS-Agent
mkdir build && cd build
cmake ..
make
sudo make install
sudo ldconfig /usr/local/lib/
```

**Start the agent** in its own terminal:

```bash
MicroXRCEAgent udp4 -p 8888
```

PX4 SITL connects to this agent on startup. Once connected, the terminal shows the session opening.

---

## Part 4: Setting Up the ROS 2 Workspace

### 4.1 Create the Workspace and Clone px4_msgs

```bash
mkdir -p ~/px4_ros2_ws/src
cd ~/px4_ros2_ws/src
git clone https://github.com/PX4/px4_msgs.git
```

The `px4_msgs` package contains all the ROS 2 message definitions that mirror PX4's uORB messages. You need this package to read or write any PX4 topic from ROS 2.

Build the workspace:

```bash
cd ~/px4_ros2_ws
colcon build --packages-select px4_msgs
source install/local_setup.bash
```

Add the source line to `.bashrc`:

```bash
echo "source ~/px4_ros2_ws/install/local_setup.bash" >> ~/.bashrc
```

---

### 4.2 Verify PX4 Topics Are Visible in ROS 2

Run three terminals side by side:

**Terminal 1** — PX4 SITL:
```bash
cd ~/PX4-Autopilot
make px4_sitl gz_x500
```

**Terminal 2** — micro XRCE-DDS Agent:
```bash
MicroXRCEAgent udp4 -p 8888
```

**Terminal 3** — Check ROS 2 topics:
```bash
source ~/px4_ros2_ws/install/local_setup.bash
ros2 topic list
```

You should see topics like:

```
/fmu/in/trajectory_setpoint
/fmu/in/vehicle_command
/fmu/out/vehicle_local_position
/fmu/out/vehicle_status
/fmu/out/battery_status
```

**`/fmu/in/`** topics are ones PX4 reads. Your ROS 2 node publishes to these.

**`/fmu/out/`** topics are ones PX4 writes. Your ROS 2 node subscribes to these.

Read vehicle status from the drone:

```bash
ros2 topic echo /fmu/out/vehicle_status
```

You should see live data. If you get a `Cannot find message type` error, you have not sourced the `px4_msgs` workspace yet.

---

## Part 5: The Three Pillars of Offboard Control

Before writing any control code, you must understand why offboard control fails silently for most beginners.

PX4 has many flight modes. **Offboard mode** is the one where PX4 hands control to your ROS 2 code. PX4 does not give up control easily. You must satisfy three conditions simultaneously and continuously. If any one condition breaks, PX4 exits offboard mode and enters fail-safe, then lands.

---

### Pillar 1: QoS Compatibility

QoS stands for Quality of Service. It controls how ROS 2 delivers messages.

PX4 publishes and subscribes with a specific QoS profile. If your ROS 2 node uses a different QoS, the connection silently fails. No error message. No data. Just silence.

The three QoS settings that matter:

| Setting | PX4's Value | What It Means |
|---|---|---|
| Reliability | Best Effort | PX4 does not retry dropped packets |
| Durability | Transient Local | Messages persist briefly for late subscribers |
| History | Keep Last (depth 1) | Only the most recent message is buffered |

Use this QoS profile in every publisher and subscriber that talks to PX4:

```python
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy

px4_qos = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    history=HistoryPolicy.KEEP_LAST,
    depth=1
)
```

Pass this profile when you create a publisher or subscription:

```python
self.vehicle_status_sub = self.create_subscription(
    VehicleStatus,
    '/fmu/out/vehicle_status',
    self.vehicle_status_callback,
    px4_qos
)
```

---

### Pillar 2: Continuous Heartbeat

PX4 needs proof that your companion computer is alive. It checks this proof of life at a frequency of at least 2 Hz. If your code crashes, or the heartbeat drops below 2 Hz, PX4 exits offboard mode and lands.

The heartbeat is an `OffboardControlMode` message. Publish it continuously before you request offboard mode and keep publishing for as long as you want to stay in control.

Here is the heartbeat function:

```python
from px4_msgs.msg import OffboardControlMode

def publish_offboard_heartbeat(self):
    msg = OffboardControlMode()
    msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
    msg.position = True      # tell PX4 you will send position setpoints
    msg.velocity = False
    msg.acceleration = False
    msg.attitude = False
    msg.body_rate = False
    self.offboard_control_pub.publish(msg)
```

Call this function from a timer that runs at 10 Hz or higher:

```python
self.timer = self.create_timer(0.1, self.timer_callback)

def timer_callback(self):
    self.publish_offboard_heartbeat()
```

**Set `position = True` for position control, `velocity = True` for velocity control.** Set only one to True at a time.

---

### Pillar 3: Continuous Trajectory Setpoints

The moment PX4 switches to offboard mode, your code must already be flooding it with setpoints. A setpoint tells the drone where to go (position) or how fast to move (velocity).

PX4 checks its setpoint buffer every cycle. If the buffer is empty, it exits offboard mode. One setpoint sent once is not enough. Your timer callback must publish a new setpoint every cycle.

Position setpoint example:

```python
from px4_msgs.msg import TrajectorySetpoint

def publish_position_setpoint(self, x, y, z, yaw=0.0):
    msg = TrajectorySetpoint()
    msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
    msg.position = [x, y, z]       # NED frame, meters
    msg.yaw = yaw                   # radians, NED frame
    self.trajectory_pub.publish(msg)
```

Velocity setpoint example (for joystick control):

```python
def publish_velocity_setpoint(self, vx, vy, vz, yaw_rate=0.0):
    msg = TrajectorySetpoint()
    msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
    msg.position = [float('nan'), float('nan'), float('nan')]  # ignore position
    msg.velocity = [vx, vy, vz]    # NED frame, m/s
    msg.yaw = float('nan')
    msg.yawspeed = yaw_rate         # rad/s
    self.trajectory_pub.publish(msg)
```

Pass `float('nan')` for any field you are not controlling. This tells PX4 to ignore that field.

---

## Part 6: Frame Conventions

This is the most common source of confusion for new drone developers.

PX4 uses the **NED frame** (North, East, Down):
- X points North (forward when drone faces North)
- Y points East (right)
- Z points Down (positive Z is toward the ground)

ROS 2 uses the **ENU frame** (East, North, Up) for world coordinates and **FLU** (Forward, Left, Up) for body coordinates:
- X points East (world) or Forward (body)
- Y points North (world) or Left (body)
- Z points Up

**For SITL and basic teleoperation, here is the practical impact:**

When you want the drone to go up 5 meters in position control, send `z = -5.0` (not `+5.0`) in the NED `TrajectorySetpoint`. Down is positive in NED, so up is negative.

```python
# Go up 5 meters
publish_position_setpoint(x=0.0, y=0.0, z=-5.0)
```

**For velocity control with a joystick**, you read joystick inputs in FLU (intuitive body frame), then convert to NED before publishing. The conversion:

```python
import math

def flu_to_ned(self, vx_flu, vy_flu, vz_flu, yaw_ned):
    # Rotate FLU velocity into NED using current drone yaw
    cos_yaw = math.cos(yaw_ned)
    sin_yaw = math.sin(yaw_ned)

    vx_ned = cos_yaw * vx_flu - sin_yaw * vy_flu
    vy_ned = sin_yaw * vx_flu + cos_yaw * vy_flu
    vz_ned = -vz_flu  # FLU up is positive, NED down is positive

    return vx_ned, vy_ned, vz_ned
```

**Yaw vs yaw rate:**

- `yaw` is an absolute angle in radians. Set it to 1.57 and the drone rotates to face 90° and stops.
- `yawspeed` is angular velocity in rad/s. Set it to 1.0 and the drone rotates continuously at 1 rad/s. Use yaw rate for joystick control.

---

## Part 7: Position Offboard Control (Full Code)

### 7.1 Warmup Logic

PX4 will not switch to offboard mode after just one heartbeat. You must send at least 10 heartbeats first, then request the mode change. This is called warming up.

```python
self.offboard_setpoint_counter = 0

def timer_callback(self):
    self.publish_offboard_heartbeat()

    if self.offboard_setpoint_counter < 10:
        self.offboard_setpoint_counter += 1
    elif self.offboard_setpoint_counter == 10:
        self.engage_offboard_mode()
        self.arm()
        self.offboard_setpoint_counter += 1

    # Always publish a setpoint after warmup
    if self.offboard_setpoint_counter > 10:
        self.publish_position_setpoint(0.0, 0.0, -5.0)
```

### 7.2 Arming and Engaging Offboard Mode

```python
from px4_msgs.msg import VehicleCommand

def publish_vehicle_command(self, command, param1=0.0, param2=0.0):
    msg = VehicleCommand()
    msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
    msg.param1 = param1
    msg.param2 = param2
    msg.command = command
    msg.target_system = 1
    msg.target_component = 1
    msg.source_system = 1
    msg.source_component = 1
    msg.from_external = True
    self.vehicle_command_pub.publish(msg)

def arm(self):
    self.publish_vehicle_command(
        VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM,
        param1=1.0
    )

def disarm(self):
    self.publish_vehicle_command(
        VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM,
        param1=0.0
    )

def engage_offboard_mode(self):
    self.publish_vehicle_command(
        VehicleCommand.VEHICLE_CMD_DO_SET_MODE,
        param1=1.0,
        param2=6.0
    )
```

`param2=6.0` is the PX4 code for offboard mode.

### 7.3 Reading Drone State

```python
from px4_msgs.msg import VehicleLocalPosition, VehicleStatus

def vehicle_local_position_callback(self, msg):
    self.vehicle_local_position = msg

def vehicle_status_callback(self, msg):
    self.vehicle_status = msg
```

Check if the drone is in offboard mode:

```python
# VehicleStatus.NAVIGATION_STATE_OFFBOARD == 14
if self.vehicle_status.nav_state == VehicleStatus.NAVIGATION_STATE_OFFBOARD:
    print("In offboard mode")
```

Check current altitude:

```python
current_z = self.vehicle_local_position.z  # NED, negative is up
```

### 7.4 Landing

```python
def land(self):
    self.publish_vehicle_command(VehicleCommand.VEHICLE_CMD_NAV_LAND)
```

Once you call `land()`, PX4 takes back control. Do not keep sending setpoints.

---

## Part 8: Joystick Integration

### 8.1 Install the Joy Package

```bash
sudo apt install ros-jazzy-joy
```

### 8.2 Find Your Joystick Axis Mapping

Install jstest-gtk to see button and axis numbers for your specific controller:

```bash
sudo apt install jstest-gtk
jstest-gtk
```

Connect your joystick, click Refresh, then open it. Move each stick and watch which axis number changes. Press each button and note which button number lights up. Write these numbers down before coding.

### 8.3 Run the Joy Node

The joy node reads hardware joystick input and publishes it as a ROS 2 topic:

```bash
ros2 run joy joy_node
```

Check what it publishes:

```bash
ros2 topic echo /joy
```

You see `axes` (float array, -1.0 to 1.0) and `buttons` (int array, 0 or 1).

### 8.4 Joystick Node Structure

Create a ROS 2 node that subscribes to `/joy` and converts axis values to drone velocity commands:

```python
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from geometry_msgs.msg import Twist

class JoystickTeleop(Node):
    def __init__(self):
        super().__init__('joystick_teleop')

        # Axis mapping (change these to match your controller)
        self.AXIS_VX = 1       # left stick up/down → forward/back
        self.AXIS_VY = 0       # left stick left/right → strafe
        self.AXIS_VZ = 4       # right stick up/down → altitude
        self.AXIS_YAW = 3      # right stick left/right → yaw rate

        # Button mapping
        self.BTN_ARM = 0       # button A
        self.BTN_DISARM = 3    # button Y
        self.BTN_HOVER = 2     # button X → zero velocity

        # Speed limits
        self.MAX_VX = 0.8      # m/s
        self.MAX_VY = 0.8
        self.MAX_VZ = 0.5
        self.MAX_YAW_RATE = 1.5  # rad/s
        self.DEAD_ZONE = 0.1

        # Hover Z velocity target (drone stays at altitude)
        self.HOVER_VZ = 0.0

        self.joy_sub = self.create_subscription(
            Joy, '/joy', self.joy_callback, 10
        )
        self.cmd_pub = self.create_publisher(
            Twist, '/offboard_velocity_cmd', 10
        )

    def apply_dead_zone(self, value, threshold):
        if abs(value) < threshold:
            return 0.0
        return value

    def joy_callback(self, msg):
        vx = self.apply_dead_zone(msg.axes[self.AXIS_VX], self.DEAD_ZONE)
        vy = self.apply_dead_zone(msg.axes[self.AXIS_VY], self.DEAD_ZONE)
        vz_raw = msg.axes[self.AXIS_VZ]
        yaw = self.apply_dead_zone(msg.axes[self.AXIS_YAW], self.DEAD_ZONE)

        # Scale to speed limits
        vx *= self.MAX_VX
        vy *= self.MAX_VY
        yaw *= self.MAX_YAW_RATE

        # Throttle: center stick = hover, up = climb, down = descend
        vz = ((vz_raw + 1.0) / 2.0 - 0.5) * self.MAX_VZ * 2.0

        cmd = Twist()
        cmd.linear.x = vx
        cmd.linear.y = vy
        cmd.linear.z = vz
        cmd.angular.z = yaw
        self.cmd_pub.publish(cmd)
```

---

## Part 9: Velocity Offboard Control Node

This node subscribes to joystick velocity commands and sends them to PX4 via offboard control.

```python
import rclpy
from rclpy.node import Node
import math
from px4_msgs.msg import (
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleLocalPosition,
    VehicleStatus
)
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy

class VelocityOffboardController(Node):
    def __init__(self):
        super().__init__('velocity_offboard_controller')

        px4_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )

        # Publishers
        self.offboard_mode_pub = self.create_publisher(
            OffboardControlMode, '/fmu/in/offboard_control_mode', px4_qos)
        self.trajectory_pub = self.create_publisher(
            TrajectorySetpoint, '/fmu/in/trajectory_setpoint', px4_qos)
        self.vehicle_cmd_pub = self.create_publisher(
            VehicleCommand, '/fmu/in/vehicle_command', px4_qos)

        # Subscribers
        self.local_pos_sub = self.create_subscription(
            VehicleLocalPosition, '/fmu/out/vehicle_local_position',
            self.local_position_callback, px4_qos)
        self.status_sub = self.create_subscription(
            VehicleStatus, '/fmu/out/vehicle_status',
            self.vehicle_status_callback, px4_qos)
        self.velocity_cmd_sub = self.create_subscription(
            Twist, '/offboard_velocity_cmd',
            self.velocity_cmd_callback, 10)
        self.arm_cmd_sub = self.create_subscription(
            Bool, '/arm_command',
            self.arm_cmd_callback, 10)

        # State
        self.vehicle_status = VehicleStatus()
        self.local_position = VehicleLocalPosition()
        self.vx = 0.0
        self.vy = 0.0
        self.vz = 0.0
        self.yaw_rate = 0.0
        self.current_yaw = 0.0
        self.warmup_counter = 0
        self.armed = False

        self.timer = self.create_timer(0.05, self.timer_callback)  # 20 Hz

    def local_position_callback(self, msg):
        self.local_position = msg
        # Extract yaw from quaternion
        q = [msg.q[0], msg.q[1], msg.q[2], msg.q[3]]
        self.current_yaw = math.atan2(
            2.0 * (q[0] * q[3] + q[1] * q[2]),
            1.0 - 2.0 * (q[2] ** 2 + q[3] ** 2)
        )

    def vehicle_status_callback(self, msg):
        self.vehicle_status = msg

    def velocity_cmd_callback(self, msg):
        self.vx = msg.linear.x
        self.vy = msg.linear.y
        self.vz = msg.linear.z
        self.yaw_rate = msg.angular.z

    def arm_cmd_callback(self, msg):
        if msg.data and not self.armed:
            self.engage_offboard_mode()
            import time
            time.sleep(0.5)
            self.arm()
            self.armed = True
        elif not msg.data:
            self.disarm()
            self.armed = False

    def publish_offboard_heartbeat(self):
        msg = OffboardControlMode()
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        msg.position = False
        msg.velocity = True
        msg.acceleration = False
        self.offboard_mode_pub.publish(msg)

    def publish_velocity_setpoint(self):
        # Convert FLU joystick input to NED setpoint
        vx_ned, vy_ned, vz_ned = self.flu_to_ned(
            self.vx, self.vy, self.vz, self.current_yaw)

        msg = TrajectorySetpoint()
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        msg.position = [float('nan'), float('nan'), float('nan')]
        msg.velocity = [vx_ned, vy_ned, vz_ned]
        msg.yaw = float('nan')
        msg.yawspeed = self.yaw_rate
        self.trajectory_pub.publish(msg)

    def flu_to_ned(self, vx, vy, vz, yaw):
        cos_y = math.cos(yaw)
        sin_y = math.sin(yaw)
        vx_ned = cos_y * vx - sin_y * vy
        vy_ned = sin_y * vx + cos_y * vy
        vz_ned = -vz
        return vx_ned, vy_ned, vz_ned

    def publish_vehicle_command(self, command, param1=0.0, param2=0.0):
        msg = VehicleCommand()
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        msg.param1 = param1
        msg.param2 = param2
        msg.command = command
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        self.vehicle_cmd_pub.publish(msg)

    def arm(self):
        self.publish_vehicle_command(
            VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, param1=1.0)

    def disarm(self):
        self.publish_vehicle_command(
            VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, param1=0.0)

    def engage_offboard_mode(self):
        self.publish_vehicle_command(
            VehicleCommand.VEHICLE_CMD_DO_SET_MODE,
            param1=1.0, param2=6.0)

    def timer_callback(self):
        self.publish_offboard_heartbeat()

        if self.warmup_counter < 10:
            self.warmup_counter += 1
            # Send dummy setpoints during warmup
            msg = TrajectorySetpoint()
            msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
            msg.position = [float('nan'), float('nan'), float('nan')]
            msg.velocity = [0.0, 0.0, 0.0]
            self.trajectory_pub.publish(msg)
            return

        self.publish_velocity_setpoint()


def main(args=None):
    rclpy.init(args=args)
    node = VelocityOffboardController()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
```

---

## Part 10: Launch File for the Full Pipeline

Create a launch file that starts all three components at once:

```python
from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node

def generate_launch_description():
    # Start PX4 SITL in a new terminal window
    px4_sitl = ExecuteProcess(
        cmd=['bash', '-c',
             'cd ~/PX4-Autopilot && make px4_sitl gz_x500'],
        output='screen'
    )

    # Start micro XRCE-DDS agent
    dds_agent = ExecuteProcess(
        cmd=['MicroXRCEAgent', 'udp4', '-p', '8888'],
        output='screen'
    )

    # Start joy node for joystick input
    joy_node = Node(
        package='joy',
        executable='joy_node',
        name='joy_node',
        output='screen'
    )

    # Start joystick teleop
    joystick_teleop = Node(
        package='px4_offboard_control',
        executable='joystick_teleop',
        name='joystick_teleop',
        output='screen'
    )

    # Start velocity offboard controller
    velocity_controller = Node(
        package='px4_offboard_control',
        executable='velocity_offboard_controller',
        name='velocity_offboard_controller',
        output='screen'
    )

    return LaunchDescription([
        px4_sitl,
        dds_agent,
        joy_node,
        joystick_teleop,
        velocity_controller
    ])
```

Run it:

```bash
ros2 launch px4_offboard_control joystick_teleop.launch.py
```

---

## Part 11: Package Setup

### 11.1 Package Structure

```
px4_offboard_control/
  config/
  launch/
    joystick_teleop.launch.py
  px4_offboard_control/
    __init__.py
    joystick_teleop.py
    velocity_offboard_controller.py
    position_offboard_controller.py
  setup.py
  package.xml
```

### 11.2 package.xml Dependencies

```xml
<depend>rclpy</depend>
<depend>px4_msgs</depend>
<depend>sensor_msgs</depend>
<depend>geometry_msgs</depend>
<depend>std_msgs</depend>
<depend>joy</depend>
```

### 11.3 setup.py Entry Points

```python
entry_points={
    'console_scripts': [
        'joystick_teleop = px4_offboard_control.joystick_teleop:main',
        'velocity_offboard_controller = px4_offboard_control.velocity_offboard_controller:main',
        'position_offboard_controller = px4_offboard_control.position_offboard_controller:main',
    ],
},
```

---

## Part 12: Running the Complete System

Open four terminals. Run each command in its own terminal:

**Terminal 1 — PX4 SITL:**
```bash
cd ~/PX4-Autopilot
make px4_sitl gz_x500
```

**Terminal 2 — DDS Agent:**
```bash
MicroXRCEAgent udp4 -p 8888
```

**Terminal 3 — Your ROS 2 nodes:**
```bash
source ~/px4_ros2_ws/install/local_setup.bash
ros2 launch px4_offboard_control joystick_teleop.launch.py
```

**Terminal 4 — Monitor topics (optional):**
```bash
source ~/px4_ros2_ws/install/local_setup.bash
ros2 topic echo /fmu/out/vehicle_local_position
```

**Control sequence with a joystick:**

1. Press A to arm. The drone motors spin up.
2. Push the throttle stick up. The drone lifts off.
3. Center the throttle stick. The drone hovers.
4. Move the left stick to fly forward, backward, left, right.
5. Move the right stick to rotate (yaw).
6. Push throttle down to descend.
7. Press Y to disarm after landing.

---

## Quick Reference: Humble vs. Jazzy Changes

| Topic | Humble (Video) | Jazzy (This Guide) |
|---|---|---|
| Ubuntu | 22.04 | 24.04 |
| Install pkg prefix | `ros-humble-*` | `ros-jazzy-*` |
| Source path | `/opt/ros/humble/setup.bash` | `/opt/ros/jazzy/setup.bash` |
| Joy package | `ros-humble-joy` | `ros-jazzy-joy` |
| PX4 SITL command | `make px4_sitl gz_x500` | Same — no change |
| Gazebo version | Gazebo (Harmonic) | Same — no change |
| micro XRCE-DDS | Same build steps | Same — no change |
| px4_msgs | Clone main branch | Same — no change |
| QoS profiles | Same | Same — no change |
| Offboard control code | Same Python logic | Same — no change |

The PX4 side and the DDS side do not know or care which ROS version you run. Only the ROS-specific packages change.

---

## Quick Reference: Key PX4 Message Types

| Message | Direction | Purpose |
|---|---|---|
| `OffboardControlMode` | ROS → PX4 (`/fmu/in/`) | Heartbeat. Sets which control axes are active. |
| `TrajectorySetpoint` | ROS → PX4 (`/fmu/in/`) | Position or velocity targets. |
| `VehicleCommand` | ROS → PX4 (`/fmu/in/`) | Arm, disarm, mode changes. |
| `VehicleStatus` | PX4 → ROS (`/fmu/out/`) | Current mode, arm state. |
| `VehicleLocalPosition` | PX4 → ROS (`/fmu/out/`) | Current XYZ position and velocity. |
| `BatteryStatus` | PX4 → ROS (`/fmu/out/`) | Battery level. |

---

## Common Errors and Fixes

**"Cannot find message type px4_msgs/msg/..."**

You have not sourced the px4_msgs workspace. Run:
```bash
source ~/px4_ros2_ws/install/local_setup.bash
```

**Drone does not switch to offboard mode.**

Check all three pillars: QoS profile matches, heartbeat publishes at 10 Hz+, setpoints publish at the same time. The most common cause is a wrong QoS durability setting.

**Drone arms but immediately disarms.**

The trajectory setpoint stream stopped. Make sure your timer callback publishes a setpoint every cycle, not just once.

**Gazebo does not open after Ctrl+C.**

Background Gazebo processes are still running. Kill them:
```bash
pkill -f gz
pkill -f gzserver
pkill -f gzclient
```

**`ros2 topic list` shows no drone topics.**

The DDS agent is not running, or PX4 SITL has not connected to it yet. Check the DDS agent terminal for a session-open message. Restart both in order: SITL first, agent second.

**Joystick axes are inverted or mismatched.**

Run `jstest-gtk`, move each stick, and record the axis numbers. Update `AXIS_VX`, `AXIS_VY`, etc. in your joystick node to match your hardware.

---

## Next Steps After This Guide

1. **Square trajectory in position control.** Send four position setpoints in sequence: (5, 0, -5), (5, 5, -5), (0, 5, -5), (0, 0, -5). Use the vehicle local position feedback to know when each waypoint is reached before sending the next one.

2. **Attach a camera to the X500.** Add a camera sensor to the drone's URDF in PX4's model folder. Bridge the image topic to ROS 2 and run a computer vision node.

3. **Obstacle avoidance.** Attach a LiDAR or depth camera. Subscribe to the point cloud in ROS 2. Modify velocity commands to avoid detected obstacles before publishing to PX4.

4. **Move to real hardware.** Replace SITL with a Pixhawk-based flight controller. Connect the Pixhawk to a Raspberry Pi via USB or UART. Run the DDS agent on the Raspberry Pi. Your ROS 2 code transfers with minimal changes.

---

*All commands target ROS 2 Jazzy Jalisco on Ubuntu 24.04 and PX4 v1.14+. For the latest PX4 documentation, visit `https://docs.px4.io`. For ROS 2 Jazzy documentation, visit `https://docs.ros.org/en/jazzy`.*
