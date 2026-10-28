#include <WiFiNINA.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "arduino_secrets.h"

// WIFI config (credentials in arduino_secrets.h, see arduino_secrets.h.example)
const char* ssid = SECRET_SSID;
const char* password = SECRET_PASS;

// MQTT config
const char* mqtt_server = "192.168.0.1";
const char* mqtt_topic_door1 = "esp-rfid/send";


// Network objects
WiFiClient espClient;
PubSubClient client(espClient);

//Relay initialisation
const int relayPin = 4;
unsigned long relayOnTime = 0;

// Daily reboot
const unsigned long rebootInterval = 24UL * 60 * 60 * 1000;

// Function prototypes
void connectToWiFi();
void connectToMQTT();
void triggerRelay(unsigned long duration = 3000);
void callback(char* topic, byte* payload, unsigned int length);
void reboot();

// Setup
void setup() {
  Serial.begin(9600);
  Serial.println("Booted");

  pinMode(relayPin, OUTPUT);
  digitalWrite(relayPin, LOW);

  

  connectToWiFi();
  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);
  connectToMQTT();
  Serial.println("WiFi + MQTT connected");

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  
  
}

// Main loop
void loop() {
  // Reboot every 24h (wait for the relay to be released first)
  if (millis() >= rebootInterval && relayOnTime == 0) {
    Serial.print("Rebooting at millis=");
    Serial.println(millis());
    Serial.flush();
    reboot();
  }

  //Wifi reconnection
  if (WiFi.status() != WL_CONNECTED) {
    connectToWiFi();
  }

  if (!client.connected()) {
    connectToMQTT();
  }
  client.loop();

  

  // Turn off relay after 3 seconds
  if (relayOnTime > 0 && millis() - relayOnTime >= 3000) {
    digitalWrite(relayPin, LOW);
    relayOnTime = 0;
    Serial.println("Relay OFF");
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

// Wi-Fi connection
void connectToWiFi() {
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
}

// MQTT connection
void connectToMQTT() {
  while (!client.connected()) {
    if (client.connect("ArduinoClient")) {
      client.subscribe(mqtt_topic_door1);
    } else {
      delay(2000);
    }
  }
}



// Software reset (Uno WiFi Rev2 / ATmega4809)
void reboot() {
  _PROTECTED_WRITE(RSTCTRL.SWRR, RSTCTRL_SWRE_bm);
}

// Relay trigger
void triggerRelay(unsigned long duration) {
  digitalWrite(relayPin, HIGH);
  relayOnTime = millis();
}