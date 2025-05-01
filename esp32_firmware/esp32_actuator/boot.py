# This file is executed on every boot (including wake-boot from deepsleep)
import esp
import network
import time
import machine
import socket
import struct

print('Board Reset and Running Boot')

# WiFi credentials
SSID = ""
PASSWORD = ""

# WiFi Connection
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

if not wlan.isconnected():
    print("Connecting to network...")
    try:
        wlan.connect(SSID, PASSWORD)
        timeout = 15
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
            print(f"Waiting for connection... {15 - timeout}s")
    except OSError as e:
        print(f"WiFi connection error: {e}")
        wlan.active(False)  # Disable WiFi to reset state
        time.sleep(1)
        wlan.active(True)
        print("Retrying WiFi connection...")
        try:
            wlan.connect(SSID, PASSWORD)
            timeout = 10
            while not wlan.isconnected() and timeout > 0:
                time.sleep(1)
                timeout -= 1
        except OSError as e:
            print(f"WiFi retry failed: {e}")

if wlan.isconnected():
    print("Wi-Fi connected! IP:", wlan.ifconfig()[0])
else:
    print("Connection failed!")

# NTP Server Function
def ntp_time():
    host = "amazon.pool.ntp.org"
    timeout = 1
    NTP_QUERY = bytearray(48)
    NTP_QUERY[0] = 0x1B
    addr = socket.getaddrinfo(host, 123)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(timeout)
        s.sendto(NTP_QUERY, addr)
        msg = s.recv(48)
    finally:
        s.close()
    val = struct.unpack("!I", msg[40:44])[0]
    MIN_NTP_TIMESTAMP = 3913056000
    if val < MIN_NTP_TIMESTAMP:
        val += 0x100000000
    EPOCH_YEAR = time.gmtime(0)[0]
    if EPOCH_YEAR == 2000:
        NTP_DELTA = 3155673600
    elif EPOCH_YEAR == 1970:
        NTP_DELTA = 2208988800
    else:
        raise Exception("Unsupported epoch: {}".format(EPOCH_YEAR))
    return val - NTP_DELTA

# Time Synchronization
def set_time():
    t = ntp_time()
    tm = time.gmtime(t)
    machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))

# Sync Time if WiFi Connected
if wlan.isconnected():
    print("\nCollecting time information from NTP server")
    UTC_OFFSET = -8  # PST
    TIME_OFFSET = UTC_OFFSET * 60 * 60
    time_before = time.localtime(time.time() + TIME_OFFSET)
    formatted_before_time = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(*time_before[:6])
    print("Local time before synchronization:", formatted_before_time)
    try:
        set_time()
        time_after = time.localtime(time.time() + TIME_OFFSET)
        formatted_after_time = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(*time_after[:6])
        print("Local time after synchronization:", formatted_after_time)
    except Exception as e:
        print("Failed to sync time:", e)

print("Boot process completed")
