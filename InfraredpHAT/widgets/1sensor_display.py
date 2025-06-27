# -*- coding: utf-8 -*-
# --- widgets/sensor_display.py (Gauge Style Fixes & Enhanced Debugging) ---\
from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QSpacerItem
from PyQt5.QtCore import Qt, QTimer, QRect, QPoint, QPointF, pyqtSignal, QRectF
from PyQt5.QtGui import QPainter, QBrush, QColor, QFont, QPen, QTransform, QConicalGradient, QFontDatabase, QPainterPath, QFontMetrics
import logging
import math
import re

# Import SettingsManager to access static methods like _format_name_for_qss and DEFAULT_THEME_COLORS
from data_management.settings import SettingsManager 

logger = logging.getLogger(__name__)

class SensorDisplayWidget(QGroupBox):
    """
    A custom QGroupBox widget designed to display a single sensor metric
    with a customizable gauge type (standard, compact, digital, analog, progress bar)
    and style, including threshold-based color changes and alerts.
    """

    # Define a signal for alert state changes, to be connected by MainWindow
    # Emits (sensor_category, metric_type, is_alert)
    alert_state_changed = pyqtSignal(str, str, bool)

    # Added is_preview parameter
    def __init__(self, title, unit, thresholds, metric_type, sensor_category, main_window, theme_colors, initial_gauge_type, initial_gauge_style, is_preview=False, parent=None):
        super().__init__(title, parent=parent)
        self.setObjectName(SettingsManager._format_name_for_qss(f"{sensor_category}_{metric_type}Display")) # Object name for QSS
        logger.debug(f"SensorDisplayWidget: Initializing {self.objectName()}. Title: {title}, Type: {initial_gauge_type}")

        self.unit = unit
        # Store thresholds directly. This is a reference to the dictionary for this *specific* sensor/metric
        self.thresholds = dict(thresholds) if thresholds is not None else {'low': None, 'high': None} 
        self.metric_type = metric_type # e.g., 'temperature'
        self.sensor_category = sensor_category # e.g., 'HTU21D'
        self.main_window = main_window # Store main_window reference
        # Ensure theme_colors is a mutable dictionary, fallback to defaults if None is passed
        self.theme_colors = dict(theme_colors) if theme_colors is not None else SettingsManager.DEFAULT_THEME_COLORS 
        self.is_preview = is_preview # Flag for preview mode

        # Set initial gauge type and style
        self.current_gauge_type = initial_gauge_type 
        self.current_gauge_style = initial_gauge_style 

        # Internal value storage and range
        self._value = None 
        self._min_value = 0.0
        self._max_value = 100.0 # Default max, can be overridden by thresholds or specific metric ranges

        # For alert state management
        self._is_alert = False # Current alert state of this specific gauge
        self._is_na = True # Is the value N/A?
        self._previous_value = None # For detecting changes
        self._previous_is_alert = False # For detecting alert state changes

        # UI elements
        self.value_label = QLabel("N/A", self)
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Load and apply Digital-7 font if available
        # The font size will be adjusted by _adjust_label_font_size later.
        self._load_and_set_digital_font(self.value_label)
        self.value_label.setObjectName("GaugeValueLabel") # For QSS styling
        self.value_label.setText("N/A") # Initial text

        # QProgressBar for gauge types that use it (Type 6 Horizontal, Type 7 Vertical)
        self.progressBar = QProgressBar(self)
        self.progressBar.setTextVisible(True) # IMPORTANT: Let QProgressBar draw its own text by default
        self.progressBar.setAlignment(Qt.AlignCenter) 
        self.progressBar.setObjectName("SensorDisplayProgressBar") # For QSS styling
        self.progressBar.hide() # Hidden by default, shown for specific gauge types
        self.progressBar.setRange(0, 100) # Default range, will be updated by _set_value_range

        self.decimal_precision = self.main_window.settings_manager.get_setting(
            f'Precision_{self.sensor_category}', self.metric_type, type=int, default=2
        )

        # Set up a layout for the QGroupBox content. This is crucial.
        self.main_layout = QVBoxLayout(self) # Use self as parent for the layout
        self.main_layout.setContentsMargins(5, 40, 5, 5) # Padding for title and content
        self.main_layout.setAlignment(Qt.AlignCenter) # Center content vertically and horizontally

        # Add initial widget based on type (only one will be visible at a time)
        self.main_layout.addWidget(self.value_label, alignment=Qt.AlignCenter)
        self.main_layout.addWidget(self.progressBar) # Add but keep hidden

        self.setLayout(self.main_layout) # Set the layout for the group box

        self.setMouseTracking(True) # Enable mouse tracking for tooltip

        # Apply initial theme colors, range, and UI visibility
        self.update_theme_colors(self.theme_colors)
        self._set_value_range() # Call here to ensure min/max are set based on thresholds
        self._update_ui_visibility() # Call here to ensure correct widgets are visible


        logger.debug(f"SensorDisplayWidget '{title}' initialized (Type: {initial_gauge_type}, Style: {initial_gauge_style}, Preview: {is_preview}).")

    def _load_and_set_digital_font(self, label_widget):
        """Loads the Digital-7 font and applies it to the QLabel if successful."""
        digital_font_path = self.main_window.get_resource_path("fonts/digital-7.ttf")
        font_id = QFontDatabase.addApplicationFont(digital_font_path)
        if font_id != -1:
            font_families = QFontDatabase.applicationFontFamilies(font_id)
            if font_families:
                # Set a base font for digital, actual size adjusted later
                digital_font = QFont(font_families[0]) 
                label_widget.setFont(digital_font)
                logger.debug(f"SensorDisplayWidget: Applied '{font_families[0]}' font to value_label.")
            else:
                logger.warning(f"SensorDisplayWidget: No font families found for font ID {font_id} from {digital_font_path}. Using default.")
        else:
            logger.warning(f"SensorDisplayWidget: Could not add font '{digital_font_path}'. Using default.")

    def _adjust_label_font_size(self, label_widget, rect, font_family):
        """
        Dynamically adjusts the font size of a QLabel to fit within a given rectangle.
        Ensures the font remains readable and scales with widget size.
        """
        if label_widget is None or rect.isEmpty() or not label_widget.text():
            return

        min_font_size = 8
        max_font_size = 72 # A reasonable maximum font size

        target_width = rect.width() * 0.9 # Use 90% of width for padding
        target_height = rect.height() * 0.9 # Use 90% of height for padding

        # Start with a guess or a predefined size
        current_font_size = label_widget.font().pointSize() 
        if current_font_size == -1: # If pointSize is -1, it means default, so set a sensible start
            current_font_size = 24 

        # Binary search or iterative adjustment for best fit
        low = min_font_size
        high = max_font_size
        best_fit_size = current_font_size

        while low <= high:
            mid = (low + high) // 2
            test_font = QFont(font_family, mid, QFont.Bold if "digital" in self.current_gauge_type.lower() else QFont.Normal)
            metrics = QFontMetrics(test_font)
            text_width = metrics.horizontalAdvance(label_widget.text())
            text_height = metrics.height()

            if text_width <= target_width and text_height <= target_height:
                best_fit_size = mid
                low = mid + 1
            else:
                high = mid - 1
        
        # Apply the best fit font size, ensuring it's within bounds
        final_font_size = max(min_font_size, min(best_fit_size, max_font_size))
        
        # Only update if the size actually changes to avoid unnecessary repaints
        if label_widget.font().pointSize() != final_font_size:
            new_font = QFont(font_family, final_font_size, QFont.Bold if "digital" in self.current_gauge_type.lower() else QFont.Normal)
            label_widget.setFont(new_font)
            logger.debug(f"  _adjust_label_font_size: Adjusted font size for '{label_widget.objectName()}' to {final_font_size}pt.")


    def _get_tooltip_text(self):
        """Constructs and returns the tooltip text."""
        low_thr = self.thresholds.get('low')
        high_thr = self.thresholds.get('high')
        
        # Format value with precision
        display_value = self._value
        if display_value is not None:
            display_value = f"{display_value:.{self.decimal_precision}f}"
        else:
            display_value = 'N/A'

        tooltip_text = f"Value: {display_value} {self.unit}\n" \
                       f"Range: {self._min_value:.1f} - {self._max_value:.1f} {self.unit}\n"
        
        if low_thr is not None:
            tooltip_text += f"Low Threshold: {low_thr:.1f} {self.unit}\n"
        if high_thr is not None:
            tooltip_text += f"High Threshold: {high_thr:.1f} {self.unit}"
        return tooltip_text

    def _get_progress_bar_qss(self):
        """Constructs and returns the QSS string for the internal QProgressBar based on theme colors and style."""
        # Get base colors from theme
        background_color = self._get_themed_color('progressbar_background', '#2A3B4C')
        border_color_str = self._get_themed_color('progressbar_border', '1px solid #4A6C8E') # This returns string
        border_radius_str = self._get_themed_color('progressbar_border_radius', '4px') # This returns string
        chunk_color = self._get_themed_color('progressbar_chunk_color', '#87CEEB')
        text_color = self._get_themed_color('progressbar_text_color', '#E0F2F7')
        
        # Determine alert state and apply alert colors if necessary
        if self._is_alert:
            # Use specific alert colors if defined, otherwise fall back to normal gauge alert colors
            background_color = self._get_themed_color('progressbar_background_alert', self._get_themed_color('gauge_background_alert', '#5C2D2D'))
            border_color_str = self._get_themed_color('progressbar_border_alert', self._get_themed_color('gauge_border_alert', '1px solid #FF6666'))
            chunk_color = self._get_themed_color('progressbar_chunk_alert_color', self._get_themed_color('gauge_fill_alert', '#FF0000'))
            text_color = self._get_themed_color('progressbar_text_alert_color', self._get_themed_color('gauge_text_alert', '#FFD700'))
            
        font_family = self._get_themed_font_family('font_family', 'Inter')
        
        # Calculate font size for ProgressBar's native text (text is handled by QProgressBar itself now)
        # Scale based on the smaller dimension of the widget to ensure it fits
        # Use a sensible default if the progressBar geometry isn't available yet (e.g. at init)
        pb_height = self.progressBar.height() if self.progressBar.height() > 0 else 100
        pb_width = self.progressBar.width() if self.progressBar.width() > 0 else 100
        
        optimal_font_size = min(pb_width, pb_height) // 4 # Adjusted to /4 for better fit
        
        # Clamp font size
        pb_font_size = max(8, min(optimal_font_size, 24)) 

        qss = f"""
        QProgressBar#{self.objectName()} {{
            background-color: {background_color.name()};
            border: {border_color_str};
            border-radius: {border_radius_str};
            color: {text_color.name()}; /* This colors the text over the unfilled portion and default */
            text-align: center;
            font-family: "{font_family}";
            font-size: {pb_font_size}pt;
        }}
        QProgressBar#{self.objectName()}::chunk {{
            background-color: {chunk_color.name()};
            border-radius: {border_radius_str};
            color: {text_color.name()}; /* This colors the text over the filled portion */
        }}
        """
        logger.debug(f"SensorDisplayWidget: Generated QSS for QProgressBar for type '{self.current_gauge_type}', style '{self.current_gauge_style}'.")
        return qss

    def _set_value_range(self):
        """
        Sets the min/max values for the gauge and progress bar based on thresholds or default ranges.
        This also updates the QProgressBar's range if it's visible.
        """
        # Use a sensible default range if thresholds are not available or are invalid
        default_min_max = {
            "temperature": (0.0, 50.0), # Example range for temperature
            "humidity": (0.0, 100.0),
            "pressure": (900.0, 1100.0), # Example range for pressure (hPa)
            "light": (0.0, 2000.0) # Example range for light (lx)
        }
        
        low_thr = self.thresholds.get('low')
        high_thr = self.thresholds.get('high')

        metric_default_min, metric_default_max = default_min_max.get(self.metric_type, (0.0, 100.0))

        # Use thresholds if valid, otherwise use default metric ranges
        if low_thr is not None and high_thr is not None and low_thr < high_thr:
            # Extend range slightly beyond thresholds for better visual representation
            range_span = high_thr - low_thr
            self._min_value = low_thr - range_span * 0.1 # 10% padding below low
            self._max_value = high_thr + range_span * 0.1 # 10% padding above high
            
            # Ensure min/max don't go below 0 for certain metrics
            if self.metric_type in ['humidity', 'light'] and self._min_value < 0:
                self._min_value = 0.0
            
            # Ensure max doesn't go above a sensible upper bound for percentages
            if self.metric_type == 'humidity' and self._max_value > 100.0:
                self._max_value = 100.0
        else:
            self._min_value = metric_default_min
            self._max_value = metric_default_max
            logger.warning(f"SensorDisplayWidget: Invalid or missing thresholds for {self.sensor_category} {self.metric_type}. Using default range: [{self._min_value:.1f}, {self._max_value:.1f}] {self.unit}.")

        # Ensure min is always less than max, preventing division by zero or inverse scales
        if self._min_value >= self._max_value:
            # Fallback to a very generic default if calculations lead to invalid ranges
            self._min_value = 0.0
            self._max_value = 100.0
            logger.error(f"SensorDisplayWidget: Calculated min_value ({self._min_value}) >= max_value ({self._max_value}) for {self.sensor_category} {self.metric_type}. Resetting to [0, 100].")

        # Update QProgressBar range if it's in use
        if self.progressBar:
            # QProgressBar works with integers, so use a simple 0-100 scale for percentage fill
            self.progressBar.setRange(0, 100) 
            logger.debug(f"SensorDisplayWidget: ProgressBar range set to [0, 100] for {self.sensor_category} {self.metric_type}.")

        logger.debug(f"SensorDisplayWidget: Value range for {self.sensor_category} {self.metric_type} set to [{self._min_value:.1f}, {self._max_value:.1f}] {self.unit}.")

    def update_value(self, value):
        """
        Updates the displayed sensor value and triggers a repaint.
        Also evaluates alert state and updates the progress bar.
        """
        logger.debug(f"SensorDisplayWidget {self.sensor_category}_{self.metric_type}: update_value received raw: '{value}' (type: {type(value)}).")
        
        new_is_na = False
        if value is not None:
            try:
                value = float(value)
                if math.isnan(value): # Check for NaN after conversion
                    new_is_na = True
                    value = None # Treat NaN as None for N/A state
            except (ValueError, TypeError):
                logger.error(f"SensorDisplayWidget: Invalid value received for {self.sensor_category}_{self.metric_type}: '{value}'. Expected numeric. Setting to None.")
                value = None # Set to None if conversion fails
                new_is_na = True
        else:
            new_is_na = True
        
        # Determine if a repaint is truly needed
        value_changed = False
        if self._value is None or value is None: 
            value_changed = (self._value != value)
        else:
            # Compare floats with a tolerance
            value_changed = (abs(self._value - value) > 0.001) 
        
        # Store previous alert state *before* updating current value and re-checking
        old_is_alert = self._is_alert
        
        # Update current value and N/A state
        self._value = value 
        self._is_na = new_is_na

        self.update_alert_state() # This sets self._is_alert internally
        alert_state_changed = (self._is_alert != old_is_alert)

        logger.debug(f"SensorDisplayWidget: {self.objectName()}: Value changed: {value_changed}, Alert state changed: {alert_state_changed}, NA state changed: {self._is_na != new_is_na}.")

        # Emit signal if alert state changed
        if alert_state_changed:
            self.alert_state_changed.emit(self.sensor_category, self.metric_type, self._is_alert)
            logger.info(f"SensorDisplayWidget: Alert state changed for {self.objectName()} to {self._is_alert}.")
        
        # --- UPDATE UI ELEMENTS & TRIGGER REPAINT ---
        # Always update QLabel and QProgressBar's internal values, then force repaint if needed
        
        # 1. Update QProgressBar's native value if visible (only for Horizontal)
        # For Vertical, we'll hide native text and draw custom text.
        if self.progressBar.isVisible():
            if not self._is_na and self._value is not None:
                # Scale actual sensor value to ProgressBar's 0-100 range
                scaled_value = 0
                if (self._max_value - self._min_value) != 0:
                    scaled_value = int(((self._value - self._min_value) / (self._max_value - self._min_value)) * 100)
                scaled_value = max(0, min(100, scaled_value)) # Clamp to 0-100
                self.progressBar.setValue(scaled_value)
                logger.debug(f"  ProgressBar value set to {scaled_value} (scaled from {self._value}).")
            else:
                self.progressBar.setValue(0) # Reset progress bar if value is N/A or None
                logger.debug("  ProgressBar value set to 0 (N/A).")
            
            # Re-apply QSS to progress bar to ensure colors/fonts update based on alert state
            self.progressBar.setStyleSheet(self._get_progress_bar_qss())
            self.progressBar.style().polish(self.progressBar) # Ensure style is re-applied
            
            # Handle text visibility based on orientation
            if self.current_gauge_type == "Type 7 (Progress Bar - Vertical)":
                self.progressBar.setTextVisible(False) # Hide native text for vertical
                logger.debug("  QProgressBar: Native text hidden for vertical bar (custom drawing will be used).")
            else:
                self.progressBar.setTextVisible(True) # Show native text for horizontal
                logger.debug("  QProgressBar: Native text visible for horizontal bar.")

        # 2. Update QLabel text if visible (for Digital gauge or fallback)
        if self.value_label.isVisible():
            if not self._is_na and self._value is not None:
                formatted_value = f"{self._value:.{self.decimal_precision}f}" if self.decimal_precision is not None else str(self._value)
                self.value_label.setText(f"{formatted_value} {self.unit}")
                # Update text color based on alert state
                text_color = self._get_themed_color('digital_gauge_font_color', '#00FF00') if "Digital" in self.current_gauge_type else self._get_themed_color('gauge_text_normal', '#E0F2F7')
                if self._is_alert:
                    text_color = self._get_themed_color('digital_gauge_font_alert_color', '#FFD700') if "Digital" in self.current_gauge_type else self._get_themed_color('gauge_text_alert', '#FFD700')
                self.value_label.setStyleSheet(f"color: {text_color.name()}; background-color: transparent;")
            else:
                self.value_label.setText("N/A")
                self.value_label.setStyleSheet(f"color: {self._get_themed_color('label_color', '#E0F2F7').name()}; background-color: transparent;")
            
            # Dynamically adjust font size for the label (always call this)
            self._adjust_label_font_size(self.value_label, self.value_label.rect(), self._get_themed_font_family(
                'digital_font_family' if "Digital" in self.current_gauge_type else 'font_family', 'Inter'))

        # Request repaint if ANY visual state changed (value, alert, N/A, or gauge type implies custom drawing)
        # We always call update() on the parent widget if value or alert state changed, or if N/A state changed.
        # This will trigger paintEvent for custom drawn gauges.
        if value_changed or alert_state_changed or (self._is_na != new_is_na):
            self.update() 
            logger.debug(f"SensorDisplayWidget: Repaint requested for {self.objectName()}.")
        else:
            logger.debug(f"SensorDisplayWidget: Value for {self.objectName()} is unchanged ({self._value}). No repaint.")
        
        # Always update tooltip with latest info
        self.setToolTip(self._get_tooltip_text())


    def update_thresholds(self, new_metric_thresholds):
        """
        Updates the thresholds for THIS SPECIFIC SENSOR/METRIC display widget.
        This method is called by the parent tab (DashboardTab or SensorDetailsTab)
        when global thresholds change.
        `new_metric_thresholds` should be a dictionary like {'low': X, 'high': Y}
        """
        logger.debug(f"SensorDisplayWidget: update_thresholds called for {self.objectName()} with new_metric_thresholds: {new_metric_thresholds}")
        
        # Update only the specific metric's thresholds within the widget's stored copy
        # Use .clear() and .update() to ensure it's a fresh copy and not merging old, irrelevant keys
        if self.thresholds != new_metric_thresholds: # Only update if there's a change
            self.thresholds.clear()
            self.thresholds.update(new_metric_thresholds) 
            
            # After updating thresholds, re-evaluate alert state and update progress bar range
            self._set_value_range() # Recalculate value range as it depends on new thresholds
            
            # Re-apply current value to update progress bar / label based on new range/alert state
            self.update_value(self._value) # This will re-evaluate alert state and call self.update()

            logger.debug(f"SensorDisplayWidget: Thresholds updated for {self.metric_type}. Alert state and value range re-evaluated.")
        else:
            logger.debug(f"SensorDisplayWidget: Thresholds for {self.metric_type} are unchanged.")


    def update_theme_colors(self, new_theme_colors):
        """
        Updates the internal theme colors and forces a repaint.
        This ensures the gauge and text colors update dynamically.
        """
        self.theme_colors.clear()
        self.theme_colors.update(new_theme_colors)
        logger.debug(f"SensorDisplayWidget: Theme colors updated. Re-polishing {self.objectName()} for new theme.")
        
        # Re-polish the widget itself and its children to apply QSS
        self.style().polish(self) # Polish the QGroupBox itself
        self.value_label.style().polish(self.value_label) # Polish QLabel
        
        # Re-apply specific QSS for progress bar if visible
        if self.progressBar.isVisible():
            self.progressBar.setStyleSheet(self._get_progress_bar_qss())
            self.progressBar.style().polish(self.progressBar) # Important to re-polish native widgets


        # Re-apply current gauge settings to ensure visibility is correct
        self._update_ui_visibility() # This will ensure correct widgets are visible/hidden
        
        # Re-apply current value to ensure colors/text for value are updated with new theme
        self.update_value(self._value) # This calls self.update() internally and recalculates alert state
        
        logger.debug(f"SensorDisplayWidget: Theme update for {self.objectName()} completed and repaint requested.")


    def update_gauge_display_type_and_style(self, gauge_type, gauge_style):
        """
        Updates the gauge type and style, and triggers a repaint.
        """
        if self.current_gauge_type != gauge_type or self.current_gauge_style != gauge_style:
            self.current_gauge_type = gauge_type
            self.current_gauge_style = gauge_style
            logger.info(f"SensorDisplayWidget: Gauge display type/style updated to Type='{gauge_type}', Style='{gauge_style}' for {self.sensor_category} {self.metric_type}.")
            self._update_ui_visibility() # Adjust which core widgets are visible
            self._set_value_range() # Range might need re-evaluation for different gauge types
            # Re-apply current value to force repaint with new style and update PBar value
            # This also re-evaluates alert state based on new gauge type potentially (if it affects styling logic)
            self.update_value(self._value) 
        else:
            logger.debug(f"SensorDisplayWidget: Gauge type/style already {gauge_type}/{gauge_style}. No update needed.")

    def _update_ui_visibility(self):
        """
        Adjusts the visibility of QLabel and QProgressBar based on the selected gauge type.
        This helps manage which underlying Qt widget is responsible for the display.
        """
        logger.debug(f"  _update_ui_visibility: Setting visibility for type '{self.current_gauge_type}'.")

        # Hide all specific UI elements first
        self.value_label.hide()
        self.progressBar.hide()

        if self.current_gauge_type in ["Type 1 (Standard)", "Type 2 (Compact)", "Type 4 (Analog - Basic)", "Type 5 (Analog - Full)"]:
            # These are primarily custom-drawn. The QLabel and ProgressBar are hidden.
            self.value_label.hide()
            self.progressBar.hide()
            logger.debug(f"  UI Visibility: Hiding QLabel and QProgressBar for custom-drawn gauge type: {self.current_gauge_type}.")
        elif self.current_gauge_type == "Type 3 (Digital)":
            self.value_label.show() # Digital uses QLabel with custom font
            # Ensure font is set correctly for digital
            self._load_and_set_digital_font(self.value_label)
            # Use digital_gauge_font_color from theme for the label's QSS
            digital_text_color = self._get_themed_color('digital_gauge_font_color', self._get_themed_color('gauge_text_normal', '#00FF00'))
            self.value_label.setStyleSheet(f"color: {digital_text_color.name()}; background-color: transparent;") 
            logger.debug(f"  UI Visibility: Showing QLabel for Digital Gauge. Font: {self.value_label.font().family()}.")
        elif self.current_gauge_type in ["Type 6 (Progress Bar - Horizontal)", "Type 7 (Progress Bar - Vertical)"]:
            self.progressBar.show()
            self.progressBar.setOrientation(Qt.Horizontal if "Horizontal" in self.current_gauge_type else Qt.Vertical)
            # Apply QSS immediately after showing, before first paint, for correct size calculation
            self.progressBar.setStyleSheet(self._get_progress_bar_qss())
            self.progressBar.style().polish(self.progressBar) # Force QSS re-evaluation for native sizing
            
            # Crucially, hide native text for vertical progress bar, as we will draw it custom
            if self.current_gauge_type == "Type 7 (Progress Bar - Vertical)":
                self.progressBar.setTextVisible(False)
                logger.debug("  UI Visibility: Hiding native QProgressBar text for Vertical Progress Bar.")
            else:
                self.progressBar.setTextVisible(True)
                logger.debug("  UI Visibility: Showing native QProgressBar text for Horizontal Progress Bar.")

        else:
            # Fallback for unknown types or initial state
            self.value_label.show()
            self.value_label.setFont(QFont(self.theme_colors.get('font_family', "Inter"), 24)) # Reset font
            self.value_label.setStyleSheet(f"color: {self._get_themed_color('label_color', '#E0F2F7').name()}; background-color: transparent;")
            logger.warning(f"  UI Visibility: Fallback: Showing QLabel. Unknown Type: {self.current_gauge_type}.")

        # Force a repaint after changing visibility
        self.update()


    def update_alert_state(self):
        """
        Evaluates the current sensor value against thresholds and updates the alert status.
        Emits alert_state_changed signal if the status changes.
        """
        new_is_alert = False
        low_threshold = self.thresholds.get('low')
        high_threshold = self.thresholds.get('high')

        if self._value is not None and not self._is_na:
            if low_threshold is not None and self._value < low_threshold:
                new_is_alert = True
                logger.debug(f"SensorDisplayWidget: {self.sensor_category} {self.metric_type} is in ALERT (LOW): Value={self._value:.2f}, Threshold={low_threshold:.2f}.")
            elif high_threshold is not None and self._value > high_threshold:
                new_is_alert = True
                logger.debug(f"SensorDisplayWidget: {self.sensor_category} {self.metric_type} is in ALERT (HIGH): Value={self._value:.2f}, Threshold={high_threshold:.2f}.")
            else:
                logger.debug(f"SensorDisplayWidget: {self.sensor_category} {self.metric_type} is NORMAL: Value={self._value:.2f}, Thresholds=[{low_threshold if low_threshold is not None else 'N/A'}-{high_threshold if high_threshold is not None else 'N/A'}].")
        else:
            new_is_alert = False # No alert if value is N/A or None
            logger.debug(f"SensorDisplayWidget: {self.sensor_category} {self.metric_type} has no value (N/A). No alert.")
        
        # Log if thresholds are missing for alert check but value exists
        if (low_threshold is None and high_threshold is None) and (self._value is not None and not self._is_na):
            logger.warning(f"SensorDisplayWidget: No thresholds defined for {self.sensor_category} {self.metric_type}. Cannot evaluate alert status.")

        if new_is_alert != self._is_alert:
            self._is_alert = new_is_alert
            # Emit signal only if alert state has truly changed
            self.alert_state_changed.emit(self.sensor_category, self.metric_type, self._is_alert)
            logger.info(f"SensorDisplayWidget: Alert state changed for {self.sensor_category} {self.metric_type} to {self._is_alert}.")
        else:
            logger.debug(f"SensorDisplayWidget: Alert state for {self.sensor_category} {self.metric_type} is unchanged ({self._is_alert}).")


    def paintEvent(self, event):
        """
        Custom painting for gauge types (Analog, Standard, Compact, Digital overlay).
        QGroupBox background, border, and title are handled by super().paintEvent.
        """
        super().paintEvent(event) 

        logger.debug(f"SensorDisplayWidget: paintEvent triggered for {self.objectName()}. Current _value: {self._value}, Type: {self.current_gauge_type}, Style: {self.current_gauge_style}")
        logger.debug(f"  Gauge Title: {self.title()}")
        logger.debug(f"  Widget Rect (total geometry): {self.rect()}")
        logger.debug(f"  Content Rect (inside margins): {self.contentsRect()}")
        logger.debug(f"  paintEvent: SensorDisplayWidget theme_colors content (first 500 chars): {str(self.theme_colors)[:500]}...")
        logger.debug(f"  paintEvent: SensorDisplayWidget theme_colors size: {len(self.theme_colors)} keys.")
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.HighQualityAntialiasing) 

        # Get the rect within which to draw the custom gauge (excluding groupbox frame)
        content_rect = self.contentsRect()
        # Reduce size to center the gauge better within the group box's content area
        gauge_size = min(content_rect.width(), content_rect.height()) * 0.95 
        gauge_rect = QRectF(
            content_rect.center().x() - gauge_size / 2,
            content_rect.center().y() - gauge_size / 2,
            gauge_size,
            gauge_size
        )
        
        # Fetch all gauge-related colors, factoring in alert state
        gauge_background_color = self._get_themed_color('gauge_background_normal', '#1A2A40') 
        gauge_border_color = self._get_themed_color('gauge_border_normal', '#3C6595') 
        gauge_fill_color = self._get_themed_color('gauge_fill_normal', '#87CEEB') 
        gauge_warning_color = self._get_themed_color('gauge_warning_color', '#FFA500') 
        gauge_critical_color = self._get_themed_color('gauge_critical_color', '#FF0000') 
        gauge_value_text_color = self._get_themed_color('gauge_text_normal', '#E0F2F7') 
        gauge_text_outline_color = self._get_themed_color('gauge_text_outline_color', '#000000') 
        high_contrast_text_color = self._get_themed_color('gauge_high_contrast_text_color', '#FFFFFF') 

        analog_bg_color = self._get_themed_color("analog_gauge_background", gauge_background_color.name())
        analog_border_color = self._get_themed_color("analog_gauge_border", gauge_border_color.name())
        analog_scale_color = self._get_themed_color("analog_gauge_scale_color", gauge_fill_color.name())
        analog_needle_color = self._get_themed_color("analog_gauge_needle_color", "#4682B4")
        analog_center_dot_color = self._get_themed_color("analog_gauge_center_dot_color", "#4682B4")
        analog_text_color = self._get_themed_color("analog_gauge_text_color", gauge_value_text_color.name())

        digital_gauge_font_color = self._get_themed_color('digital_gauge_font_color', gauge_value_text_color.name())
        digital_gauge_bg_color = self._get_themed_color('digital_gauge_bg_color', gauge_background_color.darker(150).name())
        digital_gauge_border_color = self._get_themed_color('digital_gauge_border_color', gauge_border_color.name())

        if self._is_alert:
            gauge_background_color = self._get_themed_color('gauge_background_alert', '#5C2D2D')
            gauge_border_color = self._get_themed_color('gauge_border_alert', '#FF6666')
            gauge_fill_color = self._get_themed_color('gauge_fill_alert', '#FF0000')
            gauge_value_text_color = self._get_themed_color('gauge_text_alert', '#FFD700')
            
            analog_bg_color = self._get_themed_color('analog_gauge_background_alert', gauge_background_color.name()) 
            analog_border_color = self._get_themed_color('analog_gauge_border_alert', gauge_border_color.name())
            analog_scale_color = self._get_themed_color('analog_gauge_scale_alert_color', gauge_fill_color.name())
            analog_needle_color = self._get_themed_color('analog_gauge_needle_alert_color', '#FF0000') 
            analog_center_dot_color = self._get_themed_color('analog_gauge_center_dot_alert_color', '#FF0000')
            analog_text_color = self._get_themed_color('analog_gauge_text_alert_color', '#FFD700')
            
            digital_gauge_font_color = self._get_themed_color('digital_gauge_font_alert_color', gauge_value_text_color.name())
            digital_gauge_bg_color = self._get_themed_color('digital_gauge_bg_alert_color', gauge_background_color.name())
            digital_gauge_border_color = self._get_themed_color('digital_gauge_border_alert_color', gauge_border_color.name())

            logger.debug("  paintEvent: Alert state active, overriding gauge colors.")


        # Draw the appropriate gauge type
        if self.current_gauge_type == "Type 1 (Standard)":
            self._draw_standard_gauge(painter, gauge_rect, gauge_background_color, gauge_border_color, gauge_fill_color, gauge_value_text_color, gauge_text_outline_color, high_contrast_text_color)
        elif self.current_gauge_type == "Type 2 (Compact)":
            self._draw_compact_gauge(painter, gauge_rect, gauge_background_color, gauge_border_color, gauge_fill_color, gauge_value_text_color, gauge_text_outline_color, high_contrast_text_color)
        elif self.current_gauge_type == "Type 3 (Digital)":
            # Digital gauge relies on QLabel's QSS, but we can draw an overlay background
            self._draw_digital_gauge_overlay(painter, gauge_rect, digital_gauge_bg_color, digital_gauge_border_color)
        elif self.current_gauge_type == "Type 4 (Analog - Basic)":
            self._draw_analog_gauge_basic(painter, gauge_rect, analog_bg_color, analog_border_color, analog_scale_color, analog_needle_color, analog_center_dot_color, analog_text_color, gauge_text_outline_color) 
        elif self.current_gauge_type == "Type 5 (Analog - Full)":
            self._draw_analog_gauge_full(painter, gauge_rect, analog_bg_color, analog_border_color, analog_scale_color, analog_needle_color, analog_center_dot_color, analog_text_color, gauge_text_outline_color) 
        elif self.current_gauge_type in ["Type 6 (Progress Bar - Horizontal)", "Type 7 (Progress Bar - Vertical)"]:
            # For Progress Bars, native QProgressBar handles fill and text (setTextVisible(True))
            # We just draw the custom threshold lines on top.
            is_horizontal = (self.current_gauge_type == "Type 6 (Progress Bar - Horizontal)")
            self._draw_progress_bar_threshold_lines(painter, self.progressBar.geometry(), is_horizontal, gauge_critical_color)
            
            # --- CRITICAL FIX: Custom text drawing for vertical progress bar ---
            if self.current_gauge_type == "Type 7 (Progress Bar - Vertical)":
                self._draw_progress_bar_text_overlay(painter, self.progressBar.geometry(), Qt.Vertical)
            # No else: for horizontal, native text is used (setTextVisible(True) handled in update_value)

        else:
            logger.warning(f"SensorDisplayWidget: Unknown gauge type '{self.current_gauge_type}'. Drawing fallback text.")
            self._draw_fallback_gauge(painter, gauge_rect, gauge_background_color, gauge_border_color, gauge_value_text_color) 

        painter.end() 
        logger.debug(f"SensorDisplayWidget: paintEvent finished for {self.objectName()}.")

    def _extract_border_properties_from_qss_string(self, border_string, default_width=1, default_style=Qt.SolidLine, default_color_str="#000000"):
        """
        Helper to parse a QSS border string like "1px solid #FF00FF" into width, style, and QColor.
        """
        width = default_width
        style = default_style
        color = QColor(default_color_str) # Default to black if parsing fails

        # Regex to capture width, style keyword, and color (hex or named)
        # It needs to be flexible for color part, as it can be #HEX or a name.
        match = re.match(r'(\d+)(px)?\s+(solid|dashed|dotted|double|groove|ridge|inset|outset)\s+([^;]+)', border_string, re.IGNORECASE)
        if match:
            try:
                width = int(match.group(1))
                style_str = match.group(3).lower()
                color_str = match.group(4).strip()
                
                if style_str == "solid": style = Qt.SolidLine
                elif style_str == "dashed": style = Qt.DashLine
                elif style_str == "dotted": style = Qt.DotLine
                elif style_str == "double": style = Qt.DoubleDashLine 
                elif style_str == "groove": style = Qt.NoPen 
                elif style_str == "ridge": style = Qt.NoPen
                elif style_str == "inset": style = Qt.NoPen
                elif style_str == "outset": style = Qt.NoPen

                # Try to convert color_str to QColor
                try:
                    color = QColor(color_str)
                except Exception as e:
                    logger.warning(f"  _extract_border_properties_from_qss_string: Could not convert border color string '{color_str}' to QColor. Error: {e}. Using default.", exc_info=True)
                    color = QColor(default_color_str)

                logger.debug(f"  _extract_border_properties_from_qss_string: Parsed border: Width={width}, Style={style_str}, Color={color.name()}.")
            except Exception as e:
                logger.warning(f"  _extract_border_properties_from_qss_string: Error parsing border string '{border_string}': {e}. Using defaults.", exc_info=True)
        else:
            # If the string doesn't match the full pattern, try to parse it as just a color (for backward compatibility)
            try:
                color = QColor(border_string)
                logger.debug(f"  _extract_border_properties_from_qss_string: Border string '{border_string}' treated as just a color. Using default width/style.")
            except Exception as e:
                logger.warning(f"  _extract_border_properties_from_qss_string: Border string '{border_string}' did not match regex and is not a direct color. Using full defaults. Error: {e}", exc_info=True)

        return width, style, color

    def _get_themed_color(self, key, default_value):
        """
        Helper method to retrieve a QColor from the theme_colors dictionary.
        Handles cases where the key might be missing or the value is not a valid color.
        Also resolves specific overrides (e.g., analog gauge text color).
        """
        color_data = self.theme_colors.get(key)
        
        # Special handling for font families, which are strings, not colors
        if "font_family" in key:
            return color_data # Return string directly for font families

        if key == 'gauge_text_normal' and 'analog_gauge_text_color' in self.theme_colors:
            if self.current_gauge_type in ["Type 4 (Analog - Basic)", "Type 5 (Analog - Full)"]:
                 pass # No change needed here, as the drawing functions get the correct themed color.


        # Handling for border properties which might contain full strings like "1px solid #HEX"
        # We expect these to be returned as strings by parse_qss_for_colors, so we don't try to convert them to QColor here
        if key in ['groupbox_border', 'progressbar_border', 'groupbox_border_radius', 'progressbar_border_radius']:
            # If the value for these keys is found and is a string, return it as-is
            if color_data is not None and isinstance(color_data, str):
                return color_data
            # Otherwise, use the default string value for this property
            return default_value # This default_value should also be a string for these keys

        if color_data:
            try:
                # QColor constructor can handle hex, named colors (e.g., "red"), or rgba strings.
                return QColor(color_data)
            except Exception as e:
                logger.error(f"      _get_themed_color: Error converting theme color '{color_data}' for key '{key}': {e}. Using default_value.", exc_info=True)
        else:
            logger.debug(f"      _get_themed_color: Key '{key}' not found in theme_colors. Using default_value: '{default_value}'.")

        # If color_str was not found or conversion failed, use the default_value
        if isinstance(default_value, QColor):
            return default_value
        else:
            try:
                return QColor(default_value)
            except Exception as e:
                logger.error(f"      _get_themed_color: Fallback error converting default_value '{default_value}' to QColor for key '{key}': {e}. Using a hardcoded black.", exc_info=True)
                return QColor("#000000") # Final fallback to black

    def _get_themed_font_family(self, key, default_family='Inter'):
        """Retrieves a font family name from theme_colors."""
        font_family_name = self.theme_colors.get(key, default_family)
        if not isinstance(font_family_name, str):
            logger.warning(f"  _get_themed_font_family: Expected string for font family key '{key}', got {type(font_family_name)}. Using default: '{default_family}'.")
            return default_family
        return font_family_name

    def _draw_standard_gauge(self, painter, rect, bg_color, border_color, value_color, text_color, text_outline_color, high_contrast_text_color):
        logger.debug(f"  Drawing Standard Gauge for {self.objectName()}. Value: {self._value}")
        painter.save()
        
        # Outer circle background
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 2))
        painter.drawEllipse(rect)

        if self._value is not None and not self._is_na:
            # Calculate fill percentage
            if self._max_value - self._min_value != 0:
                percentage = (self._value - self._min_value) / (self._max_value - self._min_value)
            else:
                percentage = 0 # Avoid division by zero
            percentage = max(0.0, min(1.0, percentage)) # Clamp between 0 and 1

            # Draw filled arc
            start_angle = 90 * 16 # Start from top (12 o'clock)
            span_angle = -int(percentage * 360 * 16) # Fill clockwise

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(value_color))
            painter.drawPie(rect, start_angle, span_angle)

            # Draw value text
            self._draw_value_text(painter, rect, self._value, self.unit, text_color, text_outline_color, high_contrast_text_color, QFont(self.theme_colors.get('font_family', "Inter"), int(rect.width() / 8))) # Smaller font for standard
        else:
            self._draw_na_text(painter, rect, text_color, QFont(self.theme_colors.get('font_family', "Inter"), int(rect.width() / 8)))

        painter.restore()

    def _draw_compact_gauge(self, painter, rect, bg_color, border_color, value_color, text_color, text_outline_color, high_contrast_text_color):
        logger.debug(f"  Drawing Compact Gauge for {self.objectName()}. Value: {self._value}")
        painter.save()

        # Background rectangle
        rounded_rect = rect.adjusted(rect.width() * 0.1, rect.height() * 0.3, -rect.width() * 0.1, -rect.height() * 0.3)
        radius = rounded_rect.height() / 2
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 2))
        painter.drawRoundedRect(rounded_rect, radius, radius)

        if self._value is not None and not self._is_na:
            # Calculate fill width
            if self._max_value - self._min_value != 0:
                fill_ratio = (self._value - self._min_value) / (self._max_value - self._min_value)
            else:
                fill_ratio = 0
            fill_ratio = max(0.0, min(1.0, fill_ratio))
            
            fill_width = rounded_rect.width() * fill_ratio
            fill_rect = QRectF(rounded_rect.left(), rounded_rect.top(), fill_width, rounded_rect.height())

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(value_color))
            # Draw a rounded rectangle for the filled portion
            painter.drawRoundedRect(fill_rect, radius, radius)

            # Draw value text
            self._draw_value_text(painter, rounded_rect, self._value, self.unit, text_color, text_outline_color, high_contrast_text_color, QFont(self.theme_colors.get('font_family', "Inter"), int(rect.width() / 7)))
        else:
            self._draw_na_text(painter, rounded_rect, text_color, QFont(self.theme_colors.get('font_family', "Inter"), int(rect.width() / 7)))

        painter.restore()

    def _draw_digital_gauge_overlay(self, painter, rect, bg_color, border_color): # Removed text_color, handled by QLabel
        """
        Draws a digital display-like overlay background. The actual value text is handled by QLabel
        but this provides a background aesthetic.
        """
        logger.debug(f"  Drawing Digital Gauge Overlay for {self.objectName()}.")
        painter.save()

        # Background rectangle with digital aesthetic
        bg_rect = rect.adjusted(rect.width() * 0.05, rect.height() * 0.25, -rect.width() * 0.05, -rect.height() * 0.25)
        
        painter.setBrush(QBrush(bg_color)) # Use themed digital_gauge_bg_color
        painter.setPen(QPen(border_color, 2)) # Use themed digital_gauge_border_color
        painter.drawRoundedRect(bg_rect, 5, 5)

        # "Digital" light segments effect (optional, simplified)
        # Use a slightly darker shade of the background color for the segments
        seg_color = bg_color.darker(120) 
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(seg_color))
        # Draw some horizontal lines or dots to give segmented look
        for i in range(3):
            painter.drawRect(bg_rect.x() + 5, bg_rect.y() + bg_rect.height()/4 * (i+1) - 2, bg_rect.width() - 10, 4)

        painter.restore()

    def _draw_analog_gauge_basic(self, painter, rect, bg_color, border_color, scale_color, needle_color, center_dot_color, text_color, text_outline_color): 
        """
        Draws a basic analog gauge with a fixed 270-degree arc, needle, and value text.
        """
        logger.debug(f"  Drawing Analog Gauge (Basic) for {self.objectName()}. Value: {self._value}")
        painter.save()

        center_x = rect.center().x()
        center_y = rect.center().y()
        radius = min(rect.width(), rect.height()) / 2 * 0.9 # Inner radius for drawing

        # 1. Gauge Background Arc
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 2))
        
        start_angle_deg = 225 # Bottom-left
        end_angle_deg = -45 # Bottom-right (equivalent to 315)
        total_span_deg = (end_angle_deg - start_angle_deg) # Should be -270 degrees for clockwise
        # If using drawPie, it interprets negative span as clockwise.
        # If we want 270 degrees clockwise, it's 225 to (225-270) = -45. So span is -270.
        
        painter.drawPie(rect, start_angle_deg * 16, total_span_deg * 16) # Draw background arc
        logger.debug(f"  Analog Gauge Basic: Background arc drawn from {start_angle_deg} to {end_angle_deg} degrees (span {total_span_deg}).")


        # 2. Scale Markings and Value-Based Fill (Simplified)
        if self._value is not None and not self._is_na:
            # Calculate value's position on the scale (0 to 1 ratio)
            if (self._max_value - self._min_value) != 0:
                value_ratio = (self._value - self._min_value) / (self._max_value - self._min_value)
            else:
                value_ratio = 0.5 # Default to middle if range is zero
            value_ratio = max(0.0, min(1.0, value_ratio)) # Clamp between 0 and 1

            # The span for the fill should be proportional to the value ratio * total_span_deg
            fill_span_deg = value_ratio * total_span_deg 
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(scale_color)) # Use scale_color for the active range fill
            painter.drawPie(rect, start_angle_deg * 16, int(fill_span_deg * 16)) # Convert to 16ths of degree
            logger.debug(f"  Analog Gauge Basic: Filled arc drawn to value ratio {value_ratio:.2f} with color {scale_color.name()}.")

        # 3. Draw Needle (only if value is not None)
        if self._value is not None and not self._is_na:
            # Map the value to an angle
            if (self._max_value - self._min_value) != 0:
                normalized_value = (self._value - self._min_value) / (self._max_value - self._min_value)
            else:
                normalized_value = 0.5 # Default to middle if range is zero or invalid
            normalized_value = max(0.0, min(1.0, normalized_value)) # Clamp to [0, 1]

            # Calculate needle angle relative to start_angle_deg and total_span_deg
            # For clockwise rotation, add a negative angle
            needle_angle_deg = start_angle_deg + (normalized_value * total_span_deg)
            needle_angle_rad = math.radians(needle_angle_deg)
            
            needle_length = radius * 0.8 # Length of the needle
            
            # Tip of the needle
            tip_x = center_x + needle_length * math.cos(needle_angle_rad)
            tip_y = center_y + needle_length * math.sin(needle_angle_rad)
            
            painter.setPen(QPen(needle_color, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)) # Thicker, rounded line
            painter.drawLine(QPointF(center_x, center_y), QPointF(tip_x, tip_y))
            
            # Draw a simple arrowhead
            arrow_size = radius * 0.08
            # Angles for arrowhead points relative to needle direction
            # Arrowhead should be pointed towards the tip of the needle.
            # Calculate points offset from the tip, perpendicular to the needle line.
            
            # Angle perpendicular to needle: needle_angle_rad +/- pi/2
            perp_angle1 = needle_angle_rad + math.radians(90)
            perp_angle2 = needle_angle_rad - math.radians(90)

            # Base points of the arrowhead (behind the tip)
            base_x1 = tip_x - arrow_size * math.cos(perp_angle1)
            base_y1 = tip_y - arrow_size * math.sin(perp_angle1)
            base_x2 = tip_x - arrow_size * math.cos(perp_angle2)
            base_y2 = tip_y - arrow_size * math.sin(perp_angle2)
            
            arrow_path = QPainterPath()
            arrow_path.moveTo(tip_x, tip_y) # Tip of the arrow
            arrow_path.lineTo(base_x1, base_y1)
            arrow_path.lineTo(base_x2, base_y2)
            arrow_path.closeSubpath() # Close to form triangle
            
            painter.setBrush(QBrush(needle_color))
            painter.setPen(Qt.NoPen)
            painter.drawPath(arrow_path)

            # Draw a small circle at the pivot
            painter.setBrush(QBrush(center_dot_color))
            painter.setPen(QPen(center_dot_color.darker(150), 1))
            painter.drawEllipse(QPointF(center_x, center_y), radius * 0.1, radius * 0.1)
            logger.debug(f"  Analog Gauge Basic: Needle drawn. Value: {self._value}, Angle: {needle_angle_deg:.2f} deg.")
        else:
            logger.debug("  Analog Gauge Basic: Value is None. Skipping needle drawing.")

        # 4. Draw Value Text (overlayed in the center)
        # Use _draw_value_text helper
        self._draw_value_text(painter, 
                              # Adjusted rect for text position (slightly below center of gauge)
                              rect.adjusted(rect.width() * 0.2, rect.height() * 0.6, -rect.width() * 0.2, -rect.height() * 0.1), 
                              self._value, self.unit, text_color, text_outline_color, 
                              self._get_themed_color('gauge_high_contrast_text_color', '#FFFFFF'), 
                              QFont(self._get_themed_font_family('font_family', "Inter"), int(radius / 3.5), QFont.Bold))

        painter.restore()

    def _draw_analog_gauge_full(self, painter, rect, bg_color, border_color, scale_color, needle_color, center_dot_color, text_color, text_outline_color): 
        """
        Draws a full analog gauge with a fixed 270-degree arc, needle, and value text.
        """
        logger.debug(f"  Drawing Analog Gauge (Full) for {self.objectName()}. Value: {self._value}")
        painter.save()

        center_x = rect.center().x()
        center_y = rect.center().y()
        radius = min(rect.width(), rect.height()) / 2 * 0.9 

        # 1. Gauge Background Circle
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 2))
        painter.drawEllipse(QPointF(center_x, center_y), radius, radius)

        # Define start and end angles for the active range of the gauge (e.g., 225 to -45 degrees)
        start_angle_deg = 225
        end_angle_deg = -45 
        total_span_deg = (end_angle_deg - start_angle_deg) # Should be -270 degrees for clockwise sweep

        if self._value is not None and not self._is_na:
            # Calculate value's position on the scale (0 to 1 ratio)
            if (self._max_value - self._min_value) != 0:
                value_ratio = (self._value - self._min_value) / (self._max_value - self._min_value)
            else:
                value_ratio = 0.5 
            value_ratio = max(0.0, min(1.0, value_ratio)) 

            # The span for the fill should be proportional to the value ratio * total_span_deg
            fill_span_deg = value_ratio * total_span_deg 
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(scale_color)) # Use fill color for the active range
            # Draw the arc from start_angle_deg to current_angle_deg
            painter.drawPie(rect, start_angle_deg * 16, int(fill_span_deg * 16))
            logger.debug(f"  Analog Gauge Full: Filled arc from {start_angle_deg} to {start_angle_deg + fill_span_deg} degrees.")

        # 2. Scale Markings and Labels
        painter.setPen(QPen(self._get_themed_color('analog_gauge_scale_color', '#304050'), 1)) 
        scale_font = QFont(self.theme_colors.get('font_family', "Inter"), int(radius / 8))
        painter.setFont(scale_font)

        num_ticks = 11 # 0, 10, 20, ..., 100 for a 0-100 range
        for i in range(num_ticks):
            # Calculate tick value proportionally across the actual min-max range
            tick_value = self._min_value + (self._max_value - self._min_value) * (i / (num_ticks - 1))
            
            # Calculate angle for this tick, based on total_span_deg
            tick_angle_deg = start_angle_deg + (i / (num_ticks - 1)) * total_span_deg

            # Convert angle to radians for trigonometry
            angle_rad = math.radians(tick_angle_deg)
            
            # Position for tick marks
            outer_x = center_x + radius * math.cos(angle_rad)
            outer_y = center_y + radius * math.sin(angle_rad)
            inner_x = center_x + (radius * 0.9) * math.cos(angle_rad) # Shorter inner tick
            inner_y = center_y + (radius * 0.9) * math.sin(angle_rad)

            painter.drawLine(QPointF(outer_x, outer_y), QPointF(inner_x, inner_y))

            # Position for text labels (further in from the ticks)
            text_x_base = center_x + (radius * 0.75) * math.cos(angle_rad)
            text_y_base = center_y + (radius * 0.75) * math.sin(angle_rad)
            
            # Adjust text position for readability (e.g., center text on tick)
            text_rect_size = radius / 3.5 
            text_rect = QRectF(text_x_base - text_rect_size / 2, text_y_base - text_rect_size / 2, text_rect_size, text_rect_size)
            
            # Format tick value with appropriate precision
            precision = self.main_window.settings_manager.get_setting(f'Precision_{self.sensor_category}', self.metric_type, type=int, default=0)
            formatted_tick_value = f"{tick_value:.{precision}f}"

            # Dynamically adjust text alignment to point outwards
            text_flags = Qt.AlignCenter
            # More refined alignment based on angle
            if (tick_angle_deg > 180 and tick_angle_deg < 270): # Bottom-left quadrant
                text_flags = Qt.AlignRight | Qt.AlignVCenter
            elif (tick_angle_deg >= 270 and tick_angle_deg < 360) or (tick_angle_deg >= -90 and tick_angle_deg < 0): # Bottom-right quadrant (including -45 for end)
                text_flags = Qt.AlignLeft | Qt.AlignVCenter
            elif (tick_angle_deg == 0 or tick_angle_deg == 360): # Rightmost point
                text_flags = Qt.AlignLeft | Qt.AlignVCenter
            elif (tick_angle_deg > 0 and tick_angle_deg < 90): # Top-right
                text_flags = Qt.AlignLeft | Qt.AlignVCenter
            elif (tick_angle_deg >= 90 and tick_angle_deg < 180): # Top-left
                text_flags = Qt.AlignRight | Qt.AlignVCenter
            
                
            painter.setPen(QPen(self._get_themed_color('analog_gauge_label_color', '#304050')))
            painter.drawText(text_rect, text_flags, formatted_tick_value)

        # 3. Draw Needle (only if value is not None)
        if self._value is not None and not self._is_na:
            # Map the value to an angle
            if (self._max_value - self._min_value) != 0:
                normalized_value = (self._value - self._min_value) / (self._max_value - self._min_value)
            else:
                normalized_value = 0.5 
            normalized_value = max(0.0, min(1.0, normalized_value)) 

            needle_angle_deg = start_angle_deg + (normalized_value * total_span_deg)
            needle_angle_rad = math.radians(needle_angle_deg)
            
            needle_length = radius * 0.8 
            
            # Needle shape (simple line with arrowhead)
            tip_x = center_x + needle_length * math.cos(needle_angle_rad)
            tip_y = center_y + needle_length * math.sin(needle_angle_rad)
            
            painter.setPen(QPen(needle_color, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)) 
            painter.drawLine(QPointF(center_x, center_y), QPointF(tip_x, tip_y))
            
            # Draw a simple arrowhead
            arrow_size = radius * 0.08
            # Calculate points offset from the tip, perpendicular to the needle line.
            perp_angle1 = needle_angle_rad + math.radians(90)
            perp_angle2 = needle_angle_rad - math.radians(90)
            
            base_x1 = tip_x - arrow_size * math.cos(perp_angle1)
            base_y1 = tip_y - arrow_size * math.sin(perp_angle1)
            base_x2 = tip_x - arrow_size * math.cos(perp_angle2)
            base_y2 = tip_y - arrow_size * math.sin(perp_angle2)
            
            arrow_path = QPainterPath()
            arrow_path.moveTo(tip_x, tip_y)
            arrow_path.lineTo(base_x1, base_y1)
            arrow_path.lineTo(base_x2, base_y2)
            arrow_path.closeSubpath()
            
            painter.setBrush(QBrush(needle_color))
            painter.setPen(Qt.NoPen)
            painter.drawPath(arrow_path)

            painter.setBrush(QBrush(center_dot_color))
            painter.setPen(QPen(center_dot_color.darker(150), 1))
            painter.drawEllipse(QPointF(center_x, center_y), radius * 0.1, radius * 0.1)
            logger.debug(f"  Analog Gauge Full: Needle drawn. Value: {self._value}, Angle: {needle_angle_deg:.2f} deg.")
        else:
            logger.debug("  Analog Gauge Full: Value is None. Skipping needle drawing.")

        # 5. Draw Value Text (overlayed in the center)
        self._draw_value_text(painter, 
                              rect.adjusted(rect.width() * 0.2, rect.height() * 0.6, -rect.width() * 0.2, -rect.height() * 0.1), # Smaller rect for text
                              self._value, self.unit, text_color, text_outline_color, 
                              self._get_themed_color('gauge_high_contrast_text_color', '#FFFFFF'), # Consistent high contrast
                              QFont(self._get_themed_font_family('font_family', "Inter"), int(radius / 3.5), QFont.Bold))

        painter.restore()

    def _draw_progress_bar_threshold_lines(self, painter, bar_rect, orientation, line_color):
        """
        Draws threshold lines on top of the QProgressBar.
        :param painter: QPainter instance.
        :param bar_rect: The rectangle occupied by the QProgressBar (in parent coordinates).
        :param orientation: Qt.Horizontal or Qt.Vertical.
        :param line_color: QColor for the threshold lines.
        """
        logger.debug(f"  _draw_progress_bar_threshold_lines called for {self.objectName()}.")
        logger.debug(f"  Bar Rect: {bar_rect.x()}, {bar_rect.y()}, {bar_rect.width()}, {bar_rect.height()}")
        painter.save()
        painter.setPen(QPen(line_color, 2, Qt.DotLine)) # Use the critical color for dotted threshold lines

        low_thr = self.thresholds.get('low')
        high_thr = self.thresholds.get('high')

        if low_thr is None and high_thr is None:
            logger.debug(f"  _draw_progress_bar_threshold_lines: No thresholds defined for {self.objectName()}. Skipping drawing threshold lines.")
            painter.restore()
            return

        # Ensure valid range to prevent division by zero or incorrect scaling
        if (self._max_value - self._min_value) == 0:
            logger.warning(f"  _draw_progress_bar_threshold_lines: Min and Max values are identical for {self.objectName()}. Cannot draw thresholds correctly.")
            painter.restore()
            return

        # Define a helper to map a sensor value to a normalized position (0.0 to 1.0)
        def value_to_normalized_pos(value, min_val, max_val):
            if max_val == min_val: return 0.0 # Avoid div by zero
            return (value - min_val) / (max_val - min_val)

        if orientation == Qt.Vertical:
            # Vertical progress bar: fill goes from bottom (min value) to top (max value).
            # Y-coordinates increase downwards. So, higher values are at lower Y screen positions.
            
            if low_thr is not None:
                # Calculate the normalized position of the low threshold
                low_thr_norm_pos = value_to_normalized_pos(low_thr, self._min_value, self._max_value)
                # Map to Y-coordinate: top of bar + (1 - normalized_pos) * bar_height
                # (1 - normalized_pos) because 0.0 is bottom, 1.0 is top visually (reversed Y-axis)
                y_pos_low = bar_rect.top() + (1.0 - low_thr_norm_pos) * bar_rect.height()
                painter.drawLine(bar_rect.left(), int(y_pos_low), bar_rect.right(), int(y_pos_low))
                logger.debug(f"  _draw_progress_bar_threshold_lines: Drawn low threshold line at ({bar_rect.left():.1f}, {y_pos_low:.1f}) to ({bar_rect.right():.1f}, {y_pos_low:.1f}) for {self.objectName()}. Value: {low_thr}.")

            if high_thr is not None:
                high_thr_norm_pos = value_to_normalized_pos(high_thr, self._min_value, self._max_value)
                y_pos_high = bar_rect.top() + (1.0 - high_thr_norm_pos) * bar_rect.height()
                painter.drawLine(bar_rect.left(), int(y_pos_high), bar_rect.right(), int(y_pos_high))
                logger.debug(f"  _draw_progress_bar_threshold_lines: Drawn high threshold line at ({bar_rect.left():.1f}, {y_pos_high:.1f}) to ({bar_rect.right():.1f}, {y_pos_high:.1f}) for {self.objectName()}. Value: {high_thr}.")

        else: # Horizontal orientation
            # Horizontal progress bar: fill goes from left (min value) to right (max value).
            # X-coordinates increase to the right.
            
            if low_thr is not None:
                low_thr_norm_pos = value_to_normalized_pos(low_thr, self._min_value, self._max_value)
                x_pos_low = bar_rect.left() + low_thr_norm_pos * bar_rect.width()
                painter.drawLine(int(x_pos_low), bar_rect.top(), int(x_pos_low), bar_rect.bottom())
                logger.debug(f"  _draw_progress_bar_threshold_lines: Drawn low threshold line at ({x_pos_low:.1f}, {bar_rect.top():.1f}) to ({x_pos_low:.1f}, {bar_rect.bottom():.1f}) for {self.objectName()}. Value: {low_thr}.")

            if high_thr is not None:
                high_thr_norm_pos = value_to_normalized_pos(high_thr, self._min_value, self._max_value)
                x_pos_high = bar_rect.left() + high_thr_norm_pos * bar_rect.width()
                painter.drawLine(int(x_pos_high), bar_rect.top(), int(x_pos_high), bar_rect.bottom())
                logger.debug(f"  _draw_progress_bar_threshold_lines: Drawn high threshold line at ({x_pos_high:.1f}, {bar_rect.top():.1f}) to ({x_pos_high:.1f}, {bar_rect.bottom():.1f}) for {self.objectName()}. Value: {high_thr}.")
        
        painter.restore()
        logger.debug(f"  _draw_progress_bar_threshold_lines: Threshold lines drawing complete for {self.objectName()}.")


    def _draw_progress_bar_text_overlay(self, painter, bar_rect, orientation):
        """
        Draws the value text as an overlay on a QProgressBar.
        The text changes color based on whether it's over the "filled" or "unfilled" portion.
        For vertical orientation, the text is rotated.
        Includes conditional font size adjustment for pressure.
        """
        logger.debug(f"  Drawing Progress Bar Text Overlay. Value: {self._value}, Orientation: {orientation}")
        painter.save()

        if self._value is None or self._is_na:
            self._draw_na_text(painter, bar_rect, self._get_themed_color('label_color', 'white'), 
                               QFont(self.theme_colors.get('font_family', "Inter"), int(min(bar_rect.width(), bar_rect.height()) * 0.5)))
            painter.restore()
            return

        precision_setting = self.main_window.settings_manager.get_setting(
            f'Precision_{self.sensor_category}', self.metric_type, type=int, default=2
        )
        formatted_value = f"{self._value:.{precision_setting}f}{self.unit}"
        
        # Base font size calculation
        font_size = int(min(bar_rect.width(), bar_rect.height()) * 0.5) 

        # Conditional font size adjustment for Pressure (and potentially other long values)
        if self.metric_type.lower() == 'pressure' or len(formatted_value) > 7: # Adjust for long values
            temp_font = QFont(self.theme_colors.get('font_family', "Inter"), font_size, QFont.Bold)
            temp_metrics = QFontMetrics(temp_font)
            text_width_at_current_font = temp_metrics.horizontalAdvance(formatted_value)
            
            # For vertical bar, effectively the text width is compared to bar's height (when text is rotated)
            # For horizontal bar, text width is compared to bar's width
            available_length = bar_rect.height() if orientation == Qt.Vertical else bar_rect.width()
            
            if text_width_at_current_font > available_length * 0.9: 
                font_size = int(font_size * (available_length * 0.8 / text_width_at_current_font))
                font_size = max(8, font_size) 
                logger.debug(f"  Text font size adjusted for {formatted_value}. New size: {font_size}.")

        font = QFont(self.theme_colors.get('font_family', "Inter"), font_size, QFont.Bold)
        painter.setFont(font)
        
        metrics = painter.fontMetrics()
        text_bounds_width = metrics.horizontalAdvance(formatted_value)
        text_bounds_height = metrics.height()

        # 1. Determine the "fill" point of the progress bar
        normalized_value = 0.0
        if self._max_value - self._min_value != 0:
            normalized_value = (self._value - self._min_value) / (self._max_value - self._min_value)
        normalized_value = max(0.0, min(1.0, normalized_value)) 

        fill_length = 0
        text_display_rect_rotated = QRectF() # This will be the rect in the transformed space
        
        if orientation == Qt.Horizontal:
            fill_length = bar_rect.width() * normalized_value
            text_display_rect_rotated = QRectF(
                bar_rect.x() + (bar_rect.width() - text_bounds_width) / 2,
                bar_rect.y() + (bar_rect.height() - text_bounds_height) / 2,
                text_bounds_width,
                text_bounds_height
            )
        else: # Vertical
            fill_length = bar_rect.height() * normalized_value
            
            # Translate to the center of the bar_rect for rotation
            painter.translate(bar_rect.center())
            painter.rotate(-90) # Rotate -90 degrees (counter-clockwise)
            
            text_display_rect_rotated = QRectF(
                -text_bounds_width / 2,
                -text_bounds_height / 2,
                text_bounds_width,
                text_bounds_height
            )
            logger.debug(f"  Text Display Rect (after rotation prep): {text_display_rect_rotated}.")


        # 2. Get the theme colors for filled and unfilled text
        text_color_unfilled = self._get_themed_color('progressbar_text_color', '#E0F2F7') 
        # For text over the filled part, dynamically choose based on chunk color contrast
        chunk_color_qcolor = QColor(self._get_themed_color('progressbar_chunk_color', '#87CEEB').name()) 
        if self._is_alert:
            chunk_color_qcolor = QColor(self._get_themed_color('progressbar_chunk_alert_color', '#FF0000').name()) 

        luminance = (0.299 * chunk_color_qcolor.red() + 
                     0.587 * chunk_color_qcolor.green() + 
                     0.114 * chunk_color_qcolor.blue())
        
        # Decide text color based on luminance
        if luminance > 180: # If background is bright, use a dark text color
            text_color_filled = QColor("#000000") 
            outline_color_for_text = QColor("#FFFFFF") 
        else: # If background is dark, use a light text color
            text_color_filled = QColor("#FFFFFF") 
            outline_color_for_text = QColor("#000000") 
        
        logger.debug(f"  Chunk color: {chunk_color_qcolor.name()}, Luminance: {luminance:.1f}. Text over chunk color set to: {text_color_filled.name()}. Outline: {outline_color_for_text.name()}.")


        # 3. Create a QPainterPath for the text itself
        text_path = QPainterPath()
        text_path.addText(text_display_rect_rotated.topLeft() + QPointF(0, metrics.ascent()), font, formatted_value)
        
        # 4. Draw the outline of the text
        painter.setPen(QPen(outline_color_for_text, 2))
        painter.setBrush(Qt.NoBrush) 
        painter.drawPath(text_path)
        logging.debug(f"  Text outline drawn with color {outline_color_for_text.name()}.")

        # 5. Draw the text (actual text color) with two clips for dual colors
        # Define clip paths in the *painter's current coordinate system* (which might be rotated)
        
        filled_clip_path = QPainterPath()
        unfilled_clip_path = QPainterPath()

        if orientation == Qt.Horizontal:
            filled_rect_clip = QRectF(bar_rect.x(), bar_rect.y(), fill_length, bar_rect.height())
            filled_clip_path.addRect(filled_rect_clip) 
            
            unfilled_rect_clip = QRectF(bar_rect.x() + fill_length, bar_rect.y(), bar_rect.width() - fill_length, bar_rect.height())
            unfilled_clip_path.addRect(unfilled_rect_clip)
        else: # Vertical, in the rotated coordinate system of the painter
            # The "bar_rect" here is the *original* bar_rect.
            # In the rotated coordinate system, the bar is effectively horizontal.
            # Its "width" is original bar_rect.height(), its "height" is original bar_rect.width().
            
            # filled_rect_clip in rotated space:
            # x_start: - (bar_rect.height() / 2) # Left edge of the rotated bar
            # y_start: - (bar_rect.width() / 2)  # Top edge of the rotated bar
            # width: fill_length # The amount filled along the rotated X-axis
            # height: bar_rect.width() # The full height of the rotated bar
            
            filled_rect_clip = QRectF(
                -bar_rect.height() / 2, # x start
                -bar_rect.width() / 2,  # y start
                fill_length,            # width
                bar_rect.width()        # height
            )
            filled_clip_path.addRect(filled_rect_clip)

            unfilled_rect_clip = QRectF(
                -bar_rect.height() / 2 + fill_length, # x start (from where fill ends)
                -bar_rect.width() / 2,                # y start
                bar_rect.height() - fill_length,      # width
                bar_rect.width()                      # height
            )
            unfilled_clip_path.addRect(unfilled_rect_clip)
        
        # Combine text path and filled area clip path
        combined_clip_path_filled = filled_clip_path.intersected(text_path)
        painter.setClipPath(combined_clip_path_filled)
        
        # Draw the text with the dynamically chosen contrasting color for the filled part
        painter.setPen(QPen(text_color_filled, 1)) 
        painter.setBrush(QBrush(text_color_filled)) 
        painter.drawPath(text_path) 
        logging.debug(f"  Text fill drawn with color {text_color_filled.name()} (over filled part).")
        
        # Restore painter clip to draw the unfilled portion
        painter.setClipping(False) 

        # Clip for the "unfilled" part
        painter.setPen(QPen(text_color_unfilled, 1)) 
        painter.setBrush(QBrush(text_color_unfilled)) 

        # Combine text path and unfilled area clip path
        combined_clip_path_unfilled = unfilled_clip_path.intersected(text_path)
        painter.setClipPath(combined_clip_path_unfilled)

        # Draw the text again
        painter.drawPath(text_path)
        logging.debug(f"  Text fill drawn with color {text_color_unfilled.name()} (over unfilled part).")
        
        painter.restore() # Restore painter state after transformations and clipping


    def _draw_fallback_gauge(self, painter, rect, bg_color, border_color, text_color):
        logger.debug(f"  Drawing Fallback Gauge for {self.objectName()}. Value: {self._value}")
        painter.save()
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 2))
        painter.drawRoundedRect(rect, 10, 10) # Simple rounded rectangle

        # Use _draw_value_text for consistency
        self._draw_value_text(painter, rect, self._value, self.unit, text_color, 
                              self._get_themed_color('gauge_text_outline_color', 'black'), 
                              self._get_themed_color('gauge_high_contrast_text_color', 'white'),
                              QFont(self.theme_colors.get('font_family', "Inter"), int(rect.height() * 0.2)))
        painter.restore()

    def _draw_value_text(self, painter, rect, value, unit, text_color, text_outline_color, high_contrast_text_color, font_obj):
        """Helper to draw value text with outline for better readability. Handles N/A."""
        logger.debug(f"  _draw_value_text called. Value: {value}, Unit: {unit}")
        painter.save()
        
        display_text = ""
        if value is not None and not self._is_na:
            formatted_value = f"{value:.{self.decimal_precision}f}" if self.decimal_precision is not None else str(value)
            display_text = f"{formatted_value}{unit}"
        else:
            display_text = "N/A" # Display N/A if value is None or _is_na is True

        painter.setFont(font_obj)
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(display_text) 
        text_height = metrics.height()

        # Center the text within the given rect
        text_x = rect.x() + (rect.width() - text_width) / 2
        text_y = rect.y() + (rect.height() - text_height) / 2 + metrics.ascent() # Adjust for baseline

        # Draw outline first
        painter.setPen(QPen(text_outline_color, 2))
        painter.drawText(int(text_x), int(text_y), display_text)
        
        # Draw fill text
        final_text_color = text_color
        painter.setPen(QPen(final_text_color, 1))
        painter.drawText(int(text_x), int(text_y), display_text)
        
        painter.restore()


    def _draw_na_text(self, painter, rect, text_color, font_obj):
        """Helper to draw 'N/A' text when value is None."""
        logger.debug("  _draw_na_text called. Value is N/A.")
        painter.save()
        painter.setFont(font_obj)
        
        na_text_color = self._get_themed_color('label_color', '#E0F2F7') # Use general label color for N/A
        
        # For N/A text, use the default text outline color
        outline_color = self._get_themed_color('gauge_text_outline_color', 'black')

        # Draw outline
        painter.setPen(QPen(outline_color, 2))
        text_path = QPainterPath()
        metrics = QFontMetrics(font_obj)
        # Positioning for QPainterPath needs the baseline
        text_path.addText(rect.x() + (rect.width() - metrics.horizontalAdvance("N/A")) / 2, 
                          rect.y() + (rect.height() - metrics.height()) / 2 + metrics.ascent(), 
                          font_obj, "N/A")
        painter.drawPath(text_path)

        # Draw fill
        painter.setPen(QPen(na_text_color, 1))
        # Draw the text directly using painter, centered within the rect
        painter.drawText(rect, Qt.AlignCenter, "N/A")
        painter.restore()

    def mouseMoveEvent(self, event):
        """Show tooltip with min/max values and thresholds."""
        # For performance, only show tooltip if mouse is over the widget
        self.setToolTip(self._get_tooltip_text())
        super().mouseMoveEvent(event)

    def resizeEvent(self, event):
        """Handle resize events to update font sizes and re-layout progress bar."""
        super().resizeEvent(event)
        
        # If the progress bar is visible, update its geometry and QSS
        if self.progressBar.isVisible():
            # Ensure the progressBar is resized to fill its allocated space within the main_layout
            # The contentsRect() provides the inner rectangle of the QGroupBox.
            adjusted_rect = self.contentsRect().adjusted(
                self.main_layout.contentsMargins().left(), 
                self.main_layout.contentsMargins().top(), 
                -self.main_layout.contentsMargins().right(), 
                -self.main_layout.contentsMargins().bottom()
            )
            self.progressBar.setGeometry(adjusted_rect)
            
            # Re-apply QSS for font size etc., as it depends on widget size
            self.progressBar.setStyleSheet(self._get_progress_bar_qss()) 
            self.progressBar.style().polish(self.progressBar) # Force QSS re-evaluation

        # For custom-drawn gauges, force repaint as dimensions might change text/shape size
        # This update() call is crucial for all custom drawn elements
        self.update() 
