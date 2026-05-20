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
import cv2
import threading

from detection import DeerDetector
from valve_control_cloud import CloudValveController as ValveController
from detection_storage import get_detection_storage
from model_recommendation import get_model_recommendation_api
from activation_metrics import get_metrics as get_activation_metrics
from api_usage_tracker import get_tracker as get_api_tracker
from camera_manager import get_camera_manager
from config import (
    SERVER_HOST,
    SERVER_PORT,
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

        # Initialize camera manager (multi-camera support)
        self.camera_manager = get_camera_manager()

        # System state
        self.state = SystemState.IDLE
        self.enabled = True
        self.motion_active = False  # Real-time PIR sensor state (from first camera)
        self.wifi_signal = None  # WiFi signal strength (RSSI in dBm) (from first camera)

        # Session tracking
        self.session_start = None
        self.session_detections = 0
        self.last_detection_time = None
        self.cooldown_until = None

        # Event log
        self.event_log = deque(maxlen=MAX_LOG_ENTRIES)

        # Camera stream - shared frame buffer (for backward compatibility, use first camera)
        self.current_frame = None
        self.current_jpg = None  # Store JPEG bytes for streaming
        self.annotated_jpg = None  # Store annotated frame with detections
        self.stream_active = False
        self.stream_thread = None
        self.frame_lock = threading.Lock()
        self.show_detections = True  # Always show detection overlays
        self.last_frame_time = None  # Track when frames are received
        self.auto_detection_active = False  # Track if auto-detection is running

        # Legacy frame capture for backward compatibility (uses first camera)
        # Note: Multi-camera support uses CameraManager for per-camera capture
        self._start_frame_capture()

        logger.info("System initialized successfully")

    def _start_frame_capture(self):
        """
        Start continuous frame capture from CameraManager (first camera for backward compatibility)

        Note: In multi-camera mode, each camera has its own capture thread in CameraManager.
        This legacy method pulls frames from the first available camera for backward compatibility.
        """
        def capture_worker():
            logger.info("Starting legacy frame capture thread (using first camera from CameraManager)")
            while True:
                try:
                    # Only skip if system is DISABLED
                    if self.state == SystemState.DISABLED:
                        time.sleep(1)
                        continue

                    # Get first available camera from CameraManager
                    cameras = self.camera_manager.get_all_cameras()
                    if not cameras:
                        logger.warning("No cameras available in CameraManager")
                        time.sleep(5)
                        continue

                    first_camera_id = cameras[0]['id']
                    camera = self.camera_manager.get_camera(first_camera_id)

                    if not camera or not camera.current_jpg:
                        time.sleep(0.1)  # Wait for first frame
                        continue

                    # Pull frame from first camera
                    with camera.frame_lock:
                        frame = camera.current_frame
                        jpg = camera.current_jpg

                    if frame is None:
                        time.sleep(0.1)
                        continue

                    # Copy PIR and WiFi status from camera, trigger per-camera detection
                    if camera.motion_active != self.motion_active:
                        self.motion_active = camera.motion_active
                        if camera.motion_active:
                            self.last_detection_time = datetime.now()
                            logger.info(f"🎯 PIR: MOTION DETECTED on {camera.name} - Auto-triggering detection")
                            # Trigger per-camera detection
                            if camera.trigger_detection():
                                logger.info(f"✅ [{camera.name}] Detection session started via PIR")
                        socketio.emit('motion_status', {'camera_id': camera.id, 'active': camera.motion_active})
                        logger.info(f"PIR: {'MOTION DETECTED' if camera.motion_active else 'no motion'}")

                    if camera.wifi_signal and camera.wifi_signal != self.wifi_signal:
                        self.wifi_signal = camera.wifi_signal

                    # Add timestamp overlay
                    self._draw_timestamp(frame)
                    _, stamped_buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    stamped_jpg = stamped_buffer.tobytes()

                    with self.frame_lock:
                        self.current_frame = frame
                        self.current_jpg = stamped_jpg

                        # Auto-trigger when camera becomes active
                        now = time.time()
                        if self.last_frame_time is None:
                            logger.info(f"📷 Camera stream active ({camera.name})")
                            self.stream_active = True
                            socketio.emit('camera_status', {'active': True})
                            if not self.auto_detection_active and self.enabled:
                                self.auto_detection_active = True
                                threading.Thread(target=self._auto_trigger_detection, daemon=True).start()

                        self.last_frame_time = now

                except Exception as e:
                    logger.error(f"Frame capture error: {e}")
                    with self.frame_lock:
                        self.current_frame = None
                        self.current_jpg = None
                        if self.stream_active:
                            logger.info("📷 Camera stream inactive")
                            self.stream_active = False
                            self.last_frame_time = None
                            socketio.emit('camera_status', {'active': False})
                    time.sleep(1)

        thread = threading.Thread(target=capture_worker, daemon=True, name="LegacyFrameCapture")
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

        # Broadcast health status update on state change
        try:
            dm = get_device_manager()
            metrics = get_activation_metrics()
            tracker = get_api_tracker()
            socketio.emit('health_update', {
                'credentials_valid': dm.credentials_valid,
                'activation_health': metrics.get_health_summary(),
                'api_quota': tracker.get_stats()['this_month']['quota_usage_pct']
            })
        except Exception as e:
            logger.debug(f"Failed to emit health update: {e}")

    def trigger_motion(self):
        """Handle motion detection trigger"""
        if not self.enabled:
            self.log_event('trigger', "Motion detected but system is disabled")
            return False

        if self.state == SystemState.COOLDOWN:
            self.log_event('trigger', "Motion detected during cooldown - ignoring")
            return False

        # Skip if already in active state (don't restart session)
        if self.state == SystemState.ACTIVE:
            logger.debug("Motion detected but already in active state - continuing current session")
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
        """
        DEPRECATED: Detection sessions are now handled per-camera by CameraManager
        This method is kept for backward compatibility but does nothing.
        Per-camera detection is triggered automatically via PIR motion or manual /api/trigger
        """
        logger.debug("_start_detection_session called (deprecated - using per-camera detection instead)")
        return

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

                    # Handle any detections (animals or people)
                    if detections:
                        self._handle_detection(detections, annotated_frame, deer_detected)
                else:
                    # Log when no frame is available (only occasionally to reduce spam)
                    if frame_check_count % 100 == 0:
                        logger.warning(f"No frame available for detection (check #{frame_check_count})")

                time.sleep(0.5)  # Check twice per second

            # Session ended
            if self.state == SystemState.ACTIVE:
                logger.info("Detection session ended - no deer detected")
                self.change_state(SystemState.IDLE)

        thread = threading.Thread(target=session_worker, daemon=True)
        thread.start()

    def _handle_detection(self, detections, annotated_frame, should_activate_sprinkler):
        """Handle detection (animals or people)"""
        animal_type = detections[0]['class']
        class_id = detections[0].get('class_id')

        # Determine camera (use first camera for now, will be enhanced for multi-camera)
        cameras = self.camera_manager.get_all_cameras()
        camera_id = cameras[0]['id'] if cameras else 'camera-default'

        saved_filename = None

        # Save to gallery if in save list (deer, cow, sheep, person)
        if class_id in SAVE_CLASS_IDS:
            storage = get_detection_storage()
            saved_filename = storage.save_detection(camera_id, annotated_frame, detections, animal_type)
            logger.info(f"📸 Detection image saved: {camera_id}/{saved_filename} ({animal_type})")
        else:
            logger.info(f"ℹ️ Detection not saved: {animal_type} (class {class_id}) - not in save list")

        # Only activate sprinkler for animals (not people)
        if not should_activate_sprinkler:
            logger.info(f"ℹ️ Sprinkler activation blocked (person present or non-target animal)")
            return

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
            'image': saved_filename,
            'camera': camera_id
        })

        self.change_state(SystemState.DEER_DETECTED)
        self._activate_sprinkler()

    def _activate_sprinkler(self):
        """Activate the sprinkler"""
        self.log_event('sprinkler', f"Activating sprinkler for {SPRINKLER_DURATION_SECONDS} seconds")
        self.change_state(SystemState.SPRINKLER_ON)

        # Turn on valve
        result = self.valve.turn_on(duration=SPRINKLER_DURATION_SECONDS)

        # Handle both dict return (new) and bool return (legacy)
        success = result.get('success') if isinstance(result, dict) else result
        verified = result.get('verified', False) if isinstance(result, dict) else False
        latency_ms = result.get('latency_ms', 0) if isinstance(result, dict) else 0
        error_msg = result.get('error') if isinstance(result, dict) else None

        # Record activation metrics
        try:
            metrics = get_activation_metrics()
            metrics.record_activation(success=success, verified=verified,
                                    error=error_msg, latency_ms=latency_ms)
        except Exception as e:
            logger.debug(f"Failed to record metrics: {e}")

        if success:
            # Log verification status
            if verified:
                self.log_event('sprinkler', f"✓ Sprinkler activated and verified ({latency_ms:.0f}ms)")
            else:
                self.log_event('sprinkler', f"⚠ Sprinkler command sent but could not verify ({latency_ms:.0f}ms)")

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
            error_display = error_msg if error_msg else 'Unknown error'
            self.log_event('error', f"Failed to activate sprinkler: {error_display}")
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
            'wifi_signal': self.wifi_signal,  # WiFi RSSI in dBm
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


