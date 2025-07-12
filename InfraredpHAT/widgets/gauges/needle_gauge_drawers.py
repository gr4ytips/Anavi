# widgets/gauges/needle_gauge_drawers.py
"""
Contains drawer classes for analog gauges that use a traditional needle indicator.
Both classes are updated to draw the sensor name at the top of the widget.
"""
import logging
import math
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPainter, QBrush, QColor, QFont, QPen, QPainterPath
from .base_gauge_drawer import BaseGaugeDrawer
from .analog_gauge_drawers import AnalogGaugeDrawer

logger = logging.getLogger(__name__)

class BasicNeedleGaugeDrawer(AnalogGaugeDrawer):
    """
    Draws a basic analog gauge with a simple static arc and a needle.
    This version includes the sensor name drawn at the top.
    """
    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        logger.debug(f"Drawing Basic Needle Gauge with custom name for {self.parent_widget.objectName()}.")
        painter.save()

        # Define area for the sensor name
        name_area_height = rect.height() * 0.15
        name_rect = QRectF(rect.x(), rect.y(), rect.width(), name_area_height)

        # The remaining area for the gauge itself
        gauge_rect_top = rect.y() + name_area_height
        gauge_rect = QRectF(rect.x(), gauge_rect_top, rect.width(), rect.height() - name_area_height)

        # Draw the sensor name using the helper
        self._draw_sensor_name(painter, name_rect, sensor_name, colors)

        # Define Geometry (adjusted for new gauge area)
        center_x = gauge_rect.center().x()
        center_y = gauge_rect.center().y()
        radius = min(gauge_rect.width(), gauge_rect.height()) / 2 - 10

        # Draw Gauge Body and Frame
        path = QPainterPath()
        path.addEllipse(QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2))
        self._apply_gauge_frame_and_style(painter, QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2), path, colors['background'], colors['gauge_border_color'], colors['gauge_border_width'], colors['gauge_border_style'], gauge_style)

        # Draw the Static Scale Arc
        painter.setPen(QPen(colors['scale_color'], 3))
        painter.drawArc(QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2), 225 * 16, -270 * 16)

        if self.parent_widget._current_value is not None:
            # Draw the Needle
            # Corrected: span_angle should be negative if the gauge sweeps clockwise from start_angle
            self._draw_needle(painter, center_x, center_y, radius * 0.9, colors['needle_color'],
                              current_value_animated, min_value, max_value,
                              start_angle=225, span_angle=-270, needle_type='triangle') # Changed span_angle to -270

            # Draw the Center Dot
            painter.setBrush(QBrush(colors['center_dot_color']))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(center_x, center_y), 5, 5)

            # Draw Value Text
            ### MODIFIED: Font size reduced and text rectangle shifted down ###
            value_font = QFont(self._get_themed_font_family('font_family', 'Inter'), int(radius * 0.25))
            text_rect = QRectF(center_x - radius, center_y - radius * 0.2, radius * 2, radius)
            self._draw_value_text(painter, text_rect, current_value_animated, unit, colors['text_color'],
                                  self._get_themed_color('gauge_text_outline_color', QColor('black')),
                                  self._get_themed_color('high_contrast_text_color', QColor('white')),
                                  value_font)
        painter.restore()
        
