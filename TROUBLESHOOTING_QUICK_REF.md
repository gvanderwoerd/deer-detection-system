# Deer Detection System - Quick Troubleshooting Reference

## Common Issues & Solutions

### ❌ Browser Shows "Connection Refused" After Running start.sh

**Symptoms:**
- `start.sh` appears to complete successfully
- Browser opens but shows "localhost refused to connect" or "This site can't be reached"
- Server log shows "Address already in use" but also "Running on..."

**Root Cause:**
Multiple server instances running simultaneously, causing port conflicts.

**Solution:**
```bash
# Stop all existing instances
./stop.sh

# Wait a moment
sleep 2

# Start fresh
./start.sh

# If prompted about existing server, choose 'y' to kill and restart
```

**Verification:**
```bash
# Check server is running
lsof -i :5000

# Test API
curl http://localhost:5000/api/status

# Should show server process and return JSON status
```

---

### ⚠️ Server Won't Start - Port Already in Use

**Solution:**
```bash
# Check what's using port 5000
lsof -i :5000

# Kill all processes on port 5000
lsof -ti:5000 | xargs kill -9

# Verify port is free (should return nothing)
lsof -i :5000

# Start server
./start.sh
```

---

### 📹 Camera Shows "Waiting for camera..."

**This is NORMAL if ESP32-CAM is offline/unplugged.**

The server gracefully handles the camera being offline:
- Attempts reconnection every 5 seconds
- Logs: "Frame capture error: No route to host"
- Dashboard remains functional
- Will automatically reconnect when camera comes online

**To verify ESP32-CAM is the issue:**
```bash
curl -I http://192.168.1.16:81/stream
# Expected: Timeout or "No route to host" if camera is off
# Expected: HTTP 200 OK if camera is working
```

**Fix:** Power on/connect the ESP32-CAM hardware.

---

### 🔌 SmartLife Valves Show Offline

**First Step:**
Check if devices are actually online in the SmartLife mobile app.

**Force Refresh:**
```bash
curl -X POST http://localhost:5000/api/devices/refresh
```

Or use the "Refresh" button in the Device Manager dashboard at:
http://localhost:5000/devices

---

### 🛑 Emergency Stop

**Stop everything immediately:**
```bash
# Web API
curl -X POST http://localhost:5000/api/devices/emergency_stop

# Or use stop script
./stop.sh
```

---

## Quick Commands

### Check Status
```bash
# Is server running?
lsof -i :5000

# View logs in real-time
tail -f logs/server.log

# Check system status via API
curl http://localhost:5000/api/status | python3 -m json.tool

# List all devices
curl http://localhost:5000/api/devices | python3 -m json.tool
```

### Start/Stop
```bash
# Start system
./start.sh

# Stop system
./stop.sh

# Restart (stop then start)
./stop.sh && sleep 2 && ./start.sh
```

### Access Dashboard
- **Main Dashboard:** http://localhost:5000 or http://192.168.1.15:5000
- **Device Manager:** http://localhost:5000/devices

---

## Maintenance Log

### 2026-02-16: Multiple Instance Issue
- **Issue:** Two server processes created simultaneously (PIDs 2993, 5278)
- **Impact:** Port conflict, browser couldn't connect
- **Fix:** Enhanced `start.sh` to verify instance cleanup
- **Prevention:** Always use `./stop.sh` before restarting

---

## Need More Help?

See full documentation in:
- `PROJECT_LOG.md` - Complete project history and architecture
- `README.md` - System overview and setup instructions
- `logs/server.log` - Real-time server logs

**Check server health:**
```bash
curl http://localhost:5000/api/status
```

Should return JSON with:
```json
{
    "enabled": true,
    "state": "idle",
    "valve_configured": true,
    ...
}
```
