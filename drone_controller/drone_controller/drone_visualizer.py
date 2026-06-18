import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from px4_msgs.msg import VehicleLocalPosition, VehicleStatus, VehicleCommand
import tkinter as tk
from tkinter import ttk
import threading
import math
import time

class DroneVisualizerNode(Node):
    def __init__(self, on_telemetry_cb):
        super().__init__('drone_visualizer')
        self.on_telemetry_cb = on_telemetry_cb

        px4_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )

        # Subscribers
        self.local_pos_sub = self.create_subscription(
            VehicleLocalPosition, '/fmu/out/vehicle_local_position_v1', self.position_callback, px4_qos)
        self.status_sub = self.create_subscription(
            VehicleStatus, '/fmu/out/vehicle_status_v4', self.status_callback, px4_qos)

        # Publishers for GUI command buttons
        self.vehicle_command_publisher = self.create_publisher(
            VehicleCommand, '/fmu/in/vehicle_command', px4_qos)

    def position_callback(self, msg):
        # NED coordinates: z is negative altitude
        altitude = -msg.z
        x = msg.x
        y = msg.y
        self.on_telemetry_cb(altitude=altitude, x=x, y=y)

    def status_callback(self, msg):
        armed = msg.arming_state == 2 # ARMING_STATE_ARMED
        nav_state = msg.nav_state
        self.on_telemetry_cb(armed=armed, nav_state=nav_state)

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
        self.vehicle_command_publisher.publish(msg)

    def arm(self):
        self.get_logger().info("Arming drone via GUI...")
        self.publish_command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0)

    def takeoff(self):
        self.get_logger().info("Sending Takeoff command via GUI...")
        self.publish_command(VehicleCommand.VEHICLE_CMD_NAV_TAKEOFF, param7=2.5) # Takeoff altitude 2.5m

    def land(self):
        self.get_logger().info("Sending Land command via GUI...")
        self.publish_command(VehicleCommand.VEHICLE_CMD_NAV_LAND)

    def rtl(self):
        self.get_logger().info("Sending RTL command via GUI...")
        self.publish_command(VehicleCommand.VEHICLE_CMD_NAV_RETURN_TO_LAUNCH)


class DroneVisualizerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ROS 2 PX4 Drone Visualizer")
        self.root.geometry("800x650")
        self.root.configure(bg="#1e1e24")

        # Telemetry State
        self.altitude = 0.0
        self.x = 0.0
        self.y = 0.0
        self.armed = False
        self.nav_state = 0
        self.propeller_angle = 0.0

        # Styles
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', font=('Helvetica', 11, 'bold'), borderwidth=1)
        style.configure('Takeoff.TButton', background='#2a9d8f', foreground='white')
        style.configure('Land.TButton', background='#e76f51', foreground='white')
        style.configure('Rtl.TButton', background='#f4a261', foreground='white')
        style.configure('Arm.TButton', background='#e63946', foreground='white')

        # Header Frame
        header = tk.Frame(root, bg="#2b2d42", height=60)
        header.pack(fill=tk.X)
        
        title_lbl = tk.Label(header, text="🛸 PX4 Autonomous Flight Dashboard", font=("Helvetica", 16, "bold"), fg="#edf2f4", bg="#2b2d42")
        title_lbl.pack(pady=15)

        # Layout: Main canvas and right-side telemetry panel
        main_layout = tk.Frame(root, bg="#1e1e24")
        main_layout.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 2D Side-View Canvas (Green floor/blue sky)
        self.canvas_width = 540
        self.canvas_height = 400
        self.canvas = tk.Canvas(main_layout, width=self.canvas_width, height=self.canvas_height, bg="#d8f3dc", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Telemetry Panel
        self.panel = tk.Frame(main_layout, bg="#2b2d42", width=220)
        self.panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))

        # Telemetry Labels
        tk.Label(self.panel, text="TELEMETRY DATA", font=("Helvetica", 12, "bold"), fg="#ffb703", bg="#2b2d42").pack(pady=15)
        
        self.lbl_armed = tk.Label(self.panel, text="Status: DISARMED", font=("Helvetica", 11, "bold"), fg="#e63946", bg="#2b2d42")
        self.lbl_armed.pack(anchor=tk.W, padx=15, pady=5)

        self.lbl_alt = tk.Label(self.panel, text="Altitude: 0.00 m", font=("Helvetica", 11), fg="#edf2f4", bg="#2b2d42")
        self.lbl_alt.pack(anchor=tk.W, padx=15, pady=5)

        self.lbl_x = tk.Label(self.panel, text="North (X): 0.00 m", font=("Helvetica", 11), fg="#edf2f4", bg="#2b2d42")
        self.lbl_x.pack(anchor=tk.W, padx=15, pady=5)

        self.lbl_y = tk.Label(self.panel, text="East (Y): 0.00 m", font=("Helvetica", 11), fg="#edf2f4", bg="#2b2d42")
        self.lbl_y.pack(anchor=tk.W, padx=15, pady=5)

        # Control Panel (Buttons)
        self.control_frame = tk.Frame(root, bg="#2b2d42", height=100)
        self.control_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=10)

        self.btn_arm = ttk.Button(self.control_frame, text="ARM MOTORS", style='Arm.TButton', command=self.on_arm_btn)
        self.btn_arm.pack(side=tk.LEFT, padx=15, pady=15, expand=True, fill=tk.BOTH)

        self.btn_takeoff = ttk.Button(self.control_frame, text="TAKEOFF (2.5m)", style='Takeoff.TButton', command=self.on_takeoff_btn)
        self.btn_takeoff.pack(side=tk.LEFT, padx=15, pady=15, expand=True, fill=tk.BOTH)

        self.btn_land = ttk.Button(self.control_frame, text="LAND", style='Land.TButton', command=self.on_land_btn)
        self.btn_land.pack(side=tk.LEFT, padx=15, pady=15, expand=True, fill=tk.BOTH)

        self.btn_rtl = ttk.Button(self.control_frame, text="RETURN HOME (RTL)", style='Rtl.TButton', command=self.on_rtl_btn)
        self.btn_rtl.pack(side=tk.LEFT, padx=15, pady=15, expand=True, fill=tk.BOTH)

        # Start ROS 2 Node in a separate background thread
        self.node = None
        self.ros_thread = threading.Thread(target=self.run_ros_node, daemon=True)
        self.ros_thread.start()

        # Canvas drawings
        self.draw_scenery()
        self.update_gui_loop()

    def run_ros_node(self):
        rclpy.init()
        self.node = DroneVisualizerNode(self.update_telemetry_data)
        rclpy.spin(self.node)
        self.node.destroy_node()
        rclpy.shutdown()

    def update_telemetry_data(self, **kwargs):
        if 'altitude' in kwargs:
            self.altitude = kwargs['altitude']
        if 'x' in kwargs:
            self.x = kwargs['x']
        if 'y' in kwargs:
            self.y = kwargs['y']
        if 'armed' in kwargs:
            self.armed = kwargs['armed']
        if 'nav_state' in kwargs:
            self.nav_state = kwargs['nav_state']

    def draw_scenery(self):
        # Draw sky (blue) and ground grass floor (green)
        self.sky_height = self.canvas_height - 80
        self.canvas.create_rectangle(0, 0, self.canvas_width, self.sky_height, fill="#8ecae6", outline="")
        self.canvas.create_rectangle(0, self.sky_height, self.canvas_width, self.canvas_height, fill="#2d6a4f", outline="")
        
        # Ground floor visual markings (little grass tufts)
        for gx in range(40, self.canvas_width, 80):
            self.canvas.create_line(gx, self.sky_height, gx-5, self.sky_height-10, fill="#1b4332", width=2)
            self.canvas.create_line(gx, self.sky_height, gx+5, self.sky_height-10, fill="#1b4332", width=2)

    def draw_drone(self, alt_val):
        # Scale altitude: 1 meter = 40 pixels on screen
        scale = 40.0
        # Ground baseline
        base_y = self.sky_height
        
        # Drone Y pixel position
        drone_y = base_y - (alt_val * scale)
        # Prevent drone from going below ground visually
        if drone_y > base_y - 10:
            drone_y = base_y - 10
        if drone_y < 40:
            drone_y = 40 # Don't fly off-screen top

        # X position centered
        drone_x = self.canvas_width / 2

        # Draw landing gear/shadow on the ground
        shadow_r = max(5, 30 - int(alt_val * 4))
        self.canvas.create_oval(drone_x - shadow_r, base_y - 4, drone_x + shadow_r, base_y + 4, fill="#1b4332", outline="")

        # Draw Drone body
        # Central frame
        self.canvas.create_rectangle(drone_x - 30, drone_y - 5, drone_x + 30, drone_y + 5, fill="#343a40", outline="#e9ecef", width=2)
        self.canvas.create_oval(drone_x - 12, drone_y - 12, drone_x + 12, drone_y + 12, fill="#e63946", outline="#343a40", width=2)
        
        # Left and Right motor stands
        self.canvas.create_line(drone_x - 30, drone_y, drone_x - 30, drone_y - 8, fill="#e9ecef", width=3)
        self.canvas.create_line(drone_x + 30, drone_y, drone_x + 30, drone_y - 8, fill="#e9ecef", width=3)

        # Propellers (spin if armed)
        if self.armed:
            self.propeller_angle += 0.4
            if self.propeller_angle > 2 * math.pi:
                self.propeller_angle = 0.0

        p_len = 20
        # Left propeller
        lx1 = drone_x - 30 - math.cos(self.propeller_angle) * p_len
        ly1 = drone_y - 8 - math.sin(self.propeller_angle) * p_len/3
        lx2 = drone_x - 30 + math.cos(self.propeller_angle) * p_len
        ly2 = drone_y - 8 + math.sin(self.propeller_angle) * p_len/3
        self.canvas.create_line(lx1, ly1, lx2, ly2, fill="#ffb703", width=2)

        # Right propeller
        rx1 = drone_x + 30 - math.cos(-self.propeller_angle + 1.5) * p_len
        ry1 = drone_y - 8 - math.sin(-self.propeller_angle + 1.5) * p_len/3
        rx2 = drone_x + 30 + math.cos(-self.propeller_angle + 1.5) * p_len
        ry2 = drone_y - 8 + math.sin(-self.propeller_angle + 1.5) * p_len/3
        self.canvas.create_line(rx1, ry1, rx2, ry2, fill="#ffb703", width=2)

    def update_gui_loop(self):
        # Clear dynamic drawings
        self.canvas.delete("all")
        self.draw_scenery()

        # Draw the drone at its current altitude
        self.draw_drone(self.altitude)

        # Update labels
        self.lbl_alt.config(text=f"Altitude: {self.altitude:.2f} m")
        self.lbl_x.config(text=f"North (X): {self.x:.2f} m")
        self.lbl_y.config(text=f"East (Y): {self.y:.2f} m")

        if self.armed:
            self.lbl_armed.config(text="Status: ARMED", fg="#2a9d8f")
            self.btn_arm.config(text="ARMED (Motors Running)")
        else:
            self.lbl_armed.config(text="Status: DISARMED", fg="#e63946")
            self.btn_arm.config(text="ARM MOTORS")

        # Loop at ~30 FPS
        self.root.after(33, self.update_gui_loop)

    def on_arm_btn(self):
        if self.node:
            self.node.arm()

    def on_takeoff_btn(self):
        if self.node:
            self.node.takeoff()

    def on_land_btn(self):
        if self.node:
            self.node.land()

    def on_rtl_btn(self):
        if self.node:
            self.node.rtl()


def main():
    root = tk.Tk()
    gui = DroneVisualizerGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()
