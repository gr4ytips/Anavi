import sys
import os
import datetime
import logging
import logging.handlers # For RotatingFileHandler
import time # Added for time.time() in log_sensor_data_to_file
import collections # Added for collections.deque in _on_settings_updated
from functools import partial # For partial functions with signals

# --- IMPORTANT: Set Matplotlib backend BEFORE importing pyplot ---
import matplotlib
matplotlib.use('Qt5Agg') # Ensure Matplotlib uses the Qt5 backend for PyQt5 integration
# ---------------------------------------------------------------

from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget, QStatusBar, QLabel, QAction, QMenu, QSystemTrayIcon, QMessageBox, QActionGroup, QStyle, QInputDialog
from PyQt5.QtCore import QTimer, Qt, QCoreApplication, QRect, QPoint, QPointF, pyqtSignal, pyqtSlot, QLocale # Import QLocale
from PyQt5.QtGui import QIcon, QPixmap, QImage, QPainter, QFont, QColor, QFontDatabase, QDoubleValidator, QValidator

# Using QMediaPlayer and QMediaContent for sound playback for better compatibility
from PyQt5.QtMultimedia import QSound # Original QSound for simpler cases, re-enabled

# Data management and settings
from data_management.data_store import SensorDataStore 
from data_management.settings import SettingsManager
from data_management.qss_parser import QSSParser # Import QSSParser
from data_management.logger import SensorLogger # Import SensorLogger for dedicated sensor data logging

# UI Components
from ui import AnaviSensorUI

# Sensor reading thread
from sensors.sensor_reader import SensorReaderThread

# --- GLOBAL LOGGING CONFIGURATION ---
# Get the root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG) # Set the root logger level to DEBUG

# Clear any existing handlers to prevent duplicate output if basicConfig was called implicitly
if root_logger.handlers:
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)

# Create a console handler (StreamHandler)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO) # Set console output to INFO and above
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
root_logger.addHandler(console_handler) # Add to root logger

# Create a rotating file handler for debug logs
debug_log_dir = "Debug_Logs"
os.makedirs(debug_log_dir, exist_ok=True)
debug_log_file = os.path.join(debug_log_dir, "debug.log.txt")
file_handler = logging.handlers.RotatingFileHandler(
    debug_log_file,
    maxBytes=5 * 1024 * 1024, # 5 MB per file
    backupCount=5             # Keep 5 backup files
)
file_handler.setLevel(logging.DEBUG) # File handler will capture ALL debug messages
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
root_logger.addHandler(file_handler) # Add to root logger

logger = logging.getLogger(__name__) # Get a logger instance for this module (main)
logger.info("Main application logging configured.")
logger.info("File logging ENABLED at DEBUG level to %s.", debug_log_file)


