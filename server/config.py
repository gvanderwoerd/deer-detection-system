# Deer Detection System Configuration

# === Network Configuration ===
SERVER_HOST = '0.0.0.0'  # Listen on all interfaces
SERVER_PORT = 5000
ESP32_CAM_STREAM_URL = 'http://esp32cam.local:81/'  # ESP32-CAM via mDNS (hostname)

# === Detection Configuration ===
DETECTION_CONFIDENCE = 0.25  # Confidence threshold (0.0-1.0) - lowered for testing
TARGET_CLASS_IDS = [23, 21, 19]  # COCO: deer=23, cow=21, sheep=19
PERSON_CLASS_ID = 0  # COCO: person=0 (safety check - never activate with people)
MODEL_PATH = 'yolov8n.pt'  # YOLOv8 nano model

# === System Behavior ===
ACTIVE_WINDOW_SECONDS = 600  # 10 minutes after motion detected (ESP32-CAM awake time)
SPRINKLER_DURATION_SECONDS = 120  # Sprinkler runs for 2 minutes
COOLDOWN_PERIOD_SECONDS = 120  # Wait 2 minutes between activations
MAX_DETECTIONS_PER_SESSION = 3  # Max times to activate sprinkler in one session

# === Tuya Cloud API Configuration ===
TUYA_CLOUD_API_KEY = "rqwuq7sgvv57f745g5m8"
TUYA_CLOUD_API_SECRET = "f64c246ade9f45cf9c4217851deceddc"
TUYA_CLOUD_REGION = "us"

# Primary valve for deer detection system
PRIMARY_VALVE_ID = 'eb2f5498a4e53362f5lumi'  # Back flowers valve

# === Logging ===
LOG_DETECTIONS = True
LOG_FILE = 'deer_detection.log'
MAX_LOG_ENTRIES = 1000  # Keep last 1000 events in memory

# === WiFi Configuration (for reference - enter in ESP32-CAM) ===
# WIFI_SSID = 'YourNetworkName'
# WIFI_PASSWORD = 'YourPassword'
# ESP32_GPIO_TRIGGER_PIN = 13  # GPIO pin for Yard Sentinel trigger
