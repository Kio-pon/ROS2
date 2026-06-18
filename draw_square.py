import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

class SquareDrawer(Node):
    def __init__(self):
        super().__init__('square_drawer')
        # 1. Create a publisher to /turtle1/cmd_vel
        self.publisher = self.create_publisher(Twist, '/turtle1/cmd_vel', 10)
        
        # 2. Create a timer that fires every 1.0 second
        self.timer = self.create_timer(1.0, self.timer_callback)
        
        # We start by moving forward
        self.state = "FORWARD" 
        self.get_logger().info("Square Drawer Node has started! Time to code.")

    def timer_callback(self):
        msg = Twist()
        
        if self.state == "FORWARD":
            self.get_logger().info("Moving forward...")
            # ----------------------------------------------------
            msg.linear.x = 2.0
            self.state = "TURN"
            # ----------------------------------------------------
            
            
        elif self.state == "TURN":
            self.get_logger().info("Turning 90 degrees...")
            # ----------------------------------------------------
            msg.angular.z = 1.57
            self.state = "FORWARD"
            # ----------------------------------------------------
            
            
        # Publish the command
        self.publisher.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = SquareDrawer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
