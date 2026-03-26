# Deer Detection System Configuration
import os
from pathlib import Path

# Load environment variables from .env file if it exists
env_file = Path(__file__).parent.parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

# === Network Configuration ===
SERVER_HOST = '0.0.0.0'  # Listen on all interfaces
SERVER_PORT = 5000
ESP32_CAM_STREAM_URL = 'http://esp32cam.local:81/'  # ESP32-CAM via mDNS (hostname)

# === Detection Configuration ===
DETECTION_CONFIDENCE = 0.25  # Confidence threshold (0.0-1.0) - lowered for testing
# COCO class IDs that could be misidentified as deer/cow/sheep
# 15: cat, 16: dog, 17: horse, 18: sheep, 19: cow, 20: elephant, 21: bear, 22: zebra, 23: giraffe
TARGET_CLASS_IDS = [15, 16, 17, 18, 19, 20, 21, 22, 23]  
PERSON_CLASS_ID = 0  # COCO: person=0 (safety check - never activate with people)
MODEL_PATH = 'yolov8n.pt'  # YOLOv8 nano model

# === System Behavior ===
ACTIVE_WINDOW_SECONDS = 600  # 10 minutes after motion detected (ESP32-CAM awake time)
SPRINKLER_DURATION_SECONDS = 120  # Sprinkler runs for 2 minutes
COOLDOWN_PERIOD_SECONDS = 120  # Wait 2 minutes between activations
MAX_DETECTIONS_PER_SESSION = 3  # Max times to activate sprinkler in one session

# === Tuya Cloud API Configuration ===
# Load from environment variables for security
# Create a .env file based on .env.example with your credentials
TUYA_CLOUD_API_KEY = os.getenv('TUYA_API_KEY', '')
TUYA_CLOUD_API_SECRET = os.getenv('TUYA_API_SECRET', '')
TUYA_CLOUD_REGION = os.getenv('TUYA_CLOUD_REGION', 'us')

# Primary valve for deer detection system
PRIMARY_VALVE_ID = os.getenv('PRIMARY_VALVE_ID', '')

# === Logging ===
LOG_FILE = 'deer_detection.log'
MAX_LOG_ENTRIES = 1000  # Keep last 1000 events in memory

# === WiFi Configuration (for reference - enter in ESP32-CAM) ===
# WIFI_SSID = 'YourNetworkName'
# WIFI_PASSWORD = 'YourPassword'
# ESP32_GPIO_TRIGGER_PIN = 13  # GPIO pin for Yard Sentinel trigger
