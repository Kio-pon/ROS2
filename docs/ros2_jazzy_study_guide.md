# ROS 2 Jazzy Study Guide

> **How to use this guide:** Follow the video top to bottom. Every command here is updated for **ROS 2 Jazzy on Ubuntu 24.04**. Where the video shows `humble`, use `jazzy`. Where the video shows Gazebo Classic, use Gazebo Harmonic instead. All other concepts transfer directly.

---

## Part 1: Environment Setup

### 1.1 WSL Setup (Windows Users Only)

This step is optional. Skip it if you already run Ubuntu 24.04 natively.

Open PowerShell as administrator and run:

```bash
wsl --install
```

Restart your PC. Then list available distributions:

```bash
wsl --list --online
```

Install Ubuntu 24.04:

```bash
wsl --install -d Ubuntu-24.04
```

Install the WSL extension in VS Code. Then open your Ubuntu terminal and type:

```bash
code .
```

This opens VS Code connected to your WSL environment.

---

### 1.2 Installing ROS 2 Jazzy

The video installs Humble on Ubuntu 22.04. You will install Jazzy on Ubuntu 24.04 instead. Jazzy was released May 23, 2024, and its end-of-life date is May 2029.

Run these commands in order:

```bash
# Set locale
sudo apt update && sudo apt install locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

# Add the ROS 2 apt repository
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

# Install ROS 2 Jazzy
sudo apt update && sudo apt upgrade
sudo apt install ros-jazzy-desktop
```

Test that it installed correctly:

```bash
source /opt/ros/jazzy/setup.bash
ros2
```

You should see the ros2 help output.

---

### 1.3 Sourcing ROS 2 (Automatic Setup)

The video shows adding the source command to `.bashrc`. Do the same for Jazzy:

```bash
echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

Every new terminal will now have ros2 commands available without manual sourcing.

Also install and set up `rosdep`:

```bash
sudo rosdep init
rosdep update
```

---

## Part 2: Core ROS 2 Concepts

### 2.1 Running Executables and Packages

A **package** is a folder that holds code, build instructions, and configuration files. An **executable** is a program built from that code. You run executables with:

```bash
ros2 run <package_name> <executable_name>
```

Install the TurtleSim package for practice:

```bash
sudo apt install ros-jazzy-turtlesim
```

List all available packages:

```bash
ros2 pkg list
```

List executables in a specific package:

```bash
ros2 pkg executables turtlesim
```

Run the TurtleSim node:

```bash
ros2 run turtlesim turtlesim_node
```

In a second terminal, run the teleop node to control the turtle:

```bash
ros2 run turtlesim turtle_teleop_key
```

Use arrow keys to move the turtle.

**Where packages live:** All packages installed by apt land in `/opt/ros/jazzy/`.

---

### 2.2 Nodes

A **node** is the primary unit of computation in ROS 2. Nodes communicate with each other to form an application. List running nodes:

```bash
ros2 node list
```

Get detailed info about a node:

```bash
ros2 node info /turtlesim
```

This output shows the node's subscribers, publishers, service servers, service clients, action servers, and action clients.

A node is a C++ or Python object that inherits from the `Node` class. Below is the simplest possible C++ node:

```cpp
#include "rclcpp/rclcpp.hpp"

int main(int argc, char * argv[]) {
  rclcpp::init(argc, argv);
  auto node = rclcpp::Node::make_shared("simple_node");
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
```

`rclcpp::spin(node)` blocks and keeps the node alive, processing any incoming callbacks.

---

### 2.3 Topics

Topics carry data between nodes. A **publisher** sends data to a topic. A **subscriber** receives it. This is a one-to-many, asynchronous communication model.

Run TurtleSim and teleop first, then:

```bash
# List all active topics
ros2 topic list

# List topics with their message types
ros2 topic list -t

# View messages on a topic in real time
ros2 topic echo /turtle1/cmd_vel

# View topic info
ros2 topic info /turtle1/cmd_vel

# View the message type definition
ros2 interface show geometry_msgs/msg/Twist

# Check publish frequency
ros2 topic hz /turtle1/pose
```

**Publish a message once from the terminal:**

```bash
ros2 topic pub --once /turtle1/cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 2.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 1.8}}"
```

**Publish at a rate of 1 Hz:**

```bash
ros2 topic pub --rate 1 /turtle1/cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 2.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 1.8}}"
```

**Visualize the computation graph:**

```bash
ros2 run rqt_graph rqt_graph
```

---

### 2.4 Services

Services use a request/response model. A **client** sends a request. A **server** responds. This differs from topics, which stream data continuously.

```bash
# List all services
ros2 service list

