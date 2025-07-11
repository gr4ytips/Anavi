# widgets/about_tab.py
# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QPushButton, QHBoxLayout, QGroupBox 
from PyQt5.QtCore import Qt, QUrl, pyqtSlot, pyqtSignal
from PyQt5.QtGui import QFont, QDesktopServices, QColor 

import logging
import platform
import sys
import os
import matplotlib

logger = logging.getLogger(__name__)

class AboutTab(QWidget):
    """
    The About tab provides information about the application, its version,
    license, and links to relevant resources.
    """

    ui_customization_changed = pyqtSignal(str, str) 
    theme_changed = pyqtSignal(str) 

    def __init__(self, theme_colors, main_window=None, parent=None): 
        super().__init__(parent)
        self.setObjectName("AboutTab") # Object name for the tab itself

        self.theme_colors = theme_colors # Store initial theme colors
        self.main_window = main_window 

        self.setup_ui()
        # Call update_theme_colors to apply initial theme colors and polish widgets
        self.update_theme_colors(theme_colors) 
        logger.info("AboutTab initialized.")

    def setup_ui(self):
        """Sets up the main layout and widgets for the About tab."""
        # The main_layout is the layout for the AboutTab itself
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        main_layout.setAlignment(Qt.AlignTop)

        # Even if not strictly for scrolling, QScrollArea is used as a container
        # for content_widget. We need to ensure its background is also themed.
        self.scroll_area = QScrollArea() 
        self.scroll_area.setObjectName("AboutScrollArea") 
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded) # Will hide if content fits
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # This content_widget holds all the labels and group boxes
        self.content_widget = QWidget() 
        self.content_widget.setObjectName("AboutContentWidget") 
        
        self.content_layout = QVBoxLayout(self.content_widget) 
        self.content_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter) 
        self.content_layout.setContentsMargins(0, 0, 0, 0) 

        app_name_label = QLabel("Anavi Sensor Dashboard")
        app_name_label.setObjectName("AboutAppNameLabel") 
        app_name_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(app_name_label)

        version_label = QLabel("Version: 1.0.0 (Beta)")
        version_label.setObjectName("AboutVersionLabel") 
        version_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(version_label)

        self.content_layout.addSpacing(20)

        description_label = QLabel(
            "The Anavi Sensor Dashboard is a PyQt5-based application designed "
            "to monitor and visualize environmental sensor data. It supports "
            "various Anavi pHAT sensors (HTU21D, BMP180, BH1750) and provides "
            "real-time readings, historical plots, alert notifications, and "
            "UI customization options."
        )
        description_label.setObjectName("AboutDescriptionLabel")
        description_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        description_label.setWordWrap(True)
        self.content_layout.addWidget(description_label)
        
        self.content_layout.addSpacing(20)

        system_info_group = QGroupBox("System Information") 
        system_info_group.setObjectName("SystemInfoGroup")
        system_info_layout = QVBoxLayout(system_info_group)
        
        try:
            matplotlib_version_str = matplotlib.__version__
        except ImportError:
            matplotlib_version_str = "Not Installed"
            logger.warning("Matplotlib is not installed. Version info not available.")

        system_info_layout.addWidget(QLabel(f"Operating System: {platform.system()} {platform.release()}"))
        system_info_layout.addWidget(QLabel(f"Python Version: {sys.version.split(' ')[0]}"))
        system_info_layout.addWidget(QLabel(f"PyQt5 Version: {__import__('PyQt5.QtCore').QtCore.PYQT_VERSION_STR}"))
        system_info_layout.addWidget(QLabel(f"Matplotlib Version: {matplotlib_version_str}")) 
        system_info_layout.addWidget(QLabel(f"Application Path: {os.path.dirname(os.path.abspath(sys.argv[0]))}"))

        self.content_layout.addWidget(system_info_group)
        self.content_layout.addSpacing(20)

        license_label = QLabel(
            "This software is provided under the MIT License.<br>"            
        )
        license_label.setObjectName("LicenseLabel")
        license_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(license_label)

        self.content_layout.addSpacing(20)

        links_group = QGroupBox("Useful Links")
        links_group.setObjectName("LinksGroup")
        links_layout = QVBoxLayout(links_group)
        
        anavi_website_layout = QHBoxLayout()
        anavi_website_layout.addWidget(QLabel("Graytips:"))
        self.anavi_website_button = QPushButton("Visit Website")
        self.anavi_website_button.setObjectName("AnaviWebsiteButton")

        
        anavi_website_layout.addWidget(self.anavi_website_button)
        anavi_website_layout.addStretch(1)
        links_layout.addLayout(anavi_website_layout)

        # GitHub Link (as a QLabel with openExternalLinks)
        github_link = QLabel(
            "<a href='https://github.com/gr4ytips/Anavi'>GitHub Repository</a>"
        )

        github_repo_layout = QHBoxLayout()
        github_repo_layout.addWidget(QLabel("Source Code:"))
        self.github_repo_button = QPushButton("GitHub Repo")
        self.github_repo_button.setObjectName("GithubRepoButton")
        github_repo_layout.addWidget(self.github_repo_button)
        github_repo_layout.addStretch(1)
        links_layout.addLayout(github_repo_layout)

        self.content_layout.addWidget(links_group)
        self.content_layout.addStretch(1) 

        self.scroll_area.setWidget(self.content_widget) 
        main_layout.addWidget(self.scroll_area)

        logger.info("AboutTab: UI setup complete.")

    @pyqtSlot(dict)
    def update_theme_colors(self, new_theme_colors):
        """
        Updates the internal theme color dictionary when the theme changes.
        The visual update is handled by applying QSS and polishing widgets.
        """
        logger.info(f"{self.objectName()}: update_theme_colors called.")
        
        self.theme_colors = dict(new_theme_colors) if new_theme_colors is not None else {}
        
        if not self.theme_colors:
            logger.warning(f"{self.objectName()} received empty theme colors.")
            return 

        # Get the background color from the theme (e.g., 'window_bg' or 'groupbox_bg')
        # Use 'window_bg' as it's typically the main background for tabs/windows.
        background_color = self.theme_colors.get('window_bg', QColor('#2E2E2E')).name() 

        # Apply stylesheet directly to the AboutTab itself, its content_widget, and the scroll_area's viewport
        # This ensures their backgrounds are explicitly set.
        # The AboutTab is the top-level widget for this tab.
        self.setStyleSheet(f"QWidget#AboutTab {{ background-color: {background_color}; }}")
        self.content_widget.setStyleSheet(f"QWidget#AboutContentWidget {{ background-color: {background_color}; }}")
        self.scroll_area.setStyleSheet(f"QScrollArea#AboutScrollArea {{ background-color: {background_color}; }}")
        self.scroll_area.viewport().setStyleSheet(f"QWidget {{ background-color: {background_color}; }}") # Ensure viewport is also themed
        
        # Polish the widgets to force QSS re-evaluation
        self.style().polish(self) 
        self.style().polish(self.content_widget) 
        self.style().polish(self.scroll_area) 
        self.style().polish(self.scroll_area.verticalScrollBar()) 
        self.style().polish(self.scroll_area.horizontalScrollBar()) 
        
        logger.info(f"{self.objectName()}: Theme colors updated and widgets polished.")