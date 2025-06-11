This Arduino project is responsible for monitoring the opening and closing of the doors. When a door is opened, the system sends a message through an MQTT network, which is received by the Arduino. Upon receiving this message, the Arduino turns on a specific color LED for that door and displays a message on an LCD screen informing about the door opening.

The project includes:

Connecting the Arduino to the local WiFi network.
Integration with an MQTT server to receive door opening messages.
Illumination of different color LEDs for each door (green, yellow, red).
Displaying the door opening messages on an LCD screen.
Sending notifications to a central system when a door opening is detected.
In this way, the facility staff can monitor in real-time when the different doors are opened, which allows improving security and access control. Additionally, the system sends notifications to a central system so that they can keep a record of the events.
