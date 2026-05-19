"""
Multi-Camera Management System
Manages multiple ESP32-CAM devices with per-camera configuration
"""

import json
import logging
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple
import requests
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Default camera configuration template
DEFAULT_CAMERA_CONFIG = {
    "detection_config": {
        "enabled_objects": {
            "person": True,
            "cat": True,
            "dog": True,
            "horse": True,
            "sheep": True,
            "cow": True,
            "elephant": True,
            "bear": True,
            "zebra": True,
            "giraffe": True
        },
        "confidence_threshold": 0.25,
        "save_person_detections": False
    },
    "device_assignments": [],
    "timing": {
        "active_window_seconds": 60,
        "cooldown_period_seconds": 120,
        "max_detections_per_session": 3
    },
    "state": {
        "online": False,
        "session_active": False,
        "session_detections": 0,
        "cooldown_until": None,
        "last_detection": None
    }
}


class Camera:
    """Represents a single ESP32-CAM camera"""

    def __init__(self, camera_id: str, name: str, hostname: str, stream_url: str):
        self.camera_id = camera_id
        self.name = name
        self.hostname = hostname
        self.stream_url = stream_url
        self.enabled = True
        self.created_at = datetime.now().isoformat()
        self.last_seen = None
        self.position = 0

        # Configuration (from cameras.json)
        self.detection_config = DEFAULT_CAMERA_CONFIG["detection_config"].copy()
        self.device_assignments = []
        self.timing = DEFAULT_CAMERA_CONFIG["timing"].copy()

        # Runtime state
        self.online = False
        self.session_active = False
        self.session_detections = 0
        self.cooldown_until = None
        self.last_detection = None

        # Frame buffers
        self.current_frame = None
        self.current_jpg = None
        self.annotated_jpg = None
        self.frame_lock = threading.Lock()

        # Status tracking
        self.stream_active = False
        self.last_frame_time = None
        self.motion_active = False
        self.wifi_signal = None

        # Detection session tracking
        self.session_start = None
        self.detector = None  # Will be set by CameraManager

    def trigger_detection(self) -> bool:
        """Trigger a detection session on this camera"""
        now = time.time()

        # Check if in cooldown
        if self.cooldown_until and now < self.cooldown_until:
            remaining = int(self.cooldown_until - now)
            logger.info(f"[{self.name}] Detection blocked - in cooldown ({remaining}s remaining)")
            return False

        # Check if already in active session
        if self.session_active:
            logger.debug(f"[{self.name}] Already in active session - extending")
            return False

        # Start new session
        logger.info(f"[{self.name}] Detection session triggered")
        self.session_active = True
        self.session_detections = 0
        self.session_start = now
        return True

    def end_session(self):
        """End detection session and start cooldown"""
        if self.session_active:
            self.session_active = False
            self.cooldown_until = time.time() + self.timing['cooldown_period_seconds']
            logger.info(f"[{self.name}] Session ended - cooldown {self.timing['cooldown_period_seconds']}s")

    def is_session_expired(self) -> bool:
        """Check if session has exceeded active window"""
        if not self.session_active or not self.session_start:
            return False
        elapsed = time.time() - self.session_start
        return elapsed > self.timing['active_window_seconds']

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.camera_id,
            "name": self.name,
            "hostname": self.hostname,
            "stream_url": self.stream_url,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "last_seen": self.last_seen,
            "position": self.position,
            "detection_config": self.detection_config,
            "device_assignments": self.device_assignments,
            "timing": self.timing,
            "state": {
                "online": self.online,
                "session_active": self.session_active,
                "session_detections": self.session_detections,
                "cooldown_until": self.cooldown_until,
                "last_detection": self.last_detection
            }
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Camera':
        """Create Camera from dictionary"""
        camera = cls(
            camera_id=data['id'],
            name=data['name'],
            hostname=data['hostname'],
            stream_url=data['stream_url']
        )
        camera.enabled = data.get('enabled', True)
        camera.created_at = data.get('created_at', datetime.now().isoformat())
        camera.last_seen = data.get('last_seen')
        camera.position = data.get('position', 0)
        camera.detection_config = data.get('detection_config', DEFAULT_CAMERA_CONFIG['detection_config'].copy())
        camera.device_assignments = data.get('device_assignments', [])
        camera.timing = data.get('timing', DEFAULT_CAMERA_CONFIG['timing'].copy())

        state = data.get('state', {})
        camera.online = state.get('online', False)
        camera.session_active = state.get('session_active', False)
        camera.session_detections = state.get('session_detections', 0)
        camera.cooldown_until = state.get('cooldown_until')
        camera.last_detection = state.get('last_detection')

        return camera


