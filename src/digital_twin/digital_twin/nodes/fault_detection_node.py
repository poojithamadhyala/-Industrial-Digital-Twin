import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Float32, Bool
import json
import numpy as np
import threading
import time
import pickle
import os

class FaultDetectionNode(Node):
    def __init__(self):
        super().__init__('fault_detection')

        # Publishers
        self.anomaly_pub = self.create_publisher(
            Float32, '/fault/anomaly_score', 10)
        self.alert_pub = self.create_publisher(
            String, '/fault/alert', 10)
        self.prediction_pub = self.create_publisher(
            String, '/fault/prediction', 10)

        # Subscribers
        self.create_subscription(
            String, '/plc/state', self.state_callback, 10)

        # Data collection
        self._data_buffer = []
        self._training_data = []
        self._model = None
        self._is_trained = False
        self._sample_count = 0
        self._training_samples = 100

        # Simulated joint features
        self._current_features = [0.0] * 8

        # Thresholds
        self.WARN_THRESHOLD = 0.6
        self.CRITICAL_THRESHOLD = 0.85

        # Start training thread
        threading.Thread(
            target=self._training_loop, daemon=True).start()

        self.create_timer(1.0, self.run_inference)
        self.get_logger().info('Fault Detection Node started!')
        self.get_logger().info(
            f'Collecting {self._training_samples} samples for training...')

    def state_callback(self, msg):
        try:
            state = json.loads(msg.data)
            robot_state = state.get('robot_state', 'idle')
            conveyor = float(state.get('conveyor_run', False))
            fault = float(state.get('fault_code', 0))
            cycle = float(state.get('cycle_count', 0))

            # Map robot state to number
            state_map = {
                'idle': 0.0, 'pick': 1.0,
                'place': 2.0, 'home': 3.0, 'faulted': 4.0
            }
            state_num = state_map.get(robot_state, 0.0)

            # Simulate joint torque features based on state
            # In real system these come from actual joint sensors
            base_torques = {
                'idle':  [0.1, 0.2, 0.1, 0.1, 0.1, 0.1],
                'pick':  [0.6, 0.8, 0.7, 0.4, 0.3, 0.2],
                'place': [0.5, 0.7, 0.6, 0.5, 0.4, 0.2],
                'home':  [0.2, 0.3, 0.2, 0.2, 0.2, 0.1],
            }
            torques = base_torques.get(
                robot_state, [0.1] * 6)

            # Add small noise for realism
            noise = np.random.normal(0, 0.02, 6).tolist()
            noisy_torques = [t + n for t, n in zip(torques, noise)]

            self._current_features = noisy_torques + [state_num, conveyor]
            self._sample_count += 1

            # Collect training data during normal operation
            if not self._is_trained and fault == 0:
                self._training_data.append(self._current_features)

        except Exception as e:
            self.get_logger().error(f'State callback error: {e}')

    def _training_loop(self):
        while not self._is_trained:
            if len(self._training_data) >= self._training_samples:
                self._train_model()
            time.sleep(1.0)

    def _train_model(self):
        try:
            from sklearn.ensemble import IsolationForest
            self.get_logger().info('Training Isolation Forest model...')

            X = np.array(self._training_data)
            self._model = IsolationForest(
                contamination=0.1,
                random_state=42,
                n_estimators=100
            )
            self._model.fit(X)
            self._is_trained = True

            self.get_logger().info(
                f'Model trained on {len(self._training_data)} samples!')
            self.get_logger().info(
                'Predictive fault detection is now ACTIVE!')

            # Save model
            model_path = '/root/ros2_ws/fault_model.pkl'
            with open(model_path, 'wb') as f:
                pickle.dump(self._model, f)
            self.get_logger().info(f'Model saved to {model_path}')

        except Exception as e:
            self.get_logger().error(f'Training error: {e}')

    def run_inference(self):
        if not self._is_trained:
            remaining = self._training_samples - len(self._training_data)
            if remaining > 0 and remaining % 20 == 0:
                self.get_logger().info(
                    f'Collecting training data... {remaining} samples remaining')
            return

        try:
            features = np.array(self._current_features).reshape(1, -1)

            # Get anomaly score (-1 = anomaly, 1 = normal)
            raw_score = self._model.decision_function(features)[0]

            # Normalize to 0-1 range (1 = most anomalous)
            anomaly_score = max(0.0, min(1.0, (0.5 - raw_score)))

            # Publish score
            score_msg = Float32()
            score_msg.data = float(anomaly_score)
            self.anomaly_pub.publish(score_msg)

            # Generate alert based on threshold
            if anomaly_score >= self.CRITICAL_THRESHOLD:
                alert = {
                    "level": "CRITICAL",
                    "score": round(anomaly_score, 3),
                    "message": "Critical anomaly detected! Stopping arm.",
                    "action": "stop"
                }
                self.get_logger().error(
                    f'CRITICAL ANOMALY: score={anomaly_score:.3f}')

            elif anomaly_score >= self.WARN_THRESHOLD:
                alert = {
                    "level": "WARNING",
                    "score": round(anomaly_score, 3),
                    "message": "Anomaly detected. Slowing arm.",
                    "action": "slow"
                }
                self.get_logger().warn(
                    f'ANOMALY WARNING: score={anomaly_score:.3f}')

            else:
                alert = {
                    "level": "OK",
                    "score": round(anomaly_score, 3),
                    "message": "Normal operation",
                    "action": "none"
                }

            alert_msg = String()
            alert_msg.data = json.dumps(alert)
            self.alert_pub.publish(alert_msg)

            # Publish prediction
            prediction = {
                "anomaly_score": round(anomaly_score, 3),
                "status": alert["level"],
                "trained_samples": len(self._training_data),
                "features": [round(f, 3) for f in self._current_features]
            }
            pred_msg = String()
            pred_msg.data = json.dumps(prediction)
            self.prediction_pub.publish(pred_msg)

        except Exception as e:
            self.get_logger().error(f'Inference error: {e}')


def main(args=None):
    rclpy.init(args=args)
    node = FaultDetectionNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
