# Deer Detection Sprinkler System

**Status:** ✅ Fully Operational
**Last Updated:** 2026-05-18
**Framework Version:** Phase 1-4 Complete (Sprinkler Control Reliability Framework)
**Latest Bookmark:** Code & File Bloat Cleanup - Quick Wins (Commit b5ae8ed)

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

**Detection Targets:** Cat, Dog, Horse, Sheep, Cow, Elephant, Bear, Zebra, Giraffe (all trigger sprinkler)
**Gallery Saves:** Only Deer (horse/bear proxies), Cow, Sheep (meaningful detections)
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

### 2026-05-18: Code & File Bloat Cleanup - Quick Wins (Commits 3bb0757, 296fb27, b5ae8ed)

**Three Quick-Win Cleanups to Improve Code Organization & Maintainability**

#### 1. Test File Organization (Commit 3bb0757)
Moved test files from `server/` to dedicated `tests/` directory for better project structure.

- **Moved:** `server/test_tuya.py` → `tests/test_tuya.py`
- **Moved:** `server/test_integration.py` → `tests/test_integration.py`
- **Cleaned:** Removed orphaned `.pytest_cache` from server/
- **Updated:** pytest command in test_integration.py to reflect new location
- **Status:** Test files remain unused in production (safe to move)
- **Impact:** Reduced clutter in server/ directory, improved project organization

#### 2. Remove Unused Imports (Commit 296fb27)
Removed 4 unused imports from `server/main.py` identified through code analysis.

**Removed imports:**
- `import requests` - Used by valve_control_cloud and device_manager, not main.py
- `import numpy as np` - Unused (cv2 handles all image operations)
- `from model_recommendation import ModelRecommender` - Only `get_model_recommendation_api` used
- `from config import ESP32_CAM_STREAM_URL` - Unused configuration constant

**Impact:** Cleaner imports, reduced dependency footprint
**Verified:** main.py imports successfully, all functionality preserved

#### 3. Update Documentation (Commit b5ae8ed)
Updated CODE_BLOAT_ANALYSIS.md to reflect completed cleanup work.

- Marked test file reorganization as complete
- Marked unused import removal as complete
- Updated all file references from `server/test_*.py` to `tests/test_*.py`

#### Summary
- **Lines saved:** ~10 lines in main.py
- **Files organized:** 2 test files moved
- **Documentation:** Updated to track completion
- **System status:** All changes verified, no breakage

#### Next Steps (From Analysis)
Medium-effort items for future consideration:
- Consolidate 6 HTML pages → Single-page app or template system (~500-700 lines)
- Split main.py into modular routes/ structure (maintainability improvement)
- Consolidate JavaScript apiCall() usage (app.js vs api-client.js)

---

### 2026-05-18: Synchronized Footer Counters (Commit 50dce80)

**Fixed Timing Mismatch Between Display and Actual Device Operation**

#### Problem
Duration counter on live stream footer was reaching zero several seconds before the device actually turned off. Root cause: client was calculating remaining time based on `session_elapsed_seconds` (time since session start) instead of using the server's actual device activation time.

#### Root Cause Analysis
- **Three independent timings** in the system:
  1. **Duration** = device activation time (how long sprinkler stays on) - 10 seconds
  2. **Active** = active_window_seconds (how long system monitors for detections) - 60 seconds  
  3. **Cooldown** = cooldown_period_seconds (lockout between sessions) - 120 seconds

- **The mismatch**: Duration counter was using `duration - session_elapsed_seconds`, but device activates AFTER session starts, causing drift
- **Result**: Counter hit 0 at T=10s while device actually turned off at T=10.5s (network delay)

#### Solution
Made counters use server's actual remaining times instead of client-side calculations:

1. **Server-side tracking**:
   - Added `device_activated_at` timestamp in Camera class
   - Calculates `device_remaining = activation_time + duration - current_time`
   - Sends `device_remaining` in status API (matching `session_remaining_seconds` and `cooldown_remaining`)

2. **Client-side display**:
   - Footer now uses `device_remaining` directly from server
   - Active counter uses `session_remaining_seconds` (already correct)
   - Cooldown uses `cooldown_period_seconds` (static value from config)
   - All three counters now reflect server's actual state

3. **Smooth countdown**:
   - Client locally decrements server values between updates (1s interval)
   - Keeps display smooth and responsive
   - Resynchronizes on each server update

