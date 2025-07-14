# widgets/gauges/ring_gauge_drawer.py
import logging
import math
from PyQt5.QtCore import Qt, QPointF, QRectF, QSize
from PyQt5.QtGui import QPainter, QBrush, QColor, QFont, QPen, QFontMetrics, QPixmap, QPainterPath

# Assuming a BaseGaugeDrawer exists in your framework for helper methods
from .base_gauge_drawer import BaseGaugeDrawer

logger = logging.getLogger(__name__)

class RingGaugeDrawer(BaseGaugeDrawer):
    """
    Draws a gauge with a single ring, where the value is represented by a filled arc
    within the ring. It displays a central value and a title.
    This class encapsulates the drawing logic, rendering to an offscreen QPixmap
    for improved stability and performance.
    """
    def draw(self, painter, rect, sensor_name, current_value, min_value, max_value, unit, gauge_style, colors):
        """
        Main drawing method.
        """
        painter.save()
        try:
            if rect.width() < 1 or rect.height() < 1:
                return

            pixmap = QPixmap(rect.size())
            pixmap.fill(Qt.transparent)
            pixmap_painter = QPainter(pixmap)
            
            pixmap_painter.setRenderHint(QPainter.Antialiasing, True)
            pixmap_painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

            # --- Get Colors based on Alert State ---
            # ✅ **FIX**: Use the specific 'ring_*' keys from the theme file,
            # respecting the alert state to select the correct color set.
            is_alert = self.parent_widget._alert_state in ["warning", "critical"]
            
            if is_alert:
                background_color = colors.get('ring_background_alert', QColor(75, 26, 26))
                border_color = colors.get('ring_border_alert_color', QColor(229, 57, 53))
                active_arc_color = colors.get('ring_fill_alert', QColor(229, 57, 53))
                text_color = colors.get('ring_text_alert', QColor(255, 215, 0))
            else:
                background_color = colors.get('ring_background', QColor(26, 43, 60))
                border_color = colors.get('ring_border_color', QColor(74, 99, 124))
                active_arc_color = colors.get('ring_fill_color', QColor(0, 191, 255))
                text_color = colors.get('ring_text_color', QColor(228, 230, 235))

            # The track for the unfilled part of the ring should remain consistent
            track_color = colors.get('ring_fill_color', QColor(60, 60, 60))

            # --- Define Rects for Title and Gauge ---
            title_height = pixmap.height() * 0.20
            title_rect = QRectF(0, 0, pixmap.width(), title_height)
            gauge_rect = QRectF(0, title_height, pixmap.width(), pixmap.height() - title_height)

            # --- Draw Title ---
            self._draw_sensor_name(pixmap_painter, title_rect, sensor_name, colors)

            # --- Calculate Geometry for the Gauge Ring ---
            center_x = gauge_rect.center().x()
            center_y = gauge_rect.center().y()
            outer_radius = min(gauge_rect.width(), gauge_rect.height()) / 2 * 0.9
            inner_radius = outer_radius * 0.7

            # --- Draw the Static Gauge Elements (Ring) ---
            pixmap_painter.setBrush(QBrush(background_color))
            pixmap_painter.setPen(QPen(border_color, 2))
            pixmap_painter.drawEllipse(QPointF(center_x, center_y), outer_radius, outer_radius)

            pixmap_painter.setBrush(QBrush(track_color))
            pixmap_painter.setPen(Qt.NoPen)
            pixmap_painter.drawEllipse(QPointF(center_x, center_y), outer_radius, outer_radius)
            
            pixmap_painter.setBrush(QBrush(background_color))
            pixmap_painter.drawEllipse(QPointF(center_x, center_y), inner_radius, inner_radius)

            # --- Draw the Active Arc ---
            if current_value is not None and not math.isnan(current_value):
                start_angle = 225
                span_angle_range = 270

                clamped_value = max(min_value, min(max_value, current_value))
                range_val = max_value - min_value
                
                normalized_value = (clamped_value - min_value) / range_val if range_val != 0 else 0
                
                sweep_angle = normalized_value * span_angle_range
                
                start_angle_pyqt = start_angle * 16
                sweep_angle_pyqt = -sweep_angle * 16

                pixmap_painter.setBrush(QBrush(active_arc_color))
                pixmap_painter.setPen(Qt.NoPen)

                outer_arc_rect = QRectF(center_x - outer_radius, center_y - outer_radius, outer_radius * 2, outer_radius * 2)
                pixmap_painter.drawPie(outer_arc_rect, start_angle_pyqt, sweep_angle_pyqt)

                pixmap_painter.setBrush(QBrush(background_color))
                pixmap_painter.drawEllipse(QPointF(center_x, center_y), inner_radius, inner_radius)

            # --- Draw the Value Text ---
            display_value = f"{self._format_value(current_value)}{unit}" if current_value is not None else "N/A"
            value_text_rect_size = QSize(int(inner_radius * 1.8), int(inner_radius * 0.8))
            self._draw_text_in_rect(pixmap_painter, QPointF(center_x, center_y), value_text_rect_size, display_value, text_color, "Inter", QFont.Bold, colors)

            # --- Finalize and Draw to Screen ---
            #pixmap_painter.end()
            # logger.debug("RingGaugeDrawer: Ended main pixmap_painter.")
            painter.drawPixmap(rect.topLeft(), pixmap)

        except Exception as e:
            logger.error(f"RingGaugeDrawer: CRITICAL ERROR during draw for '{sensor_name}': {e}", exc_info=True)
        finally:
            painter.restore()

    def _draw_text_in_rect(self, target_painter, center_pos, size, text, color, font_family, weight, colors):
        """
        Helper to draw dynamically sized, outlined text onto a painter for better readability.
        """
        if size.width() < 1 or size.height() < 1:
            return

        temp_pixmap = QPixmap(size)
        temp_pixmap.fill(Qt.transparent)
        temp_painter = QPainter(temp_pixmap)
        
        temp_painter.setRenderHint(QPainter.Antialiasing, True)
        temp_painter.setRenderHint(QPainter.TextAntialiasing, True)

        font_size = int(size.height() * 0.7)
        font = QFont(font_family, font_size, weight)
        
        metrics = QFontMetrics(font)
        while metrics.horizontalAdvance(text) > size.width() * 0.95 and font_size > 8:
            font_size -= 1
            font.setPointSize(font_size)
            metrics = QFontMetrics(font)
            
        path = QPainterPath()
        
        text_width = metrics.horizontalAdvance(text)
        x = (size.width() - text_width) / 2
        y = (size.height() - metrics.height()) / 2 + metrics.ascent()
        
        path.addText(x, y, font, text)

        outline_color = colors.get('text_outline_color', QColor('black'))
        
        temp_painter.setPen(QPen(outline_color, 1.5))
        temp_painter.setBrush(Qt.NoBrush)
        temp_painter.drawPath(path)
        
        temp_painter.setPen(Qt.NoPen)
        temp_painter.setBrush(QBrush(color))
        temp_painter.drawPath(path)

        temp_painter.end()

        draw_x = center_pos.x() - size.width() / 2
        draw_y = center_pos.y() - size.height() / 2
        target_painter.drawPixmap(QPointF(draw_x, draw_y), temp_pixmap)
        
    def _format_value(self, value):
        """Formats a float value to a string, handling None or NaN."""
        if value is None or math.isnan(value):
            return "N/A"
        return f"{value:.1f}"
