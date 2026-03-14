"""
Device Manager - Manages all Tuya/SmartLife devices
Handles discovery, status monitoring, and control
"""

import tinytuya
import logging
import threading
import time
from typing import Dict, List
from config import TUYA_CLOUD_API_KEY, TUYA_CLOUD_API_SECRET, TUYA_CLOUD_REGION

logger = logging.getLogger(__name__)


class DeviceManager:
    """Manages all Tuya/SmartLife devices"""

    def __init__(self):
        self.cloud = tinytuya.Cloud(
            apiRegion=TUYA_CLOUD_REGION,
            apiKey=TUYA_CLOUD_API_KEY,
            apiSecret=TUYA_CLOUD_API_SECRET
        )
        self.devices = {}  # device_id -> device_info
        self.device_status = {}  # device_id -> status
        self.refresh_interval = 3600  # seconds (1 hour) - reduce Cloud API usage
        self.monitor_thread = None
        self.stop_monitoring = False
        self.last_error = None

        # Initial device discovery
        self.refresh_devices()

    def refresh_devices(self):
        """Discover all devices from SmartLife and refresh their status"""
        try:
            logger.info("Refreshing device list and status from Cloud API...")
            
            # Do a quick connection status check on the primary valve to detect quota errors early
            try:
                from config import PRIMARY_VALVE_ID
                self.cloud.getconnectstatus(PRIMARY_VALVE_ID)
                self.last_error = None
            except Exception as e:
                err_str = str(e).lower()
                if "quota" in err_str or "trial" in err_str or "28841004" in err_str or "'result'" in err_str:
                    self.last_error = "Cloud API Quota Exceeded"
                else:
                    self.last_error = str(e)
            
            device_list = self.cloud.getdevices()

            if isinstance(device_list, list):
                # Backup existing status for missing devices
                old_status = self.device_status.copy()
                self.devices = {}
                for device in device_list:
                    device_id = device['id']
                    self.devices[device_id] = {
                        'id': device_id,
                        'name': device.get('name', 'Unknown'),
                        'model': device.get('model', 'Unknown'),
                        'category': device.get('category', 'unknown'),
                        'local_key': device.get('key', ''),
                        'online': False,  # Will be updated by get_device_status()
                        'icon': device.get('icon', '')
                    }

                logger.info(f"Discovered {len(self.devices)} devices")

                # Get FRESH status for all devices (this is the expensive part)
                for device_id in self.devices.keys():
                    self.get_device_status(device_id, force_refresh=True)
                
                return True
            else:
                logger.error(f"Device discovery failed: {device_list}")
                return False

        except Exception as e:
            logger.error(f"Error discovering devices: {e}")
            return False

    def refresh_all_status(self):
        """Force refresh status for all devices from Cloud API"""
        for device_id in self.devices.keys():
            self.get_device_status(device_id, force_refresh=True)

    def get_device_status(self, device_id: str, force_refresh: bool = False) -> Dict:
        """Get status of a device - defaults to CACHED status to save API calls"""
        # Return cached status if available and not forcing a refresh
        if not force_refresh and device_id in self.device_status:
            return self.device_status[device_id]

        try:
            # Hit the Cloud API only if forced or missing
            # logger.debug(f"HITTING CLOUD API for status of {device_id}...")
            
            # Check if device is actually online using getconnectstatus()
            is_online = False
            api_error = None
            try:
                connect_status = self.cloud.getconnectstatus(device_id)
                is_online = bool(connect_status)
            except Exception as e:
                err_str = str(e).lower()
                if "quota" in err_str or "trial" in err_str or "28841004" in err_str or "'result'" in err_str:
                    api_error = "Cloud API Quota Exceeded"
                    self.last_error = api_error
                logger.warning(f"Could not get connection status for {device_id}: {e}")
                is_online = False

            # Update device online status
            if device_id in self.devices:
                self.devices[device_id]['online'] = is_online

            # Get device state (only meaningful if online)
            is_on = False
            if is_online:
                result = self.cloud.getstatus(device_id)
                if 'result' in result and 'success' in result and result['success']:
                    status_data = result['result']
                    # Parse status - look for switch state
                    for item in status_data:
                        if item.get('code') in ['switch_1', 'switch']:
                            is_on = item.get('value', False)
                            break

            status = {
                'online': is_online,
                'is_on': is_on,
                'api_error': api_error,
                'last_update': time.time()
            }

            self.device_status[device_id] = status
            return status

        except Exception as e:
            logger.error(f"Error getting status for {device_id}: {e}")
            err_str = str(e).lower()
            api_error = "Cloud API Quota Exceeded" if "quota" in err_str or "trial" in err_str or "28841004" in err_str or "'result'" in err_str else str(e)
            status = {
                'online': False,
                'is_on': False,
                'api_error': api_error,
                'error': str(e)
            }

            # Update device online status
            if device_id in self.devices:
                self.devices[device_id]['online'] = False

            return status

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
