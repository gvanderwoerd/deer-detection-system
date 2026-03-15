# Deer Detection Sprinkler System

AI-powered animal detection system using ESP32-CAM + YOLOv8 + SmartLife valves.

**Status:** ✅ Fully Operational | **Updated:** 2026-03-14

---

## Features

- 🎥 **Live Camera Feed** - ESP32-CAM MJPEG streaming
- 🤖 **AI Detection** - YOLOv8 identifies animals in real-time
- 💧 **Smart Activation** - Controls SmartLife valves via Tuya Cloud API
- 🖼️ **Detection Gallery** - Automatic capture and review of all detections
- 🛡️ **Safety First** - Never activates if person detected
- 📊 **Web Dashboard** - Real-time monitoring and control

---

## Quick Start

```bash
# Start system
cd /mnt/linux-data/deer-detection-system
./start.sh

# Access dashboard
http://192.168.1.15:5000

# Stop system
./stop.sh
```

---

## System Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  ESP32-CAM      │──────│  Python Server   │──────│  SmartLife      │
│  (Camera)       │ MJPEG│  (AI Detection)  │ API  │  Valves         │
│  192.168.1.100  │      │  192.168.1.15    │      │  (Cloud)        │
└─────────────────┘      └──────────────────┘      └─────────────────┘
      ↓ Video                    ↓ Detection              ↓ Control
┌─────────────────────────────────────────────────────────────────────┐
│                      Web Dashboard (Port 5000)                      │
│  • Live video feed with timestamp overlay                           │
│  • AI detection bounding boxes & confidence                         │
│  • Detection gallery with stats                                     │
│  • Device manager for manual valve control                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Requirements

### Hardware
- **ESP32-CAM** (AI-Thinker) with OV2640 camera
- **MB Programmer Board** (for firmware upload)
- **5V 1A+ Power Supply** (brownout prevention)
- **SmartLife-compatible water valves** (Tuya protocol)
- **Desktop PC/Server** (Linux recommended)

### Software
- Python 3.12+
- Node.js 22+ (for development)
- PlatformIO (ESP32 firmware upload)
- YOLOv8 model (`yolov8n.pt`)

---

## Installation

### 1. Clone Repository
```bash
cd /mnt/linux-data
git clone https://github.com/gvanderwoerd/deer-detection-system.git
cd deer-detection-system
```

### 2. Setup Python Environment
```bash
cd server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure System
Edit `server/config.py`:
```python
ESP32_CAM_STREAM_URL = 'http://esp32cam.local:81/'
TUYA_CLOUD_API_KEY = "your_key"
TUYA_CLOUD_API_SECRET = "your_secret"
PRIMARY_VALVE_ID = 'your_device_id'
```

### 4. Upload ESP32-CAM Firmware
```bash
cd esp32-cam
# Edit src/main.cpp with your WiFi credentials
pio run --target upload
```

**⚠️ CRITICAL:** Read `esp32-cam/FIRMWARE_NOTES.md` before modifying firmware!

### 5. Start System
```bash
./start.sh
```

---

## Configuration

### ESP32-CAM Settings
**File:** `esp32-cam/src/main.cpp`

```cpp
const char* WIFI_SSID = "YourNetwork";
const char* WIFI_PASSWORD = "YourPassword";
IPAddress STATIC_IP(192, 168, 1, 100);  // Change if needed
const char* MDNS_HOSTNAME = "esp32cam";
```

### Detection Settings
**File:** `server/config.py`

```python
DETECTION_CONFIDENCE = 0.25  # 0.0-1.0 (lower = more sensitive)
TARGET_CLASS_IDS = [15, 16, 17, 18, 19, 20, 21, 22, 23]  # Animals
PERSON_CLASS_ID = 0  # Safety check (never activate if detected)
SPRINKLER_DURATION_SECONDS = 120  # 2 minutes
COOLDOWN_PERIOD_SECONDS = 120     # 2 minutes between activations
```

---

## API Endpoints

### Main Dashboard
- `GET /` - Web dashboard
- `GET /video_feed` - MJPEG camera stream
- `GET /api/status` - System status

### Detection Gallery
- `GET /detections` - Detection gallery interface
- `GET /api/detections` - List all detections (JSON)
- `GET /api/detections/<filename>` - Get detection image
- `POST /api/detections/delete` - Delete old detections

### Device Manager
- `GET /devices` - Device management interface
- `GET /api/devices` - List all valves (JSON)
- `POST /api/devices/turn_on` - Turn on valve
- `POST /api/devices/turn_off` - Turn off valve
- `POST /api/devices/emergency_stop` - Turn off ALL valves

---

## Troubleshooting

### ESP32-CAM Issues

**Camera shows black screen:**
1. Check LED pattern: 3 blinks → 5 blinks → 7 blinks → slow blink
2. Verify power supply (needs 1A minimum)
3. Test stream: `curl -I http://192.168.1.100:81/stream`
4. See: `esp32-cam/FIRMWARE_NOTES.md`