@app.route('/cameras')
def cameras_page():
    """Serve the camera management page"""
    return app.send_static_file('cameras.html')


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
    """Manual trigger - supports per-camera triggering"""
    data = request.get_json() or {}
    camera_id = data.get('camera_id')

    if camera_id:
        # Per-camera trigger
        cm = get_camera_manager()
        camera = cm.get_camera(camera_id)
        if not camera:
            return jsonify({'success': False, 'error': 'Camera not found'}), 404

        if camera.trigger_detection():
            return jsonify({'success': True, 'message': f'Detection triggered for {camera.name}'})
        else:
            return jsonify({'success': False, 'message': 'Trigger ignored - in cooldown or already active'})
    else:
        # Legacy: trigger default camera (for backward compatibility)
        cm = get_camera_manager()
        cameras = cm.get_all_cameras()
        if cameras:
            camera_id = cameras[0]['id']
            camera = cm.get_camera(camera_id)
            if camera and camera.trigger_detection():
                return jsonify({'success': True, 'message': f'Detection triggered for {camera.name}'})

        return jsonify({'success': False, 'message': 'No camera available or trigger ignored'})


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


@app.route('/api/cameras/<camera_id>/trigger', methods=['POST'])
def api_trigger_camera(camera_id):
    """Trigger detection session for a specific camera"""
    cm = get_camera_manager()
    camera = cm.get_camera(camera_id)

    if not camera:
        return jsonify({'success': False, 'error': 'Camera not found'}), 404

    if camera.trigger_detection():
        logger.info(f"✅ Manual trigger: Detection session started for {camera.name}")
        return jsonify({'success': True, 'message': f'Detection triggered for {camera.name}'})
    else:
        return jsonify({'success': False, 'message': 'Trigger ignored - in cooldown or already active'})


