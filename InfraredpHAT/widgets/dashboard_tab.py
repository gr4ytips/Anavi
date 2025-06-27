from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QComboBox, QSizePolicy
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
import logging
import re
import datetime

from widgets.sensor_display import SensorDisplayWidget
from widgets.matplotlib_widget import MatplotlibWidget

logger = logging.getLogger(__name__) # Added explicit logger

class DashboardTab(QWidget):
    """
    Dashboard tab displaying current sensor values with thresholds
    and a customizable plot area.
    """
    def __init__(self, data_store, thresholds, main_window, theme_colors, initial_gauge_type, initial_gauge_style, parent=None):
        super().__init__(parent)
        self.setObjectName("DashboardTab") # Added object name for QSS
        self.data_store = data_store
        # CRITICAL: This thresholds dictionary will be updated by AnaviSensorUI
        # This is a reference to the global thresholds dictionary, which AnaviSensorUI manages.
        self.thresholds = thresholds 
        self.main_window = main_window # Store main_window reference
        self.theme_colors = dict(theme_colors) if theme_colors is not None else {} # Store theme colors, defensive copy
        
        self.current_sensor_data = {} # Store last received data

        self.initial_gauge_type = initial_gauge_type
        self.initial_gauge_style = initial_gauge_style

        # Dictionary to store references to SensorDisplayWidget instances for easy iteration
        self.sensor_display_widgets = {}

        # Initialize MatplotlibWidget here so it is available before setup_ui for theme updates
        self.matplotlib_widget = MatplotlibWidget(parent=self, theme_colors=self.theme_colors) # Pass defensive copy of theme_colors

        self.setup_ui()
        self.connect_signals()
        logger.info("DashboardTab initialized.")

    def setup_ui(self):
        """Initializes and arranges the UI elements for the dashboard tab."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10) # Add some margins
        main_layout.setSpacing(10) # Spacing between elements

        # --- Top Controls Layout (Time Range and Metric Selection) ---
        top_controls_layout = QHBoxLayout()
        top_controls_layout.setContentsMargins(0, 0, 0, 10) # Bottom margin for separation
        top_controls_layout.setSpacing(10)

        # Time Range Selection
        time_range_label = QLabel("Plot Time Range:")
        time_range_label.setObjectName("DashboardLabel") # For QSS
        self.time_range_combo = QComboBox()
        self.time_range_combo.setObjectName("DashboardComboBox") # For QSS
        self.time_range_combo.addItems([
            "Last 10 minutes", "Last 30 minutes", "Last 1 hour", 
            "Last 3 hours", "Last 6 hours", "Last 12 hours", 
            "Last 24 hours", "All Data"
        ])
        # Set default from settings or hardcoded if not found
        default_time_range = self.main_window.settings_manager.get_setting('General', 'dashboard_plot_time_range', type=str, default="Last 30 minutes")
        index = self.time_range_combo.findText(default_time_range)
        if index != -1:
            self.time_range_combo.setCurrentIndex(index)
        
        top_controls_layout.addWidget(time_range_label)
        top_controls_layout.addWidget(self.time_range_combo)

        # Single Sensor Metric Selection (now for all sensors combined)
        sensor_metric_label = QLabel("Select Metric:")
        sensor_metric_label.setObjectName("DashboardLabel") # For QSS
        self.sensor_metric_combo = QComboBox()
        self.sensor_metric_combo.setObjectName("DashboardComboBox") # For QSS
        self._populate_sensor_metric_combo() # Populate based on available sensor configs

        top_controls_layout.addWidget(sensor_metric_label)
        top_controls_layout.addWidget(self.sensor_metric_combo)
        
        top_controls_layout.addStretch(1) # Pushes everything to the left

        main_layout.addLayout(top_controls_layout)

        # --- Sensor Display Widgets (Grid Layout) ---
        self.sensor_display_group = QGroupBox("Current Sensor Readings")
        self.sensor_display_group.setObjectName("DashboardGroupBox") # For QSS
        self.sensor_display_layout = QHBoxLayout(self.sensor_display_group) # Use QHBoxLayout
        self.sensor_display_layout.setContentsMargins(10, 20, 10, 10)
        self.sensor_display_layout.setSpacing(15) # Spacing between individual sensor displays
        self.sensor_display_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop) # Align widgets to top-left

        self._create_sensor_display_widgets() # Create instances of SensorDisplayWidget

        main_layout.addWidget(self.sensor_display_group)

        # --- Matplotlib Plot Area ---
        plot_group = QGroupBox("Historical Data Plot")
        plot_group.setObjectName("DashboardGroupBox") # For QSS
        plot_layout = QVBoxLayout(plot_group)
        plot_layout.setContentsMargins(10, 20, 10, 10)
        plot_layout.setSpacing(5) # Smaller spacing for plot area

        plot_layout.addWidget(self.matplotlib_widget) # Add the MatplotlibWidget instance

        main_layout.addWidget(plot_group)

        main_layout.setStretchFactor(self.sensor_display_group, 1) # Allow sensor displays to take reasonable space
        main_layout.setStretchFactor(plot_group, 3) # Plot area takes more vertical space

        self.setLayout(main_layout)


    def _populate_sensor_metric_combo(self):
        """
        Populates the sensor_metric_combo with available sensor_type_metric_type combinations.
        """
        self.sensor_metric_combo.clear()
        
        configured_sensors = self.main_window.settings_manager.get_sensor_configs()
        # Ensure consistent order
        display_order = ['HTU21D', 'BMP180', 'BH1750'] 

        items = []
        for sensor_type in display_order:
            if sensor_type in configured_sensors:
                for metric_type in configured_sensors[sensor_type]:
                    unit = self.main_window.settings_manager.get_unit_for_metric(sensor_type, metric_type)
                    formatted_name = f"{sensor_type} {metric_type.capitalize()} ({unit})"
                    # Store data as "sensor_type_metric_type" in the combo box for easy retrieval
                    items.append((formatted_name, f"{sensor_type}_{metric_type}"))

        # Sort items alphabetically by display name before adding
        items.sort(key=lambda x: x[0])
        
        # Add a "All Metrics" option at the top
        self.sensor_metric_combo.addItem("All Metrics", "all")
        for display_name, data_value in items:
            self.sensor_metric_combo.addItem(display_name, data_value)

        logger.debug(f"DashboardTab: Sensor metric combo populated with {self.sensor_metric_combo.count()} items.")


    def _create_sensor_display_widgets(self):
        """
        Creates and adds SensorDisplayWidget instances to the layout
        based on configured sensors and metrics.
        """
        # Clear existing widgets from layout if any (important for re-creation)
        for i in reversed(range(self.sensor_display_layout.count())): 
            widget_item = self.sensor_display_layout.itemAt(i)
            if widget_item:
                widget = widget_item.widget()
                if widget:
                    self.sensor_display_layout.removeWidget(widget)
                    widget.deleteLater()
        self.sensor_display_widgets.clear() # Clear the dictionary of references

        configured_sensors = self.main_window.settings_manager.get_sensor_configs()
        display_order = ['HTU21D', 'BMP180', 'BH1750'] # Maintain consistent order for display

        for sensor_type in display_order:
            if sensor_type in configured_sensors:
                for metric_type in configured_sensors[sensor_type]:
                    # --- MODIFICATION: Changed title to only show metric type ---
                    title = f"{metric_type.capitalize()}"
                    unit = self.main_window.settings_manager.get_unit_for_metric(sensor_type, metric_type)
                    
                    # --- FIX: Ensure thresholds passed to SensorDisplayWidget are correctly cased and complete ---
                    # Get the full thresholds dictionary from the settings manager (which has lowercase keys)
                    all_thresholds_from_settings = self.main_window.settings_manager.get_all_thresholds()
                    # Lookup with lowercase keys for consistency with how get_all_thresholds returns them
                    metric_thresholds = all_thresholds_from_settings.get(sensor_type.lower(), {}).get(metric_type.lower(), {})
                    
                    display_widget = SensorDisplayWidget(
                        title=title,
                        unit=unit,
                        thresholds=metric_thresholds, # Pass the specific metric's thresholds
                        metric_type=metric_type,
                        sensor_category=sensor_type,
                        main_window=self.main_window,
                        theme_colors=self.theme_colors, # Pass theme colors reference
                        initial_gauge_type=self.initial_gauge_type, # Use initial gauge type from settings
                        initial_gauge_style=self.initial_gauge_style, # Use initial gauge style from settings
                        parent=self.sensor_display_group # Parent to the group box
                    )
                    # Connect the alert_state_changed signal from each display widget to MainWindow
                    display_widget.alert_state_changed.connect(self.main_window.on_sensor_alert_state_changed)
                    
                    # This setSizePolicy was already there from the previous modification.
                    display_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

                    self.sensor_display_layout.addWidget(display_widget)
                    self.sensor_display_widgets[f"{sensor_type}_{metric_type}"] = display_widget
                    logger.debug(f"DashboardTab: Created SensorDisplayWidget for {sensor_type} {metric_type}.")


    def connect_signals(self):
        """Connects signals for the dashboard tab."""
        self.time_range_combo.currentIndexChanged.connect(self.update_plot_data)
        self.sensor_metric_combo.currentIndexChanged.connect(self.update_plot_data)
        
        # Connect to ensure the plot is resized correctly
        self.matplotlib_widget.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.matplotlib_widget.canvas.updateGeometry()

        logger.debug("DashboardTab: Signals connected.")

    def initialize_tab_data(self, theme_colors):
        """
        Initializes or refreshes all data displayed on this tab, including plot and gauges.
        This is called by AnaviSensorUI after initial setup or when tab becomes visible.
        :param theme_colors: The current theme colors dictionary.
        """
        logger.info("DashboardTab: Initializing all tab data.")
        # --- FIX: Ensure the tab's internal theme_colors is updated here as well ---
        self.theme_colors.update(theme_colors) # Ensure tab's own colors are fresh
        # Propagate to plot and sensor display widgets
        self.matplotlib_widget.theme_colors.update(self.theme_colors) # Pass the tab's (now updated) theme_colors
        self.matplotlib_widget.apply_theme() # Correct method to apply theme
        
        # Renamed method below from update_sensor_display_widgets_with_latest_data to update_sensor_values
        self.update_sensor_values(self.data_store.get_latest_data()) # Pass latest data to update values
        self.update_plot_data() # Then update plot
        
        # --- FIX: Re-initialize and update theme colors for sensor display widgets here ---
        # This loop is crucial to ensure all existing sensor display widgets get the updated theme colors
        # after the tab's theme_colors are updated.
        for display_widget in self.sensor_display_widgets.values():
            display_widget.update_theme_colors(self.theme_colors) # Pass the tab's (now updated) theme_colors
        
        logger.info("DashboardTab: All tab data initialized.")


    def update_sensor_values(self, data):
        """
        Updates the individual sensor display widgets with new data.
        This method is called by AnaviSensorUI and internally by initialize_tab_data.
        """
        self.current_sensor_data = data # Store the latest data
        logger.debug(f"DashboardTab: update_sensor_values called. Raw data: {data}")

        if not data:
            logger.debug("DashboardTab: No data available in update_sensor_values. Setting displays to N/A.")
            for display_widget in self.sensor_display_widgets.values():
                display_widget.update_value(None)
                display_widget.update() # Force repaint for N/A state
            return

        for sensor_type, metrics in data.items():
            for metric_type, value_dict in metrics.items():
                widget_key = f"{sensor_type}_{metric_type}"
                if widget_key in self.sensor_display_widgets:
                    # Check if 'value' key exists in the nested dictionary
                    if 'value' in value_dict:
                        value = value_dict['value']
                        self.sensor_display_widgets[widget_key].update_value(value) # Pass only value
                        
                        # --- MODIFICATION START ---
                        # Explicitly call update() for ALL types now, as per user request to force display
                        # This overrides the internal 'no repaint if value unchanged' logic
                        self.sensor_display_widgets[widget_key].update() # Force repaint
                        # --- MODIFICATION END ---

                        logger.debug(f"DashboardTab: Updated {sensor_type} {metric_type} display with value: {value}.")
                    else:
                        self.sensor_display_widgets[widget_key].update_value(None) # Set to N/A if 'value' key is missing
                        self.sensor_display_widgets[widget_key].update() # Force repaint for N/A state
                        logger.warning(f"DashboardTab: 'value' key missing for {sensor_type} {metric_type} in data. Setting to N/A.")
                else:
                    logger.warning(f"DashboardTab: No display widget found for {widget_key}. Data received but not displayed.")
        logger.debug("DashboardTab: All sensor display widgets updated.")


    def update_plot_data(self):
        """
        Fetches historical data based on current selections and updates the plot.
        """
        logger.info("DashboardTab: Updating plot data.")
        selected_time_range = self.time_range_combo.currentText()
        selected_metric_data = self.sensor_metric_combo.currentData() # This is like "HTU21D_temperature" or "all"

        if selected_metric_data == "all":
            # Plot all available sensor metrics
            plot_data_series = []
            configured_sensors = self.main_window.settings_manager.get_sensor_configs()
            display_order = ['HTU21D', 'BMP180', 'BH1750']

            for sensor_type in display_order:
                if sensor_type in configured_sensors:
                    for metric_type in configured_sensors[sensor_type]:
                        unit = self.main_window.settings_manager.get_unit_for_metric(sensor_type, metric_type)
                        label = f"{sensor_type} {metric_type.capitalize()}"
                        
                        # Get historical data for each metric
                        x_data, y_data = self.data_store.get_historical_data(
                            sensor_type=sensor_type,
                            metric_type=metric_type,
                            time_range_str=selected_time_range
                        )
                        # Get thresholds for the plot lines
                        # --- FIX: Use lowercase keys when getting thresholds from self.thresholds ---
                        metric_thresholds = self.thresholds.get(sensor_type.lower(), {}).get(metric_type.lower(), {})
                        low_thr = metric_thresholds.get('low')
                        high_thr = metric_thresholds.get('high')

                        plot_data_series.append({
                            'x': x_data,
                            'y': y_data,
                            'label': label,
                            'y_unit': unit,
                            'low_threshold': low_thr,
                            'high_threshold': high_thr
                        })
            if plot_data_series:
                self.matplotlib_widget.plot_data(plot_data_series, self.theme_colors)
            else:
                self.matplotlib_widget.set_status_message("No data available to plot for selected range.")
                logger.warning("DashboardTab: No data series to plot for 'All Metrics'.")

        else:
            # Plot a single selected sensor metric
            parts = selected_metric_data.split('_')
            sensor_type = parts[0]
            metric_type = parts[1]
            unit = self.main_window.settings_manager.get_unit_for_metric(sensor_type, metric_type)
            label = f"{sensor_type} {metric_type.capitalize()}"

            x_data, y_data = self.data_store.get_historical_data(
                sensor_type=sensor_type,
                metric_type=metric_type,
                time_range_str=selected_time_range
            )
            
            # Get thresholds for the plot lines
            # --- FIX: Use lowercase keys when getting thresholds from self.thresholds ---
            metric_thresholds = self.thresholds.get(sensor_type.lower(), {}).get(metric_type.lower(), {})
            low_thr = metric_thresholds.get('low')
            high_thr = metric_thresholds.get('high')

            if x_data and y_data:
                plot_data_series = [{
                    'x': x_data,
                    'y': y_data,
                    'label': label,
                    'y_unit': unit,
                    'low_threshold': low_thr,
                    'high_threshold': high_thr
                }]
                self.matplotlib_widget.plot_data(plot_data_series, self.theme_colors)
            else:
                self.matplotlib_widget.set_status_message(f"No historical data for {label} in {selected_time_range}.")
                logger.warning(f"DashboardTab: No historical data for {label} in {selected_time_range}.")

        logger.info("DashboardTab: Plot data update completed.")


    def update_theme_colors(self, theme_colors):
        """Updates the theme colors for this tab's plot widget and re-polishes the tab."""
        logger.debug("DashboardTab: Updating theme colors and re-polishing.")
        self.theme_colors.update(theme_colors) # Store theme colors

        # Propagate theme colors to the MatplotlibWidget instance
        self.matplotlib_widget.theme_colors.update(self.theme_colors) # Pass the tab's (now updated) theme_colors
        self.matplotlib_widget.apply_theme() # Re-apply theme to redraw plot with new colors

        # Apply QSS styling to the group box and combo boxes
        self.style().polish(self)
        for group_box in self.findChildren(QGroupBox):
            group_box.style().polish(group_box)

        # Polish the combo boxes
        self.time_range_combo.style().polish(self.time_range_combo)
        self.sensor_metric_combo.style().polish(self.sensor_metric_combo) # Polish the new single combo

        # Also polish labels within the top controls layout
        for label in self.findChildren(QLabel):
            label.style().polish(label)

        logger.debug("DashboardTab: Tab re-polished to apply new theme QSS.")
        # CRITICAL FIX: Also ensure SensorDisplayWidgets are updated with new theme colors AND thresholds
        for display_widget in self.sensor_display_widgets.values():
            # Pass the theme colors to update its appearance based on alert state
            display_widget.update_theme_colors(self.theme_colors) # Pass the tab's (now updated) theme_colors

    def update_gauge_styles(self, gauge_type, gauge_style):
        """
        Propagates gauge type and style changes to all SensorDisplayWidgets on this tab.
        This method is called by AnaviSensorUI.
        """
        logger.info(f"DashboardTab: Propagating gauge style (Type='{gauge_type}', Style='{gauge_style}') to individual displays.")
        # Iterate through the stored sensor_display_widgets dictionary
        for display_widget in self.sensor_display_widgets.values():
            display_widget.update_gauge_display_type_and_style(gauge_type, gauge_style)
        logger.debug("DashboardTab: All SensorDisplayWidgets updated with new gauge style.")    

    def _get_num_data_points_for_time_range(self, time_range_str):
        """
        Converts a time range string (e.g., "Last 10 minutes") to a number of data points.
        Assumes the sampling rate from settings_manager.
        This method is now mostly for illustrative purposes, as get_historical_data
        now uses time-based filtering.
        """
        if time_range_str == "All Data":
            return self.data_store.max_points

        max_points = self.data_store.max_points
        sampling_rate_ms = self.main_window.settings_manager.get_setting('General', 'sampling_rate_ms', type=int, default=5000)
        sampling_rate_sec = sampling_rate_ms / 1000.0

        unit_map = {
            "minute": 60,
            "minutes": 60,
            "hour": 3600,
            "hours": 3600,
            "day": 86400,
            "days": 86400
        }

        match = re.match(r"Last (\d+)\s*(minute|minutes|hour|hours|day|days)", time_range_str, re.IGNORECASE)
        if match:
            value = int(match.group(1))
            unit = match.group(2).lower()
            duration_sec = value * unit_map.get(unit, 1)
            
            # Calculate num_points needed to cover the duration, clamped by max_points
            num_points = min(max_points, int(duration_sec / sampling_rate_sec))
            logger.debug(f"DashboardTab: Time range '{time_range_str}' resolves to ~{num_points} data points.")
            return num_points
        
        logger.warning(f"DashboardTab: Unknown time range format: '{time_range_str}'. Returning max_points.")
        return max_points # Fallback
