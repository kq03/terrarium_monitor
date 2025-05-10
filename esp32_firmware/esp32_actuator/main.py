import network
import espnow
from machine import Pin, PWM
import time
import gc
import machine

# === CONFIGURATION ===
# Reset WiFi
sta = network.WLAN(network.STA_IF)
sta.active(False)
time.sleep(1)
sta.active(True)
time.sleep(1)
sta.disconnect()
sta.config(channel=1)

# Initialize ESP-NOW
e = espnow.ESPNow()
e.active(True)

# Define actuator pins - using Pin.OUT for all
heat_lamp_relay = Pin(27, Pin.OUT)
fan_relay = Pin(15, Pin.OUT)
humidifier_relay = Pin(32, Pin.OUT)

# Initialize servo using PWM
servo_pin = PWM(Pin(13), freq=50)

# Initialize all devices to OFF
heat_lamp_relay.off()  # Using on/off instead of value
fan_relay.off()        # Using on/off instead of value
humidifier_relay.off() # Using on/off instead of value

# Servo initial position (closed)
def set_servo_angle(angle):
    """Set servo angle (0-180 degrees)"""
    duty = int((angle / 180) * 75 + 40)  # Convert angle to duty cycle
    servo_pin.duty(duty)
    
# Initialize servo to closed position
set_servo_angle(90)  # Closed position

# Actuator state tracking
heat_lamp_state = False
fan_state = False
humidifier_state = False
servo_state = False  # False = open, True = closed

# Set up controller MAC
sender_mac_str = "14:2b:2f:af:e4:98"  # Second ESP32's MAC
sender_mac = bytes([int(sender_mac_str.split(':')[i], 16) for i in range(6)])

# Add the controller as peer
try:
    try:
        e.del_peer(sender_mac)
    except:
        pass
    try:
        e.add_peer(sender_mac, channel=1)
    except:
        e.add_peer(sender_mac, lmk=b'\0'*16, channel=1)
except:
    machine.reset()

# Track connection status
last_received = time.time()
last_heartbeat = time.time()
connection_timeout = 30  # seconds

# === FUNCTIONS ===
def set_actuator(device, state):
    """Set the state of an actuator"""
    global heat_lamp_state, fan_state, humidifier_state, servo_state
    
    if device == "heat":
        heat_lamp_state = state
        if state:
            heat_lamp_relay.on()  # Active LOW - off() turns relay ON
            print("Heat lamp set to ON")
        else:
            heat_lamp_relay.off()   # Active LOW - on() turns relay OFF
            print("Heat lamp set to OFF")
            
    elif device == "fan":
        fan_state = state
        if state:
            fan_relay.on()  # Active LOW - off() turns relay ON
            print("Fan set to ON")
        else:
            fan_relay.off()   # Active LOW - on() turns relay OFF
            print("Fan set to OFF")
            
    elif device == "humid":
        humidifier_state = state
        if state:
            humidifier_relay.on()  # Active LOW - off() turns relay ON
            print("Humidifier set to ON")
        else:
            humidifier_relay.off()   # Active LOW - on() turns relay OFF
            print("Humidifier set to OFF")
            
    elif device == "servo":
        servo_state = state
        if state:
            set_servo_angle(200)
            print("Servo set to OPEN")
        else:
            set_servo_angle(90)
            print("Servo set to CLOSED")
            
    else:
        return False
    
    return True

def send_status():
    """Send current actuator status to the controller"""
    try:
        status = f"STATUS:heat:{1 if heat_lamp_state else 0},fan:{1 if fan_state else 0},humid:{1 if humidifier_state else 0},servo:{1 if servo_state else 0}"
        e.send(sender_mac, status)
        return True
    except:
        return False

# Send a startup message
try:
    e.send(sender_mac, "Actuator controller ready")
except:
    pass

# === MAIN LOOP ===
iteration_counter = 0

while True:
    try:
        # Periodic garbage collection
        iteration_counter += 1
        if iteration_counter >= 500:
            gc.collect()
            iteration_counter = 0
        
        current_time = time.time()
        
        # Send status every 10 seconds
        if current_time - last_heartbeat > 10:
            last_heartbeat = current_time
            send_status()
        
        # Check for connection timeout
        if current_time - last_received > connection_timeout:
            # Try to refresh the connection
            try:
                e.del_peer(sender_mac)
                time.sleep(0.5)
                e.add_peer(sender_mac, channel=1)
            except:
                pass
            last_received = current_time
        
        # Wait for an ESP-NOW message
        host, msg = e.irecv(100)  # 100ms timeout
        
        if msg:
            last_received = current_time
            
            try:
                # Print raw message for debugging
                print(f"Received message: {msg}")
                
                # Try to decode the message
                try:
                    message_str = msg.decode('utf-8')
                    
                    # Process command messages (format: "device:state")
                    if ":" in message_str:
                        parts = message_str.split(":")
                        
                        if len(parts) >= 2:
                            device = parts[0]
                            state_str = parts[1].strip()
                            
                            # Convert to boolean
                            if state_str == "1" or state_str.lower() == "on" or state_str.lower() == "true":
                                state = True
                            else:
                                state = False
                            
                            # Set the actuator state
                            success = set_actuator(device, state)
                            
                            if success:
                                # Send acknowledgment
                                e.send(host, f"ACK:{device}:{1 if state else 0}")
                    
                    # Handle test messages silently
                    elif message_str.startswith("TEST"):
                        e.send(host, f"ACK:TEST")
                        
                except UnicodeError as decode_err:
                    # If UTF-8 decoding fails, try to interpret as bytes
                    print(f"Unicode decode error: {decode_err}")
                    print(f"Message as bytes: {[hex(b) for b in msg]}")
                    
            except Exception as err:
                print(f"Error processing message: {err}")
    
    except Exception as err:
        print(f"Main loop error: {err}")
    
    # Small delay
    time.sleep(0.05)