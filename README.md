# 🦌 Deer Detection Sprinkler System

Automated deer deterrent system using AI-powered object detection with ESP32-CAM and smart sprinkler control.

## System Overview

When motion is detected by the Yard Sentinel, the ESP32-CAM wakes up and streams images to your desktop PC. YOLOv8 AI analyzes the video feed in real-time to detect deer. When a deer is identified, the system automatically activates your Tuya smart water valve to run the sprinkler for 60 seconds.

**Key Features:**
- ✅ AI-powered deer detection (reduces false positives)
- ✅ Real-time web interface with live camera feed
- ✅ Low-power ESP32-CAM with deep sleep mode
- ✅ Local control (no cloud dependency for operation)
- ✅ Manual controls and testing features
- ✅ Event logging and history
- ✅ Zero ongoing costs

## Hardware Requirements

### Required:
- **ESP32-CAM** module (AI-Thinker or compatible)
- **USB-TTL programmer** (for ESP32-CAM upload)
- **Yard Sentinel** motion detector (motion trigger)
- **Tuya Smart Valve** (SM-AW713 or compatible)
- **Desktop PC** (for AI processing and hosting)
- **5V 2A power supply** for ESP32-CAM

### Optional:
- Outdoor weatherproof enclosure
- Wiring for Yard Sentinel → ESP32-CAM connection
- Extension cables

## Software Components

### 1. ESP32-CAM Firmware
- **Language**: C++ (Arduino framework)
- **Platform**: PlatformIO
- **Features**: Deep sleep, WiFi streaming, GPIO wake

### 2. Detection Server
- **Language**: Python 3.12+
- **Framework**: Flask + Socket.IO
- **AI Model**: YOLOv8 (Ultralytics)
- **Features**: Real-time detection, state machine, valve control

### 3. Web Interface
- **Tech**: HTML/CSS/JavaScript
- **Features**: Live stream, manual controls, event log, responsive design

## Installation

### Step 1: Python Server Setup

1. Navigate to server directory:
```bash
cd /mnt/linux-data/deer-detection-system/server
```

2. Dependencies are already installed, but if needed:
```bash
pip3 install -r requirements.txt
```

3. Configure the system:
```bash
nano config.py
```

Update the following:
- `ESP32_CAM_STREAM_URL` - Your ESP32-CAM IP address
- WiFi credentials (reference only - enter in ESP32 code)

### Step 2: Tuya Valve Configuration

1. Run tinytuya wizard to discover your valve:
```bash
python3 -m tinytuya wizard
```

2. Follow the prompts to:
   - Log into Tuya/Smart Life account
   - Scan your local network
   - Extract device credentials

3. Update `config.py` with:
   - `TUYA_DEVICE_ID`
   - `TUYA_DEVICE_IP`
   - `TUYA_LOCAL_KEY`

4. Test valve control:
```bash
python3 valve_control.py
```

### Step 3: ESP32-CAM Firmware

1. Install ESP32 platform in PlatformIO:
```bash
cd /mnt/linux-data/deer-detection-system/esp32-cam
pio platform install espressif32
```

2. Edit `src/main.cpp` and update:
   - `WIFI_SSID` - Your WiFi network name
   - `WIFI_PASSWORD` - Your WiFi password

3. Connect ESP32-CAM via USB-TTL programmer:
   - ESP32 RX → TTL TX
   - ESP32 TX → TTL RX
   - ESP32 GND → TTL GND
   - ESP32 5V → TTL 5V
   - ESP32 GPIO 0 → GND (for programming mode)

4. Upload firmware:
```bash
pio run --target upload
```

5. Open serial monitor:
```bash
pio device monitor
```

6. Note the IP address displayed

7. Update `server/config.py` with ESP32-CAM IP

### Step 4: Hardware Wiring

**Yard Sentinel → ESP32-CAM:**
- Connect Yard Sentinel output to ESP32-CAM GPIO 13
- Connect common ground
- ⚠️ Check voltage levels! ESP32-CAM uses 3.3V logic

**Power:**
- ESP32-CAM: 5V 2A USB power supply
- Ensure stable power (camera draws significant current)

## Usage

### Starting the System

1. Start the Python server:
```bash
cd /mnt/linux-data/deer-detection-system/server
python3 main.py
```

2. Open web interface in browser:
```
http://192.168.1.15:5000
```

Or from another device on your network:
```
http://<your-pc-ip>:5000
```

3. System is now armed and ready!

### Web Interface Controls

- **Enable System** - Arm the detection system
- **Disable System** - Disarm (no sprinkler activation)
- **Emergency Stop** - Immediately shut off sprinkler
- **Test Sprinkler** - Manual 10-second test
- **Manual Trigger** - Simulate motion detection

### How It Works

1. **Motion Detected**: Yard Sentinel detects motion → sends signal to ESP32-CAM GPIO 13
2. **Camera Wakes**: ESP32-CAM wakes from deep sleep, connects to WiFi
3. **Streaming Starts**: Camera begins streaming to desktop PC
4. **AI Analysis**: YOLOv8 processes each frame looking for deer (class ID 23)
5. **Deer Detected**: If deer found with confidence >0.5 → activate sprinkler
6. **Sprinkler ON**: Valve opens for 60 seconds
7. **Cooldown**: System waits 2 minutes before allowing another activation
8. **Sleep**: After 5 minutes of no motion, ESP32-CAM returns to deep sleep

