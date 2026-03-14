# Deer Detection System - Changelog

## 2026-03-14 - Cloud API Resilience & UI Robustness

### Enhanced Animal Detection (NEW)
- ✅ Expanded target classes to include animals often misidentified as deer by AI
- ✅ Now targets: Cat, Dog, Horse, Sheep, Cow, Elephant, Bear, Zebra, Giraffe
- ✅ Maintains strict **Person Detection Safety Check** (prevents activation if humans present)
- ✅ Sensitivity remains high with 0.25 confidence threshold for partial captures

### Live Timestamp Overlay (NEW)
- ✅ Implemented real-time date and time overlay on the camera feed
- ✅ **12-hour clock format with AM/PM** for better readability
- ✅ Timestamp is baked into the "clean" frame, ensuring it appears on the live dashboard
- ✅ Automatic inclusion of the exact detection time in all images saved to the gallery
- ✅ High-readability design with semi-transparent background box in the bottom-left corner

### Low-Quota Optimization (NEW)
- ✅ Reduced Cloud API polling from 30 seconds to **1 hour**
- ✅ Implemented **Status Caching** in `DeviceManager` to prevent API spam from dashboard
- ✅ Added manual **"Sync Valve Status (Cloud)"** buttons to main dashboard and device manager
- ✅ Mathematical reduction in API tokens: ~28,800/day reduced to ~720/month (99.9% reduction)

### Cloud API Error Handling (NEW)
- ✅ Implemented Tuya Cloud API quota detection (28841004 / 'trial' errors)
- ✅ `DeviceManager` now tracks and reports `last_error` to the frontend
- ✅ Automatic detection of "Cloud API Quota Exceeded" for easier troubleshooting
- ✅ Added `server/test_tuya.py` utility for quick API connectivity tests

### Remote Client-Side Logging (NEW)
- ✅ New server endpoint `/api/client_log` to capture frontend errors
- ✅ JS errors and key events are now automatically forwarded to server logs
- ✅ Easier debugging of mobile or remote dashboard issues
- ✅ Real-time server-side insight into client-side JS state

### UI Resilience & Diagnostic Enhancements
- ✅ Full refactor of `app.js` initialization to prevent race conditions
- ✅ Implemented "Failsafe Heartbeat" (inline JS indicators) in `index.html`
- ✅ Dynamic "API Error" status badges for valves when quotas are hit
- ✅ Enhanced error reporting on the Devices management page
- ✅ Version-bumped `app.js?v=10` to force cache refresh

## 2026-03-09 - Detection Gallery & Smart Logging

### Detection Storage System (NEW)
- ✅ Automatic image saving when animals detected (deer/cow/sheep)
- ✅ Images stored in `server/detections/` with metadata
- ✅ Filename format: `YYYY-MM-DD_HH-MM-SS_animal_confidence.jpg`
- ✅ JSON metadata tracking: timestamp, confidence, bounding boxes, animal type
- ✅ New module: `server/detection_storage.py`

### Detection Gallery Web Interface (NEW)
- ✅ Beautiful card-based gallery at `/detections`
- ✅ Statistics dashboard (total detections, by animal type, date ranges)
- ✅ Image zoom modal (click to view full-size)
- ✅ Time-based deletion controls (10min/hour/day/week/month/year/all)
- ✅ Newest-first sorting with pagination support
- ✅ Color-coded animal badges (deer=orange, cow=purple, sheep=teal)
- ✅ Mobile-responsive design
- ✅ "View Detection Gallery" button added to main dashboard

### Detection Gallery API (NEW)
- ✅ `GET /api/detections` - List detections with stats
- ✅ `GET /api/detections/<filename>` - Serve detection images
- ✅ `POST /api/detections/delete` - Delete by age filter
- ✅ `GET /api/detections/stats` - Get statistics only
- ✅ Pagination support (limit/offset parameters)

