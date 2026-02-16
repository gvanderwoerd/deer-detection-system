"""
Deer Detection Server
Main application - Flask server with WebSocket for real-time updates
"""

import logging
import time
from datetime import datetime
from enum import Enum
from collections import deque
from device_manager import get_device_manager
from flask import Flask, render_template, Response, jsonify, request
from flask_socketio import SocketIO, emit
import requests
import cv2
import numpy as np
import threading

from detection import DeerDetector
from valve_control_cloud import CloudValveController as ValveController
from config import (
    SERVER_HOST,
    SERVER_PORT,
    ESP32_CAM_STREAM_URL,
    ACTIVE_WINDOW_SECONDS,
    SPRINKLER_DURATION_SECONDS,
    COOLDOWN_PERIOD_SECONDS,
    MAX_DETECTIONS_PER_SESSION,
    LOG_FILE,
    MAX_LOG_ENTRIES
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, static_folder='../web', static_url_path='')
app.config['SECRET_KEY'] = 'deer-detection-secret-key-change-me'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')


class SystemState(Enum):
    """System state machine"""
    DISABLED = "disabled"  # System manually disabled
    IDLE = "idle"  # Waiting for motion trigger
    ACTIVE = "active"  # Camera active, scanning for deer
    DEER_DETECTED = "deer_detected"  # Deer found, activating sprinkler
    SPRINKLER_ON = "sprinkler_on"  # Sprinkler running
    COOLDOWN = "cooldown"  # Cooling down between activations


