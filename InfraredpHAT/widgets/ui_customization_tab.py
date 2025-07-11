# widgets/ui_customization_tab.py
# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, 
                             QComboBox, QPushButton, QFontDialog, QColorDialog, 
                             QScrollArea, QSizePolicy, QSpacerItem, QFormLayout,
                             QLineEdit)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QSize, QTimer
from PyQt5.QtGui import QFont, QFontDatabase, QColor

import logging
import os
import json 
import collections 

from data_management.settings import SettingsManager
from widgets.sensor_display import SensorDisplayWidget 
from widgets.matplotlib_widget import MatplotlibWidget 

logger = logging.getLogger(__name__)

class UICustomizationTab(QWidget):
    """
    UI Customization tab allowing users to change visual aspects of the dashboard,
    such as gauge types, styles, color themes, and other UI behaviors.
    """
    ui_customization_changed = pyqtSignal(str, str) 
    theme_changed = pyqtSignal(str) 

    def __init__(self, settings_manager, theme_colors, initial_gauge_type, initial_gauge_style, 
                 data_store, thresholds, main_window,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("UICustomizationTab")

        self.settings_manager = settings_manager
        self.theme_colors = theme_colors
        self.data_store = data_store
        self.thresholds = thresholds
        self.main_window = main_window

        self.initial_gauge_type = initial_gauge_type
        self.initial_gauge_style = initial_gauge_style
        self.current_theme_file_name = self.settings_manager.get_setting('General', 'current_theme', fallback='arctic_ice_theme.qss')

        self.setup_ui()
        self.setup_connections()
        #self.update_theme_colors(self.theme_colors)
        self.update_theme_colors(self.settings_manager.get_theme_colors()) 
        
        logger.info("UICustomizationTab initialized.")

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)
        main_layout.setAlignment(Qt.AlignTop)

        # --- Gauge Customization Section ---
        gauge_group_box = QGroupBox("Gauge Customization")
        gauge_group_box.setObjectName("GaugeCustomizationGroup")
        gauge_layout = QVBoxLayout(gauge_group_box)
        gauge_layout.setContentsMargins(10, 20, 10, 10)
        gauge_layout.setSpacing(10)

        gauge_form_layout = QFormLayout()
        
        # Gauge Type Selection
        self.gauge_type_combo = QComboBox()
        self.gauge_type_combo.setObjectName("GaugeTypeCombo")
        self.gauge_type_combo.addItems(SensorDisplayWidget.GAUGE_TYPES)
        self.gauge_type_combo.setCurrentText(self.initial_gauge_type)
        gauge_form_layout.addRow("Gauge Type:", self.gauge_type_combo)

        # Gauge Style Selection
        self.gauge_style_combo = QComboBox()
        self.gauge_style_combo.setObjectName("GaugeStyleCombo")
        self.gauge_style_combo.addItems(SensorDisplayWidget.GAUGE_STYLES) 
        self.gauge_style_combo.setCurrentText(self.initial_gauge_style)
        gauge_form_layout.addRow("Gauge Style:", self.gauge_style_combo)
        
        gauge_layout.addLayout(gauge_form_layout)

        # Preview Gauge
        self.preview_group_box = QGroupBox("Gauge Preview")
        self.preview_group_box.setObjectName("GaugePreviewGroup")
        self.preview_layout = QHBoxLayout(self.preview_group_box)
        self.preview_layout.setAlignment(Qt.AlignCenter)
        
        self.preview_thresholds = {
            'low_threshold': self.settings_manager.get_threshold('HTU21D', 'temperature', 'low_threshold'),
            'high_threshold': self.settings_manager.get_threshold('HTU21D', 'temperature', 'high_threshold')
        }

        self.preview_gauge = SensorDisplayWidget(
            sensor_name="Temp Preview",
            sensor_category="HTU21D", 
            metric_type="temperature", 
            settings_manager=self.settings_manager, # Pass the settings manager
            gauge_type=self.initial_gauge_type,
            gauge_style=self.initial_gauge_style,
            min_value=0.0,
            max_value=40.0,
            # FIX: REMOVE theme_colors=self.theme_colors,
            thresholds=self.preview_thresholds,
            initial_value=22.5,
            unit="°C",
            precision=1,
            main_window=self.main_window,
            is_preview=True
        )
        
        self.preview_gauge.setFixedSize(180, 180) 
        self.preview_gauge.setObjectName("PreviewGaugeWidget")
        self.preview_layout.addWidget(self.preview_gauge)
        
        gauge_layout.addWidget(self.preview_group_box)

        main_layout.addWidget(gauge_group_box)

        # --- General UI Settings ---
        general_ui_group = QGroupBox("General UI Settings")
        general_ui_group.setObjectName("GeneralUISettingsGroup")
        general_ui_layout = QFormLayout(general_ui_group)
        
        self.dashboard_plot_time_range_combo = QComboBox()
        self.dashboard_plot_time_range_combo.addItems(self.data_store.get_available_time_ranges())
        self.dashboard_plot_time_range_combo.setCurrentText(self.settings_manager.get_setting('General', 'dashboard_plot_time_range', fallback='Last 30 minutes'))
        general_ui_layout.addRow("Dashboard Plot Time Range:", self.dashboard_plot_time_range_combo)
        
        self.detail_plot_time_range_combo = QComboBox()
        self.detail_plot_time_range_combo.addItems(self.data_store.get_available_time_ranges())
        self.detail_plot_time_range_combo.setCurrentText(self.settings_manager.get_setting('General', 'detail_plot_time_range', fallback='Last 10 minutes'))
        general_ui_layout.addRow("Detail Plot Time Range:", self.detail_plot_time_range_combo)

        plot_update_interval_layout = QHBoxLayout()
        self.plot_update_interval_edit = QLineEdit(str(self.settings_manager.get_int_setting('General', 'plot_update_interval_ms', fallback=1000)))
        if self.main_window and hasattr(self.main_window, 'int_validator'):
            self.plot_update_interval_edit.setValidator(self.main_window.int_validator) 
        plot_update_interval_layout.addWidget(self.plot_update_interval_edit)
        plot_update_interval_layout.addWidget(QLabel("ms"))
        plot_update_interval_layout.addStretch(1)
        general_ui_layout.addRow("Plot Update Interval:", plot_update_interval_layout)

        self.notification_method_combo = QComboBox()
        self.notification_method_combo.addItems(["Popup", "Status Bar", "None"])
        self.notification_method_combo.setCurrentText(self.settings_manager.get_setting('General', 'notification_method', fallback='Status Bar'))
        general_ui_layout.addRow("Notification Method:", self.notification_method_combo)

        main_layout.addWidget(general_ui_group)

        # --- Theme Selection Section ---
        theme_group_box = QGroupBox("Application Theme")
        theme_group_box.setObjectName("ThemeSelectionGroup")
        theme_layout = QFormLayout(theme_group_box)
        
        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName("ThemeCombo")
        self.populate_theme_combo()
        self.theme_combo.setCurrentText(self.current_theme_file_name)
        theme_layout.addRow("Select Theme:", self.theme_combo)
        
        main_layout.addWidget(theme_group_box)
        main_layout.addStretch(1) 

        logger.info("UICustomizationTab: UI setup complete.")

    def setup_connections(self):
        self.gauge_type_combo.currentTextChanged.connect(self._on_gauge_type_changed)
        self.gauge_style_combo.currentTextChanged.connect(self._on_gauge_style_changed)
        self.theme_combo.currentTextChanged.connect(self._on_theme_selection_changed)
        
        self.dashboard_plot_time_range_combo.currentTextChanged.connect(
            lambda text: self.settings_manager.set_setting('General', 'dashboard_plot_time_range', text)
        )
        self.detail_plot_time_range_combo.currentTextChanged.connect(
            lambda text: self.settings_manager.set_setting('General', 'detail_plot_time_range', text)
        )
        self.plot_update_interval_edit.editingFinished.connect(
            lambda: self.settings_manager.set_setting('General', 'plot_update_interval_ms', self.plot_update_interval_edit.text())
        )
        self.notification_method_combo.currentTextChanged.connect(
            lambda text: self.settings_manager.set_setting('General', 'notification_method', text)
        )
        self.settings_manager.settings_updated.connect(self._on_settings_updated)

    @pyqtSlot(dict)
    def update_theme_colors(self, new_theme_colors):
        """
        Updates the theme colors for this tab and its child widgets.
        """
        logger.info(f"{self.objectName()}: update_theme_colors called.")
        
        self.theme_colors = dict(new_theme_colors) if new_theme_colors is not None else {}
        
        if not self.theme_colors:
            logger.warning(f"{self.objectName()} received empty theme colors.")

        # The global stylesheet is now responsible for theming.
        # We only need to update widgets with custom drawing, like plots and gauges.
        #for gauge in self.sensor_display_widgets.values():
        #    gauge.update_theme_colors(self.theme_colors)
        
        if self.preview_gauge:
            self.preview_gauge.update_theme_colors(self.theme_colors)
            self.preview_gauge.update_value(self.preview_gauge._current_value) 
            logger.debug("UICustomizationTab: Preview gauge theme updated.")


    def populate_theme_combo(self):
        """Populates the theme combo box with available QSS files."""
        themes_dir = self.settings_manager.get_resource_path("", resource_type="themes")
        if not os.path.exists(themes_dir):
            logger.error(f"Themes directory not found: {themes_dir}")
            return
        
        theme_files = [f for f in os.listdir(themes_dir) if f.endswith('.qss')]
        theme_files.sort()
        self.theme_combo.clear()
        self.theme_combo.addItems(theme_files)
        
        current_theme = self.settings_manager.get_setting('General', 'current_theme', fallback='arctic_ice_theme.qss')
        index = self.theme_combo.findText(current_theme)
        if index != -1:
            self.theme_combo.setCurrentIndex(index)
        
        logger.debug(f"UICustomizationTab: Populated theme combo with: {theme_files}. Current theme set to: {current_theme}")

    # --- SLOTS ---
    @pyqtSlot(str, str, object)
    def _on_settings_updated(self, section, key, value):
        if section == 'General' and key == 'current_theme':
            self.current_theme_file_name = value
            self.theme_combo.setCurrentText(value) 
            self.update_theme_colors(self.settings_manager.get_theme_colors()) 
        elif section == 'UI' and key == 'gauge_type':
            self.gauge_type_combo.setCurrentText(value)
        elif section == 'UI' and key == 'gauge_style':
            self.gauge_style_combo.setCurrentText(value)
        elif section == 'Thresholds':
            if self.preview_gauge:
                self.preview_gauge.thresholds = {
                    'low_threshold': self.settings_manager.get_threshold('HTU21D', 'temperature', 'low_threshold'),
                    'high_threshold': self.settings_manager.get_threshold('HTU21D', 'temperature', 'high_threshold')
                }
                self.preview_gauge.update_value(self.preview_gauge._current_value)

    @pyqtSlot(str)
    def _on_gauge_type_changed(self, gauge_type):
        logger.debug(f"UICustomizationTab: Gauge type changed")
        self.settings_manager.set_setting('UI', 'gauge_type', gauge_type)
        self.ui_customization_changed.emit(gauge_type, self.gauge_style_combo.currentText())

        for i in reversed(range(self.preview_layout.count())):
            widget_to_remove = self.preview_layout.itemAt(i).widget()
            if widget_to_remove:
                widget_to_remove.setParent(None)
                widget_to_remove.deleteLater()
        
        self.preview_group_box = QGroupBox("Gauge Preview")
        self.preview_group_box.setObjectName("GaugePreviewGroup")

        self.preview_gauge = SensorDisplayWidget(
            sensor_name="Temp Preview",
            sensor_category="HTU21D", 
            metric_type="temperature", 
            gauge_type=gauge_type,
            gauge_style=self.initial_gauge_style,
            min_value=0.0,
            max_value=40.0,
            settings_manager=self.settings_manager, # Pass the settings manager
            thresholds=self.preview_thresholds,
            initial_value=22.5,
            unit="°C",
            precision=1,
            parent=self.preview_group_box,
            main_window=self.main_window,
            is_preview=True
        )
        
        self.preview_gauge.setFixedSize(180, 180) 
        self.preview_gauge.setObjectName("PreviewGaugeWidget")
        self.preview_layout.addWidget(self.preview_gauge)

    
    @pyqtSlot(str)
    def _on_gauge_style_changed(self, gauge_style):
        self.settings_manager.set_setting('UI', 'gauge_style', gauge_style)
        self.ui_customization_changed.emit(self.gauge_type_combo.currentText(), gauge_style)
        self.preview_gauge._gauge_style = gauge_style
        self.initial_gauge_style = gauge_style
        #self.preview_gauge.update() 
        self.preview_gauge.style().polish(self.preview_gauge)

    @pyqtSlot(str)
    def _on_theme_selection_changed(self, theme_file_name):
        self.settings_manager.set_setting('General', 'current_theme', theme_file_name)
        self.current_theme_file_name = theme_file_name
        self.theme_changed.emit(theme_file_name)
