import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import socket
import json
import threading

class CVNode(Node):
    def __init__(self):
        super().__init__('cv_node')
        self.detection_pub = self.create_publisher(String, '/cv/detections', 10)
        self.sort_pub = self.create_publisher(String, '/cv/sort_command', 10)
        threading.Thread(target=self.start_server, daemon=True).start()
        self.get_logger().info('CV Node started on port 9003!')

    def start_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('0.0.0.0', 9003))
        server.listen(5)
        self.get_logger().info('Waiting for camera data...')
        while True:
            conn, addr = server.accept()
            self.get_logger().info(f'Camera connected!')
            threading.Thread(target=self.handle_camera,
                           args=(conn,), daemon=True).start()

    def handle_camera(self, conn):
        buffer = ""
        while True:
            try:
                data = conn.recv(4096).decode()
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    try:
                        msg = json.loads(line)
                        self.process_detections(msg.get("detections", []))
                    except:
                        pass
            except:
                break

    def classify_color(self, colors):
        r, g, b = colors[0], colors[1], colors[2]
        if r > 0.7 and g < 0.3 and b < 0.3:
            return "red"
        elif b > 0.7 and r < 0.3:
            return "blue"
        elif r > 0.7 and g > 0.3 and b < 0.3:
            return "orange"
        return "unknown"

    def process_detections(self, detections):
        for det in detections:
            color_type = self.classify_color(det["colors"])
            if color_type == "unknown":
                continue
            result = {
                "type": color_type,
                "position": det["position"],
                "bin": f"bin_{color_type}"
            }
            det_msg = String()
            det_msg.data = json.dumps(result)
            self.detection_pub.publish(det_msg)

            sort_msg = String()
            sort_msg.data = json.dumps({
                "command": "sort",
                "box_type": color_type,
                "target_bin": f"bin_{color_type}"
            })
            self.sort_pub.publish(sort_msg)
            self.get_logger().info(
                f'Detected {color_type} box → bin_{color_type}')

def main(args=None):
    rclpy.init(args=args)
    node = CVNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
