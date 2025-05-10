import network
import espnow
from machine import Pin
import time
import json
import gc
from umqtt.simple import MQTTClient

# ===== CONFIGURATION =====
# Global variables
e = None  # ESP-NOW instance will be defined globally
mqtt_client = None
mqtt_connected = False

# WiFi credentials (duplicated from boot.py for reconnection)
SSID = "Berkeley-IoT"
PASSWORD = "r8S&g9KH"

# Thresholds
TEMP_LOWER = 20.0    # Below this temperature, heat lamp ON
TEMP_UPPER = 25.0    # Above this temperature, fan ON
HUMID_LOWER = 35.0   # Below this humidity, humidifier ON
HUMID_UPPER = 65.0   # Above this humidity, fan ON
DISTANCE_THRESHOLD = 8.0  # Below this distance (in cm), close servo; above, open servo

# MQTT Broker settings
MQTT_SERVER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "esp32_environment_monitor"
MQTT_USERNAME = ""
MQTT_PASSWORD = ""

# MQTT Topics
TOPIC_DATA = b"environment/wiredin/data"
TOPIC_CONTROL = b"environment/wiredin/control"

# Actuator state tracking
heat_lamp_state = False
fan_state = False
humidifier_state = False
servo_state = False  # False = open, True = closed

# Take over mode tracking
take_over_mode = False

# Function to format MAC addresses consistently
def format_mac(mac_bytes):
    return ':'.join(['{:02x}'.format(b) for b in mac_bytes])

# ===== ESP-NOW SETUP =====
def setup_espnow():
    global e
    # Get the WiFi interface without resetting it
    sta = network.WLAN(network.STA_IF)
    
    # Instead of disconnecting completely, just ensure it's in station mode
    # and set the channel while preserving the connection
    current_channel = sta.config('channel')
    if current_channel != 1:
        print(f"Changing WiFi channel from {current_channel} to 1")
        sta.config(channel=1)
    
    # Initialize ESP-NOW
    e = espnow.ESPNow()
    e.active(True)
    
    # Set up the actuator controller's MAC address
    actuator_mac_str = "14:2b:2f:af:79:c4"  # MAC for device controlling appliances
    
    # Convert string MAC to bytes
    actuator_mac_parts = actuator_mac_str.split(':')
    actuator_mac = bytes([int(actuator_mac_parts[i], 16) for i in range(6)])
    
    # Add the actuator as a peer
    try:
        # First try to remove if it exists
        try:
            e.del_peer(actuator_mac)
        except:
            pass
            
        # Try different methods to add peer
        try:
            e.add_peer(actuator_mac)
            print("Peer added successfully")
        except:
            try:
                e.add_peer(actuator_mac, channel=1)
                print("Peer added with channel specified")
            except:
                e.add_peer(actuator_mac, lmk=b'\0'*16, channel=1)
                print("Peer added with extended parameters")
    except Exception as err:
        print(f"Failed to add actuator peer: {err}")
    
    return actuator_mac

# Initialize ESP-NOW
actuator_mac = setup_espnow()

# Send a startup message to the peer
try:
    e.send(actuator_mac, "Controller starting...")
    print("Sent startup message")
except Exception as err:
    print(f"Failed to send startup message: {err}")

# ===== MQTT FUNCTIONS =====
def connect_mqtt():
    global mqtt_client, mqtt_connected
    try:
        mqtt_client = MQTTClient(MQTT_CLIENT_ID, MQTT_SERVER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD)
        mqtt_client.set_callback(on_mqtt_message)
        mqtt_client.connect(clean_session=True)
        mqtt_client.subscribe(TOPIC_CONTROL)
        print("MQTT connected")
        mqtt_connected = True
        return True
    except Exception as e:
        print(f"MQTT connect failed: {e}")
        mqtt_connected = False
        return False

