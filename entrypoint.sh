#!/bin/bash
# ── Docker Entrypoint ────────────────────────────────────────────────────
# Boots a lightweight virtual desktop (Xvfb + Openbox + VNC/noVNC) so the
# Gazebo 3D window, Tkinter GUI, and any other graphical apps are visible
# through a web browser on the host at  http://localhost:6080/vnc.html
#
# After the desktop is ready the script drops into an interactive bash
# shell (or runs whatever CMD was passed to `docker run`).
set -e

# ── 1. Virtual framebuffer ──────────────────────────────────────────────
export DISPLAY="${DISPLAY:-:1}"
SCREEN_RES="${SCREEN_RES:-1920x1080x24}"

rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 2>/dev/null || true
Xvfb ${DISPLAY} -screen 0 "${SCREEN_RES}" +extension GLX +render -noreset \
    > /tmp/xvfb.log 2>&1 &
XVFB_PID=$!

# Wait until the X server is accepting connections
for _ in $(seq 1 20); do
    xdpyinfo -display ${DISPLAY} >/dev/null 2>&1 && break
    sleep 0.25
done

# ── 2. Window manager ──────────────────────────────────────────────────
openbox-session > /tmp/openbox.log 2>&1 &

# ── 3. VNC server (no password) ────────────────────────────────────────
x11vnc -display ${DISPLAY} -nopw -forever -shared -bg \
    -rfbport 5900 -xkb -noxrecord -noxfixes -noxdamage \
    > /tmp/x11vnc.log 2>&1

# ── 4. noVNC web gateway ───────────────────────────────────────────────
NOVNC_DIR="/usr/share/novnc"
websockify --web="${NOVNC_DIR}" 6080 localhost:5900 \
    > /tmp/novnc.log 2>&1 &

# ── 5. Source ROS 2 environment ─────────────────────────────────────────
source /opt/ros/jazzy/setup.bash
source "${HOME}/px4_ros2_ws/install/setup.bash" 2>/dev/null || true

echo "================================================================"
echo "  ✅  Virtual desktop ready!"
echo "  🌐  Open in browser:  http://localhost:6080/vnc.html"
echo "  🖥️  VNC client:       localhost:5900"
echo "  📐  Resolution:       ${SCREEN_RES%x*}"
echo "================================================================"

# ── 6. Run CMD or drop into shell ───────────────────────────────────────
if [ $# -gt 0 ]; then
    exec "$@"
else
    exec /bin/bash
fi
