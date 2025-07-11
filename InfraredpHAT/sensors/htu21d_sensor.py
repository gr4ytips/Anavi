# sensors/htu21d_sensor.py
# -*- coding: utf-8 -*-
import time
import struct
import logging
import random

try:
    import smbus2
    _SENSORS_AVAILABLE = True
except ImportError:
    _SENSORS_AVAILABLE = False
    logging.warning("HTU21D: smbus2 library not found. Hardware sensor will not be available.")


logger = logging.getLogger(__name__)

# HTU21D sensor constants
HTU21D_ADDR = 0x40
# FIX: Use the "hold master" commands for more reliable readings
CMD_READ_TEMP_HOLD = 0xE3
CMD_READ_HUM_HOLD = 0xE5
CMD_RESET = 0xFE

# User Register bits
USER_REGISTER_RESOLUTION_RH12_TEMP14 = 0x00

# I2C bus number (typically 1 for Raspberry Pi)
I2C_BUS = 1 

class HTU21D:
    """
    Driver for the HTU21D digital humidity and temperature sensor.
    """

    def __init__(self, mock_mode=False):
        """
        Initializes the HTU21D sensor.
        """
        self.mock_mode = mock_mode
        self.bus = None
        self.address = HTU21D_ADDR
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"HTU21D sensor initializing (mock_mode={self.mock_mode}).")

        if not self.mock_mode and _SENSORS_AVAILABLE:
            try:
                self.bus = smbus2.SMBus(I2C_BUS)
                self.soft_reset()
                self.logger.info(f"HTU21D hardware sensor initialized on I2C bus {I2C_BUS}.")
            except Exception as e:
                self.logger.error(f"Failed to initialize HTU21D hardware sensor: {e}. Falling back to mock mode.", exc_info=True)
                self.mock_mode = True
        else:
            if not _SENSORS_AVAILABLE:
                self.logger.warning("smbus2 not found, forcing HTU21D into mock mode.")
            self.mock_mode = True

        if self.mock_mode:
            self.logger.info("HTU21D operating in mock mode.")
            self._mock_temperature = 22.5
            self._mock_humidity = 55.0

    def soft_reset(self):
        """Performs a soft reset on the sensor."""
        if self.mock_mode or self.bus is None:
            self.logger.debug("Mock HTU21D: Soft reset simulated.")
            return
        try:
            self.bus.write_byte(self.address, CMD_RESET)
            time.sleep(0.015)
            self.logger.debug("HTU21D soft reset performed.")
        except Exception as e:
            self.logger.error(f"Failed to soft reset HTU21D: {e}")
            raise

    def read_temperature(self):
        """Reads temperature in Celsius."""
        if self.mock_mode:
            self._mock_temperature += random.uniform(-0.5, 0.5)
            return max(15.0, min(35.0, self._mock_temperature))

        if self.bus is None: return None
        try:
            # FIX: Use read_i2c_block_data with the hold command
            data = self.bus.read_i2c_block_data(self.address, CMD_READ_TEMP_HOLD, 3)
            raw_temp = (data[0] << 8) | data[1]
            # CRC check can be added here if needed
            temperature = -46.85 + 175.72 * raw_temp / 65536.0
            return temperature
        except Exception as e:
            self.logger.error(f"Failed to read HTU21D temperature: {e}")
            return None

    def read_humidity(self):
        """Reads relative humidity."""
        if self.mock_mode:
            self._mock_humidity += random.uniform(-1.0, 1.0)
            return max(30.0, min(80.0, self._mock_humidity))

        if self.bus is None: return None
        try:
            # FIX: Use read_i2c_block_data with the hold command
            data = self.bus.read_i2c_block_data(self.address, CMD_READ_HUM_HOLD, 3)
            raw_humid = (data[0] << 8) | data[1]
            # CRC check can be added here if needed
            humidity = -6.0 + 125.0 * raw_humid / 65536.0
            return humidity
        except Exception as e:
            self.logger.error(f"Failed to read HTU21D humidity: {e}")
            return None

    def read_data(self):
        """
        Reads both temperature and humidity from the sensor.
        Returns a dictionary {'temperature': value, 'humidity': value}.
        """
        temp = self.read_temperature()
        humid = self.read_humidity()
        return {'temperature': temp, 'humidity': humid}

    def close(self):
        """Closes the I2C bus connection."""
        if not self.mock_mode and self.bus:
            try:
                self.bus.close()
                self.logger.info("HTU21D I2C bus closed.")
            except Exception as e:
                self.logger.error(f"Error closing HTU21D I2C bus: {e}")
            finally:
                self.bus = None

    def cleanup(self):
        self.close()

    def __del__(self):
        self.cleanup()
