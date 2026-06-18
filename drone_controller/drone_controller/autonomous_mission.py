import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint, VehicleCommand, VehicleStatus

class AutonomousMission(Node):
    def __init__(self):
        super().__init__('autonomous_mission')

        px4_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )

        # Publishers
        self.offboard_control_mode_publisher = self.create_publisher(
            OffboardControlMode, '/fmu/in/offboard_control_mode', px4_qos)
        self.trajectory_setpoint_publisher = self.create_publisher(
            TrajectorySetpoint, '/fmu/in/trajectory_setpoint', px4_qos)
        self.vehicle_command_publisher = self.create_publisher(
            VehicleCommand, '/fmu/in/vehicle_command', px4_qos)

        # Subscribers
        self.vehicle_status_subscriber = self.create_subscription(
            VehicleStatus, '/fmu/out/vehicle_status_v4', self.vehicle_status_callback, px4_qos)

        self.vehicle_status = VehicleStatus()
        self.offboard_setpoint_counter = 0
        
        # Flight state machine variables
        self.flight_state = "WARMUP"
        self.ticks = 0 # Count cycles at 10Hz (1 tick = 100ms)

        # Timer runs at 10Hz
        self.timer = self.create_timer(0.1, self.timer_callback)

    def vehicle_status_callback(self, msg):
        self.vehicle_status = msg

    def timer_callback(self):
        # 1. Always publish heartbeat
        self.publish_offboard_heartbeat()

        # 2. State Machine for the Flight Mission
        if self.flight_state == "WARMUP":
            self.offboard_setpoint_counter += 1
            if self.offboard_setpoint_counter >= 15:
                self.engage_offboard_mode()
                self.arm()
                self.flight_state = "TAKEOFF"
                self.ticks = 0

        elif self.flight_state == "TAKEOFF":
            # Fly up to 5 meters (z = -5.0)
            self.publish_position_setpoint(0.0, 0.0, -5.0)
            self.ticks += 1
            if self.ticks >= 60: # Hold takeoff for 6 seconds
                self.get_logger().info("Hover reached. Flying forward 3 meters...")
                self.flight_state = "FLY_FORWARD"
                self.ticks = 0

        elif self.flight_state == "FLY_FORWARD":
            # x = 3.0 (North), y = 0.0, z = -5.0
            self.publish_position_setpoint(3.0, 0.0, -5.0)
            self.ticks += 1
            if self.ticks >= 60: # Fly forward for 6 seconds
                self.get_logger().info("Forward point reached. Flying right 3 meters...")
                self.flight_state = "FLY_RIGHT"
                self.ticks = 0

        elif self.flight_state == "FLY_RIGHT":
            # x = 3.0, y = 3.0 (East), z = -5.0
            self.publish_position_setpoint(3.0, 3.0, -5.0)
            self.ticks += 1
            if self.ticks >= 60: # Fly right for 6 seconds
                self.get_logger().info("Right point reached. Returning to home coordinates...")
                self.flight_state = "RETURN_HOME"
                self.ticks = 0

        elif self.flight_state == "RETURN_HOME":
            # x = 0.0, y = 0.0, z = -5.0
            self.publish_position_setpoint(0.0, 0.0, -5.0)
            self.ticks += 1
            if self.ticks >= 60: # Hover at home for 6 seconds
                self.get_logger().info("Home reached. Initiating Landing sequence...")
                self.flight_state = "LAND"
                self.ticks = 0

        elif self.flight_state == "LAND":
            self.land()
            self.get_logger().info("Landing command sent. Shutting down controller.")
            self.timer.cancel() # Stop the timer so we stop sending setpoints and let PX4 land

    def publish_offboard_heartbeat(self):
        msg = OffboardControlMode()
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        msg.position = True
        msg.velocity = False
        msg.acceleration = False
        msg.body_rate = False
        msg.attitude = False
        self.offboard_control_mode_publisher.publish(msg)

    def publish_position_setpoint(self, x, y, z):
        msg = TrajectorySetpoint()
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        msg.position = [x, y, z]
        msg.yaw = 1.57 # Face East
        self.trajectory_setpoint_publisher.publish(msg)

    def publish_vehicle_command(self, command, param1=0.0, param2=0.0):
        msg = VehicleCommand()
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        msg.param1 = param1
        msg.param2 = param2
        msg.command = command
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        self.vehicle_command_publisher.publish(msg)

    def arm(self):
        self.publish_vehicle_command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0)

    def engage_offboard_mode(self):
        self.publish_vehicle_command(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1.0, 6.0)

    def land(self):
        self.publish_vehicle_command(VehicleCommand.VEHICLE_CMD_NAV_LAND)

def main(args=None):
    rclpy.init(args=args)
    node = AutonomousMission()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()

if __name__ == '__main__':
    main()
