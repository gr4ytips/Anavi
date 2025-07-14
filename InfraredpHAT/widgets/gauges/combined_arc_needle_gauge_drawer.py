# widgets/gauges/combined_arc_needle_gauge_drawer.py
import logging
import math
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QPainter, QBrush, QColor, QFont, QPen, QPainterPath, QFontMetrics

from .analog_gauge_drawers import AnalogGaugeDrawer # Inheriting for access to themed helpers

logger = logging.getLogger(__name__)

class CombinedArcNeedleGaugeDrawer(AnalogGaugeDrawer):
    """
    Draws a gauge that combines a background arc, a filled active arc,
    and a needle indicator. The needle's position is calculated using trigonometry.
    """
    def draw(self, painter, rect, sensor_name, current_value_animated, min_value, max_value, unit, gauge_style, colors):
        """
        Paints the gauge, including the arc, value text, and needle.
        """
        logger.debug(f"CombinedArcNeedleGaugeDrawer: draw method entered for {self.parent_widget.objectName()}. "
                     f"Value: {current_value_animated}, Min: {min_value}, Max: {max_value}, Unit: {unit}, Style: {gauge_style}")

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        side = min(rect.width(), rect.height())

        # Scale the painter to a virtual 200x200 canvas.
        # This allows all drawing coordinates to be defined relative to a 200x200 square,
        # and they will automatically scale to the actual widget size.
        painter.translate(rect.center().x(), rect.center().y())
        painter.scale(side / 200.0, side / 200.0)
        painter.translate(-100, -100) # Translate back so (0,0) is top-left of virtual 200x200 canvas

        virtual_rect_200 = QRectF(0, 0, 200, 200)
        logger.debug(f"CombinedArcNeedleGaugeDrawer: Virtual canvas setup - Side: {side}, Rect center: {rect.center().x()}, {rect.center().y()}")
        logger.debug(f"CombinedArcNeedleGaugeDrawer: Virtual rect (0,0,200,200): {virtual_rect_200.x(), virtual_rect_200.y(), virtual_rect_200.width(), virtual_rect_200.height()}")

        # Define the bounding rectangle for the arc on the virtual canvas
        arc_rect = QRectF(10, 10, 180, 180) # Virtual 200x200 canvas, centered 180x180 arc
        logger.debug(f"CombinedArcNeedleGaugeDrawer: Arc bounding rect: {arc_rect.x(), arc_rect.y(), arc_rect.width(), arc_rect.height()}")

        # --- Fetch colors using theme keys ---
        # These colors are expected to be resolved by SensorDisplayWidget's _get_current_gauge_colors
        # and passed in the 'colors' dictionary.
        # Using specific new theme keys for combined gauge elements, with fallbacks
        track_color = self._get_themed_color('combined_arc_needle_track_color', colors.get('scale_color', QColor('#E0E0E0')))
        active_arc_fill_color = self._get_themed_color('combined_arc_needle_fill_color', colors.get('fill_color', QColor('#3498DB')))
        needle_color = self._get_themed_color('combined_arc_needle_needle_color', colors.get('needle_color', QColor('#CC0000')))
        center_dot_color = self._get_themed_color('combined_arc_needle_center_dot_color', colors.get('center_dot_color', QColor('#1F3A60')))
        text_color = colors['text_color'] # Resolved by parent

        logger.debug(f"CombinedArcNeedleGaugeDrawer: Fetched colors - Track: {track_color.name()}, Active Arc: {active_arc_fill_color.name()}, Needle: {needle_color.name()}, Center Dot: {center_dot_color.name()}")

        # Draw the background arc (the track)
        painter.setPen(QPen(track_color, 8, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(arc_rect, 225 * 16, -270 * 16) # Arc from 225 to -45 (270 degrees total)
        logger.debug("CombinedArcNeedleGaugeDrawer: Drawn background arc.")

        # Draw the filled arc based on the current value
        if current_value_animated is not None and not math.isnan(current_value_animated):
            angle_range = 270 # Total degrees for the gauge
            value_range = max_value - min_value
            
            # Calculate the angle based on the current value
            clamped_value = max(min_value, min(max_value, current_value_animated))
            
            fill_angle = 0
            if value_range > 0:
                # Normalize value to a 0-1 scale, then map to angle range
                normalized_value = (clamped_value - min_value) / value_range
                fill_angle = -int(normalized_value * angle_range) # Negative for counter-clockwise
            else:
                normalized_value = 0 # Handle division by zero
            logger.debug(f"CombinedArcNeedleGaugeDrawer: Active arc - Clamped value: {clamped_value}, Normalized: {normalized_value:.2f}, Fill Angle: {fill_angle} degrees")

            painter.setPen(QPen(active_arc_fill_color, 8, Qt.SolidLine, Qt.RoundCap))
            painter.drawArc(arc_rect, 225 * 16, fill_angle * 16)
            logger.debug("CombinedArcNeedleGaugeDrawer: Drawn filled active arc.")
        else:
            logger.debug("CombinedArcNeedleGaugeDrawer: current_value_animated is None or NaN. Skipping active arc drawing.")


        # --- Draw the needle ---
        painter.setPen(QPen(needle_color, 2))
        painter.setBrush(QBrush(needle_color))

        center_x, center_y = 100, 100 # Center of the virtual 200x200 canvas
        needle_length = 70 # Length of the needle in virtual units
        needle_width = 5 # Width of the needle's base in virtual units

        if current_value_animated is not None and not math.isnan(current_value_animated):
            # Calculate needle angle based on value (0 degrees is horizontal right, increases clockwise)
            # The gauge goes from 225 degrees (bottom left) to -45 degrees (bottom right)
            # So, 0% is at 225 degrees, 100% is at -45 degrees. Total span is 270 degrees.
            angle_at_zero_val = 225 # degrees
            angle_span = 270 # degrees

            # Calculate current angle
            value_normalized = (current_value_animated - min_value) / (max_value - min_value)
            # Ensure value_normalized is between 0 and 1
            value_normalized = max(0.0, min(1.0, value_normalized))
            
            # Angle decreases as value increases (counter-clockwise movement from start_angle 225)
            needle_angle_deg = angle_at_zero_val - (value_normalized * angle_span)
            needle_angle_rad = needle_angle_deg * (math.pi / 180.0) # Convert to radians for math functions

            logger.debug(f"CombinedArcNeedleGaugeDrawer: Needle - Normalized value: {value_normalized:.2f}, Angle (deg): {needle_angle_deg:.2f}, Angle (rad): {needle_angle_rad:.2f}")

            # Needle tip
            tip_x = center_x + needle_length * math.cos(needle_angle_rad)
            tip_y = center_y - needle_length * math.sin(needle_angle_rad) # Y-axis is inverted in Qt (positive Y is down)

            # Base points of the needle (perpendicular to the needle direction)
            base_angle_offset_rad = 90 * (math.pi / 180.0)
            
            base_left_x = center_x + needle_width * math.cos(needle_angle_rad + base_angle_offset_rad)
            base_left_y = center_y - needle_width * math.sin(needle_angle_rad + base_angle_offset_rad)
            
            base_right_x = center_x + needle_width * math.cos(needle_angle_rad - base_angle_offset_rad)
            base_right_y = center_y - needle_width * math.sin(needle_angle_rad - base_angle_offset_rad)

            needle_path = QPainterPath()
            needle_path.moveTo(QPointF(tip_x, tip_y))
            needle_path.lineTo(QPointF(base_left_x, base_left_y))
            needle_path.lineTo(QPointF(base_right_x, base_right_y))
            needle_path.closeSubpath()

            painter.drawPath(needle_path)
            logger.debug("CombinedArcNeedleGaugeDrawer: Drawn needle.")
        else:
            logger.debug("CombinedArcNeedleGaugeDrawer: current_value_animated is None or NaN. Skipping needle drawing.")

        # Draw the central circle (pivot for the needle)
        painter.setBrush(QBrush(center_dot_color))
        painter.setPen(Qt.NoPen) # No outline for the center dot
        painter.drawEllipse(QPointF(center_x, center_y), needle_width * 1.5, needle_width * 1.5) # Larger circle at pivot
        logger.debug("CombinedArcNeedleGaugeDrawer: Drawn central pivot circle.")

        # --- Draw Value Text ---
        # Position the value text in the center, slightly above the pivot
        value_font_size = int(virtual_rect_200.width() / 10) 
        value_font = QFont(self._get_themed_font_family('font_family', 'Inter'), value_font_size)
        value_font.setBold(True)
        
        # Virtual rectangle for value text (e.g., centered in the middle of the gauge)
        value_text_draw_rect_virtual = QRectF(50, 80, 100, 40) 
        logger.debug(f"CombinedArcNeedleGaugeDrawer: Value text font size: {value_font_size}, Rect: {value_text_draw_rect_virtual.x(), value_text_draw_rect_virtual.y(), value_text_draw_rect_virtual.width(), value_text_draw_rect_virtual.height()}")

        self._draw_value_text(painter, 
                              value_text_draw_rect_virtual, 
                              current_value_animated, 
                              unit, 
                              text_color, 
                              self._get_themed_color('gauge_text_outline_color', QColor('black')),
                              self._get_themed_color('high_contrast_text_color', QColor('white')), 
                              value_font)
        logger.debug("CombinedArcNeedleGaugeDrawer: Drawn value text.")

        # --- Draw Sensor Name (Title) ---
        # Position the sensor name at the top of the virtual canvas
        title_font_size = int(virtual_rect_200.width() / 20)
        title_font = QFont(self._get_themed_font_family('font_family', 'Inter'), title_font_size)
        title_font.setBold(False)
        
        # Virtual rectangle for sensor name (e.g., at the top)
        name_draw_rect_virtual = QRectF(0, 20, 200, 30) # Top of the virtual canvas
        logger.debug(f"CombinedArcNeedleGaugeDrawer: Sensor name font size: {title_font_size}, Rect: {name_draw_rect_virtual.x(), name_draw_rect_virtual.y(), name_draw_rect_virtual.width(), name_draw_rect_virtual.height()}")

        self._draw_sensor_name(painter, name_draw_rect_virtual, sensor_name, colors)
        logger.debug("CombinedArcNeedleGaugeDrawer: Drawn sensor name.")

        painter.restore()
        logger.debug("CombinedArcNeedleGaugeDrawer: draw method exited.")