# List services with types
ros2 service list -t

# Find services of a specific type
ros2 service find std_srvs/srv/Empty

# View the service interface
ros2 interface show turtlesim/srv/Spawn

# Call a service (clear the turtle's drawing)
ros2 service call /clear std_srvs/srv/Empty {}

# Spawn a second turtle
ros2 service call /spawn turtlesim/srv/Spawn \
  "{x: 2.0, y: 2.0, theta: 0.2, name: 'turtle2'}"
```

---

### 2.5 Parameters

Parameters configure a node's behavior. They work like function inputs but for an entire running node.

```bash
# List all parameters
ros2 param list

# Get a parameter value
ros2 param get /turtlesim background_r

# Set a parameter value
ros2 param set /turtlesim background_g 255

# Dump all parameters for a node
ros2 param dump /turtlesim

# Save parameters to a YAML file
ros2 param dump /turtlesim > turtlesim.yaml

# Load parameters from a file
ros2 param load /turtlesim turtlesim.yaml

# Pass a parameter at startup
ros2 run turtlesim turtlesim_node --ros-args -p background_r:=255
```

To load a parameter file at startup:

```bash
ros2 run turtlesim turtlesim_node --ros-args \
  --params-file turtlesim.yaml
```

---

### 2.6 Actions

Actions add a **goal**, **feedback**, and **result** on top of the service model. Use them when a task takes time and you want progress updates.

```bash
# List all actions
ros2 action list

# List actions with types
ros2 action list -t

# View action info
ros2 action info /turtle1/rotate_absolute

# View the action interface
ros2 interface show turtlesim/action/RotateAbsolute

# Send an action goal
ros2 action send_goal /turtle1/rotate_absolute \
  turtlesim/action/RotateAbsolute "{theta: 1.57}"
```

In the teleop window, press `G`, `B`, `V`, `C`, `D`, `E`, `R`, `T` to send rotation goals. Press `F` to cancel mid-rotation.

**Key behavior:**
- The node returns `RUNNING` while working toward the goal.
- It returns the final result when done.
- If you send a new goal before the old one finishes, it aborts the previous goal.

---

## Part 3: Workspace and Build Tools

### 3.1 The ROS 2 Workspace

A workspace is a directory that holds your packages. It has a specific folder structure:

```
ros2_ws/
  src/        ← put your packages here
  build/      ← generated by colcon
  install/    ← generated by colcon
  log/        ← generated by colcon
```

Create a workspace:

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws
```

The `build`, `install`, and `log` folders are created automatically when you build.

---

### 3.2 Colcon Build Tool

`colcon` builds all packages in your workspace. Always run it from the workspace root.

```bash
cd ~/ros2_ws
colcon build --symlink-install
```

`--symlink-install` creates symbolic links instead of copying files. This means you can edit Python scripts or config files without rebuilding.

After building, source the workspace overlay:

```bash
source install/local_setup.bash
```

Add this to `.bashrc` so it sources automatically:

```bash
echo "source ~/ros2_ws/install/local_setup.bash" >> ~/.bashrc
```

**Build a single package:**

```bash
colcon build --symlink-install --packages-select my_package
```

**Check for missing dependencies before building:**

```bash
rosdep install --from-paths src --ignore-src -r -y
```

To reset your workspace, delete the three generated folders:

```bash
rm -rf build install log
```

---

### 3.3 Creating Your Own Package

Navigate to the `src` folder inside your workspace, then create a package:

**C++ package:**

```bash
cd ~/ros2_ws/src
ros2 pkg create --build-type ament_cmake my_package \
  --dependencies rclcpp std_msgs
```

**Python package:**

```bash
cd ~/ros2_ws/src
ros2 pkg create --build-type ament_python my_py_package \
  --dependencies rclpy std_msgs
```

Every package has two required files: `package.xml` (metadata and dependencies) and `CMakeLists.txt` for C++ or `setup.py` for Python.

Build and run your new package:

```bash
cd ~/ros2_ws
colcon build --symlink-install --packages-select my_package
source install/local_setup.bash
ros2 run my_package my_node
```

---

## Part 4: Writing Publishers and Subscribers

### 4.1 C++ Publisher and Subscriber

Create a new package called `cpp_pub_sub`:

```bash
cd ~/ros2_ws/src
ros2 pkg create --build-type ament_cmake cpp_pub_sub \
  --dependencies rclcpp std_msgs
```

**Publisher node** (`src/publisher_member_function.cpp`):

