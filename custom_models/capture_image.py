import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import numpy as np
import cv2
import time

class ImageCapture(Node):
    def __init__(self):
        super().__init__('image_capture')
        # The camera topic depends on the launch, but is typically /camera or /camera/image_raw
        self.subscription = self.create_subscription(
            Image,
            '/camera',
            self.listener_callback,
            10)
        self.done = False
        self.get_logger().info('Waiting for camera image on /camera...')

    def listener_callback(self, msg):
        self.get_logger().info('Received image, saving to workspace...')
        img = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, -1)
        if msg.encoding == 'rgb8':
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        cv2.imwrite('/home/student/wheat_test.png', img)
        self.done = True

def main():
    rclpy.init()
    node = ImageCapture()
    
    start_time = time.time()
    while rclpy.ok() and not node.done:
        rclpy.spin_once(node, timeout_sec=0.5)
        if time.time() - start_time > 60:
            print("Timeout waiting for image")
            break
            
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
