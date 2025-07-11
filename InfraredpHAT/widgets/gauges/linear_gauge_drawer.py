# widgets/gauges/linear_gauge_drawer.py
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QBrush, QColor, QFont, QPainterPath
from .base_gauge_drawer import BaseGaugeDrawer
import logging

logger = logging.getLogger(__name__)

class LinearGaugeDrawer(BaseGaugeDrawer):
    def __init__(self, parent_widget):
        super().__init__(parent_widget)
        logger.debug(f"LinearGaugeDrawer initialized for {parent_widget.objectName()}")

    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        logger.debug(f"  Drawing Linear Gauge for {self.parent_widget.objectName()}. Value: {current_value_animated}, Style: {gauge_style}")
        painter.save()

        # The 'rect' parameter now represents the ENTIRE drawing area allocated for
        # both the sensor name and the linear gauge body.

        # Define height ratios for distributing space within the 'rect'
        sensor_name_area_ratio = 0.20 # 20% of 'rect' height for the sensor name
        gauge_body_area_ratio = 1.0 - sensor_name_area_ratio # Remaining 80% for the gauge body

        # 1. Create a sub-rectangle for the sensor name at the top portion of the 'rect'.
        sensor_name_drawing_rect = QRectF(rect.x(), rect.y(),
                                          rect.width(), rect.height() * sensor_name_area_ratio)

        # 2. Create a sub-rectangle for the main linear gauge body (including values).
        # This rectangle starts below the sensor name area.
        gauge_body_drawing_rect = QRectF(rect.x(), rect.y() + rect.height() * sensor_name_area_ratio,
                                         rect.width(), rect.height() * gauge_body_area_ratio)

        # --- Draw the sensor name within its allocated space at the top of 'rect' ---
        # The sensor name drawing is now confined to 'sensor_name_drawing_rect'.
        self._draw_sensor_name(painter, sensor_name_drawing_rect, sensor_name, colors)

        # --- Draw the linear gauge elements within its allocated space ('gauge_body_drawing_rect') ---
        # The frame and fill will now conform to the 'gauge_body_drawing_rect'.
        path = QPainterPath()
        path.addRoundedRect(QRectF(gauge_body_drawing_rect), 5, 5) # Gauge frame uses its new sub-rect
        self._apply_gauge_frame_and_style(painter, QRectF(gauge_body_drawing_rect), path,
                                           colors['background'], colors['gauge_border_color'],
                                           colors['gauge_border_width'], colors['gauge_border_style'], gauge_style)

        # Draw the fill level of the gauge, confined to 'gauge_body_drawing_rect'
        if max_value > min_value:
            fill_width = int(gauge_body_drawing_rect.width() * ((current_value_animated - min_value) / (max_value - min_value)))
            fill_width = max(0, min(gauge_body_drawing_rect.width(), fill_width))
            # Fill rect's Y and height are relative to gauge_body_drawing_rect
            fill_rect = QRectF(gauge_body_drawing_rect.x(), gauge_body_drawing_rect.y(),
                               fill_width, gauge_body_drawing_rect.height())
            painter.setBrush(QBrush(colors['fill_color']))
            painter.setPen(Qt.NoPen)
            painter.drawRect(fill_rect)

        # --- Draw the sensor value text within 'gauge_body_drawing_rect' ---
        # The sensor value text is also confined to 'gauge_body_drawing_rect'.
        self._draw_value_text(painter, gauge_body_drawing_rect, current_value_animated, unit,
                              colors['text_color'],
                              self._get_themed_color('gauge_text_outline_color', QColor('black')),
                              self._get_themed_color('high_contrast_text_color', QColor('white')),
                              # Font size adjusted relative to gauge_body_drawing_rect's height.
                              # To maintain the proportion of original `rect.height() / 6`,
                              # this is (gauge_body_drawing_rect.height() / gauge_body_area_ratio) / 6
                              # = gauge_body_drawing_rect.height() / (6 * gauge_body_area_ratio)
                              # = gauge_body_drawing_rect.height() / (6 * 0.8) = gauge_body_drawing_rect.height() / 4.8
                              QFont(self._get_themed_font_family('font_family', 'Inter'),
                                    int(gauge_body_drawing_rect.height() / 6.8)))
        painter.restore()