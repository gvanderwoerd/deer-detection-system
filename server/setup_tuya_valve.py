#!/usr/bin/env python3
"""
Tuya Valve Setup - Automated Device Discovery and Configuration
Usage: python3 setup_tuya_valve.py --api-key KEY --api-secret SECRET [--region us]
   Or: python3 setup_tuya_valve.py (interactive mode)
"""

import tinytuya
import json
import sys
import os
import argparse

def get_credentials_interactive():
    """Get API credentials from user interactively"""
    print("="*70)
    print("🦌 Tuya Smart Valve Setup")
    print("="*70)
    print("\nI need the API credentials from the Tuya IoT Platform.")
    print("In your browser (iot.tuya.com), you should see:")
    print("  - Access ID (or Client ID)")
    print("  - Access Secret (or Client Secret)")
    print()

    api_key = input("Paste Access ID / Client ID: ").strip()
    api_secret = input("Paste Access Secret / Client Secret: ").strip()
    region = input("Region (us/eu/cn/in) [us]: ").strip() or "us"

    return {
        'api_key': api_key,
        'api_secret': api_secret,
        'region': region
    }

def get_credentials_args(args):
    """Get API credentials from command-line arguments"""
    return {
        'api_key': args.api_key,
        'api_secret': args.api_secret,
        'region': args.region
    }

def discover_devices(creds):
    """Use Tuya Cloud API to discover devices"""
    print("\n" + "="*70)
    print("🔍 Discovering Devices...")
    print("="*70)

    try:
        # Initialize cloud connection
        cloud = tinytuya.Cloud(
            apiRegion=creds['region'],
            apiKey=creds['api_key'],
            apiSecret=creds['api_secret']
        )

        # Get device list
        print("\nConnecting to Tuya Cloud...")
        devices = cloud.getdevices()

        if not devices:
            print("❌ No devices found!")
            print("\nPossible issues:")
            print("1. SmartLife account not linked to IoT Platform project")
            print("2. Incorrect API credentials")
            print("3. Wrong region selected")
            return None

        print(f"\n✓ Found {len(devices)} device(s):\n")

        # Display devices
        for i, device in enumerate(devices):
            name = device.get('name', 'Unknown')
            dev_id = device.get('id', 'N/A')
            online = device.get('online', False)
            category = device.get('category', 'unknown')

            status_icon = "🟢" if online else "🔴"
            print(f"{i+1}. {status_icon} {name}")
            print(f"   ID: {dev_id}")
            print(f"   Category: {category}")
            print(f"   Online: {online}")
            print()

        return devices

    except Exception as e:
        print(f"\n❌ Error discovering devices: {e}")
        print("\nPlease verify:")
        print("1. API credentials are correct")
        print("2. SmartLife account is linked in IoT Platform")
        print("3. Region matches your IoT Platform data center")
        return None

def select_valve(devices):
    """Let user select which device is the valve"""
    print("="*70)
    print("📍 Select Your Valve")
    print("="*70)

    # Try to auto-detect valve
    valve_keywords = ['valve', 'water', 'sprinkler', 'aw713', 'gas']
    auto_detected = None

    for i, device in enumerate(devices):
        name = device.get('name', '').lower()
        if any(keyword in name for keyword in valve_keywords):
            auto_detected = i
            break

    if auto_detected is not None:
        print(f"\n🎯 Auto-detected valve: {devices[auto_detected].get('name')}")
        confirm = input("Is this correct? (y/n) [y]: ").strip().lower()
        if confirm in ['', 'y', 'yes']:
            return devices[auto_detected]

    # Manual selection
    while True:
        try:
            choice = input("\nEnter device number (1-{}): ".format(len(devices))).strip()
            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                return devices[idx]
            else:
                print("Invalid number, try again")
        except (ValueError, KeyboardInterrupt):
            print("\nCancelled")
            return None

def get_device_details(cloud, device):
    """Get full device details including local key"""
    print("\n" + "="*70)
    print("📥 Fetching Device Details...")
    print("="*70)

    dev_id = device.get('id')

    try:
        # Get device info with local key
        details = cloud.getdevice(dev_id)

        if not details:
            print("❌ Could not fetch device details")
            return None

        local_key = details.get('local_key', '')
        ip = device.get('ip', '')

        # If no IP from device list, try to get current status
        if not ip:
            try:
                status = cloud.getstatus(dev_id)
                # IP might be in status or we'll need local scan
                print("Note: IP address not available from cloud, will need local discovery")
            except:
                pass

        print(f"\n✓ Device ID: {dev_id}")
        print(f"✓ Local Key: {local_key[:10]}...")
        print(f"✓ IP Address: {ip or 'Will scan locally'}")

        return {
            'id': dev_id,
            'name': device.get('name'),
            'local_key': local_key,
            'ip': ip,
            'version': '3.3'  # Most Tuya devices use 3.3
        }

    except Exception as e:
        print(f"❌ Error getting device details: {e}")
        return None

