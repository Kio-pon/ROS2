# syntax=docker/dockerfile:1.6
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  PX4 + ROS 2 Jazzy + Gazebo Harmonic  —  Drone Simulation Image   ║
# ║                                                                    ║
# ║  Optimised for Docker layer caching:                               ║
# ║    ① System deps      (changes: almost never)                      ║
# ║    ② ROS 2 Jazzy      (changes: almost never)                      ║
# ║    ③ VNC desktop       (changes: almost never)                      ║
# ║    ④ PX4 Autopilot    (changes: rarely)                            ║
# ║    ⑤ DDS Agent        (changes: rarely)                            ║
# ║    ⑥ ROS 2 workspace  (changes: sometimes)                        ║
# ║    ⑦ User code        (changes: often  ← rebuild is instant)      ║
# ╚══════════════════════════════════════════════════════════════════════╝

FROM ubuntu:24.04 AS base

# ── Global build args ───────────────────────────────────────────────────
ARG PX4_VERSION=v1.15.4
ARG JOBS=2

# ── Environment ─────────────────────────────────────────────────────────
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring \
    DISPLAY=:1 \
    # Default drone config — override at runtime via docker-compose or -e
    PX4_SYS_AUTOSTART=4010 \
    PX4_SIM_MODEL=gz_x500_mono_cam \
    PX4_GZ_WORLD=lawn \
    GZ_SIM_RESOURCE_PATH="" \
    SCREEN_RES=1920x1080x24

# ════════════════════════════════════════════════════════════════════════
# LAYER 1 — Core system packages & locales
# ════════════════════════════════════════════════════════════════════════
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        locales curl gnupg2 lsb-release sudo ca-certificates \
        git build-essential cmake python3-pip python3-dev \
        python3-tk python3-pil python3-pil.imagetk \
        dbus-x11 wget tzdata software-properties-common \
    && locale-gen en_US en_US.UTF-8 \
    && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

# ════════════════════════════════════════════════════════════════════════
# LAYER 2 — ROS 2 Jazzy Desktop + Gazebo Harmonic packages
# ════════════════════════════════════════════════════════════════════════
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
        -o /usr/share/keyrings/ros-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) \
    signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
    http://packages.ros.org/ros2/ubuntu \
    $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
    > /etc/apt/sources.list.d/ros2.list

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        ros-jazzy-desktop \
        python3-colcon-common-extensions \
        python3-vcstool \
        python3-rosdep \
        ros-jazzy-ament-cmake \
        ros-jazzy-joy \
        ros-jazzy-ros-gz-image \
        ros-jazzy-ros-gz-bridge \
        ros-jazzy-ros-gz-sim

# Initialize rosdep (root)
RUN if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then \
        rosdep init; fi

# ════════════════════════════════════════════════════════════════════════
# LAYER 3 — VNC / noVNC virtual desktop
# ════════════════════════════════════════════════════════════════════════
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        xvfb x11vnc novnc websockify \
        openbox xterm x11-xserver-utils \
        mesa-utils libgl1-mesa-dri libgl1-mesa-glx libegl1-mesa

# ════════════════════════════════════════════════════════════════════════
# Create non-root user with passwordless sudo
# ════════════════════════════════════════════════════════════════════════
RUN useradd -m -s /bin/bash -G sudo student \
    && echo "student ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER student
ENV HOME=/home/student
WORKDIR ${HOME}

# rosdep update for the user
RUN rosdep update

# ════════════════════════════════════════════════════════════════════════
# LAYER 4 — PX4 Autopilot SITL
#   Pinned to a release tag for reproducibility. Override with:
#     docker build --build-arg PX4_VERSION=main .
# ════════════════════════════════════════════════════════════════════════
RUN git clone --depth 1 --branch ${PX4_VERSION} --recursive \
        https://github.com/PX4/PX4-Autopilot.git && \
    cd PX4-Autopilot && \
    sudo -E bash Tools/setup/ubuntu.sh --no-nuttx && \
    DONT_RUN=1 make -j${JOBS} px4_sitl && \
    # Trim build artifacts that are not needed at runtime
    rm -rf build/px4_sitl_default/tmp build/px4_sitl_default/external

