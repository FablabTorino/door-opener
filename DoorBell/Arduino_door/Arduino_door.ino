#include <WiFiNINA.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "arduino_secrets.h"

// WIFI config (credentials in arduino_secrets.h, see arduino_secrets.h.example)
const char* ssid = SECRET_SSID;
const char* password = SECRET_PASS;

// MQTT config
const char* mqtt_server = "192.168.0.1";
const char* mqtt_client_id = "ArduinoClient";
const char* mqtt_topic_door1 = "esp-rfid/send";

// Liveness for DoorMonitor: "online" every 60 s, "offline" as Last Will,
// "rebooting" before the planned daily reboot (same scheme as the Telegram bots)
const char* status_topic = "doors/status/doorbell-relay";
const unsigned long heartbeatInterval = 60UL * 1000;

// Reconnect pacing. Reconnects never block forever, so the relay still
// switches off on time and the board can always reach the reboot checks below.
const unsigned long wifiRetryInterval = 10UL * 1000;
const unsigned long mqttRetryInterval = 5UL * 1000;

// Reboot if WiFi/MQTT stay down this long (power-cycling by hand fixed a hang before)
const unsigned long disconnectedRebootAfter = 5UL * 60 * 1000;

// Daily reboot
const unsigned long rebootInterval = 24UL * 60 * 60 * 1000;

// Relay
const int relayPin = 4;
const unsigned long relayDuration = 3000;
unsigned long relayOnTime = 0;

// Network objects
WiFiClient espClient;
PubSubClient client(espClient);

// Timers (millis)
unsigned long lastConnected = 0;     // last time WiFi and MQTT were both up
unsigned long lastWifiAttempt = 0;
unsigned long lastMqttAttempt = 0;
unsigned long lastHeartbeat = 0;
bool wifiAttempted = false;
bool mqttAttempted = false;

// Function prototypes
bool ensureWiFi();
bool ensureMQTT();
void publishStatus(const char* status);
void triggerRelay();
void releaseRelayIfDue();
void callback(char* topic, byte* payload, unsigned int length);
void reboot();

// Setup
void setup() {
  Serial.begin(9600);
  Serial.println("Booted");

  pinMode(relayPin, OUTPUT);
  digitalWrite(relayPin, LOW);

  // LED on = WiFi and MQTT connected
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);
  // Broker publishes the Last Will after ~1.5x keepalive of silence
  client.setKeepAlive(15);
  // Bound how long a failed connect can hold up the loop
  client.setSocketTimeout(5);

  lastConnected = millis();
}

// Main loop
void loop() {
  releaseRelayIfDue();

  // Reboot every 24h (wait for the relay to be released first)
  if (millis() >= rebootInterval && relayOnTime == 0) {
    Serial.print("Daily reboot at millis=");
    Serial.println(millis());
    publishStatus("rebooting");
    reboot();
  }

  bool connected = ensureWiFi() && ensureMQTT();
  digitalWrite(LED_BUILTIN, connected ? HIGH : LOW);

  if (connected) {
    lastConnected = millis();
    client.loop();

    if (millis() - lastHeartbeat >= heartbeatInterval) {
      publishStatus("online");
    }
  } else if (millis() - lastConnected >= disconnectedRebootAfter && relayOnTime == 0) {
    Serial.println("Disconnected for too long, rebooting");
    reboot();
  }
}

// Wi-Fi: one attempt per wifiRetryInterval. Returns true when connected.
bool ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return true;
  }
  if (wifiAttempted && millis() - lastWifiAttempt < wifiRetryInterval) {
    return false;
  }
  wifiAttempted = true;
  lastWifiAttempt = millis();

  Serial.print("WiFi connecting to ");
  Serial.println(ssid);
  WiFi.disconnect();
  if (WiFi.begin(ssid, password) != WL_CONNECTED) {
    Serial.println("WiFi connect failed, will retry");
    return false;
  }

  Serial.print("WiFi connected, IP ");
  Serial.print(WiFi.localIP());
  Serial.print(", RSSI ");
  Serial.println(WiFi.RSSI());
  return true;
}

// MQTT: one attempt per mqttRetryInterval. Returns true when connected.
bool ensureMQTT() {
  if (client.connected()) {
    return true;
  }
  if (mqttAttempted && millis() - lastMqttAttempt < mqttRetryInterval) {
    return false;
  }
  mqttAttempted = true;
  lastMqttAttempt = millis();

  Serial.print("MQTT connecting to ");
  Serial.println(mqtt_server);
  if (!client.connect(mqtt_client_id, status_topic, 0, false, "offline")) {
    Serial.print("MQTT connect failed, state ");
    Serial.print(client.state());
    Serial.println(", will retry");
    return false;
  }

  client.subscribe(mqtt_topic_door1);
  Serial.println("MQTT connected");
  publishStatus("online");
  return true;
}

void publishStatus(const char* status) {
  if (client.connected() && client.publish(status_topic, status)) {
    lastHeartbeat = millis();
  }
}

// MQTT callback
void callback(char* topic, byte* payload, unsigned int length) {

  String message;
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  Serial.print("MQTT [");
  Serial.print(topic);
  Serial.print("] ");
  Serial.println(message);

  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, message)) {
    Serial.println("JSON parse error, ignored");
    return;
  }

  const char* desc = doc["desc"] | "";
  const char* cmd  = doc["cmd"]  | "";

  if (strcmp(desc, "Doorbell ringing") == 0 && strcmp(cmd, "event") == 0) {
    Serial.println("Doorbell ringing -> Relay ON");
    triggerRelay();
  }
}

// Relay trigger
void triggerRelay() {
  digitalWrite(relayPin, HIGH);
  relayOnTime = millis();
}

// Turn off relay after relayDuration
void releaseRelayIfDue() {
  if (relayOnTime > 0 && millis() - relayOnTime >= relayDuration) {
    digitalWrite(relayPin, LOW);
    relayOnTime = 0;
    Serial.println("Relay OFF");
  }
}

// Software reset (Uno WiFi Rev2 / ATmega4809)
void reboot() {
  Serial.flush();
  client.disconnect();   // clean disconnect: the Last Will is not sent
  delay(100);
  _PROTECTED_WRITE(RSTCTRL.SWRR, RSTCTRL_SWRE_bm);
}
