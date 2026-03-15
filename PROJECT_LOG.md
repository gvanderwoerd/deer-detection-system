# Deer Detection Sprinkler System

**Status:** ✅ Fully Operational
**Last Updated:** 2026-03-14

---

## Quick Start

```bash
cd /mnt/linux-data/deer-detection-system
./start.sh                    # Start system
./stop.sh                     # Stop system
```

**Dashboard:** http://192.168.1.15:5000
**Camera:** http://192.168.1.100:81/stream or http://esp32cam.local:81/stream

---

## System Overview

Automated animal detection system that activates SmartLife valves to deter animals from the yard.

**Components:**
- **ESP32-CAM** - MJPEG video streaming (192.168.1.100:81)
- **Python Server** - YOLOv8 AI detection + Flask dashboard (192.168.1.15:5000)
- **SmartLife Valves** - 4x water valves controlled via Tuya Cloud API
- **Detection Gallery** - Automatic capture and storage of detections

**Detection Targets:** Cat, Dog, Horse, Sheep, Cow, Elephant, Bear, Zebra, Giraffe
**Safety:** Never activates if person detected

---

## Critical Notes

### ESP32-CAM Firmware ⚠️

**Location:** `esp32-cam/src/main.cpp`
**Documentation:** `esp32-cam/FIRMWARE_NOTES.md` ← **READ THIS BEFORE MODIFYING**

**NEVER:**
- Enable dual-core processing (causes brownout/crashes)
- Remove 3-second initialization delay
- Modify initialization sequence

**Why:** ESP32-CAM requires carefully staggered initialization to prevent brownout issues. See FIRMWARE_NOTES.md for full details.

---

## Recent Updates

### 2026-03-14: Firmware Recovery
- **Issue:** Gemini AI broke firmware attempting dual-core processing
- **Fix:** Restored working firmware from backup (`Arduino-Projects/esp32cam-test/`)
- **Result:** System operational, firmware now committed to git
- **Docs:** Created `esp32-cam/FIRMWARE_NOTES.md` with brownout prevention details

### 2026-03-14: Enhanced Detection
- Expanded target classes (cat, dog, horse, etc.) to reduce missed detections
- 12-hour timestamp overlay on camera feed
- Person safety check (never activates if human present)

### 2026-03-09: Detection Gallery
- Automatic image capture of all detections
- Web gallery at `/detections` with stats and filtering
- Smart logging with rotation (20MB max)

### 2026-03-09: Cloud API Optimization
- Reduced polling from 30s → 1hr (99.9% reduction in API calls)
- Status caching to prevent API spam
- Low-quota mode for trial accounts

---

## Configuration

### Server Config
**File:** `server/config.py`

```python
ESP32_CAM_STREAM_URL = 'http://esp32cam.local:81/'
DETECTION_CONFIDENCE = 0.25
TARGET_CLASS_IDS = [15, 16, 17, 18, 19, 20, 21, 22, 23]  # Animals
PRIMARY_VALVE_ID = 'eb2f5498a4e53362f5lumi'  # Back flowers
```

### ESP32-CAM Config
**File:** `esp32-cam/src/main.cpp`

```cpp
const char* WIFI_SSID = "CityWest_0090E24F";
const char* WIFI_PASSWORD = "cf72cc1722f549aa";
IPAddress STATIC_IP(192, 168, 1, 100);
const char* MDNS_HOSTNAME = "esp32cam";
```

### Upload ESP32 Firmware
```bash
cd /mnt/linux-data/deer-detection-system/esp32-cam
pio run --target upload
```

**Expected:** 3 blinks (boot) → 5 blinks (camera) → 7 blinks (WiFi) → slow blink (running)

---

## Troubleshooting

### Camera not working
1. Check LED pattern (3-5-7 blinks?)
2. Verify power supply (needs 1A @ 5V)
3. Test: `curl -I http://192.168.1.100:81/stream`
4. See: `esp32-cam/FIRMWARE_NOTES.md`

### Server won't start
```bash
./stop.sh        # Kill any stuck processes
sleep 2
./start.sh       # Restart
```

### Detection not working
1. Check camera feed in dashboard
2. Verify YOLOv8 model exists: `ls yolov8n.pt`
3. Check logs: `tail -50 logs/server.log`

---

## Project Structure

```
deer-detection-system/
├── esp32-cam/
│   ├── src/main.cpp           # ESP32-CAM firmware
│   └── FIRMWARE_NOTES.md      # ⚠️ READ BEFORE MODIFYING
├── server/
│   ├── main.py                # Flask server + detection logic
│   ├── config.py              # System configuration
│   ├── device_manager.py      # Tuya Cloud API integration
│   └── detection_storage.py  # Gallery & image storage
├── web/
│   ├── index.html             # Main dashboard
│   ├── detections.html        # Detection gallery
│   └── devices.html           # Device manager
├── start.sh                   # System startup script
├── stop.sh                    # System shutdown script
└── PROJECT_LOG.md             # This file
```

---

## Links

- **GitHub:** https://github.com/gvanderwoerd/deer-detection-system
- **ESP32 Firmware Docs:** `esp32-cam/FIRMWARE_NOTES.md`
- **Troubleshooting:** `TROUBLESHOOTING_QUICK_REF.md`
- **Changelog:** `CHANGELOG.md`

---

**For detailed history and technical wins, see previous versions of this file in git history.**
