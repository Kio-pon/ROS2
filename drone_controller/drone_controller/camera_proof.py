#!/usr/bin/env python3
"""
Camera proof-of-life — Farmevo simulation environment, Phase 1 / Task 1.2.

This is the "external process" half of the proof-of-life: it subscribes to the
simulated camera feed (after it has been bridged from Gazebo into ROS 2) and
proves the frames are actually flowing out of the renderer and into a separate
ROS 2 process. For each run it:

  * logs the first frame with a clear PROOF-OF-LIFE banner,
  * reports resolution / encoding and a rolling frame rate,
  * writes the first frame and a periodically-refreshed "latest" frame to disk
    as the acceptance artifact (PNG if Pillow is available, otherwise PPM).

Pipeline (see run_camera_proof.sh):
    Gazebo camera sensor  --(gz transport)-->  ros_gz_image image_bridge
                          --(sensor_msgs/Image)-->  THIS NODE

Parameters:
    topic       (str)    bridged ROS image topic         default: /camera
    save_dir    (str)    where to write frames           default: ~/farmevo_proof
    save_period (float)  seconds between "latest" saves   default: 2.0

Run:
    ros2 run drone_controller camera_proof
    ros2 run drone_controller camera_proof --ros-args -p topic:=/my/image
"""

from __future__ import annotations

import os
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image

try:
    from PIL import Image as PILImage  # optional, for nicer PNG output
    _HAVE_PIL = True
except ImportError:
    _HAVE_PIL = False


class CameraProof(Node):
    def __init__(self):
        super().__init__("camera_proof")

        self.topic = self.declare_parameter("topic", "/camera").value
        save_dir = self.declare_parameter("save_dir", "~/farmevo_proof").value
        self.save_period = float(self.declare_parameter("save_period", 2.0).value)
        self.save_dir = os.path.expanduser(save_dir)
        os.makedirs(self.save_dir, exist_ok=True)

        # Sensor-data QoS (best effort) matches what the image bridge publishes.
        self.create_subscription(Image, self.topic, self._on_image, qos_profile_sensor_data)

        self.count = 0
        self.first_seen = False
        self._window_start = time.monotonic()
        self._window_count = 0
        self._last_save = 0.0

        self.get_logger().info(
            f"Waiting for camera frames on '{self.topic}' "
            f"(saving to {self.save_dir}, Pillow={'yes' if _HAVE_PIL else 'no'})..."
        )

    # ---- Frame handling ------------------------------------------------------
    def _on_image(self, msg: Image):
        self.count += 1
        self._window_count += 1

        if not self.first_seen:
            self.first_seen = True
            self.get_logger().info("=" * 58)
            self.get_logger().info("  PROOF-OF-LIFE: first camera frame received in ROS 2")
            self.get_logger().info(
                f"  {msg.width} x {msg.height}  encoding={msg.encoding}  "
                f"step={msg.step}  frame_id={msg.header.frame_id or '(none)'}"
            )
            path = self._save(msg, "first_frame")
            if path:
                self.get_logger().info(f"  saved acceptance artifact -> {path}")
            self.get_logger().info("=" * 58)

        # Rolling FPS roughly once per second.
        now = time.monotonic()
        elapsed = now - self._window_start
        if elapsed >= 1.0:
            fps = self._window_count / elapsed
            self.get_logger().info(
                f"streaming: frame #{self.count}  {msg.width}x{msg.height}  "
                f"{fps:.1f} FPS"
            )
            self._window_start = now
            self._window_count = 0

        # Refresh the "latest" still every save_period seconds.
        if now - self._last_save >= self.save_period:
            self._last_save = now
            self._save(msg, "latest")

    # ---- Saving --------------------------------------------------------------
    def _packed_rgb(self, msg: Image):
        """Return tightly-packed RGB bytes, or None if the encoding is unsupported."""
        enc = msg.encoding.lower()
        if enc in ("rgb8", "bgr8"):
            channels = 3
        elif enc in ("mono8", "8uc1"):
            channels = 1
        else:
            return None, enc

        row_bytes = msg.width * channels
        data = bytes(msg.data)
        # Drop any per-row padding (step may exceed width*channels).
        if msg.step != row_bytes:
            data = b"".join(
                data[r * msg.step: r * msg.step + row_bytes] for r in range(msg.height)
            )

        if channels == 1:
            # Expand grayscale to RGB so every viewer can open it.
            data = bytes(b for v in data for b in (v, v, v))
        elif enc == "bgr8":
            # Swap B and R.
            ba = bytearray(data)
            ba[0::3], ba[2::3] = ba[2::3], ba[0::3]
            data = bytes(ba)
        return data, enc

    def _save(self, msg: Image, stem: str):
        rgb, enc = self._packed_rgb(msg)
        if rgb is None:
            self.get_logger().warn(f"Cannot save frame: unsupported encoding '{enc}'.")
            return None

        if _HAVE_PIL:
            path = os.path.join(self.save_dir, f"{stem}.png")
            PILImage.frombytes("RGB", (msg.width, msg.height), rgb).save(path)
        else:
            path = os.path.join(self.save_dir, f"{stem}.ppm")
            with open(path, "wb") as f:
                f.write(f"P6\n{msg.width} {msg.height}\n255\n".encode())
                f.write(rgb)
        return path


def main(args=None):
    rclpy.init(args=args)
    node = CameraProof()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.get_logger().info(f"Received {node.count} frames total.")
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
