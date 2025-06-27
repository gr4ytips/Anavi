# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpacerItem, QSizePolicy
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QImage, QColor # Import QColor for theme updates
import logging
import os
import sys # Import sys for sys._MEIPASS

logger = logging.getLogger(__name__)

class AboutTab(QWidget):
    """
    About tab displaying information about the Anavi Sensor Dashboard application.
    """
    def __init__(self, main_window, theme_colors, parent=None):
        super().__init__(parent)
        self.setObjectName("AboutTab") # Object name for QSS
        self.main_window = main_window # Store main_window reference
        self.theme_colors = theme_colors # Store theme colors

        self.setup_ui()
        logger.info("AboutTab initialized.")

    def setup_ui(self):
        """Sets up the layout and widgets for the about tab."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(50, 50, 50, 50) # Ample padding
        main_layout.setAlignment(Qt.AlignCenter) # Center content in the tab

        # Application Name
        app_name_label = QLabel("Anavi Sensor Dashboard")
        app_name_label.setObjectName("AboutAppNameLabel")
        app_name_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(app_name_label)

        # Version
        version_label = QLabel("Version 1.0.0")
        version_label.setObjectName("AboutVersionLabel")
        version_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(version_label)

        # Spacer
        main_layout.addItem(QSpacerItem(20, 30, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Logo (if available)
        # CORRECTED: Pass full path from resources to get_resource_path
        logo_path = self.get_resource_path("images/logo.png") 
        if os.path.exists(logo_path):
            try:
                # Load as QImage first to allow scaling and format conversion
                logo_image = QImage(logo_path)
                # Scale the image while maintaining aspect ratio, e.g., to a max width of 200px
                scaled_logo = logo_image.scaledToWidth(200, Qt.SmoothTransformation)
                logo_pixmap = QPixmap.fromImage(scaled_logo)

                logo_label = QLabel()
                logo_label.setPixmap(logo_pixmap)
                logo_label.setAlignment(Qt.AlignCenter)
                main_layout.addWidget(logo_label)
                logger.debug(f"AboutTab: Loaded and scaled logo from {logo_path}.")
            except Exception as e:
                logger.error(f"AboutTab: Failed to load or scale logo from {logo_path}: {e}", exc_info=True)
                # Fallback to text if logo fails
                main_layout.addWidget(QLabel("Anavi Logo (Image Failed to Load)"))
        else:
            logger.warning(f"AboutTab: Logo file not found at {logo_path}.")
            main_layout.addWidget(QLabel("Anavi Logo (Image Not Found)"))
        
        # Spacer
        main_layout.addItem(QSpacerItem(20, 30, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Description
        description_label = QLabel(
            "The Anavi Sensor Dashboard is an open-source application designed "
            "to monitor environmental data from various sensors. "
            "It provides real-time value displays, customizable gauges, "
            "and historical data plotting with alert notifications."
        )
        description_label.setObjectName("AboutDescriptionLabel")
        description_label.setAlignment(Qt.AlignCenter)
        description_label.setWordWrap(True) # Enable word wrapping
        main_layout.addWidget(description_label)

        # Spacer
        main_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # Developer Info
        developer_label = QLabel("Developed by: Anavi Technology Community")
        developer_label.setObjectName("AboutDeveloperLabel")
        developer_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(developer_label)

        # GitHub Link (as a QLabel with openExternalLinks)
        github_link = QLabel(
            "<a href='https://github.com/AnaviTechnology'>GitHub Repository</a>"
        )
        github_link.setObjectName("AboutLink")
        github_link.setAlignment(Qt.AlignCenter)
        github_link.setOpenExternalLinks(True) # Allow opening links in default browser
        main_layout.addWidget(github_link)
        
        main_layout.addStretch(1) # Push content to center/top


    def get_resource_path(self, relative_path):
        """
        Get the absolute path to a resource, handling both development and PyInstaller one-file builds.
        :param relative_path: The path relative to the 'resources' directory (e.g., 'images/logo.png').
        """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        
        # CHANGED: Join directly with relative_path, assuming it now includes subdirs like 'fonts/' or 'images/'
        resource_path = os.path.join(base_path, 'resources', relative_path)
        logger.debug(f"AboutTab: Resolved resource path for '{relative_path}': {resource_path}")
        return resource_path

    def update_theme_colors(self, new_theme_colors):
        """
        Updates the theme colors for this tab and its contained widgets.
        """
        logger.debug("AboutTab: Updating theme colors and re-polishing.")
        self.theme_colors.clear() # Clear old colors
        self.theme_colors.update(new_theme_colors) # Update with new colors

        # Re-polish the tab itself and its children to apply QSS
        self.style().polish(self)
        for label in self.findChildren(QLabel):
            label.style().polish(label)
        
        logger.debug("AboutTab: Tab re-polished to apply new theme QSS.")
