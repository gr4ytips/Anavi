# widgets/gauges/speedometer_gauge_drawer.py
from PyQt5.QtCore import Qt, QPointF, QRectF, QRect
from PyQt5.QtGui import QPainter, QBrush, QColor, QFont, QPen, QPainterPath, QFontMetrics, QConicalGradient, QLinearGradient
from .analog_gauge_drawers import AnalogGaugeDrawer
import logging
import math

logger = logging.getLogger(__name__)

class SpeedometerGaugeDrawer(AnalogGaugeDrawer):
    """
    A gauge drawer specifically designed for a speedometer-like display
    with an active arc indicating the current value and a central digital readout.
    """

    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        """
        Paints the speedometer gauge, including the background arc, active value arc,
        center circle, current value text, and title text. The active arc's
        color is determined by the current alert level.
        """
        logger.debug(f"SpeedometerGaugeDrawer: draw method entered for {self.parent_widget.objectName()}. "
                     f"Value: {current_value_animated}, Min: {min_value}, Max: {max_value}, Unit: {unit}, Style: {gauge_style}")

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        side = min(rect.width(), rect.height())
        
        painter.translate(rect.center().x(), rect.center().y())
        painter.scale(side / 200.0, side / 200.0)
        painter.translate(-100, -100)

        virtual_rect = QRectF(0, 0, 200, 200)
        logger.debug(f"SpeedometerGaugeDrawer: Virtual canvas setup - Side: {side}, Rect center: {rect.center().x()}, {rect.center().y()}")
        logger.debug(f"SpeedometerGaugeDrawer: Virtual rect: {virtual_rect.x(), virtual_rect.y(), virtual_rect.width(), virtual_rect.height()}")

        # Fetch colors using theme keys
        outer_bg_color = self._get_themed_color('speedometer_outer_background', QColor(40, 40, 40))
        track_color = self._get_themed_color('speedometer_track_color', QColor(60, 60, 60))
        inner_circle_color = self._get_themed_color('speedometer_inner_circle_color', QColor(30, 30, 30))
        
        normal_fill_color = colors['fill_color']
        warning_fill_color = colors['warning_color']
        critical_fill_color = colors['critical_color']
        text_color = colors['text_color']

        logger.debug(f"SpeedometerGaugeDrawer: Fetched colors - Outer BG: {outer_bg_color.name()}, Track: {track_color.name()}, Inner Circle: {inner_circle_color.name()}")
        logger.debug(f"SpeedometerGaugeDrawer: Resolved Fill Colors - Normal: {normal_fill_color.name()}, Warning: {warning_fill_color.name()}, Critical: {critical_fill_color.name()}")

        # 1. Draw the outermost background as a fully filled circle
        painter.setBrush(QBrush(outer_bg_color))
        painter.setPen(Qt.NoPen) 
        painter.drawEllipse(virtual_rect)
        logger.debug("SpeedometerGaugeDrawer: Drawn outer background circle.")

        # 2. Draw the main gauge track background arc
        painter.setPen(QPen(track_color, 15, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(QRectF(20, 20, 160, 160), 225 * 16, -270 * 16)
        logger.debug("SpeedometerGaugeDrawer: Drawn main gauge track arc.")

        # 3. Draw the active arc (color based on alert level)
        if current_value_animated is not None and not math.isnan(current_value_animated):
            clamped_value = max(min_value, min(max_value, current_value_animated))
            range_val = max_value - min_value
            
            current_angle_span = 0
            if range_val > 0:
                normalized_value = (clamped_value - min_value) / range_val
                current_angle_span = -int(normalized_value * 270) 
            else:
                normalized_value = 0 # Avoid division by zero if min_value == max_value

            active_arc_color = normal_fill_color
            if self.parent_widget._alert_state == "warning":
                active_arc_color = warning_fill_color
            elif self.parent_widget._alert_state == "critical":
                active_arc_color = critical_fill_color
            
            logger.debug(f"SpeedometerGaugeDrawer: Value processing - Clamped: {clamped_value}, Normalized: {normalized_value:.2f}, Angle Span: {current_angle_span} degrees")
            logger.debug(f"SpeedometerGaugeDrawer: Alert State: {self.parent_widget._alert_state}, Active Arc Color: {active_arc_color.name()}")

            painter.setPen(QPen(active_arc_color, 15, Qt.SolidLine, Qt.RoundCap))
            painter.drawArc(QRectF(20, 20, 160, 160), 225 * 16, current_angle_span * 16)
            logger.debug("SpeedometerGaugeDrawer: Drawn active value arc.")
        else:
            logger.debug("SpeedometerGaugeDrawer: current_value_animated is None or NaN. Skipping active arc drawing.")


        # 4. Draw the inner circle (center of the gauge)
        painter.setBrush(QBrush(inner_circle_color))
        painter.drawEllipse(QRectF(55, 55, 90, 90))
        logger.debug("SpeedometerGaugeDrawer: Drawn inner center circle.")

        # --- Draw Value Text ---
        value_font_size = int(virtual_rect.width() / 10) 
        value_font = QFont(self._get_themed_font_family('font_family', 'Inter'), value_font_size)
        value_font.setBold(True)
        
        value_text_draw_rect_virtual = QRectF(50, 50, 100, 100)
        logger.debug(f"SpeedometerGaugeDrawer: Value text font size: {value_font_size}, Rect: {value_text_draw_rect_virtual.x(), value_text_draw_rect_virtual.y(), value_text_draw_rect_virtual.width(), value_text_draw_rect_virtual.height()}")

        self._draw_value_text(painter, 
                              value_text_draw_rect_virtual, 
                              current_value_animated, 
                              unit, 
                              text_color, 
                              self._get_themed_color('gauge_text_outline_color', QColor('black')),
                              self._get_themed_color('high_contrast_text_color', QColor('white')), 
                              value_font)
        logger.debug("SpeedometerGaugeDrawer: Drawn value text.")

        # --- Draw Sensor Name (Title) ---
        title_font_size = int(virtual_rect.width() / 20)
        title_font = QFont(self._get_themed_font_family('font_family', 'Inter'), title_font_size)
        title_font.setBold(False)
        
        title_vertical_offset_from_bottom = 25
        title_y_pos = 200 - title_vertical_offset_from_bottom
        title_draw_rect_virtual = QRectF(0, title_y_pos, 200, title_vertical_offset_from_bottom)
        logger.debug(f"SpeedometerGaugeDrawer: Sensor name font size: {title_font_size}, Rect: {title_draw_rect_virtual.x(), title_draw_rect_virtual.y(), title_draw_rect_virtual.width(), title_draw_rect_virtual.height()}")

        self._draw_sensor_name(painter, title_draw_rect_virtual, sensor_name, colors)
        logger.debug("SpeedometerGaugeDrawer: Drawn sensor name.")

        painter.restore()
        logger.debug("SpeedometerGaugeDrawer: draw method exited.")