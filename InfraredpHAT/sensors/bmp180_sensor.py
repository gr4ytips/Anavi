# sensors/bmp180_sensor.py
# This file contains the implementation for reading data from the BMP180 sensor.
# Adapted from: https://github.com/AnaviTechnology/anavi-examples/blob/master/sensors/BMP180/python/BMP180.py

import smbus2 
import time
import logging
import random # For mock mode

logger = logging.getLogger(__name__)

# BMP180 Address
BMP180_ADDR = 0x77

# BMP180 Registers
BMP180_CALIB_AC1 = 0xAA  # R   Calibration data (16 bits)
BMP180_CONTROL = 0xF4    # W   Control register
BMP180_TEMPDATA = 0xF6   # R   Temperature data (16 bits)
BMP180_PRESSUREDATA = 0xF6 # R   Pressure data (16-19 bits)

# Calibration values (read from EEPROM) - make these class attributes or pass them around if needed
# For now, let's keep them as globals for simplicity as per original
_ac1 = 0
_ac2 = 0
_ac3 = 0
_ac4 = 0
_ac5 = 0
_ac6 = 0
_b1 = 0
_b2 = 0
_mb = 0
_mc = 0
_md = 0

# Oversampling settings
# Mode 0: ultra low power, 1 sample, 4.5ms
# Mode 1: standard, 2 samples, 7.5ms
# Mode 2: high resolution, 4 samples, 13.5ms
# Mode 3: ultra high resolution, 8 samples, 25.5ms
OVERSAMPLING_SETTING = 3 # Ultra high resolution

# I2C bus number (typically 1 for Raspberry Pi)
I2C_BUS = 1

