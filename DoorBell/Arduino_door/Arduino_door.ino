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

// Diagnostics (retained JSON, published on every MQTT connect and with each
// heartbeat): why the board last reset, drops since boot, RSSI, NINA firmware.
// Read it with: mosquitto_sub -h 192.168.0.1 -v -t doors/diag/doorbell-relay
const char* diag_topic = "doors/diag/doorbell-relay";

// Reconnect pacing. Reconnects never block forever, so the relay still
// switches off on time and the board can always reach the reboot checks below.
const unsigned long wifiRetryInterval = 10UL * 1000;
const unsigned long mqttRetryInterval = 5UL * 1000;
const uint16_t tcpConnectTimeoutMs = 3000;

// Reboot if WiFi/MQTT stay down this long (power-cycling by hand fixed a hang before)
const unsigned long disconnectedRebootAfter = 5UL * 60 * 1000;

// Daily reboot
const unsigned long rebootInterval = 24UL * 60 * 60 * 1000;

// Watchdog: WiFiNINA busy-waits forever on the NINA module (SpiDrv::waitForSlaveReady),
// so a hung module freezes loop() for good. The hardware watchdog (8 s max) is fed
// from a 1 Hz RTC interrupt, but only while loop() has run in the last
// loopStallLimitSeconds, so legitimately slow calls (WiFi.begin ~10 s) are fine and a
// real freeze resets the board after ~loopStallLimitSeconds + 8 s.
const uint8_t loopStallLimitSeconds = 60;
volatile uint8_t loopStallSeconds = 0;

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

// Diagnostics state
const uint16_t rebootNoteMagic = 0xD0B1;
const char REBOOT_DAILY = 'D';
const char REBOOT_DISCONNECTED = 'X';
// .noinit RAM survives a software/watchdog reset, so the next boot can tell why we rebooted
uint16_t rebootNoteCheck __attribute__((section(".noinit")));
char rebootNote __attribute__((section(".noinit")));
char resetCause[24] = "";
unsigned int mqttConnects = 0;       // successful MQTT connects since boot
unsigned int wifiConnects = 0;       // successful WiFi connects since boot
int lastDropMqttState = 0;           // PubSubClient state when the last drop was noticed
int lastDropWifiStatus = WL_CONNECTED;
bool inOutage = false;

// Function prototypes
bool ensureWiFi();
bool ensureMQTT();
void noteDrop();
void publishStatus(const char* status);
void publishDiag();
void readResetCause();
void startWatchdog();
void triggerRelay();
void releaseRelayIfDue();
void callback(char* topic, byte* payload, unsigned int length);
void reboot(char why);

// 1 Hz: feed the hardware watchdog only while loop() is still making progress
ISR(RTC_PIT_vect) {
  RTC.PITINTFLAGS = RTC_PI_bm;
  if (loopStallSeconds < loopStallLimitSeconds) {
    loopStallSeconds++;
    __asm__ __volatile__ ("wdr");
  }
}

// Setup
void setup() {
  readResetCause();
  startWatchdog();

  Serial.begin(9600);
  Serial.print("Booted, reset cause: ");
  Serial.println(resetCause);

  pinMode(relayPin, OUTPUT);
  digitalWrite(relayPin, LOW);

  // LED on = WiFi and MQTT connected
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  espClient.setConnectionTimeout(tcpConnectTimeoutMs);
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
  loopStallSeconds = 0;   // single byte: atomic, safe against the RTC interrupt
  releaseRelayIfDue();

  // Reboot every 24h (wait for the relay to be released first)
  if (millis() >= rebootInterval && relayOnTime == 0) {
    Serial.print("Daily reboot at millis=");
    Serial.println(millis());
    publishStatus("rebooting");
    reboot(REBOOT_DAILY);
  }

  bool connected = ensureWiFi() && ensureMQTT();
  digitalWrite(LED_BUILTIN, connected ? HIGH : LOW);

  if (connected) {
    lastConnected = millis();
    client.loop();

    if (millis() - lastHeartbeat >= heartbeatInterval) {
      publishStatus("online");
      publishDiag();
    }
  } else if (millis() - lastConnected >= disconnectedRebootAfter && relayOnTime == 0) {
    Serial.println("Disconnected for too long, rebooting");
    reboot(REBOOT_DISCONNECTED);
  }
}