@app.route('/api/cameras/<camera_id>/detection/status', methods=['GET'])
def api_camera_detection_status(camera_id):
    """Get detection session status for a camera"""
    cm = get_camera_manager()
    camera = cm.get_camera(camera_id)

    if not camera:
        return jsonify({'success': False, 'error': 'Camera not found'}), 404

    response = {
        'success': True,
        'camera_id': camera_id,
        'camera_name': camera.name,
        'session_active': camera.session_active,
        'session_detections': camera.session_detections,
        'active_window_seconds': camera.timing['active_window_seconds'],
        'cooldown_period_seconds': camera.timing['cooldown_period_seconds'],
        'last_detection': camera.last_detection,
        'motion_active': camera.motion_active,
        'wifi_signal': camera.wifi_signal
    }

    # Add device assignment durations
    device_durations = [assignment['duration_seconds'] for assignment in camera.device_assignments]
    response['device_durations'] = device_durations

    # Calculate session elapsed time if active
    if camera.session_active and camera.session_start:
        elapsed = time.time() - camera.session_start
        remaining = max(0, camera.timing['active_window_seconds'] - elapsed)
        response['session_elapsed_seconds'] = elapsed
        response['session_remaining_seconds'] = remaining
    else:
        response['session_elapsed_seconds'] = 0

    # Calculate cooldown remaining time
    if camera.cooldown_until:
        now = time.time()
        cooldown_remaining = max(0, camera.cooldown_until - now)
        response['cooldown_remaining'] = cooldown_remaining
    else:
        response['cooldown_remaining'] = 0

    # Calculate device remaining time
    if camera.device_activated_at and camera.device_duration:
        now = time.time()
        device_remaining = max(0, camera.device_activated_at + camera.device_duration - now)
        response['device_remaining'] = device_remaining
    else:
        response['device_remaining'] = 0

    return jsonify(response)