```cpp
#include <chrono>
#include <memory>
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"

using namespace std::chrono_literals;

class MinimalPublisher : public rclcpp::Node
{
public:
  MinimalPublisher() : Node("minimal_publisher"), count_(0)
  {
    publisher_ = this->create_publisher<std_msgs::msg::String>("topic", 10);
    timer_ = this->create_wall_timer(
      500ms, std::bind(&MinimalPublisher::timer_callback, this));
  }

private:
  void timer_callback()
  {
    auto message = std_msgs::msg::String();
    message.data = "Hello, world! " + std::to_string(count_++);
    RCLCPP_INFO(this->get_logger(), "Publishing: '%s'", message.data.c_str());
    publisher_->publish(message);
  }

  rclcpp::TimerBase::SharedPtr timer_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr publisher_;
  size_t count_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<MinimalPublisher>());
  rclcpp::shutdown();
  return 0;
}
```

**Subscriber node** (`src/subscriber_member_function.cpp`):

```cpp
#include <memory>
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"

class MinimalSubscriber : public rclcpp::Node
{
public:
  MinimalSubscriber() : Node("minimal_subscriber")
  {
    subscription_ = this->create_subscription<std_msgs::msg::String>(
      "topic", 10,
      std::bind(&MinimalSubscriber::topic_callback, this, std::placeholders::_1));
  }

private:
  void topic_callback(const std_msgs::msg::String & msg) const
  {
    RCLCPP_INFO(this->get_logger(), "I heard: '%s'", msg.data.c_str());
  }

  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr subscription_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<MinimalSubscriber>());
  rclcpp::shutdown();
  return 0;
}
```

**Update `CMakeLists.txt`** by adding these lines after `find_package(ament_cmake REQUIRED)`:

```cmake
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)

add_executable(talker src/publisher_member_function.cpp)
ament_target_dependencies(talker rclcpp std_msgs)

add_executable(listener src/subscriber_member_function.cpp)
ament_target_dependencies(listener rclcpp std_msgs)

install(TARGETS
  talker
  listener
  DESTINATION lib/${PROJECT_NAME})

ament_package()
```

Build and run:

```bash
cd ~/ros2_ws
colcon build --packages-select cpp_pub_sub
source install/local_setup.bash

# Terminal 1
ros2 run cpp_pub_sub talker

# Terminal 2
ros2 run cpp_pub_sub listener
```

---

### 4.2 Python Publisher and Subscriber

Create a Python package:

```bash
cd ~/ros2_ws/src
ros2 pkg create --build-type ament_python py_pub_sub \
  --dependencies rclpy std_msgs
```

**Publisher** (`py_pub_sub/publisher_member_function.py`):

```python
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class MinimalPublisher(Node):
    def __init__(self):
        super().__init__('minimal_publisher')
        self.publisher_ = self.create_publisher(String, 'topic', 10)
        self.timer = self.create_timer(0.5, self.timer_callback)
        self.i = 0

    def timer_callback(self):
        msg = String()
        msg.data = f'Hello World: {self.i}'
        self.publisher_.publish(msg)
        self.get_logger().info(f'Publishing: "{msg.data}"')
        self.i += 1

def main(args=None):
    rclpy.init(args=args)
    node = MinimalPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
```

**Subscriber** (`py_pub_sub/subscriber_member_function.py`):

```python
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class MinimalSubscriber(Node):
    def __init__(self):
        super().__init__('minimal_subscriber')
        self.subscription = self.create_subscription(
            String, 'topic', self.listener_callback, 10)

    def listener_callback(self, msg):
        self.get_logger().info(f'I heard: "{msg.data}"')

def main(args=None):
    rclpy.init(args=args)
    node = MinimalSubscriber()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
```

**Update `setup.py`** entry points:

```python
entry_points={
    'console_scripts': [
        'talker = py_pub_sub.publisher_member_function:main',
        'listener = py_pub_sub.subscriber_member_function:main',
    ],
},
```

Build and run:

```bash
cd ~/ros2_ws
colcon build --packages-select py_pub_sub
source install/local_setup.bash

# Terminal 1
ros2 run py_pub_sub talker

# Terminal 2
ros2 run py_pub_sub listener
```

---

## Part 5: Launch Files

A launch file lets you start many nodes at once from a single command. This saves you from typing multiple `ros2 run` commands across separate terminals.

Create a `launch` folder inside your package and add a file named `pub_sub.launch.py`:

