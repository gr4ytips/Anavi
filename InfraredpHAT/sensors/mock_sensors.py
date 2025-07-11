# sensors/mock_sensors.py
import random
import time
import logging

logger = logging.getLogger(__name__)

class MockHTU21D:
    """Mock sensor for HTU21D (Temperature & Humidity)."""
    def __init__(self):
        logger.info("MockHTU21D initialized.")
        self.last_temp = 25.0
        self.last_humidity = 50.0

    def read_data(self):
        """Generates mock temperature and humidity data with slight variations."""
        # Simulate slight fluctuations
        temp = self.last_temp + random.uniform(-0.5, 0.5)
        humidity = self.last_humidity + random.uniform(-1.0, 1.0)

        # Clamp values to reasonable ranges
        temp = max(15.0, min(35.0, temp))
        humidity = max(30.0, min(80.0, humidity))

        self.last_temp = temp
        self.last_humidity = humidity
        
        logger.debug("Mock HTU21D - Temp: {:.2f}°C, Humidity: {:.2f}%".format(temp, humidity))
        return {'temperature': temp, 'humidity': humidity}

class MockBMP180:
    """Mock sensor for BMP180 (Temperature & Barometric Pressure)."""
    def __init__(self):
        logger.info("MockBMP180 initialized.")
        self.last_temp = 25.0
        self.last_pressure = 1010.0

    def read_data(self):
        """Generates mock temperature and pressure data with slight variations."""
        # Simulate slight fluctuations
        temp = self.last_temp + random.uniform(-0.5, 0.5)
        pressure = self.last_pressure + random.uniform(-2.0, 2.0)

        # Clamp values
        temp = max(15.0, min(35.0, temp))
        pressure = max(950.0, min(1050.0, pressure))

        self.last_temp = temp
        self.last_pressure = pressure

        logger.debug("Mock BMP180 - Temp: {:.2f}°C, Pressure: {:.2f}hPa".format(temp, pressure))
        return {'temperature': temp, 'pressure': pressure}

class MockBH1750:
    """Mock sensor for BH1750 (Light)."""
    def __init__(self):
        logger.info("MockBH1750 initialized.")
        self.last_light = 00.0

    def read_data(self):
        """Generates mock light data with slight variations."""
        # Simulate slight fluctuations
        light = self.last_light + random.uniform(-10.0, 10.0)

        # Clamp values
        light = max(0.0, min(1000.0, light)) # Lumens typically from 0 to 1000+

        self.last_light = light

        logger.debug("Mock BH1750 - Light: {:.2f}lx".format(light))
        return {'light': light}

