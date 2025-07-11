# -*- coding: utf-8 -*-
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, QDateTime, QObject, pyqtSlot
import time
import logging
import random
from collections import deque

# Import the actual sensor classes
from sensors.htu21d_sensor import HTU21D
from sensors.bmp180_sensor import BMP180
from sensors.bh1750_sensor import BH1750

logger = logging.getLogger(__name__)

class SensorReaderThread(QObject):
    """
    A QObject subclass to read sensor data in a separate thread.
    It discovers available sensors on initialization and continuously
    reads data from them, emitting signals with the results.
    """
    data_ready = pyqtSignal(dict)
    sensors_discovered = pyqtSignal(dict)
    finished = pyqtSignal()

    def __init__(self, data_store, mock_mode=False, sampling_rate_ms=5000, sensor_config=None, parent=None):
        super().__init__(parent)
        self.data_store = data_store
        self._running = False
        self._mock_mode = mock_mode
        self._sampling_rate_ms = sampling_rate_ms
        self._sensor_config = sensor_config if sensor_config is not None else {}
        
        self.sensor_instances = {}
        self._initialize_sensors()
        logger.info(f"SensorReaderThread initialized. Mock Mode: {self._mock_mode}, Sampling Rate: {self._sampling_rate_ms}ms.")

    def _initialize_sensors(self):
        """
        Initializes hardware sensors based on the configuration.
        This method attempts to create an instance of each potential sensor.
        The sensor's own __init__ method will handle hardware detection and
        fallback to its internal mock mode if the hardware is not found.
        """
        logger.info("SensorReader: Initializing and discovering sensors...")
        
        discovered = {}
        
        # Attempt to initialize HTU21D
        if 'HTU21D' in self._sensor_config:
            try:
                htu_sensor = HTU21D(mock_mode=self._mock_mode)
                self.sensor_instances['HTU21D'] = htu_sensor
                if not htu_sensor.mock_mode:
                    discovered['HTU21D'] = list(self.data_store.get_all_available_metrics().get('HTU21D', {}).keys())
                    logger.info("HTU21D sensor discovered and initialized.")
                else:
                    logger.info("HTU21D sensor initialized in MOCK mode.")
            except Exception as e:
                logger.error(f"Failed to initialize HTU21D sensor: {e}", exc_info=True)

        # Attempt to initialize BMP180
        if 'BMP180' in self._sensor_config:
            try:
                bmp_sensor = BMP180(mock_mode=self._mock_mode)
                self.sensor_instances['BMP180'] = bmp_sensor
                if not bmp_sensor.mock_mode:
                    discovered['BMP180'] = list(self.data_store.get_all_available_metrics().get('BMP180', {}).keys())
                    logger.info("BMP180 sensor discovered and initialized.")
                else:
                    logger.info("BMP180 sensor initialized in MOCK mode.")
            except Exception as e:
                logger.error(f"Failed to initialize BMP180 sensor: {e}", exc_info=True)

        # Attempt to initialize BH1750
        if 'BH1750' in self._sensor_config:
            try:
                bh_sensor = BH1750(mock_mode=self._mock_mode)
                self.sensor_instances['BH1750'] = bh_sensor
                if not bh_sensor.mock_mode:
                    discovered['BH1750'] = list(self.data_store.get_all_available_metrics().get('BH1750', {}).keys())
                    logger.info("BH1750 sensor discovered and initialized.")
                else:
                    logger.info("BH1750 sensor initialized in MOCK mode.")
            except Exception as e:
                logger.error(f"Failed to initialize BH1750 sensor: {e}", exc_info=True)

        self.sensors_discovered.emit(discovered)
        logger.info(f"Sensor discovery complete. Real sensors found: {list(discovered.keys())}")

    @pyqtSlot()
    def run(self):
        """
        The main loop of the thread where sensor data is continuously read.
        """
        self._running = True
        logger.info("SensorReaderThread: Starting data reading loop.")
        while self._running:
            start_time = time.time()
            
            sensor_data_snapshot = {
                'timestamp': int(QDateTime.currentMSecsSinceEpoch()),
                'data': {}
            }

            for sensor_type, sensor_instance in self.sensor_instances.items():
                if sensor_type in self._sensor_config:
                    # The read_data method in each sensor class handles both real and mock reading
                    data = sensor_instance.read_data()
                    if data:
                        sensor_data_snapshot['data'][sensor_type] = {}
                        for metric_type, value in data.items():
                            sensor_data_snapshot['data'][sensor_type][metric_type] = {
                                'value': value,
                                'is_alert': False # Alert status is determined later
                            }
            
            if sensor_data_snapshot['data']:
                self.data_ready.emit(sensor_data_snapshot)
            
            elapsed_time_ms = (time.time() - start_time) * 1000
            sleep_time_ms = self._sampling_rate_ms - elapsed_time_ms
            if sleep_time_ms > 0:
                QThread.msleep(int(sleep_time_ms))
        
        self._cleanup_sensors()
        self.finished.emit()
        logger.info("SensorReaderThread: Data reading loop stopped and finished.")

    def stop(self):
        """Stops the sensor reading thread gracefully."""
        logger.info("SensorReaderThread: stop() method called.")
        self._running = False

    def _cleanup_sensors(self):
        """Closes sensor connections."""
        logger.info("SensorReaderThread: Cleaning up sensor connections.")
        for sensor_instance in self.sensor_instances.values():
            if hasattr(sensor_instance, 'close'):
                sensor_instance.close()
        logger.info("SensorReaderThread: Cleanup complete.")

    def set_mock_mode(self, enabled):
        """Sets the mock mode for the sensor reader."""
        if self._mock_mode != enabled:
            self._mock_mode = enabled
            logger.info(f"SensorReaderThread: Mock mode set to {self._mock_mode}. Re-initializing sensors.")
            self._cleanup_sensors()
            self._initialize_sensors()

    def set_sampling_rate(self, rate_ms):
        """Sets the sampling rate for the sensor reader."""
        self._sampling_rate_ms = rate_ms
        logger.info(f"SensorReaderThread: Sampling rate set to {self._sampling_rate_ms} ms.")
