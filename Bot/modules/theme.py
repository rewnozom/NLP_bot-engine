"""
theme.py

En modul för att hantera applikationens tema (dark/light) och fontstorlek.
Importera och anropa funktionerna i din main.py för att applicera stilen.
"""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QWidget

def apply_theme(widget_or_app, theme_name="dark"):
    """
    Tillämpa ett tema (dark eller light) på hela applikationen eller ett enskilt widget/fönster.
    
    Args:
        widget_or_app: Antingen QApplication-objektet eller toppwidget (t.ex. QMainWindow).
        theme_name (str): "dark" eller "light". Standard är "dark".
    """
    if theme_name == "dark":
        dark_stylesheet = """
            QMainWindow, QWidget {
                background-color: #1e1e1e;
                color: #d4d4d4;
            }

            QLineEdit, QTextEdit, QPlainTextEdit { 
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #3f3f3f;
                border-radius: 4px;
                padding: 4px;
            }

            QPushButton { 
                background-color: #0e639c;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                min-width: 80px;
            }
            QPushButton:hover { 
                background-color: #1177bb;
            }
            QPushButton:pressed {
                background-color: #094771;
            }

            QSplitter::handle {
                background-color: #3f3f3f;
            }

            QTreeView, QListView { 
                background-color: #252526;
                alternate-background-color: #2d2d2d;
                color: #d4d4d4;
                border: 1px solid #3f3f3f;
            }
            QTreeView::item:selected, QListView::item:selected {
                background-color: #094771;
                color: #ffffff;
            }

            QTabWidget::pane {
                border: 1px solid #3f3f3f;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #d4d4d4;
                padding: 8px 16px;
                border: 1px solid #3f3f3f;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                border-bottom: none;
            }

            QStatusBar {
                background-color: #007acc;
                color: #ffffff;
            }

            QToolBar {
                background-color: #2d2d2d;
                border-bottom: 1px solid #3f3f3f;
                spacing: 6px;
                padding: 4px;
            }
            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: #3f3f3f;
            }

            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 14px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #424242;
                min-height: 30px;
                border-radius: 7px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #686868;
            }
            QScrollBar:horizontal {
                background-color: #1e1e1e;
                height: 14px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background-color: #424242;
                min-width: 30px;
                border-radius: 7px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #686868;
            }

            QMenuBar {
                background-color: #2d2d2d;
                color: #d4d4d4;
            }
            QMenuBar::item:selected {
                background-color: #3f3f3f;
            }
            QMenu {
                background-color: #2d2d2d;
                color: #d4d4d4;
                border: 1px solid #3f3f3f;
            }
            QMenu::item:selected {
                background-color: #094771;
            }

            QComboBox {
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #3f3f3f;
                border-radius: 4px;
                padding: 4px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #d4d4d4;
                width: 0;
                height: 0;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #3f3f3f;
                selection-background-color: #094771;
            }
        """
        _apply_stylesheet(widget_or_app, dark_stylesheet)

    else:
        # Light theme
        light_stylesheet = """
            QWidget { 
                background-color: #FFFFFF; 
                color: #000000; 
            }
            QLineEdit, QTextEdit, QPlainTextEdit { 
                background-color: #FFFFFF; 
                color: #000000; 
                border: 1px solid #DDDDDD; 
            }
            QPushButton { 
                background-color: #007ACC; 
                color: white; 
                border-radius: 4px; 
                padding: 6px 12px; 
            }
            QPushButton:hover { 
                background-color: #0066AA; 
            }
            QSplitter::handle { 
                background-color: #DDDDDD; 
            }
            QTreeView, QListView { 
                background-color: #FFFFFF; 
                alternate-background-color: #F5F5F5;
                color: #000000; 
            }
            QTabWidget::pane { 
                border: 1px solid #DDDDDD; 
            }
            QTabBar::tab { 
                background-color: #F0F0F0; 
                color: #000000; 
                padding: 6px 12px; 
            }
            QTabBar::tab:selected { 
                background-color: #FFFFFF; 
            }
        """
        _apply_stylesheet(widget_or_app, light_stylesheet)


def apply_font_size(widget_or_app, size):
    """
    Sätter global textstorlek (punktstorlek) för hela appen eller ett enskilt widget/fönster.
    
    Args:
        widget_or_app: Antingen QApplication eller QMainWindow (eller annan toppwidget).
        size (int): Teckenstorlek (pt).
    """
    if isinstance(widget_or_app, QApplication):
        # Om det är hela appen
        font = widget_or_app.font()
        font.setPointSize(size)
        widget_or_app.setFont(font)
    else:
        # Om det är ett enskilt widget/fönster
        font = widget_or_app.font()
        font.setPointSize(size)
        widget_or_app.setFont(font)

def _apply_stylesheet(widget_or_app, stylesheet: str):
    """
    Intern hjälpfunktion för att sätta styleSheet på antingen en QApplication eller QWidget.
    """
    if isinstance(widget_or_app, QApplication):
        widget_or_app.setStyleSheet(stylesheet)
    elif isinstance(widget_or_app, QWidget):
        widget_or_app.setStyleSheet(stylesheet)
    else:
        raise TypeError("apply_theme: widget_or_app måste vara QApplication eller QWidget.")
