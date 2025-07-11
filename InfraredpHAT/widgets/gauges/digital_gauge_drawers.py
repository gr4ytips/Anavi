# widgets/gauges/digital_gauge_drawers.py
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPainter, QBrush, QColor, QFont, QPainterPath
from .base_gauge_drawer import BaseGaugeDrawer
import logging

logger = logging.getLogger(__name__)

class DigitalClassicGaugeDrawer(BaseGaugeDrawer):
    #ef draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
    #  logger.debug(f"  Drawing Digital Classic Gauge for {self.parent_widget.objectName()}. Value: {current_value_animated}, Style: {gauge_style}")
    #   painter.save()

    #   # --- NEW: Call the helper to draw the name ---
    #   self._draw_sensor_name(painter, rect, sensor_name, colors) 

        
    #   path = QPainterPath()
    #   path.addRoundedRect(QRectF(rect), 5, 5)
    #   self._apply_gauge_frame_and_style(painter, QRectF(rect), path, colors['background'], colors['gauge_border_color'], colors['gauge_border_width'], colors['gauge_border_style'], gauge_style)

    #   self._draw_value_text(painter, rect, current_value_animated, unit, colors['text_color'], 
    #                         self._get_themed_color('gauge_text_outline_color', QColor('black')),
    #                         self._get_themed_color('high_contrast_text_color', QColor('white')),
    #                         QFont(self._get_themed_font_family('digital_font_family', "Digital-7"), int(rect.height() *  0.15)))
    #   painter.restore()

    
    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        logger.debug(f"  Drawing Digital Classic Gauge for {self.parent_widget.objectName()}. Value: {current_value_animated}, Style: {gauge_style}")
        painter.save()

        # Define the height for the sensor name display area.
        # This area will be positioned directly above the main gauge body.
        name_area_height_ratio = 0.20  # Allocate 20% of the total height for the sensor name
        name_area_height = rect.height() * name_area_height_ratio

        # 1. Create a rectangle for the sensor name, positioned at the top.
        # This rectangle starts at the original 'rect.y()' and has the calculated 'name_area_height'.
        sensor_name_display_rect = QRectF(rect.x(), rect.y(), rect.width(), name_area_height)

        # 2. Create the main gauge rectangle, which will be positioned below the sensor name.
        # Its 'y()' coordinate starts after the sensor name area, and its height is the remaining space.
        main_gauge_body_rect = QRectF(rect.x(), rect.y() + name_area_height,
                                    rect.width(), rect.height() - name_area_height)

        # Draw the sensor name above the main gauge rectangle
        self._draw_sensor_name(painter, sensor_name_display_rect, sensor_name, colors)

        # Draw the gauge frame and style for the main gauge body
        # The frame will encompass the 'main_gauge_body_rect'
        path = QPainterPath()
        path.addRoundedRect(QRectF(main_gauge_body_rect), 5, 5)
        self._apply_gauge_frame_and_style(painter, QRectF(main_gauge_body_rect), path, colors['background'], colors['gauge_border_color'], colors['gauge_border_width'], colors['gauge_border_style'], gauge_style)

        # Draw the sensor value text within the main gauge body rectangle
        # The sensor value will now be contained inside 'main_gauge_body_rect'
        self._draw_value_text(painter, main_gauge_body_rect, current_value_animated, unit, colors['text_color'],
                                self._get_themed_color('gauge_text_outline_color', QColor('black')),
                                self._get_themed_color('high_contrast_text_color', QColor('white')),
                                # Adjust font size to fit proportionally within the 'main_gauge_body_rect'
                                QFont(self._get_themed_font_family('digital_font_family', 'Digital-7'), int(main_gauge_body_rect.height() * 0.3)))
        painter.restore()

class DigitalSegmentedGaugeDrawer(BaseGaugeDrawer):
    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        logger.debug(f"  Drawing Digital Segmented Gauge for {self.parent_widget.objectName()}. Value: {current_value_animated}, Style: {gauge_style}")
        painter.save() 

        # --- NEW: Call the helper to draw the name ---
        self._draw_sensor_name(painter, rect, sensor_name, colors) 


        bg_rect = rect.adjusted(rect.width() * 0.05, rect.height() * 0.25, -rect.width() * 0.05, -rect.height() * 0.25)
        
        path = QPainterPath()
        path.addRoundedRect(QRectF(bg_rect), 5, 5) 
        self._apply_gauge_frame_and_style(painter, QRectF(bg_rect), path, colors['background'], colors['gauge_border_color'], colors['gauge_border_width'], colors['gauge_border_style'], gauge_style)

        seg_color = self._get_themed_color('digital_gauge_segment_color', colors['background'].darker(120)) 
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(seg_color))
        for i in range(3):
            painter.drawRect(int(bg_rect.x() + 5), int(bg_rect.y() + bg_rect.height()/4 * (i+1) - 2), int(bg_rect.width() - 10), 4)

        self._draw_value_text(painter, rect, current_value_animated, unit, colors['text_color'], 
                              self._get_themed_color('gauge_text_outline_color', QColor('black')),
                              self._get_themed_color('high_contrast_text_color', QColor('white')),
                              QFont(self._get_themed_font_family('digital_font_family', 'Digital-7'), int(rect.height() *  0.15)))

        painter.restore()