```python
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    talker = Node(
        package='cpp_pub_sub',
        executable='talker',
        output='screen'
    )
    listener = Node(
        package='cpp_pub_sub',
        executable='listener',
        output='screen'
    )
    return LaunchDescription([talker, listener])
```

**Register the launch folder in `CMakeLists.txt`:**

```cmake
install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME})
```

Run the launch file:

```bash
ros2 launch cpp_pub_sub pub_sub.launch.py
```

**Passing parameters in a launch file:**

```python
Node(
    package='turtlesim',
    executable='turtlesim_node',
    parameters=[{'background_r': 255}],
    output='screen'
)
```

**Remapping topics in a launch file:**

```python
Node(
    package='my_package',
    executable='my_node',
    remappings=[('input_scan', '/scan_raw'), ('output_vel', '/nav_vel')],
    output='screen'
)
```

---

## Part 6: URDF Robot Description

### 6.1 What Is URDF?

URDF stands for Unified Robot Description Format. It is an XML file that describes a robot's links (rigid body parts) and joints (connections between parts). Every robot in ROS 2 has one.

**Basic URDF structure:**

```xml
<?xml version="1.0"?>
<robot name="my_robot">
  <link name="base_link">
    <visual>
      <geometry>
        <box size="0.5 0.5 0.5"/>
      </geometry>
      <material name="blue">
        <color rgba="0 0 1 1"/>
      </material>
    </visual>
    <collision>
      <geometry>
        <box size="0.5 0.5 0.5"/>
      </geometry>
    </collision>
    <inertial>
      <mass value="1.0"/>
      <inertia ixx="0.1" ixy="0" ixz="0" iyy="0.1" iyz="0" izz="0.1"/>
    </inertial>
  </link>
</robot>
```

---

### 6.2 Geometry Types

| Type | Syntax | Notes |
|------|--------|-------|
| Box | `<box size="x y z"/>` | Dimensions in meters |
| Sphere | `<sphere radius="r"/>` | Radius in meters |
| Cylinder | `<cylinder radius="r" length="l"/>` | Both in meters |
| Mesh | `<mesh filename="package://my_pkg/meshes/part.stl"/>` | STL or DAE file |

---

### 6.3 Origin (rpy and xyz)

The `origin` tag places and orients a geometry relative to a link's frame.

```xml
<origin xyz="0 0 0.5" rpy="0 0 1.5707"/>
```

- `xyz` is translation in meters (X, Y, Z).
- `rpy` is rotation in radians (roll about X, pitch about Y, yaw about Z).
- Rotation applies first, then translation.

---

### 6.4 Joints

A joint connects a parent link to a child link.

```xml
<joint name="base_to_arm" type="revolute">
  <parent link="base_link"/>
  <child link="arm_link"/>
  <origin xyz="0 0 0.5" rpy="0 0 0"/>
  <axis xyz="0 0 1"/>
  <limit lower="-1.57" upper="1.57" effort="10" velocity="1.0"/>
</joint>
```

**Joint types:**

| Type | Motion |
|------|--------|
| `fixed` | No motion |
| `revolute` | Rotation with limits |
| `continuous` | Rotation, no limits |
| `prismatic` | Linear translation with limits |
| `floating` | 6 DOF |
| `planar` | Motion in a plane |

---

### 6.5 Visualizing in RViz2

```bash
ros2 run rviz2 rviz2
```

Steps in RViz2:
1. Set the **Fixed Frame** to `base_link` in Global Options.
2. Click **Add**, choose **RobotModel**, set the description topic to `/robot_description`.
3. Click **Add**, choose **TF** to see all frames.

---

## Part 7: Xacro Files

Xacro lets you write URDF with macros, properties, and reusable components. This prevents repeated code.

**Declare a property:**

```xml
<xacro:property name="wheel_radius" value="0.05"/>
```

**Use a property:**

```xml
<cylinder radius="${wheel_radius}" length="0.04"/>
```

**Define a macro:**

```xml
<xacro:macro name="default_inertial" params="mass">
  <inertial>
    <mass value="${mass}"/>
    <inertia ixx="0.01" ixy="0" ixz="0" iyy="0.01" iyz="0" izz="0.01"/>
  </inertial>
</xacro:macro>
```

**Call the macro:**

```xml
<xacro:default_inertial mass="1.0"/>
```

**Include another xacro file:**

```xml
<xacro:include filename="$(find my_pkg)/urdf/robot_parts.xacro"/>
```

**Convert a xacro file to URDF from the terminal:**

```bash
xacro my_robot.urdf.xacro > my_robot.urdf
```

In a launch file, convert xacro at runtime:

