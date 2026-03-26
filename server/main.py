"""
Deer Detection Server
Main application - Flask server with WebSocket for real-time updates
"""

import logging
from logging.handlers import RotatingFileHandler
import time
from datetime import datetime
from enum import Enum
from collections import deque
from device_manager import get_device_manager
from flask import Flask, Response, jsonify, request
from flask_socketio import SocketIO, emit
import requests
import cv2
import numpy as np
import threading

from detection import DeerDetector
from valve_control_cloud import CloudValveController as ValveController
from detection_storage import get_detection_storage
from config import (
    SERVER_HOST,
    SERVER_PORT,
    ESP32_CAM_STREAM_URL,
    ACTIVE_WINDOW_SECONDS,
    SPRINKLER_DURATION_SECONDS,
    COOLDOWN_PERIOD_SECONDS,
    MAX_DETECTIONS_PER_SESSION,
    SAVE_CLASS_IDS,
    LOG_FILE,
    MAX_LOG_ENTRIES
)

# Configure smart logging with rotation
class SmartErrorFilter(logging.Filter):
    """Filter to reduce repetitive error spam"""
    def __init__(self):
        super().__init__()
        self.consecutive_errors = 0
        self.last_error_msg = None

    def filter(self, record):
        # Always allow non-ERROR messages
        if record.levelno != logging.ERROR:
            self.consecutive_errors = 0
            self.last_error_msg = None
            return True

        # Check for repetitive frame capture errors
        if "Frame capture error" in record.getMessage():
            if record.getMessage() == self.last_error_msg:
                self.consecutive_errors += 1
                # Log first error, then every 100th repetition
                if self.consecutive_errors == 1 or self.consecutive_errors % 100 == 0:
                    record.msg = f"{record.msg} [Error repeated {self.consecutive_errors} times]"
                    return True
                return False
            else:
                self.consecutive_errors = 1
                self.last_error_msg = record.getMessage()
                return True

        # Allow all other errors
        return True

