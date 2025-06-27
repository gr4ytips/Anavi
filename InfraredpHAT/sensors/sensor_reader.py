# sensors/sensor_reader.py
import logging
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, QEventLoop, QMetaObject, Qt, pyqtSlot 

import time
import os 

# Import mock sensors
from sensors.mock_sensors import MockHTU21D, MockBMP180, MockBH1750

# Conditional import for real sensors
REAL_SENSORS_AVAILABLE = False
try:
    from sensors.htu21d_sensor import HTU21D
    from sensors.bmp180_sensor import BMP180
    from sensors.bh1750_sensor import BH1750
    REAL_SENSORS_AVAILABLE = True
    logging.info("SensorReaderThread: Real sensor modules imported successfully.")
except ImportError as e:
    logging.error(f"SensorReaderThread: CRITICAL: Could not import one or more real sensor modules. Ensure they are in the 'sensors' directory and all their dependencies (e.g., smbus, RPi.GPIO if applicable) are installed. Error: {e}", exc_info=True)
except Exception as e:
    logging.error(f"SensorReaderThread: CRITICAL: An unexpected error occurred during real sensor module import. Error: {e}", exc_info=True)
finally:
    if not REAL_SENSORS_AVAILABLE:
        logging.warning("SensorReaderThread: REAL_SENSORS_AVAILABLE is False. Only mock mode will be available, regardless of config.ini setting.")


