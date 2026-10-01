/*
 ============================================================================
  Layer 6: Wearable Activity Recognition Hardware Firmware
  Microcontroller: ESP32 DevKit V1
  Sensors:         MPU6050 (6-axis IMU) + DHT11 (Temperature & Humidity)
  Actuators:       Alert LED + Buzzer
  Protocol:        MQTT over WiFi -> HiveMQ Public Broker (broker.hivemq.com)
 ============================================================================
 
 Wiring Diagram:
  - MPU6050:
      VCC  -> 3.3V
      GND  -> GND
      SDA  -> GPIO 21
      SCL  -> GPIO 22
  - DHT11:
      VCC  -> 3.3V or 5V
      GND  -> GND
      DATA -> GPIO 4 (10k pullup recommended)
  - Actuators:
      LED_PIN    -> GPIO 18 (via 220 Ohm resistor to GND)
      BUZZER_PIN -> GPIO 19 (via NPN transistor or direct active buzzer)
 ============================================================================
*/

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <DHT.h>
#include <ArduinoJson.h>

// ----------------- WiFi & HiveMQ Configuration -----------------
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// HiveMQ Cloud Broker Settings (From your HiveMQ Cloud Console)
// Paste your cluster host here (e.g. 24d7e24e34b544e586ec5a85804a4e7f.s1.eu.hivemq.cloud)
const char* mqtt_server = "24d7e24e34b544e586ec5a85804a4e7f.s1.eu.hivemq.cloud";
const int   mqtt_port   = 8883; // 8883 for HiveMQ Cloud TLS (or 1883 for plain broker.hivemq.com)
const char* mqtt_user   = "YOUR_HIVEMQ_USERNAME"; // Created under Access Management -> Credentials
const char* mqtt_pass   = "YOUR_HIVEMQ_PASSWORD";

// Topics
const char* topic_sensor   = "wearable/activity/iot_lab/sensor";
const char* topic_actuator = "wearable/activity/iot_lab/actuator";
const char* topic_alert    = "wearable/activity/iot_lab/alert";

// ----------------- Pin Definitions -----------------
#define DHTPIN 4
#define DHTTYPE DHT11
#define LED_PIN 18
#define BUZZER_PIN 19

// ----------------- Sensor & Client Instances -----------------
Adafruit_MPU6050 mpu;
DHT dht(DHTPIN, DHTTYPE);
WiFiClientSecure espClient; // Uses TLS for HiveMQ Cloud port 8883
PubSubClient client(espClient);

// Timing
unsigned long lastMsg = 0;
const unsigned long interval = 1000; // 1 second publish interval

// ----------------- Actuator Control Function -----------------
void triggerAlarmSequence(int durationMs = 2000) {
  unsigned long start = millis();
  while (millis() - start < durationMs) {
    digitalWrite(LED_PIN, HIGH);
    digitalWrite(BUZZER_PIN, HIGH);
    delay(150);
    digitalWrite(LED_PIN, LOW);
    digitalWrite(BUZZER_PIN, LOW);
    delay(150);
  }
}

// ----------------- MQTT Callback for Actuators -----------------
void callback(char* topic, byte* message, unsigned int length) {
  String msgStr = "";
  for (unsigned int i = 0; i < length; i++) {
    msgStr += (char)message[i];
  }
  Serial.print("Message arrived on topic [");
  Serial.print(topic);
  Serial.print("]: ");
  Serial.println(msgStr);

  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, msgStr);
  if (!error) {
    const char* cmd = doc["command"];
    if (cmd && strcmp(cmd, "TRIGGER_ALARM") == 0) {
      Serial.println("ALERT! Activating Onboard Buzzer & Emergency LED!");
      triggerAlarmSequence(2500);
    }
  }
}

// ----------------- Connect to WiFi -----------------
void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected successfully!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi connection failed! Check credentials.");
  }
}

// ----------------- Reconnect to HiveMQ -----------------
void reconnect() {
  while (!client.connected()) {
    Serial.print("Connecting to HiveMQ Cloud MQTT Broker (TLS)...");
    String clientId = "ESP32_Wearable_" + String(random(0xffff), HEX);
    
    // Connect with HiveMQ Cloud Credentials
    bool connected = false;
    if (strlen(mqtt_user) > 0 && strlen(mqtt_pass) > 0) {
      connected = client.connect(clientId.c_str(), mqtt_user, mqtt_pass);
    } else {
      connected = client.connect(clientId.c_str());
    }

    if (connected) {
      Serial.println("\nConnected to HiveMQ Cloud successfully!");
      // Subscribe to remote actuator commands
      client.subscribe(topic_actuator);
      Serial.print("Subscribed to actuator topic: ");
      Serial.println(topic_actuator);
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" retrying in 5 seconds...");
      delay(5000);
    }
  }
}

// ----------------- Setup -----------------
void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);

  Wire.begin(21, 22); // SDA, SCL

  // Initialize MPU6050
  if (!mpu.begin()) {
    Serial.println("Failed to find MPU6050 chip! Check I2C wiring.");
  } else {
    Serial.println("MPU6050 Initialized successfully!");
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  }

  // Initialize DHT11
  dht.begin();
  Serial.println("DHT11 Initialized.");

  setup_wifi();

  // Configure TLS security (allow HiveMQ Cloud SSL)
  espClient.setInsecure();

  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

// ----------------- Main Loop -----------------
void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  unsigned long now = millis();
  if (now - lastMsg > interval) {
    lastMsg = now;

    // Read MPU6050
    sensors_event_t a, g, temp_mpu;
    mpu.getEvent(&a, &g, &temp_mpu);

    // Read DHT11
    float h = dht.readHumidity();
    float t = dht.readTemperature();
    if (isnan(h) || isnan(t)) {
      h = 50.0;
      t = temp_mpu.temperature; // Fallback to MPU on-die temperature sensor
    }

    float ax = a.acceleration.x;
    float ay = a.acceleration.y;
    float az = a.acceleration.z;
    float gx = g.gyro.x * 57.2957795; // Convert rad/s to deg/s
    float gy = g.gyro.y * 57.2957795;
    float gz = g.gyro.z * 57.2957795;

    float accel_mag = sqrt(ax * ax + ay * ay + az * az);

    // Edge Fall Detection (Instant Fail-Safe)
    if (accel_mag > 25.0) {
      Serial.println("EDGE ALERT: Local Fall Impact Detected!");
      digitalWrite(LED_PIN, HIGH);
      digitalWrite(BUZZER_PIN, HIGH);
      delay(300);
      digitalWrite(LED_PIN, LOW);
      digitalWrite(BUZZER_PIN, LOW);
    }

    // Build JSON Payload
    StaticJsonDocument<384> doc;
    doc["device_id"] = "ESP32_PHYSICAL_01";
    doc["timestamp"] = String(now / 1000);
    doc["ax"] = round(ax * 100) / 100.0;
    doc["ay"] = round(ay * 100) / 100.0;
    doc["az"] = round(az * 100) / 100.0;
    doc["gx"] = round(gx * 100) / 100.0;
    doc["gy"] = round(gy * 100) / 100.0;
    doc["gz"] = round(gz * 100) / 100.0;
    doc["temperature"] = round(t * 10) / 10.0;
    doc["humidity"] = round(h * 10) / 10.0;

    char buffer[384];
    serializeJson(doc, buffer);

    Serial.print("Publishing to HiveMQ: ");
    Serial.println(buffer);
    client.publish(topic_sensor, buffer);
  }
}
