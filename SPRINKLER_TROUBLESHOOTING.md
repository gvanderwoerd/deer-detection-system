# Sprinkler Control Troubleshooting Guide

**Last Updated:** 2026-05-18
**Framework Version:** Phase 1-4 Complete

---

## Quick Diagnostics

**Before doing anything else, run the automated diagnostics:**
1. Open http://192.168.1.15:5000/diagnostics
2. Click "Run Diagnostics"
3. Review the results - they will tell you exactly what's wrong

The diagnostics test:
- ✓ API Credentials (valid/invalid)
- ✓ Device Discovery (can find valves)
- ✓ Primary Valve (online/offline)
- ✓ Valve Activation (can turn on/off)
- ✓ API Quota (quota remaining)

---

## Common Issues & Solutions

### Issue #1: "Invalid Credentials - Please check setup"

**Symptoms:**
- Dashboard shows red banner: "⚠️ Invalid Credentials"
- Diagnostics fail at first step
- Cannot discover devices

**Causes & Solutions:**

**Solution A: Missing or incorrect API Key/Secret**
1. Go to http://192.168.1.15:5000/setup
2. Re-enter your Tuya API Key and Secret
3. Verify you copied them correctly from https://developer.tuya.com
4. Click "Validate Credentials"
5. If still failing, create new credentials in Tuya portal

**Solution B: Wrong region selected**
1. Check which region your Tuya account is in
2. Go to setup page
3. Select correct region (us/eu/cn/in)
4. Validate again

**Solution C: Credentials expired**
1. Log into https://developer.tuya.com
2. Check if subscription is active
3. Renew if expired
4. Get new API Key and Secret
5. Update via setup page

**Solution D: Trial account quota exhausted**
- Free tier has limited API calls
- If using trial account, upgrade to paid plan
- Or wait until next month for quota reset

---

### Issue #2: "No devices found" or "Valve offline"

**Symptoms:**
- Diagnostics pass credentials test
- Device discovery fails or finds 0 devices
- Dashboard shows: "Valve: Unknown" or "Offline"

**Causes & Solutions:**

**Solution A: Valve is powered off**
1. Check physical power to SmartLife valve
2. Verify valve has stable WiFi connection
3. Power cycle valve (off for 10s, back on)
4. Wait 30 seconds for it to reconnect
5. Run diagnostics again

**Solution B: Valve not linked to SmartLife app**
1. Open SmartLife mobile app
2. Check if valve appears in your device list
3. If not, pair it first:
   - Add Device in app
   - Scan QR code or enter device ID
   - Follow pairing steps
4. Once paired in app, try setup page again

**Solution C: Valve on different WiFi network**
- This is expected! Valve is on IoT network, server is on main network
- SmartLife app works the same way (uses Tuya Cloud API)
- This is why cloud API is required, not a problem

**Solution D: Static IP needs reconfiguration**
1. Check router's IP assignments
2. Verify valve still has its assigned IP
3. If changed, update static IP assignment
4. Or use device rediscovery in setup page

---

### Issue #3: "Sprinkler command sent but could not verify"

**Symptoms:**
- Valve turns on/off but dashboard shows "⚠ Unverified"
- Diagnostics shows "warn" instead of "pass"
- Activations sometimes don't trigger

**Causes & Solutions:**

**Solution A: Network latency issue**
- Verification checks device state 0.5s after command
- If WiFi is slow, device may not respond in time
- **Not critical** - valve still works, just can't confirm
- Network usually stabilizes after a few seconds
- Wait and retry if needed

**Solution B: Valve firmware issue**
1. In SmartLife app, check if firmware update available
2. Update valve firmware if available
3. Re-test activation

**Solution C: API latency is high**
- Check `/api/usage-stats` endpoint
- If "avg_latency" is >1000ms, network is slow
- Can still control valve, just slower
- Try restarting both server and valve

---

### Issue #4: "API Quota Exceeded" or "Trial account limit reached"

**Symptoms:**
- Diagnostics shows red: "✗ API Quota"
- Dashboard banner: "🔴 API Quota Exceeded"
- Sprinkler activations fail with "quota" error
- Cannot discover devices

**Causes & Solutions:**

**Solution A: Exceeded free tier quota**
1. Free tier = 10,000 API calls/month
2. Check dashboard: `/api/usage-stats`
3. If >10,000 calls this month, quota exhausted
4. **Options:**
   - Wait until next calendar month for reset
   - Upgrade to paid tier in Tuya console
   - Reduce polling frequency (if custom code)

**Solution B: Trial account limit reached**
1. Trial accounts have strict quotas (often 1,000-5,000 calls)
2. Convert to paid account
3. Or wait for trial reset (monthly)

**Solution C: Account suspended**
1. Log into https://developer.tuya.com
2. Check account status
3. May need to verify payment method or add credit

**Prevention:**
- Dashboard monitors quota and warns at 80% and 95%
- API calls logged with timestamps for tracking
- Check `/api/usage-stats` weekly to see usage trends

---

### Issue #5: "Sprinkler won't activate during detection"

**Symptoms:**
- Dashboard shows detection happening
- No sprinkler activation occurs
- Event log shows "Failed to activate sprinkler"
- Manual activation works fine

**Causes & Solutions:**

**Solution A: Person detected (safety check)**
- System prevents activation if person in frame
- This is by design for safety
- Move out of camera view
- Try again

**Solution B: Cooldown period active**
- After activation, 2-minute cooldown prevents next activation
- Check dashboard: "Cooldown: 45s remaining"
- Wait for cooldown to complete
- Then trigger detection again

**Solution C: Session limit reached**
- Max 3 activations per detection session
- Session lasts 60 seconds of motion
- After 3rd activation, must wait for motion to stop
- Motion must be inactive for >60s to reset
- Then can detect again

