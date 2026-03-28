from __future__ import annotations

from PySide6.QtGui import QColor, QPalette


COLOR_BG = "#F0F0F0"
COLOR_BG_ALT = "#F7F7F7"
COLOR_BG_PANEL = "#FFFFFF"
COLOR_BG_PANEL_DEEP = "#FBFBFB"
COLOR_SURFACE = "#E6E6E6"
COLOR_BORDER = "#C4C4C4"
COLOR_BORDER_STRONG = "#AFAFAF"
COLOR_TEXT = "#202020"
COLOR_TEXT_MUTED = "#6A6A6A"
COLOR_ACCENT = "#217346"
COLOR_ACCENT_ALT = "#185C37"
COLOR_SUCCESS = "#217346"
COLOR_WARNING = "#A16207"
COLOR_ERROR = "#C62828"


APP_STYLESHEET = f"""
QWidget#OuterRoot {{
    background: #EDEDED;
}}

QFrame#AppShell {{
    background: {COLOR_BG};
    border: 1px solid {COLOR_BORDER_STRONG};
    border-radius: 2px;
}}

QMainWindow, QWidget {{
    background: {COLOR_BG};
    color: {COLOR_TEXT};
    font-family: \"Microsoft YaHei UI\", \"Segoe UI\", sans-serif;
    font-size: 12px;
}}

QFrame#TitleBar {{
    background: #F3F3F3;
    border-top-left-radius: 2px;
    border-top-right-radius: 2px;
    border-bottom: 1px solid {COLOR_BORDER};
}}

QToolButton#TitleControl, QToolButton#TitleCloseButton {{
    background: transparent;
    border: none;
    border-radius: 2px;
    min-width: 28px;
    min-height: 24px;
    color: {COLOR_TEXT};
}}

QToolButton#TitleControl:hover {{
    background: #E7E7E7;
}}

QToolButton#TitleCloseButton:hover {{
    background: #F3D9D9;
    color: {COLOR_ERROR};
}}

QFrame#ToolBar {{
    background: #F6F6F6;
    border-bottom: 1px solid {COLOR_BORDER};
}}

QFrame#Panel {{
    background: {COLOR_BG_PANEL};
    border: 1px solid {COLOR_BORDER};
    border-radius: 2px;
}}

QFrame#PanelDeep, QTabWidget::pane {{
    background: {COLOR_BG_PANEL_DEEP};
    border: 1px solid {COLOR_BORDER};
    border-radius: 2px;
}}

QListWidget, QTextEdit, QLineEdit, QToolBox, QTabBar::tab, QTableView, QProgressBar {{
    background: {COLOR_BG_PANEL};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 2px;
}}

QPushButton, QToolButton {{
    background: #FFFFFF;
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 2px;
    padding: 6px 10px;
    min-height: 28px;
}}

QPushButton:hover, QToolButton:hover {{
    border-color: {COLOR_BORDER_STRONG};
    background: #F8F8F8;
}}

QPushButton:pressed, QToolButton:pressed, QToolButton:checked, QPushButton:checked {{
    background: #EDEDED;
    border-color: {COLOR_BORDER_STRONG};
}}

QPushButton[variant=\"accent\"], QToolButton[variant=\"accent\"] {{
    border-color: {COLOR_ACCENT_ALT};
    color: #FFFFFF;
    background: {COLOR_ACCENT};
}}

QPushButton[variant=\"accent\"]:hover, QToolButton[variant=\"accent\"]:hover {{
    background: {COLOR_ACCENT_ALT};
    border-color: {COLOR_ACCENT_ALT};
}}

QPushButton:disabled, QToolButton:disabled {{
    color: #8A8A8A;
    background: #F4F4F4;
}}

QLineEdit {{
    padding: 6px 8px;
    selection-background-color: #DDEBDD;
}}

QHeaderView::section {{
    background: {COLOR_SURFACE};
    color: {COLOR_TEXT};
    border: none;
    border-right: 1px solid {COLOR_BORDER};
    border-bottom: 1px solid {COLOR_BORDER};
    padding: 8px 6px;
    font-weight: 600;
}}

QTableView {{
    background: #FFFFFF;
    alternate-background-color: #FAFAFA;
    gridline-color: #E2E2E2;
    selection-background-color: rgba(33, 115, 70, 0.12);
    selection-color: {COLOR_TEXT};
}}

QTableCornerButton::section {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
}}

QScrollBar:vertical, QScrollBar:horizontal {{
    background: #F1F1F1;
    border: none;
    margin: 2px;
}}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: #BFBFBF;
    border-radius: 5px;
    min-height: 28px;
    min-width: 28px;
}}

QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
    background: #A8A8A8;
}}

QSplitter::handle {{
    background: #E2E2E2;
}}

QSplitter::handle:hover {{
    background: #D0D0D0;
}}
QToolBox::tab {{
    background: #F5F5F5;
    color: {COLOR_TEXT};
    padding: 8px 10px;
    border: 1px solid {COLOR_BORDER};
    border-radius: 2px;
    margin: 3px 0;
}}

QToolBox::tab:selected {{
    background: #EBEBEB;
    border-color: {COLOR_BORDER_STRONG};
}}

QTabBar::tab {{
    background: #F6F6F6;
    color: {COLOR_TEXT};
    padding: 8px 14px;
    margin-right: 4px;
}}

QTabBar::tab:selected {{
    background: #FFFFFF;
    border-color: {COLOR_BORDER};
}}

QProgressBar {{
    min-height: 18px;
    text-align: center;
    background: #F2F2F2;
}}

QProgressBar::chunk {{
    background: {COLOR_ACCENT};
}}

QLabel[role=\"muted\"] {{
    color: {COLOR_TEXT_MUTED};
}}

QLabel[role=\"tag\"] {{
    background: #FFFFFF;
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    padding: 4px 10px;
}}
"""


def build_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLOR_BG))
    palette.setColor(QPalette.WindowText, QColor(COLOR_TEXT))
    palette.setColor(QPalette.Base, QColor(COLOR_BG_PANEL))
    palette.setColor(QPalette.AlternateBase, QColor("#FAFAFA"))
    palette.setColor(QPalette.Text, QColor(COLOR_TEXT))
    palette.setColor(QPalette.Button, QColor(COLOR_BG_PANEL))
    palette.setColor(QPalette.ButtonText, QColor(COLOR_TEXT))
    palette.setColor(QPalette.Highlight, QColor(COLOR_ACCENT))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.PlaceholderText, QColor(COLOR_TEXT_MUTED))
    return palette



