import sys
sys.path.insert(0, '/Applications/Webots.app/Contents/lib/controller/python')

from controller import Robot, Camera
import socket
import json
import time
import threading

robot = Robot()
timestep = int(robot.getBasicTimeStep())

camera = robot.getDevice('industrial_camera')
camera.enable(timestep)
camera.recognitionEnable(timestep)

print("[Camera] Industrial camera started!")

cv_sock = None
cv_lock = threading.Lock()

def connect_to_bridge():
    global cv_sock
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('127.0.0.1', 9003))
            with cv_lock:
                cv_sock = s
            print("[Camera] Connected to CV bridge!")
            return
        except Exception as e:
            print(f"[Camera] Waiting for CV bridge... {e}")
            time.sleep(2)

threading.Thread(target=connect_to_bridge, daemon=True).start()

frame_count = 0
while robot.step(timestep) != -1:
    frame_count += 1
    if frame_count % 15 != 0:
        continue

    objects = camera.getRecognitionObjects()
    if not objects:
        continue

    detections = []
    for obj in objects:
        pos = obj.getPosition()
        colors = obj.getColors()
        detections.append({
            "position": [round(pos[0], 3), round(pos[1], 3), round(pos[2], 3)],
            "colors": [round(c, 3) for c in list(colors[:3])] if colors else [0,0,0],
            "model": str(obj.getModel())
        })

    with cv_lock:
        if cv_sock and detections:
            try:
                msg = json.dumps({"detections": detections}) + "\n"
                cv_sock.sendall(msg.encode())
            except:
                cv_sock = None
                threading.Thread(target=connect_to_bridge, daemon=True).start()
