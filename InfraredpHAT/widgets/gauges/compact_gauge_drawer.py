# widgets/gauges/compact_gauge_drawer.py
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QBrush, QColor, QFont, QPainterPath, QLinearGradient
from .base_gauge_drawer import BaseGaugeDrawer
import logging

logger = logging.getLogger(__name__)

class CompactGaugeDrawer(BaseGaugeDrawer):
    #def draw(self, painter, rect, current_value_animated, min_value, max_value, unit, gauge_style, colors):
    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        logger.debug(f"  Drawing Compact Gauge for {self.parent_widget.objectName()}. Value: {current_value_animated}, Style: {gauge_style}")
        painter.save()     
    
        # --- NEW: Call the helper to draw the name ---
        self._draw_sensor_name(painter, rect, sensor_name, colors) 

        rounded_rect = rect.adjusted(rect.width() * 0.1, rect.height() * 0.3, -rect.width() * 0.1, -rect.height() * 0.3)
        radius = rounded_rect.height() / 2

        path = QPainterPath()
        path.addRoundedRect(QRectF(rounded_rect), radius, radius) 
        self._apply_gauge_frame_and_style(painter, QRectF(rounded_rect), path, colors['background'], colors['gauge_border_color'], colors['gauge_border_width'], colors['gauge_border_style'], gauge_style)

        if current_value_animated is not None and not self.parent_widget._na_state:
            if max_value - min_value != 0:
                fill_ratio = (current_value_animated - min_value) / (max_value - min_value)
            else:
                fill_ratio = 0
            fill_ratio = max(0.0, min(1.0, fill_ratio))
            
            fill_width = rounded_rect.width() * fill_ratio
            fill_rect = QRectF(rounded_rect.left(), rounded_rect.top(), fill_width, rounded_rect.height())

            value_fill_brush = QBrush(colors['fill_color'])
            if gauge_style == "Gradient Fill":
                value_gradient = QLinearGradient(fill_rect.topLeft(), fill_rect.bottomRight())
                value_gradient.setColorAt(0, colors['fill_color'].lighter(150))
                value_gradient.setColorAt(1, colors['fill_color'])
                value_fill_brush = QBrush(value_gradient)

            painter.setPen(Qt.NoPen)
            painter.setBrush(value_fill_brush)
            painter.drawRoundedRect(fill_rect, radius, radius)

            self._draw_value_text(painter, rounded_rect, current_value_animated, unit, colors['text_color'], 
                                  self._get_themed_color('gauge_text_outline_color', QColor('black')), 
                                  self._get_themed_color('high_contrast_text_color', QColor('white')), 
                                  QFont(self._get_themed_font_family('font_family', 'Inter'), int(rect.width() / 9)))
        else:
            self._draw_na_text(painter, rounded_rect, colors['text_color'], 
                               QFont(self._get_themed_font_family('font_family', 'Inter'), int(rect.width() / 9)), 
                               self._get_themed_color('gauge_text_outline_color', QColor('black')), 
                               self._get_themed_color('high_contrast_text_color', QColor('white')))

        painter.restore()