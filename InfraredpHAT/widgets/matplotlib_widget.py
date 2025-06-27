# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSizePolicy, QLabel
from PyQt5.QtCore import QTimer, QDateTime, Qt, QRect, QPoint, QPointF
from PyQt5.QtGui import QColor, QFont
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import logging
import datetime
import numpy as np # Explicitly import numpy

logger = logging.getLogger(__name__)

class MatplotlibWidget(QWidget):
    """
    A PyQt5 widget that embeds a Matplotlib figure,
    providing a customizable plot for sensor data, now with an interactive legend.
    It can optionally hide the Matplotlib toolbar.
    """
    def __init__(self, parent=None, theme_colors=None, show_toolbar=True, show_default_title=False): # NEW: show_toolbar parameter
        """
        Initializes the MatplotlibWidget.
        :param parent: Parent QWidget.
        :param theme_colors: Dictionary of theme colors.
        :param show_toolbar: Boolean, if True, the Matplotlib toolbar is displayed.
        :param show_default_title: Boolean, if True, the default "Sensor Data Trends" title is shown when plot is cleared.
        """
        super().__init__(parent)
        # --- FIX: Ensure theme_colors is always a mutable dictionary, even if None is passed ---
        self.theme_colors = dict(theme_colors) if theme_colors is not None else {}
        self.show_toolbar = show_toolbar # Store the toolbar visibility setting
        self.show_default_title = show_default_title # Store the title visibility setting
        
        # Initialize the figure and axes
        self.figure, self.ax = plt.subplots(facecolor='none', edgecolor='none') 
        
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.updateGeometry()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Only add toolbar if show_toolbar is True
        if self.show_toolbar:
            self.toolbar = NavigationToolbar(self.canvas, self)
            main_layout.addWidget(self.toolbar)
        else:
            self.toolbar = None # Explicitly set to None if not shown
            logger.debug("MatplotlibWidget: Toolbar hidden as requested.")


        main_layout.addWidget(self.canvas)

        self.status_label = QLabel("No data available to plot.")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #E0F2F7; font-size: 16px;")
        self.status_label.setVisible(False)
        main_layout.addWidget(self.status_label)

        # Initialize legend related attributes BEFORE calling apply_theme()
        self.legend_lines = {}
        self.legend_visible = {}
        self.legend_proxy = None

        self.apply_theme() # Call apply_theme after self.theme_colors is surely set
        self.setMinimumSize(400, 380)
        logger.debug(f"MatplotlibWidget initialized. Minimum size: {self.minimumSize()}. Toolbar visible: {self.show_toolbar}")

        # Connect the pick event for interactive legend
        self.figure.canvas.mpl_connect('pick_event', self._on_pick)


    def apply_theme(self):
        """Applies theme colors to the Matplotlib figure and axes."""
        # --- FIX: Add a more robust check for theme_colors content ---
        if not self.theme_colors or not any(self.theme_colors.values()): # Check if dict is empty or all values are falsy
            logger.warning("MatplotlibWidget: Theme colors dictionary is empty or contains no valid colors. Cannot apply theme effectively.")
            # Optionally, you might want to load default colors here if self.theme_colors is empty
            # For now, we will just proceed with defaults from .get() calls
            pass # Continue to use .get() with defaults

        self.figure.patch.set_facecolor(self.theme_colors.get('plot_facecolor', '#1A2A40'))
        self.figure.patch.set_edgecolor(self.theme_colors.get('plot_edgecolor', '#3C6595'))

        # Background color for axes
        self.ax.set_facecolor(self.theme_colors.get('plot_background', '#1A2A40')) # Assuming plot_background might be a separate key for ax.set_facecolor

        # Set spine colors
        self.ax.spines['bottom'].set_color(self.theme_colors.get('plot_edgecolor', '#3C6595'))
        self.ax.spines['top'].set_color(self.theme_colors.get('plot_edgecolor', '#3C6595'))
        self.ax.spines['right'].set_color(self.theme_colors.get('plot_edgecolor', '#3C6595'))
        self.ax.spines['left'].set_color(self.theme_colors.get('plot_edgecolor', '#3C6595'))

        # Set tick colors
        self.ax.tick_params(axis='x', colors=self.theme_colors.get('plot_tick_color', '#E0F2F7'))
        self.ax.tick_params(axis='y', colors=self.theme_colors.get('plot_tick_color', '#E0F2F7'))

        # Set label colors
        self.ax.xaxis.label.set_color(self.theme_colors.get('plot_label_color', '#87EEBC')) # Default changed to match other labels
        self.ax.yaxis.label.set_color(self.theme_colors.get('plot_label_color', '#87EEBC')) # Default changed to match other labels
        
        # Ensure tick label colors are also set
        for label in self.ax.get_xticklabels():
            label.set_color(self.theme_colors.get('plot_tick_color', '#E0F2F7'))
        for label in self.ax.get_yticklabels():
            label.set_color(self.theme_colors.get('plot_tick_color', '#E0F2F7'))

        # Set title color
        self.ax.title.set_color(self.theme_colors.get('plot_title_color', '#4682B4'))
        self.ax.grid(True, color=self.theme_colors.get('plot_grid_color', '#C0D8E8'), linestyle=':', linewidth=0.5)

        # Update legend colors if legend exists
        if self.legend_proxy:
            legend = self.legend_proxy
            legend.get_frame().set_facecolor(self.theme_colors.get('plot_legend_facecolor', '#2A3B4C'))
            legend.get_frame().set_edgecolor(self.theme_colors.get('plot_legend_edgecolor', '#3C6595'))
            for text in legend.get_texts():
                text.set_color(self.theme_colors.get('plot_legend_labelcolor', '#E0F2F7'))

        self.canvas.draw_idle()
        logger.debug("MatplotlibWidget: Theme applied and plot redrawn.")


    def plot_data(self, series_data, theme_colors):
        """
        Plots multiple series of data on the same axes.
        :param series_data: A list of dictionaries, where each dictionary
                            contains 'x', 'y', 'label', and 'y_unit'.
        :param theme_colors: Dictionary of theme colors, passed to apply_theme.
        """
        logger.debug(f"MatplotlibWidget: Plotting data. Number of series: {len(series_data)}")
        self.hide_status_message()
        self.ax.clear()
        # --- FIX: Ensure theme_colors is updated before applying theme for plotting ---
        self.theme_colors.update(theme_colors) # Update internal theme_colors
        self.apply_theme() # Then apply the updated theme

        self.legend_lines.clear()
        self.legend_visible.clear()

        line_colors_str = self.theme_colors.get('plot_line_colors', '')
        line_colors = [color.strip() for color in line_colors_str.split(',') if color.strip()]
        if not line_colors: # Fallback if theme_colors didn't provide any
            line_colors = ['#87CEEB', '#4CAF50', '#FFD700', '#FF0000', '#A020F0', '#20B2AA', '#DA70D6', '#FF69B4']
            logger.warning("MatplotlibWidget: 'plot_line_colors' not found or empty in theme, using defaults.")

        all_y_values = []
        labels = []
        has_data = False
        
        y_units = set()
        
        for i, series in enumerate(series_data):
            x_data = series.get('x', [])
            y_data = series.get('y', [])
            label = series.get('label', f'Series {i+1}')
            y_unit = series.get('y_unit', '')
            low_threshold = series.get('low_threshold')
            high_threshold = series.get('high_threshold')

            if x_data and y_data:
                line, = self.ax.plot(x_data, y_data, label=label, color=line_colors[i % len(line_colors)], linewidth=2, picker=5)
                self.legend_lines[label] = line
                self.legend_visible[label] = True
                
                all_y_values.extend(y_data)
                labels.append(label)
                y_units.add(y_unit)
                has_data = True

                if low_threshold is not None:
                    self.ax.axhline(low_threshold, color='red', linestyle='--', linewidth=1, zorder=0)
                    if x_data:
                        # Position text near the line, at the rightmost x-coordinate available
                        x_pos = x_data[-1]
                        self.ax.text(x_pos, low_threshold, f' Low: {low_threshold:.1f}', color='red', va='center', ha='left', fontsize=8,
                                     backgroundcolor=(0,0,0,0.5), bbox=dict(facecolor='red', alpha=0.1, edgecolor='none', pad=1)) 
                if high_threshold is not None:
                    self.ax.axhline(high_threshold, color='red', linestyle='--', linewidth=1, zorder=0)
                    if x_data:
                        x_pos = x_data[-1]
                        self.ax.text(x_pos, high_threshold, f' High: {high_threshold:.1f}', color='red', va='center', ha='left', fontsize=8,
                                     backgroundcolor=(0,0,0,0.5), bbox=dict(facecolor='red', alpha=0.1, edgecolor='none', pad=1))
            else:
                logger.warning(f"MatplotlibWidget: Skipping plot for series '{label}' due to empty data.")

        if not has_data:
            self.set_status_message("No data available for selected time range.")
            return

        
        if self.show_default_title: # CONDITIONAL TITLE SETTING
            self.ax.set_title("Sensor Data Trends")
        self.ax.set_xlabel("Time")
        
        if len(y_units) == 1:
            unit_text = list(y_units)[0]
            #unit_text = unit_text.replace('degC', '\u00B0C') 
            self.ax.set_ylabel(unit_text)
        elif len(y_units) > 1:
            self.ax.set_ylabel("Mixed Units")

        self.figure.autofmt_xdate()

        if labels:
            main_handles = [self.legend_lines[label] for label in labels if label in self.legend_lines]
            main_labels = [label for label in labels if label in self.legend_lines]
            
            self.legend_proxy = self.ax.legend(main_handles, main_labels, loc='best', frameon=True)
            self.apply_theme()
            
            for legend_line, original_line_label in zip(self.legend_proxy.get_lines(), main_labels):
                legend_line.set_picker(5)
                legend_line._original_line = self.legend_lines[original_line_label] 
        else:
            if self.ax.legend_ is not None:
                try:
                    self.ax.legend().remove()
                except AttributeError:
                    logger.debug("MatplotlibWidget: Legend already removed or not present.")
            self.legend_proxy = None

        if all_y_values:
            min_y, max_y = np.min(all_y_values), np.max(all_y_values) # Use numpy for min/max
            # Add a small buffer to the y-axis limits to prevent lines from touching the top/bottom
            y_range = max_y - min_y
            if y_range == 0: # Handle cases where all values are the same
                padding = 0.5
            else:
                padding = y_range * 0.1 # 10% padding on each side
            self.ax.set_ylim(min_y - padding, max_y + padding)
        
        self.figure.subplots_adjust(top=0.92, bottom=0.15, left=0.1, right=0.95)
        self.figure.tight_layout(pad=0.5) 
        
        self.canvas.draw_idle()
        logger.debug("MatplotlibWidget: Plot data drawn and canvas redrawn.")


    def _on_pick(self, event):
        """Event handler for interactive legend."""
        if isinstance(event.artist, plt.matplotlib.lines.Line2D) and hasattr(event.artist, '_original_line'):
            original_line = event.artist._original_line
            label = original_line.get_label()
            
            current_visible = not original_line.get_visible()
            original_line.set_visible(current_visible)
            self.legend_visible[label] = current_visible

            if current_visible:
                event.artist.set_alpha(1.0)
            else:
                event.artist.set_alpha(0.2)
            
            self.figure.canvas.draw_idle()
            logger.debug(f"MatplotlibWidget: Toggled visibility for series '{label}' to {current_visible}.")


    def clear_plot(self):
        """Clears the plot area."""
        logger.debug("MatplotlibWidget: Clearing plot.")
        self.ax.clear()
        self.apply_theme()
        
        if self.show_default_title: # CONDITIONAL TITLE SETTING
            self.ax.set_title("Sensor Data Trends")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("")
        
        self.legend_lines.clear()
        self.legend_visible.clear()
        self.legend_proxy = None

        if self.ax.legend_ is not None:
            try:
                self.ax.legend().remove()
                logger.debug("MatplotlibWidget: Legend already removed or not present.")
            except AttributeError:
                logger.debug("MatplotlibWidget: Legend already removed or not present.")

        self.canvas.draw_idle()
        logger.debug("MatplotlibWidget: Plot cleared.")

    def set_status_message(self, message):
        """
        Sets a status message on the plot area and makes it visible.
        Clears the plot when a message is displayed.
        """
        self.clear_plot()
        self.status_label.setText(message)
        self.status_label.setVisible(True)
        logger.debug(f"MatplotlibWidget: Displaying status message: '{message}'")

    def hide_status_message(self):
        """
        Hides the status message.
        """
        self.status_label.setVisible(False)
        logger.debug("MatplotlibWidget: Hiding status message.")