### Smart Logging System
- ✅ Implemented log rotation (5MB per file, 4 backups = 20MB max)
- ✅ Added `SmartErrorFilter` to suppress repetitive errors
- ✅ Logs first error, then every 100th repetition with counter
- ✅ Archived old 26MB log file (182K lines preserved)
- ✅ Reduced logging noise (frame counts, connection retries at DEBUG level)
- ✅ Focus on important events: detections, activations, state changes
- ✅ New log file starts clean (1.4KB vs 26MB)

### Files Modified
- `server/main.py` - Detection storage integration, API endpoints, smart logging
- `web/index.html` - Added gallery button
- `web/app.js` - Gallery navigation
- `web/style.css` - Gallery button styling

### Files Created
- `server/detection_storage.py` - Detection storage manager (235 lines)
- `web/detections.html` - Gallery interface (499 lines)
- `server/detections/` - Detection images directory
- `server/detections/detections.json` - Metadata database

### Performance Impact
- **Image storage**: ~100KB per detection (JPEG compressed)
- **Log rotation**: Prevents runaway log growth (was 26MB, now capped at 20MB)
- **Disk usage**: Manageable with time-based deletion controls

---

## 2026-03-07 - System Updates

### ESP32-CAM Improvements
- ✅ Implemented mDNS support (hostname: `esp32cam.local`)
- ✅ Added static IP fallback (192.168.1.100)
- ✅ Comprehensive LED status indicators (3-5-7 blink pattern)
- ✅ Updated MULTI_DEVICE_SETUP.md for easy replication
- ✅ Cleaned up old reference code files
- ✅ Documented serial output hardware limitation

### Server Enhancements
- ✅ Updated ESP32_CAM_STREAM_URL to use mDNS hostname
- ✅ Fixed dashboard overlay issue (camera feed now shows immediately on page load)
- ✅ Added camera status to system status API
- ✅ Emit camera_status on client connect for instant UI update
- ✅ Improved WebSocket initialization

### Dashboard Improvements
- ✅ Fixed "waiting for camera..." overlay showing when camera is active
- ✅ Automatic camera feed display when ESP32-CAM is streaming
- ✅ "View Live Camera" button now only needed for manual triggering
- ✅ Cleaner CSS for camera overlay (hidden by default)

### User Experience
- ✅ Created desktop launcher: **"Sprinkler Start"** icon
- ✅ One-click system startup + browser auto-open
- ✅ Updated README.md with current configuration
- ✅ Simplified startup process with ./start.sh and ./stop.sh scripts

### Documentation
- ✅ Updated README.md to reflect current system state
- ✅ Noted upcoming HC-SR501 PIR sensor integration
- ✅ Added mDNS troubleshooting steps
- ✅ Documented LED status patterns
- ✅ Created this CHANGELOG

### Upcoming Features
- ⏳ HC-SR501 PIR motion sensor integration
- ⏳ ESP32-CAM deep sleep mode for power saving
- ⏳ Motion sensor status indicator on dashboard
- ⏳ Multiple camera support

### Known Issues
- Serial output doesn't work on ESP32-CAM hardware (documented limitation)
- Using continuous streaming mode (deep sleep not yet implemented)

### System Status
- **ESP32-CAM**: Fully operational, streaming at http://esp32cam.local:81/
- **Server**: Running stable, YOLOv8 detection active
- **Dashboard**: Fixed overlay issue, clean UI
- **SmartLife Valves**: 4 devices configured (offline when not powered)
- **Detection**: Active, monitoring for deer (class 23), cow (class 21), sheep (class 19)

---

## Quick Start Guide

### Starting the System
1. Double-click **"Sprinkler Start"** icon on desktop
2. Dashboard opens automatically at http://192.168.1.15:5000
3. System armed and ready!

### Stopping the System
```bash
cd /mnt/linux-data/deer-detection-system
./stop.sh
```

### Project Locations
- **Server**: `/mnt/linux-data/deer-detection-system/`
- **ESP32 Firmware**: `/mnt/linux-data/Arduino-Projects/esp32cam-test/`
- **Desktop Launcher**: `~/Desktop/sprinkler-start.desktop`

---

**Last Updated**: March 7, 2026
