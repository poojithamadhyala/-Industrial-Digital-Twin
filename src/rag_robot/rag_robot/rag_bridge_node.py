"""
rag_bridge_node.py
------------------
Subscribes to /voice_command (raw text from Whisper STT).
Calls the RAG pipeline + Ollama LLM to get a structured JSON command.
Dispatches the command to Nav2 (navigation) or publishes a TTS response.

Topics subscribed:
  /voice_command   std_msgs/String   — raw transcript from STT node

Topics published:
  /tts_response    std_msgs/String   — text for the TTS node to speak
  /cmd_status      std_msgs/String   — human-readable status updates

Actions called:
  /navigate_to_pose   nav2_msgs/action/NavigateToPose
"""

import json
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose

import requests  # calls Ollama REST API


# ── Semantic map: location names → (x, y) in the Gazebo world ──────────────
LOCATION_MAP = {
    "bin_a":        (1.0,  2.0),
    "bin_b":        (3.0,  0.5),
    "inspection":   (0.0, -1.5),
    "home":         (0.0,  0.0),
    "charging":     (-2.0, 0.0),
}

OLLAMA_URL  = "http://host.docker.internal:11434/api/generate"
OLLAMA_MODEL = "llama3.1"

# System prompt forces JSON-only output
SYSTEM_PROMPT = """
You are the command parser for a voice-controlled robot.
The user will give you a voice command and some retrieved context from a knowledge base.
You MUST respond with ONLY a valid JSON object — no prose, no explanation, no markdown.

JSON schema:
{
  "action":     "navigate" | "speak" | "stop" | "unknown",
  "target":     "<location name from map, or null>",
  "message":    "<what the robot should say out loud, or null>",
  "confidence": <float 0.0–1.0>,
  "reason":     "<one sentence explaining your decision>"
}

Known locations: bin_a, bin_b, inspection, home, charging.
If the command is unclear or confidence < 0.6, set action to "speak" and ask for clarification.
"""


class RAGBridgeNode(Node):

    def __init__(self):
        super().__init__('rag_bridge_node')

        # Subscriber — receives raw voice transcript
        self.voice_sub = self.create_subscription(
            String,
            '/voice_command',
            self.voice_callback,
            10
        )

        # Publishers
        self.tts_pub    = self.create_publisher(String, '/tts_response', 10)
        self.status_pub = self.create_publisher(String, '/cmd_status',   10)

        # Nav2 action client
        self.nav_client = ActionClient(self, NavigateToPose, '/navigate_to_pose')

        self.get_logger().info('RAG bridge node started — waiting for voice commands...')

    # ── Main callback ────────────────────────────────────────────────────────

    def voice_callback(self, msg: String):
        transcript = msg.data.strip()
        if not transcript:
            return

        self.get_logger().info(f'Heard: "{transcript}"')
        self.publish_status(f'Processing: "{transcript}"')

        # Step 1 — RAG retrieval (stub — replace with real ChromaDB call)
        context = self.retrieve_context(transcript)

        # Step 2 — LLM reasoning
        command = self.call_llm(transcript, context)
        if command is None:
            self.speak("Sorry, I couldn't understand that command.")
            return

        self.get_logger().info(f'Command parsed: {json.dumps(command, indent=2)}')

        # Step 3 — Dispatch
        action     = command.get("action", "unknown")
        target     = command.get("target")
        message    = command.get("message")
        confidence = command.get("confidence", 0.0)

        if confidence < 0.6:
            self.speak(message or "I'm not sure what you mean. Could you repeat that?")
            return

        if action == "navigate" and target:
            self.navigate_to(target)

        elif action == "speak":
            self.speak(message or "Okay.")

        elif action == "stop":
            self.speak("Stopping now.")
            self.publish_status("STOP command received")

        else:
            self.speak("I don't know how to do that yet.")

    # ── RAG retrieval stub ───────────────────────────────────────────────────

    def retrieve_context(self, query: str) -> str:
        """
        Stub — replace this with a real ChromaDB query.
        Example real implementation:
            import chromadb
            client = chromadb.HttpClient(host='localhost', port=8000)
            col = client.get_collection('robot_docs')
            results = col.query(query_texts=[query], n_results=3)
            return '\n'.join(results['documents'][0])
        """
        # Hardcoded context for testing without ChromaDB running
        return (
            "bin_a is at position x=1.0, y=2.0. Used for rejected parts.\n"
            "bin_b is at position x=3.0, y=0.5. Used for approved parts.\n"
            "inspection station is at x=0.0, y=-1.5. Parts are checked here first.\n"
            "Always navigate slowly near the inspection station."
        )

    # ── LLM call ─────────────────────────────────────────────────────────────

    def call_llm(self, transcript: str, context: str) -> dict | None:
        prompt = (
            f"Context from knowledge base:\n{context}\n\n"
            f"Voice command: {transcript}\n\n"
            "Respond with the JSON command object only."
        )
        try:
            response = requests.post(OLLAMA_URL, json={
                "model":  OLLAMA_MODEL,
                "prompt": prompt,
                "system": SYSTEM_PROMPT,
                "stream": False,
            }, timeout=30)
            response.raise_for_status()
            raw = response.json().get("response", "").strip()
            # Strip accidental markdown fences
            raw = raw.replace("```json", "").replace("```", "").strip()
            return json.loads(raw)
        except requests.exceptions.ConnectionError:
            self.get_logger().error("Ollama not reachable — is it running on port 11434?")
            return None
        except json.JSONDecodeError as e:
            self.get_logger().error(f"LLM returned invalid JSON: {e}")
            return None
        except Exception as e:
            self.get_logger().error(f"LLM call failed: {e}")
            return None

    # ── Nav2 navigation ───────────────────────────────────────────────────────

    def navigate_to(self, target: str):
        coords = LOCATION_MAP.get(target.lower().replace(" ", "_"))
        if coords is None:
            self.speak(f"I don't know where {target} is.")
            return

        x, y = coords
        self.speak(f"Navigating to {target}.")
        self.publish_status(f"Navigating to {target} at ({x}, {y})")

        if not self.nav_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("Nav2 action server not available")
            self.speak("Navigation system is not ready.")
            return

        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = float(x)
        goal.pose.pose.position.y = float(y)
        goal.pose.pose.orientation.w = 1.0  # facing forward

        future = self.nav_client.send_goal_async(goal)
        future.add_done_callback(self.nav_goal_response_callback)

    def nav_goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warning("Nav2 rejected the goal")
            self.speak("Navigation goal was rejected.")
            return
        self.get_logger().info("Nav2 accepted the goal — robot is moving")
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.nav_result_callback)

    def nav_result_callback(self, future):
        self.get_logger().info("Navigation complete")
        self.speak("I have arrived at the destination.")
        self.publish_status("Navigation complete")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def speak(self, text: str):
        self.get_logger().info(f'TTS: "{text}"')
        msg = String()
        msg.data = text
        self.tts_pub.publish(msg)

    def publish_status(self, text: str):
        msg = String()
        msg.data = text
        self.status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = RAGBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
