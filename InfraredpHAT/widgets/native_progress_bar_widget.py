# widgets/native_progress_bar_widget.py
from PyQt5.QtWidgets import QProgressBar, QSizePolicy, QStyleOptionProgressBar
from PyQt5.QtCore import Qt, pyqtProperty, QRectF
from PyQt5.QtGui import QColor, QPainter, QTransform, QFontMetrics, QPen
import logging

logger = logging.getLogger(__name__)

class NativeProgressBarWidget(QProgressBar):
    """
    A custom QProgressBar widget that handles its own text formatting (value + unit + precision)
    and alert-based QSS styling.
    """
    def __init__(self, parent_sensor_display_widget):
        super().__init__(parent_sensor_display_widget)
        self.parent_widget = parent_sensor_display_widget

        self.setTextVisible(True)
        self.setAlignment(Qt.AlignCenter)

        self._min_value = parent_sensor_display_widget._min_value
        self._max_value = parent_sensor_display_widget._max_value
        self.unit = parent_sensor_display_widget.unit
        self._precision = parent_sensor_display_widget._precision
        self._alert_state = parent_sensor_display_widget._alert_state

        self.setRange(int(self._min_value), int(self._max_value))

        logger.debug(f"NativeProgressBarWidget: Initialized for {self.parent_widget.objectName()}")

    def update_value_and_style(self, new_value, new_alert_state, new_na_state):
        """
        Updates the internal value, alert state, and triggers text/QSS refresh.
        """
        self._alert_state = new_alert_state

        if new_value is None or new_na_state:
            formatted_text = "N/A"
            display_value = 0
            alert_state_prop = "normal"
        else:
            formatted_text = f"{new_value:.{self._precision}f}{self.unit}"
            display_value = int(max(self._min_value, min(self._max_value, new_value)))
            alert_state_prop = new_alert_state

        self.setFormat(formatted_text)
        self.setValue(display_value)

        self.setProperty("alert_state", alert_state_prop)

        self.update() # Force a repaint to ensure paintEvent is called

        logger.debug(f"NativeProgressBarWidget: Updated value for {self.parent_widget.objectName()}: '{formatted_text}', Alert State: '{alert_state_prop}'")

    def apply_qss(self):
        """
        Applies or re-applies the QSS for the progress bar, crucial when properties change.
        This simply calls the parent's method to get the QSS string.
        """
        self.setStyleSheet(self.parent_widget._get_progress_bar_qss())
        self.style().polish(self)
        logger.debug(f"NativeProgressBarWidget: Re-applied QSS for {self.parent_widget.objectName()}")

    def set_orientation_and_size_policy(self, orientation):
        """Sets the QProgressBar's orientation and size policy."""
        self.setOrientation(orientation)
        logger.debug(f"NativeProgressBarWidget: Setting orientation to {orientation} for {self.parent_widget.objectName()}")
        if orientation == Qt.Vertical:
            self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
            logger.debug(f"NativeProgressBarWidget: Set size policy for Vertical: Minimum width, Expanding height.")
        else: # Horizontal
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
            logger.debug(f"NativeProgressBarWidget: Set size policy for Horizontal: Expanding width, Minimum height.")
        logger.debug(f"NativeProgressBarWidget: Final orientation set to {self.orientation()} for {self.parent_widget.objectName()}")

    def setRange(self, minimum, maximum):
        super().setRange(minimum, maximum)
        self._min_value = minimum
        self._max_value = maximum
        logger.debug(f"NativeProgressBarWidget: Range set to [{minimum}, {maximum}] for {self.parent_widget.objectName()}")

    def paintEvent(self, event):
        """
        Overrides the default paint event to draw vertical text for vertical progress bars.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        opt = QStyleOptionProgressBar()
        self.initStyleOption(opt)

        if self.orientation() == Qt.Vertical:
            opt.text = ""
            opt.textVisible = False

        self.style().drawControl(self.style().CE_ProgressBar, opt, painter, self)

        if self.isTextVisible() and self.orientation() == Qt.Vertical:
            logger.debug(f"NativeProgressBarWidget: paintEvent - Drawing custom vertical text for {self.objectName()}.")

            painter.save()

            text_color = self.parent_widget._get_themed_color('progressbar_text_color', QColor('#FFFFFF'))
            if self._alert_state == "critical":
                text_color = self.parent_widget._get_themed_color('progressbar_text_alert_color', QColor('#FFC107'))
            elif self._alert_state == "warning":
                text_color = self.parent_widget._get_themed_color('gauge_warning_color', QColor('#FFD700'))

            painter.setPen(text_color)
            painter.setFont(self.font())

            text = self.text()
            rect = self.rect()

            logger.debug(f"  paintEvent: Text: '{text}', Original Rect: {rect.width()}x{rect.height()}")
            logger.debug(f"  paintEvent: Text Color: {text_color.name()}")
            logger.debug(f"  paintEvent: Current Font: {painter.font().family()}, Size: {painter.font().pointSize()}")

            # Translate to the center of the widget
            center_x = rect.width() / 2
            center_y = rect.height() / 2
            painter.translate(center_x, center_y)

            # --- IMPORTANT FIX: Rotate by -90 degrees for bottom-to-top reading ---
            painter.rotate(-90)
            # --- END IMPORTANT FIX ---

            # Draw text centered on the rotated canvas.
            # After -90 deg rotation (counter-clockwise), original width becomes new height,
            # original height becomes new width.
            # The drawText method with Qt.AlignCenter will center the text within the given QRectF.
            # The QRectF should be created such that it spans the effective rotated area around (0,0).
            # Note: For -90 deg, x-axis points upwards, y-axis points left.
            # To center the original text within the widget:
            # - Half of original height along new x-axis (up/down direction)
            # - Half of original width along new y-axis (left/right direction)
            painter.drawText(QRectF(-rect.height()/2, -rect.width()/2, rect.height(), rect.width()), Qt.AlignCenter, text)

            logger.debug(f"  paintEvent: Painter Translated to ({center_x}, {center_y}), Rotated -90 deg.")
            logger.debug(f"  paintEvent: Text drawn within rectangle: {QRectF(-rect.height()/2, -rect.width()/2, rect.height(), rect.width())}")

            painter.restore()