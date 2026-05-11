import smbus
from datetime import datetime
import os

I2C_ADDR = 0x74
bus = smbus.SMBus(1)

# Register addresses (AS7331 datasheet例)
OSR = 0x00
CREG1 = 0x06
CREG3 = 0x08
MRES1 = 0x02  # UVA
MRES2 = 0x03  # UVB
MRES3 = 0x04  # UVC

def write_register(reg, value):
    bus.write_byte_data(I2C_ADDR, reg, value)

def read_channel_raw(reg_addr):
    data = bus.read_i2c_block_data(I2C_ADDR, reg_addr, 2)
    return (data[1] << 8) | data[0]

def setup_sensor(creg1_value=0xB6):
    write_register(CREG1, creg1_value)  # Gain/time設定（仮値: 必要に応じて変更）
    write_register(CREG3, 0x10)         # Continuous mode
    write_register(OSR, 0x83)           # Start measurement

def stop_sensor():
    write_register(OSR, 0x03)           # Stop

def get_next_filename(base_dir):
    base = datetime.now().strftime("uv_data_%Y%m%d")
    os.makedirs(base_dir, exist_ok=True)
    files = [f for f in os.listdir(base_dir) if f.startswith(base) and f.endswith(".txt")]
    count = len(files) + 1
    return os.path.join(base_dir, f"{base}_{count:03d}.txt")

def main():
    data_dir = "uv_data"
    filename = get_next_filename(data_dir)
    setup_sensor()              # 測定開始

    try:
        uva = read_channel_raw(MRES1)
        uvb = read_channel_raw(MRES2)
        uvc = read_channel_raw(MRES3)
        print(f"UVA={uva}, UVB={uvb}, UVC={uvc}")

        with open(filename, "w") as f:
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"UVA: {uva}\n")
            f.write(f"UVB: {uvb}\n")
            f.write(f"UVC: {uvc}\n")
        print(f"Saved to {filename}")
    finally:
        stop_sensor()
        bus.close()

if __name__ == "__main__":
    main()
