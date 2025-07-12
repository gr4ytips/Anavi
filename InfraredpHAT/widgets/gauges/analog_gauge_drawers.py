# widgets/gauges/analog_gauge_drawers.py
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPainter, QBrush, QColor, QFont, QPen, QPainterPath, QFontMetrics, QConicalGradient
from .base_gauge_drawer import BaseGaugeDrawer
import logging
import math

logger = logging.getLogger(__name__)

class AnalogGaugeDrawer(BaseGaugeDrawer):
    """
    Base class for all analog gauge drawing logic.
    Provides common methods for drawing scales, needles, and central elements.
    """
    def _draw_scale_and_labels(self, painter, center_x, center_y, radius, scale_color, start_angle, span_angle, label_interval, label_start_angle_offset=0):
        painter.setPen(QPen(scale_color, 2))
        painter.save() 
        painter.translate(center_x, center_y)
        
        min_val = self.parent_widget._min_value
        max_val = self.parent_widget._max_value

        for i in range(0, 101, label_interval):
            normalized_point = i / 100.0
            current_angle = start_angle - (normalized_point * span_angle) + label_start_angle_offset
            
            painter.save() 
            painter.rotate(current_angle)
            painter.drawLine(0, int(-radius * 0.8), 0, int(-radius * 0.9))
            
            if i % (label_interval * 2) == 0: 
                label_font = QFont(self._get_themed_font_family('font_family', 'Inter'), int(radius * 0.1))
                painter.setFont(label_font)
                metrics = QFontMetrics(label_font)
                
                label_value = min_val + (i / 100.0) * (max_val - min_val)
                label_text = self._format_value(label_value)
                
                label_width = metrics.horizontalAdvance(label_text)
                label_height = metrics.height()
                
                painter.drawText(int(-label_width / 2), int(-radius * 0.95 - label_height / 2), label_text)
            painter.restore() 
        painter.restore()

    def _draw_needle(self, painter, center_x, center_y, radius, needle_color, current_value_animated, min_value, max_value, start_angle, span_angle, needle_type='triangle'):
        painter.save() 
        painter.translate(center_x, center_y)
        
        # --- Corrected Needle Calculation ---
        if max_value > min_value:
            normalized_value = (current_value_animated - min_value) / (max_value - min_value)
        else:
            normalized_value = 0
            
        # Clamp the value to the 0.0 to 1.0 range
        normalized_value = max(0.0, min(1.0, normalized_value)) 
        
        # This formula correctly maps the normalized value to the gauge's angle span
        angle = start_angle + (normalized_value * -span_angle)
        
        painter.rotate(angle)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(needle_color))
        
        if needle_type == 'triangle':
            needle_base_width = radius * 0.1
            needle_length = radius * 0.7
            painter.drawConvexPolygon(QPointF(-needle_base_width / 2, 0),
                                      QPointF(needle_base_width / 2, 0),
                                      QPointF(0, -needle_length))
        elif needle_type == 'rectangle':
            needle_width = radius * 0.05
            needle_length = radius * 0.7
            painter.drawRect(int(-needle_width / 2), 0, int(needle_width), int(-needle_length))
        elif needle_type == 'full_circle_arrow': 
            needle_base_width = radius * 0.1
            needle_length_forward = radius * 0.7
            needle_length_backward = radius * 0.2
            painter.drawConvexPolygon(QPointF(int(-needle_base_width / 2), 0),
                                      QPointF(int(needle_base_width / 2), 0),
                                      QPointF(0, int(-needle_length_forward)))
            painter.drawRect(int(-needle_base_width/4), 0, int(needle_base_width/2), int(needle_length_backward))

        painter.restore()

    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        logger.debug(f"  Drawing Analog Gauge (Generic) for {self.parent_widget.objectName()}. Value: {current_value_animated}, Style: {gauge_style}")
        painter.save()

        center_x = rect.center().x()
        center_y = rect.center().y()
        radius = min(rect.width(), rect.height()) / 2 * 0.9 
        
        path = QPainterPath()
        path.addEllipse(QRectF(rect.center().x() - radius, rect.center().y() - radius, radius * 2, radius * 2))
        self._apply_gauge_frame_and_style(painter, QRectF(rect.center().x() - radius, rect.center().y() - radius, radius * 2, radius * 2), path, colors['background'], colors['gauge_border_color'], colors['gauge_border_width'], colors['gauge_border_style'], gauge_style)

        self._draw_scale_and_labels(painter, center_x, center_y, radius, colors['scale_color'], start_angle=225, span_angle=270, label_interval=10)

        if self.parent_widget._current_value is not None:
            self._draw_needle(painter, center_x, center_y, radius, colors['needle_color'], 
                              current_value_animated, min_value, max_value, 
                              start_angle=225, span_angle=270, needle_type='triangle')

        painter.setBrush(QBrush(colors['center_dot_color']))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(center_x, center_y), int(radius * 0.1), int(radius * 0.1))
        
        # --- Corrected Sensor Name Display ---
        name_rect_height = rect.height() * 0.15
        name_rect_width = rect.width() * 0.7
        name_rect = QRectF(0, 0, name_rect_width, name_rect_height)
        name_rect.moveCenter(QPointF(rect.center().x(), rect.y() + rect.height() * 0.30))
        self._draw_sensor_name(painter, name_rect, sensor_name, colors)

        self._draw_value_text(painter, 
                              rect.adjusted(rect.width() * 0.2, rect.height() * 0.4, -rect.width() * 0.2, -rect.height() * 0.1),
                              current_value_animated, unit, colors['text_color'], 
                              self._get_themed_color('gauge_text_outline_color', QColor('black')),
                              self._get_themed_color('high_contrast_text_color', QColor('white')), 
                              QFont(self._get_themed_font_family('font_family', 'Inter'), int(radius * 0.2)))
        painter.restore()

