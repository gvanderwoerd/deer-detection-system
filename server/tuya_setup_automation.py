#!/usr/bin/env python3
"""
Automated Tuya IoT Platform Setup
Automates account creation and device discovery for deer detection system
"""

import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Configuration
EMAIL = "gvanderwoerd@icloud.com"
PASSWORD = "987Braden!"
REGION = "us"  # Americas (British Columbia)

def setup_driver():
    """Initialize Chrome driver with options"""
    print("Setting up Chrome browser...")
    options = Options()
    # Comment out headless mode so user can see what's happening
    # options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def wait_for_user_input(prompt):
    """Wait for user to provide input"""
    return input(f"\n{prompt}: ").strip()

def tuya_signup_or_login(driver):
    """Automate Tuya IoT Platform signup/login"""
    print("\n=== Step 1: Accessing Tuya IoT Platform ===")
    driver.get("https://iot.tuya.com/")
    time.sleep(3)

    try:
        # Try to find login/signup button
        print("Looking for login button...")
        wait = WebDriverWait(driver, 10)

        # Click login/signup button
        login_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Sign In')] | //a[contains(text(), 'Sign In')] | //button[contains(text(), 'Login')]")))
        login_btn.click()
        time.sleep(2)

        # Enter email
        print(f"Entering email: {EMAIL}")
        email_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='email'] | //input[@placeholder='Email'] | //input[@name='email']")))
        email_input.clear()
        email_input.send_keys(EMAIL)
        time.sleep(1)

        # Check if we need to sign up or login
        # Try clicking "Next" or "Continue"
        next_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Next')] | //button[contains(text(), 'Continue')]")
        next_btn.click()
        time.sleep(2)

        # Check if account exists (login) or needs creation (signup)
        try:
            # If password field appears, account exists - do login
            password_input = driver.find_element(By.XPATH, "//input[@type='password']")
            print("Account exists - logging in...")
            password_input.send_keys(PASSWORD)

            # Click login button
            login_submit = driver.find_element(By.XPATH, "//button[@type='submit'] | //button[contains(text(), 'Sign In')] | //button[contains(text(), 'Login')]")
            login_submit.click()
            time.sleep(3)

            print("✓ Login successful")

        except:
            # Account doesn't exist - need to sign up
            print("Account doesn't exist - creating new account...")

            # Send verification code
            print("Requesting verification code...")
            verify_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Send')] | //button[contains(text(), 'Get Code')]")
            verify_btn.click()
            time.sleep(2)

            # Ask user for verification code
            print("\n" + "="*50)
            print("📧 CHECK YOUR EMAIL!")
            print(f"A verification code has been sent to: {EMAIL}")
            print("="*50)
            verification_code = wait_for_user_input("Enter the verification code from your email")

            # Enter verification code
            code_input = driver.find_element(By.XPATH, "//input[@placeholder='Code'] | //input[@placeholder='Verification Code']")
            code_input.send_keys(verification_code)

            # Set password
            password_input = driver.find_element(By.XPATH, "//input[@type='password']")
            password_input.send_keys(PASSWORD)

            # Submit signup
            signup_btn = driver.find_element(By.XPATH, "//button[@type='submit'] | //button[contains(text(), 'Sign Up')]")
            signup_btn.click()
            time.sleep(3)

            print("✓ Account created successfully")

        return True

    except Exception as e:
        print(f"❌ Error during login/signup: {e}")
        print("\nPlease complete the login manually in the browser window.")
        wait_for_user_input("Press Enter when you've logged in")
        return True

def create_cloud_project(driver):
    """Create a new cloud project"""
    print("\n=== Step 2: Creating Cloud Project ===")

    try:
        wait = WebDriverWait(driver, 10)

        # Navigate to Cloud Development
        print("Navigating to Cloud Development...")
        driver.get("https://iot.tuya.com/cloud/")
        time.sleep(3)

        # Click "Create Cloud Project"
        create_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Create')] | //a[contains(text(), 'Create Project')]")))
        create_btn.click()
        time.sleep(2)

        # Fill in project details
        print("Filling in project details...")

        # Project name
        name_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Project name'] | //input[@name='name']")))
        name_input.send_keys("Deer Detection System")

        # Industry: Smart Home
        industry_select = driver.find_element(By.XPATH, "//div[contains(text(), 'Industry')] | //label[contains(text(), 'Industry')]")
        industry_select.click()
        time.sleep(1)
        smart_home = driver.find_element(By.XPATH, "//*[contains(text(), 'Smart Home')]")
        smart_home.click()

        # Development Method: Smart Home
        dev_method = driver.find_element(By.XPATH, "//div[contains(text(), 'Development Method')]")
        dev_method.click()
        time.sleep(1)
        smart_home_method = driver.find_element(By.XPATH, "//*[contains(text(), 'Smart Home')]")
        smart_home_method.click()

        # Data Center: Americas or closest
        datacenter = driver.find_element(By.XPATH, "//div[contains(text(), 'Data Center')]")
        datacenter.click()
        time.sleep(1)
        us_datacenter = driver.find_element(By.XPATH, "//*[contains(text(), 'Western America')] | //*[contains(text(), 'Central Europe')]")
        us_datacenter.click()

        # Submit
        create_submit = driver.find_element(By.XPATH, "//button[@type='submit'] | //button[contains(text(), 'Create')]")
        create_submit.click()
        time.sleep(3)

        print("✓ Cloud project created")
        return True

    except Exception as e:
        print(f"Note: {e}")
        print("\nPlease create the cloud project manually if it didn't work:")
        print("1. Go to Cloud → Development")
        print("2. Click 'Create Cloud Project'")
        print("3. Fill in: Name='Deer Detection System', Industry='Smart Home', Data Center='Western America'")
        wait_for_user_input("Press Enter when project is created")
        return True

