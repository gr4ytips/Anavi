# widgets/gauges/custom_progress_bar_drawer.py
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPainter, QBrush, QColor, QFont, QPen, QPainterPath, QFontMetrics, QLinearGradient, QTransform 
import logging
import math

from .base_gauge_drawer import BaseGaugeDrawer

logger = logging.getLogger(__name__)

class CustomProgressBarDrawer(BaseGaugeDrawer):
    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        logger.debug(f"  Drawing Custom Progress Bar for {self.parent_widget.objectName()}. Value: {current_value_animated}, Style: {gauge_style}")
        painter.save() # Main save state for the draw method

        # 1. Define a percentage of the height for the title area (e.g., 20%).
        title_height = rect.height() * 0.20

        # 2. Create a specific rectangle for the title at the top of the widget.
        #    We adjust it slightly for better padding.
        title_padding = 5
        title_rect = QRectF(rect.x(), rect.y(), rect.width(), title_height - title_padding)

         # 3. Create a separate rectangle for the progress bar area below the title.
        bar_rect = QRectF(rect.x(), rect.y() + title_height, rect.width(), rect.height() - title_height)

        # 4. Draw the sensor name within the calculated title rectangle.
        self._draw_sensor_name(painter, title_rect, sensor_name, colors)

        painter.setRenderHint(QPainter.Antialiasing)

        logger.debug(f"  draw: Input rect: {rect.x():.1f},{rect.y():.1f},{rect.width():.1f},{rect.height():.1f}")
        logger.debug(f"  draw: Min/Max values: {min_value:.1f}/{max_value:.1f}")
        logger.debug(f"  draw: Gauge Style: {gauge_style}")

        # Define a desired thickness for the custom progress bar itself
        # Adjust this value to control the bar's thickness
        bar_thickness_ratio = 0.3 # Reduced from 0.5 to make it thinner. Experiment with 0.2 if needed.

        # Calculate the actual drawing rectangle for the progress bar (trough and chunk)
        custom_bar_rect = QRectF(bar_rect)
        is_horizontal = self.parent_widget._gauge_type == "Progress Bar - Custom Horizontal"

        if is_horizontal:
            # For horizontal bar, reduce height
            target_height = rect.height() * bar_thickness_ratio
            margin_y = (rect.height() - target_height) / 2
            custom_bar_rect = QRectF(rect.x(), rect.y() + margin_y, rect.width(), target_height)
        else: # Vertical
            # For vertical bar, reduce width
            target_width = rect.width() * bar_thickness_ratio
            margin_x = (rect.width() - target_width) / 2
            custom_bar_rect = QRectF(rect.x() + margin_x, rect.y(), target_width, rect.height())

        logger.debug(f"  draw: Custom bar draw rect: {custom_bar_rect.x():.1f},{custom_bar_rect.y():.1f},{custom_bar_rect.width():.1f},{custom_bar_rect.height():.1f}")

        # --- 1. Draw the Trough (Background of the Progress Bar) ---
        trough_rect = custom_bar_rect
        trough_border_radius = self._get_themed_numeric_property('progressbar_border_radius', 8)
        trough_border_width = self._get_themed_numeric_property('progressbar_border_width', 1)
        trough_border_color = self._get_themed_color('progressbar_border_color', QColor('#424242'))
        
        trough_path = QPainterPath()
        trough_path.addRoundedRect(trough_rect, trough_border_radius, trough_border_radius)

        # Apply standard pen/brush, then apply style overrides
        # Initialize with a default QPen, which is always a QPen object
        current_trough_pen_raw = QPen(trough_border_color, trough_border_width, Qt.SolidLine) 
        current_trough_brush_raw = QBrush(colors['background']) # Base trough background color (a QBrush object)

        # --- Apply Gauge Styles to Trough ---
        if gauge_style == "Flat":
            current_trough_pen_raw = Qt.NoPen # This is a Qt.PenStyle enum
            current_trough_brush_raw = QBrush(self._get_themed_color('flat_gauge_background_color', colors['background']))
        elif gauge_style == "Gradient Fill":
            if trough_rect.width() > 0 and trough_rect.height() > 0 and isinstance(colors['background'], QColor) and colors['background'].isValid():
                gradient = QLinearGradient(trough_rect.topLeft(), trough_rect.bottomRight())
                base_bg_color = colors['background']
                gradient.setColorAt(0, base_bg_color.lighter(120) if base_bg_color.isValid() else QColor('lightgray'))
                gradient.setColorAt(1, base_bg_color.darker(120) if base_bg_color.isValid() else QColor('darkgray'))
                current_trough_brush_raw = QBrush(gradient)
            else:
                current_trough_brush_raw = QBrush(colors['background'] if isinstance(colors['background'], QColor) and colors['background'].isValid() else QBrush(QColor('gray')))
        elif gauge_style == "Outline":
            current_trough_brush_raw = Qt.NoBrush # This is a Qt.BrushStyle enum
            current_trough_pen_raw = QPen(self._get_themed_color('outline_gauge_color', trough_border_color), self._get_themed_numeric_property('outline_gauge_border_width', trough_border_width * 1.5), Qt.SolidLine)
        elif gauge_style == "Heavy Border":
            current_trough_pen_raw = QPen(self._get_themed_color('heavy_gauge_border_color', trough_border_color), self._get_themed_numeric_property('heavy_gauge_border_width', trough_border_width * 2), Qt.SolidLine)
        elif gauge_style == "Clean":
            current_trough_pen_raw = Qt.NoPen # This is a Qt.PenStyle enum
            current_trough_brush_raw = self._get_themed_color('clean_gauge_background_color', colors['background'])
        elif gauge_style == "Subtle":
            current_trough_brush_raw = self._get_themed_color('subtle_gauge_background_color', colors['background'])
        elif gauge_style == "Fresh":
            current_trough_brush_raw = self._get_themed_color('fresh_gauge_background_color', colors['background'])
            current_trough_pen_raw = Qt.NoPen # This is a Qt.PenStyle enum
        elif gauge_style == "Bright":
            current_trough_brush_raw = self._get_themed_color('bright_gauge_background_color', colors['background'])
            current_trough_pen_raw = Qt.NoPen # This is a Qt.PenStyle enum
        elif gauge_style == "Vintage":
            current_trough_brush_raw = self._get_themed_color('vintage_gauge_background_color', colors['background'])
            current_trough_pen_raw = QPen(self._get_themed_color('vintage_gauge_border_color', trough_border_color.darker(120)), trough_border_width, Qt.SolidLine)
        elif gauge_style == "Raised" or gauge_style == "Inset":
            pass
        elif gauge_style == "Bold":
            pass
        elif gauge_style == "Full":
            pass
        elif gauge_style == "Minimal":
            current_trough_pen_raw = Qt.NoPen # This is a Qt.PenStyle enum
            current_trough_brush_raw = colors['background']
        # --- End of Style Application for Trough Background/Border ---

        # --- FIX: Ensure current_trough_pen is a QPen object BEFORE using its methods ---
        # This prevents 'PenStyle' object has no attribute 'color'
        current_trough_pen = QPen() # Initialize as an empty QPen object
        if isinstance(current_trough_pen_raw, QPen):
            current_trough_pen = current_trough_pen_raw
        elif current_trough_pen_raw == Qt.NoPen:
            current_trough_pen = QPen(Qt.NoPen) # Wrap the enum in a QPen object
        else: # Fallback for any other unexpected type
            current_trough_pen = QPen(current_trough_pen_raw) # Attempt to convert
            logger.warning(f"  draw: current_trough_pen raw value was unexpected type {type(current_trough_pen_raw)}. Attempting conversion to QPen.")
        
        painter.setPen(current_trough_pen) # Set the now guaranteed QPen object
        # --- END FIX ---

        # --- FIX: Robust QColor creation for transparent trough color (final version) ---
        base_color_for_transparent_trough = QColor('gray') # Default fallback
        if isinstance(current_trough_brush_raw, QBrush): # Check the raw brush type
            if current_trough_brush_raw.style() == Qt.SolidPattern and current_trough_brush_raw.color().isValid():
                base_color_for_transparent_trough = current_trough_brush_raw.color()
            elif isinstance(colors['background'], QColor) and colors['background'].isValid():
                base_color_for_transparent_trough = colors['background']
        elif isinstance(current_trough_brush_raw, QColor) and current_trough_brush_raw.isValid(): # If raw was just a QColor
            base_color_for_transparent_trough = current_trough_brush_raw
        else: # Fallback if current_trough_brush_raw is an enum like Qt.NoBrush or other unexpected type
            if isinstance(colors['background'], QColor) and colors['background'].isValid():
                base_color_for_transparent_trough = colors['background']

        trough_bg_color_transparent = QColor(
            base_color_for_transparent_trough.red(), 
            base_color_for_transparent_trough.green(), 
            base_color_for_transparent_trough.blue(), 
            100 # Alpha set to 100 (out of 255) for semi-transparency
        )
        painter.setBrush(QBrush(trough_bg_color_transparent)) 
        # --- END FIX ---

        painter.drawPath(trough_path)
        # The line below current_trough_pen.color() will now be safe because current_trough_pen is a QPen object
        logger.debug(f"  draw: Trough drawn. Rect: {trough_rect.x():.1f},{trough_rect.y():.1f},{trough_rect.width():.1f},{trough_rect.height():.1f}, BG Color (transparent): {trough_bg_color_transparent.name()}, Border Color: {current_trough_pen.color().name()}")

        # --- Handle "Deep Shadow" style for the full bar outline (draws behind trough) ---
        if gauge_style == "Deep Shadow":
            shadow_offset = trough_rect.width() * 0.02
            shadow_color1 = self._get_themed_color('deep_shadow_gauge_color1', QColor(0, 0, 0, 120))
            shadow_color2 = self._get_themed_color('deep_shadow_gauge_color2', QColor(0, 0, 0, 70))
            shadow_color3 = self._get_themed_color('deep_shadow_gauge_color3', QColor(0, 0, 0, 20))
            
            painter.setPen(Qt.NoPen)
            shadow_trough_path = QPainterPath()
            shadow_trough_path.addRoundedRect(trough_rect, trough_border_radius, trough_border_radius)

            painter.setBrush(QBrush(shadow_color1))
            painter.drawPath(shadow_trough_path.translated(shadow_offset * 3, shadow_offset * 3))
            painter.setBrush(QBrush(shadow_color2))
            painter.drawPath(shadow_trough_path.translated(shadow_offset * 2, shadow_offset * 2))
            painter.setBrush(QBrush(shadow_color3))
            painter.drawPath(shadow_trough_path.translated(shadow_offset, shadow_offset))
            logger.debug(f"  draw: Deep Shadow drawn for trough.")
            
        # --- 2. Draw the Chunk (Filled Part) ---
        if max_value - min_value != 0:
            normalized_value = (current_value_animated - min_value) / (max_value - min_value)
        else:
            normalized_value = 0.0
        normalized_value = max(0.0, min(1.0, normalized_value))

        logger.debug(f"  draw: Normalized value: {normalized_value:.2f}")

        current_fill_color = colors['fill_color'] # Base fill color for chunk
        if self.parent_widget._alert_state == "critical":
            current_fill_color = colors['critical_color']
        elif self.parent_widget._alert_state == "warning":
            current_fill_color = colors['warning_color']

        # --- Apply Gauge Styles to Chunk Fill ---
        current_fill_brush_raw = current_fill_color # Use raw color for base
        # This will be converted to QBrush object with transparent alpha later

        if gauge_style == "Gradient Fill": # Applies to chunk as well
             if trough_rect.width() > 0 and trough_rect.height() > 0 and isinstance(current_fill_color, QColor) and current_fill_color.isValid():
                gradient = QLinearGradient(trough_rect.topLeft(), trough_rect.bottomRight())
                gradient.setColorAt(0, current_fill_color.lighter(150) if current_fill_color.isValid() else QColor('lightgray'))
                gradient.setColorAt(1, current_fill_color.darker(120) if current_fill_color.isValid() else QColor('darkgray'))
                current_fill_brush_raw = QBrush(gradient)
             else:
                current_fill_brush_raw = QBrush(current_fill_color if isinstance(current_fill_color, QColor) and current_fill_color.isValid() else QBrush(QColor('gray')))
        elif gauge_style == "Fresh":
            current_fill_brush_raw = self._get_themed_color('fresh_gauge_fill_color', current_fill_color)
        elif gauge_style == "Bright":
            current_fill_brush_raw = self._get_themed_color('bright_gauge_fill_color', current_fill_color)
        elif gauge_style == "Bold":
            current_fill_brush_raw = self._get_themed_color('bold_gauge_fill_color', current_fill_color)
        elif gauge_style == "Subtle":
            current_fill_brush_raw = self._get_themed_color('subtle_gauge_fill_color', current_fill_color)
        elif gauge_style == "Vintage":
            current_fill_brush_raw = self._get_themed_color('vintage_gauge_fill_color', current_fill_color)
        elif gauge_style == "Clean":
            current_fill_brush_raw = self._get_themed_color('clean_gauge_fill_color', current_fill_color)
        elif gauge_style == "Outline": # For Outline style, the chunk itself should have no fill.
            current_fill_brush_raw = Qt.NoBrush # This is the problematic assignment if not wrapped in QBrush()
        # --- End of Style Application for Chunk Fill ---


        painter.setPen(Qt.NoPen)
        
        # --- FIX: Robust QBrush creation from current_fill_brush_raw for current_fill_brush ---
        current_fill_brush = QBrush() # Initialize as empty QBrush
        if isinstance(current_fill_brush_raw, QBrush): # If already a QBrush
            current_fill_brush = current_fill_brush_raw
        elif isinstance(current_fill_brush_raw, QColor): # If just a QColor
            current_fill_brush = QBrush(current_fill_brush_raw)
        elif current_fill_brush_raw == Qt.NoBrush: # If the specific enum Qt.NoBrush
            current_fill_brush = QBrush(Qt.NoBrush)
        else: # Fallback for any other unexpected type
            current_fill_brush = QBrush(QColor(current_fill_brush_raw) if isinstance(current_fill_brush_raw, str) else QColor('gray'))
            logger.warning(f"  draw: Fill brush raw value was unexpected type {type(current_fill_brush_raw)}. Defaulting to gray brush.")
        
        # Now, current_fill_brush is guaranteed to be a QBrush object.
        # Proceed with transparency check on this guaranteed QBrush object.
        base_color_for_transparent_fill = QColor('gray') # Default fallback
        if isinstance(current_fill_brush, QBrush): # Should always be true now
            if current_fill_brush.style() == Qt.SolidPattern and current_fill_brush.color().isValid():
                base_color_for_transparent_fill = current_fill_brush.color()
            elif isinstance(current_fill_color, QColor) and current_fill_color.isValid(): 
                base_color_for_transparent_fill = current_fill_color
        else: # Fallback if current_fill_brush is unexpectedly not a QBrush (shouldn't happen now)
            if isinstance(current_fill_color, QColor) and current_fill_color.isValid():
                base_color_for_transparent_fill = current_fill_color

        fill_color_transparent = QColor(
            base_color_for_transparent_fill.red(), 
            base_color_for_transparent_fill.green(), 
            base_color_for_transparent_fill.blue(), 
            100 # Alpha set to 100 (out of 255) for semi-transparency
        )
        if current_fill_brush.style() == Qt.SolidPattern:
             painter.setBrush(QBrush(fill_color_transparent))
        else:
             painter.setBrush(current_fill_brush) # Use the original (possibly gradient) brush
        # --- END FIX ---

        logger.debug(f"  draw: Is Custom Progress Bar Horizontal? {is_horizontal}")

        fill_chunk_rect = QRectF()
        if is_horizontal:
            fill_width = trough_rect.width() * normalized_value
            fill_chunk_rect = QRectF(trough_rect.x(), trough_rect.y(), fill_width, trough_rect.height())
        else: # Vertical
            fill_height = trough_rect.height() * normalized_value
            fill_chunk_rect = QRectF(trough_rect.x(), trough_rect.y() + trough_rect.height() - fill_height, trough_rect.width(), trough_rect.height())
        
        logger.debug(f"  draw: Fill chunk rect: {fill_chunk_rect.x():.1f},{fill_chunk_rect.y():.1f},{fill_chunk_rect.width():.1f},{fill_chunk_rect.height():.1f} with color (transparent if solid): {fill_color_transparent.name() if current_fill_brush.style() == Qt.SolidPattern else 'Gradient'}")
        
        painter.setClipPath(trough_path)
        painter.drawRect(fill_chunk_rect)
        painter.setClipping(False)


        # --- 3. Draw Text Overlay ---
        self._draw_progress_bar_text_overlay(painter, custom_bar_rect, Qt.Horizontal if is_horizontal else Qt.Vertical, colors)

        # --- 4. Draw Threshold Lines ---
        threshold_line_color = self._get_themed_color('gauge_critical_color', QColor('red')) 
        self._draw_progress_bar_threshold_lines(painter, custom_bar_rect, is_horizontal, threshold_line_color)

        painter.restore() # Main restore state
    def _draw_progress_bar_text_overlay(self, painter, bar_rect, orientation, colors):
        """
        Draws the value text as an overlay on a QProgressBar.
        The text changes color based on whether it's over the "filled" or "unfilled" portion.
        For vertical orientation, the text is rotated.
        Includes conditional font size adjustment for pressure.
        """
        logger.debug(f"  Text Overlay: Drawing Progress Bar Text Overlay. Value: {self.parent_widget._current_value}, Orientation: {orientation}") 
        painter.save()

        current_value = self.parent_widget._current_value
        is_na = self.parent_widget._na_state
        min_value = self.parent_widget._min_value
        max_value = self.parent_widget._max_value
        unit = self.parent_widget.unit
        is_alert = self.parent_widget._alert_state != "normal"

        if current_value is None or is_na:
            self._draw_na_text(painter, bar_rect, self._get_themed_color('label_color', QColor('white')), 
                               QFont(self._get_themed_font_family('font_family', 'Inter'), int(min(bar_rect.width(), bar_rect.height()) * 0.5)))
            painter.restore()
            return

        precision_setting_str = self.parent_widget.main_window.settings_manager.get_setting(
            f'Precision_{self.parent_widget.sensor_category}', self.parent_widget.metric_type, fallback="2"
        )
        try:
            precision_setting = int(precision_setting_str)
        except (ValueError, TypeError):
            precision_setting = 2 # Fallback if conversion fails
            logger.warning(f"Failed to convert precision setting '{precision_setting_str}' to int. Using fallback 2.")

        formatted_value = f"{current_value:.{precision_setting}f}{unit}"
        logger.debug(f"  Text Overlay: Formatted value: '{formatted_value}'.")
        
        #font_size = int(min(bar_rect.width(), bar_rect.height()) * 0.3) 
        #logger.debug(f"  Text Overlay: Initial font size: {font_size}.")


         # Conditionally set the font scaling factor based on the metric type
        if self.parent_widget.metric_type in ['pressure', 'altitude']:
            # Use a smaller scaling factor (e.g., 0.3) for these specific metrics
            font_scaling_factor = 0.2
        else:
            # Use a larger, default factor for all other metrics
            font_scaling_factor = 0.3
            
        font_size = int(min(bar_rect.width(), bar_rect.height()) * font_scaling_factor) 
        logger.debug(f"  Text Overlay: Initial font size: {font_size}.")


        temp_font = QFont(self._get_themed_font_family('font_family', "Inter"), font_size, QFont.Bold)
        temp_metrics = QFontMetrics(temp_font)
        text_width_at_current_font = temp_metrics.horizontalAdvance(formatted_value)
        text_height_at_current_font = temp_metrics.height()

        if orientation == Qt.Vertical:
            available_length_for_text = bar_rect.height()
            available_thickness_for_text = bar_rect.width()
            
            if text_width_at_current_font > available_length_for_text * 0.9 or \
               text_height_at_current_font > available_thickness_for_text * 0.9:
                scale_factor_length = (available_length_for_text * 0.9) / text_width_at_current_font if text_width_at_current_font else 1
                scale_factor_thickness = (available_thickness_for_text * 0.9) / text_height_at_current_font if text_height_at_current_font else 1
                
                font_size = int(font_size * min(scale_factor_length, scale_factor_thickness))
                font_size = max(8, font_size) # Ensure minimum font size
                logger.debug(f"  Text Overlay: Vertical Text font size adjusted for {formatted_value}. New size: {font_size}.")
        else: # Horizontal
            if text_width_at_current_font > bar_rect.width() * 0.9: 
                font_size = int(font_size * (bar_rect.width() * 0.8 / text_width_at_current_font))
                font_size = max(8, font_size) 
                logger.debug(f"  Horizontal Text font size adjusted for {formatted_value}. New size: {font_size}.")


        font = QFont(self._get_themed_font_family('font_family', "Inter"), font_size, QFont.Bold)
        painter.setFont(font)
        
        metrics = painter.fontMetrics()
        text_bounds_width = metrics.horizontalAdvance(formatted_value)
        text_bounds_height = metrics.height()
        logger.debug(f"  Text Overlay: Final font size: {font.pointSize()}, Text bounds (W,H): {text_bounds_width},{text_bounds_height}.")

        normalized_value = 0.0
        if max_value - min_value != 0:
            normalized_value = (current_value - min_value) / (max_value - min_value)
        normalized_value = max(0.0, min(1.0, normalized_value)) 
        logger.debug(f"  Text Overlay: Normalized value for clipping: {normalized_value:.2f}.")

        text_target_rect = QRectF(
            bar_rect.center().x() - text_bounds_width / 2,
            bar_rect.center().y() - text_bounds_height / 2,
            text_bounds_width,
            text_bounds_height
        )
        logger.debug(f"  Text Overlay: Original text_target_rect (before translate/rotate): {text_target_rect.x():.1f},{text_target_rect.y():.1f},{text_target_rect.width():.1f},{text_target_rect.height():.1f}")


        painter.translate(bar_rect.center())
        if orientation == Qt.Vertical:
            painter.rotate(-90)
            text_local_rect_after_rotation = QRectF(
                -text_bounds_width / 2,
                -text_bounds_height / 2,
                text_bounds_width,
                text_bounds_height
            )
            logger.debug(f"  Text Overlay: Rotated Text Display Rect (relative to new origin): {text_local_rect_after_rotation.x():.1f},{text_local_rect_after_rotation.y():.1f},{text_local_rect_after_rotation.width():.1f},{text_local_rect_after_rotation.height():.1f}.")
        else:
            text_local_rect_after_rotation = QRectF(
                -text_bounds_width / 2,
                -text_bounds_height / 2,
                text_bounds_width,
                text_bounds_height
            )
            logger.debug(f"  Text Overlay: Horizontal Text Display Rect (relative to new origin): {text_local_rect_after_rotation.x():.1f},{text_local_rect_after_rotation.y():.1f},{text_local_rect_after_rotation.width():.1f},{text_local_rect_after_rotation.height():.1f}.")

        text_color_unfilled = self._get_themed_color('progressbar_text_color', QColor('#E0F2F7')) 
        chunk_color_qcolor = colors['fill_color']
        if self.parent_widget._alert_state == "critical":
            chunk_color_qcolor = colors['critical_color']
        elif self.parent_widget._alert_state == "warning":
            chunk_color_qcolor = colors['warning_color']

        luminance = (0.299 * chunk_color_qcolor.red() + 
                     0.587 * chunk_color_qcolor.green() + 
                     0.114 * chunk_color_qcolor.blue())
        
        if luminance > 180:
            text_color_filled = QColor("#000000") 
            outline_color_for_text = QColor("#FFFFFF") 
        else:
            text_color_filled = QColor("#FFFFFF") 
            outline_color_for_text = QColor("#000000") 
        
        logger.debug(f"  Text Overlay: Chunk color: {chunk_color_qcolor.name()}, Luminance: {luminance:.1f}. Text over chunk color set to: {text_color_filled.name()}. Outline: {outline_color_for_text.name()}.")


        text_path = QPainterPath()
        text_path.addText(text_local_rect_after_rotation.topLeft() + QPointF(0, metrics.ascent()), font, formatted_value)
        
        painter.setPen(QPen(outline_color_for_text, 2))
        painter.setBrush(Qt.NoBrush) 
        painter.drawPath(text_path)
        logger.debug(f"  Text Overlay: Text outline drawn with color {outline_color_for_text.name()}.")

        filled_clip_path = QPainterPath()
        unfilled_clip_path = QPainterPath()

        if orientation == Qt.Horizontal:
            bar_start_x_relative = -bar_rect.width() / 2
            fill_end_x_relative = bar_start_x_relative + bar_rect.width() * normalized_value
            
            filled_rect_clip = QRectF(
                bar_start_x_relative, 
                -bar_rect.height() / 2,
                fill_end_x_relative - bar_start_x_relative, 
                bar_rect.height()
            )
            filled_clip_path.addRect(filled_rect_clip) 
            
            unfilled_rect_clip = QRectF(
                fill_end_x_relative, 
                -bar_rect.height() / 2, 
                bar_rect.width() / 2 - fill_end_x_relative,
                bar_rect.height()
            )
            unfilled_clip_path.addRect(unfilled_rect_clip)
            logger.debug(f"  Text Overlay: Horizontal clip rects - Filled: {filled_rect_clip.x():.1f},{filled_rect_clip.y():.1f},{filled_rect_clip.width():.1f},{filled_rect_clip.height():.1f}, Unfilled: {unfilled_rect_clip.x():.1f},{unfilled_rect_clip.y():.1f},{unfilled_rect_clip.width():.1f},{unfilled_rect_clip.height():.1f}.")

        else: # Vertical
            rotated_bar_length = bar_rect.height()
            rotated_bar_thickness = bar_rect.width()

            fill_length_rotated = rotated_bar_length * normalized_value
            
            rotated_bar_start_x_relative = -rotated_bar_length / 2 
            rotated_bar_start_y_relative = -rotated_bar_thickness / 2

            filled_rect_clip = QRectF(
                rotated_bar_start_x_relative,
                rotated_bar_start_y_relative,
                fill_length_rotated,
                rotated_bar_thickness
            )
            filled_clip_path.addRect(filled_rect_clip)

            unfilled_rect_clip = QRectF(
                rotated_bar_start_x_relative + fill_length_rotated,
                rotated_bar_start_y_relative,
                rotated_bar_length - fill_length_rotated,
                rotated_bar_thickness
            )
            unfilled_clip_path.addRect(unfilled_rect_clip)
            logger.debug(f"  Text Overlay: Vertical (rotated) clip rects - Filled: {filled_rect_clip.x():.1f},{filled_rect_clip.y():.1f},{filled_rect_clip.width():.1f},{filled_rect_clip.height():.1f}, Unfilled: {unfilled_rect_clip.x():.1f},{unfilled_rect_clip.y():.1f},{unfilled_rect_clip.width():.1f},{unfilled_rect_clip.height():.1f}.")


        painter.setClipPath(filled_clip_path)
        painter.setPen(QPen(text_color_filled, 1)) 
        painter.setBrush(QBrush(text_color_filled)) 
        painter.drawPath(text_path) 
        logger.debug(f"  Text Overlay: Text fill drawn with color {text_color_filled.name()} (over filled part).")
        
        painter.setClipping(False)

        painter.setClipPath(unfilled_clip_path)
        painter.setPen(QPen(text_color_unfilled, 1)) 
        painter.setBrush(QBrush(text_color_unfilled)) 
        painter.drawPath(text_path)
        logger.debug(f"  Text Overlay: Text fill drawn with color {text_color_unfilled.name()} (over unfilled part).")
        
        painter.restore()


    def _draw_progress_bar_threshold_lines(self, painter, bar_rect, is_horizontal, line_color):
        logger.debug(f"  Threshold Lines: _draw_progress_bar_threshold_lines called for {self.parent_widget.objectName()}.")
        logger.debug(f"  Threshold Lines: Bar Content Rect for drawing lines: {bar_rect.x():.1f},{bar_rect.y():.1f},{bar_rect.width():.1f},{bar_rect.height():.1f}")
        painter.save() # Saves state A (function scope)
        
        # --- TEMPORARY DEBUG CHANGES FOR LINE VISIBILITY (KEEP THESE FOR DIAGNOSIS) ---
        # Set the pen once for the function
        painter.setPen(QPen(QColor(0, 255, 0, 255), 5, Qt.SolidLine)) # Explicitly set to opaque LIME, 5px wide, SOLID
        # --- END TEMPORARY DEBUG CHANGES ---

        low_thr = float(self.parent_widget.thresholds.get('low_threshold')) if self.parent_widget.thresholds.get('low_threshold') is not None else None
        high_thr = float(self.parent_widget.thresholds.get('high_threshold')) if self.parent_widget.thresholds.get('high_threshold') is not None else None

        if low_thr is None and high_thr is None:
            logger.debug(f"  Threshold Lines: No thresholds defined. Skipping drawing.")
            painter.restore() # Restore state A
            return

        if self.parent_widget._max_value is None or \
           self.parent_widget._min_value is None or \
           (self.parent_widget._max_value - self.parent_widget._min_value) == 0:
            logger.warning(f"  Threshold Lines: Min/Max values are invalid or identical. Cannot draw. Min: {self.parent_widget._min_value}, Max: {self.parent_widget._min_value}")
            painter.restore() # Restore state A
            return

        def value_to_normalized_pos(value, min_val, max_val):
            if max_val == min_val: return 0.0
            value = max(min_val, min(max_val, value))
            return (value - min_val) / (max_val - min_val)

        if is_horizontal:
            if low_thr is not None:
                low_thr_norm_pos = value_to_normalized_pos(low_thr, self.parent_widget._min_value, self.parent_widget._max_value)
                x_pos_low = bar_rect.left() + low_thr_norm_pos * bar_rect.width()
                logger.debug(f"  Threshold Lines: Drawing HORIZONTAL low threshold line. Coords: ({x_pos_low:.1f}, {bar_rect.top():.1f}) to ({x_pos_low:.1f}, {bar_rect.bottom():.1f}).")
                painter.drawLine(int(x_pos_low), bar_rect.top(), int(x_pos_low), bar_rect.bottom())
                logger.debug(f"  Threshold Lines: Drawn horizontal low threshold line at X={x_pos_low:.1f}.")

            if high_thr is not None:
                high_thr_norm_pos = value_to_normalized_pos(high_thr, self.parent_widget._min_value, self.parent_widget._max_value)
                x_pos_high = bar_rect.left() + high_thr_norm_pos * bar_rect.width()
                logger.debug(f"  Threshold Lines: Drawing HORIZONTAL high threshold line. Coords: ({x_pos_high:.1f}, {bar_rect.top():.1f}) to ({x_pos_high:.1f}, {bar_rect.bottom():.1f}).")
                painter.drawLine(int(x_pos_high), bar_rect.top(), int(x_pos_high), bar_rect.bottom())
                logger.debug(f"  Threshold Lines: Drawn horizontal high threshold line at X={x_pos_high:.1f}.")
        else: # Vertical
            if low_thr is not None:
                low_thr_norm_pos = value_to_normalized_pos(low_thr, self.parent_widget._min_value, self.parent_widget._max_value)
                y_pos_low = bar_rect.top() + (1.0 - low_thr_norm_pos) * bar_rect.height()
                logger.debug(f"  Threshold Lines: Drawing VERTICAL low threshold line. Coords: ({bar_rect.left():.1f}, {y_pos_low:.1f}) to ({bar_rect.right():.1f}, {y_pos_low:.1f}).")
                painter.drawLine(bar_rect.left(), int(y_pos_low), bar_rect.right(), int(y_pos_low))
                logger.debug(f"  Threshold Lines: Drawn vertical low threshold line at Y={y_pos_low:.1f}.")

            if high_thr is not None:
                high_thr_norm_pos = value_to_normalized_pos(high_thr, self.parent_widget._min_value, self.parent_widget._max_value)
                y_pos_high = bar_rect.top() + (1.0 - high_thr_norm_pos) * bar_rect.height()
                logger.debug(f"  Threshold Lines: Drawing VERTICAL high threshold line. Coords: ({bar_rect.left():.1f}, {y_pos_high:.1f}) to ({bar_rect.right():.1f}, {y_pos_high:.1f}).")
                painter.drawLine(bar_rect.left(), int(y_pos_high), bar_rect.right(), int(y_pos_high))
                logger.debug(f"  Threshold Lines: Drawn vertical high threshold line at Y={y_pos_high:.1f}.")
        
        painter.restore() # Restore state A
        logger.debug(f"  Threshold Lines: Drawing complete.")