**Fast continuous LED blinking:**
- System failed during initialization
- Check power supply
- Verify WiFi credentials
- See LED pattern guide in `esp32-cam/FIRMWARE_NOTES.md`

### Server Issues

**Server won't start:**
```bash
./stop.sh      # Kill stuck processes
sleep 2
./start.sh     # Restart
```

**Detection not working:**
1. Verify camera feed visible in dashboard
2. Check YOLOv8 model: `ls yolov8n.pt`
3. Review logs: `tail -50 logs/server.log`

---

## Project Structure

```
deer-detection-system/
├── esp32-cam/              # ESP32-CAM firmware
│   ├── src/main.cpp       # Firmware code
│   └── FIRMWARE_NOTES.md  # ⚠️ Critical firmware documentation
├── server/                 # Python Flask server
│   ├── main.py            # Main application
│   ├── config.py          # Configuration
│   ├── device_manager.py  # Tuya Cloud integration
│   └── detection_storage.py
├── web/                    # Frontend
│   ├── index.html         # Main dashboard
│   ├── detections.html    # Detection gallery
│   └── devices.html       # Device manager
├── start.sh               # Startup script
├── stop.sh                # Shutdown script
├── PROJECT_LOG.md         # Detailed project log
└── README.md              # This file
```

---

## Documentation

- **Project Log:** `PROJECT_LOG.md` - Recent updates and history
- **Firmware Guide:** `esp32-cam/FIRMWARE_NOTES.md` - **Critical ESP32-CAM documentation**
- **Troubleshooting:** `TROUBLESHOOTING_QUICK_REF.md` - Quick fixes
- **Changelog:** `CHANGELOG.md` - Detailed feature history

---

## Safety & Important Notes

### ESP32-CAM Firmware ⚠️

The ESP32-CAM firmware has a **carefully structured initialization sequence** to prevent brownout issues. **DO NOT MODIFY** without reading `esp32-cam/FIRMWARE_NOTES.md`.

**Never:**
- Enable dual-core processing (causes brownout)
- Remove 3-second initialization delay
- Change initialization order

**Why:** ESP32-CAM requires staggered initialization (LED → Camera → WiFi → Server) with delays to prevent power spikes that trigger brownout resets.

### Person Safety

The system includes a **mandatory person detection check**. If YOLOv8 detects a person (class 0) in the frame, **sprinklers will NOT activate**, even if animals are present.

---

## License

MIT License - See LICENSE file for details

---

## Support

For issues or questions:
1. Check `TROUBLESHOOTING_QUICK_REF.md`
2. Review `esp32-cam/FIRMWARE_NOTES.md` (for camera issues)
3. Check logs: `logs/server.log`
4. Open issue: https://github.com/gvanderwoerd/deer-detection-system/issues

---

**Built with:** ESP32-CAM • YOLOv8 • Flask • Socket.IO • Tuya Cloud API
