#!/usr/bin/env bash
# =============================================================================
#  Container entrypoint — NATIVE display.
#  No virtual desktop, no VNC: graphical apps (Gazebo, the Tkinter Mission
#  Control GUI, rviz) open as real windows on the HOST's screen via the X11
#  socket bind-mounted from the host. GPU acceleration is provided by the
#  host driver (NVIDIA Container Toolkit, or /dev/dri for Intel/AMD).
#
#  It sources the ROS 2 environment, wires up Gazebo's custom-asset search
#  paths, prints a short readiness report, then execs the requested command
#  (defaults to an interactive shell).
# =============================================================================
set -e

# 1. ROS 2 + workspace
source /opt/ros/jazzy/setup.bash
if [ -f "${HOME}/px4_ros2_ws/install/setup.bash" ]; then
    source "${HOME}/px4_ros2_ws/install/setup.bash"
fi

# 2. Gazebo asset search paths — anything dropped into the mounted
#    custom_models / custom_worlds folders is discoverable by Gazebo.
export GZ_SIM_RESOURCE_PATH="${HOME}/custom_models:${HOME}/custom_worlds:${GZ_SIM_RESOURCE_PATH:-}"
export GZ_CONFIG_PATH="/usr/share/gz:${GZ_CONFIG_PATH:-}"

# 3. Display / GPU readiness report (informational, never fatal)
echo "================================================================"
echo "  PX4 + ROS 2 Jazzy + Gazebo Harmonic  (native display)"
if [ -n "${HEADLESS}" ]; then
    echo "  Mode      : HEADLESS (no GUI windows; ideal for automated tests)"
elif [ -n "${DISPLAY}" ] && [ -S "/tmp/.X11-unix/X${DISPLAY##*:}" ]; then
    echo "  Display   : ${DISPLAY}  (X11 socket detected — GUI windows will open on your screen)"
else
    echo "  Display   : ${DISPLAY:-<unset>}  (no X11 socket — run 'xhost +local:' on the host,"
    echo "              mount /tmp/.X11-unix, or set HEADLESS=1)"
fi
if command -v nvidia-smi >/dev/null 2>&1; then
    echo "  GPU       : NVIDIA ($(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1))"
elif [ -e /dev/dri/renderD128 ]; then
    echo "  GPU       : /dev/dri present (Intel/AMD or software rendering)"
else
    echo "  GPU       : none detected — Gazebo will use slow software (llvmpipe) rendering"
fi
echo "  Launchers : ~/launchers   (e.g.  ~/launchers/run_all.sh)"
echo "================================================================"

# 4. Run the requested command (default: interactive shell)
exec "$@"
