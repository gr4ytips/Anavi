import os
import sys
import logging

from PyQt5.QtWidgets import QTabWidget, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal # Import pyqtSignal

# Import your tab widgets
from widgets.dashboard_tab import DashboardTab
from widgets.sensor_details_tab import SensorDetailsTab
from widgets.plot_tab_widget import PlotTabWidget # IMPORT THE NEW PLOT TAB
from widgets.settings_tab import SettingsTab
from widgets.about_tab import AboutTab 

logger = logging.getLogger(__name__)

class AnaviSensorUI(QTabWidget): # Inherit from QTabWidget
    """
    Manages the main tabbed user interface for the Anavi Sensor Dashboard,
    including Dashboard, Sensor Details, and Settings tabs.
    """
    # Define a signal to emit when UI customization (gauge type/style) changes.
    # This signal will be connected to MainWindow's method to apply changes globally.
    ui_customization_changed = pyqtSignal(str, str) # Arguments: gauge_type (str), gauge_style (str)
    
    # NEW: Define a signal to emit when the theme changes (this signal will be emitted by AnaviSensorUI).
    theme_changed = pyqtSignal(str) # Argument: theme_file_name (str)

    # Signal specifically for threshold changes. Emits the entire updated thresholds dictionary.
    thresholds_updated = pyqtSignal(dict) # ADDED: Signal for threshold updates

    def __init__(self, data_store, settings_manager, thresholds, main_window, theme_colors, initial_gauge_type, initial_gauge_style):
        super().__init__()
        self.setObjectName("AnaviSensorUI") # Give the main tab widget an object name for QSS

        self.data_store = data_store
        self.settings_manager = settings_manager
        # CRITICAL: This is a reference to the global thresholds dictionary in MainWindow.
        # Changes to this dict in MainWindow will be reflected here.
        self.thresholds = thresholds 
        self.main_window = main_window # Store reference to MainWindow
        self.theme_colors = theme_colors # This is a shared reference to MainWindow's theme_colors
        self.current_gauge_type = initial_gauge_type
        self.current_gauge_style = initial_gauge_style
        
        # --- NEW: Store the last received sensor data here for easy access ---
        self.current_sensor_data = {} 
        # ------------------------------------------------------------------

        # Initialize tabs (pass necessary parameters)
        # --- FIX: Ensure a defensive copy of theme_colors is passed to tabs if they modify it ---
        # For DashboardTab, SensorDetailsTab, PlotTabWidget, SettingsTab, AboutTab,
        # it's better they work on their own copy of theme_colors or accept updates
        # The current design passes a mutable reference, which is fine if updates are always
        # propagated. Let's ensure the tabs' __init__ handles it by making a copy if needed.
        self.dashboard_tab = DashboardTab(self.data_store, self.thresholds, self.main_window, dict(self.theme_colors), self.current_gauge_type, self.current_gauge_style, parent=self)
        self.sensor_details_tab = SensorDetailsTab(self.data_store, self.thresholds, self.main_window, dict(self.theme_colors), self.current_gauge_type, self.current_gauge_style, parent=self)
        
        # INSTANTIATE THE NEW PLOT TAB
        self.plot_tab = PlotTabWidget(self.data_store, self.settings_manager, dict(self.theme_colors), parent=self) 

        # Pass self.thresholds and theme_colors to SettingsTab
        self.settings_tab = SettingsTab(self.settings_manager, self.main_window, dict(self.theme_colors), self.current_gauge_type, self.current_gauge_style, parent=self)
        self.about_tab = AboutTab(self.main_window, dict(self.theme_colors), parent=self) # Only pass main_window and theme_colors

        # ADD TABS IN THE DESIRED ORDER
        self.addTab(self.dashboard_tab, "Dashboard")
        self.addTab(self.sensor_details_tab, "Sensor Details")
        self.addTab(self.plot_tab, "Plot") # ADDED: New Plot tab, before Settings
        self.addTab(self.settings_tab, "Settings")
        self.addTab(self.about_tab, "About")

        # Set size policy to expand
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Connect signals from SettingsTab to AnaviSensorUI
        # This allows SettingsTab to inform AnaviSensorUI about UI customization changes
        self.settings_tab.ui_customization_changed.connect(self.propagate_gauge_style_change)
        self.settings_tab.theme_changed.connect(self.theme_changed.emit) # Relay theme change signal
        
        # Connect settings_tab's thresholds_updated to AnaviSensorUI's own thresholds_updated signal
        # This is the path for SettingsTab to inform MainWindow via AnaviSensorUI
        self.settings_tab.thresholds_updated.connect(self.thresholds_updated.emit) 

        # Connect tab change to update relevant tab data
        self.currentChanged.connect(self._on_tab_changed)

        # Apply initial theme colors to all tabs
        # This will now trigger the update_theme_colors method in each tab
        self.update_theme_colors_globally(self.theme_colors)
        
        logger.info("AnaviSensorUI: UI tabs initialized and added.")


    def update_sensor_displays(self, sensor_data):
        """
        Updates the displays on DashboardTab and SensorDetailsTab with the latest sensor data.
        This method is connected to data_store.data_updated signal from MainWindow.
        `sensor_data` is the structured dictionary from DataStore.
        """
        logger.debug(f"AnaviSensorUI: update_sensor_displays called with new sensor_data keys: {sensor_data.keys()}")
        # --- NEW: Store the incoming data ---
        self.current_sensor_data = sensor_data
        # -----------------------------------

        # Propagate to DashboardTab
        if self.dashboard_tab:
            self.dashboard_tab.update_sensor_values(sensor_data)
        else:
            logger.warning("AnaviSensorUI: DashboardTab not initialized.")

        # Propagate to SensorDetailsTab
        if self.sensor_details_tab:
            self.sensor_details_tab.update_sensor_values(sensor_data)
        else:
            logger.warning("AnaviSensorUI: SensorDetailsTab not initialized.")

        # The SettingsTab preview gauge also needs to be updated with current data
        if self.settings_tab and self.settings_tab.preview_gauge:
            # For the preview gauge, we'll try to feed a specific metric, e.g., HTU21D Temperature
            # Ensure lookup is lowercase as per SettingsManager's return format
            htu21d_temp_data = sensor_data.get('htu21d', {}).get('temperature', {})
            if 'value' in htu21d_temp_data:
                self.settings_tab.preview_gauge.update_value(htu21d_temp_data['value'])
            else:
                # If no real data, pass a mock value to the preview for visualization purposes
                self.settings_tab.preview_gauge.update_value(25.0) 
            logger.debug(f"AnaviSensorUI: SettingsTab preview gauge updated with {'real' if 'value' in htu21d_temp_data else 'mock'} value.")

        # NEW: Plot Tab also receives data updates for its plot
        if self.plot_tab:
            # Although PlotTab has its own update_plot_data, we can trigger it here if live updates are desired
            # or rely on its own internal timer if it has one. For now, we'll let its timer handle it.
            pass


    def _on_tab_changed(self, index):
        """Handle tab change events to update specific tabs."""
        logger.info(f"AnaviSensorUI: Tab changed to index {index}.")
        current_widget = self.widget(index)

        # When switching to a tab, ensure its data is refreshed.
        # This is particularly important for plots which might have time range selections.
        if isinstance(current_widget, DashboardTab):
            logger.debug("AnaviSensorUI: Switched to DashboardTab. Updating its plot data.")
            current_widget.update_plot_data() 
        elif isinstance(current_widget, SensorDetailsTab):
            logger.debug("AnaviSensorUI: Switched to SensorDetailsTab. Updating all its plots.")
            current_widget.update_all_plots() # Corrected method name to update_all_plots
        elif isinstance(current_widget, PlotTabWidget): # NEW: Handle PlotTabWidget
            logger.debug("AnaviSensorUI: Switched to PlotTabWidget. Updating plot data.")
            current_widget.update_plot_data() # Trigger update for the new plot tab
        elif isinstance(current_widget, SettingsTab):
            logger.debug("AnaviSensorUI: Switched to SettingsTab. Updating threshold display.")
            current_widget.update_threshold_display() # Ensure current thresholds are shown
            # Also update the preview gauge with current data if available
            if self.settings_tab.preview_gauge and self.current_sensor_data:
                # Ensure lookup is lowercase as per SettingsManager's return format
                htu21d_temp_data = self.current_sensor_data.get('htu21d', {}).get('temperature', {})
                if 'value' in htu21d_temp_data:
                    self.settings_tab.preview_gauge.update_value(htu21d_temp_data['value'])
                else:
                    self.settings_tab.preview_gauge.update_value(25.0) # Mock value for preview
        elif isinstance(current_widget, AboutTab):
            logger.debug("AnaviSensorUI: Switched to AboutTab. Ensuring theme is applied.")
            current_widget.update_theme_colors(self.theme_colors) # Ensure AboutTab has latest theme

    def initialize_all_tab_data(self):
        """
        Initializes data for all tabs. Called once during main app startup
        and potentially on major setting changes (like max_data_points).
        """
        logger.info("AnaviSensorUI: Initializing all tab data (plots, initial display values).")
        # Ensure all tabs are properly initialized with data, especially plots
        # Pass the current theme colors to ensure plots initialize with correct themes
        if self.dashboard_tab:
            # Pass the internal theme_colors of AnaviSensorUI, which should be fresh
            self.dashboard_tab.initialize_tab_data(self.theme_colors)
        if self.sensor_details_tab:
            # Pass the internal theme_colors of AnaviSensorUI, which should be fresh
            self.sensor_details_tab.initialize_tab_data(self.theme_colors)
        if self.plot_tab: # NEW: Initialize the PlotTab
            # PlotTab's initialize_tab_data handles its own theme update internally via its self.theme_colors
            self.plot_tab.initialize_tab_data()
        # Settings tab only needs its threshold display to be refreshed on init
        if self.settings_tab:
            self.settings_tab.update_threshold_display() # This refreshes the input fields
            if self.settings_tab.preview_gauge and self.current_sensor_data:
                # Update preview gauge with initial data if available
                # Ensure lookup is lowercase as per SettingsManager's return format
                htu21d_temp_data = self.current_sensor_data.get('htu21d', {}).get('temperature', {})
                if 'value' in htu21d_temp_data:
                    self.settings_tab.preview_gauge.update_value(htu21d_temp_data['value'])
                else:
                    self.settings_tab.preview_gauge.update_value(25.0) # Mock value for preview
        if self.about_tab:
            self.about_tab.update_theme_colors(self.theme_colors) # Ensure AboutTab has latest theme


    def propagate_gauge_style_change(self, gauge_type, gauge_style):
        """
        Propagates gauge type and style changes to all relevant display widgets across tabs.
        This is called by SettingsTab via AnaviSensorUI's signal.
        """
        logger.info(f"AnaviSensorUI: Propagating gauge style change (Type='{gauge_type}', Style='{gauge_style}') to Dashboard and Sensor Details tabs.")
        self.current_gauge_type = gauge_type
        self.current_gauge_style = gauge_style
        
        # Emit signal for MainWindow to also know about the change and save it
        self.ui_customization_changed.emit(gauge_type, gauge_style)

        if self.dashboard_tab:                
            self.dashboard_tab.update_gauge_styles(gauge_type, gauge_style) # Corrected method name
        else:
            logger.warning("AnaviSensorUI: DashboardTab not initialized or does not have 'update_gauge_styles' method.")                
            
        if self.sensor_details_tab:
            self.sensor_details_tab.update_gauge_styles(gauge_type, gauge_style) # Corrected method name
        else:
            logger.warning("AnaviSensorUI: SensorDetailsTab not initialized or does not have 'update_gauge_styles' method.")

        # SettingsTab's preview gauge handles its own style update internally

        # After updating styles, force a repaint of the current tab to ensure immediate visual update
        self.currentWidget().repaint()
        logger.debug("AnaviSensorUI: Repainted current widget after gauge style propagation.")

    def update_theme_colors_globally(self, theme_colors):
        """
        Updates the theme colors across all tabs and their contained widgets.
        This is called by MainWindow when the theme changes.
        """
        logger.info("AnaviSensorUI: Updating theme colors globally across all tabs.")
        self.theme_colors.clear() # Clear old colors
        self.theme_colors.update(theme_colors) # Update with new colors
        
        # Apply QSS to the AnaviSensorUI itself
        self.style().polish(self)
        
        # Propagate to individual tabs
        if self.dashboard_tab:
            self.dashboard_tab.update_theme_colors(self.theme_colors)
        if self.sensor_details_tab:
            self.sensor_details_tab.update_theme_colors(self.theme_colors)
        if self.plot_tab: # NEW: Propagate theme colors to the PlotTab
            self.plot_tab.update_theme_colors(self.theme_colors)
        if self.settings_tab:
            self.settings_tab.update_theme_colors(self.theme_colors)
        if self.about_tab:
            self.about_tab.update_theme_colors(self.theme_colors)

        # Force repaint of current tab after theme update
        self.currentWidget().repaint()
        logger.debug("AnaviSensorUI: Repainted current widget after global theme color update.")


    def update_thresholds(self, new_thresholds):
        """
        Updates the internal thresholds dictionary and propagates the changes
        to all display widgets that rely on these thresholds.
        This method is called by MainWindow (which received signal from SettingsTab).
        """
        logger.info("AnaviSensorUI: Updating internal thresholds dictionary.")
        # Update the internal reference to the global thresholds dictionary
        # This self.thresholds is ALREADY a reference to MainWindow's thresholds,
        # so simply updating its contents is sufficient.
        self.thresholds.clear()
        # --- FIX: Ensure new_thresholds uses lowercase keys for internal consistency ---
        # The new_thresholds comes from SettingsTab, which now passes lowercase keys.
        # So we just update the self.thresholds with that.
        self.thresholds.update(new_thresholds) 
        logger.debug(f"AnaviSensorUI: Internal thresholds updated to: {self.thresholds}")

        # Propagate these updated thresholds to relevant tabs and their display widgets
        self.update_thresholds_for_display_widgets(self.thresholds) # Pass the now updated self.thresholds
        
        # Also ensure plots are updated as they use thresholds for alert lines
        if self.dashboard_tab: # Ensure the plot updates with new thresholds
            self.dashboard_tab.update_plot_data() 
        if self.sensor_details_tab: # Ensure all plots update with new thresholds
            self.sensor_details_tab.update_all_plots() # Corrected method name to update_all_plots
        if self.plot_tab: # NEW: Update plot tab with new thresholds (via re-plotting)
            self.plot_tab.update_plot_data()


    def update_thresholds_for_display_widgets(self, new_thresholds):
        """
        This method is called by MainWindow when the global thresholds change.
        It updates the thresholds for all display widgets across different tabs.
        It's essentially a duplicate of `update_thresholds` but kept for clarity 
        of what `MainWindow` explicitly calls. Can be refactored to call `update_thresholds`.
        """
        logger.info("AnaviSensorUI: Updating thresholds for display widgets globally (called by MainWindow).")
        # Ensure that the display widgets themselves get the updated threshold dictionary *for their specific metric*.
        # Dashboard Tab
        if self.dashboard_tab:
            for sensor_metric_key, display_widget in self.dashboard_tab.sensor_display_widgets.items():
                parts = sensor_metric_key.split('_')
                sensor_type = parts[0].lower() # Ensure lowercase for lookup
                metric_type = '_'.join(parts[1:]).lower() # Ensure lowercase for lookup
                # Pass only the relevant part of the new_thresholds dictionary to the widget
                metric_specific_thresholds = new_thresholds.get(sensor_type, {}).get(metric_type, {})
                display_widget.update_thresholds(metric_specific_thresholds) # Call update_thresholds on the widget
                logger.debug(f"AnaviSensorUI: Updated thresholds for DashboardTab {sensor_type}-{metric_type}: {metric_specific_thresholds}")

        # Sensor Details Tab
        if self.sensor_details_tab:
            for sensor_metric_key, display_widget in self.sensor_details_tab.sensor_display_widgets.items():
                parts = sensor_metric_key.split('_')
                sensor_type = parts[0].lower() # Ensure lowercase for lookup
                metric_type = parts[1].lower() # Ensure lowercase for lookup
                # Pass only the relevant part of the new_thresholds dictionary to the widget
                metric_specific_thresholds = new_thresholds.get(sensor_type, {}).get(metric_type, {})
                display_widget.update_thresholds(metric_specific_thresholds) # Call update_thresholds on the widget
                logger.debug(f"AnaviSensorUI: Updated thresholds for SensorDetailsTab {sensor_type}-{metric_type}: {metric_specific_thresholds}")
        
        # SettingsTab's preview gauge
        if self.settings_tab and self.settings_tab.preview_gauge:
            # For the preview gauge, use HTU21D Temperature thresholds as an example
            preview_thresholds = new_thresholds.get('htu21d', {}).get('temperature', {}) # Ensure lowercase lookup
            self.settings_tab.preview_gauge.update_thresholds(preview_thresholds)
            logger.debug(f"AnaviSensorUI: Updated thresholds for SettingsTab preview gauge: {preview_thresholds}")

        # After updating thresholds, force repaint of current tab to ensure immediate visual update
        self.currentWidget().repaint()
        logger.debug("AnaviSensorUI: Repainted current widget after thresholds propagation.")


    def get_unit_for_metric(self, metric_type):
        """
        Returns the unit for a given metric type. Used by plots tab for labels.
        This method is now called from settings_manager or directly by tabs if needed,
        not directly from AnaviSensorUI anymore.
        """
        unit_map = {
            "temperature": "\u00B0C", # Use unicode escape here as well for consistency
            "humidity": "%",
            "pressure": "hPa",
            "light": "lx"
        }
        unit = unit_map.get(metric_type.lower(), "")
        logger.debug(f"AnaviSensorUI: get_unit_for_metric called for '{metric_type}', returning '{unit}'.")
        return unit

    def get_current_sensor_data(self):
        """
        Returns the last received sensor data. Useful for tabs to retrieve the latest data
        if they need to update outside of the direct signal connection.
        """
        return self.current_sensor_data

