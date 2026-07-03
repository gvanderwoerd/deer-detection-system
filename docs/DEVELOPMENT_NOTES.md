# Development Notes - Deer Detection System

**Purpose:** Track issues, solutions, and learnings for AI agent reference
**Last Updated:** 2026-07-03
**Instructions for AI Agents:** Add new session learnings to this file after troubleshooting or implementing features

---

## Hardware: ESP32-CAM Troubleshooting

### Critical Settings

**WiFi Power Requirements:**
- ⚠️ **MUST use 20dBm (full power)** for reliable streaming
- 8.5dBm (low power mode) causes HTTP server timeouts
- Symptoms: Camera boots (LED pattern correct) but HTTP requests timeout
- Fix: Set `WiFi.setTxPower(WIFI_POWER_19_5dBm)` in firmware

**Firmware Compatibility:**
- All cameras MUST use identical firmware (except hostname/IP)
- Inconsistent settings cause instability
- Required settings:
  - Resolution: SVGA (800x600)
  - JPEG Quality: 10
  - Frame Buffers: 2
  - Frame Rate: 30 FPS
  - WiFi Power: 20dBm

**LED Behavior Patterns:**
- **Normal startup:** 3 blinks → 5 blinks → 7 blinks → slow blinks
- **After server connects:** LED goes OFF (this is normal!)
- **Fast continuous blinking:** System failure during initialization
- Do NOT expect continuous slow blinking when dashboard is connected

### Hardware Quality Issues

**CanadaRobotix ESP32-CAM Units:**
- Tend to require extra troubleshooting vs other suppliers
- May work intermittently on first power-up
- Power cycling multiple times often resolves issues
- Keep spare units and proven power supplies for testing

**Debugging Process:**
1. Verify firmware matches working units (compare line-by-line)
2. Test with known-good 1.5A+ power supply
3. Check network: `ping esp32cam.local` (should work) vs HTTP (may timeout)
4. Compare LED behavior with working cameras
5. Power cycle 3-5 times if needed
6. Check WiFi signal strength in dashboard (-26 dBm is excellent, -60+ is poor)

---

## Software: Common Issues & Solutions

### Thread Leak - Critical Memory/CPU Issue (2026-07-03)

**Problem:** Server accumulated 66 threads over 36 hours, causing CPU overload (259% constantly)

**Symptoms:**
- Thread count growing from expected ~10-20 to 66+
- High CPU usage accumulating over time (2194+ minutes CPU time)
- Cameras timing out intermittently
- Server appearing "overloaded" despite normal operations

**Root Cause:**
Worker threads (`capture_worker` and `detection_worker`) never cleaned up their dictionary entries when exiting:
```python
# Before - BUG: No cleanup
def capture_worker():
    logger.info("Starting...")
    while camera_id in self.cameras:
        # ... work ...
    logger.info("Stopped")  # Dictionary entry still exists!
```

**Why It Happened:**
- Threads added to `self.capture_threads[camera_id]` and `self.detection_threads[camera_id]`
- When threads crashed, timed out, or exited normally, entries remained
- Over days of operation, zombie thread references accumulated
- Race condition fix (July 1) prevented duplicate starts but didn't address cleanup

**Solution - Thread Lifecycle Management:**
```python
# After - FIXED: Always cleanup
def capture_worker():
    try:
        logger.info("Starting...")
        while camera_id in self.cameras:
            # ... work ...
    finally:
        # Guaranteed cleanup even on exception
        if camera_id in self.capture_threads:
            del self.capture_threads[camera_id]
        logger.info("Stopped")
```

**Additional Fix:**
Changed `detection_worker` from `while True:` to `while camera_id in self.cameras:` to allow graceful exit when camera is deleted.