# ════════════════════════════════════════════════════════════════════════
# LAYER 5 — Micro-XRCE-DDS Agent
# ════════════════════════════════════════════════════════════════════════
RUN git clone --depth 1 https://github.com/eProsima/Micro-XRCE-DDS-Agent.git && \
    cd Micro-XRCE-DDS-Agent && mkdir build && cd build && \
    cmake .. && make -j${JOBS} && \
    sudo make install && sudo ldconfig /usr/local/lib/ && \
    # Clean build dir to save ~100 MB
    cd ${HOME} && rm -rf Micro-XRCE-DDS-Agent/build

# ════════════════════════════════════════════════════════════════════════
# LAYER 6 — ROS 2 workspace (px4_msgs only — stable layer)
# ════════════════════════════════════════════════════════════════════════
RUN mkdir -p ${HOME}/px4_ros2_ws/src && \
    cd ${HOME}/px4_ros2_ws/src && \
    git clone --depth 1 https://github.com/PX4/px4_msgs.git && \
    cd ${HOME}/px4_ros2_ws && \
    bash -c "source /opt/ros/jazzy/setup.bash && colcon build --symlink-install"

# ════════════════════════════════════════════════════════════════════════
# LAYER 7 — User packages (drone_controller + any future packages)
#   This layer rebuilds every time you change your code — but it is
#   cheap because all heavy dependencies are cached in layers above.
# ════════════════════════════════════════════════════════════════════════
COPY --chown=student:student drone_controller/ \
    ${HOME}/px4_ros2_ws/src/drone_controller/
COPY --chown=student:student first/ \
    ${HOME}/px4_ros2_ws/src/first/

RUN cd ${HOME}/px4_ros2_ws && \
    bash -c "source /opt/ros/jazzy/setup.bash && \
             source install/setup.bash && \
             colcon build --symlink-install --packages-select drone_controller first"

# ════════════════════════════════════════════════════════════════════════
# Extensibility mount points
#   Mount custom Gazebo models, worlds, or PX4 airframes at runtime.
#   Example:  -v ./my_models:/home/student/custom_models
# ════════════════════════════════════════════════════════════════════════
RUN mkdir -p ${HOME}/custom_models \
             ${HOME}/custom_worlds \
             ${HOME}/custom_airframes \
             ${HOME}/missions

# ════════════════════════════════════════════════════════════════════════
# Shell & environment setup
# ════════════════════════════════════════════════════════════════════════
RUN echo 'source /opt/ros/jazzy/setup.bash'                          >> ~/.bashrc && \
    echo 'source ~/px4_ros2_ws/install/setup.bash 2>/dev/null'       >> ~/.bashrc && \
    echo '# Custom Gazebo resource paths (for your 3D models)'       >> ~/.bashrc && \
    echo 'export GZ_SIM_RESOURCE_PATH="${HOME}/custom_models:${HOME}/custom_worlds:${GZ_SIM_RESOURCE_PATH}"' >> ~/.bashrc && \
    echo 'export GZ_CONFIG_PATH="/usr/share/gz:${GZ_CONFIG_PATH:-}"' >> ~/.bashrc

# ════════════════════════════════════════════════════════════════════════
# Copy launcher scripts & entrypoint
# ════════════════════════════════════════════════════════════════════════
COPY --chown=student:student run_*.sh      ${HOME}/launchers/
COPY --chown=student:student entrypoint.sh ${HOME}/entrypoint.sh
RUN sed -i 's/\r$//' ${HOME}/entrypoint.sh ${HOME}/launchers/*.sh && \
    chmod +x          ${HOME}/entrypoint.sh ${HOME}/launchers/*.sh

# ════════════════════════════════════════════════════════════════════════
# Ports & health check
# ════════════════════════════════════════════════════════════════════════
EXPOSE 6080 5900
HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -sf http://localhost:6080/vnc.html || exit 1

WORKDIR ${HOME}
ENTRYPOINT ["/home/student/entrypoint.sh"]
