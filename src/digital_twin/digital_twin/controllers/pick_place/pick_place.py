from controller import Supervisor

robot = Supervisor()
timestep = int(robot.getBasicTimeStep())

# ── Arm joints ────────────────────────────────────────────────────
joint_names = [
    'shoulder_pan_joint', 'shoulder_lift_joint', 'elbow_joint',
    'wrist_1_joint', 'wrist_2_joint', 'wrist_3_joint',
]
motors = []
for name in joint_names:
    m = robot.getDevice(name)
    m.setVelocity(0.6)
    motors.append(m)

# ── Gripper ───────────────────────────────────────────────────────
left_finger  = robot.getDevice('ROBOTIQ 2F-85 Gripper::left finger joint')
right_finger = robot.getDevice('ROBOTIQ 2F-85 Gripper::right finger joint')
if left_finger:  left_finger.setVelocity(0.5);  print('[Gripper] left ✓')
if right_finger: right_finger.setVelocity(0.5); print('[Gripper] right ✓')

OPEN = 0.0; CLOSED = 0.7

def set_gripper(pos):
    print(f'[Gripper] → {"OPEN" if pos < 0.1 else "CLOSE"}')
    if left_finger:  left_finger.setPosition(pos)
    if right_finger: right_finger.setPosition(pos)

# ── Nodes ─────────────────────────────────────────────────────────
conveyor     = robot.getFromDef('CONVEYOR')
gripper_node = robot.getFromDef('GRIPPER')
box_nodes = {
    'red':    robot.getFromDef('BOX_RED'),
    'blue':   robot.getFromDef('BOX_BLUE'),
    'orange': robot.getFromDef('BOX_ORANGE'),
}
conveyor_field = conveyor.getField('speed') if conveyor else None

# ── Bin drop positions ────────────────────────────────────────────
BIN_POS = {
    'red':    [-0.6, -1.3, 0.15],
    'blue':   [-0.6,  1.3, 0.15],
    'orange': [-1.6,  0.0, 0.15],
}

# ── Helpers ───────────────────────────────────────────────────────
def set_conveyor(speed):
    if conveyor_field:
        conveyor_field.setSFFloat(speed)
        print(f'[Conveyor] speed → {speed}')

def set_joints(angles, label=''):
    print(f'[Robot] → {label}')
    for m, a in zip(motors, angles):
        m.setPosition(a)

def freeze_box(node):
    node.setVelocity([0, 0, 0, 0, 0, 0])

def carry_box(box_node, seconds):
    steps = int((seconds * 1000) / timestep)
    t_field = box_node.getField('translation')
    for _ in range(steps):
        robot.step(timestep)
        if gripper_node and t_field:
            gpos = gripper_node.getPosition()
            t_field.setSFVec3f([gpos[0], gpos[1], gpos[2] - 0.05])
            freeze_box(box_node)

def wait(seconds, label=''):
    if label: print(f'[Wait] {seconds}s — {label}')
    steps = int((seconds * 1000) / timestep)
    for _ in range(steps):
        robot.step(timestep)

def find_box_in_pick_zone():
    for name, node in box_nodes.items():
        if not node: continue
        x = node.getPosition()[0]
        if abs(x - (-0.20)) < 0.25:
            print(f'[Sensor] ✓ {name} x={x:.3f}')
            return name, node
    return None, None

# ── Poses ─────────────────────────────────────────────────────────
HOME     = [ 0.00, -1.57,  0.00, -1.57,  0.00,  0.00]
WATCH    = [ 0.00, -1.20,  0.50, -1.57,  0.00,  0.00]
APPROACH = [ 1.57, -1.70,  1.90, -1.80, -1.57,  0.00]
PICK     = [ 1.57, -1.95,  2.15, -1.75, -1.57,  0.00]
LIFT     = [ 1.57, -1.40,  1.70, -1.90, -1.57,  0.00]
SWING_R  = [-1.57, -1.40,  1.70, -1.90, -1.57,  0.00]
SWING_B  = [ 1.57, -1.40,  1.70, -1.90, -1.57,  0.00]
SWING_O  = [-0.10, -1.40,  1.70, -1.90, -1.57,  0.00]

# ── Main ──────────────────────────────────────────────────────────
print('[Controller] UR5e + Carry + Snap-to-bin started')
set_gripper(OPEN)
set_joints(WATCH, 'WATCH')
wait(1.5)
set_conveyor(0.15)
cycle = 0

while robot.step(timestep) != -1:
    box_name, box_node = find_box_in_pick_zone()

    if box_name:
        print(f'\n[State] BOX DETECTED → {box_name}')
        set_conveyor(0.0)
        wait(0.5)

        set_gripper(OPEN)
        set_joints(APPROACH, 'APPROACH'); wait(2.5)
        set_joints(PICK,     'PICK');     wait(2.0)
        set_gripper(CLOSED);              wait(0.8)
        print('[Carry] Attached')

        # Lift
        set_joints(LIFT, 'LIFT')
        carry_box(box_node, 2.0)

        # Swing to correct bin
        if box_name == 'red':
            set_joints(SWING_R, 'SWING→RED')
        elif box_name == 'blue':
            set_joints(SWING_B, 'SWING→BLUE')
        else:
            set_joints(SWING_O, 'SWING→ORANGE')
        carry_box(box_node, 2.5)

        # Snap box directly into bin
        bin_pos = BIN_POS[box_name]
        t_field = box_node.getField('translation')
        if t_field:
            t_field.setSFVec3f(bin_pos)
            freeze_box(box_node)
            print(f'[Place] Snapped to {box_name} bin ✓')

        set_gripper(OPEN)
        wait(0.5)

        set_joints(HOME,  'HOME');  wait(2.5)
        set_joints(WATCH, 'WATCH'); wait(1.0)

        cycle += 1
        print(f'[Cycle] #{cycle} complete — {box_name} placed')
        set_conveyor(0.15)
    else:
        robot.step(timestep * 10)
