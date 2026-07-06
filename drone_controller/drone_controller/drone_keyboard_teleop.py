import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint, VehicleCommand, VehicleLocalPosition, VehicleStatus
import sys
import select
import termios
import tty
import threading
import math

# Instructions banner shown to the user on startup
msg_banner = """
=================================================
Drone Keyboard Teleoperation Node
=================================================
Control your drone in real-time using your keyboard!

Moving around:
        W (Forward)
   A (Left)   S (Back)   D (Right)

Height:
   U / Arrow-Up    : Move UP (climb)
   O / Arrow-Down  : Move DOWN (descend)

Rotation:
   J / Arrow-Left  : Rotate LEFT (yaw CCW)
   L / Arrow-Right : Rotate RIGHT (yaw CW)

Commands:
   SPACEBAR : STOP in place (zero all velocities)
   Y        : ARM the drone motors
   N        : DISARM the drone motors
   T        : TAKEOFF (climbs to 2.5m)
   G        : LAND
   R        : RETURN TO LAUNCH (RTL)

Press CTRL+C to quit.
=================================================
"""

class DroneKeyboardTeleop(Node):
    def __init__(self):
        super().__init__('drone_keyboard_teleop')

        px4_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )

        # Publishers
        self.offboard_mode_pub = self.create_publisher(
            OffboardControlMode, '/fmu/in/offboard_control_mode', px4_qos)
        self.trajectory_pub = self.create_publisher(
            TrajectorySetpoint, '/fmu/in/trajectory_setpoint', px4_qos)
        self.vehicle_cmd_pub = self.create_publisher(
            VehicleCommand, '/fmu/in/vehicle_command', px4_qos)

        # Subscribers
        self.local_pos_sub = self.create_subscription(
            VehicleLocalPosition, '/fmu/out/vehicle_local_position_v1', self.local_position_callback, px4_qos)
        self.status_sub = self.create_subscription(
            VehicleStatus, '/fmu/out/vehicle_status_v4', self.vehicle_status_callback, px4_qos)

        # State variables
        self.vehicle_status = VehicleStatus()
        self.local_position = VehicleLocalPosition()
        self.current_yaw = 0.0

        # Command Velocities (Forward-Left-Up coordinates: Forward=X, Left=Y, Up=Z)
        self.vx = 0.0
        self.vy = 0.0
        self.vz = 0.0
        self.yaw_rate = 0.0

        # Speed limits
        self.SPEED_STEP = 1.0     # m/s step per key press
        self.YAW_STEP = 0.3       # rad/s step per key press
        self.MAX_SPEED = 8.0      # m/s
        self.MAX_YAW_RATE = 1.5   # rad/s

        # Terminal settings backup
        self.settings = termios.tcgetattr(sys.stdin)

        # 20Hz Timer to send offboard commands & heartbeats
        self.timer = self.create_timer(0.05, self.timer_callback)

        # Start keyboard reader thread
        self.keep_reading = True
        self.keyboard_thread = threading.Thread(target=self.keyboard_loop, daemon=True)
        self.keyboard_thread.start()

        self.get_logger().info("Keyboard Teleop Node started!")
        print(msg_banner)
        self.print_speeds()

    def local_position_callback(self, msg):
        self.local_position = msg
        # VehicleLocalPosition has no quaternion; it exposes yaw directly as `heading`.
        self.current_yaw = msg.heading

    def vehicle_status_callback(self, msg):
        self.vehicle_status = msg

    def timer_callback(self):
        # We must publish heartbeat to stay in offboard mode
        self.publish_offboard_heartbeat()

        # Only publish setpoints if we are in offboard mode
        # (nav_state 14 is OFFBOARD mode in PX4 v1.14+)
        if self.vehicle_status.nav_state == 14:
            self.publish_velocity_setpoint()

    def publish_offboard_heartbeat(self):
        msg = OffboardControlMode()
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        msg.position = False
        msg.velocity = True
        msg.acceleration = False
        msg.body_rate = False
        msg.attitude = False
        self.offboard_mode_pub.publish(msg)

    def publish_velocity_setpoint(self):
        # Convert FLU (Forward-Left-Up) velocities to NED (North-East-Down) relative to heading
        vx_ned, vy_ned, vz_ned = self.flu_to_ned(self.vx, self.vy, self.vz, self.current_yaw)

        msg = TrajectorySetpoint()
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        msg.position = [float('nan'), float('nan'), float('nan')] # NAN means ignore position
        msg.velocity = [vx_ned, vy_ned, vz_ned]
        msg.yaw = float('nan')
        msg.yawspeed = self.yaw_rate
        self.trajectory_pub.publish(msg)

    def flu_to_ned(self, vx, vy, vz, yaw):
        # Rotate velocity vectors based on current yaw heading
        cos_y = math.cos(yaw)
        sin_y = math.sin(yaw)
        vx_ned = cos_y * vx - sin_y * vy
        vy_ned = sin_y * vx + cos_y * vy
        # In NED, Down is positive, so moving UP is negative Z
        vz_ned = -vz
        return vx_ned, vy_ned, vz_ned

    def publish_command(self, command, param1=0.0, param2=0.0):
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
        self.vehicle_cmd_pub.publish(msg)

    def print_speeds(self):
        # Overwrite the current line with updated speed readouts
        sys.stdout.write(f"\rSpeeds -> Forward (X): {self.vx:+.1f} m/s | Left (Y): {self.vy:+.1f} m/s | Up (Z): {self.vz:+.1f} m/s | Yaw Rate: {self.yaw_rate:+.1f} rad/s   ")
        sys.stdout.flush()

    def get_key(self):
        tty.setraw(sys.stdin.fileno())
        rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
        if rlist:
            key = sys.stdin.read(1)
            # Handle escape sequences for arrow keys
            if key == '\x1b':
                additional_chars = sys.stdin.read(2)
                key += additional_chars
        else:
            key = ''
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.settings)
        return key

    def keyboard_loop(self):
        while self.keep_reading:
            key = self.get_key()
            if not key:
                continue

            # Check key mappings
            if key == '\x03': # Ctrl+C
                self.keep_reading = False
                break
            
            # W / S : Forward / Back
            elif key.lower() == 'w':
                self.vx = min(self.MAX_SPEED, self.vx + self.SPEED_STEP)
            elif key.lower() == 's':
                self.vx = max(-self.MAX_SPEED, self.vx - self.SPEED_STEP)
            
            # A / D : Left / Right
            elif key.lower() == 'a':
                self.vy = min(self.MAX_SPEED, self.vy + self.SPEED_STEP)
            elif key.lower() == 'd':
                self.vy = max(-self.MAX_SPEED, self.vy - self.SPEED_STEP)
            
            # U / O or Arrow-Up / Arrow-Down : Up / Down
            elif key.lower() == 'u' or key == '\x1b[A':
                self.vz = min(self.MAX_SPEED, self.vz + self.SPEED_STEP)
            elif key.lower() == 'o' or key == '\x1b[B':
                self.vz = max(-self.MAX_SPEED, self.vz - self.SPEED_STEP)
            
            # J / L or Arrow-Left / Arrow-Right : Rotate Left / Right
            elif key.lower() == 'j' or key == '\x1b[D':
                self.yaw_rate = min(self.MAX_YAW_RATE, self.yaw_rate + self.YAW_STEP)
            elif key.lower() == 'l' or key == '\x1b[C':
                self.yaw_rate = max(-self.MAX_YAW_RATE, self.yaw_rate - self.YAW_STEP)
            
            # Spacebar : Stop in place
            elif key == ' ':
                self.vx = 0.0
                self.vy = 0.0
                self.vz = 0.0
                self.yaw_rate = 0.0
                print("\n[STOP] Zeroed all velocities.")
            
            # Y : Arm
            elif key.lower() == 'y':
                print("\n[COMMAND] Arming motors...")
                self.publish_command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0)
            
            # N : Disarm
            elif key.lower() == 'n':
                print("\n[COMMAND] Disarming motors...")
                self.publish_command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 0.0)
            
            # T : Takeoff
            elif key.lower() == 't':
                print("\n[COMMAND] Taking off...")
                self.publish_command(VehicleCommand.VEHICLE_CMD_NAV_TAKEOFF, param7=2.5)
            
            # G : Land
            elif key.lower() == 'g':
                print("\n[COMMAND] Landing...")
                self.publish_command(VehicleCommand.VEHICLE_CMD_NAV_LAND)
            
            # R : RTL
            elif key.lower() == 'r':
                print("\n[COMMAND] Returning to Launch...")
                self.publish_command(VehicleCommand.VEHICLE_CMD_NAV_RETURN_TO_LAUNCH)
            
            # Mode Switch: Switch to Offboard Mode (Must be done to control via keyboard)
            elif key.lower() == 'f':
                print("\n[COMMAND] Switching to Offboard Flight Mode...")
                self.publish_command(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1.0, 6.0)

            self.print_speeds()

        # Restore terminal settings on exit
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.settings)

def main(args=None):
    rclpy.init(args=args)
    node = DroneKeyboardTeleop()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.keep_reading = False
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, node.settings)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
