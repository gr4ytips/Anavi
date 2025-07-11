# widgets/plot_tab_widget.py
# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta
from itertools import combinations as itertools_combinations
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
                             QListWidget, QListWidgetItem, QAbstractItemView, QComboBox,
                             QStackedWidget, QSpinBox, QDateTimeEdit, QFormLayout)
from PyQt5.QtCore import Qt, pyqtSlot, QTimer, QDateTime

from .matplotlib_widget import MatplotlibWidget

logger = logging.getLogger(__name__)


class PlotTabWidget(QWidget):
    """
    A sophisticated tab for selecting multiple sensor metrics and displaying them
    on a single, configurable plot.
    """
    def __init__(self, data_store, settings_manager, theme_colors,
                 initial_hide_matplotlib_toolbar, initial_plot_update_interval_ms,
                 initial_detail_plot_time_range, main_window=None, parent=None):
        super().__init__(parent)
        self.setObjectName("PlotTabWidget")
        
        self.data_store = data_store
        self.settings_manager = settings_manager
        self.theme_colors = theme_colors
        self.hide_matplotlib_toolbar = initial_hide_matplotlib_toolbar
        self.plot_update_interval_ms = initial_plot_update_interval_ms
        self.main_window = main_window

        self.plot_widget = None
        self.sensor_list_widget = None
        self.time_range_mode_combo = None
        self.time_range_stacked_widget = None
        
        self.plot_update_debounce_timer = QTimer(self)
        self.plot_update_debounce_timer.setSingleShot(True)
        self.plot_update_debounce_timer.setInterval(250)

        self.polling_timer = QTimer(self)
        self.polling_timer.timeout.connect(self._request_plot_update)
        
        self.setup_ui()
        self.setup_connections()
        self.populate_initial_view()

        self.polling_timer.start(self.plot_update_interval_ms)

    def setup_ui(self):
        """Sets up the static UI layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        controls_widget = QWidget()
        controls_layout = QHBoxLayout(controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setAlignment(Qt.AlignTop)

        sensor_selection_group = QGroupBox("Select Sensors to Plot")
        sensor_selection_group.setObjectName("SensorSelectionGroup")
        sensor_selection_layout = QVBoxLayout(sensor_selection_group)
        self.sensor_list_widget = QListWidget()
        self.sensor_list_widget.setObjectName("SensorListWidget")
        sensor_selection_layout.addWidget(self.sensor_list_widget)
        controls_layout.addWidget(sensor_selection_group, 1)

        time_range_group = QGroupBox("Time Range Options")
        time_range_group.setObjectName("TimeRangeGroup")
        time_range_layout = QVBoxLayout(time_range_group)
        self.time_range_mode_combo = QComboBox()
        self.time_range_mode_combo.addItems(["Last N minutes", "Last N hours", "Last N days"])
        time_range_layout.addWidget(self.time_range_mode_combo)
        self.time_range_stacked_widget = QStackedWidget()
        time_range_layout.addWidget(self.time_range_stacked_widget)
        last_n_widget = QWidget()
        last_n_layout = QHBoxLayout(last_n_widget)
        self.last_n_spinbox = QSpinBox()
        self.last_n_spinbox.setMinimum(1)
        self.last_n_spinbox.setMaximum(1000)
        self.last_n_spinbox.setValue(30)
        self.last_n_unit_label = QLabel("minutes")
        last_n_layout.addWidget(self.last_n_spinbox)
        last_n_layout.addWidget(self.last_n_unit_label)
        last_n_layout.addStretch(1)
        self.time_range_stacked_widget.addWidget(last_n_widget)
        controls_layout.addWidget(time_range_group, 1)
        main_layout.addWidget(controls_widget)

        self.plot_widget = MatplotlibWidget(
            theme_colors=self.theme_colors,
            settings_manager=self.settings_manager,
            hide_toolbar=self.hide_matplotlib_toolbar
        )
        main_layout.addWidget(self.plot_widget, 1)

    def setup_connections(self):
        """Connects widget signals to their respective slots."""
        self.plot_update_debounce_timer.timeout.connect(self._execute_plot_update)
        
        # CORRECTED: Use a more reliable signal for user interaction
        self.sensor_list_widget.itemClicked.connect(self._on_list_item_clicked)
        
        self.time_range_mode_combo.currentIndexChanged.connect(self._on_time_range_mode_changed)
        self.last_n_spinbox.valueChanged.connect(self._request_plot_update)

    def populate_initial_view(self):
        """Populates the sensor list widget with all available metrics."""
        self.sensor_list_widget.clear()
        all_sensors = self.settings_manager.get_sensor_configurations()
        for sensor_type, metrics in all_sensors.items():
            for metric_type, metric_info in metrics.items():
                display_name = f"{sensor_type} - {metric_type.capitalize()}"
                item = QListWidgetItem(display_name)
                item.setData(Qt.UserRole, (sensor_type, metric_type))
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                self.sensor_list_widget.addItem(item)
        self._request_plot_update()

    @pyqtSlot(QListWidgetItem)
    def _on_list_item_clicked(self, item):
        """Manually toggles the check state and triggers a plot update."""
        if item.checkState() == Qt.Checked:
            item.setCheckState(Qt.Unchecked)
        else:
            item.setCheckState(Qt.Checked)
        self._request_plot_update()

    def update_plot(self):
        self._request_plot_update()

    @pyqtSlot()
    def _request_plot_update(self):
        self.plot_update_debounce_timer.start()

    @pyqtSlot(int)
    def _on_time_range_mode_changed(self, index):
        mode = self.time_range_mode_combo.itemText(index)
        unit_text = mode.split()[-1]
        self.last_n_unit_label.setText(unit_text)
        self._request_plot_update()

    def _get_selected_metrics(self):
        selected_metrics = []
        for i in range(self.sensor_list_widget.count()):
            item = self.sensor_list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected_metrics.append(item.data(Qt.UserRole))
        return selected_metrics

    def _get_current_time_range_string(self):
        mode = self.time_range_mode_combo.currentText()
        value = self.last_n_spinbox.value()
        unit = self.last_n_unit_label.text()
        return f"Last {value} {unit}"
        
    def _prepare_series_from_history(self, history, metrics):
        series_to_plot = []
        for sensor_type, metric_type in metrics:
            x_data = [dp.get('timestamp') for dp in history]
            y_data = [dp['sensors'].get(sensor_type, {}).get(metric_type) for dp in history]
            
            valid_points = [(x, y) for x, y in zip(x_data, y_data) if x is not None and y is not None]
            if not valid_points: continue

            x_filtered, y_filtered = zip(*valid_points)
            unit = self.settings_manager.get_unit(sensor_type, metric_type) or ""
            low_threshold = self.settings_manager.get_threshold(sensor_type, metric_type, 'warning_low_value')
            high_threshold = self.settings_manager.get_threshold(sensor_type, metric_type, 'critical_high_value')

            series_to_plot.append({
                'label': f"{sensor_type} {metric_type.capitalize()} ({unit})".strip(),
                'x_data': list(x_filtered), 'y_data': list(y_filtered),
                'low_threshold': low_threshold, 'high_threshold': high_threshold
            })
        return series_to_plot

    @pyqtSlot()
    def _execute_plot_update(self):
        selected_metrics = self._get_selected_metrics()
        if not selected_metrics:
            self.plot_widget.clear_plot("No sensors selected.")
            return

        time_range_str = self._get_current_time_range_string()
        if not time_range_str:
            self.plot_widget.clear_plot("Time range mode not supported.")
            return
        
        history = self.data_store.get_data_history(time_range=time_range_str)
        if not history:
            self.plot_widget.clear_plot("No data available for this time range.")
            return
            
        series_to_plot = self._prepare_series_from_history(history, selected_metrics)
        if not series_to_plot:
            self.plot_widget.clear_plot("No valid data points for this selection.")
            return

        self.plot_widget.plot_series(
            series_to_plot, plot_title="Sensor Data",
            x_label="Time", y_label="Value",
            time_series=True, show_legend=True, clear_plot=True
        )
        self.plot_widget.update()
        QApplication.processEvents()

    def update_theme_colors(self, new_theme_colors):
        self.theme_colors = new_theme_colors
        if self.plot_widget:
            self.plot_widget.update_theme_colors(new_theme_colors)

    def set_plot_update_interval(self, interval_ms):
        self.plot_update_interval_ms = int(interval_ms)
        if self.polling_timer.isActive():
            self.polling_timer.stop()
        self.polling_timer.start(self.plot_update_interval_ms)