class AnalogBasicGaugeDrawer(AnalogGaugeDrawer):
    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        logger.debug(f"  Drawing Analog Gauge (Basic) for {self.parent_widget.objectName()}. Value: {current_value_animated}, Style: {gauge_style}")
        painter.save()

        center_x = rect.center().x()
        center_y = rect.center().y()
        radius = min(rect.width(), rect.height()) / 2 * 0.9

        path = QPainterPath()
        path.addEllipse(QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2))
        self._apply_gauge_frame_and_style(painter, QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2), path, colors['background'], colors['gauge_border_color'], colors['gauge_border_width'], colors['gauge_border_style'], gauge_style)

        self._draw_scale_and_labels(painter, center_x, center_y, radius, colors['scale_color'], start_angle=-120, span_angle=300, label_interval=10, label_start_angle_offset=0)

        if self.parent_widget._current_value is not None:
            self._draw_needle(painter, center_x, center_y, radius, colors['needle_color'], 
                              current_value_animated, min_value, max_value, 
                              start_angle=-120, span_angle=300, needle_type='triangle')

        painter.setBrush(QBrush(colors['center_dot_color']))
        painter.drawEllipse(QPointF(center_x, center_y), 8, 8)

        # --- Corrected Sensor Name Display ---
        name_rect_height = rect.height() * 0.15
        name_rect_width = rect.width() * 0.7
        name_rect = QRectF(0, 0, name_rect_width, name_rect_height)
        name_rect.moveCenter(QPointF(rect.center().x(), rect.y() + rect.height() * 0.30))
        self._draw_sensor_name(painter, name_rect, sensor_name, colors)

        self._draw_value_text(painter, 
                              rect.adjusted(rect.width() * 0.2, rect.height() * 0.4, -rect.width() * 0.2, -rect.height() * 0.1), 
                              current_value_animated, unit, colors['text_color'], 
                              self._get_themed_color('gauge_text_outline_color', QColor('black')),
                              self._get_themed_color('high_contrast_text_color', QColor('white')), 
                              QFont(self._get_themed_font_family('font_family', 'Inter'), int(rect.width() / 10)))
        painter.restore()

