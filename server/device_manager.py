"""
Device Manager - Manages all Tuya/SmartLife devices
Handles discovery, status monitoring, and control
"""

import tinytuya
import logging
import threading
import time
import functools
from typing import Dict, List, Tuple
from config import TUYA_CLOUD_API_KEY, TUYA_CLOUD_API_SECRET, TUYA_CLOUD_REGION

# Import monitoring modules
try:
    from api_usage_tracker import get_tracker as get_api_tracker
    HAS_API_TRACKER = True
except ImportError:
    HAS_API_TRACKER = False

logger = logging.getLogger(__name__)


# Retry configuration
RETRY_CONFIG = {
    'max_retries': 3,
    'base_delay': 1.0,  # Start with 1 second
    'max_delay': 16.0   # Cap at 16 seconds
}


def retry_with_backoff(max_retries=3, base_delay=1.0):
    """
    Decorator for retrying API calls with exponential backoff.
    Distinguishes between transient (retry) and permanent (fail fast) errors.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_str = str(e).lower()

                    # Permanent errors - fail fast
                    if any(x in error_str for x in ['invalid', 'unauthorized', 'forbidden', 'not found']):
                        logger.error(f"{func.__name__} failed with permanent error: {e}")
                        raise

                    # Quota errors - fail fast
                    if any(x in error_str for x in ['quota', 'trial', '28841004']):
                        logger.error(f"{func.__name__} failed: API quota exceeded")
                        raise

                    # Transient errors - retry
                    if attempt < max_retries:
                        logger.warning(f"{func.__name__} attempt {attempt + 1}/{max_retries + 1} failed: {e}. Retrying in {delay}s...")
                        time.sleep(delay)
                        delay = min(delay * 2, 16.0)  # Exponential backoff, capped at 16s
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries + 1} attempts: {e}")
                        raise

            raise last_exception
        return wrapper
    return decorator


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
        self.credentials_valid = False
        self.startup_time = time.time()

        # Validate credentials at startup
        self.validate_credentials()

        # Initial device discovery (only if credentials valid)
        if self.credentials_valid:
            self.refresh_devices()
        else:
            logger.error("Device manager initialized with invalid credentials. Please check setup.")

    def validate_credentials(self) -> Tuple[bool, str]:
        """
        Validate Tuya API credentials by making a test API call.
        Returns (valid: bool, error_message: str)
        """
        try:
            if not TUYA_CLOUD_API_KEY or not TUYA_CLOUD_API_SECRET:
                error_msg = "Missing API credentials in .env file (TUYA_API_KEY and/or TUYA_API_SECRET)"
                logger.error(f"Credential validation failed: {error_msg}")
                self.credentials_valid = False
                self.last_error = error_msg
                return False, error_msg

            # Test API connection with a lightweight call
            logger.info("Validating Tuya API credentials...")
            result = self.cloud.getdevices()

            if isinstance(result, list):
                logger.info("✓ API credentials valid")
                self.credentials_valid = True
                self.last_error = None
                return True, ""
            else:
                error_msg = f"API credentials invalid or account has no devices: {result}"
                logger.error(f"Credential validation failed: {error_msg}")
                self.credentials_valid = False
                self.last_error = error_msg
                return False, error_msg

        except Exception as e:
            error_str = str(e).lower()
            if "quota" in error_str or "trial" in error_str or "28841004" in error_str:
                error_msg = "Cloud API Quota Exceeded - check your Tuya subscription or trial status"
            elif "unauthorized" in error_str or "invalid" in error_str:
                error_msg = "Invalid API credentials - check .env file (TUYA_API_KEY and TUYA_API_SECRET)"
            else:
                error_msg = f"Network error validating credentials: {e}"

            logger.error(f"Credential validation failed: {error_msg}")
            self.credentials_valid = False
            self.last_error = error_msg
            return False, error_msg

    def is_healthy(self) -> Dict:
        """
        Get system health status for monitoring.
        Returns dict with health indicators.
        """
        return {
            'credentials_valid': self.credentials_valid,
            'devices_discovered': len(self.devices) > 0,
            'devices_count': len(self.devices),
            'devices_online': sum(1 for d in self.devices.values() if d.get('online', False)),
            'last_error': self.last_error,
            'uptime_seconds': int(time.time() - self.startup_time)
        }

    def _track_api_call(self, endpoint: str, start_time: float):
        """Track API call latency with usage tracker"""
        if HAS_API_TRACKER:
            try:
                latency_ms = (time.time() - start_time) * 1000
                tracker = get_api_tracker()
                tracker.track_call(endpoint, latency_ms)
            except Exception as e:
                logger.debug(f"Failed to track API call: {e}")

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

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def turn_on(self, device_id: str, duration: int = 0) -> Dict:
        """
        Turn device ON with retry logic and verification.
        Returns dict with success, verified, and state info.
        """
        try:
            device_name = self.devices.get(device_id, {}).get('name', device_id)
            logger.info(f"Turning ON device: {device_name}")

            # Measure API latency
            start_time = time.time()

            # Send command with retry
            result = self.cloud.sendcommand(
                device_id,
                {"commands": [{"code": "switch_1", "value": True}]}
            )

            latency_ms = (time.time() - start_time) * 1000
            self._track_api_call('sendcommand', start_time)

            if result.get('success'):
                logger.info(f"  ✓ Command sent to {device_name} ({latency_ms:.0f}ms)")

                # Update local status optimistically
                if device_id in self.device_status:
                    self.device_status[device_id]['is_on'] = True

                # Verify command by reading back state (with small delay for device to respond)
                verified = False
                time.sleep(0.5)  # Give device time to respond
                try:
                    status = self.get_device_status(device_id, force_refresh=True)
                    if status.get('is_on'):
                        verified = True
                        logger.info(f"  ✓ Verified: {device_name} is ON")
                    else:
                        logger.warning(f"  ⚠ Verification failed: {device_name} reports OFF after command")
                except Exception as e:
                    logger.warning(f"  ⚠ Could not verify state: {e}")

                # Auto-off timer
                if duration > 0:
                    threading.Timer(duration, lambda: self.turn_off(device_id)).start()

                return {
                    'success': True,
                    'verified': verified,
                    'device_id': device_id,
                    'device_name': device_name,
                    'state': 'on',
                    'latency_ms': round(latency_ms, 2)
                }
            else:
                logger.error(f"  ✗ Failed: {result} ({latency_ms:.0f}ms)")
                return {
                    'success': False,
                    'verified': False,
                    'device_id': device_id,
                    'device_name': device_name,
                    'state': 'unknown',
                    'error': str(result),
                    'latency_ms': round(latency_ms, 2)
                }

        except Exception as e:
            logger.error(f"Error turning on {device_id}: {e}")
            raise

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def turn_off(self, device_id: str) -> Dict:
        """
        Turn device OFF with retry logic and verification.
        Returns dict with success, verified, and state info.
        """
        try:
            device_name = self.devices.get(device_id, {}).get('name', device_id)
            logger.info(f"Turning OFF device: {device_name}")

            # Measure API latency
            start_time = time.time()

            # Send command with retry
            result = self.cloud.sendcommand(
                device_id,
                {"commands": [{"code": "switch_1", "value": False}]}
            )

            latency_ms = (time.time() - start_time) * 1000
            self._track_api_call('sendcommand', start_time)

            if result.get('success'):
                logger.info(f"  ✓ Command sent to {device_name} ({latency_ms:.0f}ms)")

                # Update local status optimistically
                if device_id in self.device_status:
                    self.device_status[device_id]['is_on'] = False

                # Verify command by reading back state (with small delay for device to respond)
                verified = False
                time.sleep(0.5)  # Give device time to respond
                try:
                    status = self.get_device_status(device_id, force_refresh=True)
                    if not status.get('is_on'):
                        verified = True
                        logger.info(f"  ✓ Verified: {device_name} is OFF")
                    else:
                        logger.warning(f"  ⚠ Verification failed: {device_name} reports ON after command")
                except Exception as e:
                    logger.warning(f"  ⚠ Could not verify state: {e}")

                return {
                    'success': True,
                    'verified': verified,
                    'device_id': device_id,
                    'device_name': device_name,
                    'state': 'off',
                    'latency_ms': round(latency_ms, 2)
                }
            else:
                logger.error(f"  ✗ Failed: {result} ({latency_ms:.0f}ms)")
                return {
                    'success': False,
                    'verified': False,
                    'device_id': device_id,
                    'device_name': device_name,
                    'state': 'unknown',
                    'error': str(result),
                    'latency_ms': round(latency_ms, 2)
                }

        except Exception as e:
            logger.error(f"Error turning off {device_id}: {e}")
            raise

    def test_device(self, device_id: str, duration: int = 10) -> Dict:
        """Test device with auto-off"""
        return self.turn_on(device_id, duration=duration)

    def emergency_stop_all(self) -> Dict:
        """Turn off ALL devices immediately"""
        logger.warning("EMERGENCY STOP - Turning off all devices")

        results = {}
        for device_id in self.devices.keys():
            try:
                result = self.turn_off(device_id)
                results[device_id] = result.get('success', False)
            except Exception as e:
                logger.error(f"Emergency stop failed for {device_id}: {e}")
                results[device_id] = False

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