**Solution D: Valve offline during detection**
- Valve was online but went offline
- May have lost WiFi temporarily
- Check valve is powered and connected
- Wait 30s for reconnection
- Try again

---

### Issue #6: "Can't access dashboard" or "Server won't start"

**Symptoms:**
- Cannot reach http://192.168.1.15:5000
- Browser shows "Connection refused" or "Timed out"
- Server logs show errors

**Causes & Solutions:**

**Solution A: Server not running**
1. Check if server is running:
   ```bash
   cd /mnt/linux-data/deer-detection-system
   lsof -i :5000
   ```
2. If no process shown, server is stopped
3. Start server:
   ```bash
   ./start.sh
   ```
4. Wait 5 seconds for startup
5. Try accessing dashboard again

**Solution B: Port 5000 in use**
1. Another process is using port 5000
2. Kill stuck processes:
   ```bash
   ./stop.sh
   sleep 2
   ./start.sh
   ```
3. If still fails, reboot:
   ```bash
   sudo reboot
   ```

**Solution C: Network/IP address wrong**
1. Verify server IP address:
   ```bash
   hostname -I
   ```
2. Should show 192.168.1.15 (or your configured IP)
3. Try accessing with correct IP
4. If IP changed, update in DHCP or use static IP

**Solution D: Firewall blocking**
1. Check if port 5000 is open:
   ```bash
   sudo iptables -L | grep 5000
   ```
2. If blocked, open it:
   ```bash
   sudo ufw allow 5000
   ```

---

## Performance Issues

### Slow Detection Response

**Symptoms:**
- Detections take >5 seconds to trigger sprinkler
- Dashboard feels sluggish
- API calls are slow

**Solutions:**
1. Check `/api/usage-stats` for latency
2. If avg_latency >1000ms:
   - Internet connection may be slow
   - Tuya cloud servers may be slow
   - Wait a few seconds and try again
3. Check server logs:
   ```bash
   tail -50 logs/server.log
   ```
4. Look for "Retry attempt" messages - indicates network issues

### High API Quota Usage

**Symptoms:**
- API quota consumed too fast
- Dashboard shows 50%+ usage already

**Solutions:**
1. Check usage breakdown:
   ```bash
   curl http://localhost:5000/api/usage-stats | python3 -m json.tool
   ```
2. Review endpoint breakdown
3. Common culprits:
   - Excessive status polling (should be cached)
   - Device discovery running too often
   - Metric collection frequency

### Detection Gallery Growing Too Large

**Symptoms:**
- Dashboard slow
- Disk space running out
- Gallery loads slowly

**Solutions:**
1. Gallery auto-deletes after 7 days
2. Manually clean older detections:
   ```bash
   curl -X POST http://localhost:5000/api/detections/delete -H "Content-Type: application/json" -d '{"age_filter":"week"}'
   ```
3. Valid filters: all, year, month, week, day, hour, 10min

---

## Getting Help

### Check These First:
1. Run diagnostics: http://192.168.1.15:5000/diagnostics
2. View health panel: http://192.168.1.15:5000
3. Check API stats: http://192.168.1.15:5000/api/usage-stats
4. Review logs: `tail -100 /mnt/linux-data/deer-detection-system/logs/server.log`

### Provide This Info When Asking for Help:
```bash
# Diagnostics results
curl http://localhost:5000/api/diagnostics/run | python3 -m json.tool

# Health status
curl http://localhost:5000/api/health | python3 -m json.tool

# API usage
curl http://localhost:5000/api/usage-stats | python3 -m json.tool

# Recent logs (last 30 lines)
tail -30 /mnt/linux-data/deer-detection-system/logs/server.log
```

### Emergency Reset

If everything is broken:
```bash
# Stop server
cd /mnt/linux-data/deer-detection-system
./stop.sh

# Clean state
rm -f logs/*.log logs/*.json

# Restart
./start.sh

# Wait 10 seconds
sleep 10

# Check health
curl http://localhost:5000/api/health
```

---

## Maintenance

### Weekly:
- Check `/api/usage-stats` to monitor quota usage
- Review dashboard for any warnings
- Verify sprinkler activates when triggered

### Monthly:
- If using trial account, renew credentials before quota resets
- Check SmartLife app for any firmware updates for valve
- Review detection gallery, clean up old detections

### Quarterly:
- Review PROJECT_LOG.md for any firmware updates
- Check FIRMWARE_NOTES.md if considering ESP32 changes
- Test full detection → activation → cooldown flow

---

## Key Differences from iPhone SmartLife App

**You have:**
- ✓ Same Tuya Cloud API as iPhone
- ✓ Same valve control mechanism
- ✓ Same device discovery
- ✓ Same quota limits

**You don't have:**
- ✗ Real-time app notifications (use dashboard instead)
- ✗ Mobile app UI (use web dashboard instead)
- ✗ Multiple valve management (for now - can add)

**You have MORE than iPhone:**
- ✅ Automated detection (AI + PIR sensor)
- ✅ Real-time monitoring dashboard
- ✅ API quota tracking and warnings
- ✅ Comprehensive diagnostics
- ✅ Performance metrics and health status

---

## Summary

The system is designed to be **self-healing**:
- ✓ Retries transient failures automatically
- ✓ Validates credentials at startup
- ✓ Verifies commands succeeded
- ✓ Tracks quota to prevent surprises
- ✓ Provides clear error messages

If something goes wrong:
1. **Run diagnostics first** - It will tell you what's wrong
2. **Check the solution** - Most issues are covered above
3. **Restart if needed** - Often fixes temporary issues
4. **Collect logs** - If you need help

For questions: See PROJECT_LOG.md for architecture and VERSION_SNAPSHOT.md for current state.
