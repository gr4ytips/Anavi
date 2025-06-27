# data_management/settings.py
# -*- coding: utf-8 -*-
import configparser
import os
import logging
import re # ADDED: Import the 're' module
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QColor # For default theme colors if needed

logger = logging.getLogger(__name__)

class SettingsManager(QObject):
    """
    Manages application settings, reading from and writing to a config.ini file.
    Also manages theme colors parsed from QSS files.
    """
    # Signal emitted when any setting is updated via set_setting
    settings_updated = pyqtSignal(str, str, object) # section, key, value
    # Signal emitted specifically when the theme changes (file name)
    theme_changed_signal = pyqtSignal(str) # theme_file_name

    # Define default settings
    DEFAULT_SETTINGS = {
        'General': {
            'mock_mode': 'False', # Use string 'True' or 'False' for configparser
            'sampling_rate_ms': '5000', # Default 5 seconds
            'alert_sound_enabled': 'True',
            'dashboard_plot_time_range': 'Last 30 minutes',
            'detail_plot_time_range': 'Last 10 minutes',
            'current_theme': 'blue_theme.qss', # Default theme file name
            'current_gauge_type': 'Type 1 (Standard)', # Default gauge type for all displays
            'current_gauge_style': 'Default Style', # Default gauge style for all displays
            'data_log_enabled': 'True',
            'data_log_max_size_mb': '10',
            'data_log_max_rotations': '5',
            'plot_tab_time_range': 'All Data' # ADDED: Default for plot tab time range
        },
        'Thresholds': {
            # Example thresholds. These will be updated dynamically.
            # Stored as strings, converted to float when accessed.
            'HTU21D_temperature_low': '20.0',
            'HTU21D_temperature_high': '30.0',
            'HTU21D_humidity_low': '40.0',
            'HTU21D_humidity_high': '60.0',
            'BMP180_pressure_low': '990.0',
            'BMP180_pressure_high': '1030.0',
            'BH1750_light_low': '100.0',
            'BH1750_light_high': '500.0'
        },
        'Plots': {
            'plot_update_interval_sec': '5',
            'plot_HTU21D_temperature': 'True',
            'plot_HTU21D_humidity': 'True',
            'plot_BMP180_temperature': 'True',
            'plot_BMP180_pressure': 'True',
            'plot_BH1750_light': 'True'
        },
        'Precision_HTU21D': {
            'temperature': '2',
            'humidity': '2'
        },
        'Precision_BMP180': {
            'temperature': '2',
            'pressure': '2'
        },
        'Precision_BH1750': {
            'light': '2'
        }
    }

    # Default theme colors as a fallback if QSS parsing fails or theme is missing
    # These are hardcoded but will typically be overridden by QSSParser
    DEFAULT_THEME_COLORS = {
        # General UI
        'window_background': '#1A2A40', # Dark Blue
        'window_color': '#E0F2F7',     # Light Blue-Grey
        'label_color': '#E0F2F7',      # Light Blue-Grey
        'groupbox_background': '#1A2A40',
        'groupbox_border': '1px solid #3C6595', # CHANGED: Full string for border property
        'groupbox_border_radius': '8px', # As a string to match QSS
        'groupbox_title_color': '#87CEEB', # Sky Blue

        # Tab Widget
        'tab_pane_background': '#152535',
        'tab_bar_background': '#1A2A40',
        'tab_selected_background': '#152535',
        'tab_selected_text_color': '#87CEEB',
        'tab_unselected_background': '#2A3B4C',
        'tab_unselected_text_color': '#E0F2F7',
        'tab_hover_background': '#3C6595',

        # Button
        'button_background_normal': '#4682B4', # Steel Blue
        'button_text_color_normal': '#FFFFFF',
        'button_background_hover': '#5CACEE',
        'button_text_color_hover': '#FFFFFF',
        'button_background_pressed': '#3A6A9B',
        'button_text_color_pressed': '#FFFFFF',

        # ComboBox
        'combobox_background': '#2A3B4C',
        'combobox_border': '#3C6595',
        'combobox_text_color': '#E0F2F7',
        'combobox_arrow_color': '#87CEEB',
        'combobox_item_background_hover': '#3C6595',
        'combobox_item_text_color_hover': '#FFFFFF',

        # LineEdit (for thresholds)
        'lineedit_background': '#3C6595',
        'lineedit_border': '#5C85A6',
        'lineedit_text_color': '#E0F2F7',
        'lineedit_placeholder_color': '#B0C4DE',

        # ProgressBar (for gauge types)
        'progressbar_background': '#2A3B4C',
        'progressbar_border': '1px solid #4A6C8E', # CHANGED: Full string
        'progressbar_chunk_color': '#87CEEB', # Fill color for progress bar gauge
        'progressbar_text_color': '#E0F2F7',

        # Custom Gauge Drawing Colors (used by SensorDisplayWidget directly)
        'gauge_background_normal': '#1A2A40',
        'gauge_border_normal': '#3C6595',
        'gauge_fill_normal': '#87CEEB', # Normal fill color
        'gauge_text_normal': '#E0F2F7',
        'gauge_text_outline_color': '#000000', # Black outline for text
        'gauge_high_contrast_text_color': '#FFFFFF', # For text on darker backgrounds if needed

        'gauge_warning_color': '#FFA500',  # Orange for warning state
        'gauge_critical_color': '#FF0000', # Red for critical state

        'gauge_background_alert': '#5C2D2D', # Dark Red for alert
        'gauge_border_alert': '#FF6666',     # Lighter Red for alert border
        'gauge_fill_alert': '#FF0000',       # Bright Red for alert fill
        'gauge_text_alert': '#FFD700',       # Gold/Yellow for alert text

        # Analog Gauge Specific Drawing Colors
        'analog_gauge_background': '#FFFFFF', # White background for analog dial
        'analog_gauge_border': '#B0C4DE', # Light blue-grey border for dial
        'analog_gauge_scale_color': '#304050', # Dark grey for scale lines/ticks
        'analog_gauge_label_color': '#304050', # Dark grey for scale labels (numbers)
        'analog_gauge_needle_color': '#FF0000', # Red needle
        'analog_gauge_center_dot_color': '#4682B4', # Steel Blue center dot
        'analog_gauge_text_color': '#304050', # Text color for value on analog gauge
        'analog_gauge_needle_alert_color': '#FFFFFF', # White needle on alert
        
        # Matplotlib Plotting Colors (parsed and used by MatplotlibWidget)
        'plot_facecolor': '#1A2A40',
        'plot_edgecolor': '#3C6595',
        'plot_tick_color': '#E0F2F7',
        'plot_label_color': '#87CEEB',
        'plot_title_color': '#87CEEB',
        'plot_grid_color': '#304050',
        'plot_legend_facecolor': '#2A3B4C',
        'plot_legend_edgecolor': '#3C6595',
        'plot_legend_labelcolor': '#E0F2F7',
        # Line colors as a comma-separated string, MatplotlibWidget will parse this
        'plot_line_colors': '#87CEEB, #4CAF50, #FFD700, #FF0000, #A020F0, #20B2AA, #DA70D6, #FF69B4',
        
        # Fonts (as strings, to be loaded by QFontDatabase or QFont)
        'font_family': 'Inter', # General UI font
        'digital_font_family': 'Digital-7', # Specific font for digital gauge
    }


    def __init__(self, config_file='config.ini', theme_dir='themes', parent=None):
        """
        Initializes the SettingsManager.
        :param config_file: Path to the configuration file.
        :param theme_dir: Directory where QSS theme files are located.
        """
        super().__init__(parent)
        self.config_file = config_file
        self.theme_dir = theme_dir
        self.config = configparser.ConfigParser()
        self.theme_colors = {} # Stores colors parsed from the active QSS theme

        self._load_settings()
        self._load_theme_colors() # Load theme colors on startup

        logger.info(f"SettingsManager initialized. Config file: {self.config_file}, Theme directory: {self.theme_dir}")


    def _load_settings(self):
        """Loads settings from the config file, applying defaults if keys are missing."""
        logger.debug(f"SettingsManager: Loading settings from {self.config_file}.")
        if os.path.exists(self.config_file):
            try:
                self.config.read(self.config_file)
                logger.info(f"SettingsManager: Config file '{self.config_file}' loaded successfully.")
            except configparser.Error as e:
                logger.error(f"SettingsManager: Error reading config file '{self.config_file}': {e}. Using default settings.")
                # If error, clear config and proceed with defaults
                self.config = configparser.ConfigParser()
        else:
            logger.info(f"SettingsManager: Config file '{self.config_file}' not found. Creating with default settings.")

        # Apply defaults for any missing sections or keys
        for section, keys in self.DEFAULT_SETTINGS.items():
            if section not in self.config:
                self.config[section] = {}
            for key, default_value in keys.items():
                if key not in self.config[section]:
                    self.config[section][key] = default_value
                    logger.debug(f"SettingsManager: Set default for [{section}]{key} = {default_value}")
        
        # Ensure all threshold keys are initialized in the global thresholds dictionary if not already there
        # This is important for new installations
        if 'Thresholds' not in self.config:
            self.config['Thresholds'] = {}
        for key, default_value in self.DEFAULT_SETTINGS.get('Thresholds', {}).items():
            # Check if key already exists, case-insensitively, before setting default.
            # configparser keys are case-insensitive internally when accessed,
            # but preserve case for writing. We want to avoid overwriting existing values.
            found = False
            for existing_key in self.config['Thresholds'].keys():
                if existing_key.lower() == key.lower():
                    found = True
                    break
            if not found:
                self.config['Thresholds'][key] = default_value
                logger.debug(f"SettingsManager: Set default threshold for {key} = {default_value}")
        
        self.save_settings() # Save to ensure defaults are written to disk if file didn't exist or was incomplete


    def save_settings(self):
        """Saves current settings to the config file."""
        logger.info("SettingsManager: save_settings() called. Writing config to file.")
        try:
            with open(self.config_file, 'w') as configfile:
                self.config.write(configfile)
            logger.info(f"SettingsManager: Config file written to {self.config_file}.")
        except IOError as e:
            logger.error(f"SettingsManager: Error saving config file '{self.config_file}': {e}.")

    def _load_theme_colors(self):
        """Loads theme colors from the currently active QSS file."""
        current_theme_file = self.get_setting('General', 'current_theme', type=str)
        theme_path = os.path.join(self.theme_dir, current_theme_file)
        
        logger.info(f"SettingsManager: Attempting to load theme from: {theme_path}")
        
        if os.path.exists(theme_path):
            try:
                with open(theme_path, 'r') as f:
                    qss_content = f.read()
                
                # Use QSSParser's static method to extract colors
                parsed_colors = SettingsManager.parse_qss_for_colors(qss_content)
                self.theme_colors.clear()
                self.theme_colors.update(self.DEFAULT_THEME_COLORS) # Start with defaults
                self.theme_colors.update(parsed_colors) # Override with parsed colors
                
                logger.info(f"SettingsManager: Theme '{current_theme_file}' colors loaded successfully.")
                logger.debug(f"SettingsManager: Parsed theme colors (first 200 chars): {str(self.theme_colors)[:200]}...")
            except Exception as e:
                logger.error(f"SettingsManager: Error loading or parsing theme file '{theme_path}': {e}. Using DEFAULT_THEME_COLORS.", exc_info=True)
                self.theme_colors.clear()
                self.theme_colors.update(self.DEFAULT_THEME_COLORS)
        else:
            logger.warning(f"SettingsManager: Theme file '{theme_path}' not found. Using DEFAULT_THEME_COLORS.")
            self.theme_colors.clear()
            self.theme_colors.update(self.DEFAULT_THEME_COLORS)

    @staticmethod
    def parse_qss_for_colors(qss_content):
        """
        Static method to parse QSS content and extract custom color variables,
        Matplotlib specific color definitions, and full border properties.
        """
        colors = {}
        
        # Regex for generic key: value; pairs (e.g., color: #HEX;)
        pattern_generic = re.compile(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*([^;]+);', re.MULTILINE)
        
        # Regex for full border properties (e.g., border: 1px solid #HEX;)
        # Updated to capture the whole border value.
        pattern_border = re.compile(r'^\s*(border|border-top|border-right|border-bottom|border-left)\s*:\s*([^;]+);', re.MULTILINE)
        
        # Regex for border-radius properties (e.g., border-radius: 8px;)
        pattern_border_radius = re.compile(r'^\s*(border-radius)\s*:\s*([^;]+);', re.MULTILINE)

        # Helper to process matches
        def process_section_matches(content, prefix=""):
            for match in pattern_generic.finditer(content):
                key = match.group(1).strip()
                value = match.group(2).strip()
                if key not in ['border-width', 'border-style', 'border-color', 'border-radius']: # Avoid double-parsing parts of border
                    colors[prefix + key.replace('-', '_')] = value # Convert CSS-style to Python-style key
                    logger.debug(f"QSSParser: Parsed {prefix}color/value: {key} = {value}")
            
            # Now specifically capture full border properties
            for match in pattern_border.finditer(content):
                key = match.group(1).strip()
                value = match.group(2).strip()
                colors[prefix + key.replace('-', '_')] = value # Store full border string
                logger.debug(f"QSSParser: Parsed {prefix}border property: {key} = {value}")

            # Capture full border-radius properties
            for match in pattern_border_radius.finditer(content):
                key = match.group(1).strip()
                value = match.group(2).strip()
                colors[prefix + key.replace('-', '_')] = value # Store full border-radius string
                logger.debug(f"QSSParser: Parsed {prefix}border-radius property: {key} = {value}")

        # Search for global QSS properties first that might be relevant
        # Process the entire QSS content for top-level styles like QGroupBox
        process_section_matches(qss_content)

        # Regex for matplotlib section
        matplotlib_section_match = re.search(r'/\*matplotlib\*/(.*?)(?=/\*|$)', qss_content, re.DOTALL)
        if matplotlib_section_match:
            matplotlib_content = matplotlib_section_match.group(1)
            process_section_matches(matplotlib_content, prefix="plot_")

        # Regex for custom_drawing_colors section
        custom_drawing_section_match = re.search(r'/\*custom_drawing_colors\*/(.*?)(?=/\*|$)', qss_content, re.DOTALL)
        if custom_drawing_section_match:
            custom_drawing_content = custom_drawing_section_match.group(1)
            # No prefix for custom_drawing_colors as keys are already distinct
            process_section_matches(custom_drawing_content)
            
        # Specific overrides for QGroupBox properties from QSS, as they might be inherited
        # QGroupBox section parsing
        qgroupbox_match = re.search(r'QGroupBox\s*\{(.*?)\}', qss_content, re.DOTALL)
        if qgroupbox_match:
            qgroupbox_content = qgroupbox_match.group(1)
            
            # Look for border, background-color, border-radius directly within QGroupBox block
            # For border, capture the entire value (e.g., "1px solid #3C6595")
            border_match = re.search(r'border\s*:\s*([^;]+);', qgroupbox_content)
            if border_match:
                colors['groupbox_border'] = border_match.group(1).strip()
                logger.debug(f"QSSParser: Found QGroupBox border: {colors['groupbox_border']}")
            
            # For border-radius, capture the entire value (e.g., "8px")
            radius_match = re.search(r'border-radius\s*:\s*([^;]+);', qgroupbox_content)
            if radius_match:
                colors['groupbox_border_radius'] = radius_match.group(1).strip()
                logger.debug(f"QSSParser: Found QGroupBox border-radius: {colors['groupbox_border_radius']}")

            # For background-color
            bg_color_match = re.search(r'background-color\s*:\s*([^;]+);', qgroupbox_content)
            if bg_color_match:
                colors['groupbox_background'] = bg_color_match.group(1).strip()
                logger.debug(f"QSSParser: Found QGroupBox background-color: {colors['groupbox_background']}")

            # --- FIX: Removed the problematic regex for title_color_match ---
            # Instead, just capture the main 'color' property of QGroupBox, which applies to the title.
            color_match = re.search(r'color\s*:\s*([^;]+);', qgroupbox_content)
            if color_match:
                # Assign to groupbox_title_color directly, as this is the color applied to the title.
                colors['groupbox_title_color'] = color_match.group(1).strip()
                logger.debug(f"QSSParser: Found QGroupBox (main) color for title: {colors['groupbox_title_color']}")


        # Explicitly parse QProgressBar for border properties
        qprogressbar_match = re.search(r'QProgressBar\s*\{(.*?)\}', qss_content, re.DOTALL)
        if qprogressbar_match:
            qprogressbar_content = qprogressbar_match.group(1)
            border_match = re.search(r'border\s*:\s*([^;]+);', qprogressbar_content)
            if border_match:
                colors['progressbar_border'] = border_match.group(1).strip()
                logger.debug(f"QSSParser: Found QProgressBar border: {colors['progressbar_border']}")
            
            radius_match = re.search(r'border-radius\s*:\s*([^;]+);', qprogressbar_content)
            if radius_match:
                colors['progressbar_border_radius'] = radius_match.group(1).strip()
                logger.debug(f"QSSParser: Found QProgressBar border-radius: {colors['progressbar_border_radius']}")


        return colors

    def get_setting(self, section, key, type=str, default=None):
        """
        Retrieves a setting, converting it to the specified type.
        :param section: The section in the config file (e.g., 'General').
        :param key: The key within the section (e.g., 'mock_mode').
        :param type: The desired type (str, int, float, bool).
        :param default: Default value if setting is not found or conversion fails.
        :return: The setting value, converted to the specified type.
        """
        if default is None:
            # Try to get default from DEFAULT_SETTINGS if not explicitly provided
            default = self.DEFAULT_SETTINGS.get(section, {}).get(key)
            if default is not None and type != str:
                # Convert default to target type if it's not already string and target is not string
                try:
                    if type == int: default = int(default)
                    elif type == float: default = float(default)
                    elif type == bool: default = (default.lower() == 'true')
                except ValueError:
                    logger.warning(f"SettingsManager: Default value for [{section}]{key} ('{self.DEFAULT_SETTINGS[section][key]}') cannot be converted to {type.__name__}. Using raw string default.")
                    default = self.DEFAULT_SETTINGS[section][key] # Fallback to raw string default

        value = self.config.get(section, key, fallback=default)

        # Type conversion
        if type == int:
            try:
                return int(value)
            except (ValueError, TypeError):
                logger.error(f"SettingsManager: Could not convert setting [{section}]{key} value '{value}' to int. Using default {default}.")
                return default
        elif type == float:
            try:
                return float(value)
            except (ValueError, TypeError):
                logger.error(f"SettingsManager: Could not convert setting [{section}]{key} value '{value}' to float. Using default {default}.")
                return default
        elif type == bool:
            # ConfigParser reads boolean as strings 'True'/'False'
            if isinstance(value, str):
                return value.lower() == 'true'
            return bool(value) # Handle non-string booleans
        else: # Default to str
            return value

    def set_setting(self, section, key, value):
        """
        Sets a setting value and saves it to the config file.
        Emits settings_updated signal.
        :param section: The section in the config file.
        :param key: The key within the section.
        :param value: The value to set. Will be converted to string for storage.
        """
        if section not in self.config:
            self.config[section] = {}
        
        # Convert non-string values to string for configparser
        if isinstance(value, bool):
            str_value = str(value) # 'True' or 'False'
        else:
            str_value = str(value)

        old_value = self.config.get(section, key, fallback=None)

        if str_value != old_value:
            self.config[section][key] = str_value
            self.save_settings() # Save after setting
            self.settings_updated.emit(section, key, value) # Emit signal with original type
            logger.info(f"SettingsManager: Setting [{section}]{key} updated to '{str_value}'. Signal emitted.")
        else:
            logger.debug(f"SettingsManager: Setting [{section}]{key} value '{str_value}' is unchanged. Not saving or emitting.")

    def get_all_thresholds(self):
        """
        Retrieves all threshold settings, converted to appropriate types (float).
        Returns a nested dictionary with **lowercase** sensor and metric type keys.
        Example: {'htu21d': {'temperature': {'low': 20.0, 'high': 30.0}}}
        """
        thresholds_dict = {}
        # Ensure 'Thresholds' section exists to prevent KeyError
        if 'Thresholds' not in self.config:
            logger.warning("SettingsManager: 'Thresholds' section not found in config. Returning empty thresholds.")
            return thresholds_dict

        for key, value_str in self.config.items('Thresholds'):
            # Example key: 'HTU21D_temperature_low'
            parts = key.split('_')
            # Ensure there are enough parts to correctly identify sensor_type, metric_type, and limit_type
            if len(parts) >= 3 and (parts[-1] == 'low' or parts[-1] == 'high'):
                sensor_type_orig_case = parts[0]
                metric_type_orig_case = '_'.join(parts[1:-1]) 
                limit_type = parts[-1] # 'low' or 'high'

                # Convert keys to lowercase for the returned dictionary structure
                sensor_type_lower = sensor_type_orig_case.lower()
                metric_type_lower = metric_type_orig_case.lower()

                if sensor_type_lower not in thresholds_dict:
                    thresholds_dict[sensor_type_lower] = {}
                if metric_type_lower not in thresholds_dict[sensor_type_lower]:
                    thresholds_dict[sensor_type_lower][metric_type_lower] = {}
                
                try:
                    # Value might be empty string for None
                    if value_str:
                        thresholds_dict[sensor_type_lower][metric_type_lower][limit_type] = float(value_str)
                    else:
                        thresholds_dict[sensor_type_lower][metric_type_lower][limit_type] = None
                except ValueError:
                    logger.error(f"SettingsManager: Could not convert threshold value '{value_str}' for {key} to float. Skipping.", exc_info=True)
                    thresholds_dict[sensor_type_lower][metric_type_lower][limit_type] = None # Ensure it's explicitly None on error
            else:
                logger.warning(f"SettingsManager: Malformed threshold key in config: '{key}'. Skipping.")
        
        logger.debug(f"SettingsManager: Retrieved all thresholds: {thresholds_dict}")
        return thresholds_dict

    def get_theme_colors(self):
        """
        Returns the currently loaded theme colors dictionary.
        """
        if not self.theme_colors:
            logger.warning("SettingsManager: Theme colors dictionary is empty. Attempting to reload.")
            self._load_theme_colors() # Try to reload if empty
        return self.theme_colors

    def set_theme(self, theme_file_name):
        """
        Sets the active theme and reloads theme colors.
        Emits theme_changed_signal if the theme file changes.
        :param theme_file_name: The name of the QSS theme file (e.g., 'blue_theme.qss').
        """
        old_theme = self.get_setting('General', 'current_theme', type=str)
        if old_theme != theme_file_name:
            self.set_setting('General', 'current_theme', theme_file_name)
            self._load_theme_colors() # Reload colors from the new theme file
            self.theme_changed_signal.emit(theme_file_name)
            logger.info(f"SettingsManager: Theme changed to '{theme_file_name}'. Colors reloaded and signal emitted.")
        else:
            logger.debug(f"SettingsManager: Theme already '{theme_file_name}'. No change.")

    def get_available_themes(self):
        """
        Returns a list of available QSS theme files in the theme directory.
        """
        themes = []
        if os.path.exists(self.theme_dir) and os.path.isdir(self.theme_dir):
            for filename in os.listdir(self.theme_dir):
                if filename.endswith('.qss') or filename.endswith('.qss.txt'):
                    themes.append(filename)
        themes.sort()
        logger.debug(f"SettingsManager: Found available themes: {themes}")
        return themes

    @staticmethod
    def _format_name_for_qss(name):
        """
        Static helper to format a string for use in QSS object names or properties.
        Removes spaces and special characters, converts to lowercase.
        E.g., "Type 1 (Standard)" -> "type1standard" or "Default Style" -> "defaultstyle"
        """
        # Remove parentheses and their contents, then replace non-alphanumeric with empty string, convert to lowercase
        formatted = re.sub(r'\s*\(.*\)\s*', '', name) # Remove anything in parentheses
        formatted = re.sub(r'[^a-zA-Z0-9_]', '', formatted) # Remove non-alphanumeric (keep underscores)
        return formatted.lower()

    def get_sensor_configs(self):
        """
        Returns a dictionary of configured sensor types and their metrics,
        inferred from the 'Precision_' sections in settings.
        Example: {'HTU21D': ['temperature', 'humidity'], 'BMP180': ['pressure']}
        """
        sensor_configs = {}
        for section in self.config.sections():
            if section.startswith('Precision_'):
                sensor_type = section.replace('Precision_', '')
                metrics = list(self.config[section].keys())
                sensor_configs[sensor_type] = metrics
        
        logger.debug(f"SettingsManager: Inferred sensor configurations: {sensor_configs}")
        return sensor_configs

    @staticmethod # ADDED: Make this a static method
    def get_unit_for_metric(sensor_type, metric_type):
        """
        Returns the unit for a given metric type, now including sensor_type for context.
        This is now a static method of SettingsManager, so it can be called directly
        without needing a SettingsManager instance.
        """
        # This mapping should ideally be comprehensive based on your sensors
        # Using ASCII-safe units to prevent encoding errors
        unit_map = {
            "temperature": "\u00b0C", # Changed from "°C"
            "humidity": "%",
            "pressure": "hPa",
            "light": "lx"
        }
        unit = unit_map.get(metric_type.lower(), "")
        logger.debug(f"SettingsManager: get_unit_for_metric called for '{sensor_type}-{metric_type}', returning '{unit}'.")
        return unit

