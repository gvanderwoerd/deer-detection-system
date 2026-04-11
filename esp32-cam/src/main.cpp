/**
 * ESP32-CAM Full Test with LED + Serial Error Reporting
 *
 * LED Patterns:
 * - 3 quick blinks = boot successful
 * - 5 quick blinks = camera init successful
 * - 7 quick blinks = WiFi connected
 * - Slow blink = running normally
 * - Fast blink continuous = failed (check serial for error)
 *
 * Serial Output: Detailed progress and error messages (NOT WORKING - hardware issue)
 */

#include <Arduino.h>
#include <WiFi.h>
#include <esp_camera.h>
#include <ESPmDNS.h>  // For network discovery without needing IP address

#define LED_PIN 33
#define PIR_PIN 14  // PIR motion sensor on GPIO 14

// ============================================================
// WiFi Configuration
// ============================================================
const char* WIFI_SSID = "CityWest_0090E24F";
const char* WIFI_PASSWORD = "cf72cc1722f549aa";

// ============================================================
// Network Identity Configuration (CUSTOMIZE FOR EACH DEVICE!)
// ============================================================
// IMPORTANT: Serial output doesn't work on ESP32-CAM hardware,
// so we can't see the IP address. We solve this with:
// 1. mDNS hostname - access via http://hostname.local:81/
// 2. Static IP - predictable fallback address
//
// FOR MULTIPLE DEVICES:
// - Change MDNS_HOSTNAME for each device (e.g., "esp32cam1", "esp32cam2")
// - Change STATIC_IP last octet for each device (e.g., .100, .101, .102)
// - Keep devices within your router's allowed static IP range
//   (Usually outside DHCP range, e.g., .100-.200 if DHCP uses .2-.99)
// ============================================================

// mDNS Hostname - Device will be accessible at http://HOSTNAME.local:81/
// CUSTOMIZE: Change "esp32cam" to unique name for each device
const char* MDNS_HOSTNAME = "esp32cam";  // Device #1: "esp32cam", Device #2: "esp32cam2", etc.

// Static IP Configuration
// CUSTOMIZE: Change last number (.100) for each device
// Example: Device #1: .100, Device #2: .101, Device #3: .102
IPAddress STATIC_IP(192, 168, 1, 100);   // This device's IP address
IPAddress GATEWAY(192, 168, 1, 1);       // Router IP (usually .1)
IPAddress SUBNET(255, 255, 255, 0);      // Standard home network subnet
IPAddress DNS1(192, 168, 1, 1);          // Primary DNS (usually router)
IPAddress DNS2(8, 8, 8, 8);              // Secondary DNS (Google DNS)

// Camera pins (AI-Thinker ESP32-CAM)
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

WiFiServer server(81);  // Main camera stream server
WiFiServer pirServer(82);  // PIR status server on separate port

void blinkPattern(int count, int onTime, int offTime) {
  for(int i = 0; i < count; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(onTime);
    digitalWrite(LED_PIN, LOW);
    delay(offTime);
  }
}

void errorLoop(const char* errorMsg) {
  Serial.println("========================================");
  Serial.println("FATAL ERROR - HALTED");
  Serial.println("========================================");
  Serial.println(errorMsg);
  Serial.println("========================================");
  Serial.println("System halted. Reset to retry.");

  // Fast blink forever
  while(1) {
    digitalWrite(LED_PIN, HIGH);
    delay(100);
    digitalWrite(LED_PIN, LOW);
    delay(100);
  }
}

