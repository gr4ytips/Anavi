# sensor_details_tab.py
# -*- coding: utf-8 -*-
import logging
from itertools import combinations as itertools_combinations
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
                             QScrollArea, QComboBox)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, pyqtSlot

from .sensor_display import SensorDisplayWidget
from .matplotlib_widget import MatplotlibWidget

logger = logging.getLogger(__name__)


class SensorDetailsTab(QWidget):
    """
    Displays detailed information for a selected sensor, dynamically creating
    widgets as needed to reflect current settings.
    """
    alert_triggered = pyqtSignal(str, str, str, str)
    alert_cleared = pyqtSignal(str, str)

    def __init__(self, data_store, settings_manager,
                 initial_gauge_type, initial_gauge_style,
                 initial_hide_matplotlib_toolbar, initial_plot_update_interval_ms,
                 initial_detail_plot_time_range,
                 main_window=None,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("SensorDetailsTab")

        self.data_store = data_store
        self.settings_manager = settings_manager
        self.theme_colors = self.settings_manager.get_theme_colors()
        self.main_window = main_window

        self.plot_update_interval_ms = initial_plot_update_interval_ms
        self.detail_plot_time_range = initial_detail_plot_time_range
        self.hide_matplotlib_toolbar = initial_hide_matplotlib_toolbar

        self.gauge_type = initial_gauge_type
        self.gauge_style = initial_gauge_style

        self.current_selected_sensor_type = None
        self.current_selected_plot_metric_type = None
        self.plot_metric_display_to_actual_map = {}
        self.gauge_widgets = {}

        self.plot_group_box = None
        self.gauges_layout_left = None
        self.sensor_selection_combo = None
        self.plot_time_range_combo = None
        self.plot_metric_type_combo = None
        self.plot_widget_right = None

        self.setup_ui()
        self.setup_connections()

    def initialize_tab_data(self, theme_colors):
        """Initializes the tab's data and UI state after creation."""
        logger.info("Initializing SensorDetailsTab data and theme.")
        self.theme_colors = theme_colors
        
        if self.plot_widget_right:
            self.plot_widget_right.update_theme_colors(theme_colors)

        self.populate_sensor_selection()
        
        self.plot_update_timer = QTimer(self)
        self.plot_update_timer.timeout.connect(self.update_all_plots)
        self.plot_update_timer.start(self.plot_update_interval_ms)
        logger.info("SensorDetailsTab initialized and timer started.")

    def setup_ui(self):
        """Sets up the main static layout for the tab."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- Top: Sensor Selection ---
        sensor_selection_group = QGroupBox("Select Sensor Type")
        sensor_selection_layout = QHBoxLayout(sensor_selection_group)
        self.sensor_selection_combo = QComboBox()
        sensor_selection_layout.addWidget(QLabel("Sensor:"))
        sensor_selection_layout.addWidget(self.sensor_selection_combo)
        sensor_selection_layout.addStretch(1)
        main_layout.addWidget(sensor_selection_group)

        # --- Main Content Area ---
        content_split_layout = QHBoxLayout()
        content_split_layout.setSpacing(10)

        # --- Left Column: Gauges ---
        gauges_scroll_area = QScrollArea()
        gauges_scroll_area.setObjectName("GaugesScrollArea")
        gauges_scroll_area.setWidgetResizable(True)
        gauges_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        gauges_container = QWidget()
        gauges_container.setObjectName("GaugesContainerWidget")
        self.gauges_layout_left = QVBoxLayout(gauges_container)
        self.gauges_layout_left.setAlignment(Qt.AlignTop)
        gauges_scroll_area.setWidget(gauges_container)

        # --- Right Column: Plot Area ---
        self.plot_group_box = QGroupBox("Data Trend")
        plot_layout = QVBoxLayout(self.plot_group_box)

        # Plot controls
        plot_controls_layout = QHBoxLayout()
        self.plot_time_range_combo = QComboBox()
        self.plot_metric_type_combo = QComboBox()
        self.plot_time_range_combo.addItems(self.data_store.get_available_time_ranges())
        self.plot_time_range_combo.setCurrentText(self.detail_plot_time_range)
        plot_controls_layout.addWidget(QLabel("Time Range:"))
        plot_controls_layout.addWidget(self.plot_time_range_combo)
        plot_controls_layout.addSpacing(20)
        plot_controls_layout.addWidget(QLabel("Metric:"))
        plot_controls_layout.addWidget(self.plot_metric_type_combo)
        plot_controls_layout.addStretch(1)
        plot_layout.addLayout(plot_controls_layout)

        # Plot widget
        self.plot_widget_right = MatplotlibWidget(
            self.theme_colors, self.settings_manager, hide_toolbar=self.hide_matplotlib_toolbar)
        plot_layout.addWidget(self.plot_widget_right)

        # --- Final Assembly ---
        content_split_layout.addWidget(gauges_scroll_area, 1)
        content_split_layout.addWidget(self.plot_group_box, 3)
        main_layout.addLayout(content_split_layout, 1)

    def setup_connections(self):
        """Sets up signal-slot connections."""
        self.settings_manager.settings_updated.connect(self._on_settings_updated)
        self.data_store.data_updated.connect(self.update_sensor_values)
        self.sensor_selection_combo.currentTextChanged.connect(self._on_sensor_type_selected)
        self.plot_time_range_combo.currentTextChanged.connect(self._on_plot_time_range_changed)
        self.plot_metric_type_combo.currentTextChanged.connect(self._on_plot_metric_type_changed)

    def populate_sensor_selection(self):
        """Populates the sensor selection combo box."""
        self.sensor_selection_combo.blockSignals(True)
        self.sensor_selection_combo.clear()
        all_sensor_types = sorted(self.settings_manager.DEFAULT_METRIC_INFO.keys())

        if not all_sensor_types:
            self.sensor_selection_combo.addItem("No Sensors Configured")
            self.sensor_selection_combo.setEnabled(False)
        else:
            self.sensor_selection_combo.addItems(all_sensor_types)
            self.sensor_selection_combo.setEnabled(True)
            initial_sensor = self.settings_manager.get_setting(
                'UI', 'sensor_details_selected_sensor_type', fallback=all_sensor_types[0])
            self.sensor_selection_combo.setCurrentText(initial_sensor)

        self.sensor_selection_combo.blockSignals(False)
        self._on_sensor_type_selected(self.sensor_selection_combo.currentText())

    @pyqtSlot(str)
    def _on_sensor_type_selected(self, sensor_type):
        """High-level coordinator for when a new sensor is selected."""
        if not sensor_type or sensor_type == "No Sensors Configured":
            self.current_selected_sensor_type = None
            self._clear_gauges()
            self.plot_group_box.setTitle("Data Trend")
            self.plot_widget_right.clear_plot("No sensor selected.")
            return

        logger.info(f"Sensor type '{sensor_type}' selected.")
        self.current_selected_sensor_type = sensor_type
        self.settings_manager.set_setting('UI', 'sensor_details_selected_sensor_type', sensor_type)

        self.plot_group_box.setTitle(f"{sensor_type} Data Trend")
        self._populate_gauges_for_sensor(sensor_type)
        self._update_plot_controls_for_sensor(sensor_type)
        self.update_all_plots()

    def _clear_gauges(self):
        """Helper to remove all widgets from the gauges layout."""
        while self.gauges_layout_left.count():
            item = self.gauges_layout_left.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.gauge_widgets.clear()

    def _populate_gauges_for_sensor(self, sensor_type):
        """Dynamically creates and displays gauges for the selected sensor."""
        self._clear_gauges()
        metrics = self.settings_manager.DEFAULT_METRIC_INFO.get(sensor_type, {})
            
        for metric_type, metric_info in metrics.items():
            if self.settings_manager.get_boolean_setting('Sensor_Presence', f"{sensor_type.lower()}_{metric_type.lower()}_present", fallback=False):
                sensor_name = metric_type.capitalize()
                gauge = SensorDisplayWidget(
                    #sensor_name=f"{sensor_type} {metric_type.capitalize()}",
                    sensor_name=sensor_name,
                    sensor_category=sensor_type, 
                    metric_type=metric_type,
                    gauge_type=self.settings_manager.get_gauge_type(sensor_type, metric_type),
                    gauge_style=self.settings_manager.get_gauge_style(sensor_type, metric_type),
                    min_value=metric_info.get('min', 0.0), 
                    max_value=metric_info.get('max', 100.0),
                    settings_manager=self.settings_manager,
                    thresholds=self.settings_manager.get_thresholds().get(sensor_type, {}).get(metric_type, {}),
                    initial_value=0.0, 
                    unit=self.settings_manager.get_unit(sensor_type, metric_type),
                    precision=self.settings_manager.get_precision(sensor_type, metric_type),
                    parent=self.gauges_layout_left.widget(),
                    main_window=self.main_window,
                    is_preview=False
                )
                gauge.setFixedSize(200, 200)

                gauge.alert_triggered.connect(self.alert_triggered)
                gauge.alert_cleared.connect(self.alert_cleared)

                self.gauges_layout_left.addWidget(gauge)

                self.gauge_widgets[metric_type] = gauge

        #self.gauges_layout_left.addStretch(1)
        self.update_sensor_values()

    def _generate_metric_combinations(self, metric_types):
        """Generates all possible combinations of metrics for plotting."""
        all_combinations = {}
        # Generate combinations for every size from 2 up to the total number of metrics
        for r in range(2, len(metric_types) + 1):
            for combo_tuple in itertools_combinations(metric_types, r):
                # Create a display name like "Temperature/Pressure"
                display_name = "/".join([m.capitalize() for m in combo_tuple])
                # The value is the list of actual metric types
                all_combinations[display_name] = list(combo_tuple)
        return all_combinations

    def _update_plot_controls_for_sensor(self, sensor_type):
        """Populates the plot metric selection combo box for the selected sensor."""
        self.plot_metric_type_combo.blockSignals(True)
        self.plot_metric_type_combo.clear()
        self.plot_metric_display_to_actual_map.clear()
        
        all_metrics = self.settings_manager.DEFAULT_METRIC_INFO.get(sensor_type, {})
        enabled_metrics = {m_type: m_info for m_type, m_info in all_metrics.items()
                           if self.settings_manager.get_boolean_setting('Sensor_Presence', f"{sensor_type.lower()}_{m_type.lower()}_present", fallback=False)}

        if not enabled_metrics:
            self.plot_metric_type_combo.addItem("No Metrics Available")
            self.plot_metric_type_combo.setEnabled(False)
        else:
            self.plot_metric_type_combo.setEnabled(True)
            metric_type_list = list(enabled_metrics.keys())

            # Add "Combined" option
            if len(metric_type_list) > 1:
                self.plot_metric_type_combo.addItem("Combined")
                self.plot_metric_display_to_actual_map["Combined"] = metric_type_list

            # Add individual metrics
            for metric_type, metric_info in enabled_metrics.items():
                unit = self.settings_manager.get_unit(sensor_type, metric_type)
                display_name = f"{metric_type.capitalize()} ({unit})" if unit else metric_type.capitalize()
                self.plot_metric_type_combo.addItem(display_name)
                self.plot_metric_display_to_actual_map[display_name] = [metric_type]
            
            # Generate and add all combinations
            if len(metric_type_list) >= 2:
                combinations = self._generate_metric_combinations(metric_type_list)
                for display_name, metric_list in sorted(combinations.items()):
                    self.plot_metric_type_combo.addItem(display_name)
                    self.plot_metric_display_to_actual_map[display_name] = metric_list

            fallback = self.plot_metric_type_combo.itemText(0) if self.plot_metric_type_combo.count() > 0 else ""
            last_selected = self.settings_manager.get_setting(
                'UI', f'sensor_details_plot_metric_{sensor_type.lower()}', fallback=fallback)
            self.plot_metric_type_combo.setCurrentText(last_selected)

        self.plot_metric_type_combo.blockSignals(False)
        self._on_plot_metric_type_changed(self.plot_metric_type_combo.currentText())

    @pyqtSlot(dict)
    def update_sensor_values(self, data_snapshot={}):
        """Updates the values on the visible gauges."""
        latest_data = data_snapshot or self.data_store.get_latest_data()
        if not latest_data or 'sensors' not in latest_data or not self.current_selected_sensor_type:
            return

        sensor_data = latest_data['sensors'].get(self.current_selected_sensor_type, {})
        for metric_type, widget in self.gauge_widgets.items():
            if metric_type in sensor_data:
                widget.update_value(sensor_data[metric_type])

    @pyqtSlot()
    def update_all_plots(self):
        """Fetches data and updates the plot for the current selections."""
        if not self.current_selected_sensor_type or not self.plot_widget_right:
            return

        selected_display_name = self.plot_metric_type_combo.currentText()
        metrics_to_plot = self.plot_metric_display_to_actual_map.get(selected_display_name, [])
        if not metrics_to_plot:
            self.plot_widget_right.clear_plot(f"No enabled metrics for '{selected_display_name}'.")
            return

        time_range = self.plot_time_range_combo.currentText()
        history = self.data_store.get_data_history(time_range=time_range)

        series_to_plot = []
        if not history:
            self.plot_widget_right.clear_plot("No data available for this time range.")
            return

        for metric_type in metrics_to_plot:
            x_data = [dp.get('timestamp') for dp in history]
            y_data = [dp['sensors'].get(self.current_selected_sensor_type, {}).get(metric_type) for dp in history]
            valid_points = [(x, y) for x, y in zip(x_data, y_data) if x is not None and y is not None]
            
            if valid_points:
                x_filtered, y_filtered = zip(*valid_points)
                unit = self.settings_manager.get_unit(self.current_selected_sensor_type, metric_type) or ""
                low_threshold = self.settings_manager.get_threshold(self.current_selected_sensor_type, metric_type, 'warning_low_value')
                high_threshold = self.settings_manager.get_threshold(self.current_selected_sensor_type, metric_type, 'critical_high_value')

                series_to_plot.append({
                    'label': f"{metric_type.capitalize()} ({unit})".strip(),
                    'x_data': list(x_filtered), 'y_data': list(y_filtered),
                    'low_threshold': low_threshold, 'high_threshold': high_threshold
                })

        if not series_to_plot:
            self.plot_widget_right.clear_plot("No valid data points for this selection.")
            return
            
        self.plot_widget_right.plot_series(
             series_to_plot,
             plot_title="", x_label="Time", y_label="Value",
             time_series=True, show_legend=len(series_to_plot) > 1,
             clear_plot=True
        )

    def update_theme_colors(self, theme_colors):
        """Rebuilds the UI to apply new theme colors and styles."""
        self.theme_colors = theme_colors
        if self.plot_widget_right:
            self.plot_widget_right.update_theme_colors(theme_colors)
        
        if self.current_selected_sensor_type:
            self._on_sensor_type_selected(self.current_selected_sensor_type)
        
        self.style().polish(self)

    def set_plot_update_interval(self, interval_ms):
        """Sets the update interval for the plot timer."""
        logger.info(f"Setting plot update interval to {interval_ms} ms.")
        self.plot_update_interval_ms = int(interval_ms)
        if self.plot_update_timer and self.plot_update_timer.isActive():
            self.plot_update_timer.stop()
        self.plot_update_timer.start(self.plot_update_interval_ms)

    @pyqtSlot(str, str, object)
    def _on_settings_updated(self, section, key, value):
        """Handles updates from the settings manager."""
        if section == 'UI' and (key == 'theme' or key.startswith('gauge_')):
            self.update_theme_colors(self.settings_manager.get_theme_colors())
        elif 'Sensor_' in section:
            self.populate_sensor_selection()

    @pyqtSlot(str)
    def _on_plot_time_range_changed(self, time_range):
        """Handles plot time range changes."""
        self.detail_plot_time_range = time_range
        self.settings_manager.set_setting('General', 'detail_plot_time_range', time_range)
        self.update_all_plots()

    @pyqtSlot(str)
    def _on_plot_metric_type_changed(self, metric_display_name):
        """Handles plot metric type changes."""
        self.current_selected_plot_metric_type = metric_display_name
        if self.current_selected_sensor_type:
            self.settings_manager.set_setting(
                'UI', f'sensor_details_plot_metric_{self.current_selected_sensor_type.lower()}', metric_display_name)
        self.update_all_plots()