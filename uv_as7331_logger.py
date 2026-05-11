import time
import os
import sys
from datetime import datetime

import smbus2

# AS7331 default I2C address (e.g., 0x74)
AS7331_ADDR = 0x74

# Register addresses (AS7331 datasheet example)
OSR = 0x00
CREG1 = 0x06
CREG3 = 0x08
MRES1 = 0x02  # UVA
MRES2 = 0x03  # UVB
MRES3 = 0x04  # UVC

def read_uv(bus):
    # Read 16-bit value from 2 bytes (LSB, MSB)
    def read16(reg):
        data = bus.read_i2c_block_data(AS7331_ADDR, reg, 2)
        return (data[1] << 8) | data[0]
    uva = read16(MRES1)
    uvb = read16(MRES2)
    uvc = read16(MRES3)
    return uva, uvb, uvc

def setup_sensor(bus, creg1_value=0xB6):
    bus.write_byte_data(AS7331_ADDR, CREG1, creg1_value)
    bus.write_byte_data(AS7331_ADDR, CREG3, 0x10)
    bus.write_byte_data(AS7331_ADDR, OSR, 0x83)

def stop_sensor(bus):
    bus.write_byte_data(AS7331_ADDR, OSR, 0x03)

def get_next_filename(base_dir):
    # base_dir/uv_data_YYYYMMDD_NNN.txt
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
    base = datetime.now().strftime("uv_data_%Y%m%d")
    existing = sorted([x for x in os.listdir(base_dir) if x.startswith(base)])
    count = len(existing) + 1
    return os.path.join(base_dir, f"{base}_{count:03d}.txt")

def main():
    data_dir = "uv_data"
    bus = smbus2.SMBus(1)  # I2Cバス番号は1
    filename = get_next_filename(data_dir)

    print("AS7331 UV sensor logger (one-shot)")
    try:
        setup_sensor(bus)
        time.sleep(0.05)
        uva, uvb, uvc = read_uv(bus)
        print(f"UVA: {uva}")
        print(f"UVB: {uvb}")
        print(f"UVC: {uvc}")

        with open(filename, "w") as f:
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"UVA: {uva}\n")
            f.write(f"UVB: {uvb}\n")
            f.write(f"UVC: {uvc}\n")
        print(f"Saved to {filename}")

    except Exception as e:
        print("Error communicating with AS7331:", e)
    finally:
        try:
            stop_sensor(bus)
        except Exception:
            pass
        bus.close()

if __name__ == "__main__":
    main()