class TickedGaugeDrawer(AnalogGaugeDrawer):
    """
    FINAL VERSION: This class uses manual trigonometry to draw the needle,
    bypassing the system's broken painter.rotate() function.
    """
    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # Define drawing areas and draw sensor name
        name_area_height = rect.height() * 0.15
        name_rect = QRectF(rect.x(), rect.y(), rect.width(), name_area_height)
        gauge_rect_top = rect.y() + name_area_height
        gauge_rect = QRectF(rect.x(), gauge_rect_top, rect.width(), rect.height() - name_area_height)
        self._draw_sensor_name(painter, name_rect, sensor_name, colors)

        # Define Geometry
        center_x = gauge_rect.center().x()
        center_y = gauge_rect.center().y()
        radius_outer = min(gauge_rect.width(), gauge_rect.height()) / 2 - 5
        radius_inner = radius_outer * 0.7

        # Capture the definitive range
        gauge_min = float(min_value)
        gauge_max = float(max_value)
        if gauge_max == gauge_min:
            gauge_max = gauge_min + 100.0

        # Draw Inner Dial Background
        dial_rect = QRectF(center_x - radius_inner, center_y - radius_inner, radius_inner * 2, radius_inner * 2)
        painter.setBrush(QBrush(colors['background']))
        painter.setPen(QPen(colors['gauge_border_color'], 2))
        painter.drawEllipse(dial_rect)

        # Draw Ticks and Labels
        start_angle_deg = 225
        span_angle_deg = -270 # This means rotating clockwise from 225
        num_ticks_total = 21
        angle_increment = span_angle_deg / (num_ticks_total - 1)
        painter.setPen(QPen(colors['scale_color'], 2))
        painter.drawArc(QRectF(center_x - radius_outer, center_y - radius_outer, radius_outer * 2, radius_outer * 2), start_angle_deg * 16, span_angle_deg * 16)
        font = QFont(self._get_themed_font_family("font_family", "Inter"), 8)
        painter.setFont(font)
        for i in range(num_ticks_total):
            painter.save()
            painter.translate(center_x, center_y)
            current_angle_deg_for_tick = start_angle_deg + (angle_increment * i)
            painter.rotate(current_angle_deg_for_tick)
            is_major_tick = (i % ((num_ticks_total - 1) // 5) == 0)
            if is_major_tick:
                painter.setPen(QPen(colors['scale_color'], 2)); painter.drawLine(int(radius_outer * 0.9), 0, int(radius_outer), 0)
                painter.setPen(QPen(colors['label_color']))
                percentage = i / (num_ticks_total - 1)
                value_at_tick = gauge_min + (gauge_max - gauge_min) * percentage
                label_text = f"{int(value_at_tick)}"
                label_radius = radius_outer * 0.78
                text_rect = painter.fontMetrics().boundingRect(label_text)
                painter.translate(int(label_radius), 0)
                painter.rotate(-current_angle_deg_for_tick) # Rotate back for horizontal text
                painter.drawText(int(-text_rect.width() / 2), int(text_rect.height() / 2), label_text)
            else:
                painter.setPen(QPen(colors['scale_color'], 1)); painter.drawLine(int(radius_outer * 0.95), 0, int(radius_outer), 0)
            painter.restore()

        if self.parent_widget._current_value is not None:
            # --- Needle Drawing (Manual Rotation Workaround) ---
            painter.save()
            
            # 1. Calculate the final angle on the gauge scale in degrees
            range_span = gauge_max - gauge_min
            normalized_value = (current_value_animated - gauge_min) / range_span if range_span != 0 else 0
            normalized_value = max(0.0, min(1.0, normalized_value)) # Clamp to 0-1 range

            # Calculate the target angle for the needle tip on the gauge scale (225 down to -45)
            target_gauge_angle_deg = start_angle_deg + (normalized_value * span_angle_deg)

            # Adjust the angle for the `math.cos`/`math.sin` functions.
            # The needle points (p1, p2, p3) are defined to point "up" (along the negative Y-axis).
            # In standard trigonometric coordinates (0 at positive X, increasing counter-clockwise),
            # this "up" direction is 270 degrees (or -90 degrees).
            # To rotate the needle from its initial "up" orientation to `target_gauge_angle_deg`,
            # we need to calculate the difference and add 90 degrees to get the effective rotation
            # angle relative to the standard 0-degree (positive X-axis) reference.
            angle_rad = math.radians(target_gauge_angle_deg + 90.0) # Corrected line

            # 2. Define needle points as if it's pointing straight UP (-Y direction)
            needle_base_width = radius_inner * 0.1
            needle_length_forward = radius_inner * 0.8
            needle_length_backward = radius_inner * 0.2
            
            p1 = QPointF(0, -needle_length_forward) # Tip
            p2 = QPointF(-needle_base_width / 2, 0) # Bottom-left
            p3 = QPointF(needle_base_width / 2, 0)  # Bottom-right
            
            t1 = QPointF(-needle_base_width / 4, 0)
            t2 = QPointF(needle_base_width / 4, 0)
            t3 = QPointF(needle_base_width / 4, needle_length_backward)
            t4 = QPointF(-needle_base_width / 4, needle_length_backward)

            # 3. Manually rotate each point using trigonometry
            cos_angle = math.cos(angle_rad)
            sin_angle = math.sin(angle_rad)
            
            def rotate_point(p):
                # Standard 2D rotation matrix:
                # x' = x*cos(a) - y*sin(a)
                # y' = x*sin(a) + y*cos(a)
                return QPointF(p.x() * cos_angle - p.y() * sin_angle, p.x() * sin_angle + p.y() * cos_angle)

            # 4. Translate points to the center of the gauge and draw
            center_point = QPointF(center_x, center_y)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(colors['needle_color']))
            
            # Draw main triangle of needle
            painter.drawConvexPolygon(
                rotate_point(p1) + center_point,
                rotate_point(p2) + center_point,
                rotate_point(p3) + center_point
            )
            # Draw tail rectangle of needle
            painter.drawConvexPolygon(
                rotate_point(t1) + center_point,
                rotate_point(t2) + center_point,
                rotate_point(t3) + center_point,
                rotate_point(t4) + center_point
            )
            painter.restore()
            
            # --- Center Dot & Value Text ---
            painter.setBrush(QBrush(colors['center_dot_color']))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(center_x, center_y), 7, 7)
            
            value_font = QFont(self._get_themed_font_family('font_family', 'Inter'), int(radius_inner * 0.25))
            text_rect = QRectF(center_x - radius_inner, center_y - radius_inner * 0.2, radius_inner * 2, radius_inner)
            self._draw_value_text(painter, text_rect, current_value_animated, unit, colors['text_color'],
                                  self._get_themed_color('gauge_text_outline_color', QColor('black')),
                                  self._get_themed_color('high_contrast_text_color', QColor('white')),
                                  value_font)
        painter.restore()