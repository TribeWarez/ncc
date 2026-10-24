"""NCC visual theme: compact, dark, ICQ/Jabber-like, orange accent."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

ACCENT = "#ff7300"
ACCENT_DARK = "#9a3412"
BG = "#0e0f11"
SURFACE = "#181a1d"
SURFACE_2 = "#22252a"
INK = "#f2f3f5"
MUTED = "#9ca3af"
LINE = "#34383f"
GOOD = "#22c55e"
WARN = "#f59e0b"
BAD = "#ef4444"

APP_QSS = f"""
QMainWindow, QDialog {{
    background: {BG};
    color: {INK};
}}
QWidget {{
    color: {INK};
    font-family: "Segoe UI", "Noto Sans", sans-serif;
    font-size: 13px;
}}
QLabel#title {{
    font-size: 22px;
    font-weight: 700;
    color: {INK};
}}
QLabel#subtitle {{
    color: {MUTED};
    font-size: 12px;
}}
QLabel#section {{
    color: {MUTED};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#identity {{
    color: {MUTED};
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 11px;
}}
QLineEdit, QPlainTextEdit, QComboBox {{
    background: {SURFACE};
    color: {INK};
    border: 1px solid {LINE};
    border-radius: 3px;
    padding: 7px 9px;
    selection-background-color: {ACCENT_DARK};
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}
QComboBox QAbstractItemView {{
    background: {SURFACE};
    color: {INK};
    selection-background-color: {ACCENT_DARK};
}}
QPushButton {{
    background: {SURFACE_2};
    color: {INK};
    border: 1px solid {LINE};
    border-radius: 3px;
    padding: 7px 12px;
    min-height: 18px;
}}
QPushButton:hover {{
    border-color: {ACCENT};
}}
QPushButton:pressed {{
    background: #111214;
}}
QPushButton#primary {{
    background: {ACCENT};
    border-color: {ACCENT_DARK};
    color: #0b0b0b;
    font-weight: 700;
}}
QPushButton#danger {{
    color: {BAD};
    border-color: #5b1d1d;
}}
QListView {{
    background: {SURFACE};
    border: 1px solid {LINE};
    border-radius: 3px;
    outline: none;
}}
QListView::item {{
    border: none;
}}
QFrame#header {{
    background: {SURFACE};
    border-bottom: 1px solid {LINE};
}}
QFrame#composer {{
    background: {SURFACE};
    border-top: 1px solid {LINE};
}}
QStatusBar {{
    background: {SURFACE};
    color: {MUTED};
    border-top: 1px solid {LINE};
}}
QToolTip {{
    background: {SURFACE_2};
    color: {INK};
    border: 1px solid {LINE};
}}
QDialogButtonBox QPushButton {{
    min-width: 78px;
}}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(APP_QSS)
    font = QFont()
    font.setPointSize(10)
    app.setFont(font)
