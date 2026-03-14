"""
Cloud-based Tuya Valve Control
Wrapper around DeviceManager for controlling the primary detection valve
"""

import logging
from device_manager import get_device_manager
from config import PRIMARY_VALVE_ID

logger = logging.getLogger(__name__)


class CloudValveController:
    """Simple wrapper for controlling the primary valve via device manager"""

    def __init__(self):
        self.device_id = PRIMARY_VALVE_ID
        self.device_manager = get_device_manager()
        logger.info(f"Valve controller initialized for device: {self.device_id}")

    def turn_on(self, duration=10):
        """Turn valve ON"""
        return self.device_manager.turn_on(self.device_id, duration=duration)

    def turn_off(self):
        """Turn valve OFF"""
        return self.device_manager.turn_off(self.device_id)

    def get_status(self):
        """Get valve status"""
        status = self.device_manager.get_device_status(self.device_id)
        return {
            'success': True,
            'is_on': status.get('is_on', False),
            'configured': True,
            'online': status.get('online', False),
            'api_error': status.get('api_error')
        }
