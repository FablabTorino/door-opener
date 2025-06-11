#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// Configuración de WiFi
const char* ssid = "Fablab_Torino";
const char* password = "Fablab.Torino!";

// Configuración de MQTT
const char* mqtt_server = "172.26.34.36";
const char* mqtt_topic_door1 = "Door1_topic";
const char* mqtt_username = "tu_usuario";
const char* mqtt_password = "tu_contraseña";

WiFiClient espClient;
PubSubClient client(espClient);

// Variables para almacenar el estado de los LED
bool ledStateDoor1 = false;
unsigned long ledOnTimeDoor1 = 0;

// Datos del timbre
const char* hostname = "your esp-rfid hostname"; // Cambia esto por tu hostname

// Configuración del relé
const int relayPin = 4; // Pin al que está conectado el relé (ajusta si es necesario)
unsigned long relayOnTime = 0; // Para gestionar el tiempo de activación del relé

void setup() {
  Serial.begin(9600);

  // Conexión a WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Conectando a WiFi...");
  }
  Serial.println("Conectado a WiFi");

  // Conexión a MQTT
  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);

  while (!client.connected()) {
    Serial.println("Conectando a MQTT...");
    if (client.connect("ArduinoClient", mqtt_username, mqtt_password)) {
      Serial.println("Conectado a MQTT");
      client.subscribe(mqtt_topic_door1);
    } else {
      Serial.print("Error al conectar: ");
      Serial.print(client.state());
      delay(2000);
    }
  }

  // Inicializar los pines de los LED
  pinMode(13, OUTPUT);
  pinMode(relayPin, OUTPUT); // Configurar el pin del relé como salida
  digitalWrite(relayPin, LOW); // Asegurarse de que el relé está apagado al inicio
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // Controlar el LED de la puerta 1 según su estado
  controlLED(13, ledStateDoor1, ledOnTimeDoor1);

  // Controlar el relé, apagar después de 3 segundos
  if (millis() - relayOnTime >= 3000 && relayOnTime > 0) { // Después de 3 segundos
    digitalWrite(relayPin, LOW); // Apagar el relé
    Serial.println("Relé apagado"); // Imprimir mensaje cuando el relé se apaga
    relayOnTime = 0; // Resetear el tiempo
  }
}

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Mensaje recibido [");
  Serial.print(topic);
  Serial.print("] ");
  for (int i = 0; i < length; i++) {
    Serial.print((char)payload[i]);
  }
  Serial.println();

  // Control de los LED basado en el topic del mensaje recibido
  if (strcmp(topic, mqtt_topic_door1) == 0) {
    ledStateDoor1 = true;
    ledOnTimeDoor1 = millis();
    sendDoorbellMessage("Door 1"); // Enviar mensaje del timbre
    sendNotificationToPublisher("Door 1 opened"); // Enviar notificación al publicador

    // Activar el relé para encender las luces (12V) durante 3 segundos
    digitalWrite(relayPin, HIGH); // Encender el relé (12V)
    Serial.println("Relé activado"); // Imprimir mensaje cuando el relé se activa
    relayOnTime = millis(); // Registrar el tiempo de activación del relé
  } else {
    ledStateDoor1 = false;
  }
}

void sendDoorbellMessage(const char* doorName) {
  unsigned long currentTime = millis() / 1000; // Tiempo en segundos
  StaticJsonDocument<200> jsonDoc; // Crear un documento JSON
  
  jsonDoc["type"] = "INFO"; // Tipo de mensaje
  jsonDoc["src"] = doorName; // Nombre de la puerta
  jsonDoc["desc"] = "Doorbell ringing"; // Descripción del evento
  jsonDoc["data"] = ""; // Datos adicionales (vacío en este caso)
  jsonDoc["time"] = currentTime; // Marca de tiempo
  jsonDoc["cmd"] = "event"; // Comando relacionado
  
  // Asignar el nombre del host basado en el nombre de la puerta
  String topicName = String(doorName) + "_topic"; 
  jsonDoc["hostname"] = topicName; // Nombre del host

  String jsonString;
  serializeJson(jsonDoc, jsonString); // Serializar el documento JSON a una cadena

  Serial.println(jsonString); // Imprimir mensaje en el monitor serial
  client.publish("door/events", jsonString.c_str()); // Publicar el mensaje en el tópico MQTT
}

void sendNotificationToPublisher(const char* message) {
  StaticJsonDocument<200> jsonDoc; // Crear un documento JSON para la notificación
  
  jsonDoc["type"] = "INFO"; // Tipo de mensaje
  jsonDoc["message"] = message; // Mensaje de notificación

  String jsonString;
  serializeJson(jsonDoc, jsonString); // Serializar el documento JSON a una cadena

  // Publicar el mensaje en el tópico de notificaciones
  client.publish("door/notifications", jsonString.c_str());
}

void reconnect() {
  while (!client.connected()) {
    Serial.println("Reconectando a MQTT...");
    if (client.connect("ArduinoClient", mqtt_username, mqtt_password)) {
      Serial.println("Conectado");
      client.subscribe(mqtt_topic_door1);
    } else {
      Serial.print("Error al reconectar: ");
      Serial.print(client.state());
      delay(5000);
    }
  }
}

void controlLED(int ledPin, bool& ledState, unsigned long& ledOnTime) {
  if (ledState && (millis() - ledOnTime >= 5000)) { // Si el LED está encendido y han pasado 5 segundos
    ledState = false; // Apagar el LED
  }
  digitalWrite(ledPin, ledState);
}