#### Files Modified
- `server/camera_manager.py` - Added device activation timestamp tracking
- `server/main.py` - Calculate and send `device_remaining` in status response
- `web/app.js` - Use server values directly instead of local calculations
- `web/style.css` - Added `.footer-line` styling for multi-line footer

#### Testing
- Duration counter now reaches 0 exactly when device turns off
- No more desync between visual countdown and actual device timing
- Counters accurately reflect server's active session and device status

#### Key Learning
**Client and server should never be independent sources of truth for timing.** Server calculates actual remaining times; client displays and decrements locally for responsiveness but always respects server updates. Three separate counters need three separate server-calculated values.

---

### 2026-05-18: Sprinkler Control Reliability Framework (Commits 04edbc6, 76662d5, 0109059)

**Comprehensive Framework for Production-Ready Sprinkler Control**

#### Phase 1: Reliability Core
- **Retry Logic**: Automatic retry with exponential backoff (1s, 2s, 4s, 8s, 16s)
  - Distinguishes transient vs permanent errors
  - Max 3 retries for network issues
  - Fail-fast for authentication/quota errors
- **Startup Validation**: Credentials tested at initialization
  - Prevents runtime surprises
  - Sets credentials_valid flag
  - Clear error messages
- **Command Verification**: Read-back state checks after activation
  - Confirms valve actually changed state
  - Logs verification success/failure
  - Enhanced response data with latency

#### Phase 2: Monitoring & Observability
- **API Usage Tracker** (server/api_usage_tracker.py)
  - Tracks every API call with latency
  - Monthly quota estimation (10,000 calls/month free tier)
  - Warnings at 80% and 95% quota
  - Persistent stats (survives restart)

- **Activation Metrics** (server/activation_metrics.py)
  - Records success/failure of each activation
  - Calculates success rate and verification rate
  - Failure reason tracking
  - Last 100 activation history

- **Enhanced Logging**
  - API latency measurement (milliseconds)
  - Retry attempt logging
  - Structured log format for analysis
  - Separate API call log

#### Phase 3: Web Interfaces
- **Diagnostics Dashboard** (web/diagnostics.html)
  - One-click comprehensive system diagnostics
  - Tests: credentials, devices, valve, quota
  - Real-time results with status indicators
  - API endpoint: POST /api/diagnostics/run
  - URL: http://192.168.1.15:5000/diagnostics

- **Setup Configuration** (web/setup.html)
  - Browser-based credential management
  - Device discovery and selection
  - Valve testing (10-second activation)
  - Configuration saving
  - URL: http://192.168.1.15:5000/setup

- **System Health Panel**
  - Real-time health on main dashboard
  - Indicators: Credentials, Quota %, Success Rate, Latency
  - Color-coded status (green/yellow/red)
  - Auto-updates every 10 seconds

#### Phase 4: Documentation & Testing
- **Troubleshooting Guide** (SPRINKLER_TROUBLESHOOTING.md)
  - Common issues and solutions
  - Diagnostic steps
  - Performance optimization tips
  - Maintenance procedures

- **API Enhancements**
  - /api/health - System health status
  - /api/usage-stats - API quota tracking
  - /api/metrics - Activation performance
  - /api/diagnostics/run - Diagnostic tests
  - WebSocket events for real-time updates

- **Testing Framework**
  - Integration test suite (server/test_integration.py)
  - Mock API for testing without hitting real Tuya
  - Unit tests for retry logic, metrics, tracking

#### New Files Created:
1. server/device_manager.py (enhanced with retry & verification)
2. server/api_usage_tracker.py (API quota monitoring)
3. server/activation_metrics.py (performance metrics)
4. server/main.py (enhanced with new endpoints)
5. web/diagnostics.html (diagnostics dashboard)
6. web/setup.html (setup interface)
7. web/index.html (health panel added)
8. web/app.js (health panel logic)
9. web/style.css (new styles)
10. SPRINKLER_TROUBLESHOOTING.md (user guide)

#### Key Improvements:
✅ **Reliability**: Auto-retry transient failures, verify commands
✅ **Visibility**: Monitor quota before hitting limits
✅ **Usability**: Browser-based setup and diagnostics (no SSH needed)
✅ **Performance**: Track latency, identify bottlenecks
✅ **Maintainability**: Clear error messages, comprehensive logging
✅ **Production-Ready**: Self-healing, quota-aware, fully monitored

#### System Works Like iPhone App:
- Same Tuya Cloud API underneath
- Same quota limits (10,000 calls/month free)
- Automatic retry on transient failures
- Real-time status verification
- Command feedback and error handling