class BMP180:
    """
    Class to interface with the BMP180 barometric pressure and temperature sensor.
    Supports both mock mode (for development without hardware) and actual I2C communication.
    """
    def __init__(self, bus_number=I2C_BUS, mock_mode=False):
        """
        Initializes the BMP180 sensor and reads calibration data.
        :param bus_number (int): The I2C bus number (typically 1 for Raspberry Pi).
        :param mock_mode (bool): If True, operates in mock mode (generates random data).
                                  If False, attempts to initialize I2C bus for hardware communication.
        """
        self.bus_number = bus_number
        self.mock_mode = mock_mode
        self.bus = None # Initialize bus to None
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"BMP180 sensor initializing (mock_mode={self.mock_mode}).")

        # Mock data initialization
        self._mock_temperature = 25.0
        self._mock_pressure = 1013.25 # hPa (standard atmospheric pressure)
        self._mock_altitude = 0.0

        if not self.mock_mode:
            try:
                self.connect_and_read_calibration(retries=3)
            except IOError:
                self.logger.warning("BMP180 hardware initialization failed after retries. Falling back to mock mode.")
                self.mock_mode = True
            except Exception as e:
                self.logger.error(f"Unexpected error during BMP180 hardware initialization: {e}. Falling back to mock mode.", exc_info=True)
                self.mock_mode = True
        
        if self.mock_mode:
            self.logger.info("BMP180 operating in mock mode.")

    def connect_and_read_calibration(self, retries=3):
        """
        Attempts to connect to the I2C bus and read calibration data with retries.
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
                        self.logger.debug(f"BMP180: Closed existing I2C bus {self.bus_number} connection.")
                    except Exception as close_e:
                        self.logger.warning(f"BMP180: Error closing existing I2C bus {self.bus_number}: {close_e}")

                self.bus = smbus2.SMBus(self.bus_number)
                self._read_calibration_data() # This will raise IOError if calibration fails
                self.logger.info(f"BMP180 sensor initialized on I2C bus {self.bus_number} (Attempt {i+1}/{retries}).")
                return True
            except FileNotFoundError:
                self.logger.error(f"Attempt {i+1}/{retries}: Could not open I2C bus {self.bus_number}. Ensure I2C is enabled and 'smbus2' library is installed and permissions are correct.")
                time.sleep(1) # Wait before retrying
            except IOError as e: # Catch IOError specifically for bus/calibration issues
                self.logger.warning(f"Attempt {i+1}/{retries}: I/O Error during BMP180 connection or calibration: {e}. Retrying...")
                time.sleep(1)
            except Exception as e:
                self.logger.warning(f"Attempt {i+1}/{retries}: Unexpected error during BMP180 connection or calibration: {e}. Retrying...", exc_info=True)
                time.sleep(1)
        
        self.logger.error(f"Failed to initialize BMP180 sensor after {retries} attempts.")
        if self.bus:
            try:
                self.bus.close()
            except Exception as e:
                self.logger.error(f"Error closing BMP180 I2C bus {self.bus_number} during failed init cleanup: {e}", exc_info=True)
            finally:
                self.bus = None # Ensure bus is None on failure
        raise IOError("BMP180 sensor initialization failed. Check connections and I2C setup.")

    def _read_word_2c(self, register):
        """Reads a signed 16-bit word from a register."""
        if self.mock_mode:
            self.logger.debug(f"Mock BMP180: Simulated read word 2c from 0x{register:02x}")
            return random.randint(-32768, 32767) # Return a random 16-bit signed integer for mock

        if self.bus is None:
            self.logger.error(f"BMP180 - No I2C bus connected. Cannot read word from 0x{register:02x}.")
            return None
        try:
            # Use i2c_rdwr for combining write (register address) and read operations
            read_bytes = smbus2.i2c_msg.read(BMP180_ADDR, 2)
            write_reg = smbus2.i2c_msg.write(BMP180_ADDR, [register])
            self.bus.i2c_rdwr(write_reg, read_bytes)
            
            data = list(read_bytes) # Convert to list of integers
            msb = data[0]
            lsb = data[1]
            
            value = (msb << 8) + lsb
            if value >= 0x8000:
                return -((65535 - value) + 1)
            else:
                return value
        except IOError as e:
            self.logger.error(f"BMP180: I/O Error reading 2-byte signed word from register 0x{register:02x}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"BMP180: Error reading 2-byte signed word from register 0x{register:02x}: {e}", exc_info=True)
            return None

    def _read_unsigned_word(self, register):
        """Reads an unsigned 16-bit word from a register."""
        if self.mock_mode:
            self.logger.debug(f"Mock BMP180: Simulated read unsigned word from 0x{register:02x}")
            return random.randint(0, 65535) # Return a random 16-bit unsigned integer for mock

        if self.bus is None:
            self.logger.error(f"BMP180 - No I2C bus connected. Cannot read unsigned word from 0x{register:02x}.")
            return None
        try:
            read_bytes = smbus2.i2c_msg.read(BMP180_ADDR, 2)
            write_reg = smbus2.i2c_msg.write(BMP180_ADDR, [register])
            self.bus.i2c_rdwr(write_reg, read_bytes)
            
            data = list(read_bytes)
            msb = data[0]
            lsb = data[1]
            return (msb << 8) + lsb
        except IOError as e:
            self.logger.error(f"BMP180: I/O Error reading 2-byte unsigned word from register 0x{register:02x}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"BMP180: Error reading 2-byte unsigned word from register 0x{register:02x}: {e}", exc_info=True)
            return None

    def _read_calibration_data(self):
        """Reads the 11 calibration values from the BMP180's EEPROM."""
        # Use local variables for calibration values to avoid global state issues if possible
        # Or ensure they are class attributes if truly shared by instance methods only
        # For now, keeping as globals as per original, but be aware of implications.
        global _ac1, _ac2, _ac3, _ac4, _ac5, _ac6, _b1, _b2, _mb, _mc, _md

        if self.mock_mode: # In mock mode, use some reasonable default calibration values
            self.logger.debug("Mock BMP180: Simulating reading calibration data.")
            _ac1 = 408
            _ac2 = -72
            _ac3 = -14383
            _ac4 = 32741
            _ac5 = 32757
            _ac6 = 23153
            _b1 = 6190
            _b2 = 4
            _mb = -32768
            _mc = -8711
            _md = 2868
            return

        # Using _read_word_2c and _read_unsigned_word which now include error handling and return None on failure
        _ac1 = self._read_word_2c(0xAA)
        _ac2 = self._read_word_2c(0xAC)
        _ac3 = self._read_word_2c(0xAE)
        _ac4 = self._read_unsigned_word(0xB0)
        _ac5 = self._read_unsigned_word(0xB2)
        _ac6 = self._read_unsigned_word(0xB4)
        _b1 = self._read_word_2c(0xB6)
        _b2 = self._read_word_2c(0xB8)
        _mb = self._read_word_2c(0xBA)
        _mc = self._read_word_2c(0xBC)
        _md = self._read_word_2c(0xBE)

        # Check if any crucial calibration value is None, if so, raise an error
        # This will be caught by connect_and_read_calibration retries
        if any(v is None for v in [_ac1, _ac2, _ac3, _ac4, _ac5, _ac6, _b1, _b2, _mb, _mc, _md]):
            self.logger.error("Failed to read all BMP180 calibration values. Some are None.")
            raise IOError("BMP180 calibration data incomplete or unreadable.")
        
        # Ensure all calibration values are integers as expected by calculations
        _ac1 = int(_ac1)
        _ac2 = int(_ac2)
        _ac3 = int(_ac3)
        _ac4 = int(_ac4)
        _ac5 = int(_ac5)
        _ac6 = int(_ac6)
        _b1 = int(_b1)
        _b2 = int(_b2)
        _mb = int(_mb)
        _mc = int(_mc)
        _md = int(_md)

        self.logger.debug("BMP180 Calibration Data Read: AC1={}, AC2={}, AC3={}, AC4={}, AC5={}, AC6={}, B1={}, B2={}, MB={}, MC={}, MD={}".format(
            _ac1, _ac2, _ac3, _ac4, _ac5, _ac6, _b1, _b2, _mb, _mc, _md
        ))


    def _read_raw_temperature(self):
        """Reads the uncompensated temperature value."""
        if self.mock_mode:
            # Simulate a slowly changing temperature
            self._mock_temperature += random.uniform(-0.1, 0.1)
            self._mock_temperature = max(-40.0, min(85.0, self._mock_temperature))
            # Convert to a raw-like value for consistency with calculation function
            # This mapping is approximate, just to make the calculation path work
            return int((self._mock_temperature + 46.85) * 65536 / 175.72) 

        if self.bus is None:
            self.logger.error("BMP180 - No I2C bus connected. Cannot read raw temperature.")
            return None
        
        for attempt in range(3):
            try:
                # Write command to start temperature measurement
                self.bus.write_byte_data(BMP180_ADDR, BMP180_CONTROL, 0x2E) 
                time.sleep(0.005) # Wait for 4.5ms

                # Read 2 bytes (temperature data)
                read_msg = smbus2.i2c_msg.read(BMP180_ADDR, 2)
                write_msg = smbus2.i2c_msg.write(BMP180_ADDR, [BMP180_TEMPDATA])
                self.bus.i2c_rdwr(write_msg, read_msg)
                
                data = list(read_msg)
                msb = data[0]
                lsb = data[1]
                ut = (msb << 8) + lsb
                self.logger.debug(f"BMP180 - Raw Temp: {ut}")
                return ut
            except IOError as e:
                self.logger.warning(f"Attempt {attempt+1}/3: I/O Error reading raw temperature from BMP180: {e}. Retrying...")
                time.sleep(0.5)
            except Exception as e:
                self.logger.warning(f"Attempt {attempt+1}/3: Unexpected error reading raw temperature from BMP180: {e}. Retrying...", exc_info=True)
                time.sleep(0.1)
        self.logger.error("Failed to read raw temperature from BMP180 after 3 attempts.")
        return None

    def _read_raw_pressure(self):
        """Reads the uncompensated pressure value."""
        if self.mock_mode:
            # Simulate a slowly changing pressure with some noise
            self._mock_pressure += random.uniform(-0.5, 0.5)
            self._mock_pressure = max(950.0, min(1050.0, self._mock_pressure)) # Clamp around reasonable values
            # Convert to a raw-like value for consistency with calculation function
            # This mapping is approximate
            return int(self._mock_pressure * 100 * (1 << (8 - OVERSAMPLING_SETTING))) # Reverse pressure calculation for mock raw value

        if self.bus is None:
            self.logger.error("BMP180 - No I2C bus connected. Cannot read raw pressure.")
            return None

        for attempt in range(3):
            try:
                # Send command for pressure measurement with oversampling setting
                self.bus.write_byte_data(BMP180_ADDR, BMP180_CONTROL, 0x34 + (OVERSAMPLING_SETTING << 6))
                
                # Wait for measurement to complete based on oversampling setting
                delay = [0.005, 0.008, 0.014, 0.026][OVERSAMPLING_SETTING]
                time.sleep(delay)

                # Read 3 bytes (MSB, LSB, XLSB) for pressure data
                read_msg = smbus2.i2c_msg.read(BMP180_ADDR, 3)
                write_msg = smbus2.i2c_msg.write(BMP180_ADDR, [BMP180_PRESSUREDATA])
                self.bus.i2c_rdwr(write_msg, read_msg)

                data = list(read_msg)
                msb = data[0]
                lsb = data[1]
                xlsb = data[2]
                
                raw_pressure = ((msb << 16) + (lsb << 8) + xlsb) >> (8 - OVERSAMPLING_SETTING)
                self.logger.debug(f"BMP180 - Raw Pressure: {raw_pressure}")
                return raw_pressure
            except IOError as e:
                self.logger.warning(f"Attempt {attempt+1}/3: I/O Error reading raw pressure from BMP180: {e}. Retrying...")
                time.sleep(0.5)
            except Exception as e:
                self.logger.warning(f"Attempt {attempt+1}/3: Unexpected error reading raw pressure from BMP180: {e}. Retrying...", exc_info=True)
                time.sleep(0.1)
        self.logger.error("Failed to read raw pressure from BMP180 after 3 attempts.")
        return None

    def _calculate_temperature(self, ut):
        """Calculates true temperature from uncompensated temperature."""
        if ut is None:
            return None, None # Return None for temp and b5
        
        # All intermediate calculations for temperature compensation should be integer-based
        x1 = ((ut - _ac6) * _ac5) >> 15
        x2 = (int(_mc) << 11) // (x1 + int(_md)) # Explicit int cast for _mc and _md, use //
        b5 = int(x1 + x2) # Explicitly ensure b5 is an integer
        
        # The final temperature is a float
        temperature = ((b5 + 8) >> 4) / 10.0 
        return temperature, b5 # Return b5 as it's needed for pressure calculation

    def _calculate_pressure(self, up, b5):
        """Calculates true pressure from uncompensated pressure."""
        if up is None or b5 is None:
            return None

        # All intermediate calculations should be integer-based
        b5_int = int(b5) 

        # Step 1: calculate B6
        b6 = b5_int - 4000

        # Step 2: calculate X1, X2, X3, B3
        x1 = (_b2 * ((b6 * b6) >> 12)) >> 11
        x2 = (_ac2 * b6) >> 11
        x3 = x1 + x2
        # b3 is typically int for bitwise shifts. Adjusted based on typical implementations for integer math.
        b3 = ((_ac1 * 4 + x3) << OVERSAMPLING_SETTING + 2) // 4 

        # Step 3: calculate X1, X2, X3, B4
        x1 = (_ac3 * b6) >> 13
        x2 = (_b1 * ((b6 * b6) >> 12)) >> 16
        x3 = ((x1 + x2) + 2) // 2 
        b4 = (_ac4 * (x3 + 32768)) >> 15

        # Step 4: calculate B7
        b7 = (int(up) - b3) * (50000 >> OVERSAMPLING_SETTING)

        # Step 5: calculate p
        if b7 < 0x80000000:
            p = (b7 * 2) // b4
        else:
            p = (b7 // b4) * 2

        # Step 6: calculate X1, X2 and final pressure compensation
        x1 = (int(p) >> 8) * (int(p) >> 8) 
        x1 = (x1 * 3038) >> 16
        x2 = (-7357 * int(p)) >> 16
        pressure_pa = int(p) + ((x1 + x2 + 3791) >> 4) 

        return float(pressure_pa / 100.0) # Convert Pa to hPa (hectopascal) and return as float

    def calculate_altitude(self, pressure_hpa, sea_level_pressure_hpa=1013.25):
        """
        Calculates altitude in meters from pressure.
        Formula: altitude (m) = 44330 * [1 - (pressure / sea_level_pressure)^(1/5.255)]
        :param pressure_hpa: Current pressure in hectopascals (hPa).
        :param sea_level_pressure_hpa: Reference sea-level pressure in hPa.
        :return: Altitude in meters.
        """
        if pressure_hpa is None:
            return None
        try:
            altitude = 44330 * (1 - pow(pressure_hpa / sea_level_pressure_hpa, 1/5.255))
            return altitude
        except Exception as e:
            self.logger.error(f"Error calculating altitude: {e}")
            return None


    def read_data(self):
        """
        Reads both temperature and pressure from the BMP180 sensor.
        Returns:
            dict: A dictionary containing 'temperature', 'pressure', and 'altitude'.
                  Returns None for a value if reading failed.
        """
        if self.mock_mode:
            # Simulate a slowly changing temperature, pressure, and altitude
            self._mock_temperature += random.uniform(-0.1, 0.1)
            self._mock_temperature = max(-40.0, min(85.0, self._mock_temperature))

            self._mock_pressure += random.uniform(-0.5, 0.5)
            self._mock_pressure = max(950.0, min(1050.0, self._mock_pressure))

            # Simulate altitude based on pressure
            self._mock_altitude = self.calculate_altitude(self._mock_pressure)
            if self._mock_altitude is None: # Fallback if calculate_altitude returns None for some reason
                self._mock_altitude = random.uniform(-100, 500) # Just a random altitude

            self.logger.debug("Mock BMP180 - Temp: {:.2f}°C, Pressure: {:.2f}hPa, Altitude: {:.2f}m".format(
                self._mock_temperature, self._mock_pressure, self._mock_altitude
            ))
            return {'temperature': self._mock_temperature, 'pressure': self._mock_pressure, 'altitude': self._mock_altitude}

        # Hardware mode
        ut = self._read_raw_temperature()
        temp_c, b5 = self._calculate_temperature(ut) # Get b5 from temperature calculation

        up = self._read_raw_pressure()
        pressure_hpa = self._calculate_pressure(up, b5) 

        altitude_m = self.calculate_altitude(pressure_hpa)

        self.logger.debug("BMP180 - Temp: {:.2f}°C, Pressure: {:.2f}hPa, Altitude: {:.2f}m".format(
            temp_c if temp_c is not None else float('nan'), 
            pressure_hpa if pressure_hpa is not None else float('nan'), 
            altitude_m if altitude_m is not None else float('nan')
        ))
        return {'temperature': temp_c, 'pressure': pressure_hpa, 'altitude': altitude_m}

    def close(self):
        """
        Closes the I2C bus connection.
        """
        if not self.mock_mode and self.bus: # Only close if not in mock mode and bus was actually opened
            try:
                self.bus.close()
                self.logger.info(f"BMP180 I2C bus {self.bus_number} closed.")
            except Exception as e:
                self.logger.error(f"Error closing BMP180 I2C bus {self.bus_number}: {e}", exc_info=True)
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

