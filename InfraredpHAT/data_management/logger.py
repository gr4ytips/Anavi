# data_management/logger.py
import logging
import logging.handlers # For RotatingFileHandler
import os
import datetime
import gzip # For gzipping old log files
import shutil # For moving files
import re # For parsing filenames for archive management
import sys # Import sys for sys.is_finalizing()

logger = logging.getLogger(__name__)

class SensorLogger:
    """
    Manages logging of sensor data to a file, with rotation and archiving.
    It uses Python's standard logging module for basic file handling and then
    implements custom logic for gzipping and moving old logs to an archive directory.
    """
    def __init__(self, log_dir="Sensor_Logs", archive_dir="Archive_Sensor_Logs", 
                 max_file_size_mb=5.0, max_rotations=5):
        """
        Initializes the SensorLogger.
        :param log_dir: Absolute path to directory where current log files are stored.
        :param archive_dir: Absolute path to directory where old, gzipped log files are archived.
        :param max_file_size_mb: Maximum size of a single log file before rotation (in MB).
        :param max_rotations: Maximum number of rotated files to keep in the archive.
        """
        self.log_dir = log_dir
        self.archive_dir = archive_dir
        self.max_bytes = max_file_size_mb * 1024 * 1024 
        self.max_rotations = max_rotations 

        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.archive_dir, exist_ok=True)
        logger.info(f"SensorLogger: Log directory ensured: {self.log_dir}")
        logger.info(f"SensorLogger: Archive directory ensured: {self.archive_dir}")


        self.log_file_base = os.path.join(self.log_dir, "sensor_data.log")
        
        self._sensor_logger = logging.getLogger('sensor_data_logger')
        self._sensor_logger.setLevel(logging.INFO) 
        self._sensor_logger.propagate = False 

        for handler in self._sensor_logger.handlers[:]:
            self._sensor_logger.removeHandler(handler)

        self._handler = logging.handlers.RotatingFileHandler(
            self.log_file_base, 
            maxBytes=self.max_bytes, 
            backupCount=1, 
            encoding='utf-8'
        )
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        self._handler.setFormatter(formatter)
        self._sensor_logger.addHandler(self._handler)

        self._ensure_log_header()

        logger.info(f"SensorLogger initialized. Sensor data log file: {self.log_file_base}")
        logger.info(f"Max sensor log file size: {max_file_size_mb} MB, Max archived rotations: {max_rotations}")

    def _ensure_log_header(self):
        """
        Ensures the log file has a CSV header. If the file is new or empty, writes the header.
        This must be called before the first log entry or after a rollover.
        """
        # Temporarily remove handler to write directly to file without triggering rollover logic
        if self._handler in self._sensor_logger.handlers:
            self._sensor_logger.removeHandler(self._handler)

        if not os.path.exists(self.log_file_base) or os.stat(self.log_file_base).st_size == 0:
            try:
                with open(self.log_file_base, 'w', encoding='utf-8', errors='replace') as f:
                    f.write("timestamp_ms,iso_timestamp,sensor_type,metric_type,value,unit,is_alert\n")
                logger.info(f"SensorLogger: Wrote header to new or empty log file: {self.log_file_base}")
            except Exception as e:
                logger.error(f"SensorLogger: Failed to write CSV header to {self.log_file_base}: {e}", exc_info=True)
        
        # Add handler back
        if self._handler not in self._sensor_logger.handlers:
            self._sensor_logger.addHandler(self._handler)


    def log_sensor_data(self, data_snapshot, settings_manager):
        """
        Logs a snapshot of sensor data to the log file.
        :param data_snapshot: A dictionary containing timestamp and sensor data.
                             Expected format: {'timestamp': datetime_object, 'sensors': {...}}
        :param settings_manager: An instance of SettingsManager to retrieve units.
        """
        if not isinstance(data_snapshot, dict) or 'timestamp' not in data_snapshot or 'sensors' not in data_snapshot:
            logger.error(f"Invalid data snapshot format received by SensorLogger: {data_snapshot}")
            return

        timestamp_dt = data_snapshot['timestamp']
        snapshot_timestamp_ms = int(timestamp_dt.timestamp() * 1000)
        iso_timestamp = timestamp_dt.isoformat()
        
        for sensor_type, metrics in data_snapshot['sensors'].items():
            for metric_type, value in metrics.items():
                is_alert = False 

                unit = settings_manager.get_unit(sensor_type, metric_type) 
                
                value_str = f"{value:.2f}" if isinstance(value, (int, float)) and value is not None else "N/A"
                unit_str = str(unit) if unit is not None else ""
                
                line = f"{snapshot_timestamp_ms},{iso_timestamp},{sensor_type},{metric_type},{value_str},{unit_str},{is_alert}\n"
                
                self._sensor_logger.info(line.strip())

        logger.debug(f"SensorLogger: Logged data for snapshot {timestamp_dt}.")

        self._manage_archived_files_after_rollover()

    def _manage_archived_files_after_rollover(self):
        """
        This method is called after RotatingFileHandler has performed its rollover.
        It takes the .1 file (the old log), gzipps it, moves it to the archive,
        and then prunes old archives.
        """
        rolled_file_path = f"{self.log_file_base}.1" 
        
        if os.path.exists(rolled_file_path):
            timestamp_for_archive = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_file_name = f"sensor_data_{timestamp_for_archive}.log.gz"
            archive_file_path = os.path.join(self.archive_dir, archive_file_name)
            
            try:
                with open(rolled_file_path, 'rb') as f_in:
                    with gzip.open(archive_file_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.remove(rolled_file_path) 
                logger.info(f"SensorLogger: Archived '{rolled_file_path}' to '{archive_file_path}'.")
            except Exception as e:
                logger.error(f"SensorLogger: Error gzipping and archiving file '{rolled_file_path}': {e}", exc_info=True)
        else:
            logger.debug(f"SensorLogger: Rolled file expected at '{rolled_file_path}' not found for archiving after rollover. This is normal if no rollover occurred.")

        self._prune_old_archives()

    def _prune_old_archives(self):
        """
        Deletes oldest archived log files (gzipped) to maintain the maximum number of rotations.
        """
        archived_files = [f for f in os.listdir(self.archive_dir) if re.match(r"sensor_data_\d{8}_\d{6}\.log\.gz", f)]
        
        archived_files.sort()
        
        while len(archived_files) > self.max_rotations:
            oldest_file = archived_files.pop(0) 
            oldest_file_path = os.path.join(self.archive_dir, oldest_file)
            try:
                os.remove(oldest_file_path)
                logger.info(f"SensorLogger: Deleted oldest archived log file: {oldest_file_path}")
            except Exception as e:
                logger.error(f"SensorLogger: Error deleting old archived log file '{oldest_file_path}': {e}")

    def close(self):
        """Cleans up logger resources (e.g., closes file handlers)."""
        # Remove handlers from logger before closing them to prevent issues during interpreter shutdown
        for handler in self._sensor_logger.handlers[:]:
            try:
                self._sensor_logger.removeHandler(handler)
                handler.close()
            except Exception as e:
                # Catch exceptions, especially NameError if 'open' is gone during shutdown
                if not sys.is_finalizing(): # Only log if not during finalization
                    logger.error(f"SensorLogger: Error closing handler {handler}: {e}", exc_info=True)
                else:
                    # During finalization, just ignore errors as objects are being torn down
                    pass
        # Only log this if not during interpreter finalization
        if not sys.is_finalizing():
            logger.info("SensorLogger: All logging handlers closed.")

    def cleanup(self):
        """Provides an explicit cleanup method for consistency."""
        self.close()

    def __del__(self):
        """
        Destructor to ensure cleanup when the object is deleted.
        Includes a check for interpreter finalization to prevent NameErrors.
        """
        # Only attempt cleanup if the interpreter is not in the process of shutting down
        if not sys.is_finalizing():
            try:
                self.cleanup()
            except Exception as e:
                # Log only if not during finalization to avoid NameError for 'logger' itself
                if logging.getLogger(__name__).handlers:
                    logging.getLogger(__name__).error(f"Error during SensorLogger __del__ cleanup: {e}", exc_info=True)
                else:
                    print(f"ERROR: SensorLogger __del__ cleanup failed (logging not available): {e}")
        else:
            # During finalization, just let the object be destroyed.
            # Avoid complex operations that rely on global state or unbound builtins.
            pass