// Wi-Fi: one attempt per wifiRetryInterval. Returns true when connected.
bool ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return true;
  }
  noteDrop();
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

  wifiConnects++;
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
  noteDrop();
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

  mqttConnects++;
  inOutage = false;
  client.subscribe(mqtt_topic_door1);
  Serial.println("MQTT connected");
  publishStatus("online");
  publishDiag();
  return true;
}

// Record what the connection looked like the moment we noticed it was gone
void noteDrop() {
  if (inOutage || mqttConnects == 0) {
    return;
  }
  inOutage = true;
  lastDropMqttState = client.state();
  lastDropWifiStatus = WiFi.status();
  Serial.print("Connection lost: MQTT state ");
  Serial.print(lastDropMqttState);
  Serial.print(", WiFi status ");
  Serial.println(lastDropWifiStatus);
}

void publishStatus(const char* status) {
  if (client.connected() && client.publish(status_topic, status)) {
    lastHeartbeat = millis();
  }
}

// Keep the payload well under PubSubClient's 256-byte packet limit
void publishDiag() {
  if (!client.connected()) {
    return;
  }
  char payload[200];
  snprintf(payload, sizeof(payload),
           "{\"reset\":\"%s\",\"up\":%lu,\"mqtt_connects\":%u,\"wifi_connects\":%u,"
           "\"last_drop_mqtt\":%d,\"last_drop_wifi\":%d,\"rssi\":%ld,\"fw\":\"%s\"}",
           resetCause, millis() / 1000, mqttConnects, wifiConnects,
           lastDropMqttState, lastDropWifiStatus, (long)WiFi.RSSI(), WiFi.firmwareVersion());
  client.publish(diag_topic, payload, true);
}

// ATmega4809 reset flags (cleared after reading so the next reset starts clean)
void readResetCause() {
  uint8_t flags = RSTCTRL.RSTFR;
  RSTCTRL.RSTFR = flags;

  bool noteValid = rebootNoteCheck == rebootNoteMagic;
  char note = rebootNote;
  rebootNoteCheck = 0;

  if (flags & RSTCTRL_WDRF_bm) {
    strcpy(resetCause, "watchdog");
  } else if (flags & RSTCTRL_SWRF_bm) {
    if (noteValid && note == REBOOT_DAILY) {
      strcpy(resetCause, "software:daily");
    } else if (noteValid && note == REBOOT_DISCONNECTED) {
      strcpy(resetCause, "software:disconnected");
    } else {
      strcpy(resetCause, "software");
    }
  } else if (flags & RSTCTRL_BORF_bm) {
    strcpy(resetCause, "brownout");
  } else if (flags & RSTCTRL_EXTRF_bm) {
    strcpy(resetCause, "reset-button");
  } else if (flags & RSTCTRL_UPDIRF_bm) {
    strcpy(resetCause, "upload");
  } else if (flags & RSTCTRL_PORF_bm) {
    strcpy(resetCause, "power-on");
  } else {
    strcpy(resetCause, "unknown");
  }
}

void startWatchdog() {
  // RTC periodic interrupt at 1 Hz from the internal 1.024 kHz oscillator
  while (RTC.PITSTATUS > 0) {}
  RTC.CLKSEL = RTC_CLKSEL_INT1K_gc;
  RTC.PITINTCTRL = RTC_PI_bm;
  RTC.PITCTRLA = RTC_PERIOD_CYC1024_gc | RTC_PITEN_bm;

  // Hardware watchdog, ~8 s
  _PROTECTED_WRITE(WDT.CTRLA, WDT_PERIOD_8KCLK_gc);
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
void reboot(char why) {
  rebootNote = why;
  rebootNoteCheck = rebootNoteMagic;
  Serial.flush();
  client.disconnect();   // clean disconnect: the Last Will is not sent
  delay(100);
  _PROTECTED_WRITE(RSTCTRL.SWRR, RSTCTRL_SWRE_bm);
}
