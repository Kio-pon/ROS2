# 🐳 Dockerized PX4 + ROS 2 Jazzy Drone Simulator

This setup provides a fully containerized development environment for the drone simulator. It includes **ROS 2 Jazzy**, **PX4 SITL (v1.15.4)**, **Gazebo Harmonic**, and the **Micro-XRCE-DDS Agent**. 

To make running graphical tools (like Gazebo and the Mission Control Tkinter GUI) seamless across different operating systems, this image boots a virtual desktop (Xvfb + Openbox) and shares it over **noVNC** (HTML5 VNC client) to your host web browser.

---

## 🚀 Quick Start

### 1. Build the Docker Image
From the root of the repository, build the image (it might take some time on the first run as it compiles PX4 and DDS Agent):
```bash
docker compose build
```

### 2. Start the Simulator Container
Launch the container in the background:
```bash
docker compose up -d
```

### 3. Access the Virtual Desktop
Open your web browser and navigate to:
👉 **[http://localhost:6080/vnc.html](http://localhost:6080/vnc.html)**

Click **Connect** (no password is required). You will see a clean Linux desktop environment.

### 4. Run the Drone Simulation
Inside the web browser virtual desktop:
1. **Right-click** on the desktop background and select **Terminal** (or open an xterm window).
2. Inside the terminal, execute the launcher script:
   ```bash
   cd ~/launchers && ./run_all.sh
   ```
3. Watch the Gazebo simulator start, and control the drone using the Mission Control GUI!

---

## 🛠️ Developer Workflow

The `docker-compose.yml` mounts your local `drone_controller` folder directly into the container's active workspace (`/home/student/px4_ros2_ws/src/drone_controller`).

This enables **live edits**:
1. Edit the Python code using your IDE on the Windows host.
2. The changes are immediately updated inside the container.
3. If you make changes to nodes, message definitions, or package configurations, compile them inside the container's terminal:
   ```bash
   cd ~/px4_ros2_ws && colcon build --symlink-install
   ```

---

## 🧩 Future-Proofing & Extensibility

This container is designed to be highly modular and extensible. You can add new 3D models, custom worlds, or swap to different drone airframes without rebuilding the Docker image.

### 1. Swapping Drone Airframes
To change the active drone model, open [docker-compose.yml](file:///c:/Users/Student/ROS/docker-compose.yml) and edit the environment variables under the `drone-sim` service:

* **Standard Quadcopter (x500)**:
  ```yaml
  - PX4_SYS_AUTOSTART=4001
  - PX4_SIM_MODEL=gz_x500
  ```
* **Quadcopter with Monocular Camera (Default)**:
  ```yaml
  - PX4_SYS_AUTOSTART=4010
  - PX4_SIM_MODEL=gz_x500_mono_cam
  ```
* **Quadcopter with Depth Camera**:
  ```yaml
  - PX4_SYS_AUTOSTART=4011
  - PX4_SIM_MODEL=gz_x500_depth
  ```
* **Standard VTOL**:
  ```yaml
  - PX4_SYS_AUTOSTART=4003
  - PX4_SIM_MODEL=gz_standard_vtol
  ```

### 2. Adding Custom 3D Models
The local directory `./custom_models` is mounted to `/home/student/custom_models` in the container.
- Drop your custom Gazebo SDF model folders here.
- The path `/home/student/custom_models` is automatically added to the `GZ_SIM_RESOURCE_PATH` environment variable in the container, meaning Gazebo can find and load them instantly.

### 3. Adding Custom Worlds
The local directory `./custom_worlds` is mounted to `/home/student/custom_worlds` in the container.
- Place your `.sdf` world files here.
- Update `PX4_GZ_WORLD` in [docker-compose.yml](file:///c:/Users/Student/ROS/docker-compose.yml) to the name of your custom world file (without the `.sdf` extension) to load it.

### 4. Custom PX4 Airframes
The local directory `./custom_airframes` is mounted to `/home/student/custom_airframes`.
- If you design a custom PX4 airframe init script, place it here to make it accessible to PX4.

---

## 🛑 Stopping the Simulation

To stop the running container and release resources on your host machine, run:
```bash
docker compose down
```