def on_mqtt_message(topic, msg):
    global TEMP_LOWER, TEMP_UPPER, HUMID_LOWER, HUMID_UPPER, DISTANCE_THRESHOLD, take_over_mode
    global heat_lamp_state, fan_state, humidifier_state, servo_state

    print(f"MQTT msg: {topic}, {msg}")
    try:
        data = json.loads(msg)
        
        # Handle threshold updates
        if "temp_lower" in data: TEMP_LOWER = float(data["temp_lower"])
        if "temp_upper" in data: TEMP_UPPER = float(data["temp_upper"])
        if "humid_lower" in data: HUMID_LOWER = float(data["humid_lower"])
        if "humid_upper" in data: HUMID_UPPER = float(data["humid_upper"])
        if "distance_threshold" in data: DISTANCE_THRESHOLD = float(data["distance_threshold"])
        
        # Handle take over mode
        if "take_over" in data: 
            take_over_mode = bool(data["take_over"])
            print(f"Take over mode: {'ON' if take_over_mode else 'OFF'}")
        
        # Handle direct actuator controls when in take over mode
        if take_over_mode or "take_over" in data:
            changes_made = False
            
            if "heat" in data:
                new_state = bool(data["heat"])
                if new_state != heat_lamp_state:
                    heat_lamp_state = new_state
                    send_command("heat", new_state)
                    changes_made = True
                    
            if "fan" in data:
                new_state = bool(data["fan"])
                if new_state != fan_state:
                    fan_state = new_state
                    send_command("fan", new_state)
                    changes_made = True
                    
            if "humid" in data:
                new_state = bool(data["humid"])
                if new_state != humidifier_state:
                    humidifier_state = new_state
                    send_command("humid", new_state)
                    changes_made = True
                    
            if "servo" in data:
                new_state = bool(data["servo"])
                if new_state != servo_state:
                    servo_state = new_state
                    send_command("servo", new_state)
                    changes_made = True
            
            # Immediately publish updated state if changes were made
            if changes_made:
                publish_data(None, None, None)
    except Exception as err:
        print(f"MQTT msg parse error: {err}")

def publish_data(temperature, humidity, distance):
    global mqtt_connected, mqtt_client, heat_lamp_state, fan_state, humidifier_state, servo_state
    
    if not mqtt_connected:
        return
        
    # Create data payload for MQTT
    try:
        data = {
            "heat_lamp": heat_lamp_state,
            "fan": fan_state,
            "humidifier": humidifier_state,
            "servo": servo_state,
            "take_over": take_over_mode,
            "timestamp": time.time()
        }
        
        # Add sensor data if available
        if temperature is not None:
            data["temperature"] = temperature
        if humidity is not None:
            data["humidity"] = humidity
        if distance is not None:
            data["distance"] = distance
            
        mqtt_client.publish(TOPIC_DATA, json.dumps(data))
        print("Data published to MQTT")
    except Exception as e:
        print(f"MQTT publish error: {e}")
        mqtt_connected = False

# ===== ESP-NOW FUNCTIONS =====
def send_command(device, state):
    """Send command to the actuator controller"""
    global e, actuator_mac
    
    # Create a simple command format
    command = f"{device}:{1 if state else 0}"
    print(f"Sending command: {command}")
    
    # Try to send the command a few times
    for attempt in range(3):
        try:
            result = e.send(actuator_mac, command)
            print(f"Send result: {result}")
            if result:
                return True
            time.sleep(0.1)
        except Exception as err:
            print(f"Send error (attempt {attempt+1}): {err}")
            time.sleep(0.1)
    
    # If all attempts failed, try to refresh the connection
    try:
        print("Refreshing ESP-NOW connection")
        e.del_peer(actuator_mac)
        time.sleep(0.2)
        e.add_peer(actuator_mac, channel=1)
        print("Connection refreshed")
        
        # Try one more time after refreshing
        try:
            result = e.send(actuator_mac, command)
            print(f"Post-refresh send result: {result}")
            return result
        except Exception as err:
            print(f"Post-refresh send error: {err}")
            return False
    except Exception as err:
        print(f"Connection refresh error: {err}")
        return False

