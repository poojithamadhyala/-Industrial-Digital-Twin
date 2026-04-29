import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Int32, Bool
import json
import time
import threading
import random

class PLCSimulatorNode(Node):

    FAULT_TYPES = {
        1: "Part jam detected",
        2: "Missed pick",
        3: "Sensor timeout",
        4: "Gripper failure",
        5: "Conveyor overload",
    }

    def __init__(self):
        super().__init__('plc_simulator')

        # Publishers
        self.state_pub    = self.create_publisher(String, '/plc/state', 10)
        self.fault_pub    = self.create_publisher(Int32,  '/plc/fault_code', 10)
        self.conveyor_pub = self.create_publisher(Bool,   '/plc/conveyor_run', 10)
        self.cycle_pub    = self.create_publisher(Int32,  '/plc/cycle_count', 10)

        # Subscribers
        self.create_subscription(Bool, '/plc/reset_fault', self.reset_fault_cb, 10)

        # State
        self.robot_state  = 'idle'
        self.conveyor_run = False
        self.fault_code   = 0
        self.cycle_count  = 0
        self._faulted     = False

        # ── Change-detection: only publish when state differs ──────────
        self._last_published = {}
        self._last_heartbeat = 0.0   # force publish on startup

        # 20Hz timer — but publish_state now skips if nothing changed
        self.create_timer(0.05, self.publish_state)

        threading.Thread(target=self._cycle_loop,      daemon=True).start()
        threading.Thread(target=self._fault_generator, daemon=True).start()

        self.get_logger().info('PLC Simulator Node started!')

    # ── Cycle loop (unchanged) ──────────────────────────────────────
    def _cycle_loop(self):
        sequence = [
            ('idle',  False, 2),
            ('pick',  True,  3),
            ('place', True,  3),
            ('home',  True,  2),
        ]
        while rclpy.ok():
            for state, conveyor, duration in sequence:
                if self._faulted:
                    self.robot_state  = 'faulted'
                    self.conveyor_run = False
                    while self._faulted:
                        time.sleep(0.1)
                    continue
                self.robot_state  = state
                self.conveyor_run = conveyor
                if state == 'home':
                    self.cycle_count += 1
                time.sleep(duration)

    # ── Fault generator (unchanged) ────────────────────────────────
    def _fault_generator(self):
        while rclpy.ok():
            time.sleep(random.uniform(20, 40))
            if not self._faulted:
                self.fault_code = random.randint(1, 5)
                self._faulted   = True
                self.get_logger().warn(
                    f'FAULT INJECTED: {self.FAULT_TYPES[self.fault_code]}'
                )

    def reset_fault_cb(self, msg):
        if msg.data:
            self.fault_code = 0
            self._faulted   = False
            self.get_logger().info('Fault reset by operator')

    # ── Publisher: only fires when state actually changes ──────────
    def publish_state(self):
        current = {
            'robot_state':   self.robot_state,
            'conveyor_run':  self.conveyor_run,
            'fault_code':    self.fault_code,
            'fault_message': self.FAULT_TYPES.get(self.fault_code, ''),
            'cycle_count':   self.cycle_count,
        }

        now = time.time()
        heartbeat_due = (now - self._last_heartbeat) >= 1.0
        state_changed = (current != self._last_published)

        # Skip publish if nothing changed AND heartbeat not due
        if not state_changed and not heartbeat_due:
            return

        # Publish consolidated state (dashboard reads this)
        state_msg      = String()
        state_msg.data = json.dumps(current)
        self.state_pub.publish(state_msg)

        # Publish individual topics (for other ROS nodes)
        fault_msg      = Int32(); fault_msg.data = self.fault_code
        conveyor_msg   = Bool();  conveyor_msg.data = self.conveyor_run
        cycle_msg      = Int32(); cycle_msg.data = self.cycle_count
        self.fault_pub.publish(fault_msg)
        self.conveyor_pub.publish(conveyor_msg)
        self.cycle_pub.publish(cycle_msg)

        self._last_published = current.copy()
        self._last_heartbeat = now


def main(args=None):
    rclpy.init(args=args)
    node = PLCSimulatorNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()