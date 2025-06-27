# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox, QSizePolicy, QSpacerItem, QFormLayout
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QFontDatabase, QColor # Import QColor

import logging

from data_management.settings import SettingsManager # For accessing static _format_name_for_qss
from widgets.sensor_display import SensorDisplayWidget # For preview gauge

logger = logging.getLogger(__name__)

class SettingsTab(QWidget):
    """
    Settings tab allowing users to configure application parameters,
    including sensor settings, themes, and alert thresholds.
    """
    # Signal emitted when UI customization (gauge type/style) changes.
    # This is re-emitted by AnaviSensorUI to MainWindow.
    ui_customization_changed = pyqtSignal(str, str) # Arguments: gauge_type (str), gauge_style (str)
    
    # Signal emitted when the theme changes.
    # This is re-emitted by AnaviSensorUI to MainWindow.
    theme_changed = pyqtSignal(str) # Argument: theme_file_name (str)

    # Signal emitted when thresholds are updated by the user.
    # This is re-emitted by AnaviSensorUI to MainWindow.
    thresholds_updated = pyqtSignal(dict) # Argument: full_thresholds_dict

    def __init__(self, settings_manager, main_window, theme_colors, initial_gauge_type, initial_gauge_style, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsTab") # Added object name for QSS
        self.settings_manager = settings_manager
        self.main_window = main_window # Store reference to MainWindow for global access
        self.theme_colors = theme_colors # Reference to the global theme colors
        
        # Store initial gauge type and style from main window for preview gauge setup
        self.initial_gauge_type = initial_gauge_type
        self.initial_gauge_style = initial_gauge_style

        self.preview_gauge = None # Will be initialized in setup_ui

        self.setup_ui()
        self.load_settings_to_ui()
        self.connect_signals()
        logger.info("SettingsTab initialized.")

    def setup_ui(self):
        """Sets up the layout and widgets for the settings tab."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # --- General Settings Group ---
        general_group = QGroupBox("General Settings")
        general_group.setObjectName("SettingsGroupBox")
        general_layout = QFormLayout(general_group)
        general_layout.setContentsMargins(10, 20, 10, 10)
        general_layout.setSpacing(10)

        self.mock_mode_checkbox = QCheckBox("Enable Mock Sensor Data")
        self.mock_mode_checkbox.setObjectName("SettingsCheckBox")
        general_layout.addRow(self.mock_mode_checkbox)

        self.sampling_rate_input = QLineEdit()
        self.sampling_rate_input.setObjectName("SettingsLineEdit")
        self.sampling_rate_input.setPlaceholderText("e.g., 5000 (ms)")
        general_layout.addRow(QLabel("Sensor Sampling Rate (ms):"), self.sampling_rate_input)

        self.alert_sound_checkbox = QCheckBox("Enable Alert Sounds")
        self.alert_sound_checkbox.setObjectName("SettingsCheckBox")
        general_layout.addRow(self.alert_sound_checkbox)

        self.current_theme_combo = QComboBox()
        self.current_theme_combo.setObjectName("SettingsComboBox")
        self.populate_themes()
        general_layout.addRow(QLabel("Application Theme:"), self.current_theme_combo)

        main_layout.addWidget(general_group)

        # --- UI Customization Group ---
        ui_custom_group = QGroupBox("UI Customization")
        ui_custom_group.setObjectName("SettingsGroupBox")
        
        # This will be the overall layout for the content inside UI Customization group
        # It will hold the left column (comboboxes) and the right column (preview gauge) horizontally
        ui_custom_overall_layout = QHBoxLayout(ui_custom_group) 
        ui_custom_overall_layout.setContentsMargins(10, 20, 10, 10)
        ui_custom_overall_layout.setSpacing(10)

        # Left Column for Gauge Type/Style Comboboxes
        left_column_layout = QVBoxLayout()
        left_column_layout.setContentsMargins(0,0,0,0)
        left_column_layout.setSpacing(10) # Spacing between the horizontal rows of labels/comboboxes

        # Gauge Display Type Row (Label and ComboBox side-by-side)
        gauge_type_h_layout = QHBoxLayout()
        gauge_type_h_layout.addWidget(QLabel("Gauge Display Type:"))
        self.gauge_type_combo = QComboBox()
        self.gauge_type_combo.setObjectName("SettingsComboBox")
        self.gauge_type_combo.addItems([
            "Type 1 (Standard)", 
            "Type 2 (Compact)", 
            "Type 3 (Digital)", 
            "Type 4 (Analog - Basic)",
            "Type 5 (Analog - Full)",
            "Type 6 (Progress Bar - Horizontal)",
            "Type 7 (Progress Bar - Vertical)"
        ])
        self.gauge_type_combo.setFixedWidth(200) # Explicitly set fixed width
        gauge_type_h_layout.addWidget(self.gauge_type_combo)
        gauge_type_h_layout.addStretch(1) # Push to left, ensuring combobox respects fixed width
        left_column_layout.addLayout(gauge_type_h_layout)

        # Gauge Display Style Row (Label and ComboBox side-by-side)
        gauge_style_h_layout = QHBoxLayout()
        gauge_style_h_layout.addWidget(QLabel("Gauge Display Style:"))
        self.gauge_style_combo = QComboBox()
        self.gauge_style_combo.setObjectName("SettingsComboBox")
        self.gauge_style_combo.addItems([
            "Default Style",
            "Style 1 (Modern)",
            "Style 2 (Classic)",
            "Style 3 (Minimal)",
            "Style 4 (Flat)",
            "Style 5 (Heavy Border)",
            "Style 6 (Gradient Fill)",
            "Style 7 (Subtle Glow)",
            "Style 8 (Shadowed)",
            "Style 9 (3D Effect)",
            "Style 10 (Raised)",
            "Style 11 (Sunken)",
            "Style 12 (Rounded)",
            "Style 13 (Bold Outline)"
        ])
        self.gauge_style_combo.setFixedWidth(200) # Explicitly set fixed width
        gauge_style_h_layout.addWidget(self.gauge_style_combo)
        gauge_style_h_layout.addStretch(1) # Push to left, ensuring combobox respects fixed width
        left_column_layout.addLayout(gauge_style_h_layout)

        left_column_layout.addStretch(1) # Push content to top left within its column

        ui_custom_overall_layout.addLayout(left_column_layout) # Add the left column to the overall horizontal layout

        # Right side: Preview Gauge (Moved to the right column)
        preview_gauge_group = QGroupBox("Gauge Preview")
        preview_gauge_group.setObjectName("PreviewGaugeGroupBox")
        preview_gauge_layout = QVBoxLayout(preview_gauge_group)
        # Pass a mock dict for thresholds for preview purposes
        # These will be updated later by update_preview_gauge_thresholds using real data.
        mock_thresholds = {'low': 20.0, 'high': 30.0} 
        self.preview_gauge = SensorDisplayWidget(
            title="Temperature Preview",
            unit="\u00b0C", # Changed from "°C" to "degC"
            thresholds=mock_thresholds, # Pass mock thresholds
            metric_type="temperature",
            sensor_category="HTU21D",
            main_window=self.main_window,
            theme_colors=self.theme_colors,
            initial_gauge_type=self.initial_gauge_type, # Use the initial values from __init__
            initial_gauge_style=self.initial_gauge_style, # Use the initial values from __init__
            is_preview=True, # Set is_preview to True
            parent=preview_gauge_group
        )
        # Initially set a value for the preview gauge - this will be overwritten later by update_preview_gauge
        self.preview_gauge.update_value(25.5) 
        preview_gauge_layout.addWidget(self.preview_gauge)
        
        ui_custom_overall_layout.addWidget(preview_gauge_group) # Add the preview gauge group to the overall horizontal layout

        main_layout.addWidget(ui_custom_group) # Add the UI Customization group to the main tab layout

        # --- Threshold Settings Group ---
        threshold_group = QGroupBox("Alert Thresholds")
        threshold_group.setObjectName("SettingsGroupBox")
        self.threshold_layout = QFormLayout(threshold_group)
        self.threshold_layout.setContentsMargins(10, 20, 10, 10)
        self.threshold_layout.setSpacing(10)
        
        # This will be populated dynamically based on available sensors/metrics
        self.threshold_inputs = {} # Store references to QLineEdit widgets {metric_key: {'low': QLineEdit, 'high': QLineEdit}}
        self.populate_threshold_inputs() # Call method to create inputs

        main_layout.addWidget(threshold_group)
        
        # --- Data Logging Settings Group ---
        data_logging_group = QGroupBox("Data Logging Settings")
        data_logging_group.setObjectName("SettingsGroupBox")
        data_logging_layout = QFormLayout(data_logging_group)
        data_logging_layout.setContentsMargins(10, 20, 10, 10)
        data_logging_layout.setSpacing(10)

        self.data_log_enabled_checkbox = QCheckBox("Enable Data Logging to CSV")
        self.data_log_enabled_checkbox.setObjectName("SettingsCheckBox")
        data_logging_layout.addRow(self.data_log_enabled_checkbox)

        self.data_log_max_size_input = QLineEdit()
        self.data_log_max_size_input.setObjectName("SettingsLineEdit")
        self.data_log_max_size_input.setPlaceholderText("e.g., 10 (MB)")
        data_logging_layout.addRow(QLabel("Max Log File Size (MB):"), self.data_log_max_size_input)

        self.data_log_max_rotations_input = QLineEdit()
        self.data_log_max_rotations_input.setObjectName("SettingsLineEdit")
        self.data_log_max_rotations_input.setPlaceholderText("e.g., 5 (files)")
        data_logging_layout.addRow(QLabel("Max Daily Rotated Files:"), self.data_log_max_rotations_input)

        main_layout.addWidget(data_logging_group)

        main_layout.addStretch(1) # Push all groups to the top

    def populate_themes(self):
        """Populates the theme combo box with available QSS files."""
        self.current_theme_combo.clear()
        themes = self.settings_manager.get_available_themes()
        self.current_theme_combo.addItems(themes)
        
        # Set current theme selection
        current_theme_file = self.settings_manager.get_setting('General', 'current_theme', type=str)
        index = self.current_theme_combo.findText(current_theme_file, Qt.MatchExactly)
        if index != -1:
            self.current_theme_combo.setCurrentIndex(index)
        else:
            logger.warning(f"SettingsTab: Current theme '{current_theme_file}' not found in available themes. Defaulting to first item.")
            if self.current_theme_combo.count() > 0:
                self.current_theme_combo.setCurrentIndex(0)

    def populate_threshold_inputs(self):
        """
        Dynamically creates QLineEdit widgets for threshold settings
        based on configured sensors and metrics.
        """
        # Clear existing inputs
        for i in reversed(range(self.threshold_layout.count())): 
            widget_item = self.threshold_layout.itemAt(i)
            if widget_item:
                widget = widget_item.widget()
                if widget:
                    self.threshold_layout.removeWidget(widget)
                    widget.deleteLater() # Safely delete widget
                else: # Could be a layout within the form layout
                    layout = widget_item.layout()
                    if layout:
                        # Recursively clear layout items
                        for j in reversed(range(layout.count())):
                            item = layout.itemAt(j)
                            if item:
                                if item.widget():
                                    item.widget().deleteLater()
                                elif item.layout():
                                    self._clear_layout(item.layout())
                                layout.removeItem(item)
                        self.threshold_layout.removeItem(widget_item)
                        layout.deleteLater()
            
        self.threshold_inputs = {} # Reset dictionary

        configured_sensors = self.main_window.settings_manager.get_sensor_configs()
        # Ensure consistent order (same as dashboard/details tab)
        display_order = ['HTU21D', 'BMP180', 'BH1750'] 

        for sensor_type in display_order:
            if sensor_type in configured_sensors:
                for metric_type in configured_sensors[sensor_type]:
                    metric_key = f"{sensor_type}_{metric_type}"
                    # This unit is for the label only, not for data storage.
                    # It still needs to be ASCII-safe if the issue persists in string literals.
                    unit = self.main_window.settings_manager.get_unit_for_metric(sensor_type, metric_type)

                    label_text = f"{sensor_type} {metric_type.capitalize()} ({unit}):"
                    label = QLabel(label_text)
                    label.setObjectName("ThresholdLabel")

                    low_input = QLineEdit()
                    low_input.setPlaceholderText("Low")
                    low_input.setObjectName(f"ThresholdInput_{metric_key}_low")
                    # Use the validator from main_window
                    if hasattr(self.main_window, 'float_validator'): # Check if validator exists
                        low_input.setValidator(self.main_window.float_validator) 
                    else:
                        logger.warning("SettingsTab: float_validator not found on main_window during populate_threshold_inputs.")
                    
                    high_input = QLineEdit()
                    high_input.setPlaceholderText("High")
                    high_input.setObjectName(f"ThresholdInput_{metric_key}_high")
                    # Use the validator from main_window
                    if hasattr(self.main_window, 'float_validator'): # Check if validator exists
                        high_input.setValidator(self.main_window.float_validator) 
                    else:
                        logger.warning("SettingsTab: float_validator not found on main_window during populate_threshold_inputs.")

                    # Store references
                    self.threshold_inputs[metric_key] = {'low': low_input, 'high': high_input}

                    # Add to form layout
                    h_layout = QHBoxLayout()
                    h_layout.addWidget(low_input)
                    h_layout.addWidget(high_input)
                    self.threshold_layout.addRow(label, h_layout)
                    
                    logger.debug(f"SettingsTab: Created threshold inputs for {metric_key}.")

    def _clear_layout(self, layout):
        """Recursively clears all widgets and layouts from a layout."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget() is not None:
                    item.widget().deleteLater()
                elif item.layout() is not None:
                    self._clear_layout(item.layout())
                # Only remove if it was successfully taken
                if item:
                    layout.removeItem(item)

    def load_settings_to_ui(self):
        """Loads current settings from SettingsManager and populates UI widgets."""
        logger.info("SettingsTab: Loading settings to UI.")
        self.mock_mode_checkbox.setChecked(self.settings_manager.get_setting('General', 'mock_mode', type=bool))
        self.sampling_rate_input.setText(str(self.settings_manager.get_setting('General', 'sampling_rate_ms', type=int)))
        self.alert_sound_checkbox.setChecked(self.settings_manager.get_setting('General', 'alert_sound_enabled', type=bool))

        # Set theme combo box
        current_theme_file = self.settings_manager.get_setting('General', 'current_theme', type=str)
        index = self.current_theme_combo.findText(current_theme_file, Qt.MatchExactly)
        if index != -1:
            self.current_theme_combo.setCurrentIndex(index)

        # Set gauge type and style combo boxes
        current_gauge_type = self.settings_manager.get_setting('General', 'current_gauge_type', type=str)
        index_type = self.gauge_type_combo.findText(current_gauge_type, Qt.MatchExactly)
        if index_type != -1:
            self.gauge_type_combo.setCurrentIndex(index_type)

        current_gauge_style = self.settings_manager.get_setting('General', 'current_gauge_style', type=str)
        index_style = self.gauge_style_combo.findText(current_gauge_style, Qt.MatchExactly)
        if index_style != -1:
            self.gauge_style_combo.setCurrentIndex(index_style)

        # Load data logging settings
        self.data_log_enabled_checkbox.setChecked(self.settings_manager.get_setting('General', 'data_log_enabled', type=bool))
        self.data_log_max_size_input.setText(str(self.settings_manager.get_setting('General', 'data_log_max_size_mb', type=float)))
        self.data_log_max_rotations_input.setText(str(self.settings_manager.get_setting('General', 'data_log_max_rotations', type=int)))


        self.update_threshold_display() # Load thresholds into their respective input fields
        self.update_preview_gauge() # Update preview gauge with current UI settings
        logger.debug("SettingsTab: UI populated with settings.")


    def update_threshold_display(self):
        """
        Loads the current thresholds from SettingsManager and updates the QLineEdit widgets.
        This is called on tab change and after initial load.
        """
        all_thresholds = self.settings_manager.get_all_thresholds()
        logger.debug(f"SettingsTab: Updating threshold display with: {all_thresholds}")

        for metric_key, inputs in self.threshold_inputs.items():
            parts = metric_key.split('_')
            sensor_type = parts[0].lower() # Convert to lowercase for lookup
            metric_type = '_'.join(parts[1:]).lower() # Convert to lowercase for lookup (handles multi-word metrics)
            
            # Access the nested dictionary using the lowercase keys
            metric_thresholds = all_thresholds.get(sensor_type, {}).get(metric_type, {})
            
            low_thr = metric_thresholds.get('low')
            high_thr = metric_thresholds.get('high')

            if low_thr is not None:
                inputs['low'].setText(f"{low_thr:.1f}") # Format for display
            else:
                inputs['low'].clear()
            
            if high_thr is not None:
                inputs['high'].setText(f"{high_thr:.1f}") # Format for display
            else:
                inputs['high'].clear()
            logger.debug(f"SettingsTab: Displayed thresholds for {metric_key}: Low={inputs['low'].text()}, High={inputs['high'].text()}.")
        
        # Ensure preview gauge also has the latest thresholds applied
        self.update_preview_gauge_thresholds()


    def connect_signals(self):
        """Connects UI widget signals to their respective handler methods."""
        logger.debug("SettingsTab: Connecting signals.")
        self.mock_mode_checkbox.stateChanged.connect(lambda state: self.settings_manager.set_setting('General', 'mock_mode', state == Qt.Checked))
        self.sampling_rate_input.editingFinished.connect(self._save_sampling_rate)
        self.alert_sound_checkbox.stateChanged.connect(lambda state: self.settings_manager.set_setting('General', 'alert_sound_enabled', state == Qt.Checked))
        self.current_theme_combo.currentIndexChanged.connect(self._save_current_theme)

        self.gauge_type_combo.currentIndexChanged.connect(self._save_gauge_settings)
        self.gauge_style_combo.currentIndexChanged.connect(self._save_gauge_settings)
        
        # Connect threshold input fields to save method
        for metric_key, inputs in self.threshold_inputs.items():
            inputs['low'].editingFinished.connect(lambda mk=metric_key: self._save_threshold(mk, 'low'))
            inputs['high'].editingFinished.connect(lambda mk=metric_key: self._save_threshold(mk, 'high'))

        # Connect data logging inputs
        self.data_log_enabled_checkbox.stateChanged.connect(lambda state: self.settings_manager.set_setting('General', 'data_log_enabled', state == Qt.Checked))
        self.data_log_max_size_input.editingFinished.connect(self._save_data_log_max_size)
        self.data_log_max_rotations_input.editingFinished.connect(self._save_data_log_max_rotations)

        logger.debug("SettingsTab: Signals connected.")


    def _save_sampling_rate(self):
        """Saves the sampling rate setting."""
        try:
            rate_ms = int(self.sampling_rate_input.text())
            if rate_ms <= 0:
                raise ValueError("Sampling rate must be a positive integer.")
            self.settings_manager.set_setting('General', 'sampling_rate_ms', rate_ms)
            logger.debug(f"SettingsTab: Saved sampling rate: {rate_ms} ms.")
        except ValueError as e:
            self.sampling_rate_input.setText(str(self.settings_manager.get_setting('General', 'sampling_rate_ms', type=int))) # Revert to last valid
            self.main_window.show_status_message(f"Invalid sampling rate: {e}. Please enter a positive integer.", "error")
            logger.error(f"SettingsTab: Invalid sampling rate input: {self.sampling_rate_input.text()}. Error: {e}")

    def _save_current_theme(self):
        """Saves the selected theme and triggers theme change."""
        selected_theme = self.current_theme_combo.currentText()
        self.settings_manager.set_theme(selected_theme) # SettingsManager will handle reload and signal
        logger.debug(f"SettingsTab: Saved current theme: {selected_theme}.")
        # No need to manually emit theme_changed here, SettingsManager already does it.
        # AnaviSensorUI's theme_changed slot is connected to SettingsManager's theme_changed_signal

    def _save_gauge_settings(self):
        """Saves the selected gauge type and style, and propagates the change."""
        selected_type = self.gauge_type_combo.currentText()
        selected_style = self.gauge_style_combo.currentText()
        # Set gauge type and style in settings manager
        self.settings_manager.set_setting('General', 'current_gauge_type', selected_type)
        self.settings_manager.set_setting('General', 'current_gauge_style', selected_style)
        logger.debug(f"SettingsTab: Saved gauge settings: Type='{selected_type}', Style='{selected_style}'.")
        
        # Propagate this change to AnaviSensorUI which then tells other tabs
        self.ui_customization_changed.emit(selected_type, selected_style)
        self.update_preview_gauge() # Update the preview gauge immediately
        logger.debug("SettingsTab: Emitted ui_customization_changed signal and updated preview gauge.")


    def _save_threshold(self, metric_key, limit_type):
        """
        Saves an individual threshold value.
        :param metric_key: e.g., 'HTU21D_temperature'
        :param limit_type: 'low' or 'high'
        """
        input_widget = self.threshold_inputs[metric_key][limit_type]
        full_config_key = f"{metric_key}_{limit_type}"
        
        try:
            value_str = input_widget.text().strip()
            if not value_str: # Allow clearing threshold by leaving empty
                actual_value = None
            else:
                actual_value = float(value_str)
            
            # Retrieve existing thresholds to create the full updated dictionary
            current_all_thresholds = self.settings_manager.get_all_thresholds()
            
            parts = metric_key.split('_')
            sensor_type_orig_case = parts[0] # Keep original case for saving to config.ini
            sensor_type_lower = parts[0].lower() # Lowercase for dictionary lookup
            metric_type_lower = '_'.join(parts[1:]).lower() # Lowercase for dictionary lookup
            
            # Ensure the structure exists using lowercase keys for the dictionary
            if sensor_type_lower not in current_all_thresholds:
                current_all_thresholds[sensor_type_lower] = {}
            if metric_type_lower not in current_all_thresholds[sensor_type_lower]:
                current_all_thresholds[sensor_type_lower][metric_type_lower] = {}
            
            current_all_thresholds[sensor_type_lower][metric_type_lower][limit_type] = actual_value

            # Save the individual setting to config.ini. Use the original casing for the key.
            # config.ini keys are HTU21D_temperature_low, not htu21d_temperature_low
            self.settings_manager.set_setting('Thresholds', full_config_key, str(actual_value) if actual_value is not None else '')
            logger.debug(f"SettingsTab: Saved threshold [{full_config_key}] = {actual_value}.")
            
            # Emit the full updated thresholds dictionary
            self.thresholds_updated.emit(current_all_thresholds)
            logger.debug("SettingsTab: Emitted thresholds_updated signal with full thresholds.")
            
            # Update the preview gauge with the newly saved thresholds
            self.update_preview_gauge_thresholds()

        except ValueError as e:
            self.main_window.show_status_message(f"Invalid threshold for {metric_key} {limit_type}: {e}. Please enter a number or leave empty.", "error")
            logger.error(f"SettingsTab: Invalid threshold input for {full_config_key}: '{input_widget.text()}'. Error: {e}")
            # Revert input field to last valid saved value
            current_value = self.settings_manager.get_setting('Thresholds', full_config_key, type=float, default=None)
            input_widget.setText(f"{current_value:.1f}" if current_value is not None else "")

    def update_preview_gauge(self):
        """Updates the preview gauge based on current UI customization settings."""
        if self.preview_gauge:
            current_type = self.gauge_type_combo.currentText()
            current_style = self.gauge_style_combo.currentText()
            
            self.preview_gauge.update_theme_colors(self.theme_colors) # Ensure correct theme colors are used
            self.preview_gauge.update_gauge_display_type_and_style(current_type, current_style)
            
            preview_value = 25.0 # Default mock value

            # --- FIX: Check if data_store exists AND latest_data is not None ---
            if hasattr(self.main_window, 'data_store') and self.main_window.data_store is not None:
                latest_data = self.main_window.data_store.get_latest_data()
                if latest_data is not None: # Check if get_latest_data actually returned data
                    htu21d_temp_data = latest_data.get('HTU21D', {}).get('temperature', {})
                    if 'value' in htu21d_temp_data:
                        preview_value = htu21d_temp_data['value']
                        logger.debug(f"SettingsTab: Using live data for preview gauge: {preview_value}")
                    else:
                        logger.debug("SettingsTab: Live HTU21D temperature data not available within latest_data. Using mock value.")
                else:
                    logger.debug("SettingsTab: data_store.get_latest_data() returned None. Using mock value.")
            else:
                logger.debug("SettingsTab: data_store not available on main_window for preview. Using mock value.")

            self.preview_gauge.update_value(preview_value)
            logger.debug("SettingsTab: Preview gauge updated.")

    def update_preview_gauge_thresholds(self):
        """Updates the thresholds on the preview gauge."""
        if self.preview_gauge:
            # The preview gauge is hardcoded to show HTU21D Temperature
            all_thresholds = self.settings_manager.get_all_thresholds()
            # Ensure lowercase lookup for preview gauge thresholds
            htu21d_temp_thresholds = all_thresholds.get('htu21d', {}).get('temperature', {})
            self.preview_gauge.update_thresholds(htu21d_temp_thresholds)
            logger.debug(f"SettingsTab: Preview gauge thresholds updated: {htu21d_temp_thresholds}")

    def update_theme_colors(self, new_theme_colors):
        """
        Updates the theme colors for this tab and its contained widgets,
        including the preview gauge.
        """
        logger.debug("SettingsTab: Updating theme colors and re-polishing.")
        self.theme_colors.clear() # Clear old colors
        self.theme_colors.update(new_theme_colors) # Update with new colors

        # Re-polish the tab itself to apply QSS
        self.style().polish(self)
        for group_box in self.findChildren(QGroupBox):
            group_box.style().polish(group_box)
        for label in self.findChildren(QLabel):
            label.style().polish(label)
        for line_edit in self.findChildren(QLineEdit):
            line_edit.style().polish(line_edit)
        for combo_box in self.findChildren(QComboBox):
            combo_box.style().polish(combo_box)
        for check_box in self.findChildren(QCheckBox):
            check_box.style().polish(check_box)

        # Propagate theme colors to the preview gauge
        if self.preview_gauge:
            self.preview_gauge.update_theme_colors(self.theme_colors)

        logger.debug("SettingsTab: Tab re-polished to apply new theme QSS.")

    def _save_data_log_max_size(self):
        """Saves the data log max size setting."""
        try:
            max_size_mb = float(self.data_log_max_size_input.text())
            if max_size_mb <= 0:
                raise ValueError("Max log file size must be a positive number.")
            self.settings_manager.set_setting('General', 'data_log_max_size_mb', max_size_mb)
            logger.debug(f"SettingsTab: Saved data log max size: {max_size_mb} MB.")
        except ValueError as e:
            self.data_log_max_size_input.setText(str(self.settings_manager.get_setting('General', 'data_log_max_size_mb', type=float))) # Revert
            self.main_window.show_status_message(f"Invalid max log file size: {e}. Please enter a positive number.", "error")
            logger.error(f"SettingsTab: Invalid data log max size input: {self.data_log_max_size_input.text()}. Error: {e}")

    def _save_data_log_max_rotations(self):
        """Saves the data log max rotations setting."""
        try:
            max_rotations = int(self.data_log_max_rotations_input.text())
            if max_rotations <= 0:
                raise ValueError("Max daily rotated files must be a positive integer.")
            self.settings_manager.set_setting('General', 'data_log_max_rotations', max_rotations)
            logger.debug(f"SettingsTab: Saved data log max rotations: {max_rotations}.")
        except ValueError as e:
            self.data_log_max_rotations_input.setText(str(self.settings_manager.get_setting('General', 'data_log_max_rotations', type=int))) # Revert
            self.main_window.show_status_message(f"Invalid max daily rotated files: {e}. Please enter a positive integer.", "error")
            logger.error(f"SettingsTab: Invalid max daily rotated files: {self.data_log_max_rotations_input.text()}. Error: {e}")

