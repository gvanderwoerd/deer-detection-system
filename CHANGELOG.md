# Changelog - Deer Detection System

## 2026-05-23 - Multi-Camera Fixes & Camera Flip Controls

### 🐛 Bug Fixes

**Multi-Camera Detection Session Triggering**
- **Issue:** Second camera (Front Garden) motion detection not triggering detection sessions
- **Root Cause:** Global motion state variable in `main.py` prevented per-camera motion tracking
  - When camera A had motion=true, camera B's motion=true wouldn't trigger (no state change detected)
- **Fix:** Added `camera_motion_states` dictionary for per-camera motion tracking
- **Impact:** Both cameras now independently trigger detection sessions on PIR motion
- **Files:** `server/main.py` (lines 124, 195-203), `server/camera_manager.py` (lines 468-472)

**Video Stream Black Screen After Navigation**
- **Issue:** Camera streams show black screen when navigating back from other pages
- **Root Cause:** Browser caching MJPEG stream connections without reconnecting
- **Fix:** Added timestamp query parameter to video URLs for cache-busting
- **Implementation:** `videoUrl = /video_feed/${camera.id}?t=${Date.now()}`
- **Files:** `web/app.js` (line 1038)

### ✨ New Features

**Camera Flip Controls (Server-Side Image Transformation)**
- Added per-camera 180° rotation controls via web UI
- **UI Component:** Rotation button (🔄) overlaid on each camera stream
- **Implementation:** Server-side OpenCV transformation (`cv2.rotate(ROTATE_180)`)
- **Configuration:** Settings stored in `cameras.json` under `display.flip_vertical`
- **API Endpoint:** `POST /api/cameras/<camera_id>/flip` with `{type: 'vertical'}`
- **Benefits:**
  - No firmware reflashing required
  - Settings persist across server restarts
  - Fixes upside-down camera mounting issues
  - Per-camera independent configuration
- **Files:**
  - `server/camera_manager.py` - Added `display` config, `apply_flip()` method
  - `server/main.py` - Added `/api/cameras/<camera_id>/flip` endpoint
  - `web/app.js` - Added `toggleFlip()` function, rotation button in camera cards
  - `web/style.css` - Added `.flip-btn` and `.camera-controls` styling

### 📚 Hardware Troubleshooting Documentation

**ESP32-CAM Performance Issues - Defective Camera Module**

**Symptoms:**
- High ping latency (200-400ms instead of <10ms)
- Unresponsive HTTP server (timeouts)
- Slow/choppy video stream
- Missing timestamp overlays

**Common Misdiagnosis:**
- ❌ Power supply issues (but camera works on multiple supplies)
- ❌ ESP32 board defect (but multiple ESP32s show same issue)
- ❌ Firmware bugs (but firmware is identical to working camera)

**Actual Root Cause:** Defective OV2640 camera module
- Bad camera sensor causes ESP32 CPU to struggle processing frames
- Results in high CPU usage affecting network response and HTTP server
- Problem follows the camera module, not the ESP32 board or power supply

**Diagnostic Process:**
1. Test ping latency to ESP32 (should be <10ms, defective shows >100ms)
2. Test HTTP server direct access (should respond instantly, defective times out)
3. Swap power supplies between cameras (eliminates power as cause)
4. Flash new ESP32 with same firmware (eliminates ESP32 board as cause)
5. Swap camera modules between ESP32 boards (problem follows camera = defective module)

**Solution:** Replace OV2640 camera module

**Key Learning:** When ESP32-CAM shows persistent slow performance despite good power supply, suspect the camera module hardware before the ESP32 board itself.

### 🔧 Technical Details

**Multi-Camera Motion Tracking Implementation:**
```python
# Before (buggy):
if camera.motion_active != self.motion_active:
    self.motion_active = camera.motion_active
    # Only triggers when different from LAST camera's state

# After (fixed):
prev_motion = self.camera_motion_states.get(camera.camera_id, False)
if camera.motion_active != prev_motion:
    self.camera_motion_states[camera.camera_id] = camera.motion_active
    # Triggers when THIS camera's state changes
```

**Camera Flip Implementation:**
```python
def apply_flip(self, frame):
    """Apply 180-degree rotation if flip is enabled"""
    if frame is None:
        return frame

    if self.display.get('flip_vertical', False):
        return cv2.rotate(frame, cv2.ROTATE_180)

    return frame
```

Applied in capture worker after frame decode, before timestamp overlay.

### 📝 Configuration Changes

**cameras.json Schema Update:**
```json
{
  "display": {
    "flip_vertical": false,
    "flip_horizontal": false
  }
}
```

Added to each camera configuration. Currently only `flip_vertical` is implemented (180° rotation).

---

## Previous Changes

See commit history for earlier changes:
- 2026-05-18: Code cleanup and documentation consolidation
- 2026-04-11: WiFi signal strength indicator
- 2026-03-25: PIR motion sensor via MJPEG headers
- 2026-03-14: Firmware restoration and brownout fixes
