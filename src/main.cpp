/*******************************************************************
    A door opener via Telegram bot.
 *                                                                 *
 *  october 2018                                                   *
    written by Enkel Bici, Giacomo Leonzi and Francesco Pasino
 *******************************************************************/
#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>
#include <UniversalTelegramBot.h>
#include "stuff_secrets.h"

// Initialize Wifi connection to the router
char ssid[] = SECRET_SSID;     // your network SSID (name)
char password[] = SECRET_PASS; // your network key

// Initialize Telegram BOT
String BOTname = BOT_NAME;
String chat = CHAT_ID;
String BOTtoken = BOT_TOKEN;

WiFiClientSecure client;
UniversalTelegramBot bot(BOTtoken, client);

unsigned long Bot_mtbs = 1000; // mean time between scan messages
unsigned long Bot_lasttime;   // last time messages' scan has been done

const int doorPin = 15; // D8
const int internalDoorPin = 13; // D7
int ledStatus = 0;

void handleNewMessages(int numNewMessages) {
  Serial.println("handleNewMessages");
  Serial.println(String(numNewMessages));

  for (int i = 0; i < numNewMessages; i++) {
    String chat_id = String(bot.messages[i].chat_id);
    String text = bot.messages[i].text;

    String from_name = bot.messages[i].from_name;
    if (from_name == "") from_name = "Guest";

    Serial.print(from_name);
    Serial.println(" tried to open the door.");
    if (chat_id != chat) {
      bot.sendMessage(chat_id, "You shall not pass!");
    } else {
      if (text == "/apri" || text == "/apri@" + BOTname ) {
        bot.sendMessage(chat_id, "The external door is open " + from_name + ", the internal will open in 8 seconds.", "");

        digitalWrite(doorPin, HIGH);   // open external door
        delay(500);
        digitalWrite(doorPin, LOW);
        delay(500);
        digitalWrite(internalDoorPin, HIGH);   // open internal door
        delay(8000);
        digitalWrite(internalDoorPin, LOW);

        Serial.println("Done.");
      }

      if (text == "/start" || text == "/start@" + BOTname ) {
        String welcome = "Welcome to Fablab Torino, " + from_name + ".\n";
        welcome += BOTname + " opens the door.\n\n";
        welcome += "/apri : to open the door\n";
        bot.sendMessage(chat_id, welcome, "Markdown");

        String keyboardJson = "[[\"/apri\"]]";
        bot.sendMessageWithReplyKeyboard(chat_id, "Choose from one of the following options", "", keyboardJson, true);
      }
    }
  }
}

void setup() {
  // inizialize the relè pins
  pinMode(doorPin, OUTPUT); // initialize digital doorPin as an output.
  digitalWrite(doorPin, LOW);
  pinMode(internalDoorPin, OUTPUT); // initialize digital doorPin as an output.
  digitalWrite(internalDoorPin, LOW);

  Serial.begin(115200); // initialize the Serial

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

  // needed to make bot work :(
  client.setInsecure();
  bot.sendMessage(chat, "Sorry, I had fallen asleep... now I'm ready to open the door!");
}

void loop() {
  if (millis() > Bot_lasttime + Bot_mtbs)  {
    int numNewMessages = bot.getUpdates(bot.last_message_received + 1);

    while (numNewMessages) {
      Serial.println("got response");
      handleNewMessages(numNewMessages);
      numNewMessages = bot.getUpdates(bot.last_message_received + 1);
    }

    Bot_lasttime = millis();
  }
}
