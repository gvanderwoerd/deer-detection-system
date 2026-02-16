"""
Tuya Smart Valve Control
Controls SM-AW713 water valve via local network using tinytuya
"""

import tinytuya
import threading
import time
import logging
from config import (
    TUYA_DEVICE_ID,
    TUYA_DEVICE_IP,
    TUYA_LOCAL_KEY,
    TUYA_DEVICE_VERSION,
    SPRINKLER_DURATION_SECONDS
)

logger = logging.getLogger(__name__)


class ValveController:
    """Controls Tuya smart water valve"""

    def __init__(self):
        """Initialize valve controller"""
        self.device = None
        self.is_on = False
        self.timer_thread = None
        self.stop_timer = False

        # Check if configuration is complete
        if not TUYA_DEVICE_ID or not TUYA_LOCAL_KEY:
            logger.warning("Tuya device not configured. Run 'python3 -m tinytuya wizard' first.")
            logger.warning("Valve control will be disabled until configured.")
            self.configured = False
        else:
            self.configured = True
            self._connect()

    def _connect(self):
        """Connect to Tuya device"""
        try:
            logger.info(f"Connecting to Tuya valve: {TUYA_DEVICE_ID}")
            self.device = tinytuya.OutletDevice(
                dev_id=TUYA_DEVICE_ID,
                address=TUYA_DEVICE_IP,
                local_key=TUYA_LOCAL_KEY,
                version=TUYA_DEVICE_VERSION
            )

            # Test connection
            status = self.device.status()
            if 'Error' in str(status):
                logger.error(f"Connection error: {status}")
                self.configured = False
            else:
                logger.info("Successfully connected to valve")
                logger.info(f"Initial status: {status}")

        except Exception as e:
            logger.error(f"Failed to connect to valve: {e}")
            self.configured = False

    def turn_on(self, duration=None):
        """
        Turn valve ON

        Args:
            duration: Optional duration in seconds. If None, uses config default.
                     Use 0 for indefinite (manual shutoff required)

        Returns:
            bool: Success status
        """
        if not self.configured:
            logger.warning("Valve not configured - simulating ON command")
            self.is_on = True
            return True

        try:
            logger.info("Turning valve ON")
            self.device.turn_on()
            self.is_on = True

            # Set up timer if duration specified
            if duration is None:
                duration = SPRINKLER_DURATION_SECONDS

            if duration > 0:
                self._start_timer(duration)

            return True

        except Exception as e:
            logger.error(f"Failed to turn valve on: {e}")
            return False

    def turn_off(self):
        """
        Turn valve OFF

        Returns:
            bool: Success status
        """
        # Stop any running timer
        if self.timer_thread and self.timer_thread.is_alive():
            self.stop_timer = True
            self.timer_thread.join(timeout=2)

        if not self.configured:
            logger.warning("Valve not configured - simulating OFF command")
            self.is_on = False
            return True

        try:
            logger.info("Turning valve OFF")
            self.device.turn_off()
            self.is_on = False
            return True

        except Exception as e:
            logger.error(f"Failed to turn valve off: {e}")
            return False

    def _start_timer(self, duration):
        """Start auto-shutoff timer"""
        self.stop_timer = False

        def timer_worker():
            logger.info(f"Valve timer started: {duration} seconds")
            for i in range(duration):
                if self.stop_timer:
                    logger.info("Timer cancelled")
                    return
                time.sleep(1)

            logger.info("Timer expired - turning off valve")
            self.turn_off()

        self.timer_thread = threading.Thread(target=timer_worker, daemon=True)
        self.timer_thread.start()

    def get_status(self):
        """
        Get valve status

        Returns:
            dict: Status information
        """
        if not self.configured:
            return {
                'configured': False,
                'is_on': self.is_on,
                'message': 'Valve not configured'
            }

        try:
            status = self.device.status()

            # Parse DPS values (Tuya data points)
            # Most valves use DPS 1 for on/off state
            is_on = False
            if 'dps' in status:
                is_on = status['dps'].get('1', False)

            self.is_on = is_on

            return {
                'configured': True,
                'is_on': is_on,
                'raw_status': status
            }

        except Exception as e:
            logger.error(f"Failed to get valve status: {e}")
            return {
                'configured': True,
                'is_on': self.is_on,
                'error': str(e)
            }

    def test(self):
        """
        Test valve control (10 second on/off cycle)

        Returns:
            bool: Success status
        """
        logger.info("Testing valve control...")

        print("Turning valve ON for 10 seconds...")
        if not self.turn_on(duration=10):
            print("Failed to turn valve ON")
            return False

        print("Valve is ON. Waiting 10 seconds...")
        time.sleep(11)  # Wait for auto-off

        status = self.get_status()
        print(f"Final status: {status}")

        if status['is_on']:
            print("Warning: Valve still ON, forcing OFF...")
            self.turn_off()

        print("Test complete!")
        return True


# Utility functions for setup
def scan_devices():
    """Scan network for Tuya devices"""
    print("Scanning for Tuya devices...")
    print("This may take 20-30 seconds...\n")
    devices = tinytuya.deviceScan(False, 20)

    if not devices:
        print("No devices found!")
        return

    print(f"\nFound {len(devices)} device(s):\n")
    for device_id, device_info in devices.items():
        print(f"Device ID: {device_id}")
        print(f"IP: {device_info.get('ip', 'unknown')}")
        print(f"Version: {device_info.get('version', 'unknown')}")
        print("-" * 40)


# Example usage and testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Uncomment to scan for devices:
    # scan_devices()

    print("\nInitializing Valve Controller...")
    valve = ValveController()

    if valve.configured:
        print("\n=== Valve Control Test ===")
        print("1. Get Status")
        print("2. Turn ON (60 seconds)")
        print("3. Turn OFF")
        print("4. Test (10 second cycle)")
        print("5. Scan for devices")
        print("0. Exit")

        while True:
            choice = input("\nSelect option: ").strip()

            if choice == '1':
                status = valve.get_status()
                print(f"Status: {status}")

            elif choice == '2':
                if valve.turn_on():
                    print("Valve turned ON (60 second timer active)")
                else:
                    print("Failed to turn ON")

            elif choice == '3':
                if valve.turn_off():
                    print("Valve turned OFF")
                else:
                    print("Failed to turn OFF")

            elif choice == '4':
                valve.test()

            elif choice == '5':
                scan_devices()

            elif choice == '0':
                valve.turn_off()
                break

            else:
                print("Invalid option")

    else:
        print("\n=== Configuration Required ===")
        print("Run the following command to configure your Tuya device:")
        print("  python3 -m tinytuya wizard")
        print("\nThen update config.py with the device credentials.")