**Diagnosis Commands:**
```bash
# Check current thread count (expected: ~10-20 for 3 cameras)
ps -T -p $(pgrep -f "python3 main.py") | wc -l

# Monitor for leak (count should stay constant)
for i in {1..6}; do
    echo "Check $i: $(ps -T -p $(pgrep -f 'python3 main.py') | wc -l) threads"
    sleep 10
done

# Check if CPU time is proportional to runtime
ps aux | grep "python3 main.py"
# Normal: 290% CPU after 5 min = ~15 min CPU time
# Leak: 259% CPU after 36 hours = 2194 min CPU time (disproportionate)
```

**Results:**
- Thread count stable at 68-69 (verified over 60+ seconds)
- CPU usage proportional to runtime (not accumulating)
- All cameras streaming reliably

**Lesson:** Always use try/finally for resource cleanup in long-running threads. Thread dictionary entries are resources that need explicit management. The `finally` block guarantees execution even during exceptions or crashes.

**Files Modified:** `server/camera_manager.py` (capture_worker, detection_worker)

---

### Timestamp Rendering

**Problem:** Timestamps flashing on/off during live stream

**Root Cause:** Timestamp applied once per second, other 29 frames had no timestamp

**Solution:**
- Separate timestamp text update (1 Hz) from rendering (30 Hz)
- Store timestamp text in variable: `current_timestamp`
- Apply stored timestamp to EVERY frame
- Re-encode all frames as JPEG after timestamp overlay

**Code Pattern:**
```python
# Update timestamp text once per second
if time.time() - last_update >= 1.0:
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_update = time.time()

# Apply to EVERY frame (30 FPS)
cv2.putText(frame, current_timestamp, ...)
```

**Commit:** 00cf6fd

### MJPEG Stream Reconnection

**Problem:** Black screen when navigating back to dashboard (SPA navigation issue)

**Root Cause:**
- Browser caching prevents stream reconnection
- Cache-busting query params insufficient
- `<img>` src change doesn't trigger reload after SPA navigation

**Solution:** Use Page Visibility API
```javascript
document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
        // Force stream reload when page becomes visible
        const stream = document.getElementById('stream');
        const currentSrc = stream.src.split('?')[0];
        stream.src = `${currentSrc}?t=${Date.now()}`;
    }
});
```

**Commit:** 00cf6fd

### Session State Management

**Problem:** Sprinkler not activating after server restart (stuck at max 3/3 detections)

**Root Cause:**
- `session_active=true` loaded from cameras.json
- `session_start` timestamp NOT persisted
- Expiry check failed, session appeared permanently active

**Solution:**
- Always validate restored state against runtime requirements
- Reset state that depends on non-persisted data
- Add startup validation:
```python
# On server startup, reset stale sessions
if camera.session_active and not hasattr(camera, 'session_start'):
    camera.session_active = False
    camera.session_count = 0
    logger.info(f"Reset stale session for {camera.name}")
```

**Commit:** 00cf6fd

### API Path Bugs

**Problem:** "Cloud Sync Failed: unexpected token"

**Root Cause:** Double `/api` prefix in fetch call
```javascript
// WRONG - results in /api/api/devices/refresh
const result = await apiCall('/api/devices/refresh', 'POST');

// CORRECT - apiCall() already adds /api prefix
const result = await apiCall('/devices/refresh', 'POST');
```

**Fix:** Remove `/api` prefix when using `apiCall()` wrapper function

**Commit:** SESSION_2026-06-13

### Modal Scrolling Issues

**Problem:** Long device lists extend beyond viewport, require zoom out

**Solution:** Add scrolling constraints
```css
.modal-content {
    max-height: 90vh;
    overflow-y: auto;
}

.device-assignments {
    max-height: 400px;
    overflow-y: auto;
}
```

---

## Configuration Best Practices

### Camera Configuration (cameras.json)

**Recommended Settings:**
- Detection Confidence: 0.25 (lower = more sensitive)
- Active Window: 60 seconds (how long to keep detecting)
- Cooldown: 120 seconds (delay before next activation)
- Max Detections/Session: 3 (prevent over-watering)