```python
import xacro

xacro_file = os.path.join(pkg_share, 'urdf', 'my_robot.urdf.xacro')
robot_description = xacro.process_file(xacro_file).toxml()
```

---

## Part 8: Gazebo Simulation

### 8.1 Jazzy Uses Gazebo Harmonic — Not Gazebo Classic

**This is the biggest difference between the video (Humble) and Jazzy.** The video uses Gazebo Classic (`gazebo` command). Jazzy uses **Gazebo Harmonic** (`gz sim` command). The launch packages also changed.

Install Gazebo Harmonic and ROS integration:

```bash
sudo apt install ros-jazzy-ros-gz
sudo apt install ros-jazzy-gz-ros2-control
```

Gazebo Harmonic's main command is:

```bash
gz sim
```

The ROS-Gazebo bridge package is `ros_gz_bridge`. It connects ROS 2 topics to Gazebo topics.

---

### 8.2 Package Structure for a Gazebo Simulation

A typical simulation package has these folders:

```
my_robot_sim/
  config/       ← controller YAML files
  launch/       ← launch files
  meshes/       ← STL files
  urdf/         ← xacro and URDF files
  worlds/       ← SDF world files
  CMakeLists.txt
  package.xml
```

---

### 8.3 URDF Additions for Gazebo Harmonic

In Jazzy, the Gazebo plugin tags use the `gz` namespace instead of the old `gazebo` namespace. Add this section to your URDF/xacro file:

```xml
<gazebo>
  <plugin filename="gz_ros2_control-system"
          name="gz_ros2_control::GazeboSimROS2ControlPlugin">
    <parameters>$(find my_robot)/config/controllers.yaml</parameters>
  </plugin>
</gazebo>
```

For a ros2_control block, add joints like this:

```xml
<ros2_control name="GazeboSystem" type="system">
  <hardware>
    <plugin>gz_ros2_control/GazeboSimSystem</plugin>
  </hardware>
  <joint name="left_wheel_joint">
    <command_interface name="velocity"/>
    <state_interface name="position"/>
    <state_interface name="velocity"/>
  </joint>
  <joint name="right_wheel_joint">
    <command_interface name="velocity"/>
    <state_interface name="position"/>
    <state_interface name="velocity"/>
  </joint>
</ros2_control>
```

---

### 8.4 Launch File for Gazebo Harmonic

```python
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import xacro
import os

def generate_launch_description():
    pkg = get_package_share_directory('my_robot')

    # Parse the xacro file
    xacro_file = os.path.join(pkg, 'urdf', 'my_robot.urdf.xacro')
    robot_desc = xacro.process_file(xacro_file).toxml()

    # Robot state publisher
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_desc, 'use_sim_time': True}]
    )

    # Start Gazebo Harmonic
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('ros_gz_sim'),
                         'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={'gz_args': '-r empty.sdf'}.items()
    )

    # Spawn robot in Gazebo
    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-topic', 'robot_description', '-name', 'my_robot'],
        output='screen'
    )

    # Load controllers
    joint_state_broadcaster = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster']
    )

    diff_drive_controller = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['diff_drive_base_controller']
    )

    return LaunchDescription([
        gz_sim,
        robot_state_publisher,
        spawn_robot,
        joint_state_broadcaster,
        diff_drive_controller
    ])
```

---

### 8.5 Controller YAML File

Create `config/controllers.yaml`:

```yaml
controller_manager:
  ros__parameters:
    update_rate: 100

    joint_state_broadcaster:
      type: joint_state_broadcaster/JointStateBroadcaster

    diff_drive_base_controller:
      type: diff_drive_controller/DiffDriveController

diff_drive_base_controller:
  ros__parameters:
    left_wheel_names: ["left_wheel_joint"]
    right_wheel_names: ["right_wheel_joint"]
    wheel_separation: 0.35
    wheel_radius: 0.05
    base_frame_id: base_link
    odom_frame_id: odom
    use_stamped_vel: false
```

---

### 8.6 ROS 2 Controller Types

| Controller | Message Type | Use Case |
|---|---|---|
| `diff_drive_controller` | `geometry_msgs/Twist` | Wheeled mobile robots |
| `joint_trajectory_controller` | `trajectory_msgs/JointTrajectory` | Arms and multi-joint robots |
| `joint_state_broadcaster` | `sensor_msgs/JointState` | Reading joint states |

**Command your robot from the terminal:**

```bash
ros2 topic pub /diff_drive_base_controller/cmd_vel \
  geometry_msgs/msg/Twist \
  "{linear: {x: 0.2}, angular: {z: 0.5}}"
```

