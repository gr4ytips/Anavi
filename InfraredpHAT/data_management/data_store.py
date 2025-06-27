# -*- coding: utf-8 -*-
import collections
import datetime
import time
import logging
import re # Added for regex in time range parsing
from PyQt5.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

class SensorDataStore(QObject):
    """
    Manages the storage and retrieval of sensor data.
    Uses a deque to efficiently store a rolling window of historical data.
    Emits data_updated signal whenever new data is added.
    """
    # Define a signal that will be emitted when new data is added
    # It will carry the newly added sensor_data dictionary
    data_updated = pyqtSignal(dict)

    def __init__(self, max_points=1000):
        """
        Initializes the SensorDataStore.
        :param max_points: The maximum number of data points to store in history.
        """
        super().__init__() # Call the constructor of QObject
        self.max_points = max_points
        self.data_history = collections.deque(maxlen=self.max_points)

        # Store metadata about sensors and their metrics (units, min/max possible values)
        # This will be populated dynamically as data comes in, or can be pre-configured.
        self.metric_info = {
            'HTU21D': {
                'temperature': {'unit': '\u00B0C', 'min': -40.0, 'max': 125.0}, # °C
                'humidity': {'unit': '%', 'min': 0.0, 'max': 100.0}
            },
            'BMP180': {
                'temperature': {'unit': '\u00B0C', 'min': -20.0, 'max': 80.0}, # °C
                'pressure': {'unit': 'hPa', 'min': 300.0, 'max': 1100.0}
            },
            'BH1750': {
                'light': {'unit': 'lx', 'min': 0.0, 'max': 65535.0}
            }
        }
        # Reference to the global thresholds dictionary, managed by MainWindow/SettingsManager
        self.thresholds_reference = {} 
        logger.info(f"SensorDataStore initialized with max_points={max_points}.")

    def set_thresholds_reference(self, thresholds_dict):
        """
        Sets a reference to the global thresholds dictionary.
        This allows the data store to access current thresholds for data retrieval logic (e.g., alert status).
        :param thresholds_dict: A dictionary containing all configured thresholds.
        """
        self.thresholds_reference = thresholds_dict
        logger.debug("SensorDataStore: Thresholds reference set.")

    def get_thresholds(self, sensor_type, metric_type):
        """
        Retrieves the low and high thresholds for a specific sensor metric.
        :param sensor_type: e.g., 'HTU21D'
        :param metric_type: e.g., 'temperature'
        :return: A dictionary {'low': val, 'high': val} or empty dict if not found.
        """
        return self.thresholds_reference.get(sensor_type, {}).get(metric_type, {})

    def add_data(self, sensor_data_snapshot):
        """
        Adds a new snapshot of sensor data to the history.
        :param sensor_data_snapshot: A dictionary containing the timestamp and sensor readings.
                                    Example: {'timestamp': 1678886400000, 'data': {'HTU21D': {'temperature': {'value': 25.1}}}}
        """
        if not isinstance(sensor_data_snapshot, dict) or 'timestamp' not in sensor_data_snapshot or 'data' not in sensor_data_snapshot:
            logger.error(f"SensorDataStore: Invalid sensor_data_snapshot format. Must contain 'timestamp' and 'data' keys. Received: {sensor_data_snapshot}")
            return

        self.data_history.append(sensor_data_snapshot)
        self._infer_units_and_metrics(sensor_data_snapshot['data']) # Infer units on data addition
        self.data_updated.emit(sensor_data_snapshot['data']) # Emit signal with just the 'data' part of the snapshot
        logger.debug(f"SensorDataStore: Added data snapshot with timestamp {sensor_data_snapshot['timestamp']}. History size: {len(self.data_history)}")


    def get_historical_data(self, sensor_type=None, metric_type=None, time_range_str="All Data"):
        """
        Retrieves historical sensor data, filtered by time range, sensor type, and metric type.
        :param sensor_type: Optional filter by sensor category (e.g., 'HTU21D').
        :param metric_type: Optional filter by metric type (e.g., 'temperature').
        :param time_range_str: A string like "Last 10 minutes", "Last 1 hour", "All Data".
        :return: Tuple of (list of datetime objects, list of values)
        """
        logger.debug(f"SensorDataStore: Getting historical data for sensor_type='{sensor_type}', metric_type='{metric_type}' with time range: '{time_range_str}'.")

        start_time_ms = self._get_timestamp_from_time_range_str(time_range_str)
        end_time_ms = int(time.time() * 1000)

        x_data = [] # Timestamps (will be datetime objects for matplotlib)
        y_data = [] # Values

        for entry in reversed(self.data_history):
            record_timestamp = entry.get('timestamp')
            if record_timestamp is None:
                logger.warning("SensorDataStore: Skipping data entry with missing timestamp.")
                continue

            if record_timestamp < start_time_ms:
                break # Stop iterating if outside time range
            if record_timestamp > end_time_ms:
                continue
            
            data_section = entry.get('data', {})
            if sensor_type and sensor_type not in data_section:
                continue
            
            if metric_type:
                if sensor_type and metric_type in data_section.get(sensor_type, {}):
                    value_data = data_section[sensor_type][metric_type]
                    value = value_data.get('value')
                    if value is not None:
                        x_data.append(datetime.datetime.fromtimestamp(record_timestamp / 1000.0))
                        y_data.append(value)
            else:
                # If no specific metric_type, this path is not used by PlotTabWidget for individual series.
                # It's typically used for raw data dumps or other logic.
                # For plotting, we always expect specific sensor_type and metric_type.
                pass 

        return list(reversed(x_data)), list(reversed(y_data))

    def _get_timestamp_from_time_range_str(self, time_range_str):
        """
        Converts a time range string (e.g., "Last 10 minutes") into a Unix timestamp in milliseconds.
        Returns 0 if 'All Data' is specified to indicate no lower bound.
        """
        if time_range_str == "All Data":
            logger.debug("SensorDataStore: '_get_timestamp_from_time_range_str': 'All Data' selected, returning 0 (no cutoff).")
            return 0 

        current_time_ms = int(time.time() * 1000)

        unit_map = {
            "second": 1000, "seconds": 1000,
            "minute": 60 * 1000, "minutes": 60 * 1000,
            "hour": 3600 * 1000, "hours": 3600 * 1000,
            "day": 86400 * 1000, "days": 86400 * 1000
        }

        match = re.match(r"Last (\d+)\s*(second|seconds|minute|minutes|hour|hours|day|days)", time_range_str, re.IGNORECASE)
        if match:
            value = int(match.group(1))
            unit = match.group(2).lower()
            duration_sec = value * unit_map.get(unit, 1)
            
            cutoff_time_ms = current_time_ms - int(duration_sec * 1000)
            logger.debug(f"SensorDataStore: Time range '{time_range_str}' corresponds to cutoff timestamp: {cutoff_time_ms} ms (current: {current_time_ms} ms).")
            return cutoff_time_ms
        
        logger.warning(f"SensorDataStore: Unknown time range format: '{time_range_str}'. Returning 0 (effectively 'All Data').")
        return 0 


    def get_latest_data(self):
        """
        Returns the most recently added data snapshot.
        Returns:
            dict: The latest data snapshot (full entry with 'timestamp' and 'data' keys),
                  or None if no data.
        """
        if not self.data_history:
            logger.debug("SensorDataStore: No data in history to get latest snapshot from.")
            return None
        return self.data_history[-1].get('data') 


    def _infer_units_and_metrics(self, data_snapshot):
        """
        Infers sensor categories, metrics, and units from a data snapshot
        and updates the internal metric_info dictionary.
        """
        for sensor_category, metrics in data_snapshot.items():
            if sensor_category not in self.metric_info:
                self.metric_info[sensor_category] = {}
            for metric_type, metric_data in metrics.items():
                if metric_type not in self.metric_info[sensor_category]:
                    unit = self._get_default_unit(metric_type)
                    self.metric_info[sensor_category][metric_type] = {'unit': unit, 'min': None, 'max': None} # Initialize with None for min/max
                    logger.debug(f"SensorDataStore: Inferred unit for {sensor_category} {metric_type}: {unit}")

    def _get_default_unit(self, metric_type):
        """Helper to return a default unit for common metric types."""
        unit_map = {
            "temperature": "\u00b0C",
            "humidity": "%",
            "pressure": "hPa",
            "light": "lx",
            "co2": "ppm"
        }
        return unit_map.get(metric_type.lower(), "")

    def get_unit(self, sensor_type, metric_type):
        """
        Returns the unit for a given sensor and metric type.
        """
        return self.metric_info.get(sensor_type, {}).get(metric_type, {}).get('unit', "")

    def get_all_available_metrics(self):
        """
        Returns a dictionary of all configured sensor types and their metrics with units.
        Example: {'HTU21D': {'temperature': '°C', 'humidity': '%'}, 'BMP180': {'pressure': 'hPa'}}
        This is crucial for dynamically building the plot lists.
        """
        available_metrics = {}
        for sensor_type, metrics_data in self.metric_info.items():
            # FIX: Ensure we return the nested dictionary of metric_type: unit
            available_metrics[sensor_type] = {
                metric_type: info['unit'] 
                for metric_type, info in metrics_data.items()
            }
        logger.debug(f"SensorDataStore: Retrieved all available metrics: {available_metrics}")
        return available_metrics

    def set_thresholds_reference(self, global_thresholds_dict):
        """
        Sets the reference to the global thresholds dictionary managed by MainWindow.
        This allows the data store to access the latest thresholds when needed
        without owning the update logic for them.
        :param global_thresholds_dict: A reference to the main application's thresholds dictionary.
        """
        self.thresholds = global_thresholds_dict
        logger.info("SensorDataStore: Reference to global thresholds set.")

