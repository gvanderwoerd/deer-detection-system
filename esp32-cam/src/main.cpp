/**
 * ESP32-CAM Deer Detection System Firmware
 *
 * Features:
 * - Deep sleep mode for power saving
 * - GPIO wake on motion detection (Yard Sentinel trigger)
 * - MJPEG streaming server
 * - Auto-sleep after activity window
 */

#include <Arduino.h>
#include <WiFi.h>
#include <esp_camera.h>
#include <esp_sleep.h>

// ===== Configuration =====
const char* WIFI_SSID = "CityWest_0090E24F";
const char* WIFI_PASSWORD = "cf72cc1722f549aa";

// Motion trigger GPIO (connected to Yard Sentinel output)
const int MOTION_TRIGGER_PIN = 13;  // GPIO 13

// Activity window (milliseconds) - how long to stay awake after trigger
const unsigned long ACTIVE_WINDOW_MS = 5 * 60 * 1000;  // 5 minutes

// LED pin for status indication
const int LED_PIN = 33;  // Built-in LED on most ESP32-CAM boards

// ===== Camera Configuration =====
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

// ===== Global Variables =====
WiFiServer server(81);  // MJPEG streaming on port 81
unsigned long wakeTime = 0;
bool streamingActive = false;

// ===== Function Declarations =====
void setupCamera();
void setupWiFi();
void setupDeepSleep();
void handleStream();
void blinkLED(int times);

// ===== Setup =====
void setup() {
  Serial.begin(115200);
  Serial.println("\n\n=== ESP32-CAM Deer Detection System ===");

  // Setup LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);  // LED ON during startup

  // Record wake time
  wakeTime = millis();

  // Print wake reason
  esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
  switch(wakeup_reason) {
    case ESP_SLEEP_WAKEUP_EXT0:
      Serial.println("Woke up by motion trigger!");
      blinkLED(3);
      break;
    case ESP_SLEEP_WAKEUP_TIMER:
      Serial.println("Woke up by timer");
      break;
    default:
      Serial.println("Cold boot / reset");
      break;
  }

  // Initialize camera
  setupCamera();

  // Connect to WiFi
  setupWiFi();

  // Start streaming server
  server.begin();
  Serial.println("MJPEG server started on port 81");
  Serial.print("Stream URL: http://");
  Serial.print(WiFi.localIP());
  Serial.println(":81/stream");

  // Setup deep sleep
  setupDeepSleep();

  digitalWrite(LED_PIN, LOW);  // LED OFF - ready
}

// ===== Main Loop =====
void loop() {
  // Check if activity window expired
  if (millis() - wakeTime > ACTIVE_WINDOW_MS) {
    Serial.println("Activity window expired - entering deep sleep");
    delay(100);
    esp_deep_sleep_start();
  }

  // Handle streaming
  handleStream();

  delay(1);  // Small delay to prevent watchdog
}

// ===== Camera Setup =====
void setupCamera() {
  Serial.println("Initializing camera...");

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

  // Image quality settings
  if(psramFound()) {
    Serial.println("PSRAM found - using high quality settings");
    config.frame_size = FRAMESIZE_SVGA;  // 800x600
    config.jpeg_quality = 10;  // 0-63, lower is higher quality
    config.fb_count = 2;
  } else {
    Serial.println("PSRAM not found - using low quality settings");
    config.frame_size = FRAMESIZE_VGA;  // 640x480
    config.jpeg_quality = 12;
    config.fb_count = 1;
  }

  // Initialize camera
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x\n", err);
    // Blink LED rapidly to indicate error
    for(int i = 0; i < 10; i++) {
      digitalWrite(LED_PIN, !digitalRead(LED_PIN));
      delay(100);
    }
    ESP.restart();
  }

  Serial.println("Camera initialized successfully");

  // Additional sensor settings
  sensor_t * s = esp_camera_sensor_get();
  if (s != NULL) {
    // Flip image if needed
    // s->set_vflip(s, 1);  // Vertical flip
    // s->set_hmirror(s, 1);  // Horizontal mirror

    // Auto settings
    s->set_whitebal(s, 1);  // Auto white balance
    s->set_awb_gain(s, 1);  // Auto white balance gain
    s->set_exposure_ctrl(s, 1);  // Auto exposure
    s->set_aec2(s, 1);  // Auto exposure 2
    s->set_gain_ctrl(s, 1);  // Auto gain
    s->set_agc_gain(s, 0);  // Auto gain value
    s->set_bpc(s, 1);  // Black pixel correction
    s->set_wpc(s, 1);  // White pixel correction
    s->set_lenc(s, 1);  // Lens correction
  }
}

// ===== WiFi Setup =====
void setupWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Signal strength: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println("\nWiFi connection failed!");
    Serial.println("Entering deep sleep...");
    delay(1000);
    esp_deep_sleep_start();
  }
}

// ===== Deep Sleep Setup =====
void setupDeepSleep() {
  Serial.println("Configuring deep sleep wake sources...");

  // Wake on GPIO (motion trigger from Yard Sentinel)
  // EXT0: Wake when pin goes HIGH
  esp_sleep_enable_ext0_wakeup((gpio_num_t)MOTION_TRIGGER_PIN, 1);

  Serial.print("Will wake on GPIO ");
  Serial.print(MOTION_TRIGGER_PIN);
  Serial.println(" going HIGH");
}

// ===== Stream Handler =====
void handleStream() {
  WiFiClient client = server.available();

  if (!client) {
    return;
  }

  Serial.println("Client connected for streaming");
  streamingActive = true;
  digitalWrite(LED_PIN, HIGH);  // LED ON during streaming

  // Wait for HTTP request
  String req = "";
  while (client.connected() && !client.available()) {
    delay(1);
  }

  while (client.available()) {
    req += (char)client.read();
  }

  Serial.println("Request received");

  // Send HTTP headers for MJPEG stream
  client.println("HTTP/1.1 200 OK");
  client.println("Content-Type: multipart/x-mixed-replace; boundary=frame");
  client.println("Access-Control-Allow-Origin: *");
  client.println();

  // Stream frames
  while (client.connected()) {
    camera_fb_t *fb = esp_camera_fb_get();

    if (!fb) {
      Serial.println("Camera capture failed");
      break;
    }

    // Send frame
    client.println("--frame");
    client.println("Content-Type: image/jpeg");
    client.print("Content-Length: ");
    client.println(fb->len);
    client.println();
    client.write(fb->buf, fb->len);
    client.println();

    esp_camera_fb_return(fb);

    // Small delay between frames
    delay(33);  // ~30 FPS
  }

  client.stop();
  streamingActive = false;
  digitalWrite(LED_PIN, LOW);  // LED OFF
  Serial.println("Client disconnected");
}

// ===== Utility Functions =====
void blinkLED(int times) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(200);
    digitalWrite(LED_PIN, LOW);
    delay(200);
  }
}