void setup() {
  // Initialize serial FIRST with long delay for stability
  Serial.begin(115200);
  delay(3000);  // Give serial time to stabilize

  Serial.println();
  Serial.println();
  Serial.println("========================================");
  Serial.println("ESP32-CAM BOOT SEQUENCE STARTING");
  Serial.println("========================================");
  Serial.println();

  // Initialize LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);
  pinMode(PIR_PIN, INPUT);  // PIR sensor input
  Serial.println("[STEP 1/4] LED initialization");
  Serial.println("  Status: OK");

  // Boot successful = 3 quick blinks
  Serial.println("  LED Pattern: 3 quick blinks (boot OK)");
  blinkPattern(3, 200, 200);
  delay(500);

  // ============================================================
  // STEP 2: Camera Initialization
  // ============================================================
  Serial.println();
  Serial.println("[STEP 2/4] Camera initialization");
  Serial.println("  Configuring camera...");

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if(psramFound()) {
    Serial.println("  PSRAM: FOUND");
    config.frame_size = FRAMESIZE_SVGA;  // 800x600
    config.jpeg_quality = 10;
    config.fb_count = 2;
    Serial.println("  Resolution: SVGA (800x600)");
    Serial.println("  Quality: 10");
    Serial.println("  Frame buffers: 2");
  } else {
    Serial.println("  PSRAM: NOT FOUND");
    config.frame_size = FRAMESIZE_VGA;  // 640x480
    config.jpeg_quality = 12;
    config.fb_count = 1;
    Serial.println("  Resolution: VGA (640x480)");
    Serial.println("  Quality: 12");
    Serial.println("  Frame buffers: 1");
  }

  Serial.println("  Initializing camera driver...");
  esp_err_t err = esp_camera_init(&config);

  if (err != ESP_OK) {
    Serial.print("  Status: FAILED - Error code: 0x");
    Serial.println(err, HEX);
    Serial.println();
    Serial.println("  Camera Error Codes:");
    Serial.println("    0x105 (ESP_ERR_NOT_FOUND) - Camera not detected");
    Serial.println("    0x106 (ESP_ERR_INVALID_STATE) - Camera busy/wrong state");
    Serial.println("    0x101 (ESP_ERR_NO_MEM) - Out of memory");
    Serial.println();
    Serial.println("  Possible causes:");
    Serial.println("    - Camera module not properly connected");
    Serial.println("    - Ribbon cable dirty or damaged");
    Serial.println("    - PSRAM issue");
    Serial.println("    - Insufficient power supply");

    errorLoop("CAMERA INITIALIZATION FAILED");
  }

  Serial.println("  Status: SUCCESS");

  // Test camera capture
  Serial.println("  Testing camera capture...");
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("  Capture Status: FAILED");
    errorLoop("CAMERA CAPTURE TEST FAILED");
  }

  Serial.print("  Capture Status: SUCCESS - ");
  Serial.print(fb->len);
  Serial.println(" bytes");
  Serial.print("  Image size: ");
  Serial.print(fb->width);
  Serial.print("x");
  Serial.println(fb->height);
  esp_camera_fb_return(fb);

  // Camera success = 5 quick blinks
  Serial.println("  LED Pattern: 5 quick blinks (camera OK)");
  blinkPattern(5, 200, 200);
  delay(500);

  // ============================================================
  // STEP 3: WiFi Connection
  // ============================================================
  Serial.println();
  Serial.println("[STEP 3/4] WiFi connection");
  Serial.print("  SSID: ");
  Serial.println(WIFI_SSID);

  // Configure static IP BEFORE connecting
  // This ensures we always get the same IP address
  Serial.println("  Configuring static IP...");
  Serial.print("    Static IP: ");
  Serial.println(STATIC_IP);

  WiFi.mode(WIFI_STA);
  WiFi.config(STATIC_IP, GATEWAY, SUBNET, DNS1, DNS2);

  Serial.println("  Connecting...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
    if (attempts % 20 == 0) Serial.println();
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("  Status: FAILED");
    Serial.println();
    Serial.println("  Possible causes:");
    Serial.println("    - Incorrect SSID or password");
    Serial.println("    - Router out of range");
    Serial.println("    - WiFi antenna issue");
    Serial.println("    - 2.4GHz WiFi disabled on router");

    errorLoop("WIFI CONNECTION FAILED");
  }

  Serial.println("  Status: CONNECTED");
  Serial.print("  IP Address: ");
  Serial.println(WiFi.localIP());
  Serial.print("  Signal Strength: ");
  Serial.print(WiFi.RSSI());
  Serial.println(" dBm");
  Serial.print("  MAC Address: ");
  Serial.println(WiFi.macAddress());

  // Initialize mDNS for network discovery
  // Allows access via http://hostname.local:81/ instead of IP
  Serial.println("  Starting mDNS responder...");
  if (MDNS.begin(MDNS_HOSTNAME)) {
    Serial.print("    mDNS hostname: ");
    Serial.print(MDNS_HOSTNAME);
    Serial.println(".local");
    Serial.print("    Access via: http://");
    Serial.print(MDNS_HOSTNAME);
    Serial.println(".local:81/");
  } else {
    Serial.println("    mDNS FAILED (non-critical, use IP instead)");
  }

  // WiFi success = 7 quick blinks
  Serial.println("  LED Pattern: 7 quick blinks (WiFi OK)");
  blinkPattern(7, 200, 200);
  delay(500);

  // ============================================================
  // STEP 4: Start Streaming Server
  // ============================================================
  Serial.println();
  Serial.println("[STEP 4/4] Starting servers");

  server.begin();
  pirServer.begin();

  Serial.println("  Camera stream server: RUNNING (port 81)");
  Serial.println("  PIR status server: RUNNING (port 82)");
  Serial.println();
  Serial.println("========================================");
  Serial.println("SYSTEM READY - ALL TESTS PASSED");
  Serial.println("========================================");
  Serial.println();
  Serial.println("Stream Access (2 methods):");
  Serial.println("  1. Via mDNS (recommended):");
  Serial.print("     http://");
  Serial.print(MDNS_HOSTNAME);
  Serial.println(".local:81/");
  Serial.println("  2. Via Static IP (fallback):");
  Serial.print("     http://");
  Serial.print(WiFi.localIP());
  Serial.println(":81/");
  Serial.println();
  Serial.println("Waiting for connections...");
  Serial.println("LED will blink slowly while running");
  Serial.println();
  Serial.println("NOTE: Serial output doesn't work on this hardware.");
  Serial.println("      Use LED patterns for status monitoring.");

  digitalWrite(LED_PIN, LOW);
}