class AnalogClassicBasicGaugeDrawer(AnalogGaugeDrawer):
    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        logger.debug(f"  Drawing Analog Classic Basic Gauge for {self.parent_widget.objectName()}. Value: {current_value_animated}, Style: {gauge_style}")
        painter.save()

        center_x = rect.center().x()
        center_y = rect.center().y()
        radius = min(rect.width(), rect.height()) / 2 * 0.9 
        
        path = QPainterPath()
        path.addEllipse(QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2))
        self._apply_gauge_frame_and_style(painter, QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2), path, colors['background'], colors['gauge_border_color'], colors['gauge_border_width'], colors['gauge_border_style'], gauge_style)

        self._draw_scale_and_labels(painter, center_x, center_y, radius, colors['scale_color'], start_angle=225, span_angle=270, label_interval=20)

        if self.parent_widget._current_value is not None:
            self._draw_needle(painter, center_x, center_y, radius, colors['needle_color'], 
                              current_value_animated, min_value, max_value, 
                              start_angle=225, span_angle=270, needle_type='triangle')

        painter.setBrush(QBrush(colors['center_dot_color']))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(center_x, center_y), int(radius * 0.1), int(radius * 0.1))

        # --- Corrected Sensor Name Display ---
        name_rect_height = rect.height() * 0.15
        name_rect_width = rect.width() * 0.7
        name_rect = QRectF(0, 0, name_rect_width, name_rect_height)
        name_rect.moveCenter(QPointF(rect.center().x(), rect.y() + rect.height() * 0.30))
        self._draw_sensor_name(painter, name_rect, sensor_name, colors)

        self._draw_value_text(painter, 
                              rect.adjusted(rect.width() * 0.2, rect.height() * 0.4, -rect.width() * 0.2, -rect.height() * 0.1), 
                              current_value_animated, unit, colors['text_color'], 
                              self._get_themed_color('gauge_text_outline_color', QColor('black')),
                              self._get_themed_color('high_contrast_text_color', QColor('white')), 
                              QFont(self._get_themed_font_family('font_family', 'Inter'), int(radius * 0.2)))
        painter.restore()

class AnalogClassicFullGaugeDrawer(AnalogGaugeDrawer):
    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        logger.debug(f"  Drawing Analog Classic Full Gauge for {self.parent_widget.objectName()}. Value: {current_value_animated}, Style: {gauge_style}")
        painter.save()

        center_x = rect.center().x()
        center_y = rect.center().y()
        radius = min(rect.width(), rect.height()) / 2 * 0.9 
        
        path = QPainterPath()
        path.addEllipse(QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2))
        self._apply_gauge_frame_and_style(painter, QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2), path, colors['background'], colors['gauge_border_color'], colors['gauge_border_width'], colors['gauge_border_style'], gauge_style)

        self._draw_scale_and_labels(painter, center_x, center_y, radius, colors['scale_color'], start_angle=-0, span_angle=360, label_interval=30, label_start_angle_offset=0)

        if self.parent_widget._current_value is not None:
            self._draw_needle(painter, center_x, center_y, radius, colors['needle_color'], 
                              current_value_animated, min_value, max_value, 
                              start_angle=0, span_angle=360, needle_type='full_circle_arrow')

        painter.setBrush(QBrush(colors['center_dot_color']))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(center_x, center_y), int(radius * 0.1), int(radius * 0.1))

        # --- Corrected Sensor Name Display ---
        name_rect_height = rect.height() * 0.15
        name_rect_width = rect.width() * 0.7
        name_rect = QRectF(0, 0, name_rect_width, name_rect_height)
        name_rect.moveCenter(QPointF(rect.center().x(), rect.y() + rect.height() * 0.30))
        self._draw_sensor_name(painter, name_rect, sensor_name, colors)

        self._draw_value_text(painter, 
                              rect.adjusted(rect.width() * 0.2, rect.height() * 0.4, -rect.width() * 0.2, -rect.height() * 0.1),
                              current_value_animated, unit, colors['text_color'], 
                              self._get_themed_color('gauge_text_outline_color', QColor('black')),
                              self._get_themed_color('high_contrast_text_color', QColor('white')), 
                              QFont(self._get_themed_font_family('font_family', 'Inter'), int(radius * 0.2)))
        painter.restore()