def update_actuators(temperature, humidity, distance):
    """Update actuator states based on sensor readings"""
    global heat_lamp_state, fan_state, humidifier_state, servo_state, take_over_mode
    states_changed = False
    
    # Skip automatic control if in take over mode
    if take_over_mode:
        print("In take over mode - skipping automatic control")
        return False
    
    print(f"Checking thresholds - T:{temperature}°C, H:{humidity}%, D:{distance}cm")
    
    # Check temperature against thresholds
    if temperature < TEMP_LOWER:
        # Too cold - turn on heat lamp
        if not heat_lamp_state:
            print("Temperature too low - turning ON heat lamp")
            heat_lamp_state = True
            send_command("heat", True)
            states_changed = True
    else:
        # Temperature above lower threshold - turn off heat lamp
        if heat_lamp_state:
            print("Temperature OK - turning OFF heat lamp")
            heat_lamp_state = False
            send_command("heat", False)
            states_changed = True
    
    # Check if fan should be on (high temperature OR high humidity)
    fan_needed = temperature > TEMP_UPPER or humidity > HUMID_UPPER
    if fan_needed:
        # Too hot or too humid - turn on fan
        if not fan_state:
            print("Temperature too high or humidity too high - turning ON fan")
            fan_state = True
            send_command("fan", True)
            states_changed = True
    else:
        # Temperature and humidity OK - turn off fan
        if fan_state:
            print("Temperature and humidity OK - turning OFF fan")
            fan_state = False
            send_command("fan", False)
            states_changed = True
    
    # Check humidity against lower threshold
    if humidity < HUMID_LOWER:
        # Too dry - turn on humidifier
        if not humidifier_state:
            print("Humidity too low - turning ON humidifier")
            humidifier_state = True
            send_command("humid", True)
            states_changed = True
    else:
        # Humidity above lower threshold - turn off humidifier
        if humidifier_state:
            print("Humidity OK - turning OFF humidifier")
            humidifier_state = False
            send_command("humid", False)
            states_changed = True
    
    # Check distance against threshold for servo control
    if distance < DISTANCE_THRESHOLD:
        # Object detected close - close servo
        if not servo_state:
            print(f"Object detected (distance {distance}cm < threshold {DISTANCE_THRESHOLD}cm) - CLOSING servo")
            servo_state = True
            send_command("servo", True)
            states_changed = True
    else:
        # No close object - open servo
        if servo_state:
            print(f"No object detected (distance {distance}cm > threshold {DISTANCE_THRESHOLD}cm) - OPENING servo")
            servo_state = False
            send_command("servo", False)
            states_changed = True
    
    return states_changed

# ===== MAIN LOOP =====
# Check if WiFi is connected from boot.py
wifi_connected = network.WLAN(network.STA_IF).isconnected()
print(f"WiFi status: {'Connected' if wifi_connected else 'Disconnected'}")

# Initialize MQTT if WiFi is connected
if wifi_connected:
    mqtt_connected = connect_mqtt()
else:
    mqtt_connected = False
    
print(f"MQTT status: {'Connected' if mqtt_connected else 'Disconnected'}")
print("Ready to receive sensor data and control actuators...")

# Track timers
last_publish = time.time()
last_wifi_check = time.time()
last_peer_refresh = time.time()
publish_interval = 5    # seconds
wifi_check_interval = 60  # seconds
peer_refresh_interval = 300  # seconds (5 minutes)

# Initialize variables to store latest sensor readings
last_temperature = None
last_humidity = None
last_distance = None

# Main loop counter for periodic garbage collection
loop_counter = 0