class DeerDetectionSystem:
    """Main system coordinator"""

    def __init__(self):
        logger.info("Initializing Deer Detection System...")

        # Initialize components
        self.detector = DeerDetector()
        self.valve = ValveController()

        # System state
        self.state = SystemState.IDLE
        self.enabled = True

        # Session tracking
        self.session_start = None
        self.session_detections = 0
        self.last_detection_time = None
        self.cooldown_until = None

        # Event log
        self.event_log = deque(maxlen=MAX_LOG_ENTRIES)

        # Camera stream - shared frame buffer
        self.current_frame = None
        self.current_jpg = None  # Store JPEG bytes for streaming
        self.annotated_jpg = None  # Store annotated frame with detections
        self.stream_active = False
        self.stream_thread = None
        self.frame_lock = threading.Lock()
        self.show_detections = True  # Always show detection overlays

        # Start continuous frame capture
        self._start_frame_capture()

        logger.info("System initialized successfully")

    def _start_frame_capture(self):
        """Start continuous frame capture from ESP32-CAM"""
        def capture_worker():
            logger.info("Starting continuous frame capture thread")
            while True:
                try:
                    logger.info("Connecting to ESP32-CAM stream...")
                    stream = requests.get(ESP32_CAM_STREAM_URL, stream=True, timeout=10)
                    bytes_buffer = b''
                    frame_count = 0

                    for chunk in stream.iter_content(chunk_size=1024):
                        bytes_buffer += chunk
                        # Find JPEG boundaries
                        a = bytes_buffer.find(b'\xff\xd8')  # JPEG start
                        b = bytes_buffer.find(b'\xff\xd9')  # JPEG end

                        if a != -1 and b != -1:
                            jpg = bytes_buffer[a:b+2]
                            bytes_buffer = bytes_buffer[b+2:]

                            # Decode frame
                            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)

                            if frame is not None:
                                with self.frame_lock:
                                    self.current_frame = frame
                                    self.current_jpg = jpg
                                frame_count += 1

                                if frame_count % 100 == 0:
                                    logger.info(f"Captured {frame_count} frames")

                except Exception as e:
                    logger.error(f"Frame capture error: {e}")
                    with self.frame_lock:
                        self.current_frame = None
                        self.current_jpg = None
                    time.sleep(5)  # Wait before reconnecting

        thread = threading.Thread(target=capture_worker, daemon=True)
        thread.start()

    def log_event(self, event_type, message, data=None):
        """Log an event"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            'message': message,
            'data': data
        }
        self.event_log.append(event)
        logger.info(f"[{event_type}] {message}")

        # Broadcast to web clients
        socketio.emit('event', event)

    def change_state(self, new_state):
        """Change system state"""
        old_state = self.state
        self.state = new_state
        self.log_event('state_change', f"State: {old_state.value} → {new_state.value}")

        # Broadcast state change
        socketio.emit('state', {'state': new_state.value})

    def trigger_motion(self):
        """Handle motion detection trigger"""
        if not self.enabled:
            self.log_event('trigger', "Motion detected but system is disabled")
            return False

        if self.state == SystemState.COOLDOWN:
            self.log_event('trigger', "Motion detected during cooldown - ignoring")
            return False

        self.log_event('trigger', "Motion detected - activating camera")
        self.change_state(SystemState.ACTIVE)

        # Start new session
        self.session_start = time.time()
        self.session_detections = 0

        # Start monitoring
        self._start_detection_session()
        return True

    def _start_detection_session(self):
        """Start a detection session"""
        def session_worker():
            logger.info(f"Detection session started for {ACTIVE_WINDOW_SECONDS} seconds")

            start_time = time.time()
            frame_check_count = 0
            while time.time() - start_time < ACTIVE_WINDOW_SECONDS:
                if not self.enabled or self.state == SystemState.DISABLED:
                    logger.info("Session cancelled - system disabled")
                    break

                if self.state == SystemState.SPRINKLER_ON:
                    # Wait while sprinkler is active
                    time.sleep(1)
                    continue

                # Process frames from camera
                frame_check_count += 1
                with self.frame_lock:
                    frame = self.current_frame

                if frame is not None:
                    # Log every 20th frame check (every 10 seconds)
                    if frame_check_count % 20 == 0:
                        logger.info(f"Processing frame {frame_check_count}, frame shape: {frame.shape}")

                    deer_detected, detections, annotated_frame = self.detector.detect_deer(frame)

                    # Store annotated frame for display
                    if annotated_frame is not None:
                        _, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        with self.frame_lock:
                            self.annotated_jpg = buffer.tobytes()

                    if deer_detected:
                        self._handle_deer_detection(detections)
                else:
                    # Log when no frame is available
                    if frame_check_count % 20 == 0:
                        logger.warning(f"No frame available for detection (check #{frame_check_count})")

                time.sleep(0.5)  # Check twice per second

            # Session ended
            if self.state == SystemState.ACTIVE:
                logger.info("Detection session ended - no deer detected")
                self.change_state(SystemState.IDLE)

        thread = threading.Thread(target=session_worker, daemon=True)
        thread.start()

    def _handle_deer_detection(self, detections):
        """Handle target animal detection (deer, cow, sheep)"""
        # Check if we've hit the max detections for this session
        if self.session_detections >= MAX_DETECTIONS_PER_SESSION:
            animal_type = detections[0]['class']
            self.log_event('detection', f"{animal_type.capitalize()} detected but max activations reached ({MAX_DETECTIONS_PER_SESSION})")
            return

        # Check cooldown
        if self.cooldown_until and time.time() < self.cooldown_until:
            remaining = int(self.cooldown_until - time.time())
            animal_type = detections[0]['class']
            self.log_event('detection', f"{animal_type.capitalize()} detected but in cooldown ({remaining}s remaining)")
            return

        # Activate sprinkler
        self.session_detections += 1
        self.last_detection_time = datetime.now()
        animal_type = detections[0]['class']

        self.log_event('detection', f"{animal_type.capitalize()} detected! (confidence: {detections[0]['confidence']:.2f})", {
            'animal': animal_type,
            'detections': len(detections),
            'session_count': self.session_detections
        })

        self.change_state(SystemState.DEER_DETECTED)
        self._activate_sprinkler()

    def _activate_sprinkler(self):
        """Activate the sprinkler"""
        self.log_event('sprinkler', f"Activating sprinkler for {SPRINKLER_DURATION_SECONDS} seconds")
        self.change_state(SystemState.SPRINKLER_ON)

        # Turn on valve
        if self.valve.turn_on(duration=SPRINKLER_DURATION_SECONDS):
            # Wait for sprinkler to finish
            time.sleep(SPRINKLER_DURATION_SECONDS + 1)

            # Start cooldown
            self.cooldown_until = time.time() + COOLDOWN_PERIOD_SECONDS
            self.log_event('cooldown', f"Entering cooldown for {COOLDOWN_PERIOD_SECONDS} seconds")
            self.change_state(SystemState.COOLDOWN)

            # After cooldown, return to active
            time.sleep(COOLDOWN_PERIOD_SECONDS)
            if self.state == SystemState.COOLDOWN:
                self.change_state(SystemState.ACTIVE)
        else:
            self.log_event('error', "Failed to activate sprinkler")
            self.change_state(SystemState.ACTIVE)

    def enable_system(self):
        """Enable the system"""
        self.enabled = True
        self.change_state(SystemState.IDLE)
        self.log_event('system', "System enabled")

    def disable_system(self):
        """Disable the system"""
        self.enabled = False
        self.change_state(SystemState.DISABLED)
        self.log_event('system', "System disabled")

        # Turn off sprinkler if running
        if self.state == SystemState.SPRINKLER_ON:
            self.valve.turn_off()

    def emergency_stop(self):
        """Emergency stop - turn off sprinkler immediately"""
        self.log_event('emergency', "Emergency stop activated")
        self.valve.turn_off()

        if self.state in [SystemState.SPRINKLER_ON, SystemState.DEER_DETECTED]:
            self.change_state(SystemState.ACTIVE if self.enabled else SystemState.DISABLED)

    def get_status(self):
        """Get system status"""
        valve_status = self.valve.get_status()

        return {
            'state': self.state.value,
            'enabled': self.enabled,
            'valve_on': valve_status.get('is_on', False),
            'valve_configured': valve_status.get('configured', False),
            'session_active': self.session_start is not None,
            'session_detections': self.session_detections,
            'last_detection': self.last_detection_time.isoformat() if self.last_detection_time else None,
            'cooldown_remaining': max(0, int(self.cooldown_until - time.time())) if self.cooldown_until else 0
        }


# Initialize system
system = DeerDetectionSystem()


# ===== Flask Routes =====

@app.route('/')
def index():
    """Serve the web interface"""
    return app.send_static_file('index.html')


@app.route('/devices')
def devices_page():
    """Serve the devices management page"""
    return app.send_static_file('devices.html')


@app.route('/api/status')
def api_status():
    """Get system status"""
    return jsonify(system.get_status())


@app.route('/api/trigger', methods=['POST'])
def api_trigger():
    """Manual trigger (for testing)"""
    if system.trigger_motion():
        return jsonify({'success': True, 'message': 'Motion triggered'})
    else:
        return jsonify({'success': False, 'message': 'Trigger ignored'})


@app.route('/api/system/enable', methods=['POST'])
def api_enable():
    """Enable system"""
    system.enable_system()
    return jsonify({'success': True, 'message': 'System enabled'})


@app.route('/api/system/disable', methods=['POST'])
def api_disable():
    """Disable system"""
    system.disable_system()
    return jsonify({'success': True, 'message': 'System disabled'})


@app.route('/api/sprinkler/on', methods=['POST'])
def api_sprinkler_on():
    """Manually turn on sprinkler"""
    duration = request.json.get('duration', 10) if request.json else 10
    system.log_event('manual', f"Manual sprinkler activation ({duration}s)")

    if system.valve.turn_on(duration=duration):
        return jsonify({'success': True, 'message': f'Sprinkler on for {duration}s'})
    else:
        return jsonify({'success': False, 'message': 'Failed to activate sprinkler'})


@app.route('/api/sprinkler/off', methods=['POST'])
def api_sprinkler_off():
    """Emergency shutoff"""
    system.emergency_stop()
    return jsonify({'success': True, 'message': 'Sprinkler turned off'})


@app.route('/api/logs')
def api_logs():
    """Get recent event logs"""
    return jsonify(list(system.event_log))


def generate_frames():
    """Generate frames from shared buffer for streaming"""
    logger.info("Client connected to video feed")
    last_jpg = None

    while True:
        try:
            with system.frame_lock:
                # Use annotated frame if available (shows detections), otherwise raw frame
                jpg = system.annotated_jpg if system.annotated_jpg is not None else system.current_jpg

            if jpg is not None and jpg != last_jpg:
                last_jpg = jpg
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n')
            else:
                time.sleep(0.033)  # ~30 FPS

        except Exception as e:
            logger.error(f"Error streaming frame: {e}")
            time.sleep(1)


@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# ===== WebSocket Events =====

@socketio.on('connect')
def handle_connect():
    """Client connected"""
    logger.info("Client connected")
    emit('status', system.get_status())


@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnected"""
    logger.info("Client disconnected")


