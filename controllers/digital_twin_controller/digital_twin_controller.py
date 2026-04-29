import sys
sys.path.insert(0, '/Applications/Webots.app/Contents/lib/controller/python')

from controller import Robot
import socket
import json
import threading
import time

robot = Robot()
timestep = int(robot.getBasicTimeStep())

# Get UR5e motors
motor_names = [
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint"
]

motors = []
for name in motor_names:
    motor = robot.getDevice(name)
    motor.setPosition(0.0)
    motor.setVelocity(1.0)
    motors.append(motor)
    print(f"[Controller] Motor found: {name}")

POSES = {
    "idle":    [0.0,  -1.57,  0.0,  -1.57,  0.0,  0.0],
    "pick":    [0.5,  -1.2,   1.0,  -1.4,  -0.5,  0.0],
    "place":   [-0.5, -1.2,   1.0,  -1.4,   0.5,  0.0],
    "home":    [0.0,  -1.57,  0.0,  -1.57,  0.0,  0.0],
    "faulted": None
}

current_state = "idle"

def listen_to_ros():
    global current_state
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(('127.0.0.1', 9001))
            print("[Controller] Connected to ROS bridge!")
            buffer = ""
            while True:
                data = sock.recv(1024).decode()
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    try:
                        msg = json.loads(line)
                        new_state = msg.get("robot_state", "idle")
                        if new_state != current_state:
                            current_state = new_state
                            print(f"[Controller] State: {current_state}")
                    except:
                        pass
        except Exception as e:
            print(f"[Controller] Reconnecting in 2s... {e}")
            time.sleep(2)

threading.Thread(target=listen_to_ros, daemon=True).start()
print("[Controller] UR5e Digital Twin Controller started!")

while robot.step(timestep) != -1:
    pose = POSES.get(current_state)
    if pose:
        for i, motor in enumerate(motors):
            motor.setPosition(pose[i])
