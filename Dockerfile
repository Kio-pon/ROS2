# syntax=docker/dockerfile:1.7
# =============================================================================
#  PX4 SITL + ROS 2 Jazzy + Gazebo Harmonic  —  Native-GUI Simulation Image
# =============================================================================
#  Renders to the HOST's display (X11) with real GPU acceleration — no VNC,
#  no browser. This is the pattern robotics teams ship to the field.
#
#  Layer order is chosen so the expensive, rarely-changing steps cache and
#  only your own code (the last layer) rebuilds on a normal edit:
#     1. System + GUI/GL deps        (almost never change)
#     2. ROS 2 Jazzy + ros_gz        (almost never change)
#     3. Non-root user               (almost never change)
#     4. PX4-Autopilot SITL          (pinned commit — changes rarely)
#     5. Micro-XRCE-DDS Agent        (changes rarely)
#     6. px4_msgs workspace          (pinned commit — changes rarely)
#     7. drone_controller (your code) (changes often — rebuild is seconds)
#
#  Versions are PINNED to the exact commits the project was developed against
#  so the container's uORB topic set (…_v1 / …_v4) matches your ROS 2 nodes.
#  Override at build time, e.g.:  --build-arg PX4_REF=main
# =============================================================================

FROM ubuntu:24.04 AS base

# ── Build arguments ──────────────────────────────────────────────────────
ARG PX4_REF=183b3e38d5
ARG PX4MSGS_REF=64775a2
ARG JOBS=4
ARG USERNAME=student
ARG USER_UID=1000
ARG USER_GID=1000

# ── Environment ──────────────────────────────────────────────────────────
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring \
    # Hint the NVIDIA Container Toolkit to expose the GPU + GL/EGL libs at
    # runtime (harmless on non-NVIDIA hosts / when the toolkit is absent).
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=all \
    # Default drone/world — override per-run from docker-compose or `-e`
    PX4_SYS_AUTOSTART=4010 \
    PX4_SIM_MODEL=gz_x500_mono_cam \
    PX4_GZ_WORLD=lawn

# =============================================================================
# LAYER 1 — Core system, GUI toolkits, and OpenGL/EGL client libraries
# =============================================================================
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        locales curl gnupg2 lsb-release sudo ca-certificates git \
        build-essential cmake wget tzdata software-properties-common \
        python3-pip python3-dev python3-tk python3-pil python3-pil.imagetk \
        dbus-x11 \
        # --- OpenGL / EGL stack (Ubuntu 24.04 package names) ---------------
        mesa-utils libgl1-mesa-dri libglx-mesa0 libegl-mesa0 libglu1-mesa \
        libgl1 libglvnd0 libglx0 libegl1 \
        # --- X11 client libs needed by Tk / Qt (Gazebo GUI, rviz) ----------
        libxext6 libxrender1 libxi6 libxtst6 libxrandr2 libxfixes3 \
        libxkbcommon-x11-0 libsm6 libice6 \
    && locale-gen en_US en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

# =============================================================================
# LAYER 2 — ROS 2 Jazzy desktop + Gazebo bridge packages
# =============================================================================
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
        -o /usr/share/keyrings/ros-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
        > /etc/apt/sources.list.d/ros2.list

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        ros-jazzy-desktop \
        python3-colcon-common-extensions python3-vcstool python3-rosdep \
        ros-jazzy-ament-cmake ros-jazzy-joy \
        ros-jazzy-ros-gz-image ros-jazzy-ros-gz-bridge ros-jazzy-ros-gz-sim \
    && rosdep init

# =============================================================================
# LAYER 3 — Non-root user (UID/GID match the host so X11 + mounted files work)
#   Ubuntu 24.04 ships a default UID 1000 'ubuntu' user; remove it so we can
#   take that UID for our own developer account.
# =============================================================================
RUN userdel -r ubuntu 2>/dev/null || true; \
    groupadd -f render; \
    groupadd --gid ${USER_GID} ${USERNAME} 2>/dev/null || true; \
    useradd -m -s /bin/bash -u ${USER_UID} -g ${USER_GID} ${USERNAME}; \
    usermod -aG sudo,video,render ${USERNAME}; \
    echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/99-${USERNAME} && \
    chmod 0440 /etc/sudoers.d/99-${USERNAME}

