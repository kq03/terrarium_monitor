# sht4x.py
import time

class SHT4x:
    def __init__(self, i2c, addr=0x44):
        self.i2c = i2c
        self.addr = addr
        self.reset()

    def reset(self):
        self.i2c.writeto(self.addr, b'\x94')
        time.sleep(0.001)

    def measure(self):
        # High precision measurement command
        self.i2c.writeto(self.addr, b'\xFD')
        time.sleep(0.01)

        raw = self.i2c.readfrom(self.addr, 6)
        temp_raw = raw[0] << 8 | raw[1]
        hum_raw = raw[3] << 8 | raw[4]

        temperature = -45 + (175 * (temp_raw / 65535))
        humidity = 100 * (hum_raw / 65535)

        return temperature, humidity