### Remote Access Options

**Recommended: Tailscale**
- Zero-config VPN mesh network
- 5-minute setup, free for personal use
- Most secure and easiest option
- Installation: `curl -fsSL https://tailscale.com/install.sh | sh`

**Alternative: Progressive Web App**
- Make dashboard installable on mobile
- Requires remote access solution (Tailscale, Cloudflare, etc.)
- Add manifest.json and service worker

**Alternative: Cloudflare Tunnel**
- Public URL with reverse proxy
- Requires domain name (~$12/year)
- More complex setup

---

## Project Portability (2026-06-19)

### Virtual Environment Optimization

**Issue:** PyTorch installed with CUDA libraries (5.4GB) on CPU-only system

**Solution:** Hardware auto-detection
- Created `requirements-cpu.txt` (1.7GB install)
- Created `requirements-gpu.txt` (5.4GB install)
- `start.sh` detects GPU via `nvidia-smi`
- Auto-installs optimal version

**Savings:** 68% reduction (5.4GB → 1.7GB for CPU-only systems)

### Location Portability

**Issue:** Moving project breaks venv (hardcoded paths in pyvenv.cfg)

**Solution:** Automatic rebuild on location change
- `start.sh` detects path mismatch
- Shows progress bar during rebuild
- Preserves all dependencies via requirements files

**Result:** Project now fully portable across locations and hardware

---

## Future Enhancement Ideas

### Planned
- Assign sprinkler valves to Camera 3 (Rear Flower Garden)
- Configure detection objects for Camera 3
- Monitor Camera 3 stability over time

### Under Consideration
- Native iOS app (reuse REST APIs)
- Additional ESP32-CAM units for full yard coverage
- Detection analytics dashboard

---

## System State Reference

### Active Cameras (as of 2026-06-13)

1. **Default Camera** (esp32cam.local)
   - Location: Back yard
   - IP: 192.168.1.100
   - Sprinkler: Back flowers (30s duration)

2. **Front Garden** (esp32cam-back.local)
   - Location: Front yard
   - IP: 192.168.1.101
   - Sprinkler: Front Flowers (30s duration)

3. **Rear Flower Garden** (esp32cam-rear.local)
   - Location: Rear yard
   - IP: 192.168.1.102
   - Sprinkler: Not assigned

### Sprinkler Valves (6 total)

- Back flowers → Camera 1
- Front Flowers → Camera 2
- Back Long Flowers → Unassigned
- Avalon Tap (grass) → Unassigned
- Front Grass → Unassigned
- Kitchen Valve → Unassigned

---

## Useful Commands

```bash
# Start/stop system
./start.sh
./stop.sh

# Check server status
ps aux | grep "python3 main.py"
lsof -i :5000

# View logs
tail -f logs/server.log

# Git workflow
git add <files>
git commit -m "type: description"
git push

# Check camera status
curl http://192.168.1.15:5000/api/cameras

# Test ESP32-CAM
ping esp32cam.local
curl -I http://esp32cam.local:81/stream
```

---

## Instructions for AI Agents

**When troubleshooting or implementing features:**

1. ✅ **Read this file first** - Check if issue was solved before
2. ✅ **Document new learnings** - Add solutions to relevant sections
3. ✅ **Update system state** - Keep camera/valve info current
4. ✅ **Reference commits** - Link to git commits for context
5. ✅ **Keep it organized** - Use existing section structure

**What to document:**
- Hardware quirks discovered
- Software bugs and their fixes
- Configuration changes and why
- Performance optimizations
- Failed approaches (what NOT to do)

**What NOT to document:**
- Routine tasks (standard git operations, etc.)
- Obvious solutions (restart server, clear cache)
- Duplicate information already in README or troubleshooting guide

---

**Last session:** 2026-06-19 - Project optimization and portability improvements
**Status:** ✅ All systems operational
