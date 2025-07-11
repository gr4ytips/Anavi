# sensors/bh1750_sensor.py
# This file contains the implementation for reading data from the BH1750 sensor.
# Adapted from: https://github.com/AnaviTechnology/anavi-examples/blob/master/sensors/BH1750/python/bh1750.py

import smbus2 
import time
import logging
import random # For mock mode

logger = logging.getLogger(__name__)

# BH1750 Address
BH1750_ADDR = 0x23

# BH1750 Commands
BH1750_POWER_ON = 0x01   # Power On
# Changed to ONE_TIME_HIGH_RES_MODE for more reliable single measurements
BH1750_MEASUREMENT_MODE = 0x20 # One-time measurement mode, high resolution (1 lux)
# BH1750_CONTINUOUS_HIGH_RES_MODE = 0x10 # Keep for reference if continuous mode is desired later

# I2C bus number (typically 1 for Raspberry Pi)
I2C_BUS = 1

class BH1750:
    """
    Class to interface with the BH1750 ambient light sensor.
    Supports both mock mode (for development without hardware) and actual I2C communication.
    """
    def __init__(self, bus_number=I2C_BUS, mock_mode=False):
        """
        Initializes the BH1750 sensor.
        :param bus_number (int): The I2C bus number (typically 1 for Raspberry Pi).
        :param mock_mode (bool): If True, operates in mock mode (generates random data).
                                  If False, attempts to initialize I2C bus for hardware communication.
        """
        self.bus_number = bus_number
        self.mock_mode = mock_mode
        self.bus = None # Initialize bus to None
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"BH1750 sensor initializing (mock_mode={self.mock_mode}).")

        # Mock data initialization
        self._mock_light = 300.0 # Initial mock light value

        if not self.mock_mode:
            try:
                self.connect_and_power_on(retries=3)
            except IOError:
                self.logger.warning("BH1750 hardware initialization failed after retries. Falling back to mock mode.")
                self.mock_mode = True
            except Exception as e:
                self.logger.error(f"Unexpected error during BH1750 hardware initialization: {e}. Falling back to mock mode.", exc_info=True)
                self.mock_mode = True
        
        if self.mock_mode:
            self.logger.info("BH1750 operating in mock mode.")


    def connect_and_power_on(self, retries=3):
        """
        Attempts to connect to the I2C bus and power on the sensor with retries.
        Uses smbus2 for I2C communication.
        Raises IOError if connection fails after retries.
        """
        if self.mock_mode: # Should not be called in mock mode, but safety check
            return True

        for i in range(retries):
            try:
                if self.bus: # Close existing bus if any
                    try:
                        self.bus.close()
                        self.logger.debug(f"BH1750: Closed existing I2C bus {self.bus_number} connection.")
                    except Exception as close_e:
                        self.logger.warning(f"BH1750: Error closing existing I2C bus {self.bus_number}: {close_e}")

                self.bus = smbus2.SMBus(self.bus_number)
                self.bus.write_byte(BH1750_ADDR, BH1750_POWER_ON) # Ensure sensor is powered on
                time.sleep(0.001) # Small delay after power on
                self.logger.info(f"BH1750 sensor initialized and powered on I2C bus {self.bus_number} (Attempt {i+1}/{retries}).")
                return True
            except FileNotFoundError:
                self.logger.error(f"Attempt {i+1}/{retries}: Could not open I2C bus {self.bus_number}. Ensure I2C is enabled and 'smbus2' library is installed and permissions are correct.")
                time.sleep(1) # Wait before retrying
            except IOError as e: # Catch IOError specifically for bus/sensor issues
                self.logger.warning(f"Attempt {i+1}/{retries}: I/O Error connecting to BH1750 sensor or powering on: {e}. Retrying...")
                time.sleep(1)
            except Exception as e:
                self.logger.warning(f"Attempt {i+1}/{retries}: Unexpected error during BH1750 connection or power on: {e}. Retrying...", exc_info=True)
                time.sleep(1)
        
        self.logger.error(f"Failed to initialize BH1750 sensor after {retries} attempts.")
        if self.bus:
            try:
                self.bus.close()
            except Exception as e:
                self.logger.error(f"Error closing BH1750 I2C bus {self.bus_number} during failed init cleanup: {e}", exc_info=True)
            finally:
                self.bus = None # Ensure bus is None on failure
        raise IOError("BH1750 sensor initialization failed. Check connections and I2C setup.")


    def read_light(self):
        """
        Reads ambient light from the BH1750 sensor in Lux.
        Returns:
            float: Light intensity in Lux, or None if reading fails.
        """
        if self.mock_mode:
            # Simulate light change with some noise
            self._mock_light += random.uniform(-10.0, 10.0)
            self._mock_light = max(0.0, min(65535.0, self._mock_light)) # Clamp to sensor range
            self.logger.debug(f"Mock BH1750: Simulated light: {self._mock_light:.2f}lx")
            return self._mock_light

        # Hardware mode
        if self.bus is None:
            self.logger.error("BH1750 - No I2C bus connected. Cannot read light.")
            return None

        for attempt in range(3): # Retry reading up to 3 times
            try:
                # Send the One-Time High Resolution Mode command before each read
                self.bus.write_byte(BH1750_ADDR, BH1750_MEASUREMENT_MODE)
                # Use a slightly longer delay for reliability with one-time mode, as per your testing
                time.sleep(0.18) 

                # Read two bytes of data
                data = self.bus.read_i2c_block_data(BH1750_ADDR, 0, 2)
                
                # Convert the data to lux
                raw_value = (data[0] << 8) + data[1] # Store raw 16-bit value
                light_value = raw_value / 1.2 # Divide by 1.2 as per datasheet for Lux for High Resolution Mode
                
                # Enhanced logging to see the raw 16-bit value and bytes
                self.logger.debug("BH1750 - Raw Bytes: [{} {}], Raw 16-bit Value: {}, Calc Light: {:.2f}lx".format(
                    data[0], data[1], raw_value, light_value))
                
                # Check for consistently low or zero raw values
                if raw_value <= 10 and attempt == 0: # Only warn on first attempt if very low
                    self.logger.warning(f"BH1750 - Very low raw light value ({raw_value}). Ensure sensor is exposed to light.")
                
                return light_value
            except IOError as e:
                self.logger.warning(f"Attempt {attempt+1}/3: Failed to read light from BH1750 (0x{BH1750_ADDR:02x}): {e}. Retrying...")
                time.sleep(0.5) # Longer delay for I/O errors
            except Exception as e:
                self.logger.warning(f"Attempt {attempt+1}/3: Unexpected error reading light from BH1750: {e}. Retrying...", exc_info=True)
                time.sleep(0.1)
        
        self.logger.error(f"Failed to read light from BH1750 (0x{BH1750_ADDR:02x}) after 3 attempts.")
        return None

    def read_data(self):
        """
        Reads ambient light from the BH1750 sensor.
        Returns:
            dict: A dictionary containing 'light'. Returns None for value if reading failed.
        """
        light = self.read_light()
        return {'light': light}

    def close(self):
        """
        Closes the I2C bus connection.
        """
        if not self.mock_mode and self.bus: # Only close if not in mock mode and bus was actually opened
            try:
                self.bus.close()
                self.logger.info(f"BH1750 I2C bus {self.bus_number} closed.")
            except Exception as e:
                self.logger.error(f"Error closing BH1750 I2C bus {self.bus_number}: {e}", exc_info=True)
            finally:
                self.bus = None # Ensure bus is set to None after attempt to close

    def cleanup(self):
        """
        Provides an explicit cleanup method for consistency.
        """
        self.close()

    def __del__(self):
        """
        Ensures the I2C bus is closed when the object is deleted.
        """
        self.cleanup()
