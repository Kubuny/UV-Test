#!/usr/bin/env python3
"""Standalone AS7331 UV logger for Raspberry Pi CM4."""

import argparse
import os
import re
import time
from datetime import datetime

smbus_module = None
try:
    import smbus as _smbus  # type: ignore
    smbus_module = _smbus
except ImportError:
    try:
        import smbus2 as _smbus  # type: ignore
        smbus_module = _smbus
    except ImportError:
        smbus_module = None


I2C_ADDR = 0x74
OSR = 0x00
MRES1 = 0x02  # UVA
MRES2 = 0x03  # UVB
MRES3 = 0x04  # UVC
CREG1 = 0x06
CREG3 = 0x08

TINT_MAP = {
    "01": (1, 4, 0xB2),
    "02": (1, 64, 0xB6),
    "03": (16, 8, 0x73),
    "04": (16, 64, 0x76),
    "05": (128, 16, 0x44),
    "06": (128, 64, 0x46),
    "07": (2048, 32, 0x05),
    "08": (2048, 64, 0x06),
}

INTERVAL_MINUTES_MAP = {
    # Used only by mode=01 (varying mode): 01=1, 02=6, 03=7, 04=8, 05=9, 06=10 minutes.
    "01": 1,
    "02": 6,
    "03": 7,
    "04": 8,
    "05": 9,
    "06": 10,
}
STATIC_MODE_DURATION_MINUTES = 7
DEFAULT_VARYING_MODE_DURATION_SECONDS = 60
SAMPLE_PERIOD_SECONDS = 0.5
MIN_LOOP_SLEEP_SECONDS = 0.01
TINT_HELP_TEXT = ", ".join(
    f"{code}={gain}x/{tint_ms}ms" for code, (gain, tint_ms, _creg1) in sorted(TINT_MAP.items())
)
INTERVAL_HELP_TEXT = ", ".join(
    f"{code}={minutes}min" for code, minutes in sorted(INTERVAL_MINUTES_MAP.items())
)


def get_next_log_index(output_dir):
    pattern = re.compile(r"^uv_(\d{5,})_\d{2}_\d{2}\.txt$")
    max_index = 0
    if os.path.isdir(output_dir):
        for name in os.listdir(output_dir):
            match = pattern.match(name)
            if match:
                max_index = max(max_index, int(match.group(1)))
    return max_index + 1


def get_log_path(output_dir, mode_code, tint_code):
    os.makedirs(output_dir, exist_ok=True)
    idx = get_next_log_index(output_dir)
    return os.path.join(output_dir, f"uv_{idx:05d}_{mode_code}_{tint_code}.txt")


def create_unique_log_file(output_dir, mode_code, tint_code):
    os.makedirs(output_dir, exist_ok=True)
    idx = get_next_log_index(output_dir)
    while True:
        log_path = os.path.join(output_dir, f"uv_{idx:05d}_{mode_code}_{tint_code}.txt")
        try:
            fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            return log_path, os.fdopen(fd, "w", encoding="utf-8")
        except FileExistsError:
            idx += 1


class AS7331Sensor:
    def __init__(self, bus_num=1, i2c_addr=I2C_ADDR):
        if smbus_module is None:
            raise RuntimeError("smbus/smbus2 is required. Install with: pip install smbus2")
        self.bus = smbus_module.SMBus(bus_num)
        self.addr = i2c_addr

    def write_register(self, reg, value):
        self.bus.write_byte_data(self.addr, reg, value)

    def read_register(self, reg):
        return self.bus.read_byte_data(self.addr, reg)

    def read_channel_raw(self, reg_addr):
        data = self.bus.read_i2c_block_data(self.addr, reg_addr, 2)
        return (data[1] << 8) | data[0]

    def configure_and_start(self, creg1_value):
        self.write_register(CREG1, creg1_value)
        self.write_register(CREG3, 0x10)
        self.write_register(OSR, 0x83)

    def stop(self):
        self.write_register(OSR, 0x03)

    def read_uv(self):
        return (
            self.read_channel_raw(MRES1),
            self.read_channel_raw(MRES2),
            self.read_channel_raw(MRES3),
        )

    def read_status(self):
        return {
            "OSR": self.read_register(OSR),
            "CREG1": self.read_register(CREG1),
            "CREG3": self.read_register(CREG3),
        }

    def close(self):
        self.bus.close()


