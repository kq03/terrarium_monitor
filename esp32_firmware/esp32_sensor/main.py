import network
import espnow
import time
from machine import Pin, I2C
import sht4x
from hcsr04 import HCSR04

# ========== Configuration ==========
# Pins configuration
SHT_SCL_PIN = 14
SHT_SDA_PIN = 22
ULTRASONIC_TRIGGER_PIN = 32
ULTRASONIC_ECHO_PIN = 33  # Changed to pin 33 to avoid conflict with SHT sensor

# ESP-NOW configuration
RECEIVER_MAC = "14:2b:2f:af:e4:98"  # MAC address of the second ESP32 (receiver)
WIFI_CHANNEL = 1

# Measurement interval (in seconds)
MEASUREMENT_INTERVAL = 2

# ========== Initialize WiFi and ESP-NOW ==========
print("Initializing WiFi for ESP-NOW...")
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.disconnect()  # Disconnect from any WiFi networks
sta.config(channel=WIFI_CHANNEL)

# Display our own MAC address for reference
my_mac = sta.config('mac')
mac_bytes = bytearray(my_mac)
mac_str = ":".join(["{:02x}".format(b) for b in mac_bytes])
print(f"My MAC address: {mac_str}")

# Initialize ESP-NOW
print("Initializing ESP-NOW...")
e = espnow.ESPNow()
e.active(True)

# Convert receiver MAC string to bytes
mac_parts = RECEIVER_MAC.split(':')
peer = bytes(int(mac_parts[i], 16) for i in range(len(mac_parts)))

# Add the peer with comprehensive error handling
try:
    # Try different methods to add peer
    try:
        e.add_peer(peer)
        print("Peer added successfully")
    except:
        try:
            e.add_peer(peer, channel=WIFI_CHANNEL)
            print("Peer added with channel specification")
        except:
            e.add_peer(peer, lmk=b'\0'*16, channel=WIFI_CHANNEL)
            print("Peer added with extended parameters")
except Exception as err:
    print(f"Failed to add peer: {err}")
    print("ESP-NOW communication will not work. Check MAC address and reset.")

# ========== Initialize SHT Temperature/Humidity Sensor ==========
print("Initializing SHT4x temperature/humidity sensor...")
sht_sensor = None
i2c = None

# Initialize I2C
try:
    i2c = I2C(0, scl=Pin(SHT_SCL_PIN), sda=Pin(SHT_SDA_PIN), freq=10000)
    
    # Scan I2C bus
    print("Scanning I2C bus...")
    devices = i2c.scan()
    if devices:
        print(f"I2C devices found: {devices}")
        print(f"In hex: {[hex(d) for d in devices]}")
        
        # Initialize SHT4x sensor
        print("Initializing SHT4x sensor...")
        sht_sensor = sht4x.SHT4x(i2c)
        print("SHT4x sensor initialized")
        
        # Test the sensor with a reading
        temperature, humidity = sht_sensor.measure()
        if temperature is not None and humidity is not None:
            print(f"SHT4x test reading: Temperature: {temperature:.1f}°C, Humidity: {humidity:.1f}%")
            
            # Send success message
            try:
                e.send(peer, f"SHT4x sensor initialized: {temperature:.1f}°C, {humidity:.1f}%")
                print("Sent SHT4x initialization success message")
            except Exception as e_send:
                print(f"Failed to send SHT4x startup message: {e_send}")
        else:
            print("SHT4x sensor returned None values during initialization")
    else:
        print("No I2C devices found! Check connections and power.")
except Exception as e_sensor:
    error_msg = f"Failed to initialize SHT4x sensor: {e_sensor}"
    print(error_msg)
    try:
        e.send(peer, error_msg)
    except:
        print("Failed to send error message")
    print("Temperature/humidity monitoring will not be available.")

# ========== Initialize HC-SR04 Ultrasonic Sensor ==========
print("Initializing HC-SR04 ultrasonic sensor...")
ultrasonic_sensor = None

