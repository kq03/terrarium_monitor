# Smart Terrarium Kit
Sp25 MECENG 100 Course Project

## Project Overview
Owning exotic pets or plants requires maintaining specific terrarium conditions, but separate, non-integrated components demand manual monitoring and multiple apps, while costly pre-built terrariums limit options and remote control. Our smart terrarium kit, targeting owners and pet stores, integrates sensors and actuators for automatic temperature and humidity regulation (e.g., fans for high temperatures, heat lamp for low), monitors food levels with an ultrasonic sensor and servo feeder, and enables remote control via a single app, offering a versatile, all-in-one solution compatible with any terrarium.

## System Architecture
### ESP32 #1: Sensor Node

- Collects environmental data from attached sensors.
- Sends temperature, humidity, and food level data to the Master Controller (ESP32 #2).
- Also communicates this data to the mobile application for user visibility.

### ESP32 #2: Master Controller

- Central control unit receiving data from the Sensor Node and user input from the mobile app.
- Evaluates sensor data against defined thresholds.
- Sends corresponding instructions to the Actuator Node (ESP32 #3) to trigger required actions.

### ESP32 #3: Actuator Node

- Receives commands from the Master Controller.
- Controls actuators through relays based on received instructions or manual override.
- Includes a mechanical emergency switch to cut off power if needed.

### Mobile App: User End

- Interconnects with the Master Controller through MQTT Broker [HiveMQ].
- Receives sensors data and actuators status from the Master Controller.
- Provides "Take Over" mode to let user take control of the actuators.

### Sensors

| Sensor                            | Function                                                                 |
|-----------------------------------|--------------------------------------------------------------------------|
| SHT45 Temperature and Humidity Sensor | Measures temperature and humidity levels inside the terrarium. Used to maintain optimal environmental conditions. |
| HC-SR04 Ultrasonic Sensor         | Measures the distance to the surface of the food in the feeder to estimate remaining food level. |
| Mechanical Switch                 | Manual power cut-off switch for emergency shutdown of the Actuator Node. |

*Table: Sensor Components and Functions*

### Actuators

| Actuator                          | Function                                                                 |
|-----------------------------------|--------------------------------------------------------------------------|
| 5V Fans (x2)                      | Activated when temperature or humidity exceed upper thresholds to help cool and dehumidify the terrarium. |
| Heat Lamp                         | Activates when the temperature falls below the lower threshold. Provides both heating and lighting. |
| Atomizer                          | Increases humidity when levels drop below the defined minimum. |
| Feetech FS90 Micro Servo          | Opens/closes the food dispenser door based on user command or feeding schedule. |

*Table: Actuator Components and Functions*

## Code
### ESP32 #1: 
<code>./esp32_firmware/esp32_sensor</code>
### ESP32 #2: 
<code>./esp32_firmware/esp32_data</code>
### ESP32 #3: 
<code>./esp32_firmware/esp32_actuator</code>
### Mobile App: 
<code>./app</code>
