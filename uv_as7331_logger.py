import time
import os
import sys
from datetime import datetime

import smbus2

# AS7331 default I2C address (例: 0x39)
AS7331_ADDR = 0x39

# レジスタアドレス（仮: データシート参照。機種により異なる場合あり）
REG_UVA = 0x0C
REG_UVB = 0x0E
REG_UVC = 0x10

def read_uv(bus):
    # 2バイト（MSB, LSB）で16ビット値を読む
    def read16(reg):
        data = bus.read_i2c_block_data(AS7331_ADDR, reg, 2)
        return (data[0] << 8) | data[1]
    uva = read16(REG_UVA)
    uvb = read16(REG_UVB)
    uvc = read16(REG_UVC)
    return uva, uvb, uvc

def get_next_filename(base_dir):
    # base_dir/uv_data_YYYYmmdd_NNN.txt
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
        bus.close()

if __name__ == "__main__":
    main()