class CameraManager:
    """
    Singleton managing multiple ESP32-CAM devices
    - Load/save camera configurations from cameras.json
    - Spawn capture thread per camera
    - Route frames to detection system
    - Track per-camera state
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CameraManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.cameras: Dict[str, Camera] = {}
        self.capture_threads: Dict[str, threading.Thread] = {}
        self.detection_threads: Dict[str, threading.Thread] = {}
        self.cameras_file = Path(__file__).parent / "cameras.json"
        self._initialized = True

        # Initialize detector (shared across all cameras)
        try:
            from detection import DeerDetector
            self.detector = DeerDetector()
            logger.info("✅ Detector initialized for per-camera detection")
        except Exception as e:
            logger.error(f"Failed to initialize detector: {e}")
            self.detector = None

        # Load existing cameras or create default
        self._load_cameras()

        # Set detector on all cameras
        for camera in self.cameras.values():
            camera.detector = self.detector

        # Start capture threads
        for camera_id in self.cameras:
            self._start_capture_thread(camera_id)
            self._start_detection_thread(camera_id)

        logger.info(f"✅ Camera Manager initialized with {len(self.cameras)} camera(s)")

    def _load_cameras(self):
        """Load camera configuration from cameras.json"""
        if self.cameras_file.exists():
            try:
                with open(self.cameras_file, 'r') as f:
                    data = json.load(f)
                    for camera_data in data.get('cameras', []):
                        camera = Camera.from_dict(camera_data)
                        self.cameras[camera.camera_id] = camera
                logger.info(f"Loaded {len(self.cameras)} camera(s) from {self.cameras_file}")
            except Exception as e:
                logger.error(f"Failed to load cameras: {e}")
                self.cameras = {}
        else:
            # Create default camera from legacy single-camera config
            self._migrate_from_single_camera()

    def _migrate_from_single_camera(self):
        """Auto-migrate from single-camera config if cameras.json doesn't exist"""
        try:
            from config import ESP32_CAM_STREAM_URL, PRIMARY_VALVE_ID

            logger.info("No cameras.json found - migrating from single-camera configuration")

            # Create default camera
            default_camera = Camera(
                camera_id="camera-default",
                name="Default Camera",
                hostname="esp32cam.local",
                stream_url=ESP32_CAM_STREAM_URL
            )

            # Assign primary valve if configured
            if PRIMARY_VALVE_ID:
                default_camera.device_assignments = [
                    {
                        "device_id": PRIMARY_VALVE_ID,
                        "duration_seconds": 120  # Default duration
                    }
                ]

            self.cameras["camera-default"] = default_camera
            self._save_cameras()

            logger.info("✅ Auto-migrated to multi-camera configuration")
            logger.info("   Camera ID: 'camera-default'")
            logger.info("   Add more cameras via /api/cameras endpoint")

        except Exception as e:
            logger.error(f"Failed to migrate from single-camera config: {e}")
            # Create a minimal default if all else fails
            self.cameras["camera-default"] = Camera(
                camera_id="camera-default",
                name="Default Camera",
                hostname="esp32cam.local",
                stream_url="http://esp32cam.local:81/"
            )

    def _save_cameras(self):
        """Save camera configuration to cameras.json"""
        try:
            data = {
                "version": 1,
                "cameras": [camera.to_dict() for camera in self.cameras.values()]
            }
            with open(self.cameras_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self.cameras)} camera(s) to {self.cameras_file}")
        except Exception as e:
            logger.error(f"Failed to save cameras: {e}")

    def register_camera(self, name: str, hostname: str, stream_url: str) -> str:
        """Register new camera and start capture"""
        camera_id = self._generate_camera_id(name)

        camera = Camera(
            camera_id=camera_id,
            name=name,
            hostname=hostname,
            stream_url=stream_url
        )

        self.cameras[camera_id] = camera
        self._save_cameras()
        self._start_capture_thread(camera_id)

        logger.info(f"✅ Registered camera: {name} (ID: {camera_id})")
        return camera_id

    def get_camera(self, camera_id: str) -> Optional[Camera]:
        """Get camera by ID"""
        return self.cameras.get(camera_id)

    def get_all_cameras(self) -> list:
        """Get all cameras as dictionaries"""
        return [camera.to_dict() for camera in self.cameras.values()]

    def update_camera(self, camera_id: str, data: Dict) -> bool:
        """Update camera configuration"""
        camera = self.get_camera(camera_id)
        if not camera:
            return False

        if 'name' in data:
            camera.name = data['name']
        if 'enabled' in data:
            camera.enabled = data['enabled']
        if 'detection_config' in data:
            camera.detection_config = data['detection_config']
        if 'device_assignments' in data:
            camera.device_assignments = data['device_assignments']
        if 'timing' in data:
            camera.timing = data['timing']

        self._save_cameras()
        logger.info(f"Updated camera: {camera_id}")
        return True

    def delete_camera(self, camera_id: str) -> bool:
        """Delete camera and stop capture thread"""
        if camera_id not in self.cameras:
            return False

        # Stop capture thread
        thread = self.capture_threads.get(camera_id)
        if thread and thread.is_alive():
            # Thread will exit naturally on next iteration
            logger.debug(f"Marked capture thread for {camera_id} to stop")

        # Remove from registry
        del self.cameras[camera_id]
        self._save_cameras()

        logger.info(f"Deleted camera: {camera_id}")
        return True

    def test_camera_connection(self, camera_id: str) -> Tuple[bool, Dict]:
        """Test camera connection and return status"""
        camera = self.get_camera(camera_id)
        if not camera:
            return False, {"error": "Camera not found"}

        try:
            start_time = time.time()
            response = requests.get(camera.stream_url, stream=True, timeout=5)

            # Try to get first frame
            bytes_buffer = b''
            for chunk in response.iter_content(chunk_size=1024):
                bytes_buffer += chunk
                if len(bytes_buffer) > 50000:  # Got enough data
                    break

            latency = (time.time() - start_time) * 1000

            # Try to parse a frame to get resolution
            a = bytes_buffer.find(b'\xff\xd8')
            b = bytes_buffer.find(b'\xff\xd9')

            if a != -1 and b != -1:
                jpg = bytes_buffer[a:b+2]
                frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    height, width = frame.shape[:2]
                    camera.online = True
                    camera.last_seen = datetime.now().isoformat()
                    self._save_cameras()

                    return True, {
                        "online": True,
                        "latency_ms": round(latency, 1),
                        "resolution": f"{width}x{height}",
                        "fps": 30  # Assuming standard 30 FPS
                    }

            return False, {"error": "Could not decode frame"}

        except requests.exceptions.Timeout:
            return False, {"error": "Connection timeout"}
        except requests.exceptions.ConnectionError:
            return False, {"error": "Connection refused"}
        except Exception as e:
            return False, {"error": str(e)}

    def _start_capture_thread(self, camera_id: str):
        """Start dedicated capture thread for camera"""
        camera = self.get_camera(camera_id)
        if not camera:
            return

        def capture_worker():
            logger.info(f"🎥 Starting capture thread for {camera.name}")
            connection_attempts = 0

            while camera_id in self.cameras:  # Continue until camera is deleted
                try:
                    if not camera.enabled:
                        time.sleep(1)
                        continue

                    connection_attempts += 1
                    if connection_attempts == 1 or connection_attempts % 10 == 0:
                        logger.debug(f"[{camera.name}] Connecting to stream (attempt {connection_attempts})...")

                    stream = requests.get(camera.stream_url, stream=True, timeout=10)
                    connection_attempts = 0

                    bytes_buffer = b''
                    frame_count = 0

                    for chunk in stream.iter_content(chunk_size=1024):
                        if camera_id not in self.cameras:  # Check if camera was deleted
                            break

                        bytes_buffer += chunk

                        # Parse PIR status
                        pir_header_marker = b'X-PIR-Status: '
                        pir_pos = bytes_buffer.find(pir_header_marker)
                        if pir_pos != -1:
                            status_start = pir_pos + len(pir_header_marker)
                            status_end = bytes_buffer.find(b'\r\n', status_start)
                            if status_end != -1:
                                pir_status = bytes_buffer[status_start:status_end].decode('utf-8').strip()
                                is_active = (pir_status == 'active')

                                if camera.motion_active != is_active:
                                    camera.motion_active = is_active
                                    if is_active:
                                        camera.last_detection = datetime.now().isoformat()
                                        logger.info(f"[{camera.name}] PIR: MOTION DETECTED")
                                    logger.debug(f"[{camera.name}] PIR: {'MOTION' if is_active else 'no motion'}")

                        # Parse WiFi signal
                        wifi_header_marker = b'X-WiFi-Signal: '
                        wifi_pos = bytes_buffer.find(wifi_header_marker)
                        if wifi_pos != -1:
                            signal_start = wifi_pos + len(wifi_header_marker)
                            signal_end = bytes_buffer.find(b'\r\n', signal_start)
                            if signal_end != -1:
                                try:
                                    camera.wifi_signal = int(bytes_buffer[signal_start:signal_end].decode('utf-8').strip())
                                except ValueError:
                                    pass

                        # Extract JPEG frames
                        a = bytes_buffer.find(b'\xff\xd8')
                        b = bytes_buffer.find(b'\xff\xd9')

                        if a != -1 and b != -1:
                            jpg = bytes_buffer[a:b+2]
                            bytes_buffer = bytes_buffer[b+2:]

                            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)

                            if frame is not None:
                                with camera.frame_lock:
                                    camera.current_frame = frame
                                    camera.current_jpg = jpg

                                    # Mark camera as online
                                    now = time.time()
                                    if camera.last_frame_time is None:
                                        logger.info(f"📷 [{camera.name}] Stream active")
                                        camera.stream_active = True
                                        camera.online = True

                                    camera.last_frame_time = now

                                frame_count += 1
                                if frame_count % 1000 == 0:
                                    logger.debug(f"[{camera.name}] Captured {frame_count} frames")

                except Exception as e:
                    logger.error(f"[{camera.name}] Capture error: {e}")
                    with camera.frame_lock:
                        camera.current_frame = None
                        camera.current_jpg = None
                        if camera.stream_active:
                            logger.info(f"📷 [{camera.name}] Stream inactive")
                            camera.stream_active = False
                            camera.online = False
                            camera.last_frame_time = None
                    time.sleep(5)

            logger.info(f"🛑 Stopped capture thread for {camera.name}")

        thread = threading.Thread(target=capture_worker, daemon=True, name=f"CaptureWorker-{camera_id}")
        thread.start()
        self.capture_threads[camera_id] = thread

    def _start_detection_thread(self, camera_id: str):
        """Start detection processing thread for a camera"""
        camera = self.cameras.get(camera_id)
        if not camera or not self.detector:
            return

        def detection_worker():
            """Process frames for this camera during detection sessions"""
            from config import MAX_DETECTIONS_PER_SESSION
            from device_manager import get_device_manager

            logger.info(f"🎯 Detection worker started for {camera.name}")
            logger.info(f"   Device assignments: {len(camera.device_assignments)} device(s)")
            for idx, assignment in enumerate(camera.device_assignments):
                logger.info(f"   - Device {idx+1}: {assignment.get('device_id')} ({assignment.get('duration_seconds')}s)")

            while True:
                try:
                    # Check if session is active
                    if camera.session_active:
                        # Check if session has expired
                        if camera.is_session_expired():
                            camera.end_session()
                            continue

                        # Get current frame
                        with camera.frame_lock:
                            frame = camera.current_frame

                        if frame is not None:
                            try:
                                # Run detection
                                deer_detected, detections, annotated_frame = self.detector.detect_deer(frame)

                                # Store annotated frame for streaming
                                if annotated_frame is not None:
                                    _, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                                    with camera.frame_lock:
                                        camera.annotated_jpg = buffer.tobytes()

                                # Handle detections
                                if detections:
                                    from detection_storage import get_detection_storage
                                    storage = get_detection_storage()
                                    animal_type = detections[0]['class']
                                    class_id = detections[0].get('class_id')

                                    # Check if this animal type is enabled in camera settings
                                    enabled_objects = camera.detection_config.get('enabled_objects', {})
                                    is_enabled = enabled_objects.get(animal_type.lower(), False)

                                    # Save to gallery only if enabled in camera settings
                                    if is_enabled:
                                        saved_filename = storage.save_detection(camera_id, annotated_frame, detections, animal_type)
                                        logger.info(f"📸 [{camera.name}] Detection saved: {saved_filename}")
                                    else:
                                        logger.info(f"ℹ️ [{camera.name}] {animal_type.upper()} detected but disabled in camera settings - not saving")

                                    # Activate sprinkler if target animal is enabled (not person, safety check is in detector)
                                    if deer_detected and is_enabled and camera.session_detections < MAX_DETECTIONS_PER_SESSION:
                                        camera.session_detections += 1
                                        camera.last_detection = datetime.now().isoformat()
                                        logger.info(f"🎯 [{camera.name}] {animal_type.upper()} detected! (#{camera.session_detections})")

                                        # Activate assigned devices
                                        dm = get_device_manager()
                                        logger.info(f"💨 [{camera.name}] Attempting to activate {len(camera.device_assignments)} device(s)")
                                        if not camera.device_assignments:
                                            logger.warning(f"⚠️ [{camera.name}] No device assignments configured!")

                                        for assignment in camera.device_assignments:
                                            device_id = assignment['device_id']
                                            duration = assignment['duration_seconds']
                                            try:
                                                logger.info(f"💨 [{camera.name}] Calling turn_on({device_id}, duration={duration})")
                                                dm.turn_on(device_id, duration=duration)
                                                logger.info(f"✅ [{camera.name}] Device {device_id} activated for {duration}s")
                                            except Exception as e:
                                                logger.error(f"❌ [{camera.name}] Failed to activate device {device_id}: {e}")
                                    elif deer_detected and not is_enabled:
                                        logger.info(f"ℹ️ [{camera.name}] {animal_type.upper()} detected but disabled in camera settings - not activating sprinkler")

                            except Exception as e:
                                logger.error(f"[{camera.name}] Detection error: {e}")

                        time.sleep(0.5)  # Check twice per second
                    else:
                        # Not in session, just update current frame for preview
                        time.sleep(0.1)

                except Exception as e:
                    logger.error(f"[{camera.name}] Detection worker error: {e}")
                    time.sleep(1)

            logger.info(f"🛑 Detection worker stopped for {camera.name}")

        thread = threading.Thread(target=detection_worker, daemon=True, name=f"DetectionWorker-{camera_id}")
        thread.start()
        self.detection_threads[camera_id] = thread

    @staticmethod
    def _generate_camera_id(name: str) -> str:
        """Generate camera ID from name"""
        # Convert to lowercase, replace spaces with hyphens, remove special chars
        camera_id = name.lower()
        camera_id = camera_id.replace(' ', '-')
        camera_id = ''.join(c for c in camera_id if c.isalnum() or c == '-')
        camera_id = camera_id.strip('-')
        return f"camera-{camera_id}"


# Global camera manager instance
_camera_manager = None


def get_camera_manager() -> CameraManager:
    """Get or create global camera manager instance"""
    global _camera_manager
    if _camera_manager is None:
        _camera_manager = CameraManager()
    return _camera_manager