# Set up logging with rotation (5MB per file, keep 4 backups = ~20MB max)
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5*1024*1024,  # 5MB per file
    backupCount=4          # Keep 4 backups (20MB total)
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
file_handler.addFilter(SmartErrorFilter())

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
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
        self.motion_active = False  # Real-time PIR sensor state

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
        self.last_frame_time = None  # Track when frames are received
        self.auto_detection_active = False  # Track if auto-detection is running

        # Start continuous frame capture (includes PIR status from stream headers)
        self._start_frame_capture()

        logger.info("System initialized successfully")

    def _start_frame_capture(self):
        """Start continuous frame capture from ESP32-CAM"""
        def capture_worker():
            logger.info("Starting continuous frame capture thread")
            connection_attempts = 0
            while True:
                try:
                    # Only skip connection if system is DISABLED (not IDLE)
                    # IDLE means waiting for motion, but camera can still be viewed
                    if self.state == SystemState.DISABLED:
                        time.sleep(1)
                        continue

                    connection_attempts += 1
                    # Only log every 10th connection attempt (reduce noise)
                    if connection_attempts == 1 or connection_attempts % 10 == 0:
                        logger.debug(f"Connecting to ESP32-CAM stream (attempt {connection_attempts})...")
                    stream = requests.get(ESP32_CAM_STREAM_URL, stream=True, timeout=10)
                    connection_attempts = 0  # Reset on successful connection
                    bytes_buffer = b''
                    frame_count = 0

                    for chunk in stream.iter_content(chunk_size=1024):
                        bytes_buffer += chunk

                        # Parse PIR status from multipart headers (before JPEG data)
                        pir_header_marker = b'X-PIR-Status: '
                        pir_pos = bytes_buffer.find(pir_header_marker)
                        if pir_pos != -1:
                            # Extract PIR status value (everything until \r\n)
                            status_start = pir_pos + len(pir_header_marker)
                            status_end = bytes_buffer.find(b'\r\n', status_start)
                            if status_end != -1:
                                pir_status = bytes_buffer[status_start:status_end].decode('utf-8').strip()
                                is_active = (pir_status == 'active')

                                # Update PIR status if changed
                                if self.motion_active != is_active:
                                    self.motion_active = is_active
                                    # Track last motion detection time
                                    if is_active:
                                        self.last_detection_time = datetime.now()
                                    socketio.emit('motion_status', {'active': is_active})
                                    logger.info(f"PIR: {'MOTION DETECTED' if is_active else 'no motion'}")

                        # Find JPEG boundaries
                        a = bytes_buffer.find(b'\xff\xd8')  # JPEG start
                        b = bytes_buffer.find(b'\xff\xd9')  # JPEG end

                        if a != -1 and b != -1:
                            jpg = bytes_buffer[a:b+2]
                            bytes_buffer = bytes_buffer[b+2:]

                            # Decode frame
                            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)

                            if frame is not None:
                                # Add date/time overlay BEFORE storing
                                # This ensures both live feed and saved gallery images have the timestamp
                                self._draw_timestamp(frame)
                                
                                # Re-encode to JPEG for the live feed (this puts the timestamp on the screen)
                                _, stamped_buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                                stamped_jpg = stamped_buffer.tobytes()

                                with self.frame_lock:
                                    self.current_frame = frame
                                    self.current_jpg = stamped_jpg

                                    # Auto-trigger detection when camera becomes active
                                    now = time.time()
                                    if self.last_frame_time is None:
                                        # Camera just woke up!
                                        logger.info("📷 ESP32-CAM stream active - AUTO-STARTING detection")
                                        self.stream_active = True
                                        socketio.emit('camera_status', {'active': True})
                                        # Auto-trigger motion detection
                                        if not self.auto_detection_active and self.enabled:
                                            self.auto_detection_active = True
                                            threading.Thread(target=self._auto_trigger_detection, daemon=True).start()

                                    self.last_frame_time = now

                                frame_count += 1

                                # Only log every 1000 frames (reduced noise)
                                if frame_count % 1000 == 0:
                                    logger.debug(f"Captured {frame_count} frames (streaming active)")

                except Exception as e:
                    logger.error(f"Frame capture error: {e}")
                    with self.frame_lock:
                        self.current_frame = None
                        self.current_jpg = None
                        # Mark camera as inactive
                        if self.stream_active:
                            logger.info("📷 ESP32-CAM went to sleep")
                            self.stream_active = False
                            self.last_frame_time = None
                            socketio.emit('camera_status', {'active': False})
                    time.sleep(5)  # Wait before reconnecting

        thread = threading.Thread(target=capture_worker, daemon=True)
        thread.start()

    def _draw_timestamp(self, frame):
        """Draw date/time overlay on the frame (bottom-left)"""
        timestamp = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        
        # Text settings
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.65
        thickness = 2
        color = (255, 255, 255) # White
        
        # Calculate text size for background box
        (text_width, text_height), baseline = cv2.getTextSize(timestamp, font, scale, thickness)
        
        # Position: Bottom-left
        x, y = 10, frame.shape[0] - 10
        
        # Draw semi-transparent background box for readability
        padding = 5
        cv2.rectangle(frame, (x - padding, y - text_height - padding), 
                      (x + text_width + padding, y + padding), (0, 0, 0), -1)
        
        # Draw text with anti-aliasing
        cv2.putText(frame, timestamp, (x, y), font, scale, color, thickness, cv2.LINE_AA)

    def _auto_trigger_detection(self):
        """Automatically trigger detection when camera wakes up"""
        try:
            # Small delay to ensure stream is stable
            time.sleep(1)

            logger.info("🎯 Auto-triggering detection session (ESP32-CAM active)")
            if self.trigger_motion():
                logger.info("✅ Auto-detection session started")
            else:
                logger.warning("⚠️ Auto-trigger ignored (system disabled or in cooldown)")
        except Exception as e:
            logger.error(f"Auto-trigger error: {e}")
        finally:
            self.auto_detection_active = False

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
                        self._handle_deer_detection(detections, annotated_frame)
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

    def _handle_deer_detection(self, detections, annotated_frame):
        """Handle target animal detection (deer, cow, sheep)"""
        animal_type = detections[0]['class']
        class_id = detections[0].get('class_id')

        # Only save deer, cow, sheep detections to gallery (not cats, dogs, etc.)
        if class_id in SAVE_CLASS_IDS:
            storage = get_detection_storage()
            saved_filename = storage.save_detection(annotated_frame, detections, animal_type)
            logger.info(f"📸 Detection image saved: {saved_filename} ({animal_type})")
        else:
            logger.info(f"ℹ️ Detection not saved: {animal_type} (class {class_id}) - not in save list")

        # Check if we've hit the max detections for this session
        if self.session_detections >= MAX_DETECTIONS_PER_SESSION:
            self.log_event('detection', f"{animal_type.capitalize()} detected but max activations reached ({MAX_DETECTIONS_PER_SESSION})")
            return

        # Check cooldown
        if self.cooldown_until and time.time() < self.cooldown_until:
            remaining = int(self.cooldown_until - time.time())
            self.log_event('detection', f"{animal_type.capitalize()} detected but in cooldown ({remaining}s remaining)")
            return

        # Activate sprinkler
        self.session_detections += 1
        self.last_detection_time = datetime.now()

        self.log_event('detection', f"{animal_type.capitalize()} detected! (confidence: {detections[0]['confidence']:.2f})", {
            'animal': animal_type,
            'detections': len(detections),
            'session_count': self.session_detections,
            'image': saved_filename
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
            'motion_active': self.motion_active,
            'valve_on': valve_status.get('is_on', False),
            'valve_configured': valve_status.get('configured', False),
            'valve_api_error': valve_status.get('api_error'),
            'session_active': self.session_start is not None,
            'session_detections': self.session_detections,
            'last_detection': self.last_detection_time.isoformat() if self.last_detection_time else None,
            'cooldown_remaining': max(0, int(self.cooldown_until - time.time())) if self.cooldown_until else 0,
            'camera_active': self.stream_active  # Add camera status
        }


# Initialize system
system = DeerDetectionSystem()

# Clean up old detection images (keep last 7 days)
try:
    storage = get_detection_storage()
    files_deleted, space_freed = storage.cleanup_old_detections(max_age_days=7)
    if files_deleted > 0:
        logger.info(f"Startup cleanup: Removed {files_deleted} old detection files ({space_freed:.2f} MB)")
except Exception as e:
    logger.warning(f"Startup cleanup failed: {e}")


# ===== Flask Routes =====

@app.route('/api/client_log', methods=['POST'])
def client_log():
    """Endpoint for client-side logging"""
    try:
        data = request.json
        level = data.get('level', 'info').lower()
        message = data.get('message', '')
        
        client_logger = logging.getLogger('client')
        if level == 'error':
            client_logger.error(f"Client Error: {message}")
        elif level == 'warning':
            client_logger.warning(f"Client Warning: {message}")
        else:
            client_logger.info(f"Client Log: {message}")
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

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


@app.route('/api/debug', methods=['POST'])
def api_debug():
    """Debug endpoint to receive GPIO state from ESP32"""
    try:
        data = request.json
        gpio = data.get('gpio')
        state = data.get('state')
        high = data.get('high')
        logger.info(f"ESP32 DEBUG: GPIO {gpio} = {state} (interpreted as: {'HIGH' if high else 'LOW'})")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Debug endpoint error: {e}")
        return jsonify({'success': False}), 500


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
    # Send initial camera status so UI knows if camera is active
    emit('camera_status', {'active': system.stream_active})


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
        response = {'success': True, 'devices': devices}
        if dm.last_error:
            response['api_error'] = dm.last_error
        return jsonify(response)
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
        response = {'success': success, 'devices': devices}
        if dm.last_error:
            response['api_error'] = dm.last_error
        return jsonify(response)
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


# ===== Detection Gallery Routes =====

@app.route('/detections')
def detections_page():
    """Serve the detection gallery page"""
    return app.send_static_file('detections.html')


@app.route('/api/detections', methods=['GET'])
def api_get_detections():
    """Get list of detection records"""
    try:
        storage = get_detection_storage()

        # Get pagination parameters
        limit = request.args.get('limit', type=int, default=50)
        offset = request.args.get('offset', type=int, default=0)

        # Get detections
        detections = storage.get_detections(limit=limit, offset=offset)
        stats = storage.get_detection_stats()

        return jsonify({
            'success': True,
            'detections': detections,
            'stats': stats,
            'limit': limit,
            'offset': offset
        })
    except Exception as e:
        logger.error(f"Error getting detections: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/detections/<filename>')
def api_get_detection_image(filename):
    """Serve a detection image"""
    try:
        from flask import send_from_directory
        storage = get_detection_storage()
        image_path = storage.get_detection_image_path(filename)

        if image_path.exists():
            detections_dir = str(image_path.parent)
            return send_from_directory(detections_dir, filename)
        else:
            return jsonify({'error': 'Image not found'}), 404
    except Exception as e:
        logger.error(f"Error serving image {filename}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/detections/delete', methods=['POST'])
def api_delete_detections():
    """Delete detections based on age filter"""
    try:
        data = request.json
        age_filter = data.get('filter', 'all')

        # Validate filter
        valid_filters = ['all', 'year', 'month', 'week', 'day', 'hour', '10min']
        if age_filter not in valid_filters:
            return jsonify({
                'success': False,
                'error': f'Invalid filter. Must be one of: {valid_filters}'
            }), 400

        storage = get_detection_storage()
        deleted_count = storage.delete_detections_by_age(age_filter)

        return jsonify({
            'success': True,
            'deleted': deleted_count,
            'message': f'Deleted {deleted_count} detection(s) (filter: {age_filter})'
        })
    except Exception as e:
        logger.error(f"Error deleting detections: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/detections/stats', methods=['GET'])
def api_detection_stats():
    """Get detection statistics"""
    try:
        storage = get_detection_storage()
        stats = storage.get_detection_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    logger.info(f"Starting server on {SERVER_HOST}:{SERVER_PORT}")
    logger.info(f"Web interface: http://192.168.1.15:{SERVER_PORT}")

    # Start the server
    socketio.run(app, host=SERVER_HOST, port=SERVER_PORT, debug=False, allow_unsafe_werkzeug=True)
