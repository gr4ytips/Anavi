# widgets/gauges/base_gauge_drawer.py
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPainter, QBrush, QColor, QFont, QPen, QPainterPath, QFontMetrics, QLinearGradient, QTransform
import logging

logger = logging.getLogger(__name__)

METRIC_SYMBOLS = {
    'temperature': '🌡️',
    'humidity':    '💧',
    'pressure':    '💨',
    'altitude':    '⛰️',
    'light':       '💡'
}        


class BaseGaugeDrawer:
    """
    Base class for all gauge drawing logic. Provides common helper methods
    and an interface for drawing.
    """
    def __init__(self, parent_widget):
        self.parent_widget = parent_widget # Reference to the SensorDisplayWidget instance



    def _get_themed_color(self, key, default_value=None):
        return self.parent_widget._get_themed_color(key, default_value)

    def _get_themed_numeric_property(self, key, default_value):
        return self.parent_widget._get_themed_numeric_property(key, default_value)

    def _get_themed_string_property(self, key, default_value):
        return self.parent_widget._get_themed_string_property(key, default_value)

    def _get_themed_font_family(self, key, default_family):
        return self.parent_widget._get_themed_font_family(key, default_family)

    def _format_value(self, value):
        return self.parent_widget._format_value(value)
    
    # --- MODIFIED: Updated method to create compact name with symbol ---
    def _draw_sensor_name(self, painter, rect, name, colors):
        """
        Draws a shortened sensor name with a theme-aware symbol inside the specified rect.
        Draws the text and symbol in separate steps to allow for different colors.
        """
        painter.save()
        
        # --- Get required data ---
        sensor_category = self.parent_widget.sensor_category
        metric_type = self.parent_widget.metric_type.lower()
        
        theme_key = f"symbol_{metric_type}"
        default_symbol = self._get_themed_string_property('symbol_default', '⚫')
        symbol = self._get_themed_string_property(theme_key, default_symbol)
        
        # --- Setup font and metrics ---
        font_size = int(rect.width() / 14)
        if font_size < 8: font_size = 8
        
        font = QFont(self._get_themed_font_family('font_family', 'Inter'), font_size, QFont.Bold)
        painter.setFont(font)
        metrics = QFontMetrics(font)

        # --- NEW: Logic to draw text and symbol with different colors ---
        text_part = f"{sensor_category} "  # Note the trailing space
        symbol_part = symbol

        # Calculate total width to center the entire block
        total_width = metrics.horizontalAdvance(text_part + symbol_part)
        text_part_width = metrics.horizontalAdvance(text_part)
        
        # Calculate starting position
        current_x = rect.center().x() - (total_width / 2)
        # Use a fixed vertical position for simplicity
        text_y = rect.y() + metrics.ascent() + (rect.height() - metrics.height()) / 2

        # 1. Draw the text part (e.g., "BMP180") using the label color
        text_color = colors.get('label_color', QColor('black'))
        painter.setPen(text_color)
        painter.drawText(QPointF(current_x, text_y), text_part)

        # 2. Draw the symbol part (e.g., "🌡️") using the new symbol color
        # Falls back to the text color if 'symbol_color' is not in the theme
        symbol_color = self._get_themed_color('symbol_color', text_color)
        painter.setPen(symbol_color)
        painter.drawText(QPointF(current_x + text_part_width, text_y), symbol_part)
        
        painter.restore()

    def _apply_gauge_frame_and_style(self, painter, rect, path, bg_color, border_color, border_width, border_style, gauge_style):
        """
        Applies common gauge styles (shadows, highlights, gradients) to the gauge frame.
        This method draws the background and border based on the chosen style.
        """
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        pen = QPen(border_color, int(border_width), Qt.SolidLine if border_style == 'solid' else Qt.DashLine) 
        brush = QBrush(bg_color)

        if gauge_style == "Flat":
            pen.setWidth(int(self._get_themed_numeric_property('flat_gauge_border_width', 1)))
            pen.setStyle(Qt.SolidLine)
            brush = QBrush(self._get_themed_color('flat_gauge_background_color', bg_color))
        elif gauge_style == "Shadowed":
            shadow_offset = rect.width() * 0.02
            shadow_color = self._get_themed_color('shadowed_gauge_shadow_color', QColor(0, 0, 0, 80))
            painter.setBrush(QBrush(shadow_color))
            painter.setPen(Qt.NoPen)
            if isinstance(path, QPainterPath):
                translated_path = path.translated(shadow_offset, shadow_offset)
                painter.drawPath(translated_path)
            else: 
                painter.drawEllipse(rect.adjusted(shadow_offset, shadow_offset, shadow_offset, shadow_offset)) 
        elif gauge_style == "Heavy Border":
            pen.setWidth(int(self._get_themed_numeric_property('heavy_gauge_border_width', border_width * 2))) 
            pen.setColor(self._get_themed_color('heavy_gauge_border_color', border_color))
        elif gauge_style == "Gradient Fill":
            if rect.width() > 0 and rect.height() > 0 and isinstance(bg_color, QColor) and bg_color.isValid():
                gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
                gradient.setColorAt(0, bg_color.lighter(120) if bg_color.isValid() else QColor('lightgray'))
                gradient.setColorAt(1, bg_color.darker(120) if bg_color.isValid() else QColor('darkgray'))
                brush = QBrush(gradient)
            else: 
                brush = QBrush(bg_color if isinstance(bg_color, QColor) and bg_color.isValid() else QBrush(QColor('gray')))
        elif gauge_style == "Outline":
            brush = Qt.NoBrush
            pen.setWidth(int(self._get_themed_numeric_property('outline_gauge_border_width', border_width * 1.5))) 
            pen.setColor(self._get_themed_color('outline_gauge_color', border_color))
        elif gauge_style == "Raised":
            painter.setPen(QPen(self._get_themed_color('raised_gauge_highlight_color', QColor(255, 255, 255, 90)), 1.5))
            painter.drawArc(rect, 45 * 16, 180 * 16)
            painter.setPen(QPen(self._get_themed_color('raised_gauge_shadow_color', QColor(0, 0, 0, 40)), 1.5))
            painter.drawArc(rect, 225 * 16, 180 * 16)
        elif gauge_style == "Inset":
            painter.setPen(QPen(self._get_themed_color('inset_gauge_shadow_color', QColor(0, 0, 0, 40)), 1.5))
            painter.drawArc(rect, 45 * 16, 180 * 16)
            painter.setPen(QPen(self._get_themed_color('inset_gauge_highlight_color', QColor(255, 255, 255, 90)), 1.5))
            painter.drawArc(rect, 225 * 16, 180 * 16)
        elif gauge_style == "Vintage":
            inner_rect = rect.adjusted(4, 4, -4, -4)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(self._get_themed_color('vintage_gauge_border_color', border_color.darker(120)), 1))
            painter.drawEllipse(inner_rect) 
            brush = QBrush(self._get_themed_color('vintage_gauge_background_color', bg_color))
        elif gauge_style == "Clean":
            brush = QBrush(self._get_themed_color('clean_gauge_background_color', bg_color))
            pen = Qt.NoPen 
        elif gauge_style == "Subtle":
            brush = QBrush(self._get_themed_color('subtle_gauge_background_color', bg_color))
        elif gauge_style == "Fresh":
            brush = QBrush(self._get_themed_color('fresh_gauge_background_color', bg_color))
        elif gauge_style == "Bright":
            brush = QBrush(self._get_themed_color('bright_gauge_fill_color', bg_color)) 
            pen = Qt.NoPen 
        elif gauge_style == "Bold":
            pass 
        elif gauge_style == "Deep Shadow":
            shadow_offset = rect.width() * 0.02
            shadow_color1 = self._get_themed_color('deep_shadow_gauge_color1', QColor(0, 0, 0, 80))
            shadow_color2 = self._get_themed_color('deep_shadow_gauge_color2', QColor(0, 0, 0, 40))
            shadow_color3 = self._get_themed_color('deep_shadow_gauge_color3', QColor(0, 0, 0, 20))
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(shadow_color1))
            painter.drawPath(path.translated(shadow_offset * 3, shadow_offset * 3))
            painter.setBrush(QBrush(shadow_color2))
            painter.drawPath(path.translated(shadow_offset * 2, shadow_offset * 2))
            painter.setBrush(QBrush(shadow_color3))
            painter.drawPath(path.translated(shadow_offset, shadow_offset))
            
            painter.setBrush(brush)
            painter.setPen(pen)
            painter.drawPath(path)
            
            painter.restore() 
            return 

        painter.setBrush(brush)
        painter.setPen(pen)
        painter.drawPath(path)
        
        painter.restore()

    def _draw_value_text(self, painter, rect, value, unit, text_color, text_outline_color, high_contrast_text_color, font_obj):
        """Helper to draw the main value text with outline and shadow."""
        painter.save() 
        
        current_text_color = text_color
        if self.parent_widget._alert_state != "normal":
            current_text_color = self._get_themed_color('gauge_text_alert', text_color)
            
        painter.setFont(font_obj)
        painter.setPen(Qt.NoPen) 

        text_path = QPainterPath()
        metrics = QFontMetrics(font_obj)
        
        display_text = f"{self._format_value(value)}{unit}" if value is not None else "N/A"
        
        text_width = metrics.horizontalAdvance(display_text)
        text_height = metrics.height()
        text_rect = QRectF(rect.x() + (rect.width() - text_width) / 2, 
                           rect.y() + (rect.height() - text_height) / 2 + metrics.ascent(), 
                           text_width, text_height)
        
        text_path.addText(text_rect.x(), text_rect.y(), font_obj, display_text)

        painter.setPen(QPen(text_outline_color, 2))
        painter.drawPath(text_path)

        painter.setBrush(QBrush(current_text_color))
        painter.drawPath(text_path)

        painter.restore() 


    
    def _draw_na_text(self, painter, rect, text_color, font_obj, text_outline_color, high_contrast_text_color):
        """Draws 'N/A' text when sensor data is not available."""
        painter.save() 
        painter.setFont(font_obj)
        
        na_text_color = self._get_themed_color('label_color', QColor('#ECF0F1'))
        outline_color = self._get_themed_color('gauge_text_outline_color', QColor('black'))

        painter.setPen(QPen(outline_color, 2))
        text_path = QPainterPath()
        metrics = QFontMetrics(font_obj)
        text_path.addText(rect.x() + (rect.width() - metrics.horizontalAdvance("N/A")) / 2, 
                          rect.y() + (rect.height() - metrics.height()) / 2 + metrics.ascent(), 
                          font_obj, "N/A")
        painter.drawPath(text_path)

        painter.setPen(QPen(na_text_color, 1))
        painter.drawText(rect, Qt.AlignCenter, "N/A")
        painter.restore() 

    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        """Abstract method to be implemented by concrete gauge drawers."""
        raise NotImplementedError("Each gauge drawer must implement the 'draw' method.")
    
   
    