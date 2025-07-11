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

# --- Constants for easy maintenance ---
APP_VERSION = "1.0.0 (Beta)"
GRAYTIPS_URL = "https://www.graytips.com/"
GITHUB_URL = "https://github.com/gr4ytips/Anavi"

class AboutTab(QWidget):
    ui_customization_changed = pyqtSignal(str, str)
    theme_changed = pyqtSignal(str)

    def __init__(self, settings_manager=None, main_window=None, parent=None):
        super().__init__(parent)
        self.setObjectName("AboutTab")

        self.theme_colors = {}
        self.settings_manager = settings_manager
        self.main_window = main_window

        self.setup_ui()
        logger.info("AboutTab initialized.")

    def setup_ui(self):
        """Sets up the main layout and widgets for the About tab."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        main_layout.setAlignment(Qt.AlignTop)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("AboutScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)

        self.content_widget = QWidget()
        self.content_widget.setObjectName("AboutContentWidget")

        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(25)

        app_name_label = QLabel("Anavi Sensor Dashboard")
        app_name_label.setObjectName("AboutAppNameLabel")
        app_name_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(app_name_label)

        version_label = QLabel(f"Version: {APP_VERSION}")
        version_label.setObjectName("AboutVersionLabel")
        version_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(version_label)
        self.content_layout.addSpacing(20)

        description_label = QLabel(
            "The Anavi Sensor Dashboard is a PyQt5-based application designed "
            "to monitor and visualize environmental sensor data..."
        )
        description_label.setObjectName("AboutDescriptionLabel")
        description_label.setWordWrap(True)
        self.content_layout.addWidget(description_label)
        self.content_layout.addSpacing(20)

        system_info_group = QGroupBox("System Information")
        system_info_layout = QVBoxLayout(system_info_group)
        try:
            matplotlib_version_str = matplotlib.__version__
        except (ImportError, AttributeError):
            matplotlib_version_str = "Not Installed"
        system_info_layout.addWidget(QLabel(f"<b>OS:</b> {platform.system()} {platform.release()}"))
        system_info_layout.addWidget(QLabel(f"<b>Python:</b> {sys.version.split(' ')[0]}"))
        system_info_layout.addWidget(QLabel(f"<b>PyQt5:</b> {__import__('PyQt5.QtCore').QtCore.PYQT_VERSION_STR}"))
        system_info_layout.addWidget(QLabel(f"<b>Matplotlib:</b> {matplotlib_version_str}"))
        self.content_layout.addWidget(system_info_group)
        self.content_layout.addSpacing(20)

        license_label = QLabel("This software is provided under the MIT License.")
        license_label.setObjectName("LicenseLabel")
        license_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(license_label)
        self.content_layout.addSpacing(20)

        links_group = QGroupBox("Useful Links")
        links_layout = QVBoxLayout(links_group)
        anavi_website_button = QPushButton("Visit Website")
        anavi_website_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GRAYTIPS_URL)))
        github_repo_button = QPushButton("GitHub Repo")
        github_repo_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GITHUB_URL)))
        links_layout.addWidget(anavi_website_button)
        links_layout.addWidget(github_repo_button)
        self.content_layout.addWidget(links_group)
        self.content_layout.addStretch(1)

        self.scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll_area)
        logger.info("AboutTab: UI setup complete.")

    def _get_clean_value(self, key, fallback):
        """Safely gets and cleans a value from the theme dictionary."""
        value = self.theme_colors.get(key)
        if value is None or not str(value).strip():
            return fallback
        if isinstance(value, QColor):
            return value.name()
        return str(value).strip()

    @pyqtSlot(dict)
    def update_theme_colors(self, new_theme_colors):
        """Updates theme colors with a single, robust stylesheet."""
        logger.info(f"{self.objectName()}: Applying theme stylesheet.")
        self.theme_colors = dict(new_theme_colors) if new_theme_colors is not None else {}

        if not self.theme_colors and self.settings_manager:
            self.theme_colors = self.settings_manager.get_theme_colors()

        if not self.theme_colors:
            logger.warning("Could not load any theme colors. Styles will not be applied.")
            return

        # Get clean, safe values for all theme variables
        background_color = self._get_clean_value('main_window_bg', '#161925')
        text_color = self._get_clean_value('label_color', '#E4E6EB')
        groupbox_bg = self._get_clean_value('groupbox_bg', '#232946')
        groupbox_title_color = self._get_clean_value('groupbox_title_color', '#9FA8DA')
        button_bg = self._get_clean_value('button_bg_normal', '#3B82F6')
        button_text_color = self._get_clean_value('button_color_normal', '#FFFFFF')
        button_hover_bg = self._get_clean_value('button_hover_bg', '#60A5FA')
        groupbox_border_color = self._get_clean_value('groupbox_border_color', '#3A4470')
        groupbox_border_radius = self._get_clean_value('groupbox_border_radius', '8px')
        button_border_radius = self._get_clean_value('button_border_radius', '5px')

        # Apply a single stylesheet to the parent AboutTab.
        # Your correct f-string placement makes this robust.
        self.setStyleSheet(f"""
            QWidget#AboutTab, QWidget#AboutContentWidget, QScrollArea, QScrollArea > QWidget > QWidget {{
                background-color: {background_color};
                border: none;
            }}
            QLabel {{
                color: {text_color};
                background-color: transparent;
            }}
            QLabel#AboutAppNameLabel {{
                color: {groupbox_title_color};
                font-size: 22pt;
                font-weight: bold;
            }}
            QGroupBox {{
                background-color: {groupbox_bg};
                border: 1px solid {groupbox_border_color};
                border-radius: {groupbox_border_radius};
                margin-top: 1ex;
                font-size: 11pt;
                font-weight: bold;
                color: {groupbox_title_color};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                padding: 0 5px;
            }}
            QPushButton {{
                background-color: {button_bg};
                color: {button_text_color};
                border-radius: {button_border_radius};
                padding: 8px 15px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {button_hover_bg};
            }}
        """)