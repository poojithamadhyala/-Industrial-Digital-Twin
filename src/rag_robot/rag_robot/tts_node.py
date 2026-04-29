"""
tts_node.py
-----------
Subscribes to /tts_response and speaks the text aloud using pyttsx3.
Runs on the Mac (outside Docker) since audio output lives on the host.
Or run inside the container redirecting audio via PulseAudio.

Topics subscribed:
  /tts_response   std_msgs/String   — text to speak
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False


class TTSNode(Node):

    def __init__(self):
        super().__init__('tts_node')

        if TTS_AVAILABLE:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 160)    # words per minute
            self.engine.setProperty('volume', 0.9)
        else:
            self.get_logger().warning('pyttsx3 not installed — TTS will print only')

        self.sub = self.create_subscription(
            String,
            '/tts_response',
            self.tts_callback,
            10
        )
        self.get_logger().info('TTS node ready')

    def tts_callback(self, msg: String):
        text = msg.data.strip()
        if not text:
            return
        self.get_logger().info(f'Speaking: "{text}"')
        if TTS_AVAILABLE:
            self.engine.say(text)
            self.engine.runAndWait()
        else:
            print(f'[ROBOT SAYS]: {text}')


def main(args=None):
    rclpy.init(args=args)
    node = TTSNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
