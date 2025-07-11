# widgets/sensor_display.py
# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication, QProgressBar, QGroupBox, QSizePolicy
from PyQt5.QtCore import Qt, QSize, QRect, QPoint, QRectF, QPointF, pyqtSignal, pyqtSlot, QPropertyAnimation, QEasingCurve, QTimer, pyqtProperty, QUrl
from PyQt5.QtGui import QPainter, QBrush, QColor, QFont, QPen, QTransform, QConicalGradient, QFontDatabase, QPainterPath, QFontMetrics, QLinearGradient, QRadialGradient
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
import logging
import math
import re
import os

# Import your existing SettingsManager
from data_management.settings import SettingsManager 

# --- Import individual gauge drawer classes ---
from .gauges.base_gauge_drawer import BaseGaugeDrawer
from .gauges.standard_gauge_drawer import StandardGaugeDrawer
from .gauges.semi_circle_gauge_drawer import SemiCircleGaugeDrawer
from .gauges.linear_gauge_drawer import LinearGaugeDrawer
from .gauges.analog_gauge_drawers import (
    AnalogGaugeDrawer, AnalogBasicGaugeDrawer, AnalogClassicBasicGaugeDrawer, 
    AnalogClassicFullGaugeDrawer, AnalogFullGaugeDrawer, AnalogModernBasicGaugeDrawer, 
    AnalogModernFullGaugeDrawer
)
from .gauges.digital_gauge_drawers import DigitalClassicGaugeDrawer, DigitalSegmentedGaugeDrawer
from .gauges.compact_gauge_drawer import CompactGaugeDrawer
from .gauges.custom_progress_bar_drawer import CustomProgressBarDrawer

logger = logging.getLogger(__name__)

