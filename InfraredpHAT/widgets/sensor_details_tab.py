from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QComboBox, QSizePolicy, QSpacerItem
from PyQt5.QtCore import Qt, QTimer, QSize # Import QSize
from PyQt5.QtGui import QFont
import logging
import re
import datetime

from widgets.sensor_display import SensorDisplayWidget
from widgets.matplotlib_widget import MatplotlibWidget

logger = logging.getLogger(__name__) # Added explicit logger

class SensorDetailsTab(QWidget):
    """
    Sensor Details tab displaying individual sensor metrics with
    larger gauges and dedicated plots for each, arranged in a left (gauges)
    and right (plots) column layout with a global time range control.
    Plots are now arranged side-by-side per sensor type, then stacked,
    with improved sizing and spacing.
    """
    def __init__(self, data_store, thresholds, main_window, theme_colors, initial_gauge_type, initial_gauge_style, parent=None):
        super().__init__(parent)
        self.setObjectName("SensorDetailsTab") # Added object name for QSS
        self.data_store = data_store
        # CRITICAL: This thresholds dictionary will be updated by AnaviSensorUI
        self.thresholds = thresholds
        self.main_window = main_window
        self.theme_colors = dict(theme_colors) if theme_colors is not None else {} # Store theme colors, defensive copy

        self.current_sensor_data = {}

        self.matplotlib_widgets = {} # Stores MatplotlibWidget instances for each sensor type
        self.sensor_display_widgets = {} # Important: Store these for later access to update themes/thresholds

        self.initial_gauge_type = initial_gauge_type
        self.initial_gauge_style = initial_gauge_style

        # Initialize MatplotlibWidgets for each anticipated plot - REVISED
        configured_sensors = self.main_window.settings_manager.get_sensor_configs()
        # Only create one plot widget per sensor type
        for sensor_type in configured_sensors.keys():
            plot_key = f"{sensor_type}_plot" # Key by sensor type, not metric
            self.matplotlib_widgets[plot_key] = MatplotlibWidget(
                parent=self,
                theme_colors=self.theme_colors, # Pass the tab's own theme_colors (defensive copy)
                show_toolbar=False # Hide toolbar for these detail plots
            )
            self.matplotlib_widgets[plot_key].setObjectName(f"{sensor_type}CombinedPlotWidget") # For QSS

        self.setup_ui()
        self.connect_signals()
        logger.info("SensorDetailsTab initialized.")


    def setup_ui(self):
        """Sets up the layout and widgets for the sensor details tab."""
        # Main horizontal layout for the entire SensorDetailsTab content (Left Gauges | Right Plots)
        tab_main_h_layout = QHBoxLayout(self)
        tab_main_h_layout.setContentsMargins(10, 10, 10, 10) # Padding around the entire tab content
        tab_main_h_layout.setSpacing(25) # Increased spacing between the left and right columns
        tab_main_h_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        # --- Left Column: All Gauges (Stacked Group Boxes) ---
        left_gauges_column_v_layout = QVBoxLayout()
        left_gauges_column_v_layout.setContentsMargins(0, 0, 0, 0)
        left_gauges_column_v_layout.setSpacing(15) # Spacing between sensor group boxes
        left_gauges_column_v_layout.setAlignment(Qt.AlignTop)

        # Move Global Time Range Control to the top-left, above gauges
        global_controls_layout = QHBoxLayout()
        global_controls_layout.setContentsMargins(0, 0, 0, 0)
        global_controls_layout.setSpacing(10)

        global_time_range_label = QLabel("Time Range for Plots:")
        global_time_range_label.setObjectName("PlotControlLabel") # For QSS
        global_controls_layout.addWidget(global_time_range_label)

        self.global_time_range_combo = QComboBox()
        self.global_time_range_combo.setObjectName("PlotControlComboBox") # For QSS
        self.global_time_range_combo.addItems(["Last 10 minutes", "Last 30 minutes", "Last 1 hour", "Last 3 hours", "Last 6 hours", "Last 12 hours", "Last 24 hours", "All Data"])

        initial_detail_time_range = self.main_window.settings_manager.get_setting('General', 'detail_plot_time_range', type=str, default="Last 10 minutes")
        self.global_time_range_combo.setCurrentText(initial_detail_time_range)

        global_controls_layout.addWidget(self.global_time_range_combo)
        global_controls_layout.addStretch(1) # Push to the left

        left_gauges_column_v_layout.addLayout(global_controls_layout) # Add to the left column
        logger.debug(f"SensorDetailsTab: Global controls layout added to left column.")


        configured_sensors = self.main_window.settings_manager.get_sensor_configs()
        display_order = ['HTU21D', 'BMP180', 'BH1750'] # Ensure consistent order

        # Populate the left gauges column
        for sensor_type in display_order:
            if sensor_type not in configured_sensors:
                continue

            sensor_group_box = QGroupBox(f"{sensor_type} Gauges") # Group box for gauges
            sensor_group_box.setObjectName(f"{sensor_type}GaugeGroupBox")

            # Horizontal layout for gauges within this sensor's group box (e.g., Temp and Humidity side-by-side)
            gauges_h_layout_in_group = QHBoxLayout(sensor_group_box)
            gauges_h_layout_in_group.setContentsMargins(10, 20, 10, 10) # Padding inside group box
            gauges_h_layout_in_group.setSpacing(10) # Spacing between individual gauges
            gauges_h_layout_in_group.setAlignment(Qt.AlignLeft | Qt.AlignTop) # Align content to top-left

            for metric_type in configured_sensors[sensor_type]:
                sensor_metric_key = f"{sensor_type}_{metric_type}"

                title = f"{metric_type.capitalize()}"
                unit = self.main_window.settings_manager.get_unit_for_metric(sensor_type, metric_type)
                
                all_thresholds_from_settings = self.main_window.settings_manager.get_all_thresholds()
                metric_thresholds = all_thresholds_from_settings.get(sensor_type.lower(), {}).get(metric_type.lower(), {})

                display_widget = SensorDisplayWidget(
                    title=title,
                    unit=unit,
                    thresholds=metric_thresholds, # Pass the specific metric's thresholds
                    metric_type=metric_type,
                    sensor_category=sensor_type,
                    main_window=self.main_window,
                    theme_colors=self.theme_colors, # Pass the tab's own theme_colors (defensive copy)
                    initial_gauge_type=self.initial_gauge_type,
                    initial_gauge_style=self.initial_gauge_style,
                    parent=sensor_group_box
                )
                display_widget.alert_state_changed.connect(self.main_window.on_sensor_alert_state_changed)
                self.sensor_display_widgets[sensor_metric_key] = display_widget
                
                display_widget.setMinimumSize(QSize(150, 150)) # Maintain minimum size
                # Each gauge will expand if space allows within its QHBoxLayout
                gauges_h_layout_in_group.addWidget(display_widget, 1) # Assign stretch factor of 1 to each gauge
                logger.debug(f"SensorDetailsTab: Added gauge for {sensor_type}-{metric_type}.")

            # --- FIX: Removed addStretch(1) from inside the group box layout ---
            # This allows the group box to resize horizontally to fit its contents
            # if there are fewer gauges, or for gauges to evenly divide space if more.
            
            left_gauges_column_v_layout.addWidget(sensor_group_box)

        left_gauges_column_v_layout.addStretch(1) # This stretch belongs to the main left column layout
        tab_main_h_layout.addLayout(left_gauges_column_v_layout, 1)


        # --- Right Column: Plots organized by sensor in rows ---
        right_plots_column_v_layout = QVBoxLayout()
        right_plots_column_v_layout.setContentsMargins(0, 0, 0, 0)
        right_plots_column_v_layout.setSpacing(20) # Increased spacing between plot rows
        right_plots_column_v_layout.setAlignment(Qt.AlignTop)


        # Populate the right plots column with one plot per sensor type, stacked vertically
        for sensor_type in display_order:
            if sensor_type not in configured_sensors:
                continue

            # Retrieve the single MatplotlibWidget instance for this sensor type
            plot_key = f"{sensor_type}_plot"
            matplotlib_plot = self.matplotlib_widgets[plot_key]

            # Set a title for the combined plot
            matplotlib_plot.ax.set_title(f"{sensor_type} Data Trends")

            matplotlib_plot.setMinimumSize(450, 300) # Increased height from 250 to 300
            matplotlib_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

            # Add the plot directly to the vertical layout, giving it vertical stretch of 1
            right_plots_column_v_layout.addWidget(matplotlib_plot, 1)
            logger.debug(f"SensorDetailsTab: Added combined plot for {sensor_type} to right column.")

        right_plots_column_v_layout.addStretch(1) # Push all plot rows to the top of the right column
        tab_main_h_layout.addLayout(right_plots_column_v_layout, 2)

        self.setLayout(tab_main_h_layout) # Set the main horizontal layout for the tab

        logger.debug("SensorDetailsTab UI setup complete with two-column layout.")


    def connect_signals(self):
        """Connects signals for the global plot time range control."""
        # Connect the global time range combo box to update all plots
        self.global_time_range_combo.currentTextChanged.connect(self.update_all_plots)
        self.global_time_range_combo.currentTextChanged.connect(self.save_plot_time_range_setting) # Save setting when changed
        logger.debug("SensorDetailsTab: Global time range signal connected.")

    def update_sensor_values(self, data):
        """
        Updates the individual sensor display widgets with new data.
        This method is called by AnaviSensorUI.
        """
        self.current_sensor_data = data
        logger.debug(f"SensorDetailsTab: update_sensor_values called. Raw data: {data}")

        for sensor_metric_key, display_widget in self.sensor_display_widgets.items():
            parts = sensor_metric_key.split('_')
            sensor_type = parts[0]
            metric_type = parts[1]

            if sensor_type in data and metric_type in data[sensor_type]:
                value_dict = data[sensor_type][metric_type]
                if 'value' in value_dict:
                    value = value_dict['value']
                    display_widget.update_value(value)
                    logger.debug(f"SensorDetailsTab: Updated {sensor_type} {metric_type} display with value: {value}.")
                else:
                    display_widget.update_value(None)
                    logger.warning(f"SensorDetailsTab: 'value' key missing for {sensor_type} {metric_type} in data. Setting to N/A.")
            else:
                display_widget.update_value(None)
                logger.warning(f"SensorDetailsTab: Data for {sensor_type} {metric_type} not found in current update. Setting to N/A for display.")


    def update_single_plot(self, sensor_type): # PARAMETER CHANGED
        """
        Updates a single plot (which might contain multiple series) using the GLOBAL time range selection.
        :param sensor_type: A string like "HTU21D" to identify the combined plot.
        """
        logger.info(f"SensorDetailsTab: Updating combined plot for {sensor_type}.")

        # Get selected time range from the GLOBAL combo box
        selected_time_range = self.global_time_range_combo.currentText()

        plot_key = f"{sensor_type}_plot"
        matplotlib_widget = self.matplotlib_widgets.get(plot_key) # Get by sensor type

        if not matplotlib_widget:
            logger.error(f"SensorDetailsTab: Matplotlib widget not found for sensor type: {sensor_type}.")
            return

        configured_metrics = self.main_window.settings_manager.get_sensor_configs().get(sensor_type, [])
        if not configured_metrics:
            matplotlib_widget.set_status_message(f"No configured metrics found for {sensor_type}.")
            logger.warning(f"SensorDetailsTab: No configured metrics for {sensor_type}. Cannot plot.")
            return

        plot_series_list = []
        has_any_data = False

        for metric_type in configured_metrics:
            logger.debug(f"SensorDetailsTab: Fetching data for {sensor_type} {metric_type} over GLOBAL '{selected_time_range}'.")
            timestamps, values = self.data_store.get_historical_data(
                sensor_type=sensor_type,
                metric_type=metric_type,
                time_range_str=selected_time_range
            )
            logger.debug(f"SensorDetailsTab: Fetched {len(timestamps)} data points for {sensor_type}_{metric_type}.")

            if timestamps:
                has_any_data = True
                y_unit = self.main_window.settings_manager.get_unit_for_metric(sensor_type, metric_type)
                # --- FIX: Use lowercase keys when getting thresholds from self.thresholds ---
                metric_thresholds = self.thresholds.get(sensor_type.lower(), {}).get(metric_type.lower(), {})
                low_thr = metric_thresholds.get('low')
                high_thr = metric_thresholds.get('high')

                plot_series_list.append({
                    'x': timestamps,
                    'y': values,
                    'label': f"{sensor_type} {metric_type.capitalize()}", # Label includes both sensor and metric
                    'y_unit': y_unit,
                    'low_threshold': low_thr,
                    'high_threshold': high_thr
                })

        if not has_any_data:
            matplotlib_widget.set_status_message(f"No data available for {sensor_type} in this time range.")
            logger.info(f"SensorDetailsTab: No historical data to plot for {sensor_type}.")
            return

        matplotlib_widget.plot_data(plot_series_list, self.theme_colors)
        logger.info(f"SensorDetailsTab: Plot data updated successfully for {sensor_type}.")


    def update_all_plots(self):
        """
        Updates all plots on the Sensor Details tab.
        This method is called when the global time range selection changes or the tab is activated.
        """
        logger.info("SensorDetailsTab: Updating all plots based on global time range.")
        # Iterate through sensor types as keys in matplotlib_widgets
        configured_sensors = self.main_window.settings_manager.get_sensor_configs()
        for sensor_type in configured_sensors.keys():
            self.update_single_plot(sensor_type)

    def initialize_tab_data(self, theme_colors):
        """
        Initializes data for the Sensor Details tab, including all plots.
        Ensures plots are drawn with the correct theme.
        """
        logger.info("SensorDetailsTab: Initializing tab data (plots and display widgets).")
        # --- FIX: Ensure the tab's internal theme_colors is updated here as well ---
        self.theme_colors.update(theme_colors) # Ensure tab's own colors are fresh
        # Propagate to plot widgets
        for plot_widget in self.matplotlib_widgets.values():
            plot_widget.theme_colors.update(self.theme_colors) # Pass the tab's (now updated) theme_colors
            plot_widget.apply_theme()
            logger.debug(f"SensorDetailsTab: Applied theme to plot widget {plot_widget.objectName()}.")

        self.update_all_plots() # This will now use the global time range
        # --- FIX: Call update_sensor_display_theme_colors with the tab's (now updated) theme_colors ---
        self.update_sensor_display_theme_colors(self.theme_colors) # Ensure all display widgets get the updated theme
        
        logger.info("SensorDetailsTab: Tab data initialization complete.")


    def save_plot_time_range_setting(self):
        """Saves the currently selected global plot time range to settings."""
        current_range = self.global_time_range_combo.currentText()
        self.main_window.settings_manager.set_setting('General', 'detail_plot_time_range', current_range)
        logging.info(f"Sensor details plot time range set to: {current_range}")


    def update_gauge_styles(self, gauge_type, gauge_style):
        """
        Propagates gauge type and style changes to all SensorDisplayWidgets on this tab.
        This method is called by AnaviSensorUI.
        """
        logger.info(f"SensorDetailsTab: Propagating gauge style (Type='{gauge_type}', Style='{gauge_style}') to individual displays.")
        for display_widget in self.sensor_display_widgets.values():
            display_widget.update_gauge_display_type_and_style(gauge_type, gauge_style)
        logger.debug("SensorDetailsTab: All SensorDisplayWidgets updated with new gauge style.")


    def update_sensor_display_theme_colors(self, theme_colors):
        """
        Updates the theme colors for all SensorDisplayWidgets on this tab.
        This ensures individual gauges respond to theme changes.
        """
        logger.debug("SensorDetailsTab: Updating SensorDisplayWidgets with new theme colors.")
        for display_widget in self.sensor_display_widgets.values():
            # --- FIX: Pass the correct theme_colors to the individual display widgets ---
            display_widget.update_theme_colors(theme_colors)


    def update_theme_colors(self, theme_colors):
        """Updates the theme colors for this tab's plot widget and re-polishes the tab."""
        logger.debug("SensorDetailsTab: Updating theme colors and re-polishing.")
        self.theme_colors.update(theme_colors)

        for plot_widget in self.matplotlib_widgets.values():
            plot_widget.theme_colors.update(self.theme_colors) # Pass the tab's (now updated) theme_colors
            plot_widget.apply_theme()

        self.style().polish(self)
        for group_box in self.findChildren(QGroupBox):
            group_box.style().polish(group_box)

        # Polish the global time range combo box
        self.global_time_range_combo.style().polish(self.global_time_range_combo)

        for label in self.findChildren(QLabel):
            label.style().polish(label)

        logger.debug("SensorDetailsTab: Tab re-polished to apply new theme QSS.")
        # --- FIX: Call update_sensor_display_theme_colors with the tab's (now updated) theme_colors ---
        self.update_sensor_display_theme_colors(self.theme_colors)

