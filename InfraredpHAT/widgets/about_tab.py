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
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.content_widget = QWidget()
        self.content_widget.setObjectName("AboutContentWidget")
        
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(25)

        # Header Section
        app_name_label = QLabel("Anavi Sensor Dashboard")
        app_name_label.setObjectName("AboutAppNameLabel")
        app_name_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(app_name_label)

        version_label = QLabel("Version: 1.0.0 (Beta)")
        version_label.setObjectName("AboutVersionLabel")
        version_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(version_label)
        content_layout.addSpacing(20)

        description_label = QLabel(
            "The Anavi Sensor Dashboard is a PyQt5-based application designed to monitor and "
            "visualize environmental sensor data..."
        )
        description_label.setObjectName("AboutDescriptionLabel")
        description_label.setWordWrap(True)
        content_layout.addWidget(description_label)
        content_layout.addSpacing(20)

        # --- FIX: Assign GroupBoxes and Buttons to 'self' to make them instance attributes ---
        self.system_info_group = QGroupBox("System Information")
        self.system_info_group.setObjectName("SystemInfoGroup")
        system_info_layout = QVBoxLayout(self.system_info_group)
        try:
            matplotlib_version_str = matplotlib.__version__
        except (ImportError, AttributeError):
            matplotlib_version_str = "Not Installed"
        system_info_layout.addWidget(QLabel(f"<b>OS:</b> {platform.system()} {platform.release()}"))
        system_info_layout.addWidget(QLabel(f"<b>Python:</b> {sys.version.split(' ')[0]}"))
        system_info_layout.addWidget(QLabel(f"<b>PyQt5:</b> {__import__('PyQt5.QtCore').QtCore.PYQT_VERSION_STR}"))
        system_info_layout.addWidget(QLabel(f"<b>Matplotlib:</b> {matplotlib_version_str}"))
        content_layout.addWidget(self.system_info_group)
        content_layout.addSpacing(20)

        self.links_group = QGroupBox("Useful Links")
        self.links_group.setObjectName("LinksGroup")
        links_layout = QVBoxLayout(self.links_group)
        
        self.anavi_website_button = QPushButton("Visit Website")
        self.anavi_website_button.setObjectName("AnaviWebsiteButton")
        self.anavi_website_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://anavi.technology/")))
        
        self.github_repo_button = QPushButton("GitHub Repo")
        self.github_repo_button.setObjectName("GithubRepoButton")
        self.github_repo_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/gr4ytips/Anavi")))

        links_layout.addWidget(self.anavi_website_button)
        links_layout.addWidget(self.github_repo_button)
        content_layout.addWidget(self.links_group)
        content_layout.addStretch(1)

        self.scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll_area)

        logger.info("AboutTab: UI setup complete.")

    # NO CHANGES NEEDED HERE
    @pyqtSlot(dict)
    def update_theme_colors(self, new_theme_colors):
        logger.info(f"{self.objectName()}: update_theme_colors called.")
        self.theme_colors = dict(new_theme_colors) if new_theme_colors is not None else {}

        if not self.theme_colors:
            logger.warning(f"{self.objectName()} received empty theme colors.")
            if self.settings_manager:
                self.theme_colors = self.settings_manager.get_theme_colors()
            if not self.theme_colors:
                logger.error("Failed to load any theme colors. Aborting theme update.")
                return

        background_color = self.theme_colors.get('main_window_bg', QColor('#161925')).name()
        text_color = self.theme_colors.get('label_color', QColor('#E4E6EB')).name()
        groupbox_bg = self.theme_colors.get('groupbox_bg', QColor('#232946')).name()
        groupbox_title_color = self.theme_colors.get('groupbox_title_color', QColor('#9FA8DA')).name()
        button_bg = self.theme_colors.get('button_bg_normal', QColor('#3B82F6')).name()
        button_text_color = self.theme_colors.get('button_color_normal', QColor('#FFFFFF')).name()
        button_hover_bg = self.theme_colors.get('button_hover_bg', QColor('#60A5FA')).name()
        groupbox_border_color = self.theme_colors.get('groupbox_border_color', QColor('#3A4470')).name()
        groupbox_border_width = self.theme_colors.get('groupbox_border_width', 1)
        groupbox_border_style = self.theme_colors.get('groupbox_border_style', 'solid')
        groupbox_border_radius = self.theme_colors.get('groupbox_border_radius', 8)
        groupbox_font_size = self.theme_colors.get('groupbox_font_size', '10pt')
        groupbox_font_weight = self.theme_colors.get('groupbox_font_weight', 'bold')
        button_border_radius = self.theme_colors.get('button_border_radius', 4)

        self.setStyleSheet(f"QWidget#AboutTab {{ background-color: {background_color}; color: {text_color}; }}")
        self.content_widget.setStyleSheet(f"QWidget#AboutContentWidget {{ background-color: {background_color}; color: {text_color}; }}")
        self.scroll_area.setStyleSheet(f"QScrollArea#AboutScrollArea {{ background-color: {background_color}; border: none; }}")
        self.scroll_area.viewport().setStyleSheet(f"QWidget {{ background-color: {background_color}; color: {text_color}; }}")

        label_stylesheet = f"QLabel {{ color: {text_color}; }}"
        current_stylesheet = self.styleSheet()
        if label_stylesheet not in current_stylesheet:
            self.setStyleSheet(current_stylesheet + label_stylesheet)

        groupbox_stylesheet = (
            f"QGroupBox {{ "
            f"background-color: {groupbox_bg}; "
            f"border: {groupbox_border_width}px {groupbox_border_style} {groupbox_border_color}; "
            f"border-radius: {groupbox_border_radius}px; "
            f"margin-top: 2ex; "
            f"}} "
            f"QGroupBox::title {{ "
            f"subcontrol-origin: margin; "
            f"subcontrol-position: top center; "
            f"padding: 0 3px; "
            f"background-color: {groupbox_bg}; "
            f"color: {groupbox_title_color}; "
            f"font-size: {groupbox_font_size}; "
            f"font-weight: {groupbox_font_weight}; "
            f"}}"
        )
        self.system_info_group.setStyleSheet(groupbox_stylesheet)
        self.links_group.setStyleSheet(groupbox_stylesheet)

        button_stylesheet = (
            f"QPushButton {{ "
            f"background-color: {button_bg}; "
            f"color: {button_text_color}; "
            f"border: 1px solid {button_bg}; "
            f"border-radius: {button_border_radius}px; "
            f"padding: 5px 10px; "
            f"}} "
            f"QPushButton:hover {{ "
            f"background-color: {button_hover_bg}; "
            f"}}"
        )
        self.anavi_website_button.setStyleSheet(button_stylesheet)
        self.github_repo_button.setStyleSheet(button_stylesheet)

        self.style().polish(self)
        self.style().polish(self.content_widget)
        self.style().polish(self.scroll_area)
        self.style().polish(self.scroll_area.verticalScrollBar())
        self.style().polish(self.scroll_area.horizontalScrollBar())
        self.style().polish(self.system_info_group)
        self.style().polish(self.links_group)
        self.style().polish(self.anavi_website_button)
        self.style().polish(self.github_repo_button)

        logger.info(f"{self.objectName()}: Theme colors updated and widgets polished.")