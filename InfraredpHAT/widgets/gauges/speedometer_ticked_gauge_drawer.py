# widgets/gauges/speedometer_ticked_gauge_drawer.py
import logging
import math
from PyQt5.QtCore import Qt, QPointF, QRectF, QSize 
from PyQt5.QtGui import QPainter, QBrush, QColor, QFont, QPen, QPainterPath, QFontMetrics, QPixmap

import datetime

# Inherit from BaseGaugeDrawer directly for cleaner dependency as discussed
from .base_gauge_drawer import BaseGaugeDrawer 

logger = logging.getLogger(__name__)

class SpeedometerTickedGaugeDrawer(BaseGaugeDrawer): # Changed inheritance to BaseGaugeDrawer
    """
    Draws a speedometer gauge with an active arc, central digital readout,
    and a scale with major and minor tick marks and numerical labels.
    Uses offscreen QPixmap rendering and further isolates sensor name and meter value drawing.
    """
    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        logger.debug(f"SpeedometerTickedGaugeDrawer: draw method entered for {self.parent_widget.objectName()}. "
                     f"Value: {current_value_animated}, Min: {min_value}, Max: {max_value}, Unit: {unit}, Style: {gauge_style}")
        logger.debug("SpeedometerTickedGaugeDrawer: (FINAL FIX: Offscreen QPixmap Rendering + Isolated Name Drawing + Value Positioning)")

        painter.save() # Outer save for the entire draw method

        try: # --- try...finally block for robust painter restore ---

            pixmap_size = rect.size()
            if pixmap_size.isEmpty():
                logger.warning("SpeedometerTickedGaugeDrawer: Rect size is empty, defaulting pixmap to 200x200.")
                pixmap_size = QSize(200, 200) 
            
            pixmap = QPixmap(pixmap_size)
            pixmap.fill(Qt.transparent) # Reverted to transparent background

            pixmap_painter = QPainter(pixmap)
            pixmap_painter.setRenderHint(QPainter.Antialiasing)
            pixmap_painter.setRenderHint(QPainter.HighQualityAntialiasing)
            pixmap_painter.setRenderHint(QPainter.SmoothPixmapTransform)
            logger.debug(f"SpeedometerTickedGaugeDrawer: Created offscreen QPixmap of size {pixmap_size.width()}x{pixmap_size.height()} for drawing.")

            # --- Apply initial transformations for the virtual 200x200 canvas relative to the pixmap ---
            pixmap_painter.translate(pixmap.width() / 2, pixmap.height() / 2) # Center of the pixmap
            side_pixmap = min(pixmap.width(), pixmap.height()) # Recalculate side based on pixmap's size
            pixmap_painter.scale(side_pixmap / 200.0, side_pixmap / 200.0)
            pixmap_painter.translate(-100, -100) # Translate back so (0,0) is top-left of virtual 200x200 canvas

            # --- MODIFIED: Adjust the conceptual drawing area for the entire gauge ---
            margin = 10 
            
            virtual_rect_padded = QRectF(margin, margin, 200 - 2 * margin, 200 - 2 * margin)
            
            center_x = virtual_rect_padded.center().x()
            center_y = virtual_rect_padded.center().y()
            
            main_arc_rect = QRectF(
                virtual_rect_padded.x() + virtual_rect_padded.width() * 0.1,  
                virtual_rect_padded.y() + virtual_rect_padded.height() * 0.1, 
                virtual_rect_padded.width() * 0.8,                           
                virtual_rect_padded.height() * 0.8                           
            )
            gauge_radius = main_arc_rect.width() / 2 
            
            logger.debug(f"SpeedometerTickedGaugeDrawer: Virtual rect (original 0,0,200,200): {virtual_rect_padded.x()},{virtual_rect_padded.y()},{virtual_rect_padded.width()},{virtual_rect_padded.height()}")
            logger.debug(f"SpeedometerTickedGaugeDrawer: Virtual rect (PADDED): {virtual_rect_padded.x()},{virtual_rect_padded.y()},{virtual_rect_padded.width()},{virtual_rect_padded.height()}, Gauge Radius (New): {gauge_radius}")
            # --- END MODIFIED MARGIN ADJUSTMENT ---


            # 1. Draw the outermost background as a fully filled circle (use virtual_rect_padded for this)
            outer_bg_color = self._get_themed_color('speedometer_ticked_outer_background', QColor(40, 40, 40))
            track_color = self._get_themed_color('speedometer_ticked_track_color', QColor(60, 60, 60))
            inner_circle_color = self._get_themed_color('speedometer_ticked_inner_circle_color', QColor(30, 30, 30))
            scale_tick_color = self._get_themed_color('speedometer_ticked_scale_color', QColor(150, 150, 150))
            label_text_color = self._get_themed_color('speedometer_ticked_label_color', QColor(200, 200, 200))

            normal_fill_color = colors['fill_color']
            warning_fill_color = colors['warning_color']
            critical_fill_color = colors['critical_color']
            value_text_color = colors['text_color'] # Used below for meter value


            logger.debug(f"SpeedometerTickedGaugeDrawer: Fetched colors - Outer BG: {outer_bg_color.name()}, Track: {track_color.name()}, Inner Circle: {inner_circle_color.name()}")
            logger.debug(f"SpeedometerTickedGaugeDrawer: Fetched tick/label colors - Scale: {scale_tick_color.name()}, Label: {label_text_color.name()}")
            logger.debug(f"SpeedometerTickedGaugeDrawer: Resolved Fill Colors (from parent widget) - Normal: {normal_fill_color.name()}, Warning: {warning_fill_color.name()}, Critical: {critical_fill_color.name()}")


            # 1. Draw the outermost background as a fully filled circle
            pixmap_painter.setBrush(QBrush(outer_bg_color))
            pixmap_painter.setPen(Qt.NoPen) 
            pixmap_painter.drawEllipse(virtual_rect_padded) 
            logger.debug("SpeedometerTickedGaugeDrawer: Drawn outer background circle to pixmap.")

            # 2. Draw the main gauge track background arc
            pixmap_painter.setPen(QPen(track_color, 15, Qt.SolidLine, Qt.RoundCap))
            pixmap_painter.drawArc(main_arc_rect, 225 * 16, -270 * 16)
            logger.debug("SpeedometerTickedGaugeDrawer: Drawn main gauge track arc to pixmap.")

            # 3. Draw the active arc (color based on alert level)
            if current_value_animated is not None and not math.isnan(current_value_animated):
                clamped_value = max(min_value, min(max_value, current_value_animated))
                range_val = max_value - min_value
                current_angle_span = 0
                if range_val > 0:
                    normalized_value = (clamped_value - min_value) / range_val
                    current_angle_span = -int(normalized_value * 270)
                else:
                    normalized_value = 0 
                    if clamped_value >= max_value:
                        current_angle_span = -270 # Full span if value is at max
                    else:
                        current_angle_span = 0   # No span

                active_arc_color = normal_fill_color
                if self.parent_widget._alert_state == "warning":
                    active_arc_color = warning_fill_color
                elif self.parent_widget._alert_state == "critical":
                    active_arc_color = critical_fill_color # Corrected typo: critical_critical_color -> critical_fill_color
                
                logger.debug(f"SpeedometerTickedGaugeDrawer: Active Arc - Clamped: {clamped_value}, Normalized: {normalized_value:.2f}, Angle Span: {current_angle_span} degrees, Color: {active_arc_color.name()}")

                pixmap_painter.setPen(QPen(active_arc_color, 15, Qt.SolidLine, Qt.RoundCap))
                pixmap_painter.drawArc(main_arc_rect, 225 * 16, current_angle_span * 16)
                logger.debug("SpeedometerTickedGaugeDrawer: Drawn active value arc to pixmap.")
            else:
                logger.debug("SpeedometerTickedGaugeDrawer: current_value_animated is None or NaN. Skipping active arc drawing to pixmap.")

            # 4. Draw Ticks and Labels (USING MANUAL TRIGONOMETRY)
            start_angle_deg = 225
            span_angle_deg = -270
            num_major_ticks = 11
            num_minor_ticks_per_major = 4
            angle_increment_major = span_angle_deg / (num_major_ticks - 1)
            angle_increment_minor = angle_increment_major / (num_minor_ticks_per_major + 1)
            major_tick_length = gauge_radius * 0.12
            minor_tick_length = gauge_radius * 0.06
            tick_offset_from_arc = (15/2)
            tick_inner_radius = gauge_radius + tick_offset_from_arc
            tick_outer_radius_major = tick_inner_radius + major_tick_length
            tick_outer_radius_minor = tick_inner_radius + minor_tick_length
            label_radius = tick_outer_radius_major + gauge_radius * 0.05
            label_font_size = int(gauge_radius * 0.15)
            label_font = QFont(self._get_themed_font_family("font_family", "Inter"), label_font_size)
            pixmap_painter.setFont(label_font)
            metrics = QFontMetrics(label_font)

            for i in range(num_major_ticks):
                current_major_angle_deg = start_angle_deg + (angle_increment_major * i)
                current_major_angle_rad = math.radians(current_major_angle_deg)
                pixmap_painter.setPen(QPen(scale_tick_color, 2))
                major_tick_start_x = center_x + tick_inner_radius * math.cos(current_major_angle_rad)
                major_tick_start_y = center_y - tick_inner_radius * math.sin(current_major_angle_rad)
                major_tick_end_x = center_x + tick_outer_radius_major * math.cos(current_major_angle_rad)
                major_tick_end_y = center_y - tick_outer_radius_major * math.sin(current_major_angle_rad)
                pixmap_painter.drawLine(QPointF(major_tick_start_x, major_tick_start_y), QPointF(major_tick_end_x, major_tick_end_y))
                pixmap_painter.setPen(QPen(label_text_color))
                percentage = i / (num_major_ticks - 1)
                value_at_tick = min_value + (max_value - min_value) * percentage
                label_text = self._format_value(value_at_tick)
                text_width = metrics.horizontalAdvance(label_text)
                text_height = metrics.height()
                label_center_x_raw = center_x + label_radius * math.cos(current_major_angle_rad)
                label_center_y_raw = center_y - label_radius * math.sin(current_major_angle_rad)
                label_draw_x = label_center_x_raw - (text_width / 2)
                label_draw_y = label_center_y_raw + (text_height / 4)
                pixmap_painter.drawText(QPointF(label_draw_x, label_draw_y), label_text)
                logger.debug(f"SpeedometerTickedGaugeDrawer: Drawn Major Tick {i} at {current_major_angle_deg:.1f} deg with label: '{label_text}' at ({label_draw_x:.1f},{label_draw_y:.1f}) to pixmap.")

                if i < num_major_ticks - 1:
                    base_minor_angle_deg = current_major_angle_deg
                    for j in range(1, num_minor_ticks_per_major + 1):
                        current_minor_angle_deg = base_minor_angle_deg + (angle_increment_minor * j)
                        
                        if current_minor_angle_deg < (start_angle_deg + span_angle_deg):
                             # The minor tick is outside the allowed span, stop drawing.
                             # This condition was inverted before, potentially causing an infinite loop.
                             # Changed 'continue' to 'pass' as the loop logic itself is fixed.
                             pass 

                        current_minor_angle_rad = math.radians(current_minor_angle_deg)
                        pixmap_painter.setPen(QPen(scale_tick_color, 1))
                        minor_tick_start_x = center_x + tick_inner_radius * math.cos(current_minor_angle_rad)
                        minor_tick_start_y = center_y - tick_inner_radius * math.sin(current_minor_angle_rad)
                        minor_tick_end_x = center_x + tick_outer_radius_minor * math.cos(current_minor_angle_rad)
                        minor_tick_end_y = center_y - tick_outer_radius_minor * math.sin(current_minor_angle_rad)
                        pixmap_painter.drawLine(QPointF(minor_tick_start_x, minor_tick_start_y), QPointF(minor_tick_end_x, minor_tick_end_y))
                        logger.debug(f"SpeedometerTickedGaugeDrawer: Drawn Minor Tick at {current_minor_angle_deg:.1f} deg to pixmap.")

            # 5. Draw the inner circle (center of the gauge)
            pixmap_painter.setBrush(QBrush(colors['center_dot_color']))
            pixmap_painter.setPen(Qt.NoPen) 
            pixmap_painter.drawEllipse(QPointF(center_x, center_y), gauge_radius * 0.1, gauge_radius * 0.1)
            logger.debug("SpeedometerTickedGaugeDrawer: Drawn inner center circle to pixmap.")


            # --- Draw Value Text (Main Meter Value) ---
            # Using isolated rendering strategy for robustness
            display_value = f"{self._format_value(current_value_animated)}{unit}" if current_value_animated is not None else "N/A"

            # Determine size for temporary pixmap for meter value
            temp_value_pixmap_width = virtual_rect_padded.width() * 0.8 
            temp_value_pixmap_height = virtual_rect_padded.height() * 0.5 

            temp_value_pixmap = QPixmap(int(temp_value_pixmap_width), int(temp_value_pixmap_height))
            temp_value_pixmap.fill(Qt.transparent)

            temp_value_painter = QPainter(temp_value_pixmap)
            temp_value_painter.setRenderHint(QPainter.Antialiasing)
            temp_value_painter.setRenderHint(QPainter.HighQualityAntialiasing)
            temp_value_painter.setRenderHint(QPainter.SmoothPixmapTransform)

            # --- Dynamic Font Sizing for Meter Value ---
            initial_value_font_size = int(temp_value_pixmap_height * 0.8) # Start with a size relative to pixmap height
            min_value_font_size = 15 # Minimum readable size
            max_value_width_ratio = 0.9 # Value should occupy max 90% of the pixmap width

            value_font = QFont(self._get_themed_font_family('font_family', 'Inter'), initial_value_font_size, QFont.Bold)
            temp_value_painter.setFont(value_font)
            metrics_value_text = QFontMetrics(value_font)

            while metrics_value_text.horizontalAdvance(display_value) > (temp_value_pixmap_width * max_value_width_ratio) and initial_value_font_size > min_value_font_size:
                initial_value_font_size -= 1
                value_font.setPointSize(initial_value_font_size)
                temp_value_painter.setFont(value_font)
                metrics_value_text = QFontMetrics(value_font)
            logger.debug(f"SpeedometerTickedGaugeDrawer: Meter value '{display_value}' resolved font size to: {initial_value_font_size}.")
            # --- End Dynamic Font Sizing ---
            
            # Set colors for the meter value text
            meter_value_text_color = value_text_color
            temp_value_painter.setPen(meter_value_text_color)
            
            # Draw the text into the temporary pixmap, centered horizontally and vertically
            text_rect_in_temp_pixmap_value = QRectF(0, 0, temp_value_pixmap_width, temp_value_pixmap_height)
            temp_value_painter.drawText(text_rect_in_temp_pixmap_value, Qt.AlignCenter, display_value)
            logger.debug(f"SpeedometerTickedGaugeDrawer: Drawn meter value '{display_value}' to temporary pixmap.")

            # Finalize drawing on the temporary value pixmap
            temp_value_painter.end()
            logger.debug("SpeedometerTickedGaugeDrawer: Ended temporary value pixmap_painter.")

            # Now, draw this temporary pixmap onto the main gauge's pixmap_painter
            # Position the temporary value pixmap centrally within the main gauge area.
            value_draw_x = center_x - (temp_value_pixmap_width / 2)
            value_draw_y = center_y - (temp_value_pixmap_height / 2) # Center vertically in the gauge

            pixmap_painter.drawPixmap(QPointF(value_draw_x, value_draw_y), temp_value_pixmap)
            logger.debug(f"SpeedometerTickedGaugeDrawer: Drawn temporary meter value pixmap onto main gauge pixmap at ({value_draw_x:.1f},{value_draw_y:.1f}).")

            # --- Draw Sensor Name (Title) ---
            # Bypassing _draw_sensor_name due to rendering issues.
            # Drawing directly onto a separate, temporary QPixmap for text rendering isolation.
            
            # Determine the size for the temporary sensor name pixmap.
            temp_name_pixmap_width = virtual_rect_padded.width() # Full width of padded virtual canvas for name text
            temp_name_pixmap_height = 40 # Sufficient height for name text
            temp_name_pixmap = QPixmap(temp_name_pixmap_width, temp_name_pixmap_height) 
            temp_name_pixmap.fill(Qt.transparent) 

            temp_name_painter = QPainter(temp_name_pixmap)
            temp_name_painter.setRenderHint(QPainter.Antialiasing)
            temp_name_painter.setRenderHint(QPainter.HighQualityAntialiasing)
            temp_name_painter.setRenderHint(QPainter.SmoothPixmapTransform)

            # Set font for the sensor name on the temporary painter
            # --- Dynamic Font Sizing for Sensor Name ---
            sensor_name_font_size = 16 # Starting font size
            min_font_size = 8
            max_name_width_ratio = 0.9 # Sensor name should occupy max 90% of the pixmap width

            sensor_name_font = QFont(self._get_themed_font_family('font_family', 'Inter'), sensor_name_font_size, QFont.Bold)
            temp_name_painter.setFont(sensor_name_font)
            metrics_temp_name = QFontMetrics(sensor_name_font) # Use separate metrics for temp_name_painter
            
            # Adjust font size to fit horizontally
            while metrics_temp_name.horizontalAdvance(sensor_name) > (temp_name_pixmap_width * max_name_width_ratio) and sensor_name_font_size > min_font_size:
                sensor_name_font_size -= 1
                sensor_name_font.setPointSize(sensor_name_font_size)
                temp_name_painter.setFont(sensor_name_font)
                metrics_temp_name = QFontMetrics(sensor_name_font) # Update metrics
            logger.debug(f"SpeedometerTickedGaugeDrawer: Sensor name '{sensor_name}' resolved font size to: {sensor_name_font_size}.")
            # --- End Dynamic Font Sizing ---

            # Set color for the sensor name on the temporary painter
            sensor_name_color = colors.get('label_color', QColor('white'))
            temp_name_painter.setPen(sensor_name_color)

            # Draw the text into the temporary pixmap, centered horizontally and vertically
            text_rect_in_temp_pixmap = QRectF(0, 0, temp_name_pixmap_width, temp_name_pixmap_height)
            temp_name_painter.drawText(text_rect_in_temp_pixmap, Qt.AlignCenter, sensor_name)
            logger.debug(f"SpeedometerTickedGaugeDrawer: Drawn sensor name '{sensor_name}' to temporary pixmap.")

            # Finalize drawing on the temporary pixmap
            temp_name_painter.end()
            logger.debug("SpeedometerTickedGaugeDrawer: Ended temporary name pixmap_painter.")

            # Now, draw this temporary pixmap onto the main gauge's pixmap_painter
            # Position the temporary pixmap within the padded virtual canvas.
            # Aim for horizontally centered. Vertically above the main value.
            sensor_name_draw_x = center_x - (temp_name_pixmap_width / 2) # Center horizontally on virtual canvas
            sensor_name_draw_y = virtual_rect_padded.y() + (virtual_rect_padded.height() * 0.23) # Place near top of padded area (adjust as needed)

            pixmap_painter.drawPixmap(QPointF(sensor_name_draw_x, sensor_name_draw_y), temp_name_pixmap)
            logger.debug(f"SpeedometerTickedGaugeDrawer: Drawn temporary name pixmap onto main gauge pixmap at ({sensor_name_draw_x:.1f},{sensor_name_draw_y:.1f}).")


            # --- Finalize drawing on the main pixmap ---
            pixmap_painter.end()
            logger.debug("SpeedometerTickedGaugeDrawer: Ended main pixmap_painter.")

            # --- DEBUG STEP: Save pixmap to file ---
            # You can now comment out or remove these lines:
            # timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            # debug_filename = f"Debug_Logs/debug_gauge_{self.parent_widget.objectName()}_{timestamp}.png"
            # if pixmap.isNull():
            #     logger.error(f"SpeedometerTickedGaugeDrawer: QPixmap is NULL before saving! File will not be saved.")
            # else:
            #     logger.debug(f"SpeedometerTickedGaugeDrawer: QPixmap size before saving: {pixmap.width()}x{pixmap.height()}. Attempting to save to {debug_filename}.")
            #     save_successful = pixmap.save(debug_filename)
            #     if save_successful:
            #         logger.debug(f"SpeedometerTickedGaugeDrawer: Successfully saved offscreen QPixmap to {debug_filename}.")
            #     else:
            #         logger.error(f"SpeedometerTickedGaugeDrawer: FAILED to save offscreen QPixmap to {debug_filename}. Check permissions or disk space. (PATH: {debug_filename})")
            # --- END DEBUG STEP ---


            # --- Draw the fully rendered pixmap onto the screen painter ---
            painter.drawPixmap(rect.topLeft(), pixmap)
            logger.debug(f"SpeedometerTickedGaugeDrawer: Drawn QPixmap onto screen painter at {rect.topLeft().x()},{rect.topLeft().y()}.")

        except Exception as e:
            logger.error(f"SpeedometerTickedGaugeDrawer: CRITICAL ERROR during draw for {self.parent_widget.objectName()}: {e}")
        finally:
            painter.restore() # Guaranteed restore for the initial save()
            logger.debug("SpeedometerTickedGaugeDrawer: draw method exited. (Offscreen QPixmap complete)")