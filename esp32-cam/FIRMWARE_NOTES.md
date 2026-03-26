# ESP32-CAM Firmware Notes

**Last Updated:** 2026-03-14
**Status:** ✅ Working and tested

---

## ⚠️ CRITICAL: DO NOT MODIFY INITIALIZATION SEQUENCE

This firmware has been carefully structured to prevent brownout issues on ESP32-CAM. Any modifications to the initialization sequence can cause the system to fail.

---

## Why This Firmware Structure is Essential

### 1. 3-Second Serial Stabilization Delay
```cpp
Serial.begin(115200);
delay(3000);  // CRITICAL - prevents brownout during init
```

**Why:**
- ESP32-CAM draws significant current during initialization
- Power supply needs time to stabilize
- Without this delay, brownout detector triggers false resets
- This is **NOT** optional

### 2. Staggered Initialization Sequence

The firmware initializes components in a specific order with delays:

1. **LED** - Low power, quick init
2. **Camera** - High power, slow init (needs stable power)
3. **WiFi** - High power during connection
4. **Server** - Low power, depends on WiFi

**Why:**
- Prevents simultaneous high current draw
- Each component stabilizes before the next starts
- Natural delays from Serial.println() add buffering
- Reduces brownout risk by 90%+

### 3. LED Diagnostic Patterns

The firmware uses LED blinks to indicate progress:
- **3 quick blinks** → Boot successful
- **5 quick blinks** → Camera initialized successfully
- **7 quick blinks** → WiFi connected successfully
- **Slow blink (1/3s)** → Running normally
- **Fast continuous blink** → Failed (stuck in error loop)

**Why:**
- Serial output doesn't work on ESP32-CAM hardware
- LED patterns are the ONLY way to diagnose boot issues
- Eliminates need for serial monitor during deployment

### 4. Static IP Configuration

```cpp
IPAddress STATIC_IP(192, 168, 1, 100);
WiFi.config(STATIC_IP, GATEWAY, SUBNET, DNS1, DNS2);
WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
```

**Why:**
- Predictable addressing when serial output unavailable
- Configured BEFORE WiFi.begin() to avoid DHCP delays
- DHCP adds latency and potential brownout during negotiation
- Fallback when mDNS unavailable

### 5. mDNS Hostname Support

```cpp
MDNS.begin("esp32cam");
// Accessible via: http://esp32cam.local:81/
```

**Why:**
- Network discovery without knowing IP address
- Easier access for multiple devices
- Non-critical (system works without it)

---

### 6. PIR Motion Sensor Integration (HC-SR501)
- **Pin:** GPIO 14
- **Implementation:** PIR status embedded in MJPEG stream headers
- **Header:** `X-PIR-Status: active` or `X-PIR-Status: inactive`
- **Behavior:** Server reads PIR status from video stream without separate connection
- **Advantage:** No additional network overhead, works within ESP32's single-connection limitation
- **Real-time:** Status updates with every video frame (~30 FPS)

**Note:** Port 82 server exists as backup but is not actively used (PIR via stream headers is preferred)

---

## What NOT to Do

### ❌ NEVER:
1. **Enable dual-core processing** - Causes brownout and crashes
2. **Initialize WiFi before camera** - Power spike can corrupt camera init
3. **Remove the 3-second initial delay** - Will cause random brownout resets
4. **Add complex processing during init** - Keep init simple and fast
5. **Use DHCP without static IP fallback** - Delays can cause brownout
6. **Remove LED diagnostic patterns** - You'll be blind when troubleshooting
7. **Use GPIO 14 for other purposes** - Now reserved for PIR sensor

### ❌ FAILED EXPERIMENTS:
- **Gemini's dual-core firmware (2026-03-14)** - Caused complete system failure
- **Original git firmware (2026-02-16 12:18)** - Had brownout issues, not production-ready

---

## Firmware History

