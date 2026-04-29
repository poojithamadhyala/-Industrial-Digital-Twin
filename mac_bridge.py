import socket
import json
import threading
import time

current_state = {"robot_state": "idle", "conveyor_run": False,
                 "fault_code": 0, "cycle_count": 0}

webots_clients = []
cv_clients = []

def serve_webots():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 9001))
    server.listen(5)
    print("[Bridge] Waiting for Webots controller on port 9001...")
    while True:
        conn, addr = server.accept()
        webots_clients.append(conn)
        print(f"[Bridge] Webots controller connected!")

def serve_camera():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 9003))
    server.listen(5)
    print("[Bridge] Waiting for camera controller on port 9003...")
    while True:
        conn, addr = server.accept()
        print(f"[Bridge] Camera controller connected!")
        threading.Thread(target=forward_cv, args=(conn,), daemon=True).start()

def forward_cv(camera_conn):
    docker_sock = None
    while True:
        try:
            if docker_sock is None:
                docker_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                docker_sock.connect(('127.0.0.1', 9003))
                print("[Bridge] CV forwarding to Docker!")
            data = camera_conn.recv(4096)
            if not data:
                break
            docker_sock.sendall(data)
        except Exception as e:
            print(f"[Bridge] CV forward error: {e}")
            docker_sock = None
            time.sleep(1)

def broadcast_state():
    while True:
        packet = (json.dumps(current_state) + "\n").encode()
        for client in list(webots_clients):
            try:
                client.sendall(packet)
            except:
                webots_clients.remove(client)
        time.sleep(0.05)

def receive_from_docker():
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(('127.0.0.1', 9002))
            print("[Bridge] Connected to Docker ROS bridge!")
            buffer = ""
            while True:
                data = sock.recv(1024).decode()
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    try:
                        current_state.update(json.loads(line))
                    except:
                        pass
        except Exception as e:
            print(f"[Bridge] Reconnecting to Docker... {e}")
            time.sleep(2)

threading.Thread(target=serve_webots, daemon=True).start()
threading.Thread(target=serve_camera, daemon=True).start()
threading.Thread(target=broadcast_state, daemon=True).start()
threading.Thread(target=receive_from_docker, daemon=True).start()

print("[Bridge] Mac Bridge running!")
while True:
    time.sleep(1)