try:
    ultrasonic_sensor = HCSR04(trigger_pin=ULTRASONIC_TRIGGER_PIN, 
                            echo_pin=ULTRASONIC_ECHO_PIN, 
                            echo_timeout_us=10000)
    
    # Test the sensor with an initial reading
    distance = ultrasonic_sensor.distance_cm()
    print(f"HC-SR04 sensor test: {distance:.1f}cm")
    
    # Send success message
    try:
        e.send(peer, f"HC-SR04 sensor initialized: {distance:.1f}cm")
        print("Sent HC-SR04 initialization success message")
    except Exception as e_send:
        print(f"Failed to send HC-SR04 startup message: {e_send}")
except Exception as e_ultrasonic:
    error_msg = f"Failed to initialize HC-SR04 sensor: {e_ultrasonic}"
    print(error_msg)
    try:
        e.send(peer, error_msg)
    except:
        print("Failed to send error message")
    print("Distance monitoring will not be available.")

# Wait for everything to stabilize
time.sleep(1)

# ========== Main Loop ==========
print("Starting main loop to read and send data...")
reading_count = 0
send_failure_count = 0

while True:
    try:
        reading_count += 1
        print(f"\nReading #{reading_count}...")
        
        # Read sensor values with validation
        message_parts = []
        
        # Read temperature and humidity
        if sht_sensor:
            try:
                temperature, humidity = sht_sensor.measure()
                if temperature is not None and humidity is not None:
                    message_parts.append(f"Temp: {temperature:.1f}°C, Humidity: {humidity:.1f}%")
                    print(f"Temperature: {temperature:.1f}°C, Humidity: {humidity:.1f}%")
                else:
                    print("SHT4x sensor returned None values")
                    message_parts.append("Temp/Humidity: Sensor error")
            except Exception as temp_err:
                print(f"Temperature sensor read error: {temp_err}")
                message_parts.append("Temp/Humidity: Read error")
        else:
            print("Temperature/humidity sensor not available")
            message_parts.append("Temp/Humidity: No sensor")
        
        # Read distance
        if ultrasonic_sensor:
            try:
                distance = ultrasonic_sensor.distance_cm()
                # Validate the distance reading (typical HC-SR04 range: 2-400cm)
                if distance is not None and 2 <= distance <= 400:
                    message_parts.append(f"Distance: {distance:.1f}cm")
                    print(f"Distance: {distance:.1f}cm")
                else:
                    print(f"Invalid distance reading: {distance}")
                    message_parts.append("Distance: Out of range")
            except Exception as dist_err:
                print(f"Distance sensor read error: {dist_err}")
                message_parts.append("Distance: Read error")
        else:
            print("Distance sensor not available")
            message_parts.append("Distance: No sensor")
        
        # Combine all parts into a single message
        if message_parts:
            message = " | ".join(message_parts)
            print(f"Sending: {message}")
            
            # Send the data via ESP-NOW
            try:
                send_result = e.send(peer, message)
                if send_result:
                    print("Message sent successfully")
                    send_failure_count = 0  # Reset failure counter on success
                else:
                    print("Failed to send message (send returned False)")
                    send_failure_count += 1
            except Exception as send_err:
                print(f"Error sending message: {send_err}")
                send_failure_count += 1
                
            # If too many consecutive failures, attempt to re-add the peer
            if send_failure_count >= 3:
                print("Multiple send failures. Attempting to re-add peer...")
                try:
                    # Remove peer first if possible
                    try:
                        e.del_peer(peer)
                    except:
                        pass
                    
                    # Add peer again
                    e.add_peer(peer, channel=WIFI_CHANNEL)
                    print("Peer re-added")
                    send_failure_count = 0
                except Exception as re_add_err:
                    print(f"Failed to re-add peer: {re_add_err}")
        else:
            print("No sensor data available to send")
                
    except Exception as err:
        error_message = f"Error in main loop: {err}"
        print(error_message)
        try:
            e.send(peer, f"ERROR: {error_message}")
        except:
            print("Failed to send error message")
    
    # Wait between readings
    print(f"Waiting {MEASUREMENT_INTERVAL} seconds before next reading...")
    time.sleep(MEASUREMENT_INTERVAL)