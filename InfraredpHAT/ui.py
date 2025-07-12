# ui.py
# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget, QTabWidget, QSpacerItem, QSizePolicy, QApplication
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot

import logging
import collections

from data_management.settings import SettingsManager
from widgets.dashboard_tab import DashboardTab
from widgets.sensor_details_tab import SensorDetailsTab
from widgets.plot_tab_widget import PlotTabWidget
from widgets.settings_tab import SettingsTab
from widgets.ui_customization_tab import UICustomizationTab
from widgets.about_tab import AboutTab

logger = logging.getLogger(__name__)

class AnaviSensorUI(QWidget):
    """
    Main UI container for the Anavi Sensor Dashboard, managing different tabs.
    """
    ui_customization_changed = pyqtSignal(str, str)
    theme_changed = pyqtSignal(str)
    thresholds_updated = pyqtSignal(dict)
    alert_triggered = pyqtSignal(str, str, str, str)
    alert_cleared = pyqtSignal(str, str)

    def __init__(self, settings_manager, theme_colors, initial_gauge_type, initial_gauge_style, 
                 data_store, thresholds, 
                 initial_dashboard_plot_time_range, initial_detail_plot_time_range,
                 initial_hide_matplotlib_toolbar, initial_plot_update_interval_ms,
                 main_window=None,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("AnaviSensorUI")

        self.settings_manager = settings_manager
        self.theme_colors = theme_colors
        self.data_store = data_store
        self.thresholds = thresholds
        self.main_window = main_window 

        self.initial_gauge_type = initial_gauge_type
        self.initial_gauge_style = initial_gauge_style
        self.initial_dashboard_plot_time_range = initial_dashboard_plot_time_range
        self.initial_detail_plot_time_range = initial_detail_plot_time_range
        self.initial_hide_matplotlib_toolbar = initial_hide_matplotlib_toolbar
        self.initial_plot_update_interval_ms = initial_plot_update_interval_ms

        self._setup_tabs()
        self._setup_connections()
        
        logger.info("AnaviSensorUI initialized.")

    def _setup_tabs(self):
        """
        Sets up the tab widget and adds individual sensor data tabs.
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0) 
        main_layout.setSpacing(0)

        self.tab_widget = QTabWidget(self)
        self.tab_widget.setObjectName("MainTabWidget")
        
        self.dashboard_tab = DashboardTab(
            data_store=self.data_store,
            settings_manager=self.settings_manager,
            initial_dashboard_plot_time_range=self.initial_dashboard_plot_time_range,
            initial_hide_matplotlib_toolbar=self.initial_hide_matplotlib_toolbar,
            initial_plot_update_interval_ms=self.initial_plot_update_interval_ms,
            initial_gauge_type=self.initial_gauge_type,
            initial_gauge_style=self.initial_gauge_style,
            main_window=self.main_window 
        )
        self.tab_widget.addTab(self.dashboard_tab, "Dashboard")
        
        self.sensor_details_tab = SensorDetailsTab(
            data_store=self.data_store,
            settings_manager=self.settings_manager,
            initial_gauge_type=self.initial_gauge_type,
            initial_gauge_style=self.initial_gauge_style,
            initial_hide_matplotlib_toolbar=self.initial_hide_matplotlib_toolbar,
            initial_plot_update_interval_ms=self.initial_plot_update_interval_ms,
            initial_detail_plot_time_range=self.initial_detail_plot_time_range,
            main_window=self.main_window 
        )
        self.tab_widget.addTab(self.sensor_details_tab, "Sensor Details")

        self.plot_tab = PlotTabWidget(
            data_store=self.data_store,
            settings_manager=self.settings_manager,
            theme_colors=self.theme_colors,
            initial_hide_matplotlib_toolbar=self.initial_hide_matplotlib_toolbar,
            initial_plot_update_interval_ms=self.initial_plot_update_interval_ms,
            initial_detail_plot_time_range=self.initial_detail_plot_time_range,
            main_window=self.main_window 
        )
        self.tab_widget.addTab(self.plot_tab, "Plot")

        self.settings_tab = SettingsTab(
            settings_manager=self.settings_manager,
            theme_colors=self.theme_colors,
            main_window=self.main_window, 
            data_store=self.data_store,
            thresholds=self.thresholds
        )
        self.tab_widget.addTab(self.settings_tab, "Settings")

        self.ui_customization_tab = UICustomizationTab(
            settings_manager=self.settings_manager,
            theme_colors=self.theme_colors,
            initial_gauge_type=self.initial_gauge_type,
            initial_gauge_style=self.initial_gauge_style,
            data_store=self.data_store, 
            thresholds=self.thresholds,
            main_window=self.main_window
        )
        self.tab_widget.addTab(self.ui_customization_tab, "UI Customization")

        self.about_tab = AboutTab(
            settings_manager=self.settings_manager,
            main_window=self.main_window
        )
        self.tab_widget.addTab(self.about_tab, "About")

        main_layout.addWidget(self.tab_widget)
        logger.info("AnaviSensorUI: Tabs setup complete.")


    def _setup_connections(self):
        """
        Sets up connections between UI elements and their respective slots.
        """
        self.dashboard_tab.alert_triggered.connect(self.alert_triggered)
        self.dashboard_tab.alert_cleared.connect(self.alert_cleared)
        
        self.sensor_details_tab.alert_triggered.connect(self.alert_triggered)
        self.sensor_details_tab.alert_cleared.connect(self.alert_cleared)

        self.settings_tab.thresholds_updated_signal.connect(self.thresholds_updated)
        
        self.ui_customization_tab.ui_customization_changed.connect(self.handle_ui_customization_change)
        self.ui_customization_tab.theme_changed.connect(self.theme_changed)

        self.tab_widget.currentChanged.connect(self._on_tab_changed)


    @pyqtSlot(int)
    def _on_tab_changed(self, index):
        """
        Slot to handle tab changes, potentially updating plot intervals.
        """
        current_widget = self.tab_widget.widget(index)
        logger.debug(f"AnaviSensorUI: Tab changed to: {current_widget.objectName()}")

        plot_update_interval = self.settings_manager.get_int_setting('General', 'plot_update_interval_ms')
        
        if current_widget == self.dashboard_tab:
            self.dashboard_tab.set_plot_update_interval(plot_update_interval)
            self.dashboard_tab._on_plot_timer_timeout() 
        elif current_widget == self.sensor_details_tab:
            self.sensor_details_tab.set_plot_update_interval(plot_update_interval)
            self.sensor_details_tab.update_all_plots() 
        elif current_widget == self.plot_tab:
            self.plot_tab.set_plot_update_interval(plot_update_interval) 
            self.plot_tab.update_plot() 

    @pyqtSlot(str, str)
    def handle_ui_customization_change(self, gauge_type, gauge_style):
        """
        Handles UI customization changes by propagating them to relevant tabs.
        """
        self.ui_customization_changed.emit(gauge_type, gauge_style)

    @pyqtSlot(dict)
    def update_sensor_values(self, data_snapshot):
        """
        Passes the latest sensor data snapshot to the Dashboard and Sensor Details tabs.
        """
        self.dashboard_tab.update_sensor_values(data_snapshot)
        self.sensor_details_tab.update_sensor_values(data_snapshot)

    @pyqtSlot(dict)
    def update_theme_colors_globally(self, new_theme_colors):
        """
        Updates the theme colors for all child tabs. This is called by MainWindow.
        """
        logger.info("AnaviSensorUI: Propagating theme colors to all tabs.")
        self.theme_colors.clear()

        logger.debug(f"AnaviAnaviSensorUI - Dumping new theme colors\n{new_theme_colors}")

        # Use the new theme colors if they are provided, otherwise initialize an empty dict
        self.theme_colors = dict(new_theme_colors) if new_theme_colors is not None else {}

        # ---- FIX ----
        # If the theme_colors dictionary is empty, it means the update was triggered
        # without the necessary data, so we fetch it directly from the SettingsManager.
        if not self.theme_colors:
            logger.warning(f"{self.objectName()} received empty theme colors. Fetching from SettingsManager.")
            self.theme_colors = self.settings_manager.get_theme_colors() # <-- This is the key line

        #self.theme_colors.update(new_theme_colors) 

        # The individual tabs will update their non-QSS elements (plots, custom gauges)
        self.dashboard_tab.update_theme_colors(self.theme_colors)
        self.sensor_details_tab.update_theme_colors(self.theme_colors)
        self.plot_tab.update_theme_colors(self.theme_colors)
        self.settings_tab.update_theme_colors(self.theme_colors)
        self.ui_customization_tab.update_theme_colors(self.theme_colors)
        if hasattr(self, 'about_tab'):
            self.about_tab.update_theme_colors(self.theme_colors)
        logger.info("AnaviSensorUI: Global theme update propagated.")

    def initialize_all_tab_data(self, theme_colors):
        """
        Called once from MainWindow to initialize all tabs.
        """
        logger.info("AnaviSensorUI: Initializing all tab data.")
        self.dashboard_tab._on_plot_timer_timeout() 
        self.sensor_details_tab.initialize_tab_data(theme_colors) 
        self.plot_tab.update_plot() 
        logger.info("AnaviSensorUI: All tab data initialized.")
