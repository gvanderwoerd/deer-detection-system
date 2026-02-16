#!/usr/bin/env python3
"""
Tuya IoT Platform Browser Automation
Takes control of existing browser session to complete setup
"""

import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

EMAIL = "gvanderwoerd@icloud.com"
REGION = "us"

def connect_to_existing_browser():
    """Connect to existing Chrome browser session"""
    print("Connecting to existing browser...")
    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

    try:
        driver = webdriver.Chrome(options=options)
        print("✓ Connected to browser")
        return driver
    except Exception as e:
        print(f"❌ Could not connect to browser: {e}")
        print("\nTo allow remote control, restart Chrome with:")
        print("google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug")
        return None

def close_dialogs(driver):
    """Close any open dialogs"""
    try:
        # Try to find and close modal/dialog
        wait = WebDriverWait(driver, 5)
        close_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'close')] | //button[contains(text(), 'Close')] | //*[@class='modal']//button")
        for btn in close_buttons:
            try:
                btn.click()
                print("✓ Closed dialog")
                time.sleep(1)
            except:
                pass
    except:
        pass

def create_cloud_project(driver):
    """Navigate and create cloud project"""
    print("\n=== Creating Cloud Project ===")

    try:
        wait = WebDriverWait(driver, 10)

        # Look for Cloud menu
        print("Looking for Cloud menu...")
        cloud_menu = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//a[contains(text(), 'Cloud')] | //div[contains(text(), 'Cloud')] | //span[contains(text(), 'Cloud')]"
        )))
        cloud_menu.click()
        time.sleep(2)

        # Click Development or Create Project
        print("Looking for Create Project button...")
        create_btn = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//button[contains(text(), 'Create')] | //a[contains(text(), 'Create')] | //button[contains(text(), 'New Project')]"
        )))
        create_btn.click()
        time.sleep(2)

        # Fill in project form
        print("Filling in project details...")

        # Project name
        name_input = wait.until(EC.presence_of_element_located((
            By.XPATH,
            "//input[@placeholder='Project name'] | //input[@name='name'] | //input[contains(@class, 'project-name')]"
        )))
        name_input.clear()
        name_input.send_keys("Deer Detection System")
        time.sleep(1)

        # Find and select Industry dropdown
        print("Selecting Smart Home industry...")
        industry_selects = driver.find_elements(By.XPATH, "//select | //div[contains(@class, 'select')] | //div[contains(@class, 'dropdown')]")
        for select in industry_selects:
            try:
                select.click()
                time.sleep(1)
                smart_home = driver.find_element(By.XPATH, "//*[contains(text(), 'Smart Home')]")
                smart_home.click()
                time.sleep(1)
                break
            except:
                continue

        # Submit form
        print("Submitting project creation...")
        submit_btn = driver.find_element(By.XPATH, "//button[@type='submit'] | //button[contains(text(), 'Create')] | //button[contains(text(), 'Confirm')]")
        submit_btn.click()
        time.sleep(3)

        print("✓ Project created successfully")
        return True

    except Exception as e:
        print(f"Note: {e}")
        print("Could not auto-create project. May already exist.")
        return False

def link_smartlife_account(driver):
    """Link SmartLife app account"""
    print("\n=== Linking SmartLife Account ===")

    try:
        wait = WebDriverWait(driver, 10)

        # Go to Devices tab
        devices_tab = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//a[contains(text(), 'Devices')] | //div[contains(text(), 'Devices')] | //tab[contains(text(), 'Devices')]"
        )))
        devices_tab.click()
        time.sleep(2)

        # Click Link App Account
        link_btn = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//button[contains(text(), 'Link')] | //button[contains(text(), 'Add Account')] | //a[contains(text(), 'Link App')]"
        )))
        link_btn.click()
        time.sleep(2)

        # Enter email
        email_input = wait.until(EC.presence_of_element_located((
            By.XPATH,
            "//input[@type='email'] | //input[@placeholder='Email']"
        )))
        email_input.send_keys(EMAIL)

        # Submit
        submit_btn = driver.find_element(By.XPATH, "//button[@type='submit'] | //button[contains(text(), 'Confirm')] | //button[contains(text(), 'Link')]")
        submit_btn.click()
        time.sleep(3)

        print("✓ SmartLife account linked")
        return True

    except Exception as e:
        print(f"Note: {e}")
        print("Could not auto-link account. May already be linked.")
        return False

def extract_api_credentials(driver):
    """Extract API credentials from Overview page"""
    print("\n=== Extracting API Credentials ===")

    try:
        wait = WebDriverWait(driver, 10)

        # Go to Overview tab
        overview_tab = driver.find_element(By.XPATH, "//a[contains(text(), 'Overview')] | //div[contains(text(), 'Overview')]")
        overview_tab.click()
        time.sleep(2)

        # Find Access ID
        print("Looking for Access ID...")
        access_id_element = driver.find_element(By.XPATH, "//*[contains(text(), 'Access ID')]/following-sibling::* | //*[contains(text(), 'Client ID')]/following-sibling::*")
        access_id = access_id_element.text.strip()

        # Find Access Secret
        print("Looking for Access Secret...")
        access_secret_element = driver.find_element(By.XPATH, "//*[contains(text(), 'Access Secret')]/following-sibling::* | //*[contains(text(), 'Client Secret')]/following-sibling::*")
        access_secret = access_secret_element.text.strip()

        if access_id and access_secret:
            print(f"✓ Access ID: {access_id}")
            print(f"✓ Access Secret: {access_secret[:10]}...")

            return {
                'api_key': access_id,
                'api_secret': access_secret,
                'region': REGION
            }
        else:
            raise Exception("Could not extract credentials")

    except Exception as e:
        print(f"❌ Could not auto-extract credentials: {e}")
        print("\nPlease copy them manually from the Overview tab")
        return None

def main():
    print("="*60)
    print("🦌 Tuya IoT Platform - Browser Automation")
    print("="*60)

    driver = connect_to_existing_browser()
    if not driver:
        return None

    try:
        # Close any dialogs
        close_dialogs(driver)

        # Create project (or skip if exists)
        create_cloud_project(driver)

        # Link SmartLife account (or skip if exists)
        link_smartlife_account(driver)

        # Extract API credentials
        credentials = extract_api_credentials(driver)

        if credentials:
            print("\n" + "="*60)
            print("✅ Setup Complete!")
            print("="*60)
            print(f"\nAPI Key: {credentials['api_key']}")
            print(f"API Secret: {credentials['api_secret'][:20]}...")
            print(f"Region: {credentials['region']}")

            # Save credentials
            import json
            with open('tuya_credentials.json', 'w') as f:
                json.dump(credentials, f, indent=2)
            print("\n✓ Credentials saved to tuya_credentials.json")

            return credentials
        else:
            return None

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return None
    finally:
        print("\nBrowser session remains open for manual review")

if __name__ == "__main__":
    main()