class SensorDisplayWidget(QGroupBox):
    """
    A custom QGroupBox widget designed to display a single sensor metric
    with a customizable gauge type (standard, compact, digital, analog, progress bar)
    and style, including threshold-based color changes and alerts.
    """
    GAUGE_TYPES = [
        'Analog', 
        'Analog - Basic', 
        'Analog - Basic Classic', 
        'Analog - Full', 
        'Analog - Full Classic', 
        'Analog - Modern Basic', 
        'Analog - Modern Full', 
        'Compact', 
        'Digital - Classic', 
        'Digital - Segmented', 
        'Linear', 
        'Linear - Basic', 
        'Progress Bar - Horizontal', 
        'Progress Bar - Vertical', 
        'Progress Bar - Custom Horizontal',
        'Progress Bar - Custom Vertical',  
        'Semi-Circle', 
        'Semi-Circle - Modern', 
        'Standard', 
        'Standard - Modern'
        ]
    GAUGE_STYLES = [
        'Bold',
        'Bright',
        'Clean',
        'Deep Shadow',
        'Flat',
        'Fresh',
        'Full',
        'Gradient Fill',
        'Heavy Border',
        'Inset',
        'Minimal',
        'Outline',
        'Raised',
        'Subtle',
        'Vintage'
        ]

    alert_triggered = pyqtSignal(str, str, str, str)
    alert_cleared = pyqtSignal(str, str)
    alert_state_changed = pyqtSignal(str, str, str) 

    # Mapping gauge types to their drawing classes
    GAUGE_DRAWERS = {
        'Analog': AnalogGaugeDrawer,
        'Analog - Basic': AnalogBasicGaugeDrawer,
        'Analog - Basic Classic': AnalogClassicBasicGaugeDrawer,
        'Analog - Full': AnalogFullGaugeDrawer,
        'Analog - Full Classic': AnalogClassicFullGaugeDrawer,
        'Analog - Modern Basic': AnalogModernBasicGaugeDrawer,
        'Analog - Modern Full': AnalogModernFullGaugeDrawer,
        'Compact': CompactGaugeDrawer,
        'Digital - Classic': DigitalClassicGaugeDrawer,
        'Digital - Segmented': DigitalSegmentedGaugeDrawer,
        'Linear': LinearGaugeDrawer,
        'Linear - Basic': LinearGaugeDrawer, 
        'Semi-Circle': SemiCircleGaugeDrawer,
        'Semi-Circle - Modern': SemiCircleGaugeDrawer, 
        'Standard': StandardGaugeDrawer,
        'Standard - Modern': StandardGaugeDrawer, 
        'Progress Bar - Custom Horizontal': CustomProgressBarDrawer,
        'Progress Bar - Custom Vertical': CustomProgressBarDrawer,     
    }

    def __init__(self, sensor_name, sensor_category, metric_type,
                 gauge_type="Standard", gauge_style="Full",
                 min_value=0.0, max_value=100.0,
                 settings_manager=None, 
                 thresholds=None,
                 initial_value=0.0, unit="", precision=1, parent=None,
                 main_window=None,
                 is_preview=False):
        
        super().__init__(sensor_name, parent=parent)
        self.setMouseTracking(True)
        self.setObjectName(SettingsManager._format_name_for_qss(f"{sensor_category}_{metric_type}Display"))
        logger.debug(f"SensorDisplayWidget: Initializing {self.objectName()}. Title: {sensor_name}, Type: {gauge_type}")
        
        self.sensor_name = sensor_name
        self.sensor_category = sensor_category
        self.metric_type = metric_type
        self.unit = unit
        self.main_window = main_window
        self.is_preview = is_preview
        self.settings_manager = settings_manager 

        self._gauge_type = gauge_type
        self._gauge_style = gauge_style
        self._current_value = initial_value 
        self._current_value_animated = initial_value 
        self._precision = precision
        self._alert_state = "normal" 
        self._na_state = False 

        self.theme_colors = {} 
        
        self.thresholds = dict(thresholds) if thresholds is not None else {'low_threshold': None, 'high_threshold': None} 
        logger.debug(f"SensorDisplayWidget '{self.objectName()}' initialized with thresholds: {self.thresholds}")
        
        self._min_value = min_value 
        self._max_value = max_value

        # --- Instantiate the gauge drawer based on type ---
        self.gauge_drawer = None 
        if self._gauge_type in self.GAUGE_DRAWERS:
            self._set_gauge_drawer(gauge_type)


        # --- UI Element Initialization ---
        self.value_label = QLabel(self)
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setObjectName("GaugeValueLabel")
        self.value_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self.progressBar = QProgressBar(self)
        self.progressBar.setTextVisible(False) 
        self.progressBar.setAlignment(Qt.AlignCenter)
        self.progressBar.hide() 

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 20, 5, 5) 
        self.main_layout.addWidget(self.value_label)
        self.main_layout.addWidget(self.progressBar)
        self.main_layout.addStretch(1)

        # --- Animation and Sound Initialization ---
        self.animation = QPropertyAnimation(self, b"current_value_animated")
        self.animation.setDuration(150) 
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

        self.alert_sound_player = QMediaPlayer()
        self.alert_sound_timer = QTimer(self)
        self.alert_sound_timer.setInterval(1000) 
        self.alert_sound_timer.timeout.connect(self._play_alert_sound)
        
        if self.main_window and hasattr(self.main_window, 'settings_manager'):
            # Corrected: Removed 'fallback' keyword argument from get_setting()
            alert_sound_file = self.main_window.settings_manager.get_setting('General', 'alert_sound_file', 'alert.wav')
            self._alert_sound_path = self.main_window.settings_manager.get_resource_path(
                alert_sound_file,
                resource_type="sounds"
            )
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self._alert_sound_path = os.path.normpath(os.path.join(base_dir, '..', 'resources', 'sounds', 'alert.wav'))
        logger.debug(f"SensorDisplayWidget: Alert sound path resolved to: {self._alert_sound_path}")

        # --- Final Setup Calls (order matters!) ---
        self._set_value_range() 
        
        if self.settings_manager: 
            self.update_theme_colors(self.settings_manager.get_theme_colors())
        else:
            logger.warning("SensorDisplayWidget: SettingsManager not available for initial theme. Using hardcoded defaults.")
            self.update_theme_colors({}) 

        self._update_ui_visibility() 
        
        self.update_value(initial_value) 
        
        logger.info(f"SensorDisplayWidget for {sensor_name} initialized (Type: {gauge_type}, Style: {gauge_style}).")

    def _set_gauge_drawer(self, gauge_type):
        """Sets the appropriate gauge drawing instance based on the type."""
        drawer_class = self.GAUGE_DRAWERS.get(gauge_type)
        if drawer_class:
            self.gauge_drawer = drawer_class(self)
            logger.debug(f"SensorDisplayWidget: Set gauge drawer to {drawer_class.__name__} for type '{gauge_type}'.")
        else:
            self.gauge_drawer = None 

    def _get_themed_color(self, key, default_value=None):
        color_val = self.theme_colors.get(key)
        if color_val is None:
            logger.warning(f"SensorDisplayWidget: _get_themed_color: Key '{key}' not found in theme_colors. Using default_value: '{default_value}'.")
            return default_value if isinstance(default_value, QColor) else QColor(default_value) if isinstance(default_value, str) and QColor(default_value).isValid() else QColor('gray')
        
        if isinstance(color_val, QColor):
            return color_val
        elif isinstance(color_val, str):
            qcolor = QColor(color_val)
            if qcolor.isValid():
                return qcolor
            else:
                logger.warning(f"SensorDisplayWidget: _get_themed_color: Invalid color string '{color_val}' for key '{key}'. Using default_value: '{default_value}'.")
                return default_value if isinstance(default_value, QColor) else QColor(default_value) if isinstance(default_value, str) and QColor(default_value).isValid() else QColor('gray')
        else:
            logger.warning(f"SensorDisplayWidget: _get_themed_color: Unexpected type '{type(color_val)}' for key '{key}'. Using default_value: '{default_value}'.")
            return default_value if isinstance(default_value, QColor) else QColor(default_value) if isinstance(default_value, str) and QColor(default_value).isValid() else QColor('gray')

    def _get_themed_numeric_property(self, key, default_value):
        value = self.theme_colors.get(key)
        if value is None:
            logger.warning(f"SensorDisplayWidget: _get_themed_numeric_property: Key '{key}' not found in theme_colors. Using default_value: '{default_value}'.")
            return default_value
        try:
            return float(value) if isinstance(default_value, float) else int(value)
        except (ValueError, TypeError):
            logger.warning(f"SensorDisplayWidget: _get_themed_numeric_property: Invalid numeric value '{value}' for key '{key}'. Using default_value: '{default_value}'.")
            return default_value

    def _get_themed_string_property(self, key, default_value):
        value = self.theme_colors.get(key)
        if value is None:
            logger.warning(f"SensorDisplayWidget: _get_themed_string_property: Key '{key}' not found in theme_colors. Using default_value: '{default_value}'.")
            return default_value
        return str(value)

    def _get_current_gauge_colors(self):
        """
        Determines the set of colors to use for drawing the gauge based on the
        current theme and the sensor's alert state.
        """
        # --- MODIFIED: Color selection logic updated for specific alert states ---

        # 1. Define base colors for the 'normal' state
        base_bg = self._get_themed_color('gauge_background_normal', QColor('#F0F8FF'))
        base_border = self._get_themed_string_property('gauge_border_normal', '1px solid #87CEFA')
        base_fill = self._get_themed_color('gauge_fill_normal', QColor('#4682B4'))
        base_text = self._get_themed_color('gauge_text_normal', QColor('#2C3E50'))
        base_scale = self._get_themed_color('analog_gauge_scale_color', QColor('#2C3E50'))
        base_needle = self._get_themed_color('analog_gauge_needle_color', QColor('#CC0000'))
        base_center_dot = self._get_themed_color('analog_gauge_center_dot_color', QColor('#1F3A60'))
        base_label = self._get_themed_color('analog_gauge_label_color', QColor('#2C3E50'))

        # 2. Conditionally override colors based on the specific alert state
        if self._alert_state == 'critical':
            base_bg = self._get_themed_color('gauge_background_alert', QColor('#FFDCDC'))
            base_border = self._get_themed_string_property('gauge_border_alert', '1px solid #FF6666')
            base_fill = self._get_themed_color('gauge_critical_color', QColor('#CC0000'))  # Use CRITICAL color
            base_text = self._get_themed_color('gauge_text_alert', QColor('#FFFFFF'))
            base_scale = self._get_themed_color('analog_gauge_scale_alert_color', QColor('#CC0000'))
            base_needle = self._get_themed_color('analog_gauge_needle_alert_color', QColor('#FF4500'))
            base_center_dot = self._get_themed_color('analog_gauge_center_dot_alert_color', QColor('#CC0000'))
            base_label = self._get_themed_color('analog_gauge_text_alert_color', QColor('#FFFFFF'))
        elif self._alert_state == 'warning':
            base_bg = self._get_themed_color('gauge_background_alert', QColor('#FFF3CD'))
            base_border = self._get_themed_string_property('gauge_border_alert', '1px solid #FFC107')
            base_fill = self._get_themed_color('gauge_warning_color', QColor('#FFD700'))  # Use WARNING color
            base_text = self._get_themed_color('gauge_text_normal', QColor('#000000')) # Darker text for warning
            base_scale = self._get_themed_color('analog_gauge_scale_alert_color', QColor('#FFC107'))
            base_needle = self._get_themed_color('analog_gauge_needle_alert_color', QColor('#FF4500'))
            base_center_dot = self._get_themed_color('analog_gauge_center_dot_alert_color', QColor('#FFC107'))
            base_label = self._get_themed_color('analog_gauge_text_alert_color', QColor('#000000'))

        # --- END OF MODIFICATIONS ---

        # 3. Assemble the initial colors dictionary
        colors = {
            'background': base_bg,
            'border': base_border,
            'fill_color': base_fill,
            'text_color': base_text,
            'scale_color': base_scale,
            'needle_color': base_needle,
            'center_dot_color': base_center_dot,
            'label_color': base_label, 
            'text_outline_color': self._get_themed_color('gauge_text_outline_color', QColor('black')),
            'high_contrast_text_color': self._get_themed_color('gauge_high_contrast_text_color', QColor('white')),
            'warning_color': self._get_themed_color('gauge_warning_color', QColor('#FFD700')),
            'critical_color': self._get_themed_color('gauge_critical_color', QColor('#CC0000')),
            'gauge_border_width': self._get_themed_numeric_property('gauge_border_width', 1),
            'gauge_border_style': self._get_themed_string_property('gauge_border_style', 'solid'),
            'gauge_border_color': self._get_themed_color('gauge_border_color', QColor('#87CEFA')), 
        }

        # 4. Apply gauge-specific overrides (This logic remains the same)
        prefix = ""
        if self._gauge_type == "Analog - Basic Classic":
            prefix = "analog_basic_classic_"
        elif self._gauge_type == "Analog - Full Classic":
            prefix = "analog_full_classic_"
        elif self._gauge_type == "Analog - Modern Basic":
            prefix = "analog_modern_basic_"
        elif self._gauge_type == "Analog - Modern Full":
            prefix = "analog_modern_full_"
        elif self._gauge_type == "Semi-Circle - Modern":
            prefix = "semi_circle_modern_"
        elif self._gauge_type == "Standard - Modern":
            prefix = "standard_modern_"
        elif self._gauge_type == "Linear - Basic":
            prefix = "linear_basic_"
        elif self._gauge_style == "Flat":
            prefix = "flat_gauge_"
        elif self._gauge_style == "Shadowed": 
            prefix = "shadowed_gauge_"
        elif self._gauge_style == "Raised":
            prefix = "raised_gauge_"
        elif self._gauge_style == "Inset":
            prefix = "inset_gauge_"
        elif self._gauge_style == "Heavy Border":
            prefix = "heavy_gauge_"
        elif self._gauge_style == "Clean":
            prefix = "clean_gauge_"
        elif self._gauge_style == "Deep Shadow":
            prefix = "deep_shadow_gauge_"
        elif self._gauge_style == "Outline":
            prefix = "outline_gauge_"
        elif self._gauge_style == "Vintage":
            prefix = "vintage_gauge_"
        elif self._gauge_style == "Subtle":
            prefix = "subtle_gauge_"
        elif self._gauge_style == "Fresh":
            prefix = "fresh_gauge_"
        elif self._gauge_style == "Bright":
            prefix = "bright_gauge_"
        elif self._gauge_style == "Bold":
            prefix = "bold_gauge_"
        elif self._gauge_type == "Digital - Classic" or self._gauge_type == "Digital - Segmented":
            prefix = "digital_gauge_"
        elif self._gauge_type.startswith("Progress Bar - Custom"):
            prefix = "custom_progressbar_"


        if prefix:
            colors['background'] = self._get_themed_color(f"{prefix}background", colors['background'])
            colors['border'] = self._get_themed_string_property(f"{prefix}border", colors['border'])
            colors['fill_color'] = self._get_themed_color(f"{prefix}fill_color", colors['fill_color'])
            colors['text_color'] = self._get_themed_color(f"{prefix}text_color", colors['text_color'])
            colors['scale_color'] = self._get_themed_color(f"{prefix}scale_color", colors['scale_color'])
            colors['needle_color'] = self._get_themed_color(f"{prefix}needle_color", colors['needle_color'])
            colors['center_dot_color'] = self._get_themed_color(f"{prefix}center_dot_color", colors['center_dot_color'])
            colors['label_color'] = self._get_themed_color(f"{prefix}label_color", colors['label_color']) 

            colors['gauge_border_width'] = self._get_themed_numeric_property(f"{prefix}border_width", colors['gauge_border_width'])
            colors['gauge_border_style'] = self._get_themed_string_property(f"{prefix}border_style", colors['gauge_border_style'])
            colors['gauge_border_color'] = self._get_themed_color(f"{prefix}border_color", colors['gauge_border_color'])

            if self._alert_state != "normal":
                colors['background'] = self._get_themed_color(f"{prefix}background_alert", colors['background'])
                colors['border'] = self._get_themed_string_property(f"{prefix}border_alert", colors['border'])
                colors['fill_color'] = self._get_themed_color(f"{prefix}fill_alert", colors['fill_color'])
                colors['text_color'] = self._get_themed_color(f"{prefix}text_alert", colors['text_color'])
                colors['scale_color'] = self._get_themed_color(f"{prefix}scale_alert_color", colors['scale_color'])
                colors['needle_color'] = self._get_themed_color(f"{prefix}needle_alert_color", colors['needle_color'])
                colors['center_dot_color'] = self._get_themed_color(f"{prefix}center_dot_alert_color", colors['center_dot_color'])
                colors['label_color'] = self._get_themed_color(f"{prefix}label_alert_color", colors['label_color']) 

                colors['gauge_border_width'] = self._get_themed_numeric_property(f"{prefix}border_alert_width", colors['gauge_border_width'])
                colors['gauge_border_style'] = self._get_themed_string_property(f"{prefix}border_alert_style", colors['gauge_border_style'])
                colors['gauge_border_color'] = self._get_themed_color(f"{prefix}border_alert_color", colors['gauge_border_color'])

        logger.debug(f"SensorDisplayWidget: Resolved colors for {self.objectName()} (Alert: {self._alert_state}): {dict(list(colors.items())[:5])}...")
        return colors

    def paintEvent(self, event):
        """Custom paint event for drawing the gauge."""
        is_progressbar_native_type = (self._gauge_type == "Progress Bar - Horizontal" or
                                      self._gauge_type == "Progress Bar - Vertical")

        if is_progressbar_native_type:
            super().paintEvent(event)
            return 

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.HighQualityAntialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        rect = self.contentsRect()
        logger.debug(f"SensorDisplayWidget: paintEvent triggered for {self.objectName()}. Current _value: {self._current_value}, Type: {self._gauge_type}, Style: {self._gauge_style}")

        colors = self._get_current_gauge_colors()
        
        if self.gauge_drawer:
            try:
                #self.gauge_drawer.draw(painter, rect, self._current_value_animated, 
                #                       self._min_value, self._max_value, self.unit, 
                #                       self._gauge_style, colors)
                self.gauge_drawer.draw(painter, rect, self.sensor_name, self._current_value_animated, 
                                       self._min_value, self._max_value, self.unit, 
                                       self._gauge_style, colors)
            except Exception as e:
                logger.error(f"Error drawing gauge for {self.objectName()} with type {self._gauge_type}: {e}")
                self.value_label.setText(f"Error: {e}")
                self.value_label.setVisible(True)
                self.progressBar.setVisible(False)
        else:
            logger.warning(f"SensorDisplayWidget: paintEvent: No custom drawer and not a native progress bar type '{self._gauge_type}'. Falling back to default QLabel.")
            self.value_label.setText(f"{self._format_value(self._current_value)} {self.unit}")
            self.value_label.setVisible(True)
            self.progressBar.setVisible(False)

        #painter.restore()       

        
    def _trigger_alert(self, message):
        """Triggers an alert, playing sound if enabled and emitting signal."""
        if self.settings_manager.get_boolean_setting('General', 'alert_sound_enabled', default=True):
            if not self.alert_sound_timer.isActive():
                self.alert_sound_timer.start()
                logger.debug("SensorDisplayWidget: Alert sound timer started.")
        
        self.alert_triggered.emit(self.sensor_category, self.metric_type, self._alert_state, message)
        logger.info(f"SensorDisplayWidget: Alert state changed for {self.sensor_name} to {self._alert_state.capitalize()}.")

    @pyqtProperty(float)
    def current_value_animated(self):
        """Property for animation to smoothly update gauge values."""
        return self._current_value_animated        

    @current_value_animated.setter
    def current_value_animated(self, value):
        self._current_value_animated = value
        self.update() 

    @pyqtSlot(object) 
    def update_value(self, raw_value):
        """
        Updates the sensor's current value, triggers alerts, and repaints the gauge.
        """
        logger.debug(f"SensorDisplayWidget {self.sensor_category}_{self.metric_type}: update_value received raw: '{raw_value}' (type: {type(raw_value)}).")

        old_value = self._current_value
        old_alert_state = self._alert_state
        old_na_state = self._na_state

        if raw_value is None or (isinstance(raw_value, (str)) and raw_value.strip().lower() == 'n/a'):
            self._current_value = None
            self._na_state = True
            self._alert_state = "normal" 
            logger.debug(f"SensorDisplayWidget: {self.sensor_name} is in N/A state.")
        else:
            try:
                value_float = float(raw_value)
                self._current_value = value_float
                self._na_state = False
                self._check_and_set_alert_state(value_float)
            except (ValueError, TypeError):
                self._current_value = None
                self._na_state = True
                self._alert_state = "normal"
                logger.warning(f"SensorDisplayWidget: Could not convert raw value '{raw_value}' to float for {self.sensor_name}. Setting to N/A.")

        value_changed = (old_value != self._current_value) or (old_na_state != self._na_state)
        alert_state_changed = (old_alert_state != self._alert_state)

        if value_changed or alert_state_changed:
            logger.debug(f"SensorDisplayWidget: {self.objectName()}: Value changed: {value_changed}, Alert state changed: {alert_state_changed}, NA state changed: {old_na_state != self._na_state}.")
            
            is_native_progressbar_type = (self._gauge_type == "Progress Bar - Horizontal" or
                                          self._gauge_type == "Progress Bar - Vertical")
            is_custom_progressbar_type = (self._gauge_type == "Progress Bar - Custom Horizontal" or
                                          self._gauge_type == "Progress Bar - Custom Vertical")


            if is_native_progressbar_type:
                if not self._na_state:
                    display_value = int(max(self._min_value, min(self._max_value, self._current_value)))
                    self.progressBar.setValue(display_value)
                    if self._alert_state == "warning":
                        self.progressBar.setProperty("alert_state", "warning")
                    elif self._alert_state == "critical":
                        self.progressBar.setProperty("alert_state", "critical")
                    else:
                        self.progressBar.setProperty("alert_state", "normal")
                    self.progressBar.setStyleSheet(self._get_progress_bar_qss())
                    self.progressBar.style().polish(self.progressBar)
                    logger.debug(f"SensorDisplayWidget: Progress bar value set to {display_value}.")
                else:
                    self.progressBar.setValue(0)
                    self.progressBar.setProperty("alert_state", "normal")
                    self.progressBar.setStyleSheet(self._get_progress_bar_qss())
                    self.progressBar.style().polish(self.progressBar)

            else: 
                if self.value_label.isVisible(): 
                    if self._na_state:
                        self.value_label.setText("N/A")
                    else:
                        self.value_label.setText(f"{self._format_value(self._current_value)} {self.unit}")
                    if self._alert_state == "normal":
                        self.value_label.setStyleSheet(f"color: {self._get_themed_color('label_color', QColor('#34495E')).name()};")
                    else:
                        self.value_label.setStyleSheet(f"color: {self._get_themed_color('gauge_text_alert', QColor('red')).name()};")
                
                if self.animation.state() == QPropertyAnimation.Running:
                    self.animation.stop()
                
                if value_changed and not self._na_state:
                    self.animation.setStartValue(old_value if old_value is not None else self._min_value)
                    self.animation.setEndValue(self._current_value)
                    self.animation.start()
                else:
                    self._current_value_animated = self._min_value if self._current_value is None else self._current_value
                    self.update() 


            if alert_state_changed:
                if self._alert_state != "normal":
                    alert_message = self._get_alert_message()
                    self.alert_triggered.emit(self.sensor_category, self.metric_type, self._alert_state, alert_message)
                    if self.settings_manager.get_boolean_setting('General', 'alert_sound_enabled', fallback=True):
                        self._play_alert_sound()
                else:
                    self.alert_cleared.emit(self.sensor_category, self.metric_type)
                    self.alert_sound_player.stop()

            logger.debug(f"SensorDisplayWidget: Repaint requested for {self.objectName()}.")
            self.update() 

    
    #def _check_and_set_alert_state(self, value):
    #    """Evaluates the alert state based on current value and thresholds."""
    #    new_alert_state = "normal"
    #    try:
    #        # --- FIX: Use the correct keys to get threshold values ---
    #        low_warn_str = self.thresholds.get('warning_low_value')
    #        high_warn_str = self.thresholds.get('warning_high_value')
     #       low_crit_str = self.thresholds.get('critical_low_value')
     #       high_crit_str = self.thresholds.get('critical_high_value')

            # Convert string values from config to float for comparison
      #      low_warn = float(low_warn_str) if low_warn_str is not None else None
      #      high_warn = float(high_warn_str) if high_warn_str is not None else None
      #      low_crit = float(low_crit_str) if low_crit_str is not None else None
       #     high_crit = float(high_crit_str) if high_crit_str is not None else None

            # Check critical thresholds first
        #    if (low_crit is not None and value < low_crit) or \
         #      (high_crit is not None and value > high_crit):
          #      new_alert_state = "critical"
            # Then check warning thresholds
          #  elif (low_warn is not None and value < low_warn) or \
           #      (high_warn is not None and value > high_warn):
            #    new_alert_state = "warning"

        #except (ValueError, TypeError) as e:
        #    logger.error(f"Error evaluating alert state for {self.sensor_name}: {e}")
        #    new_alert_state = "normal" 

        #if self._alert_state != new_alert_state:
        #    self._alert_state = new_alert_state
        #    self.alert_state_changed.emit(self.sensor_name, self.metric_type, self._alert_state)
        #    logger.debug(f"SensorDisplayWidget: {self.sensor_name} alert state evaluated to {self._alert_state}.")    

    def _check_and_set_alert_state(self, value):
        """Evaluates the alert state based on current value and thresholds."""
        new_alert_state = "normal"
        try:
            # FIX: Use the correct new key names to get threshold values
            low_warn = self.thresholds.get('warning_low_value')
            high_warn = self.thresholds.get('warning_high_value')
            low_crit = self.thresholds.get('critical_low_value')
            high_crit = self.thresholds.get('critical_high_value')

            # Critical thresholds take precedence
            if (low_crit is not None and value < low_crit) or \
               (high_crit is not None and value > high_crit):
                new_alert_state = "critical"
            # Then check for warning thresholds
            elif (low_warn is not None and value < low_warn) or \
                 (high_warn is not None and value > high_warn):
                new_alert_state = "warning"

        except (ValueError, TypeError) as e:
            logger.error(f"Error evaluating alert state for {self.sensor_name}: {e}")
            new_alert_state = "normal" 

        if self._alert_state != new_alert_state:
            self._alert_state = new_alert_state
            self.alert_state_changed.emit(self.sensor_name, self.metric_type, self._alert_state)
            logger.debug(f"SensorDisplayWidget: {self.sensor_name} alert state evaluated to {self._alert_state}.")        

    def _get_alert_message(self):
        """Constructs the alert message based on current state."""
        logger.debug(f"Constructing alert message for {self.sensor_name} with state '{self._alert_state}' and value '{self._current_value}'")

        # 1. Create the base message
        message = f"{self.sensor_name}: {self._format_value(self._current_value)} {self.unit}"

        # 2. Add the state suffix (Warning/Critical)
        if self._alert_state == "warning":
            message += " (Warning!)"
        elif self._alert_state == "critical":
            message += " (CRITICAL!)"

        logger.debug(f"  Base message: '{message}'")
        logger.debug(f"  Available thresholds for this sensor: {self.thresholds}")

        # 3. Get all possible threshold values
        warning_low = self.thresholds.get('warning_low_value')
        warning_high = self.thresholds.get('warning_high_value')
        critical_low = self.thresholds.get('critical_low_value')
        critical_high = self.thresholds.get('critical_high_value')
        current_val = self._current_value

        # 4. Append the specific threshold that was breached to the message
        if current_val is not None:
            if self._alert_state == "critical":
                if critical_low is not None and current_val < critical_low:
                    message += f" Critical Low: {self._format_value(critical_low)}"
                elif critical_high is not None and current_val > critical_high:
                    message += f" Critical High: {self._format_value(critical_high)}"
            elif self._alert_state == "warning":
                if warning_low is not None and current_val < warning_low:
                    message += f" Low: {self._format_value(warning_low)}"
                elif warning_high is not None and current_val > warning_high:
                    message += f" High: {self._format_value(warning_high)}"

        logger.debug(f"  Final constructed message: '{message}'")
        return message

    def _play_alert_sound(self):
        """Plays the alert sound."""
        if os.path.exists(self._alert_sound_path):
            if self.alert_sound_player.state() != QMediaPlayer.PlayingState:
                self.alert_sound_player.setMedia(QMediaContent(QUrl.fromLocalFile(self._alert_sound_path)))
                self.alert_sound_player.play()
                logger.debug(f"SensorDisplayWidget: Playing alert sound from {self._alert_sound_path}.")
            else:
                logger.debug("SensorDisplayWidget: Alert sound already playing.")
        else:
            self.alert_sound_timer.stop() 
            logger.warning(f"SensorDisplayWidget: Alert sound file not found at '{self._alert_sound_path}'. Skipping sound.")

    def _clear_alert(self):
        """Clears the alert state and stops alert indications."""
        self._alert_state = "normal"
        self.alert_sound_timer.stop()
        self.alert_sound_player.stop()
        self.alert_cleared.emit(self.sensor_category, self.metric_type)
        logger.info(f"SensorDisplayWidget: Alert cleared for {self.sensor_name}.")

    def _format_value(self, value):
        """Formats the value to the specified precision."""
        if value is None:
            return "N/A"
        try:
            return f"{value:.{self._precision}f}"
        except (ValueError, TypeError):
            return "N/A"

    #def _get_tooltip_text(self):
    #    """Generates the tooltip text for the widget."""
    #    tooltip = f"{self.sensor_name}: {self._format_value(self._current_value)} {self.unit}"
    #    if self._alert_state != "normal":
    #        tooltip += f" ({self._alert_state.upper()} ALERT!)"
    #    if self.thresholds.get('low_threshold') is not None:
    #        tooltip += f"\nLow Threshold: {self._format_value(self.thresholds['low_threshold'])}"
    #    if self.thresholds.get('high_threshold') is not None:
    #        tooltip += f"\nHigh Threshold: {self._format_value(self.thresholds['high_threshold'])}"
    #    return tooltip


    #def _get_tooltip_text(self):
    #    """Generates the tooltip text for the widget."""
    #    # Add a logger statement at the start of the method
    #    logger.debug(f"Generating tooltip for '{self.objectName()}'. Current thresholds: {self.thresholds}")

        #tooltip = f"{self.sensor_name}: {self._format_value(self._current_value)} {self.unit}"
       # if self._alert_state != "normal":
        #    tooltip += f" ({self._alert_state.upper()} ALERT!)"
        
        #low_threshold = self.thresholds.get('low_threshold')
        #high_threshold = self.thresholds.get('high_threshold')

        # Add loggers to check the retrieved values
        #logger.debug(f"Tooltip check: low_threshold is {low_threshold}, high_threshold is {high_threshold}")

        #if low_threshold is not None:
        #    tooltip += f"\nLow Threshold: {self._format_value(low_threshold)}"
        #if high_threshold is not None:
        #    tooltip += f"\nHigh Threshold: {self._format_value(high_threshold)}"
        #return tooltip

    def _get_tooltip_text(self):
        """
        Generates the complete tooltip text, including the current value,
        alert status, and all configured warning and critical thresholds.
        """
        # 1. LOG ENTRY: Announce the method call and show the data being used.
        logger.debug(f"Generating tooltip for '{self.objectName()}'. Thresholds received: {self.thresholds}")

        # Start with the essential sensor name and current value
        tooltip = f"{self.sensor_name}: {self._format_value(self._current_value)} {self.unit}"

        # Append the alert status if the state is not normal
        if self._alert_state != "normal":
            tooltip += f" ({self._alert_state.upper()} ALERT!)"

        # Check for and append the warning low threshold
        warning_low = self.thresholds.get('warning_low_value')
        if warning_low is not None:
            tooltip += f"\nWarn Low: {self._format_value(warning_low)}"

        # Check for and append the warning high threshold
        warning_high = self.thresholds.get('warning_high_value')
        if warning_high is not None:
            tooltip += f"\nWarn High: {self._format_value(warning_high)}"

        # Check for and append the critical low threshold
        critical_low = self.thresholds.get('critical_low_value')
        if critical_low is not None:
            tooltip += f"\nCritical Low: {self._format_value(critical_low)}"
            
        # Check for and append the critical high threshold
        critical_high = self.thresholds.get('critical_high_value')
        if critical_high is not None:
            tooltip += f"\nCritical High: {self._format_value(critical_high)}"
        
        # 2. LOG EXIT: Show the final constructed string before returning it.
        #    Newlines are replaced for a cleaner, single-line log entry.
        # This is the corrected line
        # Perform the replacement outside the f-string
        formatted_tooltip = tooltip.replace('\n', ' | ')

        # Now, use the new variable in the logger call
        logger.debug(f"Final tooltip for '{self.objectName()}': \"{formatted_tooltip}\"")
            
        return tooltip    
    def _set_value_range(self):
        """Internal helper to set the min/max values and update the progress bar range."""
        min_val, max_val = self.main_window.settings_manager.get_range(self.sensor_category, self.metric_type)
        
        if min_val is None:
            min_val = SettingsManager.DEFAULT_METRIC_INFO.get(self.sensor_category, {}).get(self.metric_type, {}).get('min', 0.0)
            logger.warning(f"SensorDisplayWidget: Invalid or missing min range for {self.sensor_name}. Using default: {min_val} {self.unit}.")
        if max_val is None:
            max_val = SettingsManager.DEFAULT_METRIC_INFO.get(self.sensor_category, {}).get(self.metric_type, {}).get('max', 100.0)
            logger.warning(f"SensorDisplayWidget: Invalid or missing max range for {self.sensor_name}. Using default: {max_val} {self.unit}.")

        self._min_value = min_val
        self._max_value = max_val

        self.progressBar.setRange(int(self._min_value), int(self._max_value)) 
        
        logger.debug(f"SensorDisplayWidget: Value range for {self.sensor_name} set to [{self._min_value}, {self._max_value}] {self.unit}.")
        

    def _update_ui_visibility(self):
        """Manages visibility of QLabel vs. QProgressBar based on gauge type."""
        is_native_progressbar_type = (self._gauge_type == "Progress Bar - Horizontal" or
                                      self._gauge_type == "Progress Bar - Vertical")
        is_custom_progressbar_type = (self._gauge_type == "Progress Bar - Custom Horizontal" or
                                      self._gauge_type == "Progress Bar - Custom Vertical")

        if is_native_progressbar_type:
            self.value_label.setVisible(False) 
            self.progressBar.setVisible(True)   
            self.progressBar.setStyleSheet(self._get_progress_bar_qss())
            self.progressBar.style().polish(self.progressBar)
            if self._gauge_type == "Progress Bar - Vertical":
                self.progressBar.setOrientation(Qt.Vertical)
                self.progressBar.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
            else: # Horizontal
                self.progressBar.setOrientation(Qt.Horizontal)
                self.progressBar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            logger.debug(f"  _update_ui_visibility: Showing NATIVE QProgressBar for type '{self._gauge_type}'.")
        elif is_custom_progressbar_type: 
            self.value_label.setVisible(False)
            self.progressBar.setVisible(False) 
            logger.debug(f"  _update_ui_visibility: Hiding QLabel/QProgressBar, CUSTOM Progress Bar will draw itself for type '{self._gauge_type}'.")
        elif self._gauge_type in self.GAUGE_DRAWERS: 
            self.value_label.setVisible(False) 
            self.progressBar.setVisible(False)  
            logger.debug(f"  _update_ui_visibility: Hiding QLabel/QProgressBar for custom drawn gauge type '{self._gauge_type}'.")
        else:
            logger.warning(f"  _update_ui_visibility: Fallback: Showing QLabel. Unknown/Unhandled Type: {self._gauge_type}.")
            self.value_label.setVisible(True)   
            self.progressBar.setVisible(False)  
            self.value_label.setText(f"{self._format_value(self._current_value)} {self.unit}")
            if self._alert_state == "normal":
                self.value_label.setStyleSheet(f"color: {self._get_themed_color('label_color', QColor('#34495E')).name()};")
            else:
                self.value_label.setStyleSheet(f"color: {self._get_themed_color('gauge_text_alert', QColor('red')).name()};")
            
        self.update() 
    
    def _get_progress_bar_qss(self):
        """Generates dynamic QSS for the QProgressBar based on theme colors and orientation."""
        logger.debug(f"  _get_progress_bar_qss for type: {self._gauge_type}")
        colors = self._get_current_gauge_colors()
        
        bg_color = colors['background'].name() if isinstance(colors['background'], QColor) else colors['background']
        chunk_color = colors['fill_color'].name() if isinstance(colors['fill_color'], QColor) else colors['fill_color']
        text_color = colors['text_color'].name() if isinstance(colors['text_color'], QColor) else colors['text_color']

        border_width = self._get_themed_numeric_property('progressbar_border_width', 1)
        border_style = self._get_themed_string_property('progressbar_border_style', 'solid')
        border_color_qcolor = self._get_themed_color('progressbar_border_color', QColor('#424242'))
        border_radius = self._get_themed_numeric_property('progressbar_border_radius', 8) 
        
        alert_bg_color = self._get_themed_color('progressbar_background_alert', QColor('#FFDCDC')).name()
        alert_chunk_color = self._get_themed_color('progressbar_chunk_alert_color', QColor('#CC0000')).name()
        alert_text_color = self._get_themed_color('progressbar_text_alert_color', QColor('#FFFFFF')).name()
        alert_border_color_qcolor = self._get_themed_color('progressbar_border_alert_color', QColor('#FF6666'))
        
        # Base QSS applicable to both orientations
        qss = f"""
        QProgressBar {{
            background-color: {bg_color};
            border: {border_width}px {border_style} {border_color_qcolor.name()};
            border-radius: {border_radius}px;
            text-align: center;
            color: {text_color};
        }}
        """

        if self._gauge_type == "Progress Bar - Horizontal":
            qss += f"""
            QProgressBar::chunk:horizontal {{
                background-color: {chunk_color};
                border-radius: {border_radius}px;
            }}
            """
        elif self._gauge_type == "Progress Bar - Vertical":
            qss += f"""
            QProgressBar::chunk:vertical {{
                background-color: {chunk_color};
                border-radius: {border_radius}px;
            }}
            """
        else: # Fallback, though ideally this function is only called for progress bars
            qss += f"""
            QProgressBar::chunk {{ /* Generic chunk style */
                background-color: {chunk_color};
                border-radius: {border_radius}px;
            }}
            """

        # Alert states (apply to both horizontal and vertical)
        if self._alert_state == "warning":
            qss += f"""
            QProgressBar[alert_state="warning"] {{
                background-color: {alert_bg_color};
                border-color: {self._get_themed_color('gauge_warning_color', QColor('#FFD700')).name()};
                color: {alert_text_color};
            }}
            QProgressBar::chunk[alert_state="warning"] {{
                background-color: {self._get_themed_color('gauge_warning_color', QColor('#FFD700')).name()};
            }}
            """
        elif self._alert_state == "critical":
            qss += f"""
            QProgressBar[alert_state="critical"] {{
                background-color: {alert_bg_color};
                border-color: {alert_border_color_qcolor.name()};
                color: {alert_text_color};
            }}
            QProgressBar::chunk[alert_state="critical"] {{
                background-color: {alert_chunk_color};
            }}
            """
        logger.debug(f"Dumping Progress Bar QSS\n'{qss}'")
        return qss

    def _get_themed_font_family(self, key, default_family):
        font_family = self._get_themed_string_property(key, default_family)
        return font_family
    
    #def mouseMoveEvent(self, event):
    #    self.setToolTip(self._get_tooltip_text())
    #    super().mouseMoveEvent(event)

    def mouseMoveEvent(self, event):
        """Handles mouse hover events to display the tooltip."""
        # 2. Add this log to confirm the event is firing
        logger.debug(f"mouseMoveEvent triggered for '{self.objectName()}' at position {event.pos()}")
        
        self.setToolTip(self._get_tooltip_text())
        super().mouseMoveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
     
        if self.progressBar and self.progressBar.isVisible():
         adjusted_rect = self.contentsRect().adjusted(
             self.main_layout.contentsMargins().left(), 
             self.main_layout.contentsMargins().top(), 
             -self.main_layout.contentsMargins().right(), 
             -self.main_layout.contentsMargins().bottom()
         )
         self.progressBar.setGeometry(adjusted_rect)
         
         self.progressBar.setStyleSheet(self._get_progress_bar_qss()) 
         self.progressBar.style().polish(self.progressBar)

        self.update() 

    @pyqtSlot(dict)
    def update_theme_colors(self, new_theme_colors):
        logger.info(f"SensorDisplayWidget: '{self.title()}' updating theme colors.")
        
        self.theme_colors = self.main_window.settings_manager.get_theme_colors() 
        
        if not self.theme_colors:
            logger.warning("SensorDisplayWidget: Theme colors are empty after update. Widget may not display correctly.")
            self.theme_colors = self.main_window.settings_manager._get_fallback_theme_colors()
            logger.info("SensorDisplayWidget: Using SettingsManager's fallback theme colors.")
        else:
            logger.debug(f"SensorDisplayWidget: Theme colors updated with {len(self.theme_colors)} properties.")

        logger.debug(f"SensorDisplayWidget: Theme colors updated. Re-polishing {self.objectName()} for new theme.")
        
        self.style().polish(self)
        self.value_label.style().polish(self.value_label)
        
        if self.progressBar and self.progressBar.isVisible():
             self.progressBar.setStyleSheet(self._get_progress_bar_qss())
             self.progressBar.style().polish(self.progressBar)

        self.update() 
        logger.debug(f"SensorDisplayWidget: '{self.title()}' theme colors updated and repainted.")
        
        self._update_ui_visibility() 
        if self._current_value is not None:
            self.update_value(self._current_value)