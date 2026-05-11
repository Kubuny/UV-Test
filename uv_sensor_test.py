#!/usr/bin/env python3
"""
UV Sensor Test Script for Raspberry Pi CM4
Displays UV sensor status and readings
Saves data to numbered text files
"""

import time
import os
import sys
from datetime import datetime

try:
    import board
    import busio
    import adafruit_veml6075
except ImportError:
    print("Error: Required libraries not found.")
    print("Install with: pip install adafruit-circuitpython-veml6075")
    sys.exit(1)


class UVSensorLogger:
    def __init__(self, data_dir="uv_data"):
        self.data_dir = data_dir
        self.file_count = 0
        self.sensor = None
        self.i2c = None
        
        # Create data directory if it doesn't exist
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            print(f"Created data directory: {self.data_dir}")
    
    def init_sensor(self):
        """Initialize the UV sensor"""
        try:
            self.i2c = busio.I2C(board.SCL, board.SDA)
            # Use VEML6075 class (not Adafruit_VEML6075)
            self.sensor = adafruit_veml6075.VEML6075(self.i2c)
            print("✓ UV Sensor initialized successfully")
            return True
        except Exception as e:
            print(f"✗ Failed to initialize sensor: {e}")
            return False
    
    def get_next_filename(self):
        """Get the next numbered filename"""
        self.file_count += 1
        return os.path.join(self.data_dir, f"uv_data_{self.file_count:04d}.txt")
    
    def read_sensor(self):
        """Read sensor data"""
        try:
            uv_a = self.sensor.uv_a
            uv_b = self.sensor.uv_b
            uv_index = self.sensor.uv_index
            return {
                "uv_a": uv_a,
                "uv_b": uv_b,
                "uv_index": uv_index,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            }
        except Exception as e:
            print(f"✗ Error reading sensor: {e}")
            return None
    
    def log_data(self, data, filename):
        """Log data to file"""
        try:
            with open(filename, 'w') as f:
                f.write("=" * 50 + "\n")
                f.write(f"UV Sensor Data Log #{self.file_count}\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Timestamp: {data['timestamp']}\n")
                f.write(f"UV-A: {data['uv_a']:.2f} W/m²\n")
                f.write(f"UV-B: {data['uv_b']:.2f} W/m²\n")
                f.write(f"UV Index: {data['uv_index']:.2f}\n")
                f.write("\n" + "=" * 50 + "\n")
            return True
        except Exception as e:
            print(f"✗ Failed to save data: {e}")
            return False
    
    def display_reading(self, data):
        """Display reading in console"""
        print(f"\n[{data['timestamp']}]")
        print(f"  UV-A:     {data['uv_a']:7.2f} W/m²")
        print(f"  UV-B:     {data['uv_b']:7.2f} W/m²")
        print(f"  UV Index: {data['uv_index']:7.2f}")
    
    def run(self, interval=1):
        """Main loop"""
        if not self.init_sensor():
            return
        
        print("\n" + "=" * 50)
        print("UV Sensor Test Started")
        print("=" * 50)
        print(f"Data directory: {os.path.abspath(self.data_dir)}")
        print(f"Reading interval: {interval} second(s)")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                data = self.read_sensor()
                if data:
                    self.display_reading(data)
                    filename = self.get_next_filename()
                    if self.log_data(data, filename):
                        print(f"  → Saved to: {filename}")
                
                time.sleep(interval)
        
        except KeyboardInterrupt:
            print("\n" + "=" * 50)
            print(f"Test stopped. Total readings: {self.file_count}")
            print("=" * 50)
        except Exception as e:
            print(f"\n✗ Unexpected error: {e}")
        finally:
            if self.i2c:
                self.i2c.deinit()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="UV Sensor Test for Raspberry Pi CM4")
    parser.add_argument("-d", "--dir", default="uv_data", help="Data directory (default: uv_data)")
    parser.add_argument("-i", "--interval", type=float, default=1, help="Read interval in seconds (default: 1)")
    
    args = parser.parse_args()
    
    logger = UVSensorLogger(data_dir=args.dir)
    logger.run(interval=args.interval)
