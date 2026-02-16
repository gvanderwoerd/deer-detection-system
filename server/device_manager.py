"""
Device Manager - Manages all Tuya/SmartLife devices
Handles discovery, status monitoring, and control
"""

import tinytuya
import logging
import threading
import time
from typing import Dict, List

logger = logging.getLogger(__name__)

# Cloud API credentials
CLOUD_API_KEY = "rqwuq7sgvv57f745g5m8"
CLOUD_API_SECRET = "f64c246ade9f45cf9c4217851deceddc"
CLOUD_REGION = "us"


class DeviceManager:
    """Manages all Tuya/SmartLife devices"""

    def __init__(self):
        self.cloud = tinytuya.Cloud(
            apiRegion=CLOUD_REGION,
            apiKey=CLOUD_API_KEY,
            apiSecret=CLOUD_API_SECRET
        )
        self.devices = {}  # device_id -> device_info
        self.device_status = {}  # device_id -> status
        self.refresh_interval = 30  # seconds
        self.monitor_thread = None
        self.stop_monitoring = False

        # Initial device discovery
        self.refresh_devices()

    def refresh_devices(self):
        """Discover all devices from SmartLife"""
        try:
            logger.info("Discovering SmartLife devices...")
            device_list = self.cloud.getdevices()

            if isinstance(device_list, list):
                self.devices = {}
                for device in device_list:
                    device_id = device['id']
                    self.devices[device_id] = {
                        'id': device_id,
                        'name': device.get('name', 'Unknown'),
                        'model': device.get('model', 'Unknown'),
                        'category': device.get('category', 'unknown'),
                        'local_key': device.get('key', ''),
                        'online': device.get('online', False),
                        'icon': device.get('icon', '')
                    }

                logger.info(f"Discovered {len(self.devices)} devices")
                for dev_id, dev in self.devices.items():
                    logger.info(f"  - {dev['name']} ({dev['model']}) - {'Online' if dev['online'] else 'Offline'}")

                # Get initial status for all devices
                self.refresh_all_status()
                return True
            else:
                logger.error(f"Device discovery failed: {device_list}")
                return False

        except Exception as e:
            logger.error(f"Error discovering devices: {e}")
            return False

    def refresh_all_status(self):
        """Refresh status for all devices"""
        for device_id in self.devices.keys():
            self.get_device_status(device_id)

    def get_device_status(self, device_id: str) -> Dict:
        """Get current status of a device"""
        try:
            result = self.cloud.getstatus(device_id)

            if 'result' in result:
                status_data = result['result']

                # Parse status - look for switch state
                is_on = False
                for item in status_data:
                    if item.get('code') in ['switch_1', 'switch']:
                        is_on = item.get('value', False)
                        break

                status = {
                    'online': True,
                    'is_on': is_on,
                    'last_update': time.time()
                }

                self.device_status[device_id] = status
                return status
            else:
                # Device might be offline
                status = {
                    'online': False,
                    'is_on': False,
                    'last_update': time.time()
                }
                self.device_status[device_id] = status
                return status

        except Exception as e:
            logger.error(f"Error getting status for {device_id}: {e}")
            return {
                'online': False,
                'is_on': False,
                'error': str(e)
            }

    def turn_on(self, device_id: str, duration: int = 0) -> bool:
        """Turn device ON"""
        try:
            logger.info(f"Turning ON device: {self.devices[device_id]['name']}")

            result = self.cloud.sendcommand(
                device_id,
                {"commands": [{"code": "switch_1", "value": True}]}
            )

            if result.get('success'):
                logger.info(f"  ✓ Device turned ON")

                # Update local status
                if device_id in self.device_status:
                    self.device_status[device_id]['is_on'] = True

                # Auto-off timer
                if duration > 0:
                    threading.Timer(duration, lambda: self.turn_off(device_id)).start()

                return True
            else:
                logger.error(f"  ✗ Failed: {result}")
                return False

        except Exception as e:
            logger.error(f"Error turning on {device_id}: {e}")
            return False

    def turn_off(self, device_id: str) -> bool:
        """Turn device OFF"""
        try:
            logger.info(f"Turning OFF device: {self.devices[device_id]['name']}")

            result = self.cloud.sendcommand(
                device_id,
                {"commands": [{"code": "switch_1", "value": False}]}
            )

            if result.get('success'):
                logger.info(f"  ✓ Device turned OFF")

                # Update local status
                if device_id in self.device_status:
                    self.device_status[device_id]['is_on'] = False

                return True
            else:
                logger.error(f"  ✗ Failed: {result}")
                return False

        except Exception as e:
            logger.error(f"Error turning off {device_id}: {e}")
            return False

    def test_device(self, device_id: str, duration: int = 10) -> bool:
        """Test device with auto-off"""
        return self.turn_on(device_id, duration=duration)

    def emergency_stop_all(self) -> Dict[str, bool]:
        """Turn off ALL devices immediately"""
        logger.warning("EMERGENCY STOP - Turning off all devices")

        results = {}
        for device_id in self.devices.keys():
            results[device_id] = self.turn_off(device_id)

        return results

    def get_all_devices(self) -> List[Dict]:
        """Get list of all devices with current status"""
        devices_list = []

        for device_id, device_info in self.devices.items():
            status = self.device_status.get(device_id, {})

            devices_list.append({
                'id': device_id,
                'name': device_info['name'],
                'model': device_info['model'],
                'category': device_info['category'],
                'online': device_info['online'],  # Use actual online status from device info
                'is_on': status.get('is_on', False),
                'icon': device_info.get('icon', '')
            })

        return devices_list

    def start_monitoring(self):
        """Start background monitoring thread"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            return

        self.stop_monitoring = False

        def monitor_loop():
            while not self.stop_monitoring:
                try:
                    # Refresh device list (detects new/removed devices)
                    self.refresh_devices()
                    time.sleep(self.refresh_interval)
                except Exception as e:
                    logger.error(f"Monitor error: {e}")
                    time.sleep(10)

        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Device monitoring started")

    def stop_monitoring_thread(self):
        """Stop background monitoring"""
        self.stop_monitoring = True
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Device monitoring stopped")


# Global device manager instance
device_manager = None


def get_device_manager() -> DeviceManager:
    """Get or create global device manager"""
    global device_manager
    if device_manager is None:
        device_manager = DeviceManager()
        device_manager.start_monitoring()
    return device_manager