#### Usage:
- **Setup**: http://192.168.1.15:5000/setup (first time)
- **Monitor**: http://192.168.1.15:5000 (main dashboard)
- **Diagnose**: http://192.168.1.15:5000/diagnostics (troubleshooting)
- **API**: /api/health, /api/metrics, /api/usage-stats (programmatic)

### 2026-05-18: API Quota Timeline Tracking (Commit 8ab714a)
- **Feature:** Comprehensive API quota tracking with reset timeline metrics
- **Metrics Added:**
  - `reset_date`: Date when monthly quota was last reset (YYYY-MM-DD)
  - `days_since_reset`: Number of days elapsed since quota reset
  - `daily_burn_rate_pct`: Percentage of quota consumed per day (calculated)
  - `projected_depletion_date`: Estimated date when quota reaches 100%
- **Implementation:**
  - Added `reset_timestamp` tracking in APIUsageTracker
  - Persists reset_timestamp in api_stats.json for recovery after restart
  - Automatic reset_timestamp update when month changes
  - Dashboard tooltip shows reset date + burn rate + depletion estimate
  - Diagnostics page displays full timeline metrics
- **Benefit:** Users can now understand quota consumption patterns and plan ahead for renewal
- **Files Modified:**
  - server/api_usage_tracker.py - Reset timeline calculation
  - web/app.js - Health panel tooltip with timeline info
  - web/diagnostics.html - API statistics display with timeline metrics
  - server/test_integration.py - Use isolated tracker for test isolation

---

### 2026-03-25: Detection Gallery Filtering (Commit 9a03462)
- **Feature:** Gallery now only saves deer, cow, sheep detections (not cats, dogs, etc.)
- **Rationale:** Reduces clutter - other animals still trigger sprinkler but don't fill gallery
- **Implementation:** Added SAVE_CLASS_IDS config [17, 18, 19, 21] for filtering
- **Detection.py:** Added class_id field to detection data
- **Main.py:** Filters saves based on SAVE_CLASS_IDS before storage
- **Logging:** Shows "Detection not saved" for filtered animals vs "Detection image saved"
- **Status:** ✅ Gallery focused on meaningful detections only

### 2026-03-25: Phase 2 Optimization - Performance & Auto-cleanup (Commit 2100b22)
- **Performance:** Removed redundant /api/motion endpoint (motion via stream headers only)
- **Frontend:** HTTP polling now WebSocket-fallback only (90%+ reduction in requests)
- **Auto-cleanup:** Detection images auto-deleted after 7 days (prevents disk bloat)
- **Impact:** Reduced server load, managed disk space, cleaner API
- **Status:** ✅ System optimized for long-term operation

### 2026-03-25: Phase 1 Cleanup - Dead Code Removal & Security (Commit a098fab)
- **Security:** Moved Tuya credentials to .env file (no longer in git)
- **Dead Code:** Removed 100 lines (unused methods, imports, test blocks)
- **File Cleanup:** Deleted 26MB old log archive
- **Impact:** Secure credentials, cleaner codebase, 26MB disk space freed
- **Status:** ✅ Security hardened, code maintainability improved

### 2026-03-25: Last Detection Timestamp Enhancement (Commit ac736db)
- **Feature:** "Last Detection" dashboard field now shows last PIR motion detection
- **Display Format:** "March 25 2026 7:37:43 PM" (full date + 12-hour time)
- **Behavior:** Updates in real-time when PIR detects motion, persists until next detection
- **Implementation:** Timestamp tracked when motion_active changes from false to true
- **Status:** ✅ Provides clear visual feedback of most recent motion event

### 2026-03-25: PIR Motion Sensor Integration (Commit cbc440b)
- **Feature:** Added HC-SR501 PIR sensor on GPIO 14
- **Implementation:** PIR status embedded in MJPEG stream headers (`X-PIR-Status: active/inactive`)
- **Architecture:** Server parses PIR status from video stream - no separate connection needed
- **Advantages:**
  - Works within ESP32's single-connection limitation
  - Real-time updates with every frame (~30 FPS)
  - No additional network overhead
  - Always available when camera is streaming
- **Bug Fixes:** Removed non-functional "Tuning Mode" feature from Gemini's implementation
- **Status:** ✅ Fully operational - PIR sensor provides continuous real-time motion feedback

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
- **Troubleshooting:** `SPRINKLER_TROUBLESHOOTING.md`

---

**For detailed history and technical wins, see previous versions of this file in git history.**