while True:
    try:
        loop_counter += 1
        if loop_counter >= 1000:
            gc.collect()  # Run garbage collection periodically
            loop_counter = 0
            print("GC run")
        
        current_time = time.time()
        
        # Periodically check WiFi/MQTT connection
        if current_time - last_wifi_check > wifi_check_interval:
            last_wifi_check = current_time
            
            wifi_status = network.WLAN(network.STA_IF)
            if not wifi_status.isconnected():
                print("WiFi disconnected, attempting to reconnect...")
                wifi_status.active(True)
                try:
                    wifi_status.connect(SSID, PASSWORD)
                    attempt_counter = 0
                    while not wifi_status.isconnected() and attempt_counter < 10:
                        time.sleep(1)
                        attempt_counter += 1
                        print(f"Reconnecting attempt {attempt_counter}...")
                    
                    if wifi_status.isconnected():
                        print(f"WiFi reconnected! IP: {wifi_status.ifconfig()[0]}")
                        wifi_connected = True
                        # Reconnect MQTT after WiFi is back
                        mqtt_connected = connect_mqtt()
                    else:
                        print("WiFi reconnection failed")
                        wifi_connected = False
                        mqtt_connected = False
                except Exception as err:
                    print(f"WiFi reconnection error: {err}")
                    wifi_connected = False
                    mqtt_connected = False
            elif not mqtt_connected:
                print("MQTT disconnected, attempting to reconnect...")
                mqtt_connected = connect_mqtt()
        
        # Periodically refresh ESP-NOW peer to keep connection healthy
        if current_time - last_peer_refresh > peer_refresh_interval:
            last_peer_refresh = current_time
            print("Refreshing ESP-NOW peer connection...")
            try:
                e.del_peer(actuator_mac)
                time.sleep(0.2)
                e.add_peer(actuator_mac, channel=1)
                print("Peer refreshed")
                
                # Send a test message
                try:
                    e.send(actuator_mac, "TEST")
                    print("Test message sent")
                except Exception as err:
                    print(f"Test message failed: {err}")
            except Exception as err:
                print(f"Peer refresh failed: {err}")
        
        # Check MQTT messages if connected
        if mqtt_connected:
            try:
                mqtt_client.check_msg()
            except Exception as err:
                print(f"MQTT check error: {err}")
                mqtt_connected = False
        
        # Publish periodic updates even without new sensor data
        if mqtt_connected and current_time - last_publish > publish_interval:
            publish_data(last_temperature, last_humidity, last_distance)
            last_publish = current_time
        
        # Wait for an ESP-NOW message with short timeout
        try:
            host, msg = e.irecv(100)  # 100ms timeout
            
            if msg:  # If we got a message
                try:
                    # Decode the message
                    message_str = msg.decode('utf-8')
                    print(f"Received: {message_str}")
                    
                    # Process based on message type
                    if "ACK:" in message_str or "TEST" in message_str:
                        # Just an acknowledgment or test message, nothing to do
                        pass
                    elif "Temp:" in message_str and "Humidity:" in message_str:
                        # This is a sensor data message from the first ESP32
                        try:
                            # Extract temperature value
                            temp_start = message_str.find("Temp:") + 5
                            temp_end = message_str.find("°C", temp_start)
                            if temp_end == -1:  # If not found with degree symbol
                                temp_end = message_str.find(",", temp_start)
                            temperature = float(message_str[temp_start:temp_end].strip())
                            
                            # Extract humidity value
                            humid_start = message_str.find("Humidity:") + 9
                            humid_end = message_str.find("%", humid_start)
                            if humid_end == -1:  # If not found with percent symbol
                                humid_end = message_str.find(",", humid_start)
                                if humid_end == -1:  # If not found with comma
                                    humid_end = message_str.find("|", humid_start)
                                    if humid_end == -1:  # If not found with pipe
                                        humid_end = len(message_str)
                            humidity = float(message_str[humid_start:humid_end].strip())
                            
                            # Extract distance if available
                            distance = None
                            if "Distance:" in message_str:
                                dist_start = message_str.find("Distance:") + 9
                                dist_end = message_str.find("cm", dist_start)
                                if dist_end == -1:  # If not found with cm
                                    dist_end = message_str.find("|", dist_start)
                                    if dist_end == -1:  # If not found with pipe
                                        dist_end = len(message_str)
                                distance = float(message_str[dist_start:dist_end].strip())
                            
                            # Update last known values
                            last_temperature = temperature
                            last_humidity = humidity
                            if distance is not None:
                                last_distance = distance
                            
                            print(f"Parsed data - Temp: {temperature}°C, Humidity: {humidity}%", end="")
                            if distance is not None:
                                print(f", Distance: {distance}cm")
                            else:
                                print("")
                            
                            # Decide actuator states based on thresholds
                            states_changed = update_actuators(
                                temperature, 
                                humidity, 
                                last_distance if last_distance is not None else 100
                            )
                            
                            # Publish to MQTT if states changed or it's time for regular update
                            if states_changed or (current_time - last_publish > publish_interval):
                                publish_data(temperature, humidity, distance)
                                last_publish = current_time
                                
                        except Exception as err:
                            print(f"Error parsing sensor values: {err}")
                    
                    # Handle distance-only messages (possibly from first ESP32)
                    elif "Distance:" in message_str:
                        try:
                            # Extract distance more carefully
                            dist_start = message_str.find("Distance:") + 9
                            dist_end = message_str.find("cm", dist_start)
                            if dist_end == -1:  # If not found with cm
                                dist_end = len(message_str)
                            distance = float(message_str[dist_start:dist_end].strip())
                            
                            # Update last known value
                            last_distance = distance
                            print(f"Parsed Distance: {distance}cm")
                            
                            # Update servo based on distance threshold
                            if distance < DISTANCE_THRESHOLD:
                                # Object detected - close servo
                                if not servo_state:
                                    print(f"Object detected - CLOSING servo")
                                    servo_state = True
                                    send_command("servo", True)
                            else:
                                # No object - open servo
                                if servo_state:
                                    print(f"No object detected - OPENING servo")
                                    servo_state = False
                                    send_command("servo", False)
                            
                            # Publish the distance data
                            publish_data(None, None, distance)
                            last_publish = current_time
                        except Exception as err:
                            print(f"Error parsing distance: {err}")
                    
                    # Handle error messages
                    elif "ERROR:" in message_str:
                        print(f"Error message received: {message_str}")
                    
                    # Unknown message format
                    else:
                        print(f"Unknown message format: {message_str}")
                        
                except Exception as err:
                    print(f"Error processing message: {err}")
            
        except Exception as recv_err:
            print(f"Error in ESP-NOW receive: {recv_err}")
    
    except Exception as err:
        print(f"Error in main loop: {err}")
    
    # Small delay to prevent CPU hogging
    time.sleep(0.05)