---

## Part 9: Camera Sensor in Gazebo

### 9.1 Add a Camera to Your URDF

Add a camera link and joint to your xacro file:

```xml
<link name="camera_link">
  <visual>
    <geometry><box size="0.05 0.05 0.05"/></geometry>
  </visual>
</link>

<joint name="head_to_camera" type="fixed">
  <parent link="head"/>
  <child link="camera_link"/>
  <origin xyz="0.1 0 0" rpy="0 0 0"/>
</joint>
```

Add the Gazebo camera plugin (Harmonic syntax):

```xml
<gazebo reference="camera_link">
  <sensor name="camera" type="camera">
    <camera>
      <horizontal_fov>1.047</horizontal_fov>
      <image>
        <width>640</width>
        <height>480</height>
        <format>R8G8B8</format>
      </image>
      <clip>
        <near>0.1</near>
        <far>100</far>
      </clip>
    </camera>
    <always_on>1</always_on>
    <update_rate>30</update_rate>
    <visualize>true</visualize>
    <topic>camera/image_raw</topic>
    <gz_frame_id>camera_link</gz_frame_id>
  </sensor>
</gazebo>
```

### 9.2 Bridge Camera Topic to ROS 2

In Gazebo Harmonic, you need to bridge the topic from Gazebo to ROS 2. Add this to your launch file:

```python
bridge = Node(
    package='ros_gz_bridge',
    executable='parameter_bridge',
    arguments=[
        '/camera/image_raw@sensor_msgs/msg/Image@gz.msgs.Image'
    ],
    output='screen'
)
```

### 9.3 View Camera in RViz2

1. Run RViz2: `ros2 run rviz2 rviz2`
2. Click **Add**, choose **Image**.
3. Set the topic to `/camera/image_raw`.

---

## Part 10: LiDAR Sensor in Gazebo

### 10.1 Add LiDAR to Your URDF

```xml
<link name="lidar_link"/>

<joint name="base_to_lidar" type="fixed">
  <parent link="base_link"/>
  <child link="lidar_link"/>
  <origin xyz="0 0 0.2" rpy="0 0 0"/>
</joint>

<gazebo reference="lidar_link">
  <sensor name="lidar" type="gpu_lidar">
    <topic>lidar_out</topic>
    <update_rate>10</update_rate>
    <lidar>
      <scan>
        <horizontal>
          <samples>720</samples>
          <resolution>1</resolution>
          <min_angle>-3.14159</min_angle>
          <max_angle>3.14159</max_angle>
        </horizontal>
      </scan>
      <range>
        <min>0.1</min>
        <max>30.0</max>
        <resolution>0.01</resolution>
      </range>
    </lidar>
    <always_on>1</always_on>
    <visualize>true</visualize>
    <gz_frame_id>lidar_link</gz_frame_id>
  </sensor>
</gazebo>
```

### 10.2 Bridge LiDAR to ROS 2

```python
lidar_bridge = Node(
    package='ros_gz_bridge',
    executable='parameter_bridge',
    arguments=[
        '/lidar_out@sensor_msgs/msg/LaserScan@gz.msgs.LaserScan'
    ],
    output='screen'
)
```

### 10.3 View LiDAR in RViz2

1. Click **Add**, choose **LaserScan** by topic.
2. Set the topic to `/lidar_out`.
3. Change the Fixed Frame to `lidar_link` or `base_link`.

---

## Part 11: Depth Camera in Gazebo

### 11.1 Add a Depth Camera to Your URDF

```xml
<gazebo reference="camera_link">
  <sensor name="depth_camera" type="depth_camera">
    <camera>
      <horizontal_fov>1.047</horizontal_fov>
      <image>
        <width>640</width>
        <height>480</height>
      </image>
      <clip>
        <near>0.1</near>
        <far>10.0</far>
      </clip>
    </camera>
    <always_on>1</always_on>
    <update_rate>30</update_rate>
    <topic>depth_camera</topic>
    <gz_frame_id>camera_optical_frame</gz_frame_id>
  </sensor>
</gazebo>
```

### 11.2 Camera Frame Orientation

The camera frame follows an optical convention. Z points forward (into the scene), X points right, and Y points down. You must apply two rotations to convert from the robot's standard frame:

1. Rotate -90° about X.
2. Rotate -90° about Z.

Create a separate `camera_optical_frame` link with this transform applied.

### 11.3 Bridge Depth Topics to ROS 2

