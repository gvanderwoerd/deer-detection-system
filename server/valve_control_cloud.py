"""
Cloud-based Tuya Valve Control
Uses Tuya Cloud API for remote valve control (works across different networks)
"""

import tinytuya
import time
from config import TUYA_DEVICE_ID

# Cloud API credentials
CLOUD_API_KEY = "rqwuq7sgvv57f745g5m8"
CLOUD_API_SECRET = "f64c246ade9f45cf9c4217851deceddc"
CLOUD_REGION = "us"

class CloudValveController:
    """Cloud-based valve controller using Tuya Cloud API"""

    def __init__(self):
        self.device_id = TUYA_DEVICE_ID
        self.cloud = tinytuya.Cloud(
            apiRegion=CLOUD_REGION,
            apiKey=CLOUD_API_KEY,
            apiSecret=CLOUD_API_SECRET
        )
        print(f"Cloud valve controller initialized for device: {self.device_id}")

    def turn_on(self, duration=10):
        """Turn valve ON via cloud API"""
        try:
            print(f"☁️  Sending cloud command: Turn ON")

            # Send command via cloud API
            result = self.cloud.sendcommand(
                self.device_id,
                {"commands": [{"code": "switch_1", "value": True}]}
            )

            print(f"   Response: {result}")

            if result.get('success'):
                print(f"   ✅ Valve turned ON!")

                if duration > 0:
                    print(f"   ⏱️  Auto-off in {duration} seconds...")
                    time.sleep(duration)
                    self.turn_off()

                return True
            else:
                print(f"   ❌ Command failed: {result}")
                return False

        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False

    def turn_off(self):
        """Turn valve OFF via cloud API"""
        try:
            print(f"☁️  Sending cloud command: Turn OFF")

            result = self.cloud.sendcommand(
                self.device_id,
                {"commands": [{"code": "switch_1", "value": False}]}
            )

            print(f"   Response: {result}")

            if result.get('success'):
                print(f"   ✅ Valve turned OFF!")
                return True
            else:
                print(f"   ❌ Command failed: {result}")
                return False

        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False

    def get_status(self):
        """Get valve status via cloud API"""
        try:
            result = self.cloud.getstatus(self.device_id)

            if 'result' in result:
                status = result['result']
                # Look for switch status
                is_on = False
                for item in status:
                    if item.get('code') == 'switch_1':
                        is_on = item.get('value', False)
                        break

                return {
                    'success': True,
                    'is_on': is_on,
                    'online': result.get('success', False)
                }
            else:
                return {'success': False, 'error': 'No result'}

        except Exception as e:
            return {'success': False, 'error': str(e)}

if __name__ == "__main__":
    print("="*60)
    print("🦌 Cloud Valve Control Test")
    print("="*60)

    valve = CloudValveController()

    print("\n1️⃣  Getting status...")
    status = valve.get_status()
    print(f"   Status: {status}")

    print("\n2️⃣  Turning valve ON for 10 seconds...")
    valve.turn_on(duration=10)

    print("\n3️⃣  Final status check...")
    status = valve.get_status()
    print(f"   Status: {status}")

    print("\n✅ Test complete!")
