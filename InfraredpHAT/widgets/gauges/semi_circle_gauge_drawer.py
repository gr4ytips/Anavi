# widgets/gauges/semi_circle_gauge_drawer.py
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QBrush, QColor, QFont, QPainterPath
from .base_gauge_drawer import BaseGaugeDrawer
import logging

logger = logging.getLogger(__name__)

class SemiCircleGaugeDrawer(BaseGaugeDrawer):
    def __init__(self, parent_widget):
        super().__init__(parent_widget)
        logger.debug(f"SemiCircleGaugeDrawer initialized for {parent_widget.objectName()}")

    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        logger.debug(f"  Drawing Semi-Circle Gauge for {self.parent_widget.objectName()}. Value: {current_value_animated}, Style: {gauge_style}")
        painter.save()

        # The 'rect' parameter represents the ENTIRE drawing area allocated for
        # both the sensor name and the semi-circle gauge body.

        # Define height ratios for distributing space within the 'rect'
        sensor_name_area_ratio = 0.20 # 20% of 'rect' height for the sensor name
        gauge_body_area_ratio = 1.0 - sensor_name_area_ratio # Remaining 80% for the gauge body

        # 1. Create a sub-rectangle for the sensor name at the top portion of the 'rect'.
        sensor_name_drawing_rect = QRectF(rect.x(), rect.y(),
                                          rect.width(), rect.height() * sensor_name_area_ratio)

        # 2. Create a sub-rectangle for the main semi-circle gauge body (including values).
        # This rectangle starts below the sensor name area and is the new base for all gauge elements.
        gauge_body_drawing_rect = QRectF(rect.x(), rect.y() + rect.height() * sensor_name_area_ratio,
                                         rect.width(), rect.height() * gauge_body_area_ratio)

        # --- Draw the sensor name within its allocated space at the top of 'rect' ---
        self._draw_sensor_name(painter, sensor_name_drawing_rect, sensor_name, colors)

        # --- Draw the semi-circle gauge elements within its allocated space ('gauge_body_drawing_rect') ---
        # All semi-circle geometry calculations must now be relative to 'gauge_body_drawing_rect'.

        # Calculate the ideal diameter for the semi-circle based on the gauge_body_drawing_rect.
        # The semi-circle itself has a height of diameter / 2.
        # We ensure it fits both horizontally and vertically, with a slight reduction factor for padding.
        
        # Max diameter considering width: gauge_body_drawing_rect.width()
        # Max diameter considering height (semicircle height is diameter/2): gauge_body_drawing_rect.height() * 2
        
        # Take the minimum of these two, then apply a reduction factor to prevent overlap and provide padding.
        diameter = min(gauge_body_drawing_rect.width(), gauge_body_drawing_rect.height() * 2) * 0.9 

        # Calculate the X position to center the semi-circle horizontally within gauge_body_drawing_rect.
        arc_rect_x = gauge_body_drawing_rect.center().x() - diameter / 2

        # Calculate the Y position for the arc_rect (the bounding box of the full circle).
        # The semi-circle is drawn as the top half of the full circle (0 to 180 degrees).
        # Its actual height is 'diameter / 2'.
        # To align its base with the bottom of 'gauge_body_drawing_rect', 
        # its bounding box's Y-coordinate (arc_rect_y) should be:
        # gauge_body_drawing_rect.bottom() - diameter
        arc_rect_y = gauge_body_drawing_rect.bottom() - diameter
        
        arc_rect = QRectF(arc_rect_x, arc_rect_y, diameter, diameter)

        path = QPainterPath()
        path.arcTo(arc_rect, 0, 180)
        path.lineTo(arc_rect.bottomLeft())
        path.lineTo(arc_rect.bottomRight())
        path.closeSubpath()

        self._apply_gauge_frame_and_style(painter, arc_rect, path,
                                           colors['background'], colors['gauge_border_color'],
                                           colors['gauge_border_width'], colors['gauge_border_style'], gauge_style)

        if max_value > min_value:
            angle_range = 180
            fill_angle = angle_range * ((current_value_animated - min_value) / (max_value - min_value))
            fill_angle = max(0, min(angle_range, fill_angle))

            painter.setBrush(QBrush(colors['fill_color']))
            painter.setPen(Qt.NoPen)
            painter.drawPie(arc_rect, (angle_range - fill_angle) * 16, fill_angle * 16)

        # --- Draw the sensor value text within 'gauge_body_drawing_rect' ---
        # Position the value text roughly in the center of the semi-circle's drawn area.
        # text_rect will be a sub-rectangle within the semi-circle's visual space.
        text_rect_width = diameter * 0.8 # Some portion of diameter for text width
        text_rect_height = diameter * 0.4 # Some portion of diameter for text height

        text_rect_x = arc_rect.center().x() - text_rect_width / 2
        # Position text_rect_y so it's centered vertically within the semi-circle's height.
        # The semi-circle spans from arc_rect.y() to arc_rect.y() + diameter/2.
        text_rect_y = arc_rect.y() + (diameter / 2 - text_rect_height) / 2 

        text_rect = QRectF(text_rect_x, text_rect_y, text_rect_width, text_rect_height)
        
        self._draw_value_text(painter, text_rect, current_value_animated, unit,
                              colors['text_color'],
                              self._get_themed_color('gauge_text_outline_color', QColor('black')),
                              self._get_themed_color('high_contrast_text_color', QColor('white')),
                              # Font size based on the new text_rect's height.
                              QFont(self._get_themed_font_family('font_family', 'Inter'), int(text_rect.height() * 0.3)))
        painter.restore()