# widgets/dashboard_tab.py
# -*- coding: utf-8 -*-
import logging
import math
import collections
from datetime import datetime
from itertools import combinations as itertools_combinations

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QProgressBar, QSizePolicy, QSpacerItem, QScrollArea, QComboBox, QFormLayout
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QRect, QPoint, QRectF, QPointF, QSize

from data_management.settings import SettingsManager
from widgets.sensor_display import SensorDisplayWidget
from widgets.matplotlib_widget import MatplotlibWidget

logger = logging.getLogger(__name__)


class DashboardTab(QWidget):
    """
    Dashboard tab displaying an overview of all active sensor metrics
    with dynamic gauges and a live plot.
    """
    alert_triggered = pyqtSignal(str, str, str, str)
    alert_cleared = pyqtSignal(str, str)

    ui_customization_changed = pyqtSignal(str, str)
    theme_changed = pyqtSignal(str)

    def __init__(self, data_store, settings_manager,
                 initial_dashboard_plot_time_range, initial_hide_matplotlib_toolbar, initial_plot_update_interval_ms,
                 initial_gauge_type, initial_gauge_style,
                 main_window=None,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("DashboardTab")

        self.data_store = data_store
        self.settings_manager = settings_manager
        self.theme_colors = self.settings_manager.get_theme_colors()
        self.thresholds = self.settings_manager.get_thresholds()
        self.main_window = main_window

        self.sensor_widgets = {}

        self.dashboard_plot_time_range = initial_dashboard_plot_time_range
        self.hide_matplotlib_toolbar = initial_hide_matplotlib_toolbar
        self.plot_update_interval_ms = initial_plot_update_interval_ms
        self.gauge_type = initial_gauge_type
        self.gauge_style = initial_gauge_style

        self.dashboard_plot_time_range_combo = None
        # MODIFIED: Add sensor combo box and related variables
        self.dashboard_plot_sensor_combo = None
        self.dashboard_plot_metric_type_combo = None
        self.current_selected_dashboard_plot_sensor = "All Sensors" # Default value
        self.current_selected_dashboard_plot_metric_type = None
        self.dashboard_plot_metric_display_to_actual_map = {}

        self._setup_ui()

        self.plot_update_timer = QTimer(self)
        self.plot_update_timer.timeout.connect(self._on_plot_timer_timeout)
        self.plot_update_timer.start(self.plot_update_interval_ms)

        self._setup_connections()

        logger.info("DashboardTab initialized.")

    def _setup_ui(self):
        """
        Sets up the layout and initial widgets for the Dashboard tab.
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)
        main_layout.setAlignment(Qt.AlignTop)

        self.content_widget = QGroupBox("Current Sensor Readings")
        self.content_layout = QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(10, 20, 10, 10)
        self.content_layout.setSpacing(15)
        self.content_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        main_layout.addWidget(self.content_widget)

        plot_group_box = QGroupBox("Live Sensor Data Plot")
        plot_group_box.setObjectName("PlotGroupBox")
        plot_layout = QVBoxLayout(plot_group_box)

        plot_options_row_layout = QHBoxLayout()
        plot_options_row_layout.setAlignment(Qt.AlignLeft)
        plot_options_row_layout.setSpacing(10)

        plot_options_row_layout.addWidget(QLabel("Time Range:"))
        self.dashboard_plot_time_range_combo = QComboBox()
        self.dashboard_plot_time_range_combo.setObjectName("DashboardPlotTimeRangeCombo")
        self.dashboard_plot_time_range_combo.addItems(self.data_store.get_available_time_ranges())
        self.dashboard_plot_time_range_combo.setCurrentText(self.dashboard_plot_time_range)
        plot_options_row_layout.addWidget(self.dashboard_plot_time_range_combo)

        # MODIFIED: Add Sensor selection QComboBox
        plot_options_row_layout.addWidget(QLabel("Sensor:"))
        self.dashboard_plot_sensor_combo = QComboBox()
        self.dashboard_plot_sensor_combo.setObjectName("DashboardPlotSensorCombo")
        plot_options_row_layout.addWidget(self.dashboard_plot_sensor_combo)

        plot_options_row_layout.addWidget(QLabel("Metric:"))
        self.dashboard_plot_metric_type_combo = QComboBox()
        self.dashboard_plot_metric_type_combo.setObjectName("DashboardPlotMetricTypeCombo")
        plot_options_row_layout.addWidget(self.dashboard_plot_metric_type_combo)

        plot_options_row_layout.addStretch(1)

        plot_layout.addLayout(plot_options_row_layout)

        self.plot_widget = MatplotlibWidget(
            self.theme_colors,
            self.settings_manager,
            hide_toolbar=self.hide_matplotlib_toolbar
        )
        self.plot_widget.setObjectName("DashboardPlotWidget")
        plot_layout.addWidget(self.plot_widget)

        main_layout.addWidget(plot_group_box)

        self.populate_sensor_display_widgets()
        self.update_all_sensor_values()

    def _setup_connections(self):
        self.settings_manager.settings_updated.connect(self._on_settings_updated)
        self.data_store.data_updated.connect(self.update_sensor_values)
        self.dashboard_plot_time_range_combo.currentTextChanged.connect(self._on_plot_time_range_changed)
        # MODIFIED: Connect the new sensor combo box
        self.dashboard_plot_sensor_combo.currentTextChanged.connect(self._on_plot_sensor_changed)
        self.dashboard_plot_metric_type_combo.currentTextChanged.connect(self._on_dashboard_plot_metric_type_changed)


    def populate_sensor_display_widgets(self):
        logger.info("DashboardTab: Populating sensor display widgets.")
        
        # Correctly clear the layout to prevent segmentation faults
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        self.sensor_widgets.clear()

        enabled_sensor_configs = self.settings_manager.get_sensor_configurations()

        if not enabled_sensor_configs:
            no_sensors_label = QLabel("No sensors enabled in settings to show details.")
            no_sensors_label.setAlignment(Qt.AlignCenter)
            self.content_layout.addWidget(no_sensors_label)
        else:
            for sensor_type, metrics in enabled_sensor_configs.items():
                for metric_type, metric_info in metrics.items():
                    sensor_name = f"{sensor_type} {metric_type.capitalize()}"

                    gauge = SensorDisplayWidget(
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
                        parent=self.content_widget,
                        main_window=self.main_window,
                        is_preview=False
                    )
              
                    gauge.setObjectName(f"SensorDisplayWidget_{SettingsManager._format_name_for_qss(sensor_type)}_{SettingsManager._format_name_for_qss(metric_type)}")
                    gauge.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

                    gauge.alert_triggered.connect(self.alert_triggered)
                    gauge.alert_cleared.connect(self.alert_cleared)

                    self.sensor_widgets[f"{sensor_type}_{metric_type}"] = gauge
                    
                    self.content_layout.addWidget(gauge)
                    logger.debug(f"DashboardTab: Added gauge for {sensor_name}.")
            
        self._update_plot_combos()

    def _update_plot_combos(self):
        """Populates the sensor and metric combo boxes for the plot."""
        logger.debug("Updating plot combo boxes.")
        self.dashboard_plot_sensor_combo.blockSignals(True)
        self.dashboard_plot_sensor_combo.clear()

        enabled_sensor_configs = self.settings_manager.get_sensor_configurations()

        if not enabled_sensor_configs:
            self.dashboard_plot_sensor_combo.addItem("No Sensors Available")
            self.dashboard_plot_sensor_combo.setEnabled(False)
            self.dashboard_plot_metric_type_combo.clear()
            self.dashboard_plot_metric_type_combo.addItem("No Metrics Available")
            self.dashboard_plot_metric_type_combo.setEnabled(False)
            self.plot_widget.clear_plot("No enabled sensors to plot.")
        else:
            self.dashboard_plot_sensor_combo.setEnabled(True)
            self.dashboard_plot_sensor_combo.addItem("All Sensors")
            sensor_names = sorted(enabled_sensor_configs.keys())
            self.dashboard_plot_sensor_combo.addItems(sensor_names)

            # Restore previous selection
            last_selected_sensor = self.settings_manager.get_setting('UI', 'dashboard_plot_selected_sensor', fallback="All Sensors")
            index = self.dashboard_plot_sensor_combo.findText(last_selected_sensor)
            if index != -1:
                self.dashboard_plot_sensor_combo.setCurrentIndex(index)
            self.current_selected_dashboard_plot_sensor = self.dashboard_plot_sensor_combo.currentText()

        self.dashboard_plot_sensor_combo.blockSignals(False)

        # Update metric combo based on the (newly updated) sensor combo
        self._update_metric_combo()

    def _update_metric_combo(self):
        """Populates the metric combo box based on the selected sensor."""
        logger.debug(f"Updating metric combo for sensor: '{self.current_selected_dashboard_plot_sensor}'")
        self.dashboard_plot_metric_type_combo.blockSignals(True)
        self.dashboard_plot_metric_type_combo.clear()
        self.dashboard_plot_metric_display_to_actual_map.clear()

        enabled_sensor_configs = self.settings_manager.get_sensor_configurations()
        selected_sensor = self.current_selected_dashboard_plot_sensor

        metrics_to_consider = []
        if selected_sensor == "All Sensors":
            for s_type, metrics in enabled_sensor_configs.items():
                for m_type in metrics.keys():
                    unit = self.settings_manager.get_unit(s_type, m_type)
                    display_name = f"{s_type} {m_type.capitalize()} ({unit})" if unit else f"{s_type} {m_type.capitalize()}"
                    metrics_to_consider.append((display_name, m_type, s_type))
        elif selected_sensor in enabled_sensor_configs:
            for m_type in enabled_sensor_configs[selected_sensor].keys():
                unit = self.settings_manager.get_unit(selected_sensor, m_type)
                display_name = f"{selected_sensor} {m_type.capitalize()} ({unit})" if unit else f"{selected_sensor} {m_type.capitalize()}"
                metrics_to_consider.append((display_name, m_type, selected_sensor))

        metrics_to_consider.sort(key=lambda x: x[0])

        if not metrics_to_consider:
            self.dashboard_plot_metric_type_combo.addItem("No Metrics Available")
            self.dashboard_plot_metric_type_combo.setEnabled(False)
            self.plot_widget.clear_plot("No metrics for this sensor.")
            self.dashboard_plot_metric_type_combo.blockSignals(False)
            return

        # Add "Combined" option for all available metrics in the current view
        if len(metrics_to_consider) > 1:
            self.dashboard_plot_metric_type_combo.addItem("Combined")
            self.dashboard_plot_metric_display_to_actual_map["Combined"] = [(item[2], item[1]) for item in metrics_to_consider]

        # Generate and add combinations
        combinations = self._generate_metric_combinations_dashboard(metrics_to_consider, selected_sensor)
        for combo_display_name, combo_metric_pairs in sorted(combinations.items()):
            self.dashboard_plot_metric_type_combo.addItem(combo_display_name)
            self.dashboard_plot_metric_display_to_actual_map[combo_display_name] = combo_metric_pairs

        # Add individual metrics
        for display_name, actual_metric_type, actual_sensor_type in metrics_to_consider:
            self.dashboard_plot_metric_type_combo.addItem(display_name)
            self.dashboard_plot_metric_display_to_actual_map[display_name] = [(actual_sensor_type, actual_metric_type)]

        self.dashboard_plot_metric_type_combo.setEnabled(True)
        # Restore previous selection
        initial_plot_metric_display_name = self.settings_manager.get_setting('UI', 'dashboard_plot_selected_metric', fallback=self.dashboard_plot_metric_type_combo.itemText(0))
        index = self.dashboard_plot_metric_type_combo.findText(initial_plot_metric_display_name)
        if index != -1:
            self.dashboard_plot_metric_type_combo.setCurrentIndex(index)
        elif self.dashboard_plot_metric_type_combo.count() > 0:
            self.dashboard_plot_metric_type_combo.setCurrentIndex(0)

        self.current_selected_dashboard_plot_metric_type = self.dashboard_plot_metric_type_combo.currentText()
        self.dashboard_plot_metric_type_combo.blockSignals(False)
        self._on_plot_timer_timeout() # Trigger a plot update with new metric options

    def _generate_metric_combinations_dashboard(self, enabled_metrics_for_combo, selected_sensor):
        """
        Generates display names and actual (sensor_type, metric_type) pairs for combinations.
        If a specific sensor is selected, it combines its metrics regardless of unit.
        If "All Sensors" is selected, it combines metrics that share the same unit.
        """
        combinations = collections.OrderedDict()

        if selected_sensor != "All Sensors":
            # Combine all metrics for a single sensor, regardless of unit
            if len(enabled_metrics_for_combo) >= 2:
                for r in range(2, len(enabled_metrics_for_combo) + 1):
                    for combo_items in itertools_combinations(enabled_metrics_for_combo, r):
                        combo_display_names_parts = [f"{item[2]} {item[1].capitalize()}" for item in combo_items]
                        combo_actual_pairs = [(item[2], item[1]) for item in combo_items]

                        final_display_name = "/".join(combo_display_names_parts)
                        combinations[final_display_name] = combo_actual_pairs
        else: # "All Sensors" selected, group by unit for sensible plotting
            metrics_by_unit = collections.defaultdict(list)
            for display_name, m_type, s_type in enabled_metrics_for_combo:
                unit = self.settings_manager.get_unit(s_type, m_type)
                metrics_by_unit[unit].append((display_name, m_type, s_type))

            for unit, metrics_in_unit in metrics_by_unit.items():
                if len(metrics_in_unit) >= 2:
                    for r in range(2, len(metrics_in_unit) + 1):
                        for combo_items in itertools_combinations(metrics_in_unit, r):
                            combo_display_names_parts = [f"{item[2]} {item[1].capitalize()}" for item in combo_items]
                            combo_actual_pairs = [(item[2], item[1]) for item in combo_items]

                            display_name_base = "/".join(combo_display_names_parts)
                            final_display_name = f"{display_name_base} ({unit})" if unit else display_name_base
                            combinations[final_display_name] = combo_actual_pairs

        return combinations

    @pyqtSlot(str, str, object)
    def _on_settings_updated(self, section, key, value):
        """Responds to changes in application settings."""
        logger.debug(f"DashboardTab._on_settings_updated: Settings updated - Section: {section}, Key: '{key}', Value: {value}.")

        if 'Sensor_' in section:
            logger.debug(f"DashboardTab: Sensor config changed ({key}:{value}), re-populating UI.")
            self.populate_sensor_display_widgets() # This will now update gauges and plot combos
            self.update_all_sensor_values()
        elif section == 'General' and key == 'dashboard_plot_time_range':
            self.dashboard_plot_time_range = value
            self.dashboard_plot_time_range_combo.setCurrentText(value)
        elif section == 'General' and key == 'plot_update_interval_ms':
            # MODIFIED: Call the new method to handle interval changes
            self.set_plot_update_interval(int(value))
        elif section == 'UI' and (key == 'hide_matplotlib_toolbar' or key.startswith('gauge_')):
            self.hide_matplotlib_toolbar = self.settings_manager.get_boolean_setting('UI', 'hide_matplotlib_toolbar', fallback=False)
            self.plot_widget.set_toolbar_visibility(self.hide_matplotlib_toolbar)
            self.populate_sensor_display_widgets() # Re-populate to update gauge styles
        elif section == 'UI' and key == 'theme':
            logger.debug(f"{self.objectName()}: Theme changed, updating colors.")
            new_theme_colors = self.settings_manager.get_theme_colors()
            self.update_theme_colors(new_theme_colors)

    @pyqtSlot(dict)
    def update_sensor_values(self, data_snapshot):
        """Updates the values displayed on all active sensor gauges."""
        if not data_snapshot or 'sensors' not in data_snapshot: return

        for sensor_type_from_source, metrics_data in data_snapshot['sensors'].items():
            for metric_type_from_source, new_value in metrics_data.items():
                widget_key = f"{sensor_type_from_source}_{metric_type_from_source}"

                if widget_key in self.sensor_widgets:
                    self.sensor_widgets[widget_key].update_value(new_value)

    def update_all_sensor_values(self):
        """Requests the latest data snapshot to update all gauges."""
        latest_snapshot = self.data_store.get_latest_data()
        if latest_snapshot:
            self.update_sensor_values(latest_snapshot)

    # ADDED: New method to set plot update interval
    def set_plot_update_interval(self, interval_ms):
        """Sets the update interval for the internal QTimer that triggers plot updates."""
        logger.debug(f"DashboardTab.set_plot_update_interval: Setting plot update interval to {interval_ms} ms.")
        self.plot_update_interval_ms = interval_ms
        if self.plot_update_timer.isActive():
            self.plot_update_timer.stop()
        self.plot_update_timer.start(self.plot_update_interval_ms)
        logger.info(f"Plot update timer interval set to {self.plot_update_interval_ms} ms.")

    @pyqtSlot(str)
    def _on_plot_time_range_changed(self, time_range):
        """Handles plot time range changes from the UI."""
        if not time_range: return
        self.dashboard_plot_time_range = time_range
        self.settings_manager.set_setting('General', 'dashboard_plot_time_range', time_range)
        self._on_plot_timer_timeout()

    # MODIFIED: Add handler for the new sensor combo box
    @pyqtSlot(str)
    def _on_plot_sensor_changed(self, sensor_name):
        """Handles plot sensor changes from the UI."""
        if not sensor_name: return
        logger.info(f"DashboardTab: Plot sensor set to '{sensor_name}'.")
        self.current_selected_dashboard_plot_sensor = sensor_name
        self.settings_manager.set_setting('UI', 'dashboard_plot_selected_sensor', sensor_name)
        self._update_metric_combo() # This will update metrics and trigger a plot update

    @pyqtSlot(str)
    def _on_dashboard_plot_metric_type_changed(self, metric_display_name):
        """Handles plot metric type changes from the UI (Dashboard tab)."""
        if not metric_display_name: return
        logger.info(f"DashboardTab._on_dashboard_plot_metric_type_changed: Plot metric type set to '{metric_display_name}'.")
        self.current_selected_dashboard_plot_metric_type = metric_display_name
        self.settings_manager.set_setting('UI', 'dashboard_plot_selected_metric', metric_display_name)
        self._on_plot_timer_timeout()

    @pyqtSlot()
    def _on_plot_timer_timeout(self):
        """
        Fetches data and updates the plot based on the current time range and selected metric(s).
        This method is called by the QTimer.
        """
        logger.debug(f"DashboardTab._on_plot_timer_timeout: Updating plot via timer.")
        # Check for valid selections before proceeding
        if not self.current_selected_dashboard_plot_metric_type or "No Metrics" in self.current_selected_dashboard_plot_metric_type:
             self.plot_widget.clear_plot("No metric selected to plot.")
             return

        current_time_range = self.dashboard_plot_time_range_combo.currentText()
        history = self.data_store.get_data_history(time_range=current_time_range)
        logger.debug(f"  Full history fetched for dashboard plot. Number of data points: {len(history)}.")

        if not history:
            self.plot_widget.clear_plot("No data to plot for this time range.")
            return

        series_to_plot = []
        all_y_data_collected = []

        x_data_template = []
        for dp in history:
            ts = dp.get('timestamp')
            if isinstance(ts, datetime):
                x_data_template.append(ts)
            elif isinstance(ts, str):
                try:
                    # Assuming format is like '2024-01-15T10:30:00.123Z' or similar ISO format
                    dt_obj = datetime.fromisoformat(ts.replace('Z', '+00:00')) if 'Z' in ts else datetime.fromisoformat(ts)
                    x_data_template.append(dt_obj)
                except (ValueError, TypeError):
                    try: # Fallback for time-only strings like HH:MM:SS
                       dt_obj = datetime.strptime(ts, "%H:%M:%S")
                       x_data_template.append(dt_obj)
                    except (ValueError, TypeError):
                       logger.warning(f"      Could not parse timestamp '{ts}'. Skipping this data point for X-axis.")
                       x_data_template.append(None)
            else:
                x_data_template.append(None)

        metrics_to_plot_pairs = []
        selected_display_name = self.current_selected_dashboard_plot_metric_type

        if selected_display_name in self.dashboard_plot_metric_display_to_actual_map:
            metrics_to_plot_pairs = self.dashboard_plot_metric_display_to_actual_map[selected_display_name]
        else:
            logger.warning(f"Invalid dashboard plot metric selection: '{selected_display_name}'. Clearing plot.")
            self.plot_widget.clear_plot("Invalid metric selection.")
            return

        plot_title_base = "Live Sensor Readings Over Time"
        show_legend_for_plot = True

        if len(metrics_to_plot_pairs) == 1:
            s_type, m_type = metrics_to_plot_pairs[0]
            plot_title_base = f"{s_type} {m_type.capitalize()} Trend"
            show_legend_for_plot = False
        else:
            plot_title_base = f"Live Sensor Data: {selected_display_name}"
            show_legend_for_plot = True

        has_any_valid_data = False

        for s_type, m_type in metrics_to_plot_pairs:
            is_metric_enabled = self.settings_manager.get_boolean_setting('Sensor_Presence', f"{s_type.lower()}_{m_type.lower()}_present", fallback=False)
            if not is_metric_enabled:
                logger.debug(f"    Metric '{s_type}/{m_type}' is disabled. Skipping plot series.")
                continue

            y_data = [dp['sensors'].get(s_type, {}).get(m_type) for dp in history]

            valid_data_points = [(x, y) for x, y in zip(x_data_template, y_data) if x is not None and y is not None]

            if not valid_data_points:
                logger.debug(f"    No valid data points for '{s_type}/{m_type}'. Skipping series.")
                continue

            x_data_filtered = [dp[0] for dp in valid_data_points]
            y_data_filtered = [dp[1] for dp in valid_data_points]
            all_y_data_collected.extend(y_data_filtered)

            unit = self.settings_manager.get_unit(s_type, m_type) or ""

            low_threshold_value = self.settings_manager.get_threshold(s_type, m_type, 'warning_low_value')
            high_threshold_value = self.settings_manager.get_threshold(s_type, m_type, 'critical_high_value')

            series_to_plot.append({
                'label': f"{s_type} {m_type.capitalize()} ({unit})",
                'x_data': x_data_filtered,
                'y_data': y_data_filtered,
                'low_threshold': low_threshold_value,
                'high_threshold': high_threshold_value
            })
            has_any_valid_data = True

        if not has_any_valid_data:
            self.plot_widget.clear_plot("No enabled sensor data to plot for this time range.")
            return

        y_label_text = "Value"
        # Determine appropriate Y-axis label
        all_units = {self.settings_manager.get_unit(s, m) for s, m in metrics_to_plot_pairs}
        all_units.discard(None) # Remove None if present
        all_units.discard('') # Remove empty string if present

        if len(all_units) == 1:
            y_label_text = f"Value ({list(all_units)[0]})"
        # If units are mixed, the generic "Value" is best.

        if all_y_data_collected:
            data_y_min = min(all_y_data_collected)
            data_y_max = max(all_y_data_collected)

            if data_y_min == data_y_max:
                if data_y_max == 0.0:
                    y_min_plot, y_max_plot = -0.5, 0.5
                else:
                    y_min_plot, y_max_plot = data_y_max * 0.9, data_y_max * 1.1
            else:
                y_buffer = (data_y_max - data_y_min) * 0.1
                y_min_plot = data_y_min - y_buffer
                y_max_plot = data_y_max + y_buffer

            if hasattr(self.plot_widget, 'set_ylim'):
                self.plot_widget.set_ylim(y_min_plot, y_max_plot)
            else:
                logger.warning("DashboardTab: plot_widget has no 'set_ylim' method. Cannot force Y-axis range.")

        self.plot_widget.plot_series(
            series_to_plot,
            plot_title=plot_title_base,
            x_label="Time",
            y_label=y_label_text,
            time_series=True,
            show_legend=show_legend_for_plot,
            draw_now=True,
            clear_plot=True
        )
        logger.info("DashboardTab: Plot updated successfully.")

    #@pyqtSlot(dict)
    #def update_theme_colors(self, new_theme_colors):
    #    """
    #    Updates the theme colors for this tab and its child widgets.
    #    """
    #    logger.info(f"{self.objectName()}: update_theme_colors called.")

    #    self.theme_colors = dict(new_theme_colors) if new_theme_colors is not None else {}

    #    if not self.theme_colors:
    #        logger.warning(f"{self.objectName()} received empty theme colors.")

    #    self.populate_sensor_display_widgets()

    #    if hasattr(self, 'plot_widget'):
    #        self.plot_widget.update_theme_colors(self.theme_colors)
    #        #self.plot_widget.style.polish(self.plot_widget)
        #self.style().polish(self)            

    @pyqtSlot(dict)
    def update_theme_colors(self, new_theme_colors):
        """
        Updates the theme colors for this tab and its child widgets.
        """
        logger.info(f"{self.objectName()}: update_theme_colors called.")

        # Use the new theme colors if they are provided, otherwise initialize an empty dict
        self.theme_colors = dict(new_theme_colors) if new_theme_colors is not None else {}

        # ---- FIX ----
        # If the theme_colors dictionary is empty, it means the update was triggered
        # without the necessary data, so we fetch it directly from the SettingsManager.
        if not self.theme_colors:
            logger.warning(f"{self.objectName()} received empty theme colors. Fetching from SettingsManager.")
            self.theme_colors = self.settings_manager.get_theme_colors() # <-- This is the key line

        # Now, proceed with the updated theme_colors
        self.populate_sensor_display_widgets()

        if hasattr(self, 'plot_widget'):
            self.plot_widget.update_theme_colors(self.theme_colors)        