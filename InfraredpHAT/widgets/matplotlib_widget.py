# widgets/matplotlib_widget.py
# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy, QApplication
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QFont, QFontDatabase

import matplotlib
matplotlib.use('Qt5Agg') # Use the Qt5Agg backend
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm 

import logging

logger = logging.getLogger(__name__)

class MatplotlibWidget(QWidget):
    """
    A Qt widget that embeds a Matplotlib figure for plotting sensor data.
    Provides basic plotting functionality and theme integration.
    """
    def __init__(self, theme_colors, settings_manager, parent=None, hide_toolbar=False):
        super().__init__(parent)
        self.setObjectName("MatplotlibWidget")
        
        self.theme_colors = theme_colors # Initial theme colors
        self.settings_manager = settings_manager
        self.hide_toolbar = hide_toolbar

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        self.toolbar.setVisible(not self.hide_toolbar) 

        self.ax = self.figure.add_subplot(111) 
        
        self.status_label = QLabel("Loading plot data...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.status_label.hide() 
        
        self.vertical_layout = QVBoxLayout(self)
        self.vertical_layout.addWidget(self.toolbar)
        self.vertical_layout.addWidget(self.canvas)
        self.vertical_layout.addWidget(self.status_label) 

        self.vertical_layout.setContentsMargins(0, 0, 0, 0)
        self.vertical_layout.setSpacing(0)

        # Set initial background to transparent to allow QSS styling
        #self.figure.patch.set_alpha(0.0) 
        #self.ax.patch.set_alpha(0.0)

        self.apply_initial_theme() 
        
        # Polish self in init to apply QSS immediately to the widget's own background
        self.style().polish(self) 
        logger.info("MatplotlibWidget initialized.")

    def _get_color_from_theme(self, key, default_color_hex_string):
        """
        Helper to safely get a color from theme_colors and ensure it's a hex string.
        `default_color_hex_string` should always be like '#RRGGBB'.
        """
        color_val = self.theme_colors.get(key) # Get the value directly

        if isinstance(color_val, QColor):
            # If it's already a QColor object (from update_theme_colors conversion), convert it to hex
            return color_val.name()
        elif isinstance(color_val, str) and color_val.startswith('#'):
            # If it's a hex string already, use it directly
            return color_val
        else:
            # Fallback to the provided default or handle other unexpected types
            # Log a warning if default_color_hex_string is not a hex string either
            if not isinstance(default_color_hex_string, str) or not default_color_hex_string.startswith('#'):
                logger.warning(f"MatplotlibWidget: Default color for key '{key}' is not a hex string: {default_color_hex_string}. Using black.")
                return '#000000' # Safe fallback

            return default_color_hex_string           
        

    #def _get_color_from_theme(self, key, default_color):
    #    """Helper to safely get a QColor from theme_colors and convert to hex string."""
    #    color_val = self.theme_colors.get(key, default_color)
    #    if isinstance(color_val, QColor):
    #        return color_val.name()
    #    elif isinstance(color_val, str):
    #        # If it's a string (e.g., '#RRGGBB'), ensure it's a valid QColor then return name
    #        return QColor(color_val).name()
    #   return QColor(default_color).name() # Fallback

    def _apply_matplotlib_theme_elements(self):
        """
        Applies all theme-related colors and fonts to the Matplotlib figure and axes.
        This method should be called whenever the theme changes or the plot is cleared/redrawn.
        """
        logger.debug("MatplotlibWidget: Applying Matplotlib theme elements.")

        # --- Figure and Axes Backgrounds ---
        self.figure.set_facecolor(self._get_color_from_theme('matplotlib_figure_facecolor', '#2E2E2E')) # Default to dark
        self.ax.set_facecolor(self._get_color_from_theme('matplotlib_axes_facecolor', '#383838')) # Default to dark

        # --- Spines (Borders of the plot area) ---
        spine_color = self._get_color_from_theme('matplotlib_edgecolor', '#606060')
        self.ax.spines['bottom'].set_color(spine_color)
        self.ax.spines['top'].set_color(spine_color)
        self.ax.spines['left'].set_color(spine_color)
        self.ax.spines['right'].set_color(spine_color)

        # --- Tick Labels (Numbers on axes) ---
        tick_color = self._get_color_from_theme('matplotlib_tick_color', '#E0E0E0')
        self.ax.tick_params(axis='x', colors=tick_color)
        self.ax.tick_params(axis='y', colors=tick_color)
        
        # --- Axis Labels (e.g., "Time", "Value") ---
        label_color = self._get_color_from_theme('matplotlib_label_color', '#E0E0E0')
        self.ax.xaxis.label.set_color(label_color)
        self.ax.yaxis.label.set_color(label_color)

        # --- Title ---
        title_color = self._get_color_from_theme('matplotlib_title_color', '#00B0FF')
        if self.ax.get_title():
            self.ax.set_title(self.ax.get_title(), color=title_color)
        
        # --- Grid Lines ---
        grid_color = self._get_color_from_theme('matplotlib_grid_color', '#555555')
        self.ax.grid(True, linestyle=':', alpha=0.6, color=grid_color)

        # --- Legend ---
        legend = self.ax.get_legend()
        if legend:
            legend_facecolor = self._get_color_from_theme('matplotlib_legend_facecolor', '#4A4A4A')
            legend_edgecolor = self._get_color_from_theme('matplotlib_edgecolor', '#606060') 
            legend_label_color = self._get_color_from_theme('matplotlib_legend_label_color', '#E0E0E0')

            legend.get_frame().set_facecolor(legend_facecolor)
            legend.get_frame().set_edgecolor(legend_edgecolor)
            for text in legend.get_texts():
                text.set_color(legend_label_color)

        # --- Apply Font Settings (separate method, but part of theming) ---
        self.apply_font_settings() 

        self.canvas.draw_idle() 
        logger.debug("MatplotlibWidget: Matplotlib theme elements applied.")


    def apply_initial_theme(self):
        """Applies theme colors based on the current self.theme_colors on initialization."""
        logger.debug("MatplotlibWidget: Applying initial theme.")
        self._apply_matplotlib_theme_elements() 
        logger.debug("MatplotlibWidget: Initial theme applied.")

    def set_toolbar_visibility(self, hide):
        """
        Sets the visibility of the Matplotlib toolbar.
        :param hide: Boolean, True to hide, False to show.
        """
        self.toolbar.setVisible(not hide)
        self.hide_toolbar = hide
        logger.debug(f"MatplotlibWidget: Toolbar visibility set to {'hidden' if hide else 'visible'}.")

    def plot_series(self, series_data, plot_title="", x_label="", y_label="",
                    time_series=False, show_legend=True, draw_now=True, clear_plot=True):
        """
        Plots multiple series on the Matplotlib figure.
        :param series_data: A list of dictionaries, each containing 'x_data', 'y_data', 'label', 'color'.
                            Optionally, 'low_threshold', 'high_threshold' for horizontal lines.
        :param plot_title: Title of the plot.
        :param x_label: Label for the x-axis.
        :param y_label: Label for the y-axis.
        :param time_series: If True, format x-axis as time.
        :param show_legend: If True, display the legend.
        :param draw_now: If True, redraw the canvas immediately.
        :param clear_plot: If True, clear the existing plot before drawing.
        """
        logger.debug(f"MatplotlibWidget.plot_series: Plotting {len(series_data)} series. Clear plot: {clear_plot}.")

        if clear_plot:
            self.ax.clear()
            self._apply_matplotlib_theme_elements() 
        
        if not series_data:
            self.clear_plot("No data provided to plot.")
            return

        self.ax.set_title(plot_title, color=self._get_color_from_theme('matplotlib_title_color', '#00B0FF'))
        self.ax.set_xlabel(x_label, color=self._get_color_from_theme('matplotlib_label_color', '#E0E0E0'))
        self.ax.set_ylabel(y_label, color=self._get_color_from_theme('matplotlib_label_color', '#E0E0E0'))

        theme_line_colors = self.theme_colors.get('matplotlib_line_colors', [])
        if not theme_line_colors: 
            theme_line_colors = [QColor("#F02BFE"), QColor("#D81B60"), QColor("#E040FB"), QColor("#CE93D8")] 
        
        matplotlib_line_colors_hex = []
        for color_item in theme_line_colors:
            if isinstance(color_item, QColor):
                matplotlib_line_colors_hex.append(color_item.name())
            elif isinstance(color_item, str):
                matplotlib_line_colors_hex.append(QColor(color_item).name())
            else:
                matplotlib_line_colors_hex.append('gray') 
                logger.warning(f"MatplotlibWidget: Unexpected color item in matplotlib_line_colors: {color_item}. Using gray.")

        plt.rcParams['axes.prop_cycle'] = plt.cycler(color=matplotlib_line_colors_hex)

        for i, series in enumerate(series_data):
            x_data = series.get('x_data', [])
            y_data = series.get('y_data', [])
            label = series.get('label', f"Series {i+1}")
            
            series_color_val = series.get('color') 
            if series_color_val is None:
                plot_kwargs = {'label': label, 'linewidth': 2}
            else:
                specific_color_hex = self._get_color_from_theme(None, series_color_val) 
                plot_kwargs = {'label': label, 'color': specific_color_hex, 'linewidth': 2}


            filtered_data = [(x, y) for x, y in zip(x_data, y_data) if y is not None]
            if not filtered_data:
                logger.warning(f"MatplotlibWidget: No valid data points for series '{label}'. Skipping plot for this series.")
                continue
            
            filtered_x_data, filtered_y_data = zip(*filtered_data) 
            
            self.ax.plot(filtered_x_data, filtered_y_data, **plot_kwargs)

            # Plot thresholds
            low_threshold = series.get('low_threshold')
            high_threshold = series.get('high_threshold')
            
            threshold_low_color = self._get_color_from_theme('plot_threshold_low_color', '#FFC107') 
            threshold_high_color = self._get_color_from_theme('plot_threshold_high_color', '#FF5252') 

            if low_threshold is not None:
                self.ax.axhline(y=low_threshold, color=threshold_low_color, 
                                linestyle='--', linewidth=1, label='Low Threshold')
            if high_threshold is not None:
                self.ax.axhline(y=high_threshold, color=threshold_high_color, 
                                linestyle='--', linewidth=1, label='High Threshold')

        if time_series:
            self.figure.autofmt_xdate() 

        # --- FIX: Force Matplotlib to recompute limits after plotting new data ---
        self.ax.relim()  # Recalculate plot limits based on the new data
        self.ax.autoscale_view(True, True, False) # Autoscale x and y axes, but not z
        # This helps ensure the plot doesn't appear flat if the data range is small.
        # --- END FIX ---

        if show_legend:
            legend_facecolor = self._get_color_from_theme('matplotlib_legend_facecolor', '#4A4A4A')
            legend_edgecolor = self._get_color_from_theme('matplotlib_edgecolor', '#606060')
            legend_label_color = self._get_color_from_theme('matplotlib_legend_label_color', '#E0E0E0')

            handles, labels = self.ax.get_legend_handles_labels()
            unique_labels = list(dict.fromkeys(labels)) 
            unique_handles = [handles[labels.index(ul)] for ul in unique_labels]

            self.ax.legend(unique_handles, unique_labels, loc='best', frameon=True, 
                           facecolor=legend_facecolor,
                           edgecolor=legend_edgecolor,
                           labelcolor=legend_label_color)
        
        self.figure.tight_layout() 

        self.hide_status_message() 
        if draw_now:
            self.draw()
        logger.info("MatplotlibWidget: Data plotted and canvas redrawn.")

    def apply_font_settings(self):
        """Applies font settings to all text elements in the plot."""
        logger.debug("MatplotlibWidget: Applying font settings.")
        font_family = self.theme_colors.get('plot_font_family', "Inter")
        font_size = self.theme_colors.get('plot_font_size', 10)
        
        matplotlib.rcParams['font.family'] = font_family
        matplotlib.rcParams['font.size'] = font_size
        
        title_color = self._get_color_from_theme('matplotlib_title_color', '#00B0FF')
        label_color = self._get_color_from_theme('matplotlib_label_color', '#E0E0E0')
        tick_color = self._get_color_from_theme('matplotlib_tick_color', '#E0E0E0')
        legend_label_color = self._get_color_from_theme('matplotlib_legend_label_color', '#E0E0E0')

        self.ax.set_title(self.ax.get_title(), fontdict={'family': font_family, 'size': font_size, 'color': title_color})
        self.ax.set_xlabel(self.ax.get_xlabel(), fontdict={'family': font_family, 'size': font_size, 'color': label_color})
        self.ax.set_ylabel(self.ax.get_ylabel(), fontdict={'family': font_family, 'size': font_size, 'color': label_color})

        for tick_label in self.ax.get_xticklabels() + self.ax.get_yticklabels():
            tick_label.set_fontsize(font_size)
            tick_label.set_fontfamily(font_family)
            tick_label.set_color(tick_color)
        
        for text_obj in self.ax.texts:
            text_obj.set_fontfamily(font_family)
            text_obj.set_fontsize(font_size)
            text_obj.set_color(self._get_color_from_theme('matplotlib_text_color', '#E0E0E0')) 

        if self.ax.legend_:
            for text in self.ax.legend_.get_texts():
                text.set_fontsize(font_size)
                text.set_fontfamily(font_family)
                text.set_color(legend_label_color)
        
        logger.debug(f"MatplotlibWidget: Applied font family: {font_family}, size: {font_size}.")

    def clear_plot(self, message=""):
        """Clears the plot and optionally displays a message."""
        logger.debug(f"MatplotlibWidget.clear_plot: Clearing plot with message: '{message}'.")
        self.ax.clear()
        
        self._apply_matplotlib_theme_elements() 

        if message:
            self.show_status_message(message)
        else:
            self.hide_status_message()
            
        self.draw() 
        logger.info("MatplotlibWidget: Plot cleared.")

    def draw(self):
        """Redraws the canvas."""
        self.canvas.draw_idle()

    @pyqtSlot(dict)
    def update_theme_colors(self, new_theme_colors):
        """
        Updates the theme colors for the plot elements and reapplies them.
        :param new_theme_colors: Dictionary of new theme colors.
        """
        logger.debug("MatplotlibWidget.update_theme_colors: Called with new theme colors.")
        self.theme_colors.update(new_theme_colors)

        for key, value in self.theme_colors.items():
            if isinstance(value, str) and value.startswith('#'): 
                self.theme_colors[key] = QColor(value)
            elif isinstance(value, list) and key == 'matplotlib_line_colors': 
                new_list = []
                for item in value:
                    if isinstance(item, str):
                        new_list.append(QColor(item))
                    else:
                        new_list.append(item)
                self.theme_colors[key] = new_list

        self._apply_matplotlib_theme_elements() 
        
        self.style().polish(self) 
        
        logger.info("MatplotlibWidget: Theme colors updated.")

    def show_status_message(self, message):
        """Displays a status message over the plot area."""
        self.status_label.setText(message)
        self.status_label.show()
        self.canvas.hide()
        self.toolbar.hide()
        logger.debug(f"MatplotlibWidget: Showing status message: {message}")

    def hide_status_message(self):
        """Hides the status message and shows the plot canvas."""
        self.status_label.hide()
        self.canvas.show()
        if not self.hide_toolbar: 
            self.toolbar.show()
        logger.debug("MatplotlibWidget: Hiding status message.")

