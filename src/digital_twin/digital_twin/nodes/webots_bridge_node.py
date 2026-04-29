import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import socket
import json
import threading

class WebotsBridgeNode(Node):
    def __init__(self):
        super().__init__('webots_bridge')
        self._clients = []

        self.create_subscription(
            String, '/plc/state', self.state_callback, 10)

        threading.Thread(target=self.start_server, daemon=True).start()
        self.get_logger().info('Webots Bridge Node started on port 9001!')

    def start_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('0.0.0.0', 9001))
        server.listen(5)
        self.get_logger().info('Waiting for Webots controller on port 9001...')
        while True:
            conn, addr = server.accept()
            self._clients.append(conn)
            self.get_logger().info(f'Webots controller connected from {addr}!')

    def state_callback(self, msg):
        packet = (msg.data + "\n").encode()
        for client in list(self._clients):
            try:
                client.sendall(packet)
            except:
                self._clients.remove(client)

def main(args=None):
    rclpy.init(args=args)
    node = WebotsBridgeNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