# Example usage (for testing purposes, if run directly)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    data_store = SensorDataStore(max_points=5)

    # Simple mock data structure mimicking sensor_reader output
    mock_data1 = {
        'timestamp': int(time.time() * 1000),
        'data': {
            'HTU21D': {
                'temperature': {'value': 25.1, 'timestamp': int(time.time() * 1000) - 100},
                'humidity': {'value': 50.2, 'timestamp': int(time.time() * 1000) - 100}
            },
            'BMP180': {
                'pressure': {'value': 1012.5, 'timestamp': int(time.time() * 1000) - 100}
            }
        }
    }
    time.sleep(0.1) # Simulate time passing

    mock_data2 = {
        'timestamp': int(time.time() * 1000),
        'data': {
            'HTU21D': {
                'temperature': {'value': 25.5, 'timestamp': int(time.time() * 1000)},
                'humidity': {'value': 51.0, 'timestamp': int(time.time() * 1000)}
            },
            'BMP180': {
                'pressure': {'value': 1013.0, 'timestamp': int(time.time() * 1000)}
            }
        }
    }
    time.sleep(0.1)

    mock_data3 = {
        'timestamp': int(time.time() * 1000),
        'data': {
            'HTU21D': {
                'temperature': {'value': 26.0, 'timestamp': int(time.time() * 1000)},
                'humidity': {'value': 52.0, 'timestamp': int(time.time() * 1000)}
            },
            'BH1750': { # New sensor introduced
                'light': {'value': 350.0, 'timestamp': int(time.time() * 1000)}
            }
        }
    }

    print("Adding data...")
    data_store.add_data(mock_data1)
    data_store.add_data(mock_data2)
    data_store.add_data(mock_data3)

    print("\n--- All Historical Data ---")
    # Test with time_range_str
    timestamps_all, data_all = data_store.get_historical_data(time_range_str="All Data")
    print("All Data (via time_range_str):")
    if timestamps_all and data_all:
        for i in range(len(timestamps_all)):
            print(f"Timestamp: {timestamps_all[i]}, Data: {data_all[i]}")
    else:
        print("No data retrieved for 'All Data' range.")

    current_time_ms = int(time.time() * 1000)
    
    print(f"\n--- Getting HTU21D Temperature for last 500ms (approx) ---")
    filtered_temp_x, filtered_temp_y = data_store.get_historical_data(
        sensor_type='HTU21D',
        metric_type='temperature',
        time_range_str="Last 5 seconds" # Example of new usage
    )
    print("Filtered HTU21D Temperature:")
    if filtered_temp_x and filtered_temp_y:
        for i in range(len(filtered_temp_x)):
            print(f"Timestamp: {filtered_temp_x[i]}, Value: {filtered_temp_y[i]}")
    else:
        print("No filtered HTU21D temperature data.")


    print("\n--- Getting all available metrics (corrected output) ---")
    all_metrics = data_store.get_all_available_metrics()
    print(all_metrics)

    print("\n--- Getting unit for HTU21D temperature ---")
    print(data_store.get_unit('HTU21D', 'temperature'))

    print("\n--- Testing latest data ---")
    # Get the latest full snapshot, then extract specific sensor data
    latest_snapshot = data_store.get_latest_data() 
    if latest_snapshot:
        latest_htu21d_data = latest_snapshot.get('HTU21D', {})
        print(f"Latest HTU21D data: {latest_htu21d_data}")

        latest_bmp180_data = latest_snapshot.get('BMP180', {})
        print(f"Latest BMP180 data: {latest_bmp180_data}")
    else:
        print("No latest data available.")

