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
        """
        Turn valve ON
        Returns: dict with success, verified, device_name, and state info
        """
        try:
            result = self.device_manager.turn_on(self.device_id, duration=duration)
            return result
        except Exception as e:
            logger.error(f"Error in turn_on: {e}")
            return {
                'success': False,
                'verified': False,
                'device_id': self.device_id,
                'device_name': 'Unknown',
                'state': 'unknown',
                'error': str(e)
            }

    def turn_off(self):
        """
        Turn valve OFF
        Returns: dict with success, verified, device_name, and state info
        """
        try:
            result = self.device_manager.turn_off(self.device_id)
            return result
        except Exception as e:
            logger.error(f"Error in turn_off: {e}")
            return {
                'success': False,
                'verified': False,
                'device_id': self.device_id,
                'device_name': 'Unknown',
                'state': 'unknown',
                'error': str(e)
            }

    def get_status(self):
        """Get valve status with health information"""
        status = self.device_manager.get_device_status(self.device_id)
        health = self.device_manager.is_healthy()
        return {
            'success': True,
            'is_on': status.get('is_on', False),
            'configured': self.device_manager.credentials_valid,
            'online': status.get('online', False),
            'api_error': status.get('api_error'),
            'health': health
        }