@app.route('/api/sprinkler/on', methods=['POST'])
def api_sprinkler_on():
    """Manually turn on sprinkler"""
    duration = request.json.get('duration', 10) if request.json else 10
    system.log_event('manual', f"Manual sprinkler activation ({duration}s)")

    result = system.valve.turn_on(duration=duration)

    # Handle both dict return (new) and bool return (legacy)
    success = result.get('success') if isinstance(result, dict) else result
    verified = result.get('verified', False) if isinstance(result, dict) else False

    if success:
        return jsonify({
            'success': True,
            'message': f'Sprinkler on for {duration}s',
            'verified': verified,
            'device': result.get('device_name') if isinstance(result, dict) else 'Unknown'
        })
    else:
        error_msg = result.get('error', 'Unknown error') if isinstance(result, dict) else 'Failed to activate sprinkler'
        return jsonify({
            'success': False,
            'message': f'Failed to activate sprinkler: {error_msg}'
        })


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
    """Video streaming route (legacy - uses first camera for backward compatibility)"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/video_feed/<camera_id>')
def video_feed_camera(camera_id):
    """Per-camera video streaming route"""
    cm = get_camera_manager()
    camera = cm.get_camera(camera_id)

    if not camera:
        return jsonify({'error': 'Camera not found'}), 404

    def generate_frames_for_camera(cam):
        """Generate frames from specific camera"""
        logger.info(f"Client connected to video feed for {cam.name}")
        last_jpg = None

        while True:
            try:
                with cam.frame_lock:
                    jpg = cam.annotated_jpg if cam.annotated_jpg is not None else cam.current_jpg

                if jpg is not None and jpg != last_jpg:
                    last_jpg = jpg
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n')
                else:
                    time.sleep(0.033)  # ~30 FPS

            except Exception as e:
                logger.error(f"Error streaming frame from {cam.name}: {e}")
                time.sleep(1)

    return Response(generate_frames_for_camera(camera),
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
# CAMERA MANAGEMENT API ROUTES
# ============================================================================

@app.route('/api/cameras', methods=['GET'])
def api_get_cameras():
    """Get all cameras"""
    try:
        cm = get_camera_manager()
        cameras = cm.get_all_cameras()
        return jsonify({'success': True, 'cameras': cameras})
    except Exception as e:
        logger.error(f"Error getting cameras: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cameras', methods=['POST'])
def api_register_camera():
    """Register a new camera"""
    try:
        data = request.json
        cm = get_camera_manager()

        # Validate required fields
        required = ['name', 'hostname', 'stream_url']
        if not all(f in data for f in required):
            return jsonify({'success': False, 'error': f'Missing required fields: {required}'}), 400

        # Register camera
        camera_id = cm.register_camera(
            name=data['name'],
            hostname=data['hostname'],
            stream_url=data['stream_url']
        )

        if camera_id:
            logger.info(f"✅ Camera registered: {camera_id} ({data['name']})")
            return jsonify({'success': True, 'camera_id': camera_id}), 201
        else:
            return jsonify({'success': False, 'error': 'Failed to register camera'}), 500
    except Exception as e:
        logger.error(f"Error registering camera: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cameras/<camera_id>', methods=['GET'])
def api_get_camera(camera_id):
    """Get camera details"""
    try:
        cm = get_camera_manager()
        camera = cm.get_camera(camera_id)

        if not camera:
            return jsonify({'success': False, 'error': 'Camera not found'}), 404

        return jsonify({'success': True, 'camera': camera.to_dict()})
    except Exception as e:
        logger.error(f"Error getting camera: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cameras/<camera_id>', methods=['PUT'])
def api_update_camera(camera_id):
    """Update camera configuration"""
    try:
        cm = get_camera_manager()
        data = request.json

        if cm.update_camera(camera_id, data):
            logger.info(f"✅ Camera updated: {camera_id}")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Camera not found'}), 404
    except Exception as e:
        logger.error(f"Error updating camera: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cameras/<camera_id>', methods=['DELETE'])
def api_delete_camera(camera_id):
    """Delete a camera"""
    try:
        cm = get_camera_manager()

        if cm.delete_camera(camera_id):
            logger.info(f"🗑️  Camera deleted: {camera_id}")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Camera not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting camera: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cameras/<camera_id>/test', methods=['POST'])
def api_test_camera(camera_id):
    """Test camera connection"""
    try:
        cm = get_camera_manager()
        success, result = cm.test_camera_connection(camera_id)

        if success:
            logger.info(f"✅ Camera test successful: {camera_id}")
            return jsonify({'success': True, 'result': result})
        else:
            logger.warning(f"⚠️  Camera test failed: {camera_id}")
            return jsonify({'success': False, 'error': result.get('error', 'Connection failed')}), 500
    except Exception as e:
        logger.error(f"Error testing camera: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cameras/<camera_id>/enable', methods=['POST'])
def api_enable_camera(camera_id):
    """Enable a camera"""
    try:
        cm = get_camera_manager()
        camera = cm.get_camera(camera_id)

        if not camera:
            return jsonify({'success': False, 'error': 'Camera not found'}), 404

        # Update enabled status
        if cm.update_camera(camera_id, {'enabled': True}):
            logger.info(f"✅ Camera enabled: {camera_id}")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to enable camera'}), 500
    except Exception as e:
        logger.error(f"Error enabling camera: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cameras/<camera_id>/disable', methods=['POST'])
def api_disable_camera(camera_id):
    """Disable a camera"""
    try:
        cm = get_camera_manager()
        camera = cm.get_camera(camera_id)

        if not camera:
            return jsonify({'success': False, 'error': 'Camera not found'}), 404

        # Update enabled status
        if cm.update_camera(camera_id, {'enabled': False}):
            logger.info(f"⏸️  Camera disabled: {camera_id}")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to disable camera'}), 500
    except Exception as e:
        logger.error(f"Error disabling camera: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


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
        result = dm.turn_on(device_id, duration=duration)

        # Handle both dict return (new) and bool return (legacy)
        success = result.get('success') if isinstance(result, dict) else result

        socketio.emit('device_update', {
            'device_id': device_id,
            'action': 'turned_on',
            'verified': result.get('verified', False) if isinstance(result, dict) else False
        })

        return jsonify({
            'success': success,
            'verified': result.get('verified', False) if isinstance(result, dict) else False,
            'device': result.get('device_name') if isinstance(result, dict) else 'Unknown'
        })
    except Exception as e:
        logger.error(f"Error turning on device {device_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/device/<device_id>/off', methods=['POST'])
def turn_device_off(device_id):
    """Turn specific device OFF"""
    try:
        dm = get_device_manager()
        result = dm.turn_off(device_id)

        # Handle both dict return (new) and bool return (legacy)
        success = result.get('success') if isinstance(result, dict) else result

        socketio.emit('device_update', {
            'device_id': device_id,
            'action': 'turned_off',
            'verified': result.get('verified', False) if isinstance(result, dict) else False
        })

        return jsonify({
            'success': success,
            'verified': result.get('verified', False) if isinstance(result, dict) else False,
            'device': result.get('device_name') if isinstance(result, dict) else 'Unknown'
        })
    except Exception as e:
        logger.error(f"Error turning off device {device_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/device/<device_id>/test', methods=['POST'])
def test_device(device_id):
    """Test device with 10-second run"""
    try:
        dm = get_device_manager()
        result = dm.test_device(device_id, duration=10)
        success = result.get('success') if isinstance(result, dict) else result

        socketio.emit('log_event', {
            'message': f'Testing device (10 seconds)',
            'device_id': device_id,
            'verified': result.get('verified', False) if isinstance(result, dict) else False
        })

        return jsonify({
            'success': success,
            'verified': result.get('verified', False) if isinstance(result, dict) else False,
            'device': result.get('device_name') if isinstance(result, dict) else 'Unknown'
        })
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
    """Get list of detection records (supports per-camera and legacy)"""
    try:
        storage = get_detection_storage()

        # Get pagination parameters
        limit = request.args.get('limit', type=int, default=50)
        offset = request.args.get('offset', type=int, default=0)
        camera_id = request.args.get('camera_id', default=None)  # Optional: specific camera

        # Get detections (camera_id=None returns legacy detections)
        detections = storage.get_detections(camera_id=camera_id, limit=limit, offset=offset)
        stats = storage.get_detection_stats(camera_id=camera_id)

        return jsonify({
            'success': True,
            'detections': detections,
            'stats': stats,
            'camera_id': camera_id,
            'limit': limit,
            'offset': offset
        })
    except Exception as e:
        logger.error(f"Error getting detections: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/detections/<camera_id>/<filename>')
def api_get_detection_image_per_camera(camera_id, filename):
    """Serve a per-camera detection image"""
    try:
        from flask import send_from_directory
        storage = get_detection_storage()
        image_path = storage.get_detection_image_path(camera_id=camera_id, filename=filename)

        if image_path.exists():
            detections_dir = str(image_path.parent)
            return send_from_directory(detections_dir, filename)
        else:
            return jsonify({'error': 'Image not found'}), 404
    except Exception as e:
        logger.error(f"Error serving image {camera_id}/{filename}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/detections/<filename>')
def api_get_detection_image(filename):
    """Serve a detection image (legacy endpoint for backward compatibility)"""
    try:
        from flask import send_from_directory
        storage = get_detection_storage()
        image_path = storage.get_detection_image_path(camera_id=None, filename=filename)

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
    """Delete detections based on age filter (supports per-camera and legacy)"""
    try:
        data = request.json
        age_filter = data.get('filter', 'all')
        camera_id = data.get('camera_id', None)  # Optional: specific camera

        # Validate filter
        valid_filters = ['all', 'year', 'month', 'week', 'day', 'hour', '10min']
        if age_filter not in valid_filters:
            return jsonify({
                'success': False,
                'error': f'Invalid filter. Must be one of: {valid_filters}'
            }), 400

        storage = get_detection_storage()
        deleted_count = storage.delete_detections_by_age(age_filter, camera_id=camera_id)

        return jsonify({
            'success': True,
            'deleted': deleted_count,
            'message': f'Deleted {deleted_count} detection(s) (filter: {age_filter})',
            'camera_id': camera_id
        })
    except Exception as e:
        logger.error(f"Error deleting detections: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/detections/stats', methods=['GET'])
def api_detection_stats():
    """Get detection statistics (supports per-camera and legacy)"""
    try:
        storage = get_detection_storage()
        camera_id = request.args.get('camera_id', default=None)  # Optional: specific camera
        stats = storage.get_detection_stats(camera_id=camera_id)
        return jsonify({'success': True, 'stats': stats, 'camera_id': camera_id})
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500




@app.route('/api/model-recommendation', methods=['POST'])
def api_model_recommendation():
    """
    Get Claude model recommendation for a task

    Request body:
    {
        "task_description": "What you want to do",
        "current_model": "haiku|sonnet|opus" (optional)
    }

    Returns model recommendation and whether current model is appropriate
    """
    try:
        data = request.get_json()
        if not data or 'task_description' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: task_description'
            }), 400

        task_description = data['task_description']
        current_model = data.get('current_model')

        recommendation = get_model_recommendation_api(task_description, current_model)

        logger.info(f"Model recommendation for task: {task_description[:50]}... "
                   f"-> {recommendation.get('recommended_model', 'Unknown')}")

        return jsonify({
            'success': True,
            'recommendation': recommendation
        })

    except Exception as e:
        logger.error(f"Error in model recommendation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/usage-stats', methods=['GET'])
def api_usage_stats():
    """Get API usage statistics and quota monitoring"""
    try:
        tracker = get_api_tracker()
        stats = tracker.get_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        logger.error(f"Error getting usage stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/metrics', methods=['GET'])
def api_activation_metrics():
    """Get sprinkler activation performance metrics"""
    try:
        metrics = get_activation_metrics()
        stats = metrics.get_metrics()
        return jsonify({'success': True, 'metrics': stats})
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def api_health():
    """Get overall system health status"""
    try:
        dm = get_device_manager()
        metrics = get_activation_metrics()
        tracker = get_api_tracker()

        health_status = {
            'timestamp': time.time(),
            'device_manager': dm.is_healthy(),
            'activation_metrics': metrics.get_health_summary(),
            'api_usage': tracker.get_stats()
        }

        # Determine overall health
        issues = []
        if not dm.credentials_valid:
            issues.append("Invalid API credentials")
        if not health_status['activation_metrics']['health'] == 'healthy':
            issues.append(f"Activation health: {health_status['activation_metrics']['health']}")
        if health_status['api_usage']['health_status'] != 'healthy':
            issues.append(f"API quota: {health_status['api_usage']['health_status']}")

        overall_health = 'critical' if issues else 'healthy'

        return jsonify({
            'success': True,
            'health': overall_health,
            'issues': issues,
            'detailed': health_status
        })
    except Exception as e:
        logger.error(f"Error getting health: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/diagnostics/run', methods=['POST'])
def api_run_diagnostics():
    """Run comprehensive system diagnostics"""
    try:
        dm = get_device_manager()
        results = {
            'timestamp': time.time(),
            'tests': []
        }

        # Test 1: Credentials valid
        cred_valid, cred_error = dm.credentials_valid, dm.last_error
        results['tests'].append({
            'name': 'API Credentials',
            'status': 'pass' if cred_valid else 'fail',
            'message': cred_error if not cred_valid else 'Credentials valid',
            'icon': '✓' if cred_valid else '✗'
        })

        # Test 2: Device discovery
        device_count = len(dm.devices)
        results['tests'].append({
            'name': f'Device Discovery',
            'status': 'pass' if device_count > 0 else 'fail',
            'message': f'Found {device_count} devices' if device_count > 0 else 'No devices found',
            'icon': '✓' if device_count > 0 else '✗'
        })

        # Test 3: Primary valve reachability
        from config import PRIMARY_VALVE_ID
        if PRIMARY_VALVE_ID in dm.devices:
            status = dm.get_device_status(PRIMARY_VALVE_ID, force_refresh=True)
            is_online = status.get('online', False)
            device_name = dm.devices[PRIMARY_VALVE_ID].get('name', 'Primary Valve')
            results['tests'].append({
                'name': f'Primary Valve ({device_name})',
                'status': 'pass' if is_online else 'warn',
                'message': f'Online' if is_online else 'Offline (WiFi may be disconnected)',
                'icon': '✓' if is_online else '⚠'
            })

            # Test 4: Valve activation test
            if is_online:
                test_result = dm.turn_on(PRIMARY_VALVE_ID, duration=2)
                activation_success = test_result.get('success', False) if isinstance(test_result, dict) else test_result
                activation_verified = test_result.get('verified', False) if isinstance(test_result, dict) else False

                results['tests'].append({
                    'name': 'Valve Activation Test',
                    'status': 'pass' if activation_verified else 'warn',
                    'message': 'Activation verified' if activation_verified else 'Command sent but could not verify',
                    'icon': '✓' if activation_verified else '⚠'
                })
        else:
            results['tests'].append({
                'name': 'Primary Valve',
                'status': 'fail',
                'message': f'PRIMARY_VALVE_ID not found in devices',
                'icon': '✗'
            })

        # Test 5: API quota
        tracker = get_api_tracker()
        quota_stats = tracker.get_stats()
        quota_usage = quota_stats['this_month']['quota_usage_pct']
        quota_health = quota_stats['health_status']

        results['tests'].append({
            'name': 'API Quota',
            'status': 'pass' if quota_health == 'healthy' else quota_health,
            'message': f'{quota_usage:.1f}% of monthly quota used ({quota_stats["this_month"]["count"]} calls)',
            'icon': '✓' if quota_health == 'healthy' else ('⚠' if quota_health == 'warning' else '✗')
        })

        # Add detection system information
        try:
            storage = get_detection_storage()
            detection_stats = storage.get_detection_stats()
            gallery_count = detection_stats.get('total', 0)
        except:
            gallery_count = 0

        results['detection_system'] = {
            'title': 'Detection System Status',
            'status': 'enabled',
            'configuration': {
                'model': 'YOLOv8 Nano',
                'confidence_threshold': 0.25,
                'target_animals': ['Cat', 'Dog', 'Horse', 'Sheep', 'Cow', 'Elephant', 'Bear', 'Zebra', 'Giraffe'],
                'gallery_saves': ['Person (safety review)', 'Horse (deer proxy)', 'Sheep', 'Cow', 'Bear (deer proxy)'],
                'detection_frequency': '~30 FPS from camera'
            },
            'safety_features': [
                'Person detection blocking - sprinkler won\'t activate if human is in frame',
                'Session limits - max 3 activations per detection session (60 seconds)',
                'Cooldown period - 2-minute cooldown between sessions to prevent excessive cycling',
                'Gallery auto-cleanup - detection images auto-deleted after 7 days'
            ],
            'expected_behavior': [
                'When camera comes online, system captures frames continuously',
                'YOLOv8 analyzes each frame for animals (9 types monitored)',
                'Animal detection → sprinkler activation (unless person detected)',
                'Meaningful detections saved to gallery (deer proxies, livestock)',
                'All activations logged with confidence scores and latency',
                'Activation metrics tracked for health monitoring'
            ],
            'camera_status': 'Offline (ESP32-CAM) - will auto-connect when powered on',
            'gallery_count': gallery_count
        }

        # Overall result
        failed = sum(1 for t in results['tests'] if t['status'] == 'fail')
        warned = sum(1 for t in results['tests'] if t['status'] == 'warn')

        results['overall'] = 'critical' if failed > 0 else ('warning' if warned > 0 else 'healthy')
        results['summary'] = f'{len(results["tests"])} tests: {sum(1 for t in results["tests"] if t["status"] == "pass")} passed'

        if failed > 0:
            results['summary'] += f', {failed} failed'
        if warned > 0:
            results['summary'] += f', {warned} warnings'

        return jsonify({
            'success': True,
            'diagnostics': results
        })

    except Exception as e:
        logger.error(f"Error running diagnostics: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'diagnostics': {
                'timestamp': time.time(),
                'tests': [{
                    'name': 'Diagnostics',
                    'status': 'fail',
                    'message': f'Error: {e}',
                    'icon': '✗'
                }],
                'overall': 'critical'
            }
        }), 500


@app.route('/setup', methods=['GET'])
def setup_page():
    """Serve setup configuration page"""
    from flask import send_from_directory
    return send_from_directory('../web', 'setup.html')


@app.route('/diagnostics', methods=['GET'])
def diagnostics_page():
    """Serve diagnostics dashboard page"""
    from flask import send_from_directory
    return send_from_directory('../web', 'diagnostics.html')


if __name__ == '__main__':
    logger.info(f"Starting server on {SERVER_HOST}:{SERVER_PORT}")
    logger.info(f"Web interface: http://192.168.1.15:{SERVER_PORT}")

    # Start the server
    socketio.run(app, host=SERVER_HOST, port=SERVER_PORT, debug=False, allow_unsafe_werkzeug=True)
