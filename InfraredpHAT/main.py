# main.py
# -*- coding: utf-8 -*-
import sys
import os
import logging
import configparser
from datetime import datetime, timedelta
import collections 

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QMessageBox, QTabWidget, QSpacerItem, QSizePolicy, QStatusBar
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QUrl, QThread, QObject, QLocale
from PyQt5.QtGui import QIcon, QFont, QFontDatabase, QPalette, QColor, QBrush, QTransform, QIntValidator, QDoubleValidator 

# Import custom modules
from data_management.data_store import SensorDataStore
from data_management.settings import SettingsManager
from data_management.logger import SensorLogger 
from ui import AnaviSensorUI
from sensors.sensor_reader import SensorReaderThread

# Get the logger for this module. Configuration will be applied later by setup_logging.
logger = logging.getLogger(__name__)

def setup_logging(settings_manager):
    """
    Configures the root logger based on settings from SettingsManager.
    This function is called once at startup.
    """
    root_logger = logging.getLogger()
    # Clear any existing handlers to prevent duplicate logs from being created
    # if this function is ever called more than once.
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Configure Console Logging
    if settings_manager.get_boolean_setting('Logging', 'enable_console_logging', True):
        console_level_str = settings_manager.get_setting('Logging', 'log_level_console', fallback='INFO').upper()
        console_level = getattr(logging, console_level_str, logging.INFO)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # Configure File Logging
    if settings_manager.get_boolean_setting('Logging', 'enable_file_logging', True):
        log_file_path = settings_manager.get_setting('Logging', 'log_file_path', fallback='Debug_Logs/debug.log.txt')
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        
        file_level_str = settings_manager.get_setting('Logging', 'log_level_file', fallback='DEBUG').upper()
        file_level = getattr(logging, file_level_str, logging.DEBUG)

        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(file_level)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Set the overall level for the root logger to the most verbose of its handlers
    # This ensures that messages are passed to the handlers to be filtered.
    root_logger.setLevel(logging.DEBUG) 
    logger.info("Application logging configured from settings.")