def resolve_duration_seconds(mode, duration_minutes, interval_code):
    if mode == "02":
        # Static mode is fixed to 7 minutes to match the required mission behavior.
        return STATIC_MODE_DURATION_MINUTES * 60

    if duration_minutes is not None:
        if not 1 <= duration_minutes <= 10:
            raise ValueError("--duration-minutes must be in the range 1-10 for mode=01")
        return duration_minutes * 60

    if interval_code is None:
        return DEFAULT_VARYING_MODE_DURATION_SECONDS

    # Keep this check for direct function usage where argparse choices are not applied.
    minutes = INTERVAL_MINUTES_MAP.get(interval_code)
    if minutes is None:
        raise ValueError(f"Invalid interval code: {interval_code}")
    return minutes * 60


def run_logger(mode, tint_code, output_dir, duration_minutes=None, interval_code=None):
    if tint_code not in TINT_MAP:
        raise ValueError(f"Invalid tint code: {tint_code}")

    gain, tint_ms, creg1_value = TINT_MAP[tint_code]
    duration_seconds = resolve_duration_seconds(mode, duration_minutes, interval_code)
    sample_period = SAMPLE_PERIOD_SECONDS

    if mode == "02" and (duration_minutes is not None or interval_code is not None):
        print("[INFO] mode=02 uses fixed 7 minutes; duration/interval options are ignored.")

    log_path, log_file = create_unique_log_file(output_dir, mode, tint_code)
    print(f"[INFO] Output file: {log_path}")
    print(f"[INFO] I2C address: 0x{I2C_ADDR:02X}")
    print(f"[INFO] Mode={mode}, Gain={gain}x, Tint={tint_ms}ms, CREG1=0x{creg1_value:02X}, Duration={duration_seconds}s")

    sensor = None
    try:
        sensor = AS7331Sensor()
        print("[INFO] Sensor initialized successfully.")
        sensor.configure_and_start(creg1_value)
        status = sensor.read_status()
        status_line = (
            f"STATUS OSR=0x{status['OSR']:02X}, "
            f"CREG1=0x{status['CREG1']:02X}, "
            f"CREG3=0x{status['CREG3']:02X}"
        )
        print(f"[INFO] {status_line}")

        start = time.time()
        next_sample = start
        with log_file:
            log_file.write(f"# Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write(f"# Mode={mode}, Gain={gain}x, Tint={tint_ms}ms, CREG1=0x{creg1_value:02X}\n")
            log_file.write(f"# {status_line}\n")

            while time.time() - start < duration_seconds:
                try:
                    uva, uvb, uvc = sensor.read_uv()
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    line = f"[{ts}] UVA={uva}, UVB={uvb}, UVC={uvc}"
                    print(line)
                    log_file.write(line + "\n")
                    log_file.flush()
                except Exception as read_err:
                    print(f"[ERROR] Failed to read UV channels: {read_err}")

                next_sample += sample_period
                sleep_for = max(MIN_LOOP_SLEEP_SECONDS, next_sample - time.time())
                time.sleep(sleep_for)

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")
    except Exception as err:
        print(f"[ERROR] Sensor operation failed: {err}")
    finally:
        if sensor is not None:
            try:
                sensor.stop()
            except Exception as stop_err:
                print(f"[WARN] Failed to stop sensor cleanly: {stop_err}")
            sensor.close()
            print("[INFO] Sensor deinitialized.")


def parse_args():
    parser = argparse.ArgumentParser(description="AS7331 UV logger for Raspberry Pi CM4")
    parser.add_argument("--mode", choices=["01", "02"], default="01", help="01=varying, 02=static")
    parser.add_argument("--duration-minutes", type=int, default=None, help="Used in mode=01 (1-10); ignored in mode=02")
    parser.add_argument("--tint-code", choices=sorted(TINT_MAP.keys()), default="02", help=f"Tint/Gain code ({TINT_HELP_TEXT})")
    parser.add_argument("--interval-code", choices=sorted(INTERVAL_MINUTES_MAP.keys()), default=None, help=f"Duration code for mode=01 ({INTERVAL_HELP_TEXT}); ignored in mode=02")
    parser.add_argument("--output-dir", default="uv_readings", help="Directory for UV log text files")
    return parser.parse_args()


if __name__ == "__main__":
    if smbus_module is None:
        print("[ERROR] smbus/smbus2 is required. Install with: pip install smbus2")
        raise SystemExit(1)

    args = parse_args()
    run_logger(
        mode=args.mode,
        tint_code=args.tint_code,
        output_dir=args.output_dir,
        duration_minutes=args.duration_minutes,
        interval_code=args.interval_code,
    )
