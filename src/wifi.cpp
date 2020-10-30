#ifdef ESP32

#include "wifi.h"
#include "stuff_secrets.h"

// Initialize Wifi connection to the router
char ssid[] = SECRET_SSID;     // your network SSID (name)
char password[] = SECRET_PASS; // your network key

WiFiClientSecure client;

void initWifi() {
  // Set WiFi to station mode and disconnect from an AP if it was Previously connected
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();

  delay(100);

  // attempt to connect to Wifi network:
  Serial.print("Connecting Wifi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(500);
  }

  Serial.println();
  Serial.println("WiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

#endif
