# data_management/settings.py
# -*- coding: utf-8 -*-
import configparser
import os
import logging
import re
import sys 
import collections 
import json 

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QColor

try:
    from data_management.qss_parser import QSSParser 
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Could not import QSSParser directly. Using a dummy class.")
    class QSSParser:
        @staticmethod
        def parse_variables(stylesheet_content): return {}
        @staticmethod
        def replace_placeholders(stylesheet_content, variables): return stylesheet_content

logger = logging.getLogger(__name__)

class SettingsManager(QObject):
    settings_updated = pyqtSignal(str, str, object) 
    theme_changed_signal = pyqtSignal(str) 

    DEFAULT_SETTINGS = {
        'General': {
            'mock_mode': False,
            'sampling_rate_ms': 3000,
            'alert_sound_enabled': True,
            'dashboard_plot_time_range': 'All History',
            'detail_plot_time_range': 'All History',
            'current_theme': 'royal_purple_theme.qss',
            'plot_update_interval_ms': 1000,
            'data_log_enabled': True,
            'data_log_max_size_mb': 5.0,
            'data_log_max_rotations': 5,
            'notification_method': 'Status Bar',
            'data_store_max_points': 1000,
            'alert_sound_file': 'alert.wav',
            'low_threshold_critical': False,
            'high_threshold_critical': False
        },
        'Logging': {
            'enable_file_logging': True,
            'log_level_file': 'DEBUG',
            'log_file_path': 'Debug_Logs/debug.log.txt',
            'enable_console_logging': True,
            'log_level_console': 'DEBUG'
        },
        'UI': {
            'gauge_type': 'Digital - Classic',
            'gauge_style': 'Full',
            'hide_matplotlib_toolbar': False,
            'plot_font_size': 10,
            'plot_font_family': 'Inter',
            'matplotlib_line_colors': ["#1F3A60", "#4682B4", "#87CEFA", "#ADD8E6", "#6A96C2", "#2C3E50", "#3498DB", "#9B59B6", "#E74C3C", "#F1C40F"]
        },
        'Sensor_Presence': {
            'htu21d_present': True,
            'htu21d_temperature_present': True,
            'htu21d_humidity_present': True,
            'bmp180_present': True,
            'bmp180_temperature_present': True,
            'bmp180_pressure_present': True,
            'bmp180_altitude_present': True,
            'bh1750_present': True,
            'bh1750_light_present': True
        },
        'Sensor_Precision': {
            'htu21d_temperature_precision': 2,
            'htu21d_humidity_precision': 2,
            'bmp180_temperature_precision': 2,
            'bmp180_pressure_precision': 2,
            'bmp180_altitude_precision': 2,
            'bh1750_light_precision': 2
        },
        'Sensor_Ranges': {
            'htu21d_temperature_min': -40.0,
            'htu21d_temperature_max': 125.0,
            'htu21d_humidity_min': 0.0,
            'htu21d_humidity_max': 100.0,
            'bmp180_temperature_min': -40.0,
            'bmp180_temperature_max': 85.0,
            'bmp180_pressure_min': 200.0,
            'bmp180_pressure_max': 1100.0,
            'bmp180_altitude_min': -500.0,
            'bmp180_altitude_max': 9000.0,
            'bh1750_light_min': 0.0,
            'bh1750_light_max': 500.0
        },
        'Thresholds': {
            "htu21d_temperature_warning_low_value": 18.0,
            "htu21d_temperature_warning_high_value": 28.0,
            "htu21d_humidity_warning_low_value": 40.0,
            "htu21d_humidity_warning_high_value": 60.0,
            "bmp180_temperature_warning_low_value": 15.0,
            "bmp180_temperature_warning_high_value": 30.0,
            "bmp180_pressure_warning_low_value": 950.0,
            "bmp180_pressure_warning_high_value": 1050.0,
            "bmp180_altitude_warning_low_value": 0.0,
            "bmp180_altitude_warning_high_value": 100.0,
            "bh1750_light_warning_low_value": 50.0,
            "bh1750_light_warning_high_value": 500.0,
            "htu21d_temperature_critical_high_value": 45.0,
            "htu21d_temperature_critical_low_value": 0.0,
            "htu21d_humidity_critical_high_value": 95.0,
            "htu21d_humidity_critical_low_value": 5.0,
            "bmp180_temperature_critical_high_value": 45.0,
            "bmp180_temperature_critical_low_value": 0.0,
            "bmp180_pressure_critical_high_value": 1090.0,
            "bmp180_pressure_critical_low_value": 910.0,
            "bmp180_altitude_critical_high_value": 950.0,
            "bmp180_altitude_critical_low_value": 50.0,
            "bh1750_light_critical_high_value": 9500.0,
            "bh1750_light_critical_low_value": 50.0,
            "htu21d_temperature_low_threshold": 10.0,
            "bmp180_temperature_low_threshold": 8.0,
            "htu21d_temperature_high_threshold": 30.0,
            "htu21d_humidity_high_threshold": 70.0,
            "htu21d_humidity_low_threshold": 30.0,
            "bmp180_temperature_high_threshold": 32.0,
            "bmp180_pressure_high_threshold": 1070.0,
            "bmp180_pressure_low_threshold": 930.0,
            "bmp180_altitude_high_threshold": 90.0,
            "bmp180_altitude_low_threshold": 10.0,
            "bh1750_light_high_threshold": 450.0,
            "bh1750_light_low_threshold": 70.0
        }
    }

   

            
    DEFAULT_METRIC_INFO = {
        'HTU21D': {
            'temperature': {
                'unit': '\u00B0C', 'min': 0.0, 'max': 50.0,
                'warning_high_value_default': 35.0, 'warning_low_value_default': 5.0,
                'critical_high_value_default': 45.0, 'critical_low_value_default': 0.0
            },
            'humidity': {
                'unit': '%', 'min': 0.0, 'max': 100.0,
                'warning_high_value_default': 80.0, 'warning_low_value_default': 20.0,
                'critical_high_value_default': 95.0, 'critical_low_value_default': 5.0
            }
        },
        'BMP180': {
            'temperature': {
                'unit': '\u00B0C', 'min': 0.0, 'max': 50.0,
                'warning_high_value_default': 35.0, 'warning_low_value_default': 5.0,
                'critical_high_value_default': 45.0, 'critical_low_value_default': 0.0
            },
            'pressure': {
                'unit': 'hPa', 'min': 900.0, 'max': 1100.0,
                'warning_high_value_default': 1050.0, 'warning_low_value_default': 950.0,
                'critical_high_value_default': 1090.0, 'critical_low_value_default': 910.0
            },
            'altitude': {
                'unit': 'm', 'min': 0.0, 'max': 1000.0,
                'warning_high_value_default': 800.0, 'warning_low_value_default': 200.0,
                'critical_high_value_default': 950.0, 'critical_low_value_default': 50.0
            }
        },
        'BH1750': { 
                'light': {
                    'unit': 'lx', 'min': 0.0, 'max': 1000.0, # Changed max to 1000.0
                    'warning_high_value_default': 800.0, 'warning_low_value_default': 100.0,
                    'critical_high_value_default': 950.0, 'critical_low_value_default': 50.0
                } 
            }
    }

    def __init__(self, config_file='config.ini', parent=None):
        super().__init__(parent)
        self._theme_cache = {}
        self.config_file = self.get_resource_path(config_file, sub_folder='config') 
        self.config = configparser.ConfigParser()
        self.current_stylesheet = ""
        self._theme_colors = {} 

        try:
            self.load_settings()
        except Exception as e:
            logger.critical(f"A critical error occurred during SettingsManager initialization: {e}", exc_info=True)
            self.config = configparser.ConfigParser() 
            self._theme_colors = {}
            self.set_default_settings() 

    def get_resource_path(self, file_name, sub_folder=None, resource_type=None):
        """
        Constructs the absolute path to a resource file.
        Assumes a 'resources' folder at the project root.
        Accepts 'sub_folder' or 'resource_type' for the subdirectory.
        """
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(script_dir, '..')) 
        
        # --- FIX: Corrected logic for folder_to_use ---
        folder_to_use = sub_folder
        if folder_to_use is None: # Only use resource_type if sub_folder was explicitly None
            folder_to_use = resource_type 
        # --- END FIX ---

        if folder_to_use:
            resource_path = os.path.join(project_root, 'resources', folder_to_use, file_name)
        else:
            resource_path = os.path.join(project_root, 'resources', file_name)
        
        logger.debug(f"SettingsManager.get_resource_path: Constructed path for '{file_name}' in '{folder_to_use}': {resource_path}")
        return resource_path

    def load_settings(self):
        logger.debug(f"Attempting to load settings from: {self.config_file}")
        if os.path.exists(self.config_file):
            try:
                self.config.read(self.config_file)
                logger.info(f"Settings successfully loaded from {self.config_file}")
            except configparser.Error as e:
                logger.error(f"Failed to parse config file {self.config_file}. Error: {e}. Loading default settings instead.", exc_info=True)
                self.set_default_settings()
        else:
            logger.warning(f"Config file not found at {self.config_file}. Creating a new one with default settings.")
            self.set_default_settings()

    def set_default_settings(self):
        logger.debug("Applying default settings.")
        try:
            for section, settings in self.DEFAULT_SETTINGS.items():
                if not self.config.has_section(section):
                    self.config.add_section(section)
                for key, value in settings.items():
                    self.config.set(section, key, str(value)) 
            self.save_settings() 
            logger.info("Default settings have been created and saved.")
        except Exception as e:
            logger.error(f"An unexpected error occurred while setting default settings: {e}", exc_info=True)

    def save_settings(self):
        """Saves all current settings to disk."""
        logger.debug(f"Attempting to save settings to {self.config_file}")
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as configfile:
                self.config.write(configfile)
            logger.info(f"Settings saved to {self.config_file}")
        except (IOError, PermissionError) as e:
            logger.error(f"Failed to save settings to {self.config_file} due to an I/O or permission error: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"An unexpected error occurred while saving settings: {e}", exc_info=True)

    def get_setting(self, section, key, fallback=None):
        try:
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            logger.debug(f"Setting '{key}' in section '{section}' not found. Returning fallback: {fallback}.")
            return fallback
        except Exception as e:
            logger.error(f"An unexpected error occurred getting setting '{key}' from '{section}': {e}", exc_info=True)
            return fallback

    def get_int_setting(self, section, key, fallback=0):
        """Gets a setting value as an integer, with a fallback."""
        try:
            return self.config.getint(section, key)
        except (configparser.NoOptionError, configparser.NoSectionError, ValueError):
            logger.debug(f"Could not find or convert '{key}' in section '{section}'. Falling back to {fallback}.")
            return fallback        

    #def get_int_setting(self, section, key, default=0):
    #    try:
    #        return self.config.getint(section, key)
    #    except (configparser.NoSectionError, configparser.NoOptionError):
    #        logger.debug(f"Setting '{key}' in section '{section}' not found. Returning default: {default}.")
    #        return default
    #    except ValueError:
    #        logger.warning(f"Value for '{key}' in section '{section}' is not a valid integer. Returning default: {default}.")
    #        return default
    #    except Exception as e:
    #        logger.error(f"An unexpected error occurred getting int setting '{key}' from '{section}': {e}", exc_info=True)
    #        return default

    #def get_float_setting(self, section, key, default=0.0):
    #    try:
    #        return self.config.getfloat(section, key)
    #    except (configparser.NoSectionError, configparser.NoOptionError):
    #        logger.debug(f"Setting '{key}' in section '{section}' not found. Returning default: {default}.")
    #        return default
    #    except ValueError:
    #        logger.warning(f"Value for '{key}' in section '{section}' is not a valid float. Returning default: {default}.")
    #        return default
    #    except Exception as e:
    #        logger.error(f"An unexpected error occurred getting float setting '{key}' from '{section}': {e}", exc_info=True)
    #        return default

    def get_float_setting(self, section, key, fallback=0.0):
        """Gets a setting value as a float, with a fallback."""
        try:
            return self.config.getfloat(section, key)
        except (configparser.NoOptionError, configparser.NoSectionError, ValueError):
            logger.debug(f"Could not find or convert '{key}' in section '{section}'. Falling back to {fallback}.")
            return fallback

    #def get_boolean_setting(self, section, key, default=False):
    #    try:
    #        return self.config.getboolean(section, key)
    #    except (configparser.NoSectionError, configparser.NoOptionError):
    #        logger.debug(f"Setting '{key}' in section '{section}' not found. Returning default: {default}.")
    #        return default
    #    except ValueError:
    #        logger.warning(f"Value for '{key}' in section '{section}' is not a valid boolean. Returning default: {default}.")
    #        return default
    #    except Exception as e:
    #        logger.error(f"An unexpected error occurred getting boolean setting '{key}' from '{section}': {e}", exc_info=True)
    #        return default

    def get_boolean_setting(self, section, key, fallback=False):
        """Gets a setting value as a boolean, with a fallback."""
        try:
            return self.config.getboolean(section, key)
        except (configparser.NoOptionError, configparser.NoSectionError, ValueError):
            logger.debug(f"Could not find or convert '{key}' in section '{section}'. Falling back to {fallback}.")
            return fallback    

    def set_setting(self, section, key, value):
        try:
            if not self.config.has_section(section):
                logger.debug(f"Section '{section}' not found. Creating it.")
                self.config.add_section(section)
            
            new_value_str = str(value)
            
            current_value_str = None
            if self.config.has_option(section, key):
                current_value_str = self.config.get(section, key)

            if current_value_str == new_value_str:
                logger.debug(f"SettingsManager: Setting {section}/{key} already has value {value}. No change.")
                return 

            self.config.set(section, key, new_value_str)
            self.save_settings() 
            logger.debug(f"Setting '{key}' in '{section}' set to '{value}'.")
            self.settings_updated.emit(section, key, value) 
        except Exception as e:
            logger.error(f"Failed to set setting '{key}' in '{section}' to '{value}': {e}", exc_info=True)

    def set_theme_color(self, key, value):
        """Manually sets or overrides a single theme color property in _theme_colors."""
        self._theme_colors[key] = value
        logger.debug(f"SettingsManager: Manually set theme property '{key}'.")            

    def get_sensor_configurations(self):
        """Returns a dictionary of all sensors and their metrics that are enabled in settings."""
        configs = collections.defaultdict(dict)
        for sensor_type, metrics in self.DEFAULT_METRIC_INFO.items():
            if self.get_boolean_setting('Sensor_Presence', f'{sensor_type.lower()}_present', fallback=False):
                for metric_type, info in metrics.items():
                    if self.get_boolean_setting('Sensor_Presence', f'{sensor_type.lower()}_{metric_type.lower()}_present', fallback=False):
                        precision = self.get_int_setting('Sensor_Precision', f"{sensor_type.lower()}_{metric_type.lower()}_precision", info.get('precision', 2))
                        min_val = self.get_float_setting('Sensor_Ranges', f"{sensor_type.lower()}_{metric_type.lower()}_min", info.get('min', 0.0)) 
                        max_val = self.get_float_setting('Sensor_Ranges', f"{sensor_type.lower()}_{metric_type.lower()}_max", info.get('max', 100.0)) 
                        
                        metric_config = info.copy()
                        metric_config['precision'] = precision
                        metric_config['min'] = min_val
                        metric_config['max'] = max_val
                        
                        configs[sensor_type][metric_type] = metric_config
        logger.debug(f"Returning sensor configurations: {dict(configs)}")
        return configs
        
    def get_all_metric_info(self):
        """Returns all possible metric info, regardless of presence, for UI population."""
        return self.DEFAULT_METRIC_INFO

    def get_unit(self, sensor_type, metric_type):
        return self.DEFAULT_METRIC_INFO.get(sensor_type, {}).get(metric_type, {}).get('unit', '')        
        
    #def get_range(self, sensor_type, metric_type):
    #    min_val = self.get_float_setting('Sensor_Ranges', f"{sensor_type.lower()}_{metric_type.lower()}_min", 0.0)
    #    max_val = self.get_float_setting('Sensor_Ranges', f"{sensor_type.lower()}_{metric_type.lower()}_max", 100.0)
    #    return min_val, max_val    

    def get_range(self, sensor_type, metric_type):
        """Gets the min and max range for a sensor metric as floats."""
        try:
            logger.debug(f"Getting range for sensor='{sensor_type}', metric='{metric_type}'")
            section = 'Sensor_Ranges'
            key_min = f"{sensor_type.lower()}_{metric_type.lower()}_min"
            key_max = f"{sensor_type.lower()}_{metric_type.lower()}_max"
            
            min_val = self.get_float_setting(section, key_min, fallback=None)
            max_val = self.get_float_setting(section, key_max, fallback=None)
            
            logger.debug(f"Found range: min_key='{key_min}', min_val={min_val}; max_key='{key_max}', max_val={max_val}")
            
            return min_val, max_val
        except Exception as e:
            logger.error(f"An unexpected error occurred in get_range for {sensor_type}/{metric_type}: {e}")
            return None, None
        
    @staticmethod
    def _format_name_for_qss(name):
        """Replaces characters not allowed in QSS object names with underscores."""
        return re.sub(r'[^a-zA-Z0-9_]', '_', name.replace(' ', '_').replace('-', '_').replace('.', '_')).strip().lower()
        
    def get_precision(self, sensor_type, metric_type):
        return self.get_int_setting('Sensor_Precision', f"{sensor_type.lower()}_{metric_type.lower()}_precision", 2)
    
    def get_gauge_type(self, sensor_type=None, metric_type=None):
        return self.get_setting('UI', 'gauge_type', fallback='Analog')

    def get_gauge_style(self, sensor_type=None, metric_type=None):
        return self.get_setting('UI', 'gauge_style', fallback='Full')

    LOGICAL_TO_INI_KEY_MAP = {
        'warning_low_value': 'low_threshold',
        'warning_high_value': 'high_threshold',
        'critical_low_value': 'critical_low_value',
        'critical_high_value': 'critical_high_value'
    }
    INI_TO_LOGICAL_KEY_MAP = {v: k for k, v in LOGICAL_TO_INI_KEY_MAP.items()}

    def get_thresholds(self):
        """
        Retrieves threshold values for all configured sensors and metrics from configparser.
        Returns a dict: {'SensorType': {'metric_type': {'threshold_type': value}}}
        """
        all_thresholds = collections.defaultdict(lambda: collections.defaultdict(dict))
        
        for sensor_type, metrics in self.DEFAULT_METRIC_INFO.items():
            for metric_type, default_metric_info in metrics.items():
                for logical_threshold_name in ['warning_high_value', 'warning_low_value', 'critical_high_value', 'critical_low_value']:
                    ini_key_suffix = self.LOGICAL_TO_INI_KEY_MAP.get(logical_threshold_name)
                    
                    if ini_key_suffix is None:
                        logger.warning(f"SettingsManager: No INI key mapping found for logical threshold '{logical_threshold_name}'. Skipping in get_thresholds.")
                        continue 

                    full_ini_key = f"{sensor_type.lower()}_{metric_type.lower()}_{ini_key_suffix}"
                    
                    default_val = default_metric_info.get(f"{logical_threshold_name}_default")
                    
                    value = self.get_float_setting('Thresholds', full_ini_key, fallback=default_val)
                    
                    if value is not None:
                        all_thresholds[sensor_type][metric_type][logical_threshold_name] = value
                        logger.debug(f"SettingsManager: Loaded threshold {sensor_type}/{metric_type}/{logical_threshold_name} (INI key: {full_ini_key}): {value}")
                    else:
                        logger.debug(f"SettingsManager: No value found for {full_ini_key} in INI or DEFAULT_METRIC_INFO. Value remains None.")
        return dict(all_thresholds) 

    def set_threshold(self, sensor_type, metric_type, threshold_type, value):
        """Sets a specific threshold value and saves it."""
        ini_key_suffix = self.LOGICAL_TO_INI_KEY_MAP.get(threshold_type)
        if ini_key_suffix is None:
            logger.error(f"SettingsManager: Cannot set threshold. No INI key mapping found for logical threshold type '{threshold_type}'.")
            return

        full_ini_key = f"{sensor_type.lower()}_{metric_type.lower()}_{ini_key_suffix}"
        
        self.set_setting('Thresholds', full_ini_key, str(value)) 

        self.settings_updated.emit('Thresholds', f"{sensor_type}/{metric_type}/{threshold_type}", value) 

    def get_threshold(self, sensor_type, metric_type, threshold_name):
        """Gets a single threshold value for a sensor metric as a float."""
        try:
            logger.debug(f"Getting threshold for sensor='{sensor_type}', metric='{metric_type}', threshold='{threshold_name}'")
            section = 'Thresholds'
            key = f"{sensor_type.lower()}_{metric_type.lower()}_{threshold_name}"
            
            value = self.get_float_setting(section, key, fallback=None)

            logger.debug(f"Found threshold: key='{key}', value={value}")
            
            return value
        except Exception as e:
            logger.error(f"An unexpected error occurred in get_threshold for {sensor_type}/{metric_type}/{threshold_name}: {e}")
            return None

    #def get_threshold(self, sensor_type, metric_type, threshold_type, fallback=None):
    #    """
    #    Retrieves a specific threshold value.
    #    This is used by SensorDisplayWidget and MatplotlibWidget.
    #    """
    #    ini_key_suffix = self.LOGICAL_TO_INI_KEY_MAP.get(threshold_type)
    #    if ini_key_suffix is None:
    #        logger.warning(f"SettingsManager: Cannot get threshold. No INI key mapping found for logical threshold type '{threshold_type}'. Returning fallback: {fallback}.")
    #        return fallback

    #    full_ini_key = f"{sensor_type.lower()}_{metric_type.lower()}_{ini_key_suffix}"
        
    #    raw_value = self.get_setting('Thresholds', full_ini_key, None)

    #    value = None
    #    if raw_value is not None:
    #        try:
    #           value = float(raw_value)
    #        except ValueError:
    #            logger.warning(f"SettingsManager: Invalid stored threshold value '{raw_value}' for {full_ini_key}. Using fallback.")
        
    #    if value is None:
    #        default_key_in_metric_info = f"{threshold_type}_default"
    #        default_metric_info = self.DEFAULT_METRIC_INFO.get(sensor_type, {}).get(metric_type, {})
    #        if default_key_in_metric_info in default_metric_info:
    #            value = default_metric_info[default_key_in_metric_info]
    #        else:
    #            value = fallback

    #   logger.debug(f"SettingsManager: get_threshold for {sensor_type}/{metric_type}/{threshold_type} (INI key: {full_ini_key}). Result: {value}")
    #    return value

    def get_theme_stylesheet(self):
        """
        Loads, processes, and caches the current theme's QSS file using a
        robust separator-based parsing method.
        """
        theme_file_name = self.get_setting('General', 'current_theme', fallback='royal_purple_theme.qss')

        if theme_file_name in self._theme_cache:
            logger.debug(f"SettingsManager.get_theme_stylesheet: Loading '{theme_file_name}' from cache.")
            self.current_stylesheet = self._theme_cache[theme_file_name]
            return self.current_stylesheet

        theme_path = self.get_resource_path(file_name=theme_file_name, sub_folder='themes')
        if not os.path.exists(theme_path):
            logger.error(f"SettingsManager.get_theme_stylesheet: Theme file not found: {theme_path}. No QSS theme will be applied.")
            self._theme_colors = {} 
            return ""

        try:
            with open(theme_path, 'r') as f:
                qss_content = f.read()

            separator = '/* --- QSS Styling Rules --- */'
            if separator not in qss_content:
                logger.error(f"SettingsManager.get_theme_stylesheet: Stylesheet {theme_path} is missing the separator: '{separator}'")
                self._theme_colors = {} 
                return qss_content

            variable_part, rules_part = qss_content.split(separator, 1)

            self._theme_colors = QSSParser.parse_variables(variable_part)
            if not self._theme_colors:
                logger.error("SettingsManager.get_theme_stylesheet: Parsing variables from QSS returned an empty dictionary. Theming might fail.")
                
            def replacer(match):
                key = match.group(1).replace('-', '_')
                value_obj = self._theme_colors.get(key)

                if value_obj is None:
                    logger.warning(f"SettingsManager.get_theme_stylesheet: Variable '{key}' not found for placeholder '{{{match.group(1)}}}'.")
                    return "/* VAR_NOT_FOUND */"

                if isinstance(value_obj, QColor):
                    return value_obj.name(QColor.HexArgb) if value_obj.alpha() < 255 else value_obj.name()
                
                if isinstance(value_obj, list):
                    converted_colors = []
                    for item in value_obj:
                        if isinstance(item, QColor):
                            converted_colors.append(item.name(QColor.HexArgb) if item.alpha() < 255 else item.name())
                        elif isinstance(item, str):
                            converted_colors.append(QColor(item).name(QColor.HexArgb) if QColor(item).alpha() < 255 else QColor(item).name())
                        else:
                            converted_colors.append(str(item))
                    return f"[{', '.join(converted_colors)}]"
                
                return str(value_obj)

            placeholder_pattern = re.compile(r'@\{([\w-]+)\}')
            processed_qss = placeholder_pattern.sub(replacer, rules_part)
            self.current_stylesheet = processed_qss.strip()
            
            self._theme_cache[theme_file_name] = self.current_stylesheet
            logger.debug(f"Processed and cached '{theme_file_name}'.")
            logger.debug(f"Dumbing Processed and cached QSS\n '{self._theme_cache[theme_file_name]}' from cache.")

            return self.current_stylesheet

        except Exception as e:
            logger.exception(f"An unexpected error occurred while processing stylesheet {theme_path}: {e}")
            self._theme_colors = {} 
            return ""

    def get_theme_color(self, key, fallback=None):
        """Gets a specific color or value from the theme dictionary."""
        color = self._theme_colors.get(key, fallback)
        if color is fallback:
            logger.debug(f"Theme color '{key}' not found, returning fallback.")
        return color      

    def get_theme_colors(self):
        if not self._theme_colors:
            logger.debug("Theme colors not loaded yet. Calling get_theme_stylesheet() to load them.")
            self.get_theme_stylesheet()
        return self._theme_colors
    
    def get_plot_color(self, index):
        """Gets a plot color from the theme's color list by index."""
        try:
            colors = self.get_theme_colors().get('matplotlib_line_colors', [])
            
            if not isinstance(colors, list) or not colors:
                logger.warning("SettingsManager: 'matplotlib_line_colors' is not a valid list in theme. Using default blue.")
                return QColor('blue')
            
            color_item = colors[index % len(colors)]
            if isinstance(color_item, str):
                return QColor(color_item)
            return color_item 
        except Exception as e:
            logger.error(f"Error getting plot color at index {index}: {e}. Returning default blue.", exc_info=True)
            return QColor('blue')

    def _get_fallback_theme_colors(self):
        """
        Provides a comprehensive default theme based on a royal purple palette.
        This is used if a QSS file fails to load and the requested theme is RoyalPurple.
        """
        return {
            'plot_font_size': 10,
            'plot_font_family': 'Inter',
            'matplotlib_figure_facecolor': QColor('#2C1D33'),
            'matplotlib_axes_facecolor': QColor('#31223D'),
            'matplotlib_edgecolor': QColor('#6A357A'),
            'matplotlib_label_color': QColor('#CE93D8'),
            'matplotlib_tick_color': QColor('#BA68C8'),
            'matplotlib_title_color': QColor('#F02BFE'),
            'matplotlib_grid_color': QColor('#4A235A'),
            'matplotlib_legend_facecolor': QColor('#4A235A'),
            'matplotlib_legend_label_color': QColor('#F3E5F5'),
            'matplotlib_line_colors': [QColor(c) for c in ["#F02BFE", "#D81B60", "#E040FB", "#CE93D8", "#BA68C8", "#9C27B0", "#AB47BC", "#8E24AA"]],
            'plot_threshold_low_color': QColor('#AF7AC5'),
            'plot_threshold_high_color': QColor('#E57373'),
            'plot_na_text_color': QColor('#BA68C8'),

            'font_family': 'Inter',
            'digital_font_family': 'Digital-7',

            'gauge_text_outline_color': QColor('#000000'),
            'gauge_high_contrast_text_color': QColor('#FFFFFF'),
            'gauge_background_normal': QColor('#4A235A'),
            'gauge_border_normal': '1px solid #6A357A',
            'gauge_fill_normal': QColor('#AF7AC5'),
            'gauge_text_normal': QColor('#F3E5F5'),
            'gauge_background_alert': QColor('#5D4037'),
            'gauge_border_alert': '1px solid #E57373',
            'gauge_fill_alert': QColor('#D32F2F'),
            'gauge_text_alert': QColor('#FFFFFF'),
            'gauge_warning_color': QColor('#FBC02D'),
            'gauge_critical_color': QColor('#D32F2F'),

            'gauge_border_width': 1,
            'gauge_border_style': 'solid',
            'gauge_border_color': QColor('#6A357A'), 

            'progressbar_background': QColor('#4A235A'),
            'progressbar_border': '1px solid #6A357A',
            'progressbar_border_radius': 4,
            'progressbar_chunk_color': QColor('#AF7AC5'),
            'progressbar_text_color': QColor('#F3E5F5'),
            'progressbar_background_alert': QColor('#5D4037'),
            'progressbar_border_alert': '1px solid #E57373',
            'progressbar_chunk_alert_color': QColor('#D32F2F'),
            'progressbar_text_alert_color': QColor('#FFFFFF'),

            'digital_gauge_font_color': QColor('#F02BFE'),
            'digital_gauge_bg_color': QColor('#000000'),
            'digital_gauge_border_color': '1px solid #333333',
            'digital_gauge_font_alert_color': QColor('#FFB74D'),
            'digital_gauge_bg_alert_color': QColor('#4E342E'),
            'digital_gauge_border_alert_color': '1px solid #E57373',
            'digital_gauge_segment_color': QColor('#333333'),

            'analog_gauge_background': QColor('#4A235A'),
            'analog_gauge_border': '1px solid #6A357A',
            'analog_gauge_scale_color': QColor('#BA68C8'),
            'analog_gauge_label_color': QColor('#CE93D8'),
            'analog_gauge_needle_color': QColor('#E53935'),
            'analog_gauge_center_dot_color': QColor('#F02BFE'),
            'analog_gauge_text_color': QColor('#F3E5F5'),
            'analog_gauge_background_alert': QColor('#5D4037'),
            'analog_gauge_border_alert': '1px solid #E57373',
            'analog_gauge_scale_alert_color': QColor('#FF7043'),
            'analog_gauge_needle_alert_color': QColor('#FFCA28'),
            'analog_gauge_center_dot_alert_color': QColor('#D32F2F'),
            'analog_gauge_text_alert_color': QColor('#FFFFFF'),

            'analog_basic_classic_background': QColor('#212121'),
            'analog_basic_classic_border': '1px solid #424242',
            'analog_basic_classic_scale_color': QColor('#CE93D8'),
            'analog_basic_classic_needle_color': QColor('#AF7AC5'),
            'analog_basic_classic_center_dot_color': QColor('#AF7AC5'),
            'analog_basic_classic_text_color': QColor('#F3E5F5'),
            'analog_basic_classic_background_alert': QColor('#4E342E'),
            'analog_basic_classic_border_alert': '1px solid #E57373',
            'analog_basic_classic_scale_alert_color': QColor('#FF8A65'),
            'analog_basic_classic_needle_alert_color': QColor('#FFD54F'),
            'analog_basic_classic_center_dot_alert_color': QColor('#E53935'),
            'analog_basic_classic_text_alert_color': QColor('#FFD54F'),

            'analog_full_classic_background': QColor('#121212'),
            'analog_full_classic_border': '1px solid #333333',
            'analog_full_classic_scale_color': QColor('#CE93D8'),
            'analog_full_classic_needle_color': QColor('#AF7AC5'),
            'analog_full_classic_center_dot_color': QColor('#AF7AC5'),
            'analog_full_classic_text_color': QColor('#F3E5F5'),
            'analog_full_classic_background_alert': QColor('#4E342E'),
            'analog_full_classic_border_alert': '1px solid #E57373',
            'analog_full_classic_scale_alert_color': QColor('#FF8A65'),
            'analog_full_classic_needle_alert_color': QColor('#FFD54F'),
            'analog_full_classic_center_dot_alert_color': QColor('#E53935'),
            'analog_full_classic_text_alert_color': QColor('#FFD54F'),

            'analog_modern_basic_background': QColor('#4A235A'),
            'analog_modern_basic_border': '1px solid #6A357A',
            'analog_modern_basic_scale_color': QColor('#BA68C8'),
            'analog_modern_basic_needle_color': QColor('#E53935'),
            'analog_modern_basic_center_dot_color': QColor('#F02BFE'),
            'analog_modern_basic_text_color': QColor('#F3E5F5'),
            'analog_modern_basic_background_alert': QColor('#5D4037'),
            'analog_modern_basic_border_alert': '1px solid #E57373',
            'analog_modern_basic_scale_alert_color': QColor('#FF7043'),
            'analog_modern_basic_needle_alert_color': QColor('#FFCA28'),
            'analog_modern_basic_center_dot_alert_color': QColor('#D32F2F'),
            'analog_modern_basic_text_alert_color': QColor('#FFFFFF'),

            'analog_modern_full_background': QColor('#4A235A'),
            'analog_modern_full_border': '1px solid #6A357A',
            'analog_modern_full_scale_color': QColor('#BA68C8'),
            'analog_modern_full_needle_color': QColor('#E53935'),
            'analog_modern_full_center_dot_color': QColor('#F02BFE'),
            'analog_modern_full_text_color': QColor('#F3E5F5'),
            'analog_modern_full_background_alert': QColor('#5D4037'),
            'analog_modern_full_border_alert': '1px solid #E57373',
            'analog_modern_full_scale_alert_color': QColor('#FF7043'),
            'analog_modern_full_needle_alert_color': QColor('#FFCA28'),
            'analog_modern_full_center_dot_alert_color': QColor('#D32F2F'),
            'analog_modern_full_text_alert_color': QColor('#FFFFFF'),

            'semi_circle_modern_background': QColor('#4A235A'),
            'semi_circle_modern_border': '1px solid #6A357A',
            'semi_circle_modern_fill_color': QColor('#AF7AC5'),
            'semi_circle_modern_text_color': QColor('#F3E5F5'),
            'semi_circle_modern_background_alert': QColor('#5D4037'),
            'semi_circle_modern_border_alert': '1px solid #E57373',
            'semi_circle_modern_fill_alert': QColor('#D32F2F'),
            'semi_circle_modern_text_alert': QColor('#FFFFFF'),

            'standard_modern_background': QColor('#4A235A'),
            'standard_modern_border': '1px solid #6A357A',
            'standard_modern_fill_color': QColor('#AF7AC5'),
            'standard_modern_text_color': QColor('#F3E5F5'),
            'standard_modern_background_alert': QColor('#5D4037'),
            'standard_modern_border_alert': '1px solid #E57373',
            'standard_modern_fill_alert': QColor('#D32F2F'),
            'standard_modern_text_alert': QColor('#FFFFFF'),

            'linear_basic_background': QColor('#4A235A'),
            'linear_basic_border': '1px solid #6A357A',
            'linear_basic_fill_color': QColor('#AF7AC5'),
            'linear_basic_text_color': QColor('#F3E5F5'),
            'linear_basic_background_alert': QColor('#5D4037'),
            'linear_basic_border_alert': '1px solid #E57373',
            'linear_basic_fill_alert': QColor('#D32F2F'),
            'linear_basic_text_alert': QColor('#FFFFFF'),

            'flat_gauge_fill_color': QColor('#AF7AC5'),
            'flat_gauge_background_color': QColor('#4A235A'),

            'shadowed_gauge_shadow_color': QColor(0, 0, 0, 150),

            'raised_gauge_highlight_color': QColor(243, 229, 245, 30),
            'raised_gauge_shadow_color': QColor(0, 0, 0, 100),

            'inset_gauge_highlight_color': QColor(0, 0, 0, 100),
            'inset_gauge_shadow_color': QColor(243, 229, 245, 30),

            'heavy_gauge_border_color': QColor('#F02BFE'),
            'heavy_gauge_border_width': 4,

            'clean_gauge_fill_color': QColor('#F02BFE'),
            'clean_gauge_background_color': QColor('#4A235A'),
            'clean_gauge_scale_color': QColor('#7B1FA2'),

            'deep_shadow_gauge_color1': QColor(0, 0, 0, 120),
            'deep_shadow_gauge_color2': QColor(0, 0, 0, 70),
            'deep_shadow_gauge_color3': QColor(0, 0, 0, 30),

            'outline_gauge_color': QColor('#F02BFE'),

            'vintage_gauge_background_color': QColor('#4A148C'),
            'vintage_gauge_fill_color': QColor('#9C27B0'),
            'vintage_gauge_needle_color': QColor('#E1BEE7'),
            'vintage_gauge_text_color': QColor('#F3E5F5'),

            'subtle_gauge_fill_color': QColor('#7B1FA2'),
            'subtle_gauge_background_color': QColor('#311B92'),

            'fresh_gauge_fill_color': QColor('#76FF03'),
            'fresh_gauge_background_color': QColor('#31223D'),

            'bright_gauge_fill_color': QColor('#D500F9'),
            'bright_gauge_background_color': QColor('#AA00FF'),

            'bold_gauge_fill_color': QColor('#D50000'),
            'bold_gauge_text_color': QColor('#FFFFFF'),

            'groupbox_bg': QColor('#31223D'),
            'groupbox_border_width': '1px',
            'groupbox_border_style': 'solid',
            'groupbox_border_color': QColor('#6A357A'),
            'groupbox_title_color': QColor('#CE93D8'),
            'groupbox_border_radius': '8px',
            'groupbox_font_size': '9pt',
            'groupbox_font_weight': 'bold',
            'tabwidget_pane_border_radius':'8px'
        }

    def save_settings(self):
        """Saves all current settings to disk."""
        logger.debug(f"Attempting to save settings to {self.config_file}")
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as configfile:
                self.config.write(configfile)
            logger.info(f"Settings saved to {self.config_file}")
        except (IOError, PermissionError) as e:
            logger.error(f"Failed to save settings to {self.config_file} due to an I/O or permission error: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"An unexpected error occurred while saving settings: {e}", exc_info=True)

    @staticmethod
    def _format_name_for_qss(name):
        """Replaces characters not allowed in QSS object names with underscores."""
        return re.sub(r'[^a-zA-Z0-9_]', '_', name.replace(' ', '_').replace('-', '_').replace('.', '_')).strip().lower()