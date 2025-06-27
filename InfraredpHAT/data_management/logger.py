# -*- coding: utf-8 -*-
import logging
import os
import datetime
import shutil
import time # For time.time()

logger = logging.getLogger(__name__)

class SensorLogger:
    """
    Manages logging of sensor data to a CSV file, with daily rotation and archiving.
    It ensures that logging occurs in a structured way and old logs are managed.
    """
    def __init__(self, log_directory='Sensor_Logs', archive_directory='Archive_Sensor_Logs',
                 max_file_size_mb=10, max_rotations=5):
        """
        Initializes the SensorLogger.
        :param log_directory: Directory to store current day's log files.
        :param archive_directory: Directory to move older, rotated log files.
        :param max_file_size_mb: Maximum size of a single CSV file before rotation (in MB).
        :param max_rotations: Maximum number of rotated files to keep for the current day.
        """
        self.log_directory = log_directory
        self.archive_directory = archive_directory
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.max_rotations = max_rotations
        self.current_log_file = None
        self.current_file_path = None
        self.current_date = None
        self.rotation_count = 0 # Keeps track of rotations for the current day
        self.log_file_handle = None # File handle for the CSV writer

        self._ensure_log_directories()
        self._check_for_date_change() # Initial check for date change and file opening
        logger.info("SensorLogger initialized. Log directory: %s", self.log_directory)

    def _ensure_log_directories(self):
        """Ensures the log and archive directories exist."""
        os.makedirs(self.log_directory, exist_ok=True)
        os.makedirs(self.archive_directory, exist_ok=True)
        logger.debug(f"SensorLogger: Ensured log directory '{self.log_directory}' and archive directory '{self.archive_directory}' exist.")

    def _get_log_filename(self, rotation_index=0):
        """Generates the log filename based on the current date and rotation index."""
        date_str = datetime.datetime.now().strftime('%Y-%m-%d')
        if rotation_index == 0:
            return f"sensor_log_{date_str}.csv"
        return f"sensor_log_{date_str}_part{rotation_index}.csv"

    def _open_log_file(self):
        """Opens the current log file, creating it with headers if it's new."""
        if self.log_file_handle:
            self.log_file_handle.close() # Close any existing handle
            logger.debug("SensorLogger: Closed previous log file handle before opening a new one.")

        self.current_log_file = self._get_log_filename(self.rotation_count)
        self.current_file_path = os.path.join(self.log_directory, self.current_log_file)
        
        write_header = not os.path.exists(self.current_file_path) or os.path.getsize(self.current_file_path) == 0
        
        try:
            self.log_file_handle = open(self.current_file_path, 'a', buffering=1) # Line-buffered for immediate writes
            logger.info(f"SensorLogger: Opened log file: {self.current_file_path} in mode 'a'.")
            if write_header:
                self.log_file_handle.write("Timestamp (ms),Sensor,Metric,Value,Unit,Alert\n")
                logger.info(f"SensorLogger: Wrote header to {self.current_file_path}.")
        except IOError as e:
            logger.error(f"SensorLogger: Could not open log file '{self.current_file_path}': {e}", exc_info=True)
            self.log_file_handle = None # Ensure handle is None if opening failed

    def _check_for_date_change(self):
        """
        Checks if the date has changed and performs daily log rotation if needed.
        Also handles initial file opening on startup.
        """
        today_date = datetime.date.today()
        if self.current_date is None or self.current_date != today_date:
            logger.debug(f"SensorLogger: Date changed from {self.current_date} to {today_date}. Performing daily rotation and reset.")
            if self.current_date is not None: # If not the very first startup
                self._archive_old_logs(self.current_date)
            self.current_date = today_date
            self.rotation_count = 0 # Reset rotation count for the new day
            self._open_log_file()
        else:
            logger.debug(f"SensorLogger: Date is still {today_date}. No daily rotation needed.")

    def _archive_old_logs(self, date_to_archive):
        """
        Archives all log files for a given date from the log directory to the archive directory.
        """
        archive_subdir = os.path.join(self.archive_directory, date_to_archive.strftime('%Y-%m-%d'))
        os.makedirs(archive_subdir, exist_ok=True)
        
        for filename in os.listdir(self.log_directory):
            if filename.startswith(f"sensor_log_{date_to_archive.strftime('%Y-%m-%d')}") and filename.endswith('.csv'):
                src_path = os.path.join(self.log_directory, filename)
                dest_path = os.path.join(archive_subdir, filename)
                try:
                    shutil.move(src_path, dest_path)
                    logger.info(f"SensorLogger: Archived {filename} to {archive_subdir}.")
                except IOError as e:
                    logger.error(f"SensorLogger: Failed to archive '{src_path}' to '{dest_path}': {e}")

    def _check_and_rotate_file(self):
        """
        Checks current file size and rotates the log file if it exceeds max_file_size_mb.
        Also manages max_rotations for the current day.
        """
        if self.current_file_path and os.path.exists(self.current_file_path) and self.log_file_handle:
            current_size = os.path.getsize(self.current_file_path)
            if current_size >= self.max_file_size_bytes:
                self.log_file_handle.close()
                logger.info(f"SensorLogger: Log file {self.current_log_file} reached {current_size / (1024*1024):.2f}MB, rotating...")

                # Increment rotation count and open new file
                self.rotation_count += 1
                if self.rotation_count >= self.max_rotations:
                    logger.warning(f"SensorLogger: Max rotations ({self.max_rotations}) reached for today. Oldest file will be overwritten.")
                    # If max rotations reached, delete the oldest file for the current day
                    # This ensures we don't infinitely create files for a single day.
                    # This could be improved to move to a 'daily-overflow' archive if desired.
                    oldest_file_to_delete = os.path.join(self.log_directory, self._get_log_filename(self.rotation_count - self.max_rotations))
                    if os.path.exists(oldest_file_to_delete):
                        try:
                            os.remove(oldest_file_to_delete)
                            logger.info(f"SensorLogger: Removed oldest rotated file: {oldest_file_to_delete}")
                        except IOError as e:
                            logger.error(f"SensorLogger: Error removing oldest rotated file {oldest_file_to_delete}: {e}")

                self._open_log_file()
                logger.info(f"SensorLogger: Rotated to new log file: {self.current_log_file}.")
            else:
                logger.debug(f"SensorLogger: Log file size {current_size / (1024*1024):.2f}MB, within limit.")
        else:
            logger.warning("SensorLogger: Current log file path or handle not valid during rotation check. Attempting to reopen.")
            self._open_log_file() # Try to re-open if for some reason it's invalid

    def log_sensor_data_to_file(self, sensor_data_snapshot, alert_status_dict):
        """
        Logs a snapshot of sensor data to the current CSV file.
        Automatically handles daily rotation and file size rotation.
        :param sensor_data_snapshot: The full data snapshot dict from SensorReaderThread,
                                     e.g., {'timestamp': ..., 'data': {...}}
        :param alert_status_dict: A dictionary of current alert statuses,
                                  e.g., {'HTU21D_temperature': True, 'BMP180_pressure': False}
        """
        if not self.log_file_handle:
            logger.warning("SensorLogger: Log file handle not available. Cannot log data. Attempting to re-open.")
            self._check_for_date_change() # This will attempt to open the file
            if not self.log_file_handle:
                logger.error("SensorLogger: Failed to obtain log file handle after re-attempt. Data will not be logged.")
                return

        self._check_for_date_change() # Check for new day before writing
        self._check_and_rotate_file() # Check for file size before writing

        try:
            # The top-level timestamp for the whole snapshot
            snapshot_timestamp_ms = sensor_data_snapshot.get('timestamp', int(time.time() * 1000))
            data = sensor_data_snapshot.get('data', {})

            for sensor_type, metrics in data.items():
                for metric_type, metric_data in metrics.items():
                    value = metric_data.get('value', 'N/A')
                    unit = self._get_unit_for_metric(sensor_type, metric_type) # Get unit
                    
                    # Determine if this specific metric is in alert
                    alert_key = f"{sensor_type}_{metric_type}"
                    is_alert = alert_status_dict.get(alert_key, False)
                    
                    # Format as CSV line
                    line = f"{snapshot_timestamp_ms},{sensor_type},{metric_type},{value},{unit},{is_alert}\n"
                    self.log_file_handle.write(line)
                    # No explicit flush needed with buffering=1, but good practice to know it's handled.
            logger.debug(f"SensorLogger: Logged data for snapshot {snapshot_timestamp_ms}.")
        except Exception as e:
            logger.error(f"SensorLogger: Error writing sensor data to file: {e}", exc_info=True)

    def _get_unit_for_metric(self, sensor_type, metric_type):
        """
        A simple helper to get unit. In a real app, this would come from a data_store
        or a sensor configuration. For now, a hardcoded map.
        """
        # This should ideally be pulled from SensorDataStore.get_unit()
        # For logging, we'll use a simple local map or infer from settings if available.
        unit_map = {
            "temperature": "\u00b0C", # Changed from "°C"
            "humidity": "%",
            "pressure": "hPa",
            "light": "lx"
        }
        return unit_map.get(metric_type.lower(), "")


    def close(self):
        """Closes the current log file handle."""
        if self.log_file_handle:
            self.log_file_handle.close()
            self.log_file_handle = None
            logger.info(f"SensorLogger: Closed log file {self.current_file_path}")

    def __del__(self):
        """Ensures the log file is closed when the object is garbage collected."""
        self.close()
