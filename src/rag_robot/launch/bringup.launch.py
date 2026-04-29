"""
bringup.launch.py
-----------------
Starts the RAG bridge node and TTS node together.
Usage inside the container:
    ros2 launch rag_robot bringup.launch.py
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([

        Node(
            package='rag_robot',
            executable='rag_bridge_node',
            name='rag_bridge_node',
            output='screen',
            emulate_tty=True,
        ),

        Node(
            package='rag_robot',
            executable='tts_node',
            name='tts_node',
            output='screen',
            emulate_tty=True,
        ),

    ])