```python
depth_bridge = Node(
    package='ros_gz_bridge',
    executable='parameter_bridge',
    arguments=[
        '/depth_camera/depth_image@sensor_msgs/msg/Image@gz.msgs.Image',
        '/depth_camera/points@sensor_msgs/msg/PointCloud2@gz.msgs.PointCloudPacked'
    ],
    output='screen'
)
```

### 11.4 View in RViz2

Add a **DepthCloud** or **PointCloud2** display and set the topic to `/depth_camera/points`.

---

## Part 12: Mobile Robot Simulation (Differential Drive)

### 12.1 Key Dimensions You Need

| Dimension | What it affects |
|---|---|
| Wheel radius | `wheel_radius` in YAML |
| Wheel separation | `wheel_separation` in YAML |
| Base frame | `base_frame_id` in YAML |

### 12.2 Controlling the Robot

**Send a velocity command:**

```bash
ros2 topic pub /diff_drive_base_controller/cmd_vel \
  geometry_msgs/msg/Twist \
  "{linear: {x: 0.1}, angular: {z: 0.1}}"
```

For keyboard teleop, install and run:

```bash
sudo apt install ros-jazzy-teleop-twist-keyboard
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args -r cmd_vel:=/diff_drive_base_controller/cmd_vel
```

### 12.3 Plot Juggler for Data Visualization

Install:

```bash
sudo apt install ros-jazzy-plotjuggler-ros
```

Run:

```bash
ros2 run plotjuggler plotjuggler
```

Under **Streaming**, choose **ROS 2 Topic Subscriber**, then start. Select your topic (like `/diff_drive_base_controller/odom`) and drag signals onto the plot canvas.

Save a layout by clicking the save icon. Load it later with the load icon.

---

## Part 13: SLAM Toolbox

### 13.1 What Is SLAM?

SLAM stands for Simultaneous Localization and Mapping. The robot builds a map of its environment while tracking its own position in that map at the same time.

Three key frames in ROS 2 SLAM:

| Frame | Description |
|---|---|
| `map` | Fixed origin of the built map |
| `odom` | Robot's starting position (drifts over time) |
| `base_link` | Current robot position |

SLAM corrects the drift in `odom` using the LiDAR and odometry together.

### 13.2 Install SLAM Toolbox

```bash
sudo apt install ros-jazzy-slam-toolbox
```

### 13.3 Configure SLAM Parameters

Copy the default parameter file and edit it:

```bash
cp /opt/ros/jazzy/share/slam_toolbox/config/mapper_params_online_async.yaml \
   ~/ros2_ws/src/my_robot/config/
```

Edit the key parameters:

```yaml
odom_frame: odom
map_frame: map
base_frame: base_link
scan_topic: /lidar_out
mode: mapping
```

### 13.4 Run SLAM Toolbox

```bash
ros2 launch slam_toolbox online_async_launch.py \
  slam_params_file:=/path/to/mapper_params_online_async.yaml \
  use_sim_time:=true
```

Or add it to your launch file:

```python
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
import os

slam_toolbox_dir = get_package_share_directory('slam_toolbox')
slam_launch = IncludeLaunchDescription(
    PythonLaunchDescriptionSource(
        os.path.join(slam_toolbox_dir, 'launch', 'online_async_launch.py')
    ),
    launch_arguments={
        'slam_params_file': '/path/to/config/mapper_params_online_async.yaml',
        'use_sim_time': 'true'
    }.items()
)
```

### 13.5 RViz2 Settings for SLAM

1. Set Fixed Frame to `map`.
2. Add **Map** display, set topic to `/map`.
3. Add **LaserScan**, set topic to `/lidar_out`.
4. Add **RobotModel**, set topic to `/robot_description`.
5. Add **TF** to see all frames.

### 13.6 Drive the Robot to Build the Map

Use teleop to drive the robot around your environment:

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args -r cmd_vel:=/diff_drive_base_controller/cmd_vel
```

Watch the map grow in RViz2 as you move.

### 13.7 Save the Map

In RViz2, go to **Panels**, add the **SlamToolboxPlugin** panel. Type a map name and click **Save Map** and **Serialize Map**.

This creates four files: `.pgm`, `.yaml`, `.data`, and `.posegraph`.

### 13.8 Load a Saved Map

Update `mapper_params_online_async.yaml`:

```yaml
map_file_name: /full/path/to/map
map_start_at_dock: true
mode: localization
```

Rebuild and relaunch. The map loads automatically.

---

## Part 14: Nav2 Navigation

### 14.1 Install Nav2

```bash
sudo apt install ros-jazzy-navigation2 ros-jazzy-nav2-bringup
```

### 14.2 Remap Command Velocity for Nav2

Nav2 publishes to `/cmd_vel` by default. Your robot may use a different topic like `/diff_drive_base_controller/cmd_vel`. Add a remap in the navigation launch file:

```python
remappings=[('/cmd_vel', '/diff_drive_base_controller/cmd_vel')]
```

See the official Nav2 Jazzy documentation for full remap instructions: `https://docs.nav2.org`