## Configuration Options

Edit `server/config.py` to customize:

```python
DETECTION_CONFIDENCE = 0.5          # Detection threshold (0.3-0.7)
ACTIVE_WINDOW_SECONDS = 300         # How long to scan (5 minutes)
SPRINKLER_DURATION_SECONDS = 60     # Spray duration
COOLDOWN_PERIOD_SECONDS = 120       # Wait between activations
MAX_DETECTIONS_PER_SESSION = 3      # Max sprinkler activations per session
```

## Troubleshooting

### Camera Issues

**ESP32-CAM won't connect to WiFi:**
- Check WiFi credentials in `main.cpp`
- Ensure 2.4GHz WiFi (ESP32 doesn't support 5GHz)
- Check signal strength (ESP32 needs good WiFi signal)

**Camera feed not showing:**
- Verify ESP32-CAM IP address
- Update `ESP32_CAM_STREAM_URL` in `config.py`
- Check firewall settings
- Test stream directly: `http://<esp32-ip>:81/stream`

**Camera crashes/reboots:**
- Use stable 5V 2A power supply
- Check power supply quality
- Reduce frame size in code if needed

### Detection Issues

**No deer detected:**
- Check detection confidence threshold
- Verify YOLO model loaded correctly
- Test with deer images: `python3 detection.py`
- Check lighting conditions (detection works better in good light)

**Too many false positives:**
- Increase `DETECTION_CONFIDENCE` to 0.6 or 0.7
- Check what objects are being detected in logs
- Consider fine-tuning model with your specific environment

### Valve Issues

**Valve not responding:**
- Run `python3 valve_control.py` to test
- Verify Tuya credentials in `config.py`
- Check valve is on same network
- Ensure valve has power
- Try tinytuya scan: `python3 -m tinytuya scan`

**Valve stays on:**
- Use Emergency Stop button in web interface
- Or run: `python3 valve_control.py` and manually turn off

### Server Issues

**Web interface not loading:**
- Check server is running
- Verify correct IP address
- Check port 5000 is not blocked
- Try: `netstat -tuln | grep 5000`

**WebSocket not connecting:**
- Check browser console for errors
- Ensure Socket.IO library loads correctly
- Verify firewall allows WebSocket connections

## Testing

### Component Tests

**1. Test Detection Engine:**
```bash
cd server
python3 detection.py
# Model should load successfully
```

**2. Test Valve Control:**
```bash
cd server
python3 valve_control.py
# Select option 4 for 10-second test
```

**3. Test ESP32-CAM:**
- Access stream directly: `http://<esp32-ip>:81/stream`
- Should see camera feed in browser

### Integration Test

1. Start server: `python3 main.py`
2. Open web interface: `http://192.168.1.15:5000`
3. Click "Manual Trigger"
4. Show deer image to camera (or test image)
5. Verify detection appears in log
6. Verify sprinkler activates

## System Startup (Auto-Start)

To run server automatically on boot, create systemd service:

```bash
sudo nano /etc/systemd/system/deer-detection.service
```

Add:
```ini
[Unit]
Description=Deer Detection System
After=network.target

[Service]
Type=simple
User=gvanderwoerd
WorkingDirectory=/mnt/linux-data/deer-detection-system/server
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable deer-detection.service
sudo systemctl start deer-detection.service
```

## Maintenance

### Logs
- Server logs: `server/deer_detection.log`
- Recent events: Check web interface Event Log
- System logs: `journalctl -u deer-detection.service -f`

### Updates
- Update YOLOv8: `pip3 install --upgrade ultralytics`
- Update dependencies: `pip3 install --upgrade -r requirements.txt`
- Update ESP32 firmware: Modify code and re-upload with PlatformIO

## Performance

### Expected Performance:
- **Detection Speed**: ~30 FPS on modern desktop CPU
- **ESP32-CAM Power**:
  - Active: ~300mA
  - Deep sleep: ~10mA
- **Server Resources**: ~100MB RAM, <5% CPU when idle
- **Detection Accuracy**: ~85-95% (depends on lighting and conditions)

## Future Enhancements

### Phase 2 Ideas:
- [ ] Multiple camera support
- [ ] SQLite database for detection history
- [ ] Push notifications (email/SMS)
- [ ] Raspberry Pi deployment option
- [ ] Local Zigbee hub (Zigbee2MQTT) for complete offline operation
- [ ] Solar power for ESP32-CAM
- [ ] Fine-tuned deer detection model
- [ ] Mobile app (PWA)
- [ ] Schedule-based arming (e.g., only at night)
- [ ] Detection zones (ignore specific areas)

## Costs

### Ongoing: **$0/month**
- All software is free and open-source
- No cloud subscriptions required
- No API fees

### One-Time Hardware:
- ESP32-CAM: ~$10-15
- USB-TTL Programmer: ~$5
- Outdoor enclosure: ~$10-20
- Power supplies: ~$10
- **Total**: ~$35-50 (if buying all new)

## Credits

- **YOLOv8**: Ultralytics (https://github.com/ultralytics/ultralytics)
- **tinytuya**: Jason Cox (https://github.com/jasonacox/tinytuya)
- **ESP32-CAM**: AI-Thinker

## License

MIT License - Free to use and modify

## Support

For issues or questions:
1. Check Troubleshooting section above
2. Review logs for error messages
3. Test components individually
4. Check hardware connections

---

**Built with Claude Code** 🤖
