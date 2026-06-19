# Camera 3 Setup - Rear Flower Garden

**Created:** 2026-05-25
**Status:** Ready for upload

---

## Camera Configuration

**Name:** Rear Flower Garden
**Hostname:** esp32cam-rear.local
**IP Address:** 192.168.1.102
**Stream URL:** http://192.168.1.102:81/ or http://esp32cam-rear.local:81/

---

## Upload Firmware

### Step 1: Connect ESP32-CAM to Computer

1. Insert ESP32-CAM into MB Programmer board
2. Connect USB cable to computer
3. Verify connection (LED should light up)

### Step 2: Upload Firmware

```bash
cd /mnt/linux-data/deer-detection-system/esp32-cam3
pio run --target upload
```

**Expected Upload:**
- Compile time: ~5-10 seconds
- Upload time: ~100 seconds
- Final size: ~860KB

### Step 3: Watch LED Pattern

After upload completes, the ESP32 will reboot and show:

1. **3 quick blinks** = Boot successful
2. **5 quick blinks** = Camera initialized
3. **7 quick blinks** = WiFi connected
4. **Slow blink (every 1 second)** = System running normally

✅ If you see all 4 patterns, the camera is working!

### Step 4: Test Camera Stream

Open browser and test:
- http://192.168.1.102:81/
- OR http://esp32cam-rear.local:81/

You should see the live camera feed.

---

## Server Integration (Automatic)

The server's multi-camera system will **automatically detect** the new camera when it comes online. No server-side configuration needed!

### To Register Camera in Server:

1. **Option A: Automatic (Recommended)**
   - Just power on the camera
   - Server will detect it when you access the dashboard
   - You can then name it "Rear Flower Garden" via the camera management page

2. **Option B: Manual Registration**
   - Go to http://192.168.1.15:5000/cameras
   - Click "Add Camera"
   - Enter:
     - Name: Rear Flower Garden
     - Hostname: esp32cam-rear.local
     - Stream URL: http://esp32cam-rear.local:81/
   - Click "Register"

---

## Expected Behavior

Once camera is powered on and registered:

✅ Camera appears in multi-camera grid on main dashboard
✅ Live video feed with timestamp overlay
✅ PIR motion sensor triggers detection sessions
✅ WiFi signal strength displayed
✅ Flip controls available (if needed)
✅ Independent detection sessions and cooldowns
✅ Device assignments (configure which valves to activate)

---

## All 3 Cameras Summary

| Camera | Name | Hostname | IP Address |
|--------|------|----------|------------|
| 1 | Default Camera | esp32cam.local | 192.168.1.100 |
| 2 | Front Garden | esp32cam-back.local | 192.168.1.101 |
| 3 | **Rear Flower Garden** | **esp32cam-rear.local** | **192.168.1.102** |

---

## Troubleshooting

**Problem: LED fast-blinking continuously**
- Power issue - use 1A+ USB power supply
- Check camera ribbon cable connection

**Problem: No WiFi (no 7 blinks)**
- WiFi credentials in firmware are correct (same as other cameras)
- Check router settings
- Verify 2.4GHz WiFi is enabled

**Problem: Can't access stream**
- Wait 30 seconds after power-on
- Try IP address instead of hostname: http://192.168.1.102:81/
- Check router firewall settings

**Problem: Black screen in browser**
- Camera may be upside-down - use flip controls on dashboard
- Check camera lens for protective film
- Verify power supply

---

## Next Steps

After successful upload:

1. ✅ Upload firmware to ESP32-CAM
2. ✅ Watch for 3-5-7 blink pattern
3. ✅ Test stream in browser (http://192.168.1.102:81/)
4. ✅ Access main dashboard (http://192.168.1.15:5000)
5. ✅ Register camera if not auto-detected
6. ✅ Configure camera settings (flip, device assignments)
7. ✅ Test detection session by waving hand in front of camera

---

**Questions?** See `FIRMWARE_NOTES.md` for detailed firmware documentation.