void loop() {
  // Handle PIR status requests (port 82) - checked first so it's always responsive
  WiFiClient pirClient = pirServer.available();
  if (pirClient) {
    // Read HTTP request
    String req = "";
    while (pirClient.connected() && !pirClient.available()) delay(1);
    while (pirClient.available()) req += (char)pirClient.read();

    // Return PIR sensor status as JSON
    bool pirState = digitalRead(PIR_PIN) == HIGH;
    pirClient.println("HTTP/1.1 200 OK");
    pirClient.println("Content-Type: application/json");
    pirClient.println("Access-Control-Allow-Origin: *");
    pirClient.println();
    pirClient.print("{\"active\":");
    pirClient.print(pirState ? "true" : "false");
    pirClient.println("}");
    pirClient.stop();
    return;  // Return immediately to keep loop responsive
  }

  // Handle streaming clients (port 81)
  WiFiClient client = server.available();

  if (client) {
    Serial.println(">>> Client connected for streaming");
    digitalWrite(LED_PIN, HIGH);

    // Read HTTP request
    String req = "";
    while (client.connected() && !client.available()) delay(1);
    while (client.available()) req += (char)client.read();

    Serial.println("Sending MJPEG stream...");

    // Send MJPEG headers
    client.println("HTTP/1.1 200 OK");
    client.println("Content-Type: multipart/x-mixed-replace; boundary=frame");
    client.println("Access-Control-Allow-Origin: *");
    client.println();

    // Stream frames
    int frameCount = 0;
    while (client.connected()) {
      camera_fb_t *fb = esp_camera_fb_get();

      if (!fb) {
        Serial.println("ERROR: Camera capture failed during stream");
        break;
      }

      // Send frame with PIR status and WiFi signal strength in headers
      client.println("--frame");
      client.println("Content-Type: image/jpeg");
      client.print("Content-Length: ");
      client.println(fb->len);
      // Include PIR sensor status in custom header
      client.print("X-PIR-Status: ");
      client.println(digitalRead(PIR_PIN) == HIGH ? "active" : "inactive");
      // Include WiFi signal strength (RSSI in dBm)
      client.print("X-WiFi-Signal: ");
      client.println(WiFi.RSSI());
      client.println();
      client.write(fb->buf, fb->len);
      client.println();

      esp_camera_fb_return(fb);

      frameCount++;
      if (frameCount % 30 == 0) {
        Serial.print("Streaming... frame ");
        Serial.println(frameCount);
      }

      delay(33);  // ~30 FPS
    }

    client.stop();
    digitalWrite(LED_PIN, LOW);
    Serial.print("<<< Client disconnected - streamed ");
    Serial.print(frameCount);
    Serial.println(" frames");
    Serial.println();
  }

  // Slow blink when idle
  static unsigned long lastBlink = 0;
  static bool ledState = false;
  if (millis() - lastBlink > 1000) {
    ledState = !ledState;
    digitalWrite(LED_PIN, ledState);
    lastBlink = millis();

    if (ledState) {
      Serial.print(".");  // Heartbeat
    }
  }
}