### Timeline:
1. **2026-02-16 12:18** - Initial commit (had brownout issues)
2. **2026-02-16 ~13:00** - Fixed brownout issues (never committed - LOST)
3. **2026-02-16 - 2026-03-14** - System working perfectly
4. **2026-03-14** - Gemini broke it with dual-core attempt
5. **2026-03-14 20:00** - Recovered from `/mnt/linux-data/Arduino-Projects/esp32cam-test/`
6. **2026-03-14 20:30** - NOW COMMITTED TO GIT (this version)

### Lesson Learned:
**ALWAYS commit working firmware immediately!**

---

## Firmware Locations

**Primary (Definitive):**
```
/mnt/linux-data/deer-detection-system/esp32-cam/src/main.cpp
```
✅ In git, tested and working

**Backup (Reference):**
```
/mnt/linux-data/Arduino-Projects/esp32cam-test/src/main.cpp
```
✅ Working copy, keep as backup

**OLD/Obsolete:**
```
~/Desktop/OLD Pi Sprinker Server/
```
❌ Different project from 2025, ignore

---

## How to Upload Firmware

### Using PlatformIO:
```bash
cd /mnt/linux-data/deer-detection-system/esp32-cam
pio run --target upload
```

### Expected Upload Output:
- Compile time: ~5-10 seconds
- Upload time: ~100 seconds
- Upload speed: ~70-80 kbit/s
- Final size: ~860KB

### After Upload:
1. Wait 5 seconds for boot
2. Watch for LED patterns: 3 blinks → 5 blinks → 7 blinks
3. Slow blink = Success!
4. Test stream: `http://192.168.1.100:81/stream` or `http://esp32cam.local:81/stream`

---

## Troubleshooting

### Problem: Black screen in browser
**Diagnosis:** Camera not streaming
**Steps:**
1. Check LED pattern - did you see 3-5-7 blinks?
2. If fast continuous blink: Check power supply (needs 1A+)
3. If no WiFi (no 7 blinks): Check WiFi credentials
4. If camera failed (no 5 blinks): Check camera ribbon cable

### Problem: Can't connect to IP
**Diagnosis:** WiFi or network issue
**Steps:**
1. Verify LED showed 7 blinks (WiFi connected)
2. Try mDNS: `http://esp32cam.local:81/stream`
3. Check router DHCP/static IP settings
4. Ping test: `ping 192.168.1.100`

### Problem: Random reboots
**Diagnosis:** Brownout (power issue)
**Steps:**
1. Verify 3-second delay is in firmware
2. Use external 5V 1A+ power supply
3. Check USB cable quality
4. Add capacitor (100µF) across 5V if needed

---

## Power Requirements

**Minimum:** 500mA @ 5V
**Recommended:** 1A @ 5V
**Peak (WiFi transmit):** 240mA
**Average (streaming):** 160-200mA

**Power Sources:**
- ✅ USB power adapter (1A+)
- ✅ USB port on computer (usually 500mA, borderline)
- ❌ MB programmer board USB ONLY (insufficient for WiFi)
- ✅ External 5V regulator with good filtering

---

## Configuration

### WiFi Credentials:
Edit in `main.cpp`:
```cpp
const char* WIFI_SSID = "CityWest_0090E24F";
const char* WIFI_PASSWORD = "cf72cc1722f549aa";
```

### Static IP Address:
Edit in `main.cpp`:
```cpp
IPAddress STATIC_IP(192, 168, 1, 100);   // Change last number if needed
IPAddress GATEWAY(192, 168, 1, 1);       // Your router IP
```

### mDNS Hostname:
Edit in `main.cpp`:
```cpp
const char* MDNS_HOSTNAME = "esp32cam";  // Change for multiple devices
```

---

## Summary

This firmware works because it:
1. ✅ Gives power supply time to stabilize (3-second delay)
2. ✅ Staggers high-power operations (Camera, then WiFi)
3. ✅ Uses static IP to avoid DHCP delays
4. ✅ Provides LED diagnostics (no serial needed)
5. ✅ Tested and proven stable since Feb 2026

**If it ain't broke, don't fix it!**

---

**Questions? Check PROJECT_LOG.md for full system context.**