def scan_local_ip(dev_id, local_key):
    """Scan local network for device IP"""
    print("\n🔍 Scanning local network for device...")
    print("(This may take 20-30 seconds)")

    devices = tinytuya.deviceScan(False, 20)

    if dev_id in devices:
        ip = devices[dev_id].get('ip')
        print(f"✓ Found device at: {ip}")
        return ip
    else:
        print("❌ Could not find device on local network")
        print("Device may be on a different network/VLAN")
        return None

def update_config(valve_info):
    """Update config.py with valve credentials"""
    print("\n" + "="*70)
    print("💾 Updating Configuration...")
    print("="*70)

    config_path = 'config.py'

    try:
        # Read current config
        with open(config_path, 'r') as f:
            lines = f.readlines()

        # Update Tuya credentials
        new_lines = []
        for line in lines:
            if line.startswith('TUYA_DEVICE_ID ='):
                new_lines.append(f'TUYA_DEVICE_ID = \'{valve_info["id"]}\'\n')
            elif line.startswith('TUYA_DEVICE_IP ='):
                ip = valve_info['ip'] or ''
                new_lines.append(f'TUYA_DEVICE_IP = \'{ip}\'\n')
            elif line.startswith('TUYA_LOCAL_KEY ='):
                new_lines.append(f'TUYA_LOCAL_KEY = \'{valve_info["local_key"]}\'\n')
            else:
                new_lines.append(line)

        # Write updated config
        with open(config_path, 'w') as f:
            f.writelines(new_lines)

        print(f"✓ Updated {config_path}")
        print(f"  Device ID: {valve_info['id']}")
        print(f"  Local Key: {valve_info['local_key'][:10]}...")
        print(f"  IP: {valve_info['ip'] or 'Not set (will discover on first use)'}")

        return True

    except Exception as e:
        print(f"❌ Error updating config: {e}")
        return False

def test_connection(valve_info):
    """Test connection to valve"""
    print("\n" + "="*70)
    print("🧪 Testing Valve Connection...")
    print("="*70)

    try:
        # Import valve controller
        from valve_control import ValveController

        print("\nInitializing valve controller...")
        valve = ValveController()

        if not valve.configured:
            print("❌ Valve not configured properly")
            return False

        print("✓ Valve controller initialized")

        # Get status
        print("\nGetting valve status...")
        status = valve.get_status()

        if 'error' in status:
            print(f"❌ Error: {status['error']}")
            return False

        print(f"✓ Valve is {'ON' if status['is_on'] else 'OFF'}")
        print(f"✓ Connection successful!")

        return True

    except Exception as e:
        print(f"❌ Error testing connection: {e}")
        return False

def main():
    """Main setup flow"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Tuya Valve Setup')
    parser.add_argument('--api-key', help='Tuya API Key (Access ID)')
    parser.add_argument('--api-secret', help='Tuya API Secret')
    parser.add_argument('--region', default='us', choices=['us', 'eu', 'cn', 'in'], help='Tuya region')
    args = parser.parse_args()

    try:
        # Get credentials (from args or interactively)
        if args.api_key and args.api_secret:
            print("Using provided API credentials...")
            creds = get_credentials_args(args)
        else:
            creds = get_credentials_interactive()

        # Save credentials for future use
        with open('tinytuya.json', 'w') as f:
            json.dump(creds, f, indent=2)

        # Discover devices
        devices = discover_devices(creds)
        if not devices:
            return 1

        # Select valve
        valve_device = select_valve(devices)
        if not valve_device:
            return 1

        # Initialize cloud for device details
        cloud = tinytuya.Cloud(
            apiRegion=creds['region'],
            apiKey=creds['api_key'],
            apiSecret=creds['api_secret']
        )

        # Get device details
        valve_info = get_device_details(cloud, valve_device)
        if not valve_info:
            return 1

        # If no IP, try local scan
        if not valve_info['ip']:
            ip = scan_local_ip(valve_info['id'], valve_info['local_key'])
            if ip:
                valve_info['ip'] = ip

        # Update config
        if not update_config(valve_info):
            return 1

        # Test connection
        test_connection(valve_info)

        print("\n" + "="*70)
        print("✅ Setup Complete!")
        print("="*70)
        print("\nYour valve is now configured for the deer detection system.")
        print("SmartLife app will continue to work normally.")
        print("\nNext steps:")
        print("1. Test valve: python3 valve_control.py")
        print("2. Start system: python3 main.py")

        return 0

    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        return 1
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
