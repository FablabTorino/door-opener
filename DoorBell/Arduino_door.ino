#include <WiFiNINA.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// WIFI config
const char* ssid = "Fablab_TorinoSTAFF";
const char* password = "Fablab.TorinoSTAFF!";

// MQTT config
const char* mqtt_server = "192.168.0.1";
const char* mqtt_topic_door1 = "esp-rfid/send";


// Network objects
WiFiClient espClient;
PubSubClient client(espClient);

//Relay initialisation
const int relayPin = 4;
unsigned long relayOnTime = 0;

// Function prototypes
void connectToWiFi();
void connectToMQTT();
void triggerRelay(unsigned long duration = 3000);
void callback(char* topic, byte* payload, unsigned int length);

// Setup
void setup() {
  pinMode(relayPin, OUTPUT);
  digitalWrite(relayPin, LOW);

  

  connectToWiFi();
  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);
  connectToMQTT();

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  
  
}

// Main loop
void loop() {
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
  }
}

// MQTT callback
void callback(char* topic, byte* payload, unsigned int length) {
  
  String message;
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, message)) return;

  const char* desc = doc["desc"] | "";
  const char* cmd  = doc["cmd"]  | "";

  if (strcmp(desc, "Doorbell ringing") == 0 && strcmp(cmd, "event") == 0) {
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



// Relay trigger
void triggerRelay(unsigned long duration) {
  digitalWrite(relayPin, HIGH);
  relayOnTime = millis();
}