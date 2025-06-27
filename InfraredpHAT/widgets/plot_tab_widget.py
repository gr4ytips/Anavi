# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSizePolicy
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
import logging
import datetime
import re # For parsing time range strings, if necessary

from widgets.matplotlib_widget import MatplotlibWidget # Import the MatplotlibWidget
from data_management.data_store import SensorDataStore # For accessing sensor data

logger = logging.getLogger(__name__)

class PlotTabWidget(QWidget):
    """
    A dedicated tab for plotting historical sensor data using Matplotlib.
    It displays trends for all available sensor metrics on a single plot,
    with options to select the time range, filter by sensor type, and metric type,
    including specific comparison options.
    """
    def __init__(self, data_store, settings_manager, theme_colors, parent=None):
        """
        Initializes the PlotTabWidget.
        :param data_store: An instance of SensorDataStore to fetch historical data.
        :param settings_manager: An instance of SettingsManager to save/load settings.
        :param theme_colors: Dictionary of current theme colors.
        :param parent: Parent QWidget.
        """
        super().__init__(parent)
        self.setObjectName("PlotTabWidget") # Object name for QSS styling

        self.data_store = data_store
        self.settings_manager = settings_manager
        self.theme_colors = theme_colors

        self.matplotlib_plot = MatplotlibWidget(parent=self, theme_colors=self.theme_colors)
        self.matplotlib_plot.setMinimumHeight(450) # Ensure ample space for the plot
        self.matplotlib_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Store the currently selected sensor filter (e.g., "Combined", "HTU21D", "Temperature Comparison")
        self.current_sensor_selection = "Combined"
        # Store the currently selected metric filter for a specific sensor (e.g., "All Metrics", "Temperature")
        self.current_metric_selection = "All Metrics" # Default for individual sensor view

        self.setup_ui()
        self.connect_signals()

        logger.info("PlotTabWidget initialized.")

    def setup_ui(self):
        """Sets up the layout and widgets for the plot tab."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # Controls Layout (Time Range, Sensor Filter, and Metric Filter)
        controls_h_layout = QHBoxLayout()
        controls_h_layout.setContentsMargins(0, 0, 0, 0)
        controls_h_layout.setSpacing(10)

        # Time Range Selection
        time_range_label = QLabel("Time Range:")
        time_range_label.setObjectName("PlotControlLabel") # For QSS
        controls_h_layout.addWidget(time_range_label)

        self.time_range_combo = QComboBox()
        self.time_range_combo.setObjectName("PlotControlComboBox") # For QSS
        self.time_range_combo.addItems([
            "Last 10 minutes", "Last 30 minutes", "Last 1 hour",
            "Last 3 hours", "Last 6 hours", "Last 12 hours",
            "Last 24 hours", "All Data"
        ])
        initial_plot_time_range = self.settings_manager.get_setting('General', 'plot_tab_time_range', type=str, default="Last 1 hour")
        self.time_range_combo.setCurrentText(initial_plot_time_range)
        controls_h_layout.addWidget(self.time_range_combo)
        
        # Spacer
        controls_h_layout.addSpacing(20) # Add some space between combos

        # Sensor Selection Combo Box
        sensor_label = QLabel("Sensor:")
        sensor_label.setObjectName("PlotControlLabel") # For QSS
        controls_h_layout.addWidget(sensor_label)

        self.sensor_combo = QComboBox()
        self.sensor_combo.setObjectName("PlotControlComboBox") # For QSS
        controls_h_layout.addWidget(self.sensor_combo)

        # New: Metric Selection Combo Box
        self.metric_label = QLabel("Metric:")
        self.metric_label.setObjectName("PlotControlLabel") # For QSS
        controls_h_layout.addWidget(self.metric_label)

        self.metric_combo = QComboBox()
        self.metric_combo.setObjectName("PlotControlComboBox") # For QSS
        controls_h_layout.addWidget(self.metric_combo)


        controls_h_layout.addStretch(1) # Push controls to the left

        main_layout.addLayout(controls_h_layout)
        main_layout.addWidget(self.matplotlib_plot, 1) # Plot takes remaining vertical space

        self.setLayout(main_layout)
        logger.debug("PlotTabWidget UI setup complete.")

    def connect_signals(self):
        """Connects signals for time range and sensor/metric filter controls."""
        self.time_range_combo.currentTextChanged.connect(self.update_plot_data)
        self.time_range_combo.currentTextChanged.connect(self.save_plot_time_range_setting)
        
        self.sensor_combo.currentTextChanged.connect(self._on_sensor_selection_changed)
        self.metric_combo.currentTextChanged.connect(self._on_metric_selection_changed) # NEW: Connect metric combo
        logger.debug("PlotTabWidget signals connected.")

    def _populate_sensor_combo(self):
        """
        Populates the sensor selection combo box with available sensor types and comparison options.
        Ensures "Combined" is always the first option.
        """
        self.sensor_combo.blockSignals(True) # Block signals during population
        self.sensor_combo.clear()
        self.sensor_combo.addItem("Combined") # Always offer combined view

        # Add specific comparison options
        available_metrics = self.data_store.get_all_available_metrics()
        
        htu21d_temp_available = 'HTU21D' in available_metrics and 'temperature' in available_metrics['HTU21D']
        bmp180_temp_available = 'BMP180' in available_metrics and 'temperature' in available_metrics['BMP180']

        if htu21d_temp_available and bmp180_temp_available:
            self.sensor_combo.addItem("Temperature Comparison")
            logger.debug("PlotTabWidget: 'Temperature Comparison' option added.")
        
        # Add individual sensor types
        available_sensors = list(available_metrics.keys())
        available_sensors.sort() # Sort sensors alphabetically for consistent order
        for sensor_type in available_sensors:
            self.sensor_combo.addItem(sensor_type) # Add sensor type as an option
        
        # Restore previous sensor selection if it's still available
        if self.current_sensor_selection in [self.sensor_combo.itemText(i) for i in range(self.sensor_combo.count())]:
            self.sensor_combo.setCurrentText(self.current_sensor_selection)
        else:
            self.sensor_combo.setCurrentText("Combined") # Default if previous not found

        self.current_sensor_selection = self.sensor_combo.currentText() # Update stored selection
        self.sensor_combo.blockSignals(False) # Re-enable signals
        logger.debug(f"PlotTabWidget: Sensor combo box populated. Current selection: {self.current_sensor_selection}")


    def _populate_metric_combo(self, sensor_type):
        """
        Populates the metric selection combo box based on the selected sensor type.
        If "Combined" or "Temperature Comparison" is selected for sensor_type,
        the metric combo is disabled or hidden.
        """
        self.metric_combo.blockSignals(True) # Block signals during population
        self.metric_combo.clear()

        if sensor_type in ["Combined", "Temperature Comparison"]:
            self.metric_label.setVisible(False)
            self.metric_combo.setVisible(False)
            self.metric_combo.addItem("N/A") # Add a dummy item for consistency
            self.current_metric_selection = "N/A"
        else:
            self.metric_label.setVisible(True)
            self.metric_combo.setVisible(True)
            self.metric_combo.addItem("All Metrics") # Option to show all metrics for the selected sensor

            available_metrics_for_sensor = self.data_store.get_all_available_metrics().get(sensor_type, {})
            metric_types = list(available_metrics_for_sensor.keys())
            metric_types.sort() # Sort metrics alphabetically
            for metric_type in metric_types:
                self.metric_combo.addItem(metric_type.replace('_', ' ').title()) # Add human-readable metric name
            
            # Restore previous metric selection if available for this sensor
            if self.current_metric_selection in [self.metric_combo.itemText(i) for i in range(self.metric_combo.count())]:
                self.metric_combo.setCurrentText(self.current_metric_selection)
            else:
                self.metric_combo.setCurrentText("All Metrics") # Default if previous not found

            self.current_metric_selection = self.metric_combo.currentText() # Update stored selection

        self.metric_combo.blockSignals(False) # Re-enable signals
        logger.debug(f"PlotTabWidget: Metric combo box populated for '{sensor_type}'. Current selection: {self.current_metric_selection}")


    def _on_sensor_selection_changed(self, selection_text):
        """
        Handles changes in the sensor selection combo box.
        Updates the metric combo box and triggers a plot data update.
        """
        logger.info(f"PlotTabWidget: Sensor selection changed to: {selection_text}")
        self.current_sensor_selection = selection_text
        self._populate_metric_combo(selection_text) # Populate metric combo based on new sensor
        self.update_plot_data() # Re-plot based on new sensor filter (and metric filter will be updated)

    def _on_metric_selection_changed(self, selection_text):
        """
        Handles changes in the metric selection combo box.
        Triggers a plot data update based on the new selection.
        """
        logger.info(f"PlotTabWidget: Metric selection changed to: {selection_text}")
        self.current_metric_selection = selection_text
        self.update_plot_data() # Re-plot based on new metric filter


    def update_plot_data(self):
        """
        Fetches historical data based on current time range, sensor, and metric selections,
        then updates the Matplotlib plot.
        """
        logger.info(f"PlotTabWidget: Updating plot data for: Sensor='{self.current_sensor_selection}', Metric='{self.current_metric_selection}'.")
        selected_time_range = self.time_range_combo.currentText()
        all_available_metrics = self.data_store.get_all_available_metrics()
        
        plot_series_list = []

        if not all_available_metrics:
            self.matplotlib_plot.set_status_message("No sensor metrics available to plot. Please check sensor configuration.")
            logger.warning("PlotTabWidget: No available metrics found from data store.")
            return

        # Determine which sensors/metrics to plot based on current selections
        if self.current_sensor_selection == "Combined":
            sensors_to_process = all_available_metrics # Plot all sensors/metrics
            for sensor_type, metrics in sensors_to_process.items():
                for metric_type, unit in metrics.items(): 
                    self._add_series_to_plot_list(plot_series_list, sensor_type, metric_type, unit, selected_time_range)

        elif self.current_sensor_selection == "Temperature Comparison":
            logger.debug("PlotTabWidget: Preparing 'Temperature Comparison' plot.")
            # Explicitly add HTU21D Temperature
            if 'HTU21D' in all_available_metrics and 'temperature' in all_available_metrics['HTU21D']:
                unit = all_available_metrics['HTU21D']['temperature']
                self._add_series_to_plot_list(plot_series_list, 'HTU21D', 'temperature', unit, selected_time_range, label_suffix="(HTU21D)")
            else:
                logger.warning("PlotTabWidget: HTU21D Temperature not available for comparison.")
            
            # Explicitly add BMP180 Temperature
            if 'BMP180' in all_available_metrics and 'temperature' in all_available_metrics['BMP180']:
                unit = all_available_metrics['BMP180']['temperature']
                self._add_series_to_plot_list(plot_series_list, 'BMP180', 'temperature', unit, selected_time_range, label_suffix="(BMP180)")
            else:
                logger.warning("PlotTabWidget: BMP180 Temperature not available for comparison.")
            
            if not plot_series_list: # If after checking, neither temperature is available
                 self.matplotlib_plot.set_status_message(f"Neither HTU21D nor BMP180 Temperature data available in {selected_time_range}.")
                 logger.warning("PlotTabWidget: No temperature data for comparison plot.")
                 return

        else: # An Individual Sensor Type is selected (e.g., "HTU21D")
            sensor_type = self.current_sensor_selection
            if sensor_type in all_available_metrics:
                if self.current_metric_selection == "All Metrics":
                    # Plot all metrics for the selected sensor
                    metrics_to_plot = all_available_metrics[sensor_type]
                    for metric_type, unit in metrics_to_plot.items():
                        self._add_series_to_plot_list(plot_series_list, sensor_type, metric_type, unit, selected_time_range)
                else:
                    # Plot a specific metric for the selected sensor
                    metric_type_raw = self.current_metric_selection.replace(' ', '_').lower() # Convert "Temperature" to "temperature"
                    if metric_type_raw in all_available_metrics[sensor_type]:
                        unit = all_available_metrics[sensor_type][metric_type_raw]
                        self._add_series_to_plot_list(plot_series_list, sensor_type, metric_type_raw, unit, selected_time_range)
                    else:
                        logger.warning(f"PlotTabWidget: Selected metric '{self.current_metric_selection}' not found for sensor '{sensor_type}'.")
                        self.matplotlib_plot.set_status_message(f"No data available for {sensor_type} {self.current_metric_selection}.")
                        return
            else:
                logger.warning(f"PlotTabWidget: Selected sensor '{sensor_type}' not found in available metrics during plot update.")
                self.matplotlib_plot.set_status_message(f"No data available for selected sensor: {sensor_type}.")
                return


        if plot_series_list:
            self.matplotlib_plot.plot_data(plot_series_list, self.theme_colors)
            logger.info(f"PlotTabWidget: Plot updated with {len(plot_series_list)} series.")
        else:
            self.matplotlib_plot.set_status_message(f"No data available for the current selection in {selected_time_range}.")
            logger.warning("PlotTabWidget: No series found with data for plotting.")

    def _add_series_to_plot_list(self, plot_list, sensor_type, metric_type, unit, time_range_str, label_suffix=""):
        """Helper function to fetch data and add a series to the plot_list."""
        timestamps, values = self.data_store.get_historical_data(
            sensor_type=sensor_type,
            metric_type=metric_type,
            time_range_str=time_range_str
        )

        if timestamps and values:
            thresholds = self.data_store.get_thresholds(sensor_type, metric_type)
            low_thr = thresholds.get('low')
            high_thr = thresholds.get('high')

            label = f"{sensor_type} {metric_type.replace('_', ' ').title()}"
            if label_suffix: # For "Temperature Comparison" or similar specific labels
                label = f"{metric_type.replace('_', ' ').title()} {label_suffix}" 

            plot_list.append({
                'x': timestamps,
                'y': values,
                'label': label,
                'y_unit': unit,
                'low_threshold': low_thr,
                'high_threshold': high_thr
            })
            logger.debug(f"PlotTabWidget: Added series for {sensor_type}-{metric_type} with {len(timestamps)} points.")
        else:
            logger.debug(f"PlotTabWidget: No data for {sensor_type}-{metric_type} in {time_range_str}. Skipping adding series.")

    def save_plot_time_range_setting(self):
        """Saves the currently selected plot time range to settings."""
        current_range = self.time_range_combo.currentText()
        self.settings_manager.set_setting('General', 'plot_tab_time_range', current_range)
        logging.info(f"Plot tab time range setting saved: {current_range}")

    def initialize_tab_data(self):
        """
        Initializes the data for this tab (e.g., loads initial plot data).
        This method is called by AnaviSensorUI.
        """
        logger.info("PlotTabWidget: Initializing tab data.")
        self._populate_sensor_combo() # Populate sensor combo on init
        # After sensor combo is populated, populate the metric combo based on the initial sensor selection
        self._populate_metric_combo(self.current_sensor_selection) 
        self.update_plot_data() # Perform initial plot update
        self.update_theme_colors(self.theme_colors) # Ensure theme is applied
        logger.info("PlotTabWidget: Tab data initialization complete.")


    def update_theme_colors(self, theme_colors):
        """
        Updates the theme colors for this tab's plot widgets and re-polishes the tab.
        :param theme_colors: The updated dictionary of theme colors.
        """
        logger.debug("PlotTabWidget: Updating theme colors and re-polishing.")
        self.theme_colors.update(theme_colors) # Update internal reference

        # Propagate theme colors to the MatplotlibWidget
        if self.matplotlib_plot:
            self.matplotlib_plot.theme_colors.update(theme_colors)
            self.matplotlib_plot.apply_theme() # Re-apply theme to redraw plot with new colors
            logger.debug("PlotTabWidget: Matplotlib plot theme updated.")

        # Re-polish the widgets to apply new QSS
        self.style().polish(self)
        for label in self.findChildren(QLabel):
            label.style().polish(label)
        self.time_range_combo.style().polish(self.time_range_combo)
        self.sensor_combo.style().polish(self.sensor_combo) 
        self.metric_label.style().polish(self.metric_label) # NEW: Polish metric label
        self.metric_combo.style().polish(self.metric_combo) # NEW: Polish metric combo
        logger.debug("PlotTabWidget: Tab re-polished to apply new theme QSS.")

