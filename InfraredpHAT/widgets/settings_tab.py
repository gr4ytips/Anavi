# widgets/settings_tab.py
# -*- coding: utf-8 -*-
import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, 
                             QLineEdit, QPushButton, QComboBox, QCheckBox,
                             QSizePolicy, QScrollArea, QFormLayout, QSpacerItem)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIntValidator, QDoubleValidator, QFont, QFontDatabase, QColor
from functools import partial
import re

from data_management.settings import SettingsManager
from widgets.sensor_display import SensorDisplayWidget

logger = logging.getLogger(__name__)

class SettingsTab(QWidget):
    settings_changed = pyqtSignal()
    # --- FIX: Re-add thresholds_updated_signal ---
    thresholds_updated_signal = pyqtSignal(dict) 
    # --- END FIX ---

    ui_customization_changed = pyqtSignal(str, str) 
    theme_changed = pyqtSignal(str) 

    def __init__(self, settings_manager, theme_colors,
                 main_window, data_store, thresholds, 
                 parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsTab")

        self.settings_manager = settings_manager
        self.theme_colors = theme_colors
        self.main_window = main_window
        self.data_store = data_store
        self.thresholds = thresholds 

        self.sensor_config_widgets = {}
        self.precision_line_edits = {}
        self.threshold_line_edits = {} 
        self.range_inputs = {}

        self.setup_ui()
        self.setup_connections()
        self.load_settings() 
        logger.info("SettingsTab initialized.")

    def setup_ui(self):
        """Sets up the layout and initial widgets for the Settings tab."""
        main_layout = QVBoxLayout(self)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(15)
        content_layout.setAlignment(Qt.AlignTop)

        content_widget.setProperty("class", "tab-page") 

        general_settings_group = QGroupBox("General Settings")
        general_settings_group.setObjectName("GeneralSettingsGroup")
        general_form_layout = QFormLayout(general_settings_group)
        self.populate_general_settings_section(general_form_layout)
        content_layout.addWidget(general_settings_group)

        sensor_config_group = QGroupBox("Sensor Presence & Precision")
        sensor_config_group.setObjectName("SensorConfigGroup")
        self.sensor_config_layout = QVBoxLayout(sensor_config_group)
        self.sensor_config_layout.setContentsMargins(10, 20, 10, 10) 
        self.sensor_config_layout.setSpacing(10) 
        content_layout.addWidget(sensor_config_group)
        
        self.sensor_ranges_group = QGroupBox("Sensor Display Ranges")
        self.sensor_ranges_group.setObjectName("SensorRangesGroup")
        self.sensor_ranges_layout = QVBoxLayout(self.sensor_ranges_group)
        self.sensor_ranges_layout.setContentsMargins(10, 20, 10, 10)
        self.sensor_ranges_layout.setSpacing(5)
        content_layout.addWidget(self.sensor_ranges_group)

        thresholds_group = QGroupBox("Alert Thresholds")
        thresholds_group.setObjectName("ThresholdsGroup")
        self.thresholds_layout = QVBoxLayout(thresholds_group)
        self.thresholds_layout.setContentsMargins(10, 20, 10, 10)
        self.thresholds_layout.setSpacing(5)
        content_layout.addWidget(thresholds_group)

        self.populate_all_sensor_sections() 
        
        button_bar_widget = QWidget()
        button_bar_widget.setObjectName("ButtonBar")
        button_layout = QHBoxLayout(button_bar_widget)
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.addStretch(1)
        
        self.apply_button = QPushButton("Apply All Settings")
        self.apply_button.setObjectName("SettingsApplyButton")
        button_layout.addWidget(self.apply_button)
        content_layout.addWidget(button_bar_widget)
        
        content_layout.addStretch(1) 

    def populate_general_settings_section(self, layout):
        self.mock_mode_checkbox = QCheckBox("Enable Mock Data Mode")
        layout.addRow(self.mock_mode_checkbox)

        self.sampling_rate_edit = QLineEdit()
        self.sampling_rate_edit.setValidator(QIntValidator()) 
        layout.addRow("Sensor Sampling Rate (ms):", self.sampling_rate_edit)

        self.data_store_max_points_edit = QLineEdit()
        self.data_store_max_points_edit.setValidator(QIntValidator()) 
        layout.addRow("Data Store Max Points:", self.data_store_max_points_edit)
        
        self.alert_sound_checkbox = QCheckBox("Enable Alert Sound")
        layout.addRow(self.alert_sound_checkbox)
        
        self.data_log_enabled_checkbox = QCheckBox("Enable Sensor Data Logging to File")
        layout.addRow(self.data_log_enabled_checkbox)

    def _clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()
                elif item.layout() is not None:
                    self._clear_layout(item.layout())

    def populate_all_sensor_sections(self):
        logger.debug("SettingsTab: Populating all sensor sections.")
        self.populate_sensor_config_section()
        self.populate_sensor_ranges_section()
        self.populate_threshold_section()
        self.load_settings() 

    def populate_sensor_config_section(self):
        logger.debug("SettingsTab: Populating sensor config section.")
        self._clear_layout(self.sensor_config_layout)
        self.sensor_config_widgets.clear()
        self.precision_line_edits.clear()

        all_sensor_metric_configs = self.settings_manager.get_all_metric_info()

        if not all_sensor_metric_configs:
            self.sensor_config_layout.addWidget(QLabel("No sensors configured."))
            return

        for sensor_type, metrics in sorted(all_sensor_metric_configs.items()):
            sensor_group_box = QGroupBox(f"{sensor_type} Configuration")
            self.sensor_config_layout.addWidget(sensor_group_box)
            
            group_layout = QFormLayout() 
            sensor_group_box.setLayout(group_layout)

            sensor_present_key = f"{sensor_type.lower()}_present"
            sensor_checkbox = QCheckBox(f"Enable {sensor_type} Sensor")
            sensor_checkbox.setObjectName(f"SensorPresentCheckbox_{SettingsManager._format_name_for_qss(sensor_type)}")
            sensor_checkbox.stateChanged.connect(partial(self._on_sensor_presence_changed, sensor_type))
            group_layout.addRow(sensor_checkbox) 
            self.sensor_config_widgets[sensor_present_key] = sensor_checkbox 

            for metric_type in sorted(metrics.keys()):
                h_layout = QHBoxLayout()
                
                metric_present_key = f"{sensor_type.lower()}_{metric_type.lower()}_present"
                metric_checkbox = QCheckBox(f"Enable {metric_type.capitalize()}")
                metric_checkbox.setObjectName(f"MetricPresentCheckbox_{SettingsManager._format_name_for_qss(sensor_type)}_{SettingsManager._format_name_for_qss(metric_type)}")
                metric_checkbox.stateChanged.connect(partial(self._on_metric_presence_changed, sensor_type, metric_type))
                h_layout.addWidget(metric_checkbox)
                self.sensor_config_widgets[metric_present_key] = metric_checkbox 

                h_layout.addStretch(1)

                precision_edit = QLineEdit()
                precision_edit.setValidator(QIntValidator())
                precision_edit.setFixedWidth(50)
                precision_edit.editingFinished.connect(partial(self._on_precision_changed, sensor_type, metric_type, precision_edit))
                self.precision_line_edits[(sensor_type, metric_type)] = precision_edit 
                
                h_layout.addWidget(precision_edit)
                h_layout.addWidget(QLabel("decimals"))
                
                group_layout.addRow(f"  — {metric_type.capitalize()}:", h_layout) 

    def populate_sensor_ranges_section(self):
        logger.debug("SettingsTab: Populating sensor ranges section.")
        self._clear_layout(self.sensor_ranges_layout)
        self.range_inputs.clear()

        sensor_configs = self.settings_manager.get_all_metric_info()
        for sensor_type, metrics in sorted(sensor_configs.items()):
            for metric_type in sorted(metrics.keys()):
                row_layout = QHBoxLayout()
                row_layout.setSpacing(10)
                
                label = QLabel(f"{sensor_type} {metric_type.capitalize()}:")
                row_layout.addWidget(label, 2)

                min_input = QLineEdit()
                min_input.setValidator(QDoubleValidator())
                min_key = f"{sensor_type.lower()}_{metric_type.lower()}_min"
                min_input.setObjectName(min_key) 
                self.range_inputs[min_key] = min_input
                
                max_input = QLineEdit()
                max_input.setValidator(QDoubleValidator())
                max_key = f"{sensor_type.lower()}_{metric_type.lower()}_max"
                max_input.setObjectName(max_key) 
                self.range_inputs[max_key] = max_input

                row_layout.addWidget(QLabel("Min:"))
                row_layout.addWidget(min_input, 1)
                row_layout.addWidget(QLabel("Max:"))
                row_layout.addWidget(max_input, 1)
                
                self.sensor_ranges_layout.addLayout(row_layout)

                min_input.editingFinished.connect(partial(self._on_range_changed, sensor_type, metric_type))
                max_input.editingFinished.connect(partial(self._on_range_changed, sensor_type, metric_type))

    def populate_threshold_section(self):
        logger.debug("SettingsTab: Populating threshold section.")
        self._clear_layout(self.thresholds_layout)
        self.threshold_line_edits.clear()

        sensor_configs = self.settings_manager.get_all_metric_info()
        
        if not sensor_configs:
            no_thresholds_label = QLabel("No sensors configured to set thresholds for.")
            self.thresholds_layout.addWidget(no_thresholds_label)
            return

        for sensor_type, metrics in sorted(sensor_configs.items()):
            group_box = QGroupBox(f"{sensor_type} Thresholds")
            group_layout = QFormLayout(group_box) 
            
            for metric_type in sorted(metrics.keys()):
                h_layout = QHBoxLayout()
                h_layout.setSpacing(5) 
                
                low_edit = QLineEdit()
                low_edit.setValidator(QDoubleValidator())
                low_edit.setFixedWidth(60) 
                self.threshold_line_edits[(sensor_type, metric_type, 'warning_low_value')] = low_edit 
                h_layout.addWidget(QLabel("Low:"))
                h_layout.addWidget(low_edit)

                high_edit = QLineEdit()
                high_edit.setValidator(QDoubleValidator())
                high_edit.setFixedWidth(60) 
                self.threshold_line_edits[(sensor_type, metric_type, 'warning_high_value')] = high_edit 
                h_layout.addWidget(QLabel("High:"))
                h_layout.addWidget(high_edit)

                crit_low_edit = QLineEdit()
                crit_low_edit.setValidator(QDoubleValidator())
                crit_low_edit.setFixedWidth(60) 
                self.threshold_line_edits[(sensor_type, metric_type, 'critical_low_value')] = crit_low_edit 
                h_layout.addWidget(QLabel("Crit. Low:"))
                h_layout.addWidget(crit_low_edit)

                crit_high_edit = QLineEdit()
                crit_high_edit.setValidator(QDoubleValidator())
                crit_high_edit.setFixedWidth(60) 
                self.threshold_line_edits[(sensor_type, metric_type, 'critical_high_value')] = crit_high_edit 
                h_layout.addWidget(QLabel("Crit. High:"))
                h_layout.addWidget(crit_high_edit)

                h_layout.addStretch(1) 

                group_layout.addRow(QLabel(f"{metric_type.capitalize()}:"), h_layout) 
            
            self.thresholds_layout.addWidget(group_box)

    def setup_connections(self):
        logger.debug("SettingsTab: Setting up connections.")
        self.apply_button.clicked.connect(self.apply_settings)
        self.mock_mode_checkbox.toggled.connect(self._on_mock_mode_changed)
        self.sampling_rate_edit.editingFinished.connect(lambda: self._on_int_setting_changed('General', 'sampling_rate_ms', self.sampling_rate_edit))
        self.alert_sound_checkbox.toggled.connect(self._on_alert_sound_changed)
        self.data_log_enabled_checkbox.toggled.connect(self._on_data_log_enabled_changed)
        self.data_store_max_points_edit.editingFinished.connect(lambda: self._on_int_setting_changed('General', 'data_store_max_points', self.data_store_max_points_edit))
        
        # This connection is fine, it connects to the method defined below.
        self.settings_manager.settings_updated.connect(self._on_settings_updated) 

        # Connect range inputs
        for key, line_edit in self.range_inputs.items():
            parts = key.split('_')
            sensor_type = parts[0].upper()
            metric_type = parts[1].lower()
            line_edit.editingFinished.connect(partial(self._on_range_changed, sensor_type, metric_type))

    def load_settings(self):
        """Loads all current settings from the manager and populates the UI fields."""
        logger.debug("SettingsTab.load_settings: Loading settings into UI.")
        
        self.mock_mode_checkbox.setChecked(self.settings_manager.get_boolean_setting('General', 'mock_mode', fallback=False))
        self.sampling_rate_edit.setText(str(self.settings_manager.get_int_setting('General', 'sampling_rate_ms', fallback=3000)))
        self.data_store_max_points_edit.setText(str(self.settings_manager.get_int_setting('General', 'data_store_max_points', fallback=1000)))
        self.alert_sound_checkbox.setChecked(self.settings_manager.get_boolean_setting('General', 'alert_sound_enabled', fallback=True))
        self.data_log_enabled_checkbox.setChecked(self.settings_manager.get_boolean_setting('General', 'data_log_enabled', fallback=False))
        
        for key, checkbox in self.sensor_config_widgets.items():
            if isinstance(key, str): 
                config_key = key 
            else: 
                config_key = f"{key[0].lower()}_{key[1].lower()}_present"
            
            is_checked = self.settings_manager.get_boolean_setting('Sensor_Presence', config_key, fallback=True)
            checkbox.setChecked(is_checked)
            logger.debug(f"SettingsTab.load_settings: Loaded sensor presence for {key}: {is_checked}")

        for key_tuple, line_edit in self.precision_line_edits.items():
            precision_value = self.settings_manager.get_precision(key_tuple[0], key_tuple[1])
            line_edit.setText(str(precision_value))
            logger.debug(f"SettingsTab.load_settings: Loaded precision for {key_tuple}: {precision_value}")

        for key_str, input_widget in self.range_inputs.items():
            parts = key_str.split('_')
            sensor_type = parts[0].upper()
            metric_type = parts[1].lower()
            range_type = parts[2].lower() 
            
            value = self.settings_manager.get_float_setting('Sensor_Ranges', key_str, None) 
            
            input_widget.setText(str(value) if value is not None else "")
            logger.debug(f"SettingsTab.load_settings: Loaded range for {sensor_type} {metric_type} ({range_type}): {value}")


        for (sensor, metric, logical_th_name), line_edit in self.threshold_line_edits.items():
            value = self.settings_manager.get_threshold(sensor, metric, logical_th_name)
            line_edit.setText(str(value) if value is not None else "")
            logger.debug(f"SettingsTab.load_settings: Loaded threshold for {sensor} {metric} {logical_th_name}: {value}")

        logger.debug("SettingsTab.load_settings: Finished loading settings into UI.")

    def apply_settings(self):
        logger.info("SettingsTab: Applying all settings.")
        # Apply General
        self.settings_manager.set_setting('General', 'mock_mode', self.mock_mode_checkbox.isChecked())
        self.settings_manager.set_setting('General', 'sampling_rate_ms', self.sampling_rate_edit.text())
        self.settings_manager.set_setting('General', 'data_store_max_points', self.data_store_max_points_edit.text())
        self.settings_manager.set_setting('General', 'alert_sound_enabled', self.alert_sound_checkbox.isChecked())
        self.settings_manager.set_setting('General', 'data_log_enabled', self.data_log_enabled_checkbox.isChecked())
        
        # Apply Sensor Presence
        for key, checkbox in self.sensor_config_widgets.items():
            if isinstance(key, str): 
                self.settings_manager.set_setting('Sensor_Presence', key, checkbox.isChecked())
            else: 
                config_key = f"{key[0].lower()}_{key[1].lower()}_present"
                self.settings_manager.set_setting('Sensor_Presence', config_key, checkbox.isChecked())

        # Apply Precision
        for (sensor, metric), line_edit in self.precision_line_edits.items():
            self.settings_manager.set_setting('Sensor_Precision', f"{sensor.lower()}_{metric.lower()}_precision", line_edit.text())
            
        # Apply Ranges
        for key_str, line_edit in self.range_inputs.items():
            self.settings_manager.set_setting('Sensor_Ranges', key_str, line_edit.text())

        # Apply Thresholds
        for (sensor, metric, logical_th_name), line_edit in self.threshold_line_edits.items():
            self.settings_manager.set_threshold(sensor, metric, logical_th_name, line_edit.text())

        self.settings_changed.emit() 
        logger.info("All settings have been applied.")

    @pyqtSlot(str, str, object)
    def _on_settings_updated(self, section, key, value):
        logger.debug(f"SettingsTab._on_settings_updated: Settings updated - Section: {section}, Key: '{key}', Value: {value}.")

        if section in ['Sensor_Presence', 'Sensor_Precision', 'Sensor_Ranges']:
            logger.debug(f"  Sensor configuration section '{section}' changed. Re-populating all sensor sections.")
            self.populate_all_sensor_sections()
            self.load_settings()
        elif section == 'Thresholds':
            logger.debug(f"  Thresholds section changed. Attempting to update specific threshold input.")
            try:
                parts = key.split('/')
                if len(parts) == 3:
                    sensor_type = parts[0]
                    metric_type = parts[1]
                    threshold_type_suffix = parts[2] 
                    
                    line_edit_key = (sensor_type, metric_type, threshold_type_suffix)
                    if line_edit_key in self.threshold_line_edits:
                        line_edit = self.threshold_line_edits[line_edit_key]
                        latest_value = self.settings_manager.get_threshold(sensor_type, metric_type, threshold_type_suffix)
                        line_edit.setText(str(latest_value) if latest_value is not None else "")
                        logger.debug(f"    Updated UI for threshold {sensor_type}/{metric_type}/{threshold_type_suffix} to: {latest_value}")
                    else:
                        logger.warning(f"    Line edit not found for threshold key: {line_edit_key}. Repopulating all sensor sections.")
                        self.populate_all_sensor_sections()
                        self.load_settings()
                else:
                    logger.warning(f"    Unexpected key format for Thresholds update: '{key}'. Re-populating all sensor sections.")
                    self.populate_all_sensor_sections()
                    self.load_settings()
            except Exception as e:
                logger.error(f"Error updating specific threshold UI for key '{key}': {e}", exc_info=True)
                self.populate_all_sensor_sections()
                self.load_settings()
        
        self.style().polish(self)
        logger.debug("SettingsTab: Finished _on_settings_updated.")

    @pyqtSlot(bool)
    def _on_mock_mode_changed(self, checked):
        logger.debug(f"SettingsTab: Mock mode changed to {checked}.")
        self.settings_manager.set_setting('General', 'mock_mode', checked)
        self.settings_changed.emit()

    @pyqtSlot(bool)
    def _on_alert_sound_changed(self, checked):
        logger.debug(f"SettingsTab: Alert sound enabled changed to {checked}.")
        self.settings_manager.set_setting('General', 'alert_sound_enabled', checked)

    @pyqtSlot(bool)
    def _on_data_log_enabled_changed(self, checked):
        logger.debug(f"SettingsTab: Data logging enabled changed to {checked}.")
        self.settings_manager.set_setting('General', 'data_log_enabled', checked)

    @pyqtSlot(str, int)
    def _on_sensor_presence_changed(self, sensor_type, state):
        is_present = (state == Qt.Checked)
        logger.debug(f"SettingsTab: Sensor presence for {sensor_type} changed to {is_present}.")
        self.settings_manager.set_setting('Sensor_Presence', f"{sensor_type.lower()}_present", is_present)
        self.settings_changed.emit()

    @pyqtSlot(str, str, int)
    def _on_metric_presence_changed(self, sensor_type, metric_type, state):
        is_present = (state == Qt.Checked)
        logger.debug(f"SettingsTab: Metric presence for {sensor_type} {metric_type} changed to {is_present}.")
        self.settings_manager.set_setting('Sensor_Presence', f"{sensor_type.lower()}_{metric_type.lower()}_present", is_present)
        self.settings_changed.emit()

    @pyqtSlot(str, str, QLineEdit)
    def _on_precision_changed(self, sensor_type, metric_type, line_edit):
        logger.debug(f"SettingsTab: Precision for {sensor_type} {metric_type} changed to {line_edit.text()}.")
        self.settings_manager.set_setting('Sensor_Precision', f"{sensor_type.lower()}_{metric_type.lower()}_precision", line_edit.text())
        self.settings_changed.emit()

    @pyqtSlot(str, str)
    def _on_range_changed(self, sensor_type, metric_type):
        logger.debug(f"SettingsTab: Range for {sensor_type} {metric_type} changed.")
        min_key = f"{sensor_type.lower()}_{metric_type.lower()}_min"
        max_key = f"{sensor_type.lower()}_{metric_type.lower()}_max"
        min_input = self.range_inputs[min_key]
        max_input = self.range_inputs[max_key]
        
        self.settings_manager.set_setting('Sensor_Ranges', min_key, min_input.text())
        self.settings_manager.set_setting('Sensor_Ranges', max_key, max_input.text())
        self.settings_changed.emit()

    @pyqtSlot(str, str, str, QLineEdit)
    def _on_threshold_changed(self, sensor_type, metric_type, threshold_type_suffix, line_edit):
        logger.debug(f"SettingsTab: Threshold for {sensor_type} {metric_type} {threshold_type_suffix} changed to {line_edit.text()}.")
        self.settings_manager.set_threshold(sensor_type, metric_type, threshold_type_suffix, line_edit.text())

    @pyqtSlot(str, object, QLineEdit) 
    def _on_int_setting_changed(self, section, key, line_edit):
        logger.debug(f"SettingsTab: Int setting {section}/{key} changed to {line_edit.text()}.")
        self.settings_manager.set_setting(section, key, line_edit.text())

    @pyqtSlot(str, object, QLineEdit) 
    def _on_float_setting_changed(self, section, key, line_edit):
        logger.debug(f"SettingsTab: Float setting {section}/{key} changed to {line_edit.text()}.")
        self.settings_manager.set_setting(section, key, line_edit.text())

    def _clear_layout(self, layout):
        """Removes all widgets from a layout."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()
                elif item.layout() is not None:
                    self._clear_layout(item.layout())

    @pyqtSlot(dict)
    def update_available_sensors(self, available_sensors_info):
        """
        Updates the UI based on newly discovered sensors.
        """
        logger.info("SettingsTab: Updating available sensors and repopulating UI sections.")
        self.populate_all_sensor_sections()
        self.load_settings()
                
    def update_theme_colors(self, new_theme_colors):
        logger.info("SettingsTab: update_theme_colors called for SettingsTab. Re-polishing UI elements.")
        self.theme_colors.clear()
        self.theme_colors.update(new_theme_colors) 
        
        self.style().polish(self)
        for child_widget in self.findChildren(QGroupBox):
            self.style().polish(child_widget)
        for child_widget in self.findChildren(QLabel):
            self.style().polish(child_widget)
        for child_widget in self.findChildren(QLineEdit):
            self.style().polish(child_widget)
        for child_widget in self.findChildren(QComboBox):
            self.style().polish(child_widget)
        for child_widget in self.findChildren(QCheckBox):
            self.style().polish(child_widget)
        for child_widget in self.findChildren(QPushButton):
            self.style().polish(child_widget)
        
        logger.info("SettingsTab: Theme colors applied and UI polished.")