# Session Notes - Deer Detection System

## 2026-05-23 - Timestamp & Remote Access Session

### Issues Resolved

1. **Front Garden Camera - Missing Timestamps**
   - Timestamps were flashing on/off
   - Fixed by applying timestamp to every frame (not just once per second)
   - Commit: 00cf6fd

2. **Default Camera - Sprinkler Not Activating**
   - Detection session was stuck at 3/3 after server restart
   - Fixed by resetting stale sessions on startup
   - Session start timestamp not persisted, causing expiry check to fail
   - Commit: 00cf6fd

3. **Video Streams - Black Screen After Navigation**
   - Streams not reconnecting when returning from manage cameras page
   - Fixed with page visibility API event listeners
   - Commit: 00cf6fd

### Key Learnings

**Timestamp Rendering Best Practice:**
- Separate text update frequency (1 Hz) from rendering frequency (30 Hz)
- Store timestamp text in variable, apply to every frame
- Prevents flickering while maintaining accurate time updates

**Session State Management:**
- Always validate restored state against runtime requirements
- Reset state that depends on non-persisted data (like session_start)
- Log state resets for debugging

**MJPEG Stream Reconnection:**
- Browser caching can prevent stream reconnection
- Cache-busting query params not sufficient for SPA navigation
- Page Visibility API provides reliable reconnection triggers

### Server Status

**Location:** /mnt/linux-data/deer-detection-system
**Server URL:** http://192.168.1.15:5000
**Current Branch:** main
**Last Commit:** 00cf6fd (pushed to GitHub)

**Cameras:**
- Default Camera (esp32cam.local) - Back yard, sprinkler control
- Front Garden (esp32cam-back.local) - Front yard monitoring

### Remote Access Discussion

User wants iPhone app for remote (offsite) access. Options discussed:

1. **Tailscale (RECOMMENDED)**
   - Zero-config VPN mesh network
   - 5-minute setup, free for personal use
   - Most secure and easiest option
   - Install: `curl -fsSL https://tailscale.com/install.sh | sh`

2. **Progressive Web App**
   - Make existing dashboard installable on iPhone
   - Requires remote access solution (Tailscale, Cloudflare, etc.)
   - Add manifest.json and service worker

3. **Cloudflare Tunnel**
   - Public URL with reverse proxy
   - Requires domain name ($12/year)
   - More complex setup

4. **Native iOS App**
   - Most powerful but requires Swift development
   - Could reuse existing REST APIs

**Next Steps (if user wants remote access):**
- Install Tailscale on Linux Mint server
- Install Tailscale iOS app
- Test remote access
- Optionally convert to PWA for app-like experience

### Useful Commands

```bash
# Start server
cd /mnt/linux-data/deer-detection-system/server
python3 main.py

# Check server status
ps aux | grep "python3 main.py"

# View logs
tail -f /tmp/deer-server.log

# Git workflow
git add server/camera_manager.py web/app.js
git commit -m "fix: description"
git push

# Check camera status
curl http://192.168.1.15:5000/api/cameras
```

### Known Issues / Future Improvements

- None currently - all reported issues resolved

### Project Structure

```
deer-detection-system/
├── server/
│   ├── main.py              # Flask server, API endpoints
│   ├── camera_manager.py    # Multi-camera handling, timestamp overlay
│   ├── detection.py         # YOLOv8 object detection
│   ├── cameras.json         # Camera configurations (not committed)
│   └── detections/          # Saved detection images
├── web/
│   ├── index.html          # Main dashboard
│   ├── app.js              # Frontend logic, page visibility handling
│   └── style.css           # Styling
├── esp32-cam/              # Default camera firmware
└── esp32-cam2/             # Front Garden camera firmware
```

### Configuration Files (Not in Git)

- `server/cameras.json` - Camera state and config
- `server/.env` - API credentials (Tuya, etc.)
- `server/detections/` - Detection images

---

**Session Closed:** 2026-05-23
**All changes committed and pushed to GitHub**