class AnalogFullGaugeDrawer(AnalogGaugeDrawer):
    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        logger.debug(f"  Drawing Analog Full Gauge for {self.parent_widget.objectName()}. Value: {current_value_animated}, Style: {gauge_style}")
        painter.save()

        center_x = rect.center().x()
        center_y = rect.center().y()
        radius_outer = min(rect.width(), rect.height()) / 2 * 0.95
        radius_inner = radius_outer * 0.75 

        path = QPainterPath()
        path.addEllipse(QRectF(center_x - radius_outer, center_y - radius_outer, radius_outer * 2, radius_outer * 2))
        self._apply_gauge_frame_and_style(painter, QRectF(center_x - radius_outer, center_y - radius_outer, radius_outer * 2, radius_outer * 2), path, colors['background'], colors['gauge_border_color'], colors['gauge_border_width'], colors['gauge_border_style'], gauge_style)

        arc_rect = QRectF(center_x - radius_outer, center_y - radius_outer, radius_outer * 2, radius_outer * 2)
        
        conical_gradient = QConicalGradient(center_x, center_y, 90)
        
        if max_value - min_value != 0:
            normalized_value = (current_value_animated - min_value) / (max_value - min_value)
        else:
            normalized_value = 0
            
        normalized_value = max(0.0, min(1.0, normalized_value))
        
        fill_color_q = self._get_themed_color('gauge_fill_normal', QColor('#87CEFA'))
        background_color_q = self._get_themed_color('gauge_background_normal', QColor('#F0F8FF'))

        conical_gradient.setColorAt(0, fill_color_q)
        conical_gradient.setColorAt(normalized_value, fill_color_q)
        conical_gradient.setColorAt(normalized_value + 0.001, background_color_q)
        conical_gradient.setColorAt(1, background_color_q)

        painter.setBrush(QBrush(conical_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawPie(arc_rect, 0 * 16, 360 * 16)

        painter.setBrush(QBrush(colors['background']))
        painter.drawEllipse(QPointF(center_x, center_y), int(radius_inner), int(radius_inner))

        self._draw_scale_and_labels(painter, center_x, center_y, radius_outer, colors['scale_color'], start_angle=90, span_angle=360, label_interval=30, label_start_angle_offset=0)

        if self.parent_widget._current_value is not None:
            self._draw_needle(painter, center_x, center_y, radius_outer, colors['needle_color'], 
                              current_value_animated, min_value, max_value, 
                              start_angle=90, span_angle=360, needle_type='full_circle_arrow')

        painter.setBrush(QBrush(colors['center_dot_color']))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(center_x, center_y), int(radius_inner * 0.15), int(radius_inner * 0.15))

        # --- Corrected Sensor Name Display ---
        name_rect_height = rect.height() * 0.15
        name_rect_width = rect.width() * 0.7
        name_rect = QRectF(0, 0, name_rect_width, name_rect_height)
        name_rect.moveCenter(QPointF(rect.center().x(), rect.y() + rect.height() * 0.30))
        self._draw_sensor_name(painter, name_rect, sensor_name, colors)

        self._draw_value_text(painter, 
                              rect.adjusted(rect.width() * 0.2, rect.height() * 0.4, -rect.width() * 0.2, -rect.height() * 0.1), 
                              current_value_animated, unit, colors['text_color'], 
                              self._get_themed_color('gauge_text_outline_color', QColor('black')),
                              self._get_themed_color('high_contrast_text_color', QColor('white')), 
                              QFont(self._get_themed_font_family('font_family', 'Inter'), int(radius_outer * 0.2 )))
        painter.restore()

class AnalogModernBasicGaugeDrawer(AnalogGaugeDrawer):
    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        logger.debug(f"  Drawing Analog Modern Basic Gauge for {self.parent_widget.objectName()}. Value: {current_value_animated}, Style: {gauge_style}")
        painter.save()

        center_x = rect.center().x()
        center_y = rect.center().y()
        radius = min(rect.width(), rect.height()) / 2 * 0.9 
        
        path = QPainterPath()
        path.addEllipse(QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2))
        self._apply_gauge_frame_and_style(painter, QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2), path, colors['background'], colors['gauge_border_color'], colors['gauge_border_width'], colors['gauge_border_style'], gauge_style)

        self._draw_scale_and_labels(painter, center_x, center_y, radius, colors['scale_color'], start_angle=225, span_angle=270, label_interval=20)

        if self.parent_widget._current_value is not None:
            self._draw_needle(painter, center_x, center_y, radius, colors['needle_color'], 
                              current_value_animated, min_value, max_value, 
                              start_angle=225, span_angle=270, needle_type='rectangle')

        painter.setBrush(QBrush(colors['center_dot_color']))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(center_x, center_y), int(radius * 0.1), int(radius * 0.1))

        # --- Corrected Sensor Name Display ---
        name_rect_height = rect.height() * 0.15
        name_rect_width = rect.width() * 0.7
        name_rect = QRectF(0, 0, name_rect_width, name_rect_height)
        name_rect.moveCenter(QPointF(rect.center().x(), rect.y() + rect.height() * 0.30))
        self._draw_sensor_name(painter, name_rect, sensor_name, colors)

        self._draw_value_text(painter, 
                              rect.adjusted(rect.width() * 0.2, rect.height() * 0.4, -rect.width() * 0.2, -rect.height() * 0.1),
                              current_value_animated, unit, colors['text_color'], 
                              self._get_themed_color('gauge_text_outline_color', QColor('black')),
                              self._get_themed_color('high_contrast_text_color', QColor('white')), 
                              QFont(self._get_themed_font_family('font_family', 'Inter'), int(radius * 0.2)))
        painter.restore()

