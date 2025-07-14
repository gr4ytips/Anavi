from PyQt5.QtWidgets import QWidget, QLabel, QSizePolicy
from PyQt5.QtGui import QFont, QColor, QPainter, QPen
from PyQt5.QtCore import Qt, QRect, QSize # Import QSize

import math # For math.isnan
from utils.config_manager import ConfigManager # Import ConfigManager for theme access

class GaugeWidgetMultiRing(QWidget):
    """
    A custom PyQt5 widget designed to display a sensor value as a gauge.
    It shows a circular gauge with a value display in the center and a title.
    The outer ring changes color based on the value's proximity to defined thresholds.
    """
    def __init__(self, title, min_val, max_val, unit="", sensor_thresholds=None, config_manager=None, parent=None):
        """
        Initializes the GaugeWidgetMultiRing.

        :param title: The title of the gauge (e.g., "Temperature").
        :param min_val: The minimum value for the gauge's scale.
        :param max_val: The maximum value for the gauge's scale.
        :param unit: The unit of measurement (e.g., "°C", "さんも").
        :param sensor_thresholds: A dictionary containing specific thresholds for this sensor
                                  (e.g., {"WARNING_HIGH": val, "CRITICAL_HIGH": val, ...}).
                                  If None, a default 'NORMAL' state is assumed.
        :param config_manager: Reference to the ConfigManager for theme settings.
        :param parent: The parent widget, if any.
        """
        super().__init__(parent)
        self.title = title
        self.min_val = min_val
        self.max_val = max_val
        self.unit = unit
        self.original_unit = unit # Store the original unit to decide title modification
        self._value = float('nan') # Initialize current value to NaN for "no data" state
        self._alert_level = "NORMAL" # Initialize alert level

        # Store the actual sensor-specific thresholds
        self.sensor_thresholds = sensor_thresholds if sensor_thresholds is not None else {}

        self.config = config_manager if config_manager else ConfigManager.get_instance() # Get config instance
        self._set_theme_colors_internal() # Set initial theme colors based on current config

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) # Changed to Expanding for full responsiveness

    def _set_theme_colors_internal(self):
        """
        Sets internal color attributes based on the current theme from ConfigManager.
        This method is called internally or when the theme changes.
        """
        current_theme = self.config.get_setting("current_theme", "dark_theme")
        theme_palettes = {
            "dark_theme": {
                "outer_bg_color": QColor("#3A3A3A"), # Darkest gray for outer filled circle
                "track_color": QColor("#555555"),   # Medium-dark gray for main track
                "inner_circle_color": QColor("#3E3E3E"), # Darker gray for inner circle
                "text_color": QColor("#E0E0E0"),    # Off-white text for value and title
                "critical_color": QColor("red"),    # Red
                "warning_color": QColor("orange"),  # Amber (Orange)
                "normal_color": QColor("#00BFFF")   # Vibrant Blue
            },
            "light_theme": {
                "outer_bg_color": QColor("#F0F0F0"),
                "track_color": QColor("#C0C0C0"),
                "inner_circle_color": QColor("#FFFFFF"),
                "text_color": QColor("#333333"),
                "critical_color": QColor("#CC0000"),
                "warning_color": QColor("#E5A000"),
                "normal_color": QColor("#007bff")
            },
            "blue_theme": {
                "outer_bg_color": QColor("#264264"),
                "track_color": QColor("#3c6595"),
                "inner_circle_color": QColor("#1A2A40"),
                "text_color": QColor("#e0f2f7"),
                "critical_color": QColor("#E74C3C"),
                "warning_color": QColor("#F39C12"),
                "normal_color": QColor("#4682B4")
            },
            "dark_gray_theme": {
                "outer_bg_color": QColor("#4B4F52"),
                "track_color": QColor("#6C7072"),
                "inner_circle_color": QColor("#3D4042"),
                "text_color": QColor("#fdfdfd"),
                "critical_color": QColor("#E74C3C"),
                "warning_color": QColor("#F39C12"),
                "normal_color": QColor("#6a737d")
            },
            "forest_green_theme": {
                "outer_bg_color": QColor("#2E7D32"),
                "track_color": QColor("#4CAF50"),
                "inner_circle_color": QColor("#1D4D1F"),
                "text_color": QColor("#FFFFFF"),
                "critical_color": QColor("#E74C3C"),
                "warning_color": QColor("#F39C12"),
                "normal_color": QColor("#66BB6A")
            },
            "warm_sepia_theme": {
                "outer_bg_color": QColor("#5A2D0C"),
                "track_color": QColor("#A0522D"),
                "inner_circle_color": QColor("#3A1D07"),
                "text_color": QColor("#F5DEB3"),
                "critical_color": QColor("#D35400"),
                "warning_color": QColor("#F39C12"),
                "normal_color": QColor("#A0522D")
            },
            "ocean_blue_theme": {
                "outer_bg_color": QColor("#002244"),
                "track_color": QColor("#005099"),
                "inner_circle_color": QColor("#001122"),
                "text_color": QColor("#E0FFFF"),
                "critical_color": QColor("#E74C3C"),
                "warning_color": QColor("#F39C12"),
                "normal_color": QColor("#4682B4")
            },
            "vibrant_purple_theme": {
                "outer_bg_color": QColor("#300050"),
                "track_color": QColor("#8A2BE2"),
                "inner_circle_color": QColor("#200030"),
                "text_color": QColor("#E6E6FA"),
                "critical_color": QColor("#E74C3C"),
                "warning_color": QColor("#F39C12"),
                "normal_color": QColor("#8A2BE2")
            },
            "light_modern_theme": {
                "outer_bg_color": QColor("#F8F8F8"),
                "track_color": QColor("#C0C0C0"),
                "inner_circle_color": QColor("#FFFFFF"),
                "text_color": QColor("#333333"),
                "critical_color": QColor("#CC0000"),
                "warning_color": QColor("#E5A000"),
                "normal_color": QColor("#607D8B")
            },
            "high_contrast_theme": {
                "outer_bg_color": QColor("#111111"),
                "track_color": QColor("#FF00FF"),
                "inner_circle_color": QColor("#000000"),
                "text_color": QColor("#FFFF00"),
                "critical_color": QColor("#FF0000"),
                "warning_color": QColor("#FFA500"),
                "normal_color": QColor("#00FF00")
            }
        }
        palette = theme_palettes.get(current_theme, theme_palettes["dark_theme"])

        self.outer_bg_color = palette["outer_bg_color"]
        self.track_color = palette["track_color"]
        self.inner_circle_color = palette["inner_circle_color"]
        self.text_color = palette["text_color"]
        
        # Override threshold colors to use theme colors if provided
        self.threshold_colors = {
            "CRITICAL_HIGH": palette["critical_color"],
            "WARNING_HIGH": palette["warning_color"],
            "NORMAL": palette["normal_color"],
            "WARNING_LOW": palette["warning_color"],
            "CRITICAL_LOW": palette["critical_color"]
        }
        self.update() # Trigger repaint


    def set_theme_colors(self, bg_color: str, border_color: str, text_color: str,
                         accent_color: str, critical_color: str, warning_color: str,
                         normal_color: str, gauge_fill_color: str):
        """
        Public method to set the theme-specific colors for the gauge widget from external calls.
        This allows external components like tabs to update the gauge's colors.
        Note: The parameters for this method might be slightly different than
        GaugeWidgetOne as MultiRing uses different drawing components.
        """
        # Map the general colors to MultiRing's specific components
        self.outer_bg_color = QColor(bg_color) # Corresponds to gauge_bg_color from main tab
        self.track_color = QColor(gauge_fill_color) # Corresponds to gauge_fill_color for the track
        self.inner_circle_color = QColor(bg_color) # Inner circle same as outer background
        self.text_color = QColor(text_color)
        
        # Explicitly set alert colors based on the passed parameters
        self.threshold_colors["CRITICAL_HIGH"] = QColor(critical_color)
        self.threshold_colors["CRITICAL_LOW"] = QColor(critical_color)
        self.threshold_colors["WARNING_HIGH"] = QColor(warning_color)
        self.threshold_colors["WARNING_LOW"] = QColor(warning_color)
        self.threshold_colors["NORMAL"] = QColor(normal_color) # Normal color passed in

        self.update() # Trigger repaint


    def set_value(self, value):
        """
        Sets the current value for the gauge and updates its alert level.

        :param value: The new sensor value.
        """
        if value is not None and not math.isnan(value):
            self._value = value
            self._update_alert_level() # Update alert level based on new value
        else:
            self._value = float('nan') # Use NaN to indicate no valid data
            self._alert_level = "NORMAL" # Reset to normal if no data
        self.update() # Trigger a repaint of the widget

    def _update_alert_level(self):
        """
        Determines the current alert level based on the sensor's actual thresholds.
        """
        if math.isnan(self._value):
            self._alert_level = "NORMAL" # Default to normal if no valid data
            return

        current_value = self._value
        thresholds = self.sensor_thresholds

        # Check CRITICAL_HIGH
        if "CRITICAL_HIGH" in thresholds and current_value >= thresholds["CRITICAL_HIGH"]["value"]:
            self._alert_level = "CRITICAL_HIGH"
        # Check WARNING_HIGH (only if not already critical high)
        elif "WARNING_HIGH" in thresholds and current_value >= thresholds["WARNING_HIGH"]["value"]:
            self._alert_level = "WARNING_HIGH"
        # Check CRITICAL_LOW (only if not already high alerts)
        elif "CRITICAL_LOW" in thresholds and current_value <= thresholds["CRITICAL_LOW"]["value"]:
            self._alert_level = "CRITICAL_LOW"
        # Check WARNING_LOW (only if not already low/high alerts)
        elif "WARNING_LOW" in thresholds and current_value <= thresholds["WARNING_LOW"]["value"]:
            self._alert_level = "WARNING_LOW"
        else:
            self._alert_level = "NORMAL" # Value is within normal operating range


    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        """
        Paints the gauge widget, including the background arc, active value arc,
        center circle, current value text, and title text. The active arc's
        color is determined by the current alert level.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        side = min(rect.width(), rect.height())
        
        # Scale the painter to a virtual 200x200 canvas, which will then stretch
        # to fill the actual widget's side (min(width, height))
        painter.translate(rect.center())
        painter.scale(side / 200.0, side / 200.0)
        painter.translate(-100, -100) # Translate back to (0,0) of the virtual 200x200 canvas

        # 1. Draw the outermost background as a fully filled dark gray circle
        painter.setBrush(self.outer_bg_color)
        painter.setPen(Qt.NoPen) # No outline for this filled circle
        painter.drawEllipse(0, 0, 200, 200) # Fills the entire virtual 200x200 area

        # 2. Draw the main gauge track background arc
        painter.setPen(QPen(self.track_color, 15, Qt.SolidLine, Qt.RoundCap)) # Medium-dark gray for main track
        painter.drawArc(20, 20, 160, 160, 225 * 16, -270 * 16) # Arc for the static track

        # 3. Draw the active arc (color based on alert level)
        if not math.isnan(self._value):
            clamped_value = max(self.min_val, min(self.max_val, self._value))
            range_val = self.max_val - self.min_val
            
            current_angle = 0
            if range_val > 0:
                normalized_value = (clamped_value - self.min_val) / range_val
                current_angle = -int(normalized_value * 270)
            
            # Get color based on alert level
            active_arc_color = self.threshold_colors.get(self._alert_level, self.threshold_colors["NORMAL"])
            painter.setPen(QPen(active_arc_color, 15, Qt.SolidLine, Qt.RoundCap)) # Set color dynamically
            painter.drawArc(20, 20, 160, 160, 225 * 16, current_angle * 16)

        # 4. Draw the inner circle (center of the gauge)
        painter.setBrush(self.inner_circle_color) # Use theme-aware inner circle color
        painter.drawEllipse(55, 55, 90, 90) # Reduced from 100x100 to 90x90, shifted by 5px

        # --- IMPORTANT: Drawing text after all other visual elements, with adjusted rectangle ---

        # Prepare font for value
        value_font = QFont("Arial", 20)
        value_font.setBold(True)
        painter.setFont(value_font)
        painter.setPen(self.text_color) # Use theme-aware text color for value

        # Define units that should be moved to the title
        units_to_move = ["Raw", "cm", "%", "°C", "°F"]

        # Modify display_value_text based on whether the original unit is in the list
        display_value_text = ""
        if math.isnan(self._value):
            if self.original_unit in units_to_move:
                display_value_text = "--"
            else:
                display_value_text = "--{0}".format(self.original_unit)
        else:
            if self.original_unit in units_to_move:
                display_value_text = "{:.1f}".format(self._value)
            else:
                display_value_text = "{:.1f}{0}".format(self._value, self.original_unit)
        
        # Reverted to original 100x100 size for text rect, now the inner circle provides the padding
        value_text_draw_rect = QRect(50, 50, 100, 100) 
        painter.drawText(value_text_draw_rect, Qt.AlignCenter, display_value_text)


        # Draw the gauge title below the value
        title_font = QFont("Arial", 10)
        title_font.setBold(False)
        painter.setFont(title_font)
        painter.setPen(self.text_color) # Use theme-aware text color for title

        # Adjust title based on original unit, appending the unit in parentheses if applicable
        displayed_title = self.title
        if self.original_unit == "Raw":
            displayed_title = "{0} (Raw)".format(self.title)
        elif self.original_unit == "cm":
            displayed_title = "{0} (cm)".format(self.title)
        elif self.original_unit == "%": # Add logic for "%"
            displayed_title = "{0} (%)".format(self.title)
        elif self.original_unit == "°C": # Add logic for "°C"
            displayed_title = "{0} (°C)".format(self.title)
        elif self.original_unit == "°F": # Add logic for "°F"
            displayed_title = "{0} (°F)".format(self.title)

        title_vertical_offset_from_bottom = 25
        title_y_pos = 200 - title_vertical_offset_from_bottom
        
        title_draw_rect = QRect(0, title_y_pos, 200, title_vertical_offset_from_bottom)
        painter.drawText(title_draw_rect, Qt.AlignHCenter | Qt.AlignTop, displayed_title)

    def minimumSizeHint(self):
        """
        Provides a reasonable minimum size hint for the layout system.
        """
        return QSize(120, 120)

    def sizeHint(self):
        """
        Provides an ideal size hint for the layout system.
        """
        return QSize(200, 200)
