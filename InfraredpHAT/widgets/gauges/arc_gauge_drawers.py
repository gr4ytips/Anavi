# widgets/gauges/arc_gauge_drawers.py
"""
Contains drawer classes for gauges where the value is represented by the
length of a colored arc, rather than a traditional needle.
"""
import logging
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPainter, QBrush, QColor, QFont, QPen
from .base_gauge_drawer import BaseGaugeDrawer
from .analog_gauge_drawers import AnalogGaugeDrawer

logger = logging.getLogger(__name__)

class AnalogArcGaugeDrawer(AnalogGaugeDrawer):
    """
    Draws an analog gauge where the value is represented by a filled arc
    instead of a traditional needle. The arc fills a background track,
    providing a clean and modern visualization.
    """
    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        """
        Renders the arc gauge within the given rectangle.
        """
        logger.debug(f"  Drawing Analog Arc Gauge for {self.parent_widget.objectName()}. Value: {current_value_animated}")
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # --- 1. Geometry and Value Calculation ---
        center_x = rect.center().x()
        center_y = rect.center().y() + rect.height() * 0.1 # Nudge down to make space for name
        radius = min(rect.width(), rect.height()) / 2 * 0.85
        
        # Normalize the value to a 0.0-1.0 scale
        if max_value > min_value:
            normalized_value = (current_value_animated - min_value) / (max_value - min_value)
        else:
            normalized_value = 0
        normalized_value = max(0.0, min(1.0, normalized_value)) # Clamp value

        # --- 2. Define Arc Properties ---
        start_angle = 210  # Start angle in degrees (bottom-left)
        span_angle = -240 # Total sweep in degrees (clockwise to bottom-right)
        
        # Calculate the angle for the value arc
        value_angle = normalized_value * span_angle
        
        # --- 3. Draw the Arcs ---
        pen = QPen()
        pen.setCapStyle(Qt.RoundCap)
        pen_width = int(radius * 0.18)
        pen.setWidth(pen_width)

        arc_rect = QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2)

        # Draw the background arc (the full track)
        pen.setColor(colors.get('scale_color', QColor('#E0E0E0')))
        painter.setPen(pen)
        painter.drawArc(arc_rect, start_angle * 16, span_angle * 16)

        # Draw the foreground arc (the value)
        # Use needle_color for the main indicator
        pen.setColor(colors.get('needle_color', QColor('#3498DB')))
        painter.setPen(pen)
        painter.drawArc(arc_rect, start_angle * 16, value_angle * 16)
        
        # --- 4. Draw Sensor Name and Value Text (using helpers from base classes) ---
        if self.parent_widget._current_value is not None:
            # Draw the sensor name above the center
            name_rect_height = rect.height() * 0.20
            name_rect_width = rect.width() * 0.7
            name_rect = QRectF(0, 0, name_rect_width, name_rect_height)
            name_rect.moveCenter(QPointF(rect.center().x(), rect.y() + name_rect_height * 0.75))
            self._draw_sensor_name(painter, name_rect, sensor_name, colors)

            # Draw the value text in the center of the arc
            value_rect_size = radius * 1.2
            value_rect = QRectF(0, 0, value_rect_size, value_rect_size * 0.5)
            value_rect.moveCenter(QPointF(center_x, center_y))
            
            self._draw_value_text(painter,
                                  value_rect,
                                  current_value_animated,
                                  unit,
                                  colors['text_color'],
                                  self._get_themed_color('gauge_text_outline_color', QColor('black')),
                                  self._get_themed_color('high_contrast_text_color', QColor('white')),
                                  QFont(self._get_themed_font_family('font_family', 'Inter'), int(radius * 0.35)))
        else:
            # If no value, draw N/A in the center
            self._draw_na_text(painter, rect, colors['text_color'], 
                               QFont(self._get_themed_font_family('font_family', 'Inter'), int(radius * 0.4)),
                               self._get_themed_color('gauge_text_outline_color', QColor('black')),
                               self._get_themed_color('high_contrast_text_color', QColor('white')))

        painter.restore()