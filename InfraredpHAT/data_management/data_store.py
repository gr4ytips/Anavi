# data_management/data_store.py
# -*- coding: utf-8 -*-
import datetime
import random
import collections
import logging
import re
from PyQt5.QtCore import pyqtSignal, QObject, pyqtSlot, QDateTime

logger = logging.getLogger(__name__)

# MOCK_SENSORS is now only used as a fallback or for defining metric properties
MOCK_SENSORS = {
    "HTU21D": {
        "temperature": {"unit": "°C", "min": 15.0, "max": 35.0},
        "humidity": {"unit": "%", "min": 30.0, "max": 90.0}
    },
    "BMP180": {
        "temperature": {"unit": "°C", "min": 10.0, "max": 40.0},
        "pressure": {"unit": "hPa", "min": 900.0, "max": 1100.0},
        "altitude": {"unit": "m", "min": -100.0, "max": 1000.0}
    },
    "BH1750": {
        "light": {"unit": "lx", "min": 0.0, "max": 10000.0}
    }
}


# FIX: Inherit from QObject to allow this class to have signals and slots.
class SensorDataStore(QObject):
    """
    Manages the storage and retrieval of sensor data.
    Receives data from a reader thread and signals UI for updates.
    """
    # FIX: Define signals directly in the class
    data_updated = pyqtSignal(dict)
    sensors_discovered = pyqtSignal(dict)

    def __init__(self, settings_manager, parent=None):
        """
        Initializes the data store.
        :param settings_manager: An instance of SettingsManager to access configurations.
        """
        # FIX: Call the parent constructor
        super().__init__(parent)
        
        self.settings_manager = settings_manager
        self.max_points = self.settings_manager.get_int_setting('General', 'data_store_max_points', fallback=1000)
        self.data_history = collections.deque(maxlen=self.max_points)
        self.latest_data = {}
        self.available_sensors = {}
        self.metric_info = self._initialize_metric_info()
        # The nested Signals class is no longer needed.

        logger.info(f"SensorDataStore initialized. Max data points: {self.max_points}")

    def _initialize_metric_info(self):
        """
        Initializes the metric_info dictionary from MOCK_SENSORS.
        This serves as a master list of all *possible* metrics and their properties.
        """
        info = collections.defaultdict(dict)
        for sensor_type, metrics in MOCK_SENSORS.items():
            for metric_type, details in metrics.items():
                info[sensor_type][metric_type] = details
        logger.debug(f"Metric info initialized: {info}")
        return info

    @pyqtSlot(dict)
    def add_data(self, data_snapshot):
        """
        Adds a new sensor data snapshot to the history.
        This is the primary slot for receiving data from the sensor reader thread.
        """
        timestamp = QDateTime.fromMSecsSinceEpoch(data_snapshot['timestamp']).toPyDateTime()
        
        formatted_snapshot = {
            'timestamp': timestamp,
            'sensors': {}
        }
        for sensor_type, metrics in data_snapshot['data'].items():
            formatted_snapshot['sensors'][sensor_type] = {}
            for metric_type, details in metrics.items():
                formatted_snapshot['sensors'][sensor_type][metric_type] = details['value']
        
        self.data_history.append(formatted_snapshot)
        self.latest_data = formatted_snapshot
        self.data_updated.emit(formatted_snapshot) # Use the class's signal
        logger.debug(f"Sensor data added and updated: {timestamp.strftime('%H:%M:%S')}")

    @pyqtSlot(dict)
    def update_available_sensors(self, discovered_sensors):
        """
        Updates the list of available sensors based on what the reader thread found.
        """
        self.available_sensors = discovered_sensors
        logger.info(f"DataStore: Discovered sensors updated: {self.available_sensors}")
        self.sensors_discovered.emit(self.available_sensors) # Use the class's signal

    def get_latest_data(self):
        """Returns the most recent sensor data snapshot."""
        return self.latest_data

    def get_data_history(self, time_range=None, start_time=None, end_time=None):
        """
        Returns a filtered subset of the data history based on a time range string or start/end datetimes.
        """
        if start_time and end_time:
            return [data for data in self.data_history if start_time <= data['timestamp'] <= end_time]

        if not time_range or time_range == "All History":
            return list(self.data_history)

        now = datetime.datetime.now()
        time_delta = None
        
        match = re.match(r'Last (\d+) (minute|minutes|hour|hours|day|days)', time_range, re.IGNORECASE)
        if match:
            value = int(match.group(1))
            unit = match.group(2).lower()
            if 'minute' in unit:
                time_delta = datetime.timedelta(minutes=value)
            elif 'hour' in unit:
                time_delta = datetime.timedelta(hours=value)
            elif 'day' in unit:
                time_delta = datetime.timedelta(days=value)
        
        if time_delta:
            cutoff_time = now - time_delta
            filtered_history = [data for data in self.data_history if data['timestamp'] >= cutoff_time]
            logger.debug(f"Filtered data history for '{time_range}'. {len(filtered_history)} points retained.")
            return filtered_history

        logger.warning(f"Unknown time range format: '{time_range}'. Returning all data history.")
        return list(self.data_history)

    def get_available_time_ranges(self):
        """
        Returns a list of predefined time range strings for plot filtering.
        """
        return [
            "Last 10 minutes",
            "Last 30 minutes",
            "Last 1 hour",
            "Last 3 hours",
            "Last 6 hours",
            "Last 12 hours",
            "Last 24 hours",
            "All History"
        ]

    def get_all_available_metrics(self):
        """
        Returns the entire metric_info dictionary, which contains details
        (units, min/max) for all known sensor types and their metrics.
        """
        return self.metric_info
        
    def get_unit(self, sensor_type, metric_type):
        """
        Retrieves the unit for a given sensor metric from the internally stored metric_info.
        """
        unit = self.metric_info.get(sensor_type.upper(), {}).get(metric_type.lower(), {}).get('unit')
        if unit is None:
            logger.warning(f"DataStore: Unit not found for {sensor_type}-{metric_type}. Returning empty string.")
            return ""
        return unit
    
    def get_metric_min_max(self, sensor_type, metric_type):
        """
        Retrieves the min and max values for a given sensor metric.
        """
        info = self.metric_info.get(sensor_type.upper(), {}).get(metric_type.lower(), {})
        return info.get('min'), info.get('max')

    def cleanup(self):
        """Performs any necessary cleanup for the data store."""
        logger.info("SensorDataStore cleaned up.")