### 14.3 Start Nav2

Run your robot simulation first, then:

```bash
ros2 launch nav2_bringup navigation_launch.py \
  use_sim_time:=true \
  map:=/path/to/map.yaml
```

### 14.4 RViz2 Settings for Nav2

1. Add **Map** display, topic `/map`, QoS: Reliable, Transient Local.
2. Add **Map** for local costmap: topic `/local_costmap/costmap`.
3. Add **Map** for global costmap: topic `/global_costmap/costmap`.
4. Add **LaserScan**, topic `/lidar_out`.
5. Add **RobotModel**.

### 14.5 Send Navigation Goals

1. Click the **2D Goal Pose** button in RViz2.
2. Click on the map where you want the robot to go.
3. Drag the arrow to set the goal orientation.
4. Release the mouse to send the goal.

Nav2 plans a path and commands the robot to follow it.

**Send a goal from the terminal:**

```bash
ros2 action send_goal /navigate_to_pose \
  nav2_msgs/action/NavigateToPose \
  "{pose: {header: {frame_id: 'map'}, pose: {position: {x: 1.0, y: 0.5, z: 0.0}, orientation: {w: 1.0}}}}"
```

---

## Quick Reference: Humble vs. Jazzy Differences

| Topic | Humble (Video) | Jazzy (This Guide) |
|---|---|---|
| Ubuntu version | 22.04 | 24.04 |
| Installation | `ros-humble-desktop` | `ros-jazzy-desktop` |
| Source command | `/opt/ros/humble/setup.bash` | `/opt/ros/jazzy/setup.bash` |
| Gazebo | Gazebo Classic (`gazebo`) | Gazebo Harmonic (`gz sim`) |
| Gazebo ROS pkg | `gazebo_ros` | `ros_gz_bridge`, `ros_gz_sim` |
| Gazebo plugin tag | `<gazebo><plugin filename="libgazebo_ros_...">` | `<gazebo><sensor type="..." ...>` or gz plugin |
| Topic bridge | Built-in Gazebo Classic | Needs `ros_gz_bridge` |
| Nav2 install | `ros-humble-navigation2` | `ros-jazzy-navigation2` |
| SLAM Toolbox | `ros-humble-slam-toolbox` | `ros-jazzy-slam-toolbox` |
| Python version | Python 3.10 | Python 3.12 |

---

## Quick Reference: Common Commands

```bash
# List packages
ros2 pkg list

# Run a node
ros2 run <pkg> <executable>

# List nodes
ros2 node list

# Node info
ros2 node info /<node_name>

# List topics
ros2 topic list -t

# Echo a topic
ros2 topic echo /<topic>

# Topic frequency
ros2 topic hz /<topic>

# List services
ros2 service list

# Call a service
ros2 service call /<service> <type> "<args>"

# List parameters
ros2 param list

# Get a parameter
ros2 param get /<node> <param>

# Set a parameter
ros2 param set /<node> <param> <value>

# List actions
ros2 action list

# Build workspace
cd ~/ros2_ws && colcon build --symlink-install

# Build one package
colcon build --symlink-install --packages-select <pkg>

# Source workspace
source install/local_setup.bash

# Run a launch file
ros2 launch <pkg> <file>.launch.py

# Remap at runtime
ros2 run <pkg> <exec> --ros-args -r old_topic:=new_topic

# Pass a parameter at runtime
ros2 run <pkg> <exec> --ros-args -p param_name:=value
```

---

## Recommended Learning Order

1. Finish the full video while reading the matching sections here.
2. Practice every command yourself in a live terminal.
3. Build the TurtleSim examples before moving to custom nodes.
4. Write your own publisher and subscriber from scratch without copying.
5. Create a simple URDF with one box and visualize it in RViz2.
6. Set up a robot in Gazebo Harmonic with a diff drive controller.
7. Add a LiDAR, run SLAM, and save a map.
8. Use Nav2 to send a goal to your mapped environment.

---

*All commands in this guide target ROS 2 Jazzy Jalisco on Ubuntu 24.04. For the latest documentation, visit `https://docs.ros.org/en/jazzy`.*