def get_api_credentials(driver):
    """Extract API credentials from project overview"""
    print("\n=== Step 3: Getting API Credentials ===")

    try:
        # Should be on project page now
        # Look for Access ID and Access Secret
        wait = WebDriverWait(driver, 10)

        # Navigate to Overview tab
        driver.get("https://iot.tuya.com/cloud/")
        time.sleep(2)

        # Find the project and click it
        project = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Deer Detection')]")))
        project.click()
        time.sleep(2)

        # Get Access ID (API Key)
        access_id = driver.find_element(By.XPATH, "//*[contains(text(), 'Access ID')]/following-sibling::*").text
        access_secret = driver.find_element(By.XPATH, "//*[contains(text(), 'Access Secret')]/following-sibling::*").text

        print(f"✓ Access ID: {access_id}")
        print(f"✓ Access Secret: {access_secret[:10]}...")

        return {
            'api_key': access_id,
            'api_secret': access_secret,
            'region': REGION
        }

    except Exception as e:
        print(f"Could not auto-extract credentials: {e}")
        print("\nPlease copy the credentials manually:")
        api_key = wait_for_user_input("Enter Access ID / Client ID")
        api_secret = wait_for_user_input("Enter Access Secret / Client Secret")

        return {
            'api_key': api_key,
            'api_secret': api_secret,
            'region': REGION
        }

def link_smart_life_account(driver):
    """Link Smart Life app account to project"""
    print("\n=== Step 4: Linking Smart Life Account ===")

    try:
        # Navigate to Devices tab
        devices_tab = driver.find_element(By.XPATH, "//a[contains(text(), 'Devices')] | //div[contains(text(), 'Devices')]")
        devices_tab.click()
        time.sleep(2)

        # Click "Link App Account"
        link_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Link')] | //button[contains(text(), 'Add Account')]")
        link_btn.click()
        time.sleep(2)

        # Enter Smart Life email
        email_input = driver.find_element(By.XPATH, "//input[@type='email'] | //input[@placeholder='Email']")
        email_input.send_keys(EMAIL)

        # Submit
        submit_btn = driver.find_element(By.XPATH, "//button[@type='submit'] | //button[contains(text(), 'Confirm')]")
        submit_btn.click()
        time.sleep(2)

        print("✓ Smart Life account linked")

    except Exception as e:
        print(f"Note: {e}")
        print("\nPlease link Smart Life account manually if needed:")
        print("1. Go to Devices tab")
        print("2. Click 'Link Tuya App Account'")
        print(f"3. Enter email: {EMAIL}")
        wait_for_user_input("Press Enter when account is linked")

def main():
    """Main automation flow"""
    print("="*60)
    print("🦌 Deer Detection System - Tuya Setup Automation")
    print("="*60)

    driver = None

    try:
        driver = setup_driver()

        # Step 1: Login/Signup
        if not tuya_signup_or_login(driver):
            print("❌ Login failed")
            return

        # Step 2: Create project (or use existing)
        create_cloud_project(driver)

        # Step 3: Get API credentials
        credentials = get_api_credentials(driver)

        # Step 4: Link Smart Life account
        link_smart_life_account(driver)

        # Save credentials
        print("\n=== Saving Credentials ===")
        with open('tuya_credentials.json', 'w') as f:
            json.dump(credentials, f, indent=2)
        print("✓ Credentials saved to tuya_credentials.json")

        print("\n" + "="*60)
        print("✅ Setup Complete!")
        print("="*60)
        print("\nNext: Discovering devices...")

        input("\nPress Enter to close browser and continue...")

        return credentials

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nBrowser window will stay open for manual completion.")
        input("Press Enter when done...")

    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    creds = main()
    if creds:
        print(f"\nAPI Key: {creds['api_key']}")
        print(f"Region: {creds['region']}")