class AnalogModernFullGaugeDrawer(AnalogGaugeDrawer):
    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        logger.debug(f"  Drawing Analog Modern Full Gauge for {self.parent_widget.objectName()}. Value: {current_value_animated}, Style: {gauge_style}")
        painter.save()

        center_x = rect.center().x()
        center_y = rect.center().y()
        radius_outer = min(rect.width(), rect.height()) / 2 * 0.95
        radius_inner = radius_outer * 0.75 

        path = QPainterPath()
        path.addEllipse(QRectF(center_x - radius_outer, center_y - radius_outer, radius_outer * 2, radius_outer * 2))
        self._apply_gauge_frame_and_style(painter, QRectF(center_x - radius_outer, center_y - radius_outer, radius_outer * 2, radius_outer * 2), path, colors['background'], colors['gauge_border_color'], colors['gauge_border_width'], colors['gauge_border_style'], gauge_style)

        arc_rect = QRectF(center_x - radius_outer, center_y - radius_outer, radius_outer * 2, radius_outer * 2)
        
        conical_gradient = QConicalGradient(center_x, center_y, 90)
        
        if max_value - min_value != 0:
            normalized_value = (current_value_animated - min_value) / (max_value - min_value)
        else:
            normalized_value = 0
            
        normalized_value = max(0.0, min(1.0, normalized_value))
        
        fill_color_q = self._get_themed_color('gauge_fill_normal', QColor('#87CEFA'))
        background_color_q = self._get_themed_color('gauge_background_normal', QColor('#F0F8FF'))

        conical_gradient.setColorAt(0, fill_color_q)
        conical_gradient.setColorAt(normalized_value, fill_color_q)
        conical_gradient.setColorAt(normalized_value + 0.001, background_color_q)
        conical_gradient.setColorAt(1, background_color_q)

        painter.setBrush(QBrush(conical_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawPie(arc_rect, 0 * 16, 360 * 16)

        painter.setBrush(QBrush(colors['background']))
        painter.drawEllipse(QPointF(center_x, center_y), int(radius_inner), int(radius_inner))

        self._draw_scale_and_labels(painter, center_x, center_y, radius_outer, colors['scale_color'], start_angle=90, span_angle=360, label_interval=30, label_start_angle_offset=0)

        if self.parent_widget._current_value is not None:
            self._draw_needle(painter, center_x, center_y, radius_outer, colors['needle_color'], 
                              current_value_animated, min_value, max_value, 
                              start_angle=90, span_angle=360, needle_type='full_circle_arrow')

        painter.setBrush(QBrush(colors['center_dot_color']))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(center_x, center_y), int(radius_inner * 0.15), int(radius_inner * 0.15))

        # --- Corrected Sensor Name Display ---
        name_rect_height = rect.height() * 0.15
        name_rect_width = rect.width() * 0.7
        name_rect = QRectF(0, 0, name_rect_width, name_rect_height)
        name_rect.moveCenter(QPointF(rect.center().x(), rect.y() + rect.height() * 0.30))
        self._draw_sensor_name(painter, name_rect, sensor_name, colors)

        self._draw_value_text(painter, 
                              rect.adjusted(rect.width() * 0.2, rect.height() * 0.4, -rect.width() * 0.2, -rect.height() * 0.1), 
                              current_value_animated, unit, colors['text_color'], 
                              self._get_themed_color('gauge_text_outline_color', QColor('black')),
                              self._get_themed_color('high_contrast_text_color', QColor('white')), 
                              QFont(self._get_themed_font_family('font_family', 'Inter'), int(radius_outer * 0.2 )))
        painter.restore()