class MainWindow(QMainWindow):
    """
    The main application window for the Anavi Sensor Dashboard.
    Manages UI, data flow, settings, sensor reading, and logging.
    """
    # Define a signal for global alert state changes (any sensor goes into/out of alert)
    global_alert_state_changed = pyqtSignal(bool) # True if any sensor is in alert, False otherwise

    def __init__(self, parent=None):
        """Initializes the main window and all application components."""
        super().__init__(parent)
        self.setObjectName("MainWindow") # For QSS styling

        logger.info("MainWindow: Application starting up.")

        self.setWindowTitle("Anavi Sensor Dashboard")
        # CORRECTED: Pass full path from resources to get_resource_path
        self.setWindowIcon(QIcon(self.get_resource_path('images/icon.png'))) 
        self.setMinimumSize(800, 600) # Minimum size for usability

        # Validator for numeric input fields (thresholds, sampling rate)
        # MOVED TO TOP for immediate availability
        self.float_validator = QDoubleValidator()
        # Set locale to ensure decimal separator is consistent (e.g., dot vs comma)
        self.float_validator.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.float_validator.setDecimals(2) # Allow 2 decimal places
        self.float_validator.setRange(-9999.0, 9999.0) # Broad range, adjust as needed
        logger.info("MainWindow: float_validator initialized.")


        # --- Data Management ---
        # Initialize SettingsManager first, as other components depend on it
        self.settings_manager = SettingsManager(config_file='config.ini', theme_dir='themes')
        
        # Initialize DataStore
        self.data_store = SensorDataStore(max_points=1000) # Store up to 1000 data points
        # Set reference to thresholds in data store, as it might need them for internal logic later
        # --- FIX: Ensure thresholds are loaded from settings_manager *immediately* for data_store ---
        self.thresholds = self.settings_manager.get_all_thresholds() # Load initial thresholds immediately with proper casing
        self.data_store.set_thresholds_reference(self.thresholds)

        # Initialize SensorLogger based on settings
        self.sensor_logger_enabled = self.settings_manager.get_setting('General', 'data_log_enabled', type=bool)
        self.sensor_logger_max_size_mb = self.settings_manager.get_setting('General', 'data_log_max_size_mb', type=float)
        self.sensor_logger_max_rotations = self.settings_manager.get_setting('General', 'data_log_max_rotations', type=int)

        self.sensor_logger = None
        if self.sensor_logger_enabled:
            try:
                self.sensor_logger = SensorLogger(
                    log_directory='Sensor_Logs',
                    archive_directory='Archive_Sensor_Logs',
                    max_file_size_mb=self.sensor_logger_max_size_mb, # Use current settings
                    max_rotations=self.sensor_logger_max_rotations
                )
                logger.info("MainWindow: Sensor data logging initialized.")
            except Exception as e:
                logger.error(f"MainWindow: Failed to initialize SensorLogger: {e}. Data logging disabled.", exc_info=True)
                self.sensor_logger_enabled = False # Disable if init fails
                self.show_status_message("Error initializing data logger. Logging disabled.", "error")
        else:
            logger.info("MainWindow: Sensor data logging is DISABLED by settings.")

        # --- Sensor Reading Thread ---
        # Pass settings_manager to SensorReaderThread for dynamic config updates
        self.sensor_reader = SensorReaderThread(self.settings_manager)

        # --- UI Initialization ---
        # --- FIX: Ensure theme_colors is retrieved from SettingsManager BEFORE passing to UI ---
        self.theme_colors = self.settings_manager.get_theme_colors() # Get initial theme colors
        self._load_custom_fonts() # Load custom fonts (like Digital-7)
        self.current_gauge_type = self.settings_manager.get_setting('General', 'current_gauge_type', type=str)
        self.current_gauge_style = self.settings_manager.get_setting('General', 'current_gauge_style', type=str)

        # Pass parameters to AnaviSensorUI
        self.ui = AnaviSensorUI(self.data_store, self.settings_manager, self.thresholds, self, self.theme_colors, self.current_gauge_type, self.current_gauge_style)
        self.setCentralWidget(self.ui) # Set the tab widget as central widget

        self.status_bar = self.statusBar()
        self.status_message_label = QLabel("Initializing sensors...")
        self.status_message_label.setStyleSheet("color: white;") # Default status message color
        self.status_bar.addWidget(self.status_message_label)
        self.status_bar.setObjectName("StatusBar") # For QSS
        logger.info("MainWindow: Status bar initialized.")

        # Overall alert state management
        self.is_any_sensor_in_alert = False # Flag to track global alert status
        self.alert_sound_player = None
        self._init_alert_sound()

        # Tray Icon setup
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.windowIcon())
        self.tray_icon.setVisible(True)
        self.create_tray_menu()
        logger.info("MainWindow: System tray icon initialized.")

        # --- Signal Connections ---
        self._connect_signals()

        # Apply initial QSS theme after all widgets are initialized
        # This call will propagate theme colors to all tabs immediately after startup
        self.apply_qss_theme(self.settings_manager.get_setting('General', 'current_theme', type=str))
        logger.info("MainWindow: Initial QSS theme applied.")

        # Start sensor reader thread
        self.sensor_reader.start()
        logger.info(f"MainWindow: SensorReaderThread (ID: {id(self.sensor_reader)}) started.")

        # Initial population of UI data
        self.ui.initialize_all_tab_data() # This will trigger plot updates etc.
        logger.info("MainWindow: Initial UI data population triggered.")

        # Trigger initial gauge style propagation to ensure all display widgets pick up settings
        self.ui.propagate_gauge_style_change(self.current_gauge_type, self.current_gauge_style)
        logger.info("MainWindow: Initial gauge style propagation triggered.")

        # Initial thresholds propagation to display widgets
        # This is CRITICAL to ensure all SensorDisplayWidgets get correct, updated thresholds on startup
        self.ui.update_thresholds_for_display_widgets(self.thresholds)
        logger.info("MainWindow: Initial thresholds propagation to display widgets triggered.")

        logger.info("MainWindow: Application initialization complete.")


    def _load_custom_fonts(self):
        """Loads custom fonts (like Digital-7) into the QFontDatabase."""
        # CORRECTED: Pass the path including the 'fonts/' subdirectory
        font_path = self.get_resource_path("fonts/digital-7.ttf")
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    logger.info(f"MainWindow: Successfully loaded custom font: {font_families[0]}.")
                else:
                    logger.warning(f"MainWindow: Loaded font at {font_path}, but no family names found.")
            else:
                logger.error(f"MainWindow: Failed to add custom font from {font_path} to database.")
        else:
            logger.warning(f"MainWindow: Custom font file 'digital-7.ttf' not found at {font_path}. Digital gauge might not display correctly.")

    def _init_alert_sound(self):
        """Initializes the QSound object for alert sounds."""
        # CORRECTED: Pass the path including the 'sounds/' subdirectory
        sound_file = self.get_resource_path("sounds/alert.wav")
        if os.path.exists(sound_file):
            self.alert_sound_player = QSound(sound_file, self) # Parent to self
            logger.info(f"MainWindow: Alert sound initialized from {sound_file}.")
        else:
            self.alert_sound_player = None
            logger.warning(f"MainWindow: Alert sound file '{sound_file}' not found. Alert sounds disabled.")

    def get_resource_path(self, relative_path):
        """
        Get the absolute path to a resource, handling both development and PyInstaller one-file builds.
        :param relative_path: The path relative to the 'resources' directory (e.g., 'images/icon.png').
        """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        
        # CHANGED: Join directly with relative_path, assuming it now includes subdirs like 'fonts/' or 'images/'
        resource_path = os.path.join(base_path, 'resources', relative_path)
        logger.debug(f"MainWindow: Resolved resource path for '{relative_path}': {resource_path}")
        return resource_path


    def _connect_signals(self):
        """Connects all necessary signals and slots."""
        logger.info("MainWindow: Connecting signals.")
        # Connect sensor reader's data_ready signal to UI's update method
        self.sensor_reader.data_ready.connect(self.data_store.add_data)
        self.sensor_reader.sensor_status_update.connect(self.show_status_message)

        # Connect data store's data_updated signal to UI's display update method
        self.data_store.data_updated.connect(self.ui.update_sensor_displays)
        # Connect data_store data_updated to log data to file
        self.data_store.data_updated.connect(self.log_sensor_data_to_file)

        # Connect UI customization changes from AnaviSensorUI to MainWindow's method to save settings
        self.ui.ui_customization_changed.connect(self.on_ui_customization_changed)
        # Connect theme change signal from AnaviSensorUI (which relays from SettingsTab)
        self.ui.theme_changed.connect(self.apply_qss_theme)
        # Connect thresholds_updated signal from AnaviSensorUI (which relays from SettingsTab)
        self.ui.thresholds_updated.connect(self.on_thresholds_updated_from_ui)

        # Connect alert state changes from individual SensorDisplayWidgets (via UI tabs)
        self.global_alert_state_changed.connect(self.on_global_alert_status_changed)

        # Connect tray icon signal
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        
        # Connect settings manager settings_updated signal to log_level_changed
        self.settings_manager.settings_updated.connect(self._on_settings_manager_updated)
        
        logger.info("MainWindow: All signals connected.")

    @pyqtSlot(str, str, object)
    def _on_settings_manager_updated(self, section, key, value):
        """
        Slot to handle updates from SettingsManager and propagate them
        to relevant parts of MainWindow, specifically for logging and data log config.
        """
        logger.debug(f"MainWindow: Received setting update from SettingsManager: [{section}]{key} = {value}")
        if section == 'General':
            if key == 'data_log_enabled':
                self.sensor_logger_enabled = value
                if self.sensor_logger_enabled and self.sensor_logger is None:
                    # Initialize logger if enabled and not already initialized
                    try:
                        self.sensor_logger = SensorLogger(
                            log_directory='Sensor_Logs',
                            archive_directory='Archive_Sensor_Logs',
                            max_file_size_mb=self.sensor_logger_max_size_mb, # Use current settings
                            max_rotations=self.sensor_logger_max_rotations
                        )
                        logger.info("MainWindow: Sensor data logging re-enabled and initialized via settings update.")
                        self.show_status_message("Data logging enabled.", "info")
                    except Exception as e:
                        logger.error(f"MainWindow: Failed to re-initialize SensorLogger after enabling: {e}. Data logging disabled.", exc_info=True)
                        self.sensor_logger_enabled = False
                        self.show_status_message("Error re-enabling data logger. Logging disabled.", "error")
                elif not self.sensor_logger_enabled and self.sensor_logger:
                    # Close logger if disabled
                    self.sensor_logger.close()
                    self.sensor_logger = None
                    logger.info("MainWindow: Sensor data logging disabled via settings update.")
                    self.show_status_message("Data logging disabled.", "info")

            elif key == 'data_log_max_size_mb':
                self.sensor_logger_max_size_mb = value
                if self.sensor_logger:
                    self.sensor_logger.max_file_size_bytes = value * 1024 * 1024
                    logger.info(f"MainWindow: SensorLogger max file size updated to {value}MB.")
            
            elif key == 'data_log_max_rotations':
                self.sensor_logger_max_rotations = value
                if self.sensor_logger:
                    self.sensor_logger.max_rotations = value
                    logger.info(f"MainWindow: SensorLogger max rotations updated to {value}.")
            
            elif key == 'alert_sound_enabled':
                # No direct action needed here, on_global_alert_status_changed will check setting
                pass
            
            elif key == 'current_theme':
                # This is already connected directly to apply_qss_theme via ui.theme_changed
                pass

    def log_sensor_data_to_file(self, sensor_data):
        """
        Logs the incoming sensor data to a CSV file using SensorLogger.
        This method is connected to `data_store.data_updated`.
        `sensor_data` is the 'data' part of the snapshot from DataStore.
        """
        if self.sensor_logger and self.sensor_logger_enabled:
            # We need to reconstruct the full snapshot format for SensorLogger, including timestamp
            # Use the latest timestamp from data_store for consistency
            latest_snapshot = self.data_store.get_latest_data() # This returns the 'data' part
            # Full snapshot from data_store.get_latest_data() should be {'timestamp': ..., 'data': { ... }}
            # If get_latest_data() only returns the 'data' part, we need to adjust or ensure it returns full snapshot
            # For robustness, we construct it, ensuring timestamp is available.
            full_snapshot_for_logging = {'timestamp': int(time.time() * 1000), 'data': sensor_data}
            if latest_snapshot and 'timestamp' in latest_snapshot:
                 full_snapshot_for_logging['timestamp'] = latest_snapshot['timestamp']
            
            # Prepare alert status for logging
            alert_status = {}
            for sensor_type, metrics in sensor_data.items():
                for metric_type, metric_value_data in metrics.items():
                    metric_key = f"{sensor_type}_{metric_type}"
                    # Check if this specific metric is in alert state
                    # This logic should ideally be managed by SensorDisplayWidget emitting signals
                    # and MainWindow aggregating global alert status.
                    # For logging, we'll check against current thresholds.
                    value = metric_value_data.get('value')
                    if value is not None:
                        # --- FIX: Ensure lowercase lookup for thresholds when logging alert status ---
                        low_thr = self.thresholds.get(sensor_type.lower(), {}).get(metric_type.lower(), {}).get('low')
                        high_thr = self.thresholds.get(sensor_type.lower(), {}).get(metric_type.lower(), {}).get('high')
                        is_alert = False
                        if low_thr is not None and high_thr is not None:
                            if value < low_thr or value > high_thr:
                                is_alert = True
                        alert_status[metric_key] = is_alert
            
            self.sensor_logger.log_sensor_data_to_file(full_snapshot_for_logging, alert_status)
            logger.debug("MainWindow: Logged sensor data to file via SensorLogger.")
        else:
            logger.debug("MainWindow: Sensor data logging is disabled or logger not initialized. Skipping file log.")

    def show_status_message(self, message, message_type="info"):
        """
        Displays a status message in the status bar with a specific color.
        :param message: The message string.
        :param message_type: 'info', 'warning', or 'error'.
        """
        color = "white" # Default
        if message_type == "info":
            color = "white"
        elif message_type == "warning":
            color = "orange"
        elif message_type == "error":
            color = "red"
        
        self.status_message_label.setText(message)
        self.status_message_label.setStyleSheet(f"color: {color};")
        logger.debug(f"MainWindow: Status message displayed: [{message_type}] {message}")

    @pyqtSlot(str)
    def apply_qss_theme(self, theme_file_name):
        """
        Applies the specified QSS theme file to the entire application.
        :param theme_file_name: The name of the QSS file (e.g., 'blue_theme.qss').
        """
        theme_path = os.path.join(self.settings_manager.theme_dir, theme_file_name)
        if os.path.exists(theme_path):
            try:
                with open(theme_path, 'r') as f:
                    self.setStyleSheet(f.read())
                
                # Update the internal theme_colors dictionary in settings_manager
                self.settings_manager._load_theme_colors() # Force reload theme colors for drawing
                self.theme_colors.clear() # Clear old colors
                self.theme_colors.update(self.settings_manager.get_theme_colors()) # Update with newly parsed colors

                # Propagate theme colors to UI tabs
                if self.ui:
                    self.ui.update_theme_colors_globally(self.theme_colors)
                
                logger.info(f"MainWindow: Applied QSS theme from {theme_file_name}.")
                self.show_status_message(f"Theme changed to: {theme_file_name.replace('.qss', '').replace('_', ' ').title()}", "info")
            except Exception as e:
                logger.error(f"MainWindow: Error applying QSS theme from '{theme_path}': {e}", exc_info=True)
                self.show_status_message(f"Failed to apply theme {theme_file_name}. Error: {e}", "error")
        else:
            logger.warning(f"MainWindow: QSS theme file '{theme_path}' not found. Cannot apply theme.")
            self.show_status_message(f"Theme file '{theme_file_name}' not found.", "warning")

    @pyqtSlot(str, str, bool)
    def on_sensor_alert_state_changed(self, sensor_category, metric_type, is_alert):
        """
        Receives alert state changes from individual SensorDisplayWidgets and
        updates the global alert state and plays sound if enabled.
        """
        logger.debug(f"MainWindow: Alert state change received for {sensor_category}-{metric_type}: {is_alert}")
        
        # Determine if ANY sensor is currently in an alert state
        # Iterate through all display widgets to check their individual alert status
        any_alert = False
        
        # Check DashboardTab's widgets
        if self.ui.dashboard_tab:
            for widget_key, widget in self.ui.dashboard_tab.sensor_display_widgets.items():
                if widget._is_alert: # Access the internal alert state
                    any_alert = True
                    break
            if any_alert: # If alert found in dashboard, no need to check details tab
                pass
        
        # If no alert yet, check SensorDetailsTab's widgets
        if not any_alert and self.ui.sensor_details_tab:
            for widget_key, widget in self.ui.sensor_details_tab.sensor_display_widgets.items():
                if widget._is_alert:
                    any_alert = True
                    break

        # Emit global signal only if the overall status has changed
        if any_alert != self.is_any_sensor_in_alert:
            self.is_any_sensor_in_alert = any_alert
            self.global_alert_state_changed.emit(self.is_any_sensor_in_alert)
            logger.info(f"MainWindow: Global alert status changed to: {self.is_any_sensor_in_alert}.")
        else:
            logger.debug(f"MainWindow: Global alert status remains {self.is_any_sensor_in_alert}.")


    @pyqtSlot(bool)
    def on_global_alert_status_changed(self, is_global_alert):
        """
        Handles changes in the global alert status (any sensor in alert).
        Plays alert sound if enabled.
        """
        logger.info(f"MainWindow: Global alert status updated to: {is_global_alert}.")
        alert_sound_enabled = self.settings_manager.get_setting('General', 'alert_sound_enabled', type=bool)

        if is_global_alert:
            self.show_status_message("ALERT: One or more sensors are out of threshold!", "error")
            if alert_sound_enabled and self.alert_sound_player:
                if not self.alert_sound_player.isFinished():
                    self.alert_sound_player.stop() # Stop if already playing to restart
                self.alert_sound_player.play()
                logger.info("MainWindow: Playing alert sound.")
            elif not self.alert_sound_player:
                logger.warning("MainWindow: Alert sound enabled in settings, but sound player not initialized.")
        else:
            self.show_status_message("All sensors within normal limits.", "info")
            if self.alert_sound_player and not self.alert_sound_player.isFinished():
                self.alert_sound_player.stop()
                logger.info("MainWindow: Stopped alert sound.")

    @pyqtSlot(str, str)
    def on_ui_customization_changed(self, gauge_type, gauge_style):
        """
        Handles UI customization changes (gauge type/style) from AnaviSensorUI
        and saves them to settings.
        """
        logger.info(f"MainWindow: UI customization changed: Type='{gauge_type}', Style='{gauge_style}'. Saving settings.")
        self.settings_manager.set_setting('General', 'current_gauge_type', gauge_type)
        self.settings_manager.set_setting('General', 'current_gauge_style', gauge_style)
        logger.debug("MainWindow: UI customization settings saved.")

    @pyqtSlot(dict)
    def on_thresholds_updated_from_ui(self, new_thresholds_dict):
        """
        Receives the full updated thresholds dictionary from the UI (SettingsTab via AnaviSensorUI).
        This method updates the global thresholds dictionary reference in MainWindow
        and ensures settings_manager saves them, then propagates to data_store and UI.
        """
        logger.info("MainWindow: Received thresholds update from UI. Propagating and saving.")
        # Update the global thresholds dictionary itself
        self.thresholds.clear()
        self.thresholds.update(new_thresholds_dict)
        logger.debug(f"MainWindow: Global thresholds dictionary updated to: {self.thresholds}")

        # Save each individual threshold setting via settings_manager
        for sensor_type, metrics in new_thresholds_dict.items():
            for metric_type, limits in metrics.items():
                if 'low' in limits:
                    # Construct key using the original casing from new_thresholds_dict (which is lowercase here)
                    key = f"{sensor_type}_{metric_type}_low" 
                    # Convert None to empty string for configparser
                    value = str(limits['low']) if limits['low'] is not None else ''
                    self.settings_manager.set_setting('Thresholds', key, value)
                if 'high' in limits:
                    key = f"{sensor_type}_{metric_type}_high"
                    value = str(limits['high']) if limits['high'] is not None else ''
                    self.settings_manager.set_setting('Thresholds', key, value)
        
        logger.info("MainWindow: Thresholds saved via SettingsManager.")
        
        # Propagate the updated thresholds to data_store (if needed, already by reference)
        # and to UI display widgets (which is handled by ui.update_thresholds_for_display_widgets)
        self.ui.update_thresholds_for_display_widgets(self.thresholds)
        logger.info("MainWindow: Thresholds propagated to UI display widgets.")

    def create_tray_menu(self):
        """Creates the system tray icon menu."""
        tray_menu = QMenu(self)

        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self.showNormal)
        tray_menu.addAction(show_action)

        hide_action = QAction("Hide Window", self)
        hide_action.triggered.connect(self.hide)
        tray_menu.addAction(hide_action)
        
        # Add 'Restore' option which typically brings the window back to normal state
        restore_action = QAction("Restore", self)
        restore_action.triggered.connect(self.showNormal)
        tray_menu.addAction(restore_action)

        # Add 'Quit' option
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        logger.debug("MainWindow: Tray menu created.")

    def on_tray_icon_activated(self, reason):
        """Handles activation events from the system tray icon."""
        if reason == QSystemTrayIcon.Trigger: # Click
            self.showNormal() # Restore the window
        elif reason == QSystemTrayIcon.DoubleClick: # Double click
            self.showNormal() # Restore the window

    def closeEvent(self, event):
        """Handles the close event for the main window."""
        logger.info("MainWindow: Application closing.")
        
        # Stop sensor reader thread gracefully
        if self.sensor_reader:
            logger.info(f"MainWindow: Stopping SensorReaderThread (ID: {id(self.sensor_reader)}) in closeEvent.")
            self.sensor_reader.stop() 
            self.sensor_reader.wait() # Wait for the thread to finish
            logger.info("MainWindow: Sensor reader gracefully stopped and waited.")
        
        # Save any pending settings
        self.settings_manager.save_settings() 
        logger.info("MainWindow: Settings saved on exit.")
        
        # Close sensor data logger if active
        if self.sensor_logger:
            self.sensor_logger.close() 
            logger.info("MainWindow: Sensor data logger closed.")

        logger.info("Application exit complete.")
        event.accept()


# --- Application Entry Point ---
if __name__ == "__main__":
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling) 
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps) 

    app = QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