# ===== Main Entry Point =====



# ============================================================================
# DEVICE MANAGEMENT API ROUTES
# ============================================================================

@app.route('/api/devices', methods=['GET'])
def get_devices():
    """Get all SmartLife devices"""
    try:
        dm = get_device_manager()
        devices = dm.get_all_devices()
        return jsonify({'success': True, 'devices': devices})
    except Exception as e:
        logger.error(f"Error getting devices: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/devices/refresh', methods=['POST'])
def refresh_devices():
    """Refresh device list from SmartLife"""
    try:
        dm = get_device_manager()
        success = dm.refresh_devices()
        devices = dm.get_all_devices()
        return jsonify({'success': success, 'devices': devices})
    except Exception as e:
        logger.error(f"Error refreshing devices: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/device/<device_id>/on', methods=['POST'])
def turn_device_on(device_id):
    """Turn specific device ON"""
    try:
        duration = request.json.get('duration', 0) if request.is_json else 0
        dm = get_device_manager()
        success = dm.turn_on(device_id, duration=duration)
        
        socketio.emit('device_update', {
            'device_id': device_id,
            'action': 'turned_on'
        })
        
        return jsonify({'success': success})
    except Exception as e:
        logger.error(f"Error turning on device {device_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/device/<device_id>/off', methods=['POST'])
def turn_device_off(device_id):
    """Turn specific device OFF"""
    try:
        dm = get_device_manager()
        success = dm.turn_off(device_id)
        
        socketio.emit('device_update', {
            'device_id': device_id,
            'action': 'turned_off'
        })
        
        return jsonify({'success': success})
    except Exception as e:
        logger.error(f"Error turning off device {device_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/device/<device_id>/test', methods=['POST'])
def test_device(device_id):
    """Test device with 10-second run"""
    try:
        dm = get_device_manager()
        success = dm.test_device(device_id, duration=10)
        
        socketio.emit('log_event', {
            'message': f'Testing device (10 seconds)',
            'device_id': device_id
        })
        
        return jsonify({'success': success})
    except Exception as e:
        logger.error(f"Error testing device {device_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/devices/emergency_stop', methods=['POST'])
def emergency_stop_all_devices():
    """Emergency stop - turn off ALL devices"""
    try:
        dm = get_device_manager()
        results = dm.emergency_stop_all()
        
        socketio.emit('log_event', {
            'message': '🚨 EMERGENCY STOP - All devices turned off',
            'level': 'warning'
        })
        
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        logger.error(f"Error in emergency stop: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    logger.info(f"Starting server on {SERVER_HOST}:{SERVER_PORT}")
    logger.info(f"Web interface: http://192.168.1.15:{SERVER_PORT}")

    # Start the server
    socketio.run(app, host=SERVER_HOST, port=SERVER_PORT, debug=False, allow_unsafe_werkzeug=True)
