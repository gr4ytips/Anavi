import os
import re
import logging
import json # Import json for handling list of colors

from data_management.settings import SettingsManager 

# Initialize logger for this module
logger = logging.getLogger(__name__)

class QSSParser:
    """
    Parses QSS files to extract color variables and provides utilities
    for managing QSS themes.
    Enhanced to extract colors from rules with [type_class] and [style_class] attributes,
    and from special comment blocks for Matplotlib and custom drawing, ensuring
    all properties are correctly extracted and prefixed, with explicit override logic.
    """
    def __init__(self, settings_manager): 
        self.settings_manager = settings_manager 
        self.theme_colors_cache = {} 

        self._theme_colors_map = {} 
        
        self.property_regex = re.compile(r'([\w-]+):\s*([^;]+);') # Original regex for standard QSS properties

        # Refined block regex to be more robust for the block header itself
        self.block_comment_section_regex = re.compile(
            r'/\*\s*(?P<block_name>matplotlib|custom_drawing_colors)\s*\*/\s*'
            r'(?P<block_content>.*?)(?=\s*/\*|$)', 
            re.DOTALL | re.IGNORECASE
        )
        # CRITICAL FIX: Simplified regex for properties *within* a block.
        # It now expects "key: value;" and ignores anything after the semicolon on that line.
        # It will NOT match lines that start with '/*' (which is desired for fully commented lines).
        self.block_property_comment_regex = re.compile(
            r'^\s*(?P<key>[\w-]+):\s*(?P<value>[^;]+);.*$', # Simplified: removed optional /* and */ from the start/end of the match
            re.MULTILINE | re.IGNORECASE
        )

        self._load_qss_theme_colors() 
        logger.info("QSSParser: Initialized.")

    @staticmethod
    def _resolve_color_value(color_string, default_color="#FFFFFF"):
        """
        Resolves a color string, handling None, 'transparent', or 'none'.
        If color_string is None, returns default_color.
        If 'transparent' or 'none', returns 'transparent' (actual string) or default_color if needed elsewhere.
        """
        if color_string is None:
            return default_color
        if isinstance(color_string, str) and (
            color_string.lower().strip() == "transparent" or color_string.lower().strip() == "none"
        ):
            return "transparent" # Return the string "transparent" for special handling
        return color_string # Otherwise, return the color string as is

    def _parse_qss_block_comments(self, qss_content):
        """
        Parses special comment blocks (like /*matplotlib*/ or /*custom_drawing_colors*/)
        to extract key-value color pairs within them.
        """
        extracted_colors = {}
        for match in self.block_comment_section_regex.finditer(qss_content):
            block_name = match.group('block_name').lower()
            block_content = match.group('block_content')
            
            # Prefix for the extracted keys
            prefix = ""
            if block_name == "matplotlib":
                prefix = "matplotlib_"
            elif block_name == "custom_drawing_colors":
                # For custom_drawing_colors, the keys are usually already descriptive
                # We'll handle 'font_family' and 'digital_font_family' separately if needed,
                # but generally, we want to keep their names as is.
                pass 
            
            logger.debug(f"QSSParser: Processing block '{block_name}'. Content snippet: '{block_content[:100]}...'")

            properties_found_in_block = False
            for prop_match in self.block_property_comment_regex.finditer(block_content):
                key = prop_match.group('key').strip()
                value = prop_match.group('value').strip()

                # Special handling for line_colors which is a comma-separated list
                if key == "line_colors":
                    # Parse the comma-separated string into a Python list
                    extracted_colors[f"{prefix}{key}"] = [color.strip() for color in value.split(',')]
                    logger.debug(f"QSSParser: Extracted block property (list): '{prefix}{key}': {extracted_colors[f'{prefix}{key}']}")
                else:
                    # Resolve color value or keep as is for other properties
                    resolved_value = self._resolve_color_value(value)
                    extracted_colors[f"{prefix}{key}"] = resolved_value
                    logger.debug(f"QSSParser: Extracted block property: '{prefix}{key}': '{resolved_value}'")
                properties_found_in_block = True
            
            if not properties_found_in_block:
                logger.debug(f"QSSParser: No properties found within block '{block_name}'.")

        return extracted_colors


    def parse_qss_colors(self, qss_content, theme_name=""):
        """
        Parses the QSS content to extract specific color properties and attributes.
        This now prioritizes the new block comments for matplotlib and custom drawing,
        and then falls back to general QSS rules.
        """
        parsed_colors = SettingsManager.DEFAULT_THEME_COLORS.copy() # Start with defaults
        
        # 1. Parse special comment blocks first (highest priority for these specific keys)
        block_colors = self._parse_qss_block_comments(qss_content)
        parsed_colors.update(block_colors)

        # 2. Parse standard QSS rules
        # Pattern to find rules like QObject[property="value"] { ... } or QObject { ... }
        # This regex looks for a selector (e.g., QMainWindow, QLabel, QGroupBox[style_class="..."])
        # and then captures the content within its curly braces.
        rule_pattern = re.compile(r'(?P<selector>[^{]+)\\{(?P<properties>[^}]+)\\}')

        for rule_match in rule_pattern.finditer(qss_content):
            selector = rule_match.group('selector').strip()
            properties_block = rule_match.group('properties').strip()
            
            # Extract common properties like background-color, color, border, border-radius
            for prop_match in self.property_regex.finditer(properties_block):
                key = prop_match.group(1).strip()
                value = prop_match.group(2).strip()

                # General rules:
                if selector == "QMainWindow":
                    if key == "background-color": parsed_colors['main_window_background'] = self._resolve_color_value(value)
                    elif key == "color": parsed_colors['main_window_text_color'] = self._resolve_color_value(value)
                    elif key == "border": parsed_colors['main_window_border'] = value # Keep border string as is
                    elif key == "border-radius": parsed_colors['main_window_border_radius'] = value # Keep radius string as is
                
                elif selector == "QLabel":
                    if key == "color": parsed_colors['label_color'] = self._resolve_color_value(value)
                    elif key == "font-size": parsed_colors['label_font_size'] = value
                
                elif selector == "QPushButton":
                    if key == "background-color": parsed_colors['pushbutton_background_color'] = self._resolve_color_value(value)
                    elif key == "color": parsed_colors['pushbutton_color'] = self._resolve_color_value(value)
                    elif key == "border-radius": parsed_colors['pushbutton_border_radius'] = value
                    elif key == "padding": parsed_colors['pushbutton_padding'] = value
                    elif key == "font-size": parsed_colors['pushbutton_font_size'] = value

                elif selector == "QPushButton:hover":
                    if key == "background-color": parsed_colors['qpushbutton:hover_background_color'] = self._resolve_color_value(value)
                elif selector == "QPushButton:pressed":
                    if key == "background-color": parsed_colors['qpushbutton:pressed_background_color'] = self._resolve_color_value(value)

                elif selector == "QLineEdit":
                    if key == "background-color": parsed_colors['lineedit_background_color'] = self._resolve_color_value(value)
                    elif key == "color": parsed_colors['lineedit_color'] = self._resolve_color_value(value)
                    elif key == "border-radius": parsed_colors['lineedit_border_radius'] = value
                    elif key == "padding": parsed_colors['lineedit_padding'] = value
                elif selector == "QLineEdit:focus":
                    if key == "border": parsed_colors['qlineedit:focus_border'] = value

                elif selector == "QComboBox":
                    if key == "background-color": parsed_colors['combobox_background_color'] = self._resolve_color_value(value)
                    elif key == "color": parsed_colors['combobox_color'] = self._resolve_color_value(value)
                    elif key == "border": parsed_colors['combobox_border'] = value
                    elif key == "border-radius": parsed_colors['combobox_border_radius'] = value
                    elif key == "padding": parsed_colors['combobox_padding'] = value
                
                elif selector == "QComboBox QAbstractItemView":
                    if key == "background-color": parsed_colors['combobox_itemview_background_color'] = self._resolve_color_value(value)
                    elif key == "color": parsed_colors['combobox_itemview_color'] = self._resolve_color_value(value)
                    elif key == "selection-background-color": parsed_colors['combobox_itemview_selection_background_color'] = self._resolve_color_value(value)

                elif selector == "QCheckBox":
                    if key == "color": parsed_colors['checkbox_color'] = self._resolve_color_value(value)
                    elif key == "spacing": parsed_colors['checkbox_spacing'] = value

                elif selector == "QProgressBar":
                    # This targets the trough of the progress bar
                    if key == "background-color": parsed_colors['progressbar_background_color_trough'] = self._resolve_color_value(value)
                    elif key == "border": parsed_colors['progressbar_border_trough'] = value
                    elif key == "border-radius": parsed_colors['progressbar_border_radius_trough'] = value
                    elif key == "color": parsed_colors['progressbar_text_color'] = self._resolve_color_value(value)
                    elif key == "font-size": parsed_colors['progressbar_font_size'] = value
                    
                # QTabWidget
                elif selector == "QTabWidget::pane":
                    if key == "background": parsed_colors['tab_pane_background'] = self._resolve_color_value(value)
                    elif key == "border": parsed_colors['tab_pane_border'] = value
                    elif key == "border-radius": parsed_colors['tab_pane_border_radius'] = value

                elif selector == "QTabBar::tab":
                    if key == "background": parsed_colors['tab_background_inactive'] = self._resolve_color_value(value)
                    elif key == "color": parsed_colors['tab_text_color_inactive'] = self._resolve_color_value(value)
                    elif key == "border": parsed_colors['tab_border'] = value
                    elif key == "border-top-left-radius": parsed_colors['tab_border_top_left_radius'] = value
                    elif key == "border-top-right-radius": parsed_colors['tab_border_top_right_radius'] = value
                
                elif selector == "QTabBar::tab:selected":
                    if key == "background": parsed_colors['tab_background_active'] = self._resolve_color_value(value)
                    elif key == "color": parsed_colors['tab_text_color_active'] = self._resolve_color_value(value)
                    elif key == "border-bottom-color": parsed_colors['tab_border_bottom_color_active'] = self._resolve_color_value(value)

                # QLabel.alert
                elif selector == "QLabel.alert":
                    if key == "color": parsed_colors['label_alert_color'] = self._resolve_color_value(value)
                
                # QGroupBox.alert
                elif selector == "QGroupBox.alert":
                    if key == "border": parsed_colors['groupbox_alert_border'] = value


                # Handle QGroupBox with [style_class] and [type_class]
                groupbox_style_match = re.search(r'QGroupBox\[style_class="([^"]+)"\]', selector)
                groupbox_type_match = re.search(r'QGroupBox\[type_class="([^"]+)"\]', selector)

                if groupbox_style_match:
                    style_class = groupbox_style_match.group(1).strip()
                    # Example: groupbox_style_1_flat_background_color
                    prefix = f"groupbox_{style_class}_"
                    if key == "background-color": parsed_colors[f"{prefix}background_color"] = self._resolve_color_value(value)
                    elif key == "border": parsed_colors[f"{prefix}border"] = value
                    elif key == "border-radius": parsed_colors[f"{prefix}border_radius"] = value
                    elif key == "color": parsed_colors[f"{prefix}color"] = self._resolve_color_value(value) # Title color

                # Handle QLabel with [style_class]
                label_style_match = re.search(r'QLabel\[style_class="([^"]+)"\]', selector)
                if label_style_match:
                    style_class = label_style_match.group(1).strip()
                    # Example: label_style_1_flat_color
                    prefix = f"label_{style_class}_"
                    if key == "color": parsed_colors[f"{prefix}color"] = self._resolve_color_value(value)

                # Handle QProgressBar with [style_class]
                progressbar_style_match = re.search(r'QProgressBar\[style_class="([^"]+)"\]', selector)
                if progressbar_style_match:
                    style_class = progressbar_style_match.group(1).strip()
                    # Example: progressbar_style_1_flat_background_color
                    prefix = f"progressbar_{style_class}_"
                    if key == "background-color": parsed_colors[f"{prefix}background_color"] = self._resolve_color_value(value)
                    elif key == "border": parsed_colors[f"{prefix}border"] = value
                    elif key == "border-radius": parsed_colors[f"{prefix}border_radius"] = value
                    elif key == "color": parsed_colors[f"{prefix}color"] = self._resolve_color_value(value) # Text color

                # Handle combined QGroupBox[type_class][style_class]
                if groupbox_type_match and groupbox_style_match:
                    type_class = groupbox_type_match.group(1).strip()
                    style_class = groupbox_style_match.group(1).strip()
                    # Example: groupbox_type_3_digital_style_9_vintage_background_color
                    prefix = f"groupbox_{type_class}_{style_class}_"
                    if key == "background-color": parsed_colors[f"{prefix}background_color"] = self._resolve_color_value(value)
                    elif key == "border": parsed_colors[f"{prefix}border"] = value
                    elif key == "color": parsed_colors[f"{prefix}color"] = self._resolve_color_value(value) # Title color for combined


                # Handle combined QLabel[type_class][style_class]
                label_type_match = re.search(r'QLabel\[type_class="([^"]+)"\]', selector)
                if label_type_match and label_style_match: # Assuming label_style_match is already found
                    type_class = label_type_match.group(1).strip()
                    style_class = label_style_match.group(1).strip()
                    # Example: label_type_3_digital_style_9_vintage_color
                    prefix = f"label_{type_class}_{style_class}_"
                    if key == "color": parsed_colors[f"{prefix}color"] = self._resolve_color_value(value)
                    elif key == "font-family": parsed_colors[f"{prefix}font_family"] = value # For digital font
                    elif key == "font-size": parsed_colors[f"{prefix}font_size"] = value # For digital font size
                    elif key == "font-weight": parsed_colors[f"{prefix}font_weight"] = value # For digital font weight

        logger.debug(f"QSSParser: Parsed {len(parsed_colors)} colors for theme: {theme_name}.")
        return parsed_colors


    def _load_qss_theme_colors(self):
        """
        Loads and parses all QSS theme files found in the themes directory,
        storing the extracted colors in _theme_colors_map.
        Includes a default_theme.qss as a fallback.
        """
        theme_dir = self.settings_manager.get_theme_dir()
        if not os.path.exists(theme_dir):
            logger.error(f"QSSParser: Theme directory not found: {theme_dir}")
            return

        qss_files = [f for f in os.listdir(theme_dir) if f.endswith(('.qss', '.qss.txt'))]
        if not qss_files:
            logger.warning(f"QSSParser: No QSS theme files found in {theme_dir}.")
            return

        # Explicitly load default_theme.qss or default_theme.qss.txt first for fallback
        default_theme_filename_base = "default_theme"
        default_theme_paths = [
            os.path.join(theme_dir, f"{default_theme_filename_base}.qss"),
            os.path.join(theme_dir, f"{default_theme_filename_base}.qss.txt")
        ]
        
        default_qss_content = None
        for default_path in default_theme_paths:
            if os.path.exists(default_path):
                try:
                    with open(default_path, 'r', encoding='utf-8') as f:
                        default_qss_content = f.read()
                    self._theme_colors_map[os.path.basename(default_path)] = self.parse_qss_colors(default_qss_content, os.path.basename(default_path))
                    logger.info(f"QSSParser: Loaded base colors from '{os.path.basename(default_path)}'. Total keys: {len(self._theme_colors_map[os.path.basename(default_path)])}")
                    break
                except Exception as e:
                    logger.error(f"QSSParser: Error loading default theme '{os.path.basename(default_path)}': {e}", exc_info=True)
        
        if default_qss_content is None:
            logger.warning("QSSParser: No default theme file found or could be loaded. Custom drawing colors might be incomplete.")
            # Ensure a minimal default map exists even if no file is found
            self._theme_colors_map["default_theme.qss"] = SettingsManager.DEFAULT_THEME_COLORS.copy()


        # Now load all other QSS files
        for filename in qss_files:
            file_path = os.path.join(theme_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    qss_content = f.read()
                
                # Parse colors and store with filename as key
                self._theme_colors_map[filename] = self.parse_qss_colors(qss_content, filename)
                logger.info(f"QSSParser: Loaded colors for theme: {filename}. Total keys: {len(self._theme_colors_map[filename])}")
            except Exception as e:
                logger.error(f"QSSParser: Error loading theme file '{filename}': {e}", exc_info=True)

        logger.info(f"QSSParser: Loaded {len(self._theme_colors_map)} QSS themes into memory.")

    def get_theme_colors(self, theme_name):
        """
        Retrieves the parsed theme colors for a given theme name (e.g., 'blue_theme.qss').
        Includes logic to handle filenames with or without .qss or .qss.txt extensions.
        Falls back to default_theme.qss if the requested theme is not found.
        """
        logger.debug(f"QSSParser: get_theme_colors called for '{theme_name}'.")
        # Ensure themes are loaded if this is called before full initialization
        # or after a settings change that might invalidate the cache.
        if not self._theme_colors_map:
            logger.warning("QSSParser: _theme_colors_map is empty. Attempting to reload themes now.")
            self._load_qss_theme_colors() # Reload themes if map is empty

        # Try exact match first
        retrieved_colors = self._theme_colors_map.get(theme_name)

        # If not found, try with .qss extension
        default_theme_filename = "default_theme.qss" # Assuming this is the canonical name

        if retrieved_colors is None and not theme_name.endswith(('.qss', '.qss.txt')):
            retrieved_colors = self._theme_colors_map.get(f"{theme_name}.qss")
            if retrieved_colors is None:
                # Try with .qss.txt extension
                retrieved_colors = self._theme_colors_map.get(f"{theme_name}.qss.txt")

        # Fallback to default_theme.qss if the requested theme is not found
        if retrieved_colors is None:
            logger.warning(f"QSSParser: Theme '{theme_name}' not found. Falling back to '{default_theme_filename}'.")
            retrieved_colors = self._theme_colors_map.get(default_theme_filename, {}) # Ensure a dictionary is always returned

        logger.debug(f"QSSParser: get_theme_colors requested for '{theme_name}'. Returning map with {len(retrieved_colors)} keys.")
        return retrieved_colors.copy() # Return a copy to prevent external modification

    def get_all_theme_colors(self):
        """Returns the dictionary containing all parsed theme colors."""
        return self._theme_colors_map.copy()

    def get_current_theme_colors(self):
        """Returns the color dictionary for the currently active theme."""
        # Use settings_manager to get the current theme file name
        current_theme_file = self.settings_manager.get_setting('Appearance', 'theme', default='blue_theme.qss')
        return self.get_theme_colors(current_theme_file) # Use the existing method

    @staticmethod
    def apply_qss(widget, qss_content):
        """Applies the given QSS content to a QApplication or QWidget."""
        widget.setStyleSheet(qss_content)
        logger.debug("QSSParser: Applied QSS stylesheet.")
# data_management/qss_parser.py
import re
import logging
# QColor import is only for demonstrating QColor conversion capability in get_themed_color,
# it's not used directly within this class for parsing, as parsing extracts strings.
from PyQt5.QtGui import QColor 

logger = logging.getLogger(__name__)

class QSSParser:
    """
    A utility class for parsing custom properties from QSS files.
    This helps in bridging QSS theming with custom Python drawing logic
    by extracting specific color definitions.
    
    It focuses on extracting key-value pairs from special comment blocks like:
    /*matplotlib*/
    facecolor: #1A2A40;
    ...
    /*custom_drawing_colors*/
    font_family: Inter;
    ...
    """
    
    # Define a set of keys that are expected to contain actual color values (hex or name)
    # This helps in distinguishing color properties from font names or other strings.
    COLOR_KEYS = {
        'facecolor', 'edgecolor', 'tick_color', 'label_color', 'title_color',
        'grid_color', 'legend_facecolor', 'legend_edgecolor', 'legend_labelcolor',
        'gauge_background_normal', 'gauge_border_normal', 'gauge_fill_normal',
        'gauge_text_normal', 'gauge_text_outline_color', 'gauge_high_contrast_text_color',
        'gauge_background_alert', 'gauge_border_alert', 'gauge_fill_alert',
        'gauge_text_alert', 'analog_gauge_background', 'analog_gauge_border',
        'analog_gauge_scale_color', 'analog_gauge_label_color', 'analog_gauge_needle_color',
        'analog_gauge_center_dot_color', 'analog_gauge_text_color',
        'analog_gauge_needle_alert_color', 'alert_center_dot_color', 'alert_analog_gauge_text_color',
        'window_background', 'window_color', 'label_color', 'groupbox_background',
        'groupbox_border', 'groupbox_title_color', 'tab_pane_background',
        'tab_bar_background', 'tab_selected_background', 'tab_selected_text_color',
        'tab_unselected_background', 'tab_unselected_text_color', 'tab_hover_background',
        'button_background_normal', 'button_text_color_normal', 'button_background_hover',
        'button_text_color_hover', 'button_background_pressed', 'button_text_color_pressed',
        'combobox_background', 'combobox_border', 'combobox_text_color',
        'combobox_arrow_color', 'combobox_item_background_hover', 'combobox_item_text_color_hover',
        'lineedit_background', 'lineedit_border', 'lineedit_text_color',
        'lineedit_placeholder_color', 'progressbar_background', 'progressbar_border',
        'progressbar_chunk_color', 'progressbar_text_color', 'gauge_background_color',
        'gauge_border_color', 'gauge_fill_color', 'gauge_warning_color', 'gauge_critical_color',
        'gauge_text_color' # Added a general gauge_text_color for broader use
    }


    @staticmethod
    def parse_qss_for_colors(qss_content):
        """
        Parses QSS content to extract key-value pairs from specific comment blocks.
        These are intended for custom drawing (e.g., Matplotlib, custom gauges).
        
        Args:
            qss_content (str): The full content of the QSS file.
            
        Returns:
            dict: A dictionary of extracted property names (normalized) and their string values.
        """
        extracted_properties = {}
        
        # Regex to find key: value; pairs
        # Allows for alphanumeric keys with underscores, values can be anything until semicolon.
        # Handles optional whitespace.
        # Example: some_key: #ABCDEF; or another_property: 'Some Font';
        pattern_property = re.compile(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*([^;]+);', re.MULTILINE)

        # Matplotlib section
        # Finds content between /*matplotlib*/ and /*custom_drawing_colors*/
        matplotlib_section_match = re.search(r'/\*matplotlib\*/(.*?)/\*custom_drawing_colors\*/', qss_content, re.DOTALL)
        if matplotlib_section_match:
            matplotlib_content = matplotlib_section_match.group(1)
            for match in pattern_property.finditer(matplotlib_content):
                key = "plot_" + match.group(1).strip() # Prefix with 'plot_' to avoid collision
                value = match.group(2).strip()
                extracted_properties[key] = value
                logger.debug(f"QSSParser: Parsed Matplotlib property: {key} = '{value}'")

        # Custom Drawing Colors section
        # Finds content between /*custom_drawing_colors*/ and the next /* or end of file
        custom_drawing_section_match = re.search(r'/\*custom_drawing_colors\*/(.*?)(?=/\*|$)', qss_content, re.DOTALL)
        if custom_drawing_section_match:
            custom_drawing_content = custom_drawing_section_match.group(1)
            for match in pattern_property.finditer(custom_drawing_content):
                key = match.group(1).strip()
                value = match.group(2).strip()
                extracted_properties[key] = value
                logger.debug(f"QSSParser: Parsed Custom Drawing property: {key} = '{value}'")

        # Additionally, extract groupbox_border_radius values directly from QGroupBox rules
        # This is a bit more specific but necessary for accurate QSS-driven styling details.
        groupbox_border_radius_match = re.search(r'QGroupBox\s*\{\s*(?:[^}]*?)border-radius:\s*(\d+px);', qss_content, re.DOTALL)
        if groupbox_border_radius_match:
            radius_value = groupbox_border_radius_match.group(1).strip()
            extracted_properties['groupbox_border_radius'] = radius_value
            logger.debug(f"QSSParser: Extracted QGroupBox border-radius: '{radius_value}'")

        # Extract specific groupbox border styles
        groupbox_border_match = re.search(r'QGroupBox\s*\{\s*(?:[^}]*?)border-width:\s*([^;]+);\s*border-style:\s*([^;]+);\s*border-color:\s*([^;]+);', qss_content, re.DOTALL)
        if groupbox_border_match:
            width = groupbox_border_match.group(1).strip()
            style = groupbox_border_match.group(2).strip()
            color = groupbox_border_match.group(3).strip()
            extracted_properties['groupbox_border_width'] = width
            extracted_properties['groupbox_border_style'] = style
            extracted_properties['groupbox_border_color'] = color
            logger.debug(f"QSSParser: Extracted QGroupBox border: width='{width}', style='{style}', color='{color}'")


        logger.info(f"QSSParser: Finished parsing. Extracted {len(extracted_properties)} properties.")
        return extracted_properties

    @staticmethod
    def _format_name_for_qss(name):
        """
        Helper to format a string for use in QSS object names or properties.
        Removes spaces and special characters, converts to lowercase.
        E.g., "Type 1 (Standard)" -> "type1standard" or "Default Style" -> "defaultstyle"
        """
        # Remove parentheses and their contents, then replace non-alphanumeric with empty string, convert to lowercase
        formatted = re.sub(r'\s*\(.*\)\s*', '', name) # Remove anything in parentheses
        formatted = re.sub(r'[^a-zA-Z0-9_]', '', formatted) # Remove non-alphanumeric (keep underscores)
        return formatted.lower()