class MainWindow(QMainWindow):
    """
    The main application window for the Anavi Sensor Dashboard.
    Manages overall UI, settings, data acquisition, and alerts.
    """
    def __init__(self, settings_manager):
        """Initializes the MainWindow."""
        super().__init__()
        self.setWindowTitle("Anavi Sensor Dashboard")
        self.setWindowIcon(QIcon(self.get_resource_path("icon.png", "img"))) 
        self.setGeometry(100, 100, 1200, 800) 

        # --- FIX 1: Create the status bar ---
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Status Bar Test: Ready")


        self.settings_manager = settings_manager
        
        self.theme_colors = {} 
        
        self.thresholds = {}
        self.data_store = SensorDataStore(self.settings_manager) 

        self.sensor_logger = None 

        self.int_validator = QIntValidator(self)
        self.double_validator = QDoubleValidator(self)
        self.double_validator.setLocale(QLocale(QLocale.C)) 
        self.double_validator.setNotation(QDoubleValidator.StandardNotation) 
        logger.debug("MainWindow: Initialized QIntValidator and QDoubleValidator.")

        self._setup_data_logger_with_config() 
        
        # --- UI Initialization ---
        initial_gauge_type = self.settings_manager.get_setting('UI', 'gauge_type', fallback='Standard')
        initial_gauge_style = self.settings_manager.get_setting('UI', 'gauge_style', fallback='Full')
        initial_dashboard_plot_time_range = self.settings_manager.get_setting('General', 'dashboard_plot_time_range', fallback='Last 30 minutes')
        initial_detail_plot_time_range = self.settings_manager.get_setting('General', 'detail_plot_time_range', fallback='Last 10 minutes')
        initial_hide_matplotlib_toolbar = self.settings_manager.get_boolean_setting('UI', 'hide_matplotlib_toolbar', fallback=False)
        initial_plot_update_interval_ms = self.settings_manager.get_int_setting('General', 'plot_update_interval_ms', fallback=1000)

        self.ui_tabs = AnaviSensorUI(
            settings_manager=self.settings_manager,
            theme_colors=self.theme_colors,
            initial_gauge_type=initial_gauge_type,
            initial_gauge_style=initial_gauge_style,
            data_store=self.data_store,
            thresholds=self.thresholds,
            initial_dashboard_plot_time_range=initial_dashboard_plot_time_range,
            initial_detail_plot_time_range=initial_detail_plot_time_range,
            initial_hide_matplotlib_toolbar=initial_hide_matplotlib_toolbar,
            initial_plot_update_interval_ms=initial_plot_update_interval_ms,
            main_window=self 
        )
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.ui_tabs)
        logger.info("MainWindow: UI structure setup complete.")

        self.apply_stylesheet() 
        self.load_custom_font() 
        
        self.thresholds.update(self.settings_manager.get_thresholds()) 

        self.setup_connections() 

        self.setup_sensor_thread() 
        self.setup_alert_timer() 

        logger.info("Application starting up.")
        self.ui_tabs.initialize_all_tab_data(self.theme_colors) 
        logger.info("MainWindow: Initialization complete.")

    
    def show_alert_message(self, message, alert_type="info"):
        """Displays a temporary alert message in a status bar or message box."""
        logger.debug(f"show_alert_message called. Type: '{alert_type}', Message: '{message}'")
        
        notification_method = self.settings_manager.get_setting('General', 'notification_method', fallback='Popup')
        logger.debug(f"  Notification method from settings: '{notification_method}'")
        
        if notification_method == 'Popup':
            logger.debug("  Displaying notification as a Popup.")
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(f"Sensor Alert - {alert_type.upper()}")
            msg_box.setText(message)
            
            if alert_type == 'warning':
                msg_box.setIcon(QMessageBox.Warning)
            elif alert_type == 'critical':
                msg_box.setIcon(QMessageBox.Critical)
            else:
                msg_box.setIcon(QMessageBox.Information)

            app = QApplication.instance()
            if app:
                msg_box.setStyleSheet(app.styleSheet())
            msg_box.exec_() 
        
        elif notification_method == 'Status Bar':
            logger.debug("  Attempting to display notification on the Status Bar.")
            if self.statusBar():
                # This logic now looks for specific theme keys for each alert type
                if alert_type == 'critical':
                    bg_color = self.theme_colors.get('statusbar_critical_bg', QColor('#d32f2f'))
                    fg_color = self.theme_colors.get('statusbar_critical_fg', QColor('white'))
                elif alert_type == 'warning':
                    bg_color = self.theme_colors.get('statusbar_warning_bg', QColor('#ffa000'))
                    fg_color = self.theme_colors.get('statusbar_warning_fg', QColor('black'))
                else: # Normal info
                    bg_color = self.theme_colors.get('statusbar_bg', QColor('#1976d2'))
                    fg_color = self.theme_colors.get('statusbar_fg', QColor('white'))

                logger.debug(f"  Status bar colors determined: BG='{bg_color.name()}', FG='{fg_color.name()}'")
                
                stylesheet = f"QStatusBar {{ background-color: {bg_color.name()}; color: {fg_color.name()}; font-weight: bold; }}"
                self.statusBar().setStyleSheet(stylesheet)
                self.statusBar().showMessage(message, 10000)
            else:
                logger.warning("  Could not show status bar message because the statusBar object does not exist.")

    @pyqtSlot()
    def clear_alert_message(self):
        """Clears the alert message from the status bar."""
        if self.statusBar():
            self.statusBar().clearMessage()
            self.statusBar().setStyleSheet("")        

    def _repolish_all_widgets(self):
        """Forces all widgets in the application to re-apply their stylesheet."""
        app = QApplication.instance()
        if app:
            for widget in app.allWidgets():
                widget.style().unpolish(widget)
                widget.style().polish(widget)
        logger.debug("MainWindow: Repolished all widgets for theme update.")

    def get_resource_path(self, relative_path, resource_type=None):
        """
        Determines the absolute path to a resource file.
        """
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(os.path.dirname(__file__))

        resource_dir_parts = [base_path, "resources"]
        if resource_type: 
            resource_dir_parts.append(resource_type)
            
        resource_dir = os.path.join(*resource_dir_parts)
        full_path = os.path.join(resource_dir, relative_path)
        return full_path
    
    def _setup_data_logger_with_config(self):
        """
        Configures the SENSOR DATA logger based on settings from config.ini.
        """
        data_log_enabled = self.settings_manager.get_boolean_setting('General', 'data_log_enabled', fallback=False)
        if data_log_enabled:
            max_size_mb = self.settings_manager.get_float_setting('General', 'data_log_max_size_mb', fallback=5.0)
            max_rotations = self.settings_manager.get_int_setting('General', 'data_log_max_rotations', fallback=5)
            
            if self.sensor_logger:
                self.sensor_logger.close() 

            self.sensor_logger = SensorLogger(
                log_dir=self.get_resource_path("Sensor_Logs", "logs"), 
                archive_dir=self.get_resource_path("Archive_Sensor_Logs", "logs"),
                max_file_size_mb=max_size_mb,
                max_rotations=max_rotations
            )
            self.data_store.data_updated.connect(
                lambda data: self.sensor_logger.log_sensor_data(data, self.settings_manager)
            )
            logger.info("Sensor data logging ENABLED.")
        else:
            if self.sensor_logger:
                try:
                    self.data_store.data_updated.disconnect(
                        lambda data: self.sensor_logger.log_sensor_data(data, self.settings_manager)
                    )
                except (TypeError, RuntimeError):
                    pass
                self.sensor_logger.close()
                self.sensor_logger = None
            logger.info("Sensor data logging DISABLED.")    

    def load_custom_font(self):
        """Loads a custom font (e.g., Inter) from resources if available."""
        font_path = self.get_resource_path("Inter-Regular.ttf", "fonts")
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    QApplication.instance().setFont(QFont(font_families[0]))
                    logger.info(f"Custom font '{font_families[0]}' loaded and set as default application font.")
                    self.settings_manager.set_theme_color('plot_font_family', [font_families[0], 'sans-serif'])
                    return
            logger.warning(f"Failed to load custom font from {font_path}. Using default system font.")
        else:
            logger.warning(f"Custom font file not found at {font_path}. Using default system font.")
        self.settings_manager.set_theme_color('plot_font_family', ['sans-serif'])            

    def setup_connections(self):
        """Sets up connections for signals and slots."""
        self.data_store.data_updated.connect(self.ui_tabs.update_sensor_values) 
        self.ui_tabs.ui_customization_changed.connect(self.handle_ui_customization_change)
        self.ui_tabs.theme_changed.connect(self.apply_stylesheet_by_name)
        self.ui_tabs.thresholds_updated.connect(self.update_thresholds)
        self.ui_tabs.alert_triggered.connect(self.handle_alert_triggered)
        self.ui_tabs.alert_cleared.connect(self.handle_alert_cleared)
        self.settings_manager.settings_updated.connect(self._on_settings_updated)
        self.data_store.sensors_discovered.connect(self.ui_tabs.settings_tab.update_available_sensors)

    @pyqtSlot(str, str, object)
    def _on_settings_updated(self, section, key, value):
        """
        Slot to handle general settings updates.
        """
        if section == 'General' and key in ['data_log_enabled', 'data_log_max_size_mb', 'data_log_max_rotations']:
            self._setup_data_logger_with_config() 
        
        if section == 'General' and key == 'sampling_rate_ms':
            if hasattr(self, 'sensor_reader') and self.sensor_reader:
                self.sensor_reader.set_sampling_rate(int(value))

        if section == 'General' and key == 'data_store_max_points':
            self.data_store.max_points = int(value)
            self.data_store.data_history = collections.deque(self.data_store.data_history, maxlen=int(value))

    def setup_sensor_thread(self):
        """Sets up a QThread for sensor data acquisition using SensorReaderThread."""
        self.sensor_thread = QThread()
        
        sensor_config = self.settings_manager.get_sensor_configurations()
        mock_mode = self.settings_manager.get_boolean_setting('General', 'mock_mode')
        sampling_rate = self.settings_manager.get_int_setting('General', 'sampling_rate_ms')

        self.sensor_reader = SensorReaderThread(
            data_store=self.data_store,
            mock_mode=mock_mode,
            sampling_rate_ms=sampling_rate,
            sensor_config=sensor_config
        )
        self.sensor_reader.moveToThread(self.sensor_thread)

        self.sensor_thread.started.connect(self.sensor_reader.run)
        self.sensor_reader.finished.connect(self.sensor_thread.quit)
        self.sensor_reader.finished.connect(self.sensor_reader.deleteLater)
        self.sensor_thread.finished.connect(self.sensor_thread.deleteLater)

        self.sensor_reader.data_ready.connect(self.data_store.add_data)
        self.sensor_reader.sensors_discovered.connect(self.data_store.update_available_sensors)

        self.sensor_thread.start()

    def setup_alert_timer(self):
        """Sets up a timer for clearing temporary alerts."""
        self.alert_clear_timer = QTimer(self)
        self.alert_clear_timer.setInterval(10000) 
        self.alert_clear_timer.setSingleShot(True)
        self.alert_clear_timer.timeout.connect(self.clear_alert_message)

    @pyqtSlot(str, str, str, str)
    def handle_alert_triggered(self, sensor_category, metric_type, alert_type, message):
        """Handles when a sensor alert is triggered."""
        logger.warning(f"ALERT: {message}")
        self.show_alert_message(message, alert_type)

    @pyqtSlot(str, str)
    def handle_alert_cleared(self, sensor_category, metric_type):
        """Handles when a sensor alert is cleared."""
        self.alert_clear_timer.start() 

    def show_alert_message(self, message, alert_type="info"):
        """Displays a temporary alert message in a status bar or message box."""
        notification_method = self.settings_manager.get_setting('General', 'notification_method', fallback='Popup')
        
        if notification_method == 'Popup':
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(f"Sensor Alert - {alert_type.upper()}")
            msg_box.setText(message)
            
            # --- FIX: Check for 'warning' and 'critical' ---
            if alert_type == 'warning':
                msg_box.setIcon(QMessageBox.Warning)
            elif alert_type == 'critical':
                msg_box.setIcon(QMessageBox.Critical)
            else:
                msg_box.setIcon(QMessageBox.Information)

            # Apply the global stylesheet to the message box
            app = QApplication.instance()
            if app:
                msg_box.setStyleSheet(app.styleSheet())
            msg_box.exec_() 
        elif notification_method == 'Status Bar':
            if self.statusBar():
                status_color = self.theme_colors.get('statusbar_bg', QColor('red')) 
                status_text_color = self.theme_colors.get('statusbar_color', QColor('white'))
                self.statusBar().setStyleSheet(f"QStatusBar {{ background-color: {status_color.name()}; color: {status_text_color.name()}; }}")
                self.statusBar().showMessage(message, 10000) 

    @pyqtSlot()
    def clear_alert_message(self):
        """Clears the alert message from the status bar."""
        if self.statusBar():
            self.statusBar().clearMessage()
            self.statusBar().setStyleSheet("") 

    @pyqtSlot(str)
    def apply_stylesheet_by_name(self, theme_file_name):
        """
        Loads, processes, and applies a QSS stylesheet to the ENTIRE application.
        """
        self.settings_manager.set_setting('General', 'current_theme', theme_file_name)
        
        stylesheet = self.settings_manager.get_theme_stylesheet() 
        
        if stylesheet:
            app = QApplication.instance()
            if app:
                app.setStyleSheet(stylesheet)
            
            new_colors = self.settings_manager.get_theme_colors()
            self.theme_colors.clear()
            self.theme_colors.update(new_colors)
            
            self._repolish_all_widgets()
            
            if hasattr(self, 'ui_tabs') and self.ui_tabs:
                self.ui_tabs.update_theme_colors_globally(self.theme_colors)
                
            logger.info(f"MainWindow: Successfully applied new theme: {theme_file_name}")
        else:
            logger.error(f"MainWindow: Stylesheet for '{theme_file_name}' could not be processed.")
            app = QApplication.instance()
            if app:
                app.setStyleSheet("")

    def apply_stylesheet(self):
        """
        Applies the stylesheet that is currently configured in the settings.
        """
        current_theme_file = self.settings_manager.get_setting('General', 'current_theme', fallback='arctic_ice_theme.qss')
        self.apply_stylesheet_by_name(current_theme_file)

    @pyqtSlot(str, str) 
    def handle_ui_customization_change(self, gauge_type, gauge_style):
        """
        Handles changes to UI customization settings (gauge type/style).
        """
        logger.info(f"MainWindow: UI customization changed - Gauge Type: {gauge_type}, Style: {gauge_style}")

    @pyqtSlot(dict)
    def update_thresholds(self, updated_thresholds):
        """
        Updates the internal thresholds dictionary and propagates it.
        """
        self.thresholds.clear()
        self.thresholds.update(updated_thresholds)
        latest_data = self.data_store.get_latest_data()
        if latest_data:
            self.ui_tabs.update_sensor_values(latest_data)
        self.ui_tabs.dashboard_tab._on_plot_timer_timeout()
        self.ui_tabs.sensor_details_tab.update_all_plots()
        self.ui_tabs.plot_tab.update_plot()
        if self.ui_tabs.ui_customization_tab.preview_gauge:
            self.ui_tabs.ui_customization_tab.preview_gauge.thresholds = {
                'low_threshold': self.settings_manager.get_threshold('HTU21D', 'temperature', 'low_threshold'),
                'high_threshold': self.settings_manager.get_threshold('HTU21D', 'temperature', 'high_threshold')
            }
            self.ui_tabs.ui_customization_tab.preview_gauge.update_value(self.ui_tabs.ui_customization_tab.preview_gauge._current_value) 

    def closeEvent(self, event):
        """Handles the close event of the main window."""
        logger.info("Application closing down.")
        if hasattr(self, 'sensor_reader') and self.sensor_reader:
            self.sensor_reader.stop()
        if hasattr(self, 'sensor_thread') and self.sensor_thread.isRunning():
            self.sensor_thread.quit()
            self.sensor_thread.wait(5000) 
            if self.sensor_thread.isRunning():
                self.sensor_thread.terminate() 
        
        if self.sensor_logger:
            self.sensor_logger.close() 
            self.sensor_logger.cleanup() 
        
        self.data_store.cleanup()
        self.settings_manager.save_settings() 
        logger.info("Application shutdown complete.")
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    settings = SettingsManager()
    setup_logging(settings)

    window = MainWindow(settings)
    window.show()
    sys.exit(app.exec_())