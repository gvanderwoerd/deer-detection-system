
import tinytuya
import logging
import sys
from config import TUYA_CLOUD_API_KEY, TUYA_CLOUD_API_SECRET, TUYA_CLOUD_REGION

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_tuya_discovery():
    print(f"Testing Tuya Cloud API discovery...")
    print(f"Region: {TUYA_CLOUD_REGION}")
    print(f"API Key: {TUYA_CLOUD_API_KEY[:5]}...")
    
    try:
        cloud = tinytuya.Cloud(
            apiRegion=TUYA_CLOUD_REGION,
            apiKey=TUYA_CLOUD_API_KEY,
            apiSecret=TUYA_CLOUD_API_SECRET
        )
        
        print("\nCalling getdevices()...")
        device_list = cloud.getdevices()
        
        if isinstance(device_list, list):
            print(f"✅ Success! Found {len(device_list)} devices.")
            for i, dev in enumerate(device_list):
                print(f"  [{i+1}] {dev.get('name')} (ID: {dev.get('id')}, Category: {dev.get('category')})")
        else:
            print(f"❌ Error: getdevices() did not return a list.")
            print(f"Response: {device_list}")
            
        print("\nCalling getconnectstatus() for primary valve...")
        from config import PRIMARY_VALVE_ID
        status = cloud.getconnectstatus(PRIMARY_VALVE_ID)
        print(f"Primary Valve ({PRIMARY_VALVE_ID}) connection status: {status}")
        
    except Exception as e:
        print(f"❌ Exception occurred: {e}")

if __name__ == "__main__":
    test_tuya_discovery()
