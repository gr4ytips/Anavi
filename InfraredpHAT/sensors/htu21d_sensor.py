# -*- coding: utf-8 -*-
# sensors/htu21d_sensor.py
# This file contains the implementation for reading data from the HTU21D sensor.
# Adapted from: https://github.com/AnaviTechnology/anavi-examples/blob/master/sensors/HTU21D/python/htu21d.py

import smbus2 # Changed from smbus to smbus2
import time
import logging

# HTU21D Address
HTU21D_ADDR = 0x40

# HTU21D Commands
HTU21D_TEMP_HOLD = 0xE3  # Hold master mode, temperature
HTU21D_HUMID_HOLD = 0xE5 # Hold master mode, humidity
# HTU21D_TEMP_NOHOLD = 0xF3 # No Hold master mode, temperature (not used in provided example, keeping for reference)
# HTU21D_HUMID_NOHOLD = 0xF5 # No Hold master mode, humidity (not used in provided example, keeping for reference)
HTU21D_RESET = 0xFE    # Soft reset

class HTU21D:
    """
    Class to interface with the HTU21D temperature and humidity sensor.
    """
    def __init__(self, bus_number=1):
        """
        Initializes the HTU21D sensor and performs a soft reset.
        Args:
            bus_number (int): The I2C bus number (typically 1 for Raspberry Pi).
        """
        self.bus_number = bus_number
        self.bus = None # Initialize bus to None
        self.connect_and_reset(retries=3) # Attempt to connect and reset

    def connect_and_reset(self, retries=3):
        """
        Attempts to connect to the I2C bus and reset the sensor with retries.
        Uses smbus2 for I2C communication.
        """
        for i in range(retries):
            try:
                # Close any existing bus connection before opening a new one
                if self.bus:
                    try:
                        self.bus.close()
                        logging.debug("Closed existing I2C bus connection.")
                    except Exception as close_e:
                        logging.warning(f"Error closing existing I2C bus: {close_e}")

                self.bus = smbus2.SMBus(self.bus_number)
                
                # Create a write message for the reset command
                msg_reset = smbus2.i2c_msg.write(HTU21D_ADDR, [HTU21D_RESET])
                self.bus.i2c_rdwr(msg_reset) # Perform the write
                time.sleep(0.015)  # Wait for reset to complete (15ms as per datasheet)
                logging.info(f"HTU21D sensor initialized and reset on I2C bus {self.bus_number} (Attempt {i+1}/{retries}).")
                return True
            except FileNotFoundError:
                logging.error(f"Attempt {i+1}/{retries}: Could not open I2C bus {self.bus_number}. Ensure I2C is enabled and permissions are correct.")
                time.sleep(1) # Wait before retrying
            except Exception as e:
                logging.warning(f"Attempt {i+1}/{retries}: Failed to connect to HTU21D sensor or perform reset using smbus2: {e}. Retrying...")
                time.sleep(1) # Wait before retrying
        
        logging.error(f"Failed to initialize HTU21D sensor after {retries} attempts.")
        # If initialization fails after retries, ensure bus is closed and re-raise.
        if self.bus:
            self.bus.close()
            self.bus = None
        raise IOError("HTU21D sensor initialization failed. Check connections and I2C setup.")

    def _read_sensor_value(self, command, delay_s, sensor_name=""):
        """
        Reads a 16-bit sensor value using smbus2 and performs CRC check.
        Args:
            command (int): The I2C command to send (e.g., HTU21D_TEMP_HOLD).
            delay_s (float): Delay in seconds to wait for measurement.
            sensor_name (str): Name of the sensor/metric for logging.
        Returns:
            float: The raw 16-bit sensor value, or None if reading fails.
        """
        if self.bus is None:
            logging.error(f"HTU21D - No I2C bus connected. Cannot read {sensor_name}.")
            return None

        for attempt in range(3): # Retry reading up to 3 times
            try:
                # Trigger measurement by writing the command
                msg_write = smbus2.i2c_msg.write(HTU21D_ADDR, [command])
                self.bus.i2c_rdwr(msg_write)
                time.sleep(delay_s) # Wait for measurement to complete

                # Read 3 bytes (2 data bytes + 1 CRC byte)
                msg_read = smbus2.i2c_msg.read(HTU21D_ADDR, 3)
                self.bus.i2c_rdwr(msg_read)
                data = list(msg_read) # Convert to list of integers

                if len(data) == 3:
                    msb, lsb, crc = data[0], data[1], data[2]
                    raw_value = (msb << 8) | lsb

                    # Perform CRC check
                    if self._check_crc(msb, lsb, crc):
                        logging.debug(f"HTU21D - Read {sensor_name} raw value: {raw_value}, CRC valid.")
                        return raw_value
                    else:
                        logging.warning(f"Attempt {attempt+1}/3: HTU21D {sensor_name} CRC check failed. Retrying...")
                else:
                    logging.warning(f"Attempt {attempt+1}/3: HTU21D {sensor_name} read unexpected number of bytes ({len(data)}). Retrying...")
                
                time.sleep(0.1) # Small delay before next retry for non-IO errors

            except IOError as e: # Catch specific I/O errors (e.g., [Errno 121] Remote I/O error)
                logging.warning(f"Attempt {attempt+1}/3: Failed to read {sensor_name} from HTU21D (0x{HTU21D_ADDR:02x}): {e}. Retrying...")
                # Do NOT attempt reset inside read_sensor_value as per our new design.
                # The main application should handle persistent errors and switch to mock if needed.
                time.sleep(0.5) # Longer delay for I/O errors
            except Exception as e:
                logging.warning(f"Attempt {attempt+1}/3: Unexpected error reading {sensor_name} from HTU21D: {e}. Retrying...")
                time.sleep(0.1) # Small delay before next retry
        
        logging.error(f"Failed to read {sensor_name} from HTU21D (0x{HTU21D_ADDR:02x}) after 3 attempts.")
        return None

    def _check_crc(self, msb, lsb, checksum):
        """Calculates and checks CRC for HTU21D sensor data."""
        # This CRC algorithm is specific to HTU21D (and SHT21/SHT31)
        # Polynomial: 0x131 (x^8 + x^5 + x^4 + 1)
        data = [msb, lsb]
        crc = 0
        for byte in data:
            crc ^= byte
            for i in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x131
                else:
                    crc <<= 1
        return crc & 0xFF == checksum


    def read_temperature(self):
        """
        Reads temperature from the HTU21D sensor.
        Returns:
            float: Temperature in Celsius, or None if reading fails.
        """
        raw_temp = self._read_sensor_value(HTU21D_TEMP_HOLD, 0.05, "temperature") # 50ms delay
        if raw_temp is None:
            return None
        
        # Formula from datasheet: T = -46.85 + 175.72 * (raw_temp / 2^16)
        temperature = -46.85 + (175.72 * raw_temp / 65536.0)
        return temperature

    def read_humidity(self):
        """
        Reads humidity from the HTU21D sensor.
        Returns:
            float: Relative humidity percentage, or None if reading fails.
        """
        raw_humidity = self._read_sensor_value(HTU21D_HUMID_HOLD, 0.05, "humidity") # 50ms delay
        if raw_humidity is None:
            return None

        # Formula from datasheet: RH = -6 + 125 * (raw_humidity / 2^16)
        humidity = -6.0 + (125.0 * raw_humidity / 65536.0)
        return humidity

    def read_data(self):
        """
        Reads both temperature and humidity from the HTU21D sensor.
        Returns:
            dict: A dictionary containing 'temperature' and 'humidity'.
                  Returns None for a value if reading failed.
        """
        temperature = self.read_temperature()
        humidity = self.read_humidity()
        logging.debug("HTU21D - Temp: {:.2f}�C, Humidity: {:.2f}%".format(
            temperature if temperature is not None else -1,
            humidity if humidity is not None else -1
        ))
        return {'temperature': temperature, 'humidity': humidity}

    def close(self):
        """
        Closes the I2C bus connection.
        """
        if self.bus:
            try:
                self.bus.close()
                logging.info(f"HTU21D I2C bus {self.bus_number} closed.")
            except Exception as e:
                logging.error(f"Error closing HTU21D I2C bus {self.bus_number}: {e}", exc_info=True)
            finally:
                self.bus = None

    def __del__(self):
        """
        Ensures the I2C bus is closed when the object is deleted.
        """
        self.close()