class SensorReaderThread(QThread):
    """
    A QThread to read sensor data periodically without blocking the UI.
    It manages the instantiation of either mock or real sensor drivers
    and emits a signal with the latest sensor data.
    Includes robust error handling and fallback to mock data for real sensors.
    """
    data_ready = pyqtSignal(dict) # Emits the structured sensor data dictionary
    sensor_status_update = pyqtSignal(str, str) # Emits status messages (message, type)

    def __init__(self, settings_manager, parent=None): # Changed to accept settings_manager
        """
        Initializes the SensorReaderThread.
        :param settings_manager: An instance of SettingsManager to retrieve config.
        :param parent: Parent QObject.
        """
        logging.debug(f"SensorReaderThread: __init__ entered. Object ID: {id(self)}")
        super().__init__(parent)
        self.settings_manager = settings_manager # Store reference to settings_manager
        
        self.running = False # Flag to control the thread's event loop
        self._timer = None # QTimer for periodic reads
        self._event_loop = None # QEventLoop for the thread

        # Sensor instances
        self.htu21d_sensor = None
        self.bmp180_sensor = None
        self.bh1750_sensor = None
        
        # Load initial settings from settings manager
        self.read_interval_ms = self.settings_manager.get_setting('General', 'sampling_rate_ms', type=int)
        self.mock_mode = self.settings_manager.get_setting('General', 'mock_mode', type=bool)
        
        # Determine actual mode based on availability of real sensors
        self.mock_mode_active = self.mock_mode or not REAL_SENSORS_AVAILABLE
        if self.mock_mode_active and not self.mock_mode: # If mock_mode_active is true because real sensors are not available
            logging.warning("SensorReaderThread: Forcing mock mode active due to unavailability of real sensor modules, despite config setting.")

        logging.info(f"SensorReaderThread: Initialized with read_interval_ms={self.read_interval_ms}, mock_mode_active={self.mock_mode_active}. Object ID: {id(self)}")

        # Connect to settings_updated signal from SettingsManager
        self.settings_manager.settings_updated.connect(self._on_settings_updated)
        logging.debug(f"SensorReaderThread: Connected to settings_manager.settings_updated signal. Object ID: {id(self)}")


    @pyqtSlot(str, str, object)
    def _on_settings_updated(self, section, key, value):
        """
        Slot to receive updates from SettingsManager.
        This slot needs to run in the main thread (where SettingsManager lives).
        We then invoke a method in the worker thread to apply changes safely.
        """
        logging.debug(f"SensorReaderThread: Received settings update: section={section}, key={key}, value={value}. Object ID: {id(self)}")
        if section == 'General':
            if key == 'sampling_rate_ms':
                new_sampling_rate_ms = value # Value is already converted to int by SettingsManager
                # Invoke method on this thread's object to update timer safely
                QMetaObject.invokeMethod(self, "update_settings", Qt.QueuedConnection, 
                                         new_sampling_rate_ms, self.mock_mode) # FIX: Removed pyqtSlot wrapper
            elif key == 'mock_mode':
                new_mock_mode = value # Value is already converted to bool by SettingsManager
                QMetaObject.invokeMethod(self, "update_settings", Qt.QueuedConnection, 
                                         self.read_interval_ms, new_mock_mode) # FIX: Removed pyqtSlot wrapper

    @pyqtSlot(int, bool)
    def update_settings(self, new_sampling_rate_ms, new_mock_mode):
        """
        This method runs in the SensorReaderThread's context.
        Applies new settings for sampling rate and mock mode.
        """
        logging.info(f"SensorReaderThread: update_settings called (via QMetaObject.invokeMethod). New interval: {new_sampling_rate_ms}ms, New mock mode: {new_mock_mode}. Object ID: {id(self)}")
        
        old_mock_mode = self.mock_mode # Store old value for comparison
        self.read_interval_ms = new_sampling_rate_ms
        self.mock_mode = new_mock_mode

        # If mock mode has changed, re-initialize sensors (which will handle switching to/from mock)
        if old_mock_mode != self.mock_mode:
            logging.info(f"SensorReaderThread: Mock mode setting changed from {old_mock_mode} to {self.mock_mode}. Re-initializing sensors.")
            self.mock_mode_active = self.mock_mode or not REAL_SENSORS_AVAILABLE # Recalculate active state
            self._initialize_sensors() # This will update self.mock_mode_active internally

        # Update timer interval
        if self._timer:
            self._timer.setInterval(self.read_interval_ms)
            logging.info(f"SensorReaderThread: Timer interval updated to {self.read_interval_ms} ms. Object ID: {id(self)}")
            # Ensure timer is active after settings update, especially if it was previously stopped
            if not self._timer.isActive() and self.running:
                self._timer.start()
                logging.info(f"SensorReaderThread: Timer started after settings update. Object ID: {id(self)}")
        else:
            logging.error(f"SensorReaderThread: Timer object is None in update_settings. Cannot apply interval. Object ID: {id(self)}")

        logging.info(f"SensorReaderThread: Settings update processed. Object ID: {id(self)}")


    def run(self):
        """
        The main event loop for the QThread.
        Initializes sensors and starts the QTimer.
        """
        logging.info(f"SensorReaderThread: run() method started. Object ID: {id(self)}")
        self.running = True
        
        self._initialize_sensors() # Initialize sensors when thread starts
        
        self._timer = QTimer()
        self._timer.moveToThread(self) # IMPORTANT: Move timer to THIS thread
        self._timer.timeout.connect(self._read_sensors)
        self._timer.start(self.read_interval_ms)
        logging.info(f"SensorReaderThread: QTimer started with interval {self.read_interval_ms} ms. Object ID: {id(self)}")

        self._event_loop = QEventLoop()
        # Connect finished signal to quit event loop if something external stops it
        self.finished.connect(self._event_loop.quit) 
        self._event_loop.exec_() # Start the event loop for the thread

        logging.info(f"SensorReaderThread: Event loop finished. Object ID: {id(self)}")
        self.cleanup_on_finish() # Perform cleanup when loop exits

    def _initialize_sensors(self):
        """
        Initializes real or mock sensor instances based on `self.mock_mode_active`.
        This method can be called multiple times to switch modes or re-initialize.
        """
        logging.info(f"SensorReaderThread: Initializing sensors (mock_mode_active: {self.mock_mode_active}). Object ID: {id(self)}")
        
        # Close existing connections before re-initializing
        self._close_sensor_connections()

        if self.mock_mode_active:
            self.htu21d_sensor = MockHTU21D()
            self.bmp180_sensor = MockBMP180()
            self.bh1750_sensor = MockBH1750()
            logging.info("SensorReaderThread: Mock sensors initialized.")
            self.sensor_status_update.emit("Running in Mock Mode. Real sensors not detected or disabled.", "warning")
        elif REAL_SENSORS_AVAILABLE:
            try:
                self.htu21d_sensor = HTU21D()
                self.bmp180_sensor = BMP180()
                self.bh1750_sensor = BH1750()
                logging.info("SensorReaderThread: Real sensors initialized.")
                self.sensor_status_update.emit("Running with Real Sensors.", "info")
            except Exception as e:
                logging.error(f"SensorReaderThread: Failed to initialize real sensors: {e}. Falling back to mock mode.", exc_info=True)
                self.sensor_status_update.emit(f"Failed to initialize real sensors: {e}. Falling back to mock mode.", "error")
                # Fallback to mock mode if real sensor initialization fails
                self.mock_mode_active = True
                self.htu21d_sensor = MockHTU21D()
                self.bmp180_sensor = MockBMP180()
                self.bh1750_sensor = MockBH1750()
                logging.info("SensorReaderThread: Fallback to mock sensors initialized.")
        else:
            logging.warning("SensorReaderThread: REAL_SENSORS_AVAILABLE is False, but mock_mode_active is False. This state should not happen. Forcing mock mode.")
            self.mock_mode_active = True
            self.htu21d_sensor = MockHTU21D()
            self.bmp180_sensor = MockBMP180()
            self.bh1750_sensor = MockBH1750()
            self.sensor_status_update.emit("Forcing mock mode. Real sensors not available.", "error")

    def _read_sensors(self):
        """
        Reads data from all initialized sensors and emits the data_ready signal.
        Handles errors gracefully and emits status updates.
        """
        # logging.debug(f"SensorReaderThread: _read_sensors triggered. Object ID: {id(self)}") # Too verbose, only enable if needed
        sensor_data_snapshot = {
            'timestamp': int(time.time() * 1000), # Timestamp for the entire snapshot
            'data': {} # Nested dictionary for sensor data
        }
        
        if self.htu21d_sensor:
            try:
                htu21d_values = self.htu21d_sensor.read_data()
                if htu21d_values:
                    # Add individual timestamps to each metric's data
                    htu21d_processed = {k: {'value': v, 'timestamp': int(time.time() * 1000)} for k, v in htu21d_values.items()}
                    sensor_data_snapshot['data']['HTU21D'] = htu21d_processed
                    self.sensor_status_update.emit("HTU21D: OK", "info")
            except Exception as e:
                logging.error(f"SensorReaderThread: Error reading HTU21D data: {e}", exc_info=True)
                self.sensor_status_update.emit(f"HTU21D: Error reading data - {str(e)}", "error")
                # Provide mock data as fallback if real sensor read fails
                if not self.mock_mode_active: # Only if we were trying to read real
                    mock_htu = MockHTU21D()
                    htu21d_values = mock_htu.read_data()
                    htu21d_processed = {k: {'value': v, 'timestamp': int(time.time() * 1000)} for k, v in htu21d_values.items()}
                    sensor_data_snapshot['data']['HTU21D'] = htu21d_processed
                    self.sensor_status_update.emit("HTU21D: Reading failed, providing mock data.", "warning")
                else: # If we are already in mock mode, ensure it's still available
                    self.sensor_status_update.emit("HTU21D: Mock sensor not providing data.", "error")


        if self.bmp180_sensor:
            try:
                bmp180_values = self.bmp180_sensor.read_data()
                if bmp180_values:
                    bmp180_processed = {k: {'value': v, 'timestamp': int(time.time() * 1000)} for k, v in bmp180_values.items()}
                    sensor_data_snapshot['data']['BMP180'] = bmp180_processed
                    self.sensor_status_update.emit("BMP180: OK", "info")
            except Exception as e:
                logging.error(f"SensorReaderThread: Error reading BMP180 data: {e}", exc_info=True)
                self.sensor_status_update.emit(f"BMP180: Error reading data - {str(e)}", "error")
                if not self.mock_mode_active:
                    mock_bmp = MockBMP180()
                    bmp180_values = mock_bmp.read_data()
                    bmp180_processed = {k: {'value': v, 'timestamp': int(time.time() * 1000)} for k, v in bmp180_values.items()}
                    sensor_data_snapshot['data']['BMP180'] = bmp180_processed
                    self.sensor_status_update.emit("BMP180: Reading failed, providing mock data.", "warning")
                else:
                    self.sensor_status_update.emit("BMP180: Mock sensor not providing data.", "error")

        if self.bh1750_sensor:
            try:
                bh1750_values = self.bh1750_sensor.read_data()
                if bh1750_values:
                    bh1750_processed = {k: {'value': v, 'timestamp': int(time.time() * 1000)} for k, v in bh1750_values.items()}
                    sensor_data_snapshot['data']['BH1750'] = bh1750_processed
                    self.sensor_status_update.emit("BH1750: OK", "info")
            except Exception as e:
                logging.error(f"SensorReaderThread: Error reading BH1750 data: {e}", exc_info=True)
                self.sensor_status_update.emit(f"BH1750: Error reading data - {str(e)}", "error")
                if not self.mock_mode_active:
                    mock_bh = MockBH1750()
                    bh1750_values = mock_bh.read_data()
                    bh1750_processed = {k: {'value': v, 'timestamp': int(time.time() * 1000)} for k, v in bh1750_values.items()}
                    sensor_data_snapshot['data']['BH1750'] = bh1750_processed
                    self.sensor_status_update.emit("BH1750: Reading failed, providing mock data.", "warning")
                else:
                    self.sensor_status_update.emit("BH1750: Mock sensor not providing data.", "error")

        if sensor_data_snapshot['data']: # Only emit if there's actual data
            self.data_ready.emit(sensor_data_snapshot) # Emit the full snapshot
            logging.debug(f"SensorReaderThread: data_ready signal emitted for snapshot timestamp {sensor_data_snapshot['timestamp']} with data for sensors: {list(sensor_data_snapshot['data'].keys())}")
        else:
            logging.warning("SensorReaderThread: No sensor data collected in this cycle. Skipping data_ready emit.")


    def stop(self):
        """
        Stops the sensor reading thread gracefully.
        This method is called from the main thread.
        """
        logging.info(f"SensorReaderThread: stop() called. Object ID: {id(self)}")
        self.running = False
        if self._timer:
            self._timer.stop() # Stop the timer
            logging.info(f"SensorReaderThread: QTimer stopped. Object ID: {id(self)}")
        # If the event loop is running, quit it. This will make run() exit.
        if self._event_loop and self._event_loop.isRunning():
            self._event_loop.quit()
            logging.info(f"SensorReaderThread: Event loop quit requested. Object ID: {id(self)}")
        # Disconnect signals to prevent lingering connections if thread object is reused/deleted later
        try:
            self.settings_manager.settings_updated.disconnect(self._on_settings_updated)
            logging.debug(f"SensorReaderThread: settings_updated signal disconnected. Object ID: {id(self)}")
        except TypeError: # Signal not connected
            pass
        
        # Disconnect internal signals for data_ready and sensor_status_update to prevent issues during cleanup
        try:
            self.data_ready.disconnect()
            logging.debug(f"SensorReaderThread: data_ready signal disconnected. Object ID: {id(self)}")
        except TypeError:
            pass # Signal not connected
        try:
            self.sensor_status_update.disconnect()
            logging.debug(f"SensorReaderThread: sensor_status_update signal disconnected. Object ID: {id(self)}")
        except TypeError:
            pass # Signal not connected

        logging.info(f"SensorReaderThread: stop() method finished. Object ID: {id(self)}")


    def _close_sensor_connections(self):
        """Closes connections for real sensors if they have a 'close' method."""
        logging.info(f"SensorReaderThread: Closing sensor connections... Object ID: {id(self)}")
        sensors = [self.htu21d_sensor, self.bmp180_sensor, self.bh1750_sensor]
        for sensor in sensors:
            if hasattr(sensor, 'close') and callable(sensor.close):
                try:
                    sensor.close()
                    logging.info(f"SensorReaderThread: Closed connection for {sensor.__class__.__name__}. Object ID: {id(self)}")
                except Exception as e:
                    logging.error(f"SensorReaderThread: Error closing sensor {sensor.__class__.__name__}: {e}", exc_info=True)
            elif sensor:
                logging.debug(f"SensorReaderThread: Sensor {sensor.__class__.__name__} has no 'close' method or is not callable or is None; skipping close. Object ID: {id(self)}")
        
        # Reset sensor instances to None
        self.htu21d_sensor = None
        self.bmp180_sensor = None
        self.bh1750_sensor = None
        logging.info(f"SensorReaderThread: All relevant sensor connections released. Object ID: {id(self)}")


    def cleanup_on_finish(self):
        """
        Performs final cleanup when the thread's event loop exits.
        """
        logging.info(f"SensorReaderThread: Thread finished. Performing cleanup. Object ID: {id(self)}")
        self._close_sensor_connections()
        self._timer = None # Dereference the timer
        self._event_loop = None # Dereference the event loop
        logging.debug(f"SensorReaderThread: cleanup_on_finish completed. Object ID: {id(self)}")

