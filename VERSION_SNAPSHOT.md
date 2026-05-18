# Version Snapshot - Current State (2026-05-18)

**Git Commit:** `a4e59fe` (feat: add WiFi signal strength indicator to dashboard)
**Branch:** main
**Status:** ✅ Fully operational and stable

## Current System State

### Server Code
- All recent optimizations in place (WebSocket primary, HTTP fallback)
- Detection gallery filtering active (deer/cow/sheep only)
- Auto-cleanup after 7 days implemented
- Tuya credentials secured in .env file
- Dead code cleaned up (Phase 1 & 2 cleanup complete)

### ESP32-CAM Firmware
**Status:** ⏳ NOT YET UPDATED
- **Last firmware version:** Original brownout-prevention version (2026-03-14 20:30)
- **Pending feature:** WiFi signal strength indicator (implemented on server dashboard but not on firmware)
- **Reason:** Firmware is stable and working; firmware update not urgent
- **When to update:** Next maintenance window when adding new ESP32 features

**Note:** WiFi signal strength display was added to the dashboard (commit a4e59fe) but does not require firmware changes. The firmware reports all necessary data.

## Known Working Features

✅ PIR motion sensor integration (GPIO 14) - embedded in MJPEG headers
✅ Real-time YOLOv8 detection with confidence filtering
✅ SmartLife valve control via Tuya Cloud API
✅ Person safety detection (never activates if human present)
✅ Detection gallery with auto-cleanup
✅ Web dashboard with real-time updates
✅ WebSocket for efficient real-time communication
✅ Device manager for manual valve control
✅ Emergency stop functionality

## Critical Firmware Notes

DO NOT modify ESP32-CAM firmware without reading `esp32-cam/FIRMWARE_NOTES.md`
- Never enable dual-core (causes brownout)
- Never remove 3-second init delay
- GPIO 14 reserved for PIR sensor

## Next Steps for Development

When resuming:
1. Check this snapshot first to understand current state
2. Review pending features (WiFi signal strength firmware update when needed)
3. No breaking changes needed - system is stable
4. Focus on enhancements, not bug fixes

---
**Bookmark created at commit:** a4e59fe
**Stable until:** Next breaking change or firmware update