USER ${USERNAME}
ENV HOME=/home/${USERNAME}
WORKDIR ${HOME}
RUN rosdep update

# =============================================================================
# LAYER 4 — PX4-Autopilot SITL (pinned commit -> matches host topic versions)
# =============================================================================
RUN git clone --recursive https://github.com/PX4/PX4-Autopilot.git && \
    cd PX4-Autopilot && \
    git checkout ${PX4_REF} && \
    git submodule update --init --recursive && \
    sudo -E bash Tools/setup/ubuntu.sh --no-nuttx && \
    DONT_RUN=1 make -j${JOBS} px4_sitl && \
    rm -rf build/px4_sitl_default/tmp

# =============================================================================
# LAYER 5 — Micro-XRCE-DDS Agent (PX4 <-> ROS 2 transport)
# =============================================================================
RUN git clone --depth 1 https://github.com/eProsima/Micro-XRCE-DDS-Agent.git && \
    cd Micro-XRCE-DDS-Agent && mkdir build && cd build && \
    cmake .. && make -j${JOBS} && \
    sudo make install && sudo ldconfig /usr/local/lib/ && \
    cd ${HOME} && rm -rf Micro-XRCE-DDS-Agent/build

# =============================================================================
# LAYER 6 — ROS 2 workspace with px4_msgs (pinned commit)
# =============================================================================
RUN mkdir -p ${HOME}/px4_ros2_ws/src && \
    cd ${HOME}/px4_ros2_ws/src && \
    git clone https://github.com/PX4/px4_msgs.git && \
    cd px4_msgs && git checkout ${PX4MSGS_REF} && \
    cd ${HOME}/px4_ros2_ws && \
    bash -c "source /opt/ros/jazzy/setup.bash && colcon build --symlink-install"

# =============================================================================
# Extensibility mount points — drop in custom models / worlds / airframes /
# missions at runtime (see docker-compose.yml volumes + README_DOCKER.md).
# =============================================================================
RUN mkdir -p ${HOME}/custom_models ${HOME}/custom_worlds \
             ${HOME}/custom_airframes ${HOME}/missions ${HOME}/launchers

# =============================================================================
# Shell environment: source ROS + workspace, and expose custom Gazebo paths
# =============================================================================
RUN { \
      echo 'source /opt/ros/jazzy/setup.bash'; \
      echo 'source ~/px4_ros2_ws/install/setup.bash 2>/dev/null || true'; \
      echo 'export GZ_SIM_RESOURCE_PATH="${HOME}/custom_models:${HOME}/custom_worlds:${GZ_SIM_RESOURCE_PATH:-}"'; \
      echo 'export GZ_CONFIG_PATH="/usr/share/gz:${GZ_CONFIG_PATH:-}"'; \
    } >> ~/.bashrc

# =============================================================================
# LAYER 7 — Your code (drone_controller + first). Rebuilds fast; deps cached.
#   Note: docker-compose bind-mounts ./drone_controller over this at runtime
#   for live editing, so a host edit + `colcon build` is enough day to day.
# =============================================================================
COPY --chown=${USER_UID}:${USER_GID} drone_controller/ ${HOME}/px4_ros2_ws/src/drone_controller/
COPY --chown=${USER_UID}:${USER_GID} first/            ${HOME}/px4_ros2_ws/src/first/

RUN cd ${HOME}/px4_ros2_ws && \
    bash -c "source /opt/ros/jazzy/setup.bash && source install/setup.bash && \
             colcon build --symlink-install --packages-select drone_controller first"

# Launcher scripts + entrypoint (strip any CRLF from Windows-edited files)
COPY --chown=${USER_UID}:${USER_GID} run_*.sh      ${HOME}/launchers/
COPY --chown=${USER_UID}:${USER_GID} entrypoint.sh ${HOME}/entrypoint.sh
RUN sed -i 's/\r$//' ${HOME}/entrypoint.sh ${HOME}/launchers/*.sh && \
    chmod +x         ${HOME}/entrypoint.sh ${HOME}/launchers/*.sh

WORKDIR ${HOME}
ENTRYPOINT ["/home/student/entrypoint.sh"]
CMD ["bash"]
