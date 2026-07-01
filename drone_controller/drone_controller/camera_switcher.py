#!/usr/bin/env python3
"""
M4E camera switcher — activates one camera at a time to reduce compute.

With lazy: true in bridge_config.yaml, ros_gz_bridge only subscribes to a
Gazebo camera topic when a ROS2 subscriber exists. Gazebo then skips rendering
that sensor. This node holds exactly one camera subscription at a time.

Active camera output (raw)       : /drone/camera/active/image_raw
Active camera output (compressed): /drone/camera/active/image_raw/compressed
Switch command                   : ros2 topic pub /drone/camera/select std_msgs/msg/String \
                                     "data: 'wide'" --once
                                   # choices: wide | medium_tele | tele  (default: wide)
Zoom command                     : ros2 topic pub /drone/camera/zoom std_msgs/msg/Float64 \
                                     "data: 5.0" --once
                                   # zoom 1–168; camera switches automatically at 3× and 7×
                                   # within each camera range, the image is digitally cropped

Prefer the /compressed topic for consumers — the raw frames are 60–144 MB each
and will stress DDS transport; JPEG output is typically <1 MB at quality 85.
"""

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage, Image
from std_msgs.msg import Float64, String

CAMERAS = {
    'wide':        '/drone/camera/wide/image_raw',
    'medium_tele': '/drone/camera/medium_tele/image_raw',
    'tele':        '/drone/camera/tele/image_raw',
}
DEFAULT = 'wide'

# Zoom value at which each lens becomes active (matches GUI breakpoints).
# crop_ratio = ZOOM_BASE[camera] / current_zoom
ZOOM_BASE = {
    'wide':        1.0,
    'medium_tele': 3.0,
    'tele':        7.0,
}

JPEG_QUALITY = 85


class CameraSwitcher(Node):
    def __init__(self):
        super().__init__('camera_switcher')

        self._active_name = None
        self._active_sub  = None
        self._zoom        = 1.0
        self._crop_ratio  = 1.0

        self._pub = self.create_publisher(Image, '/drone/camera/active/image_raw', 1)
        self._compressed_pub = self.create_publisher(
            CompressedImage, '/drone/camera/active/image_raw/compressed', 1)

        self._cmd_sub = self.create_subscription(
            String,  '/drone/camera/select', self._on_select, 10)
        self._zoom_sub = self.create_subscription(
            Float64, '/drone/camera/zoom',   self._on_zoom,   10)

        self._switch(DEFAULT)
        self.get_logger().info(
            f"Camera switcher ready. Active: '{DEFAULT}'. "
            f"Zoom: {self._zoom:.1f}×. "
            f"Compressed output on /drone/camera/active/image_raw/compressed.")

    # ── camera selection ─────────────────────────────────────────────────────

    def _on_select(self, msg: String) -> None:
        name = msg.data.strip()
        if name not in CAMERAS:
            self.get_logger().warn(
                f"Unknown camera '{name}'. Choices: {list(CAMERAS)}")
            return
        if name == self._active_name:
            return
        self._switch(name)

    def _switch(self, name: str) -> None:
        if self._active_sub is not None:
            self.destroy_subscription(self._active_sub)
            self._active_sub = None

        self._active_name = name
        self._active_sub = self.create_subscription(
            Image, CAMERAS[name], self._relay, 1)
        self._update_crop()
        self.get_logger().info(
            f"Active camera → {name}  ({CAMERAS[name]})  zoom={self._zoom:.1f}×")

    # ── zoom / digital crop ──────────────────────────────────────────────────

    def _on_zoom(self, msg: Float64) -> None:
        self._zoom = max(1.0, float(msg.data))
        self._update_crop()

    def _update_crop(self) -> None:
        base = ZOOM_BASE.get(self._active_name, 1.0)
        self._crop_ratio = min(1.0, base / self._zoom)

    def _apply_zoom(self, msg: Image):
        """Return (numpy_rgb_array, Image_msg) after digital zoom crop."""
        arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)

        if self._crop_ratio >= 0.999:
            return arr, msg

        h, w = arr.shape[:2]
        ch = max(1, int(h * self._crop_ratio))
        cw = max(1, int(w * self._crop_ratio))
        y0 = (h - ch) // 2
        x0 = (w - cw) // 2
        cropped = arr[y0:y0 + ch, x0:x0 + cw]
        out_arr = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

        out_msg = Image()
        out_msg.header    = msg.header
        out_msg.height    = h
        out_msg.width     = w
        out_msg.encoding  = msg.encoding
        out_msg.is_bigendian = msg.is_bigendian
        out_msg.step      = w * 3  # R8G8B8
        out_msg.data      = out_arr.tobytes()
        return out_arr, out_msg

    # ── relay ────────────────────────────────────────────────────────────────

    def _relay(self, msg: Image) -> None:
        raw_subs = self._pub.get_subscription_count()
        cmp_subs = self._compressed_pub.get_subscription_count()

        if raw_subs == 0 and cmp_subs == 0:
            return

        arr, out_msg = self._apply_zoom(msg)

        if raw_subs > 0:
            self._pub.publish(out_msg)

        if cmp_subs == 0:
            return

        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        ok, buf = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ok:
            return

        cimg = CompressedImage()
        cimg.header = msg.header
        cimg.format = 'jpeg'
        cimg.data   = buf.tobytes()
        self._compressed_pub.publish(cimg)


def main():
    rclpy.init()
    node = CameraSwitcher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
