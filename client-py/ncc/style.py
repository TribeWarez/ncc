"""NCC visual themes and application styling.

Four built-in themes ship with the client. ``cyborg_98`` is the default.
Each theme provides both a palette for Qt widgets and a logo used as the
window icon and in the roster header.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import QApplication

SETTINGS_FILE = "settings.json"


@dataclass(frozen=True)
class Theme:
    key: str
    label: str
    logo: str
    accent: str
    accent_dark: str
    accent_ink: str
    bg: str
    surface: str
    surface_2: str
    ink: str
    muted: str
    line: str
    pressed: str
    outgoing_ink: str
    outgoing_meta: str
    sender: str
    good: str
    warn: str
    bad: str


THEMES: dict[str, Theme] = {
    "cyborg_98": Theme(
        key="cyborg_98",
        label="Cyborg 98 (default)",
        logo="client_icon_cyborg_98.png",
        accent="#b184ff",
        accent_dark="#43257a",
        accent_ink="#0c0718",
        bg="#0b0913",
        surface="#151126",
        surface_2="#211a3a",
        ink="#f2edff",
        muted="#a99cc9",
        line="#3a2d5f",
        pressed="#090711",
        outgoing_ink="#ffffff",
        outgoing_meta="#e0ccff",
        sender="#d3b3ff",
        good="#4ade80",
        warn="#fbbf24",
        bad="#fb7185",
    ),
    "aero_2007": Theme(
        key="aero_2007",
        label="Aero 2007",
        logo="client_icon_aero_2007.png",
        accent="#1d8fd8",
        accent_dark="#0d4f7c",
        accent_ink="#ffffff",
        bg="#e9f3fb",
        surface="#f8fbfe",
        surface_2="#d8e9f6",
        ink="#12293b",
        muted="#4e6f88",
        line="#a8c8dd",
        pressed="#c5dff0",
        outgoing_ink="#ffffff",
        outgoing_meta="#d7efff",
        sender="#0d5c8c",
        good="#15803d",
        warn="#b45309",
        bad="#b91c1c",
    ),
    "aero_cyborg": Theme(
        key="aero_cyborg",
        label="Aero Cyborg",
        logo="client_icon_aero_cyborg.png",
        accent="#57d7ff",
        accent_dark="#2d1c57",
        accent_ink="#04121a",
        bg="#090612",
        surface="#141026",
        surface_2="#201936",
        ink="#efe8ff",
        muted="#a89bc7",
        line="#3b2b60",
        pressed="#070410",
        outgoing_ink="#ffffff",
        outgoing_meta="#bcecff",
        sender="#7fe3ff",
        good="#34d399",
        warn="#fbbf24",
        bad="#f87171",
    ),
    "flame_fury_2003": Theme(
        key="flame_fury_2003",
        label="Flame Fury 2003",
        logo="client_icon_flame_fury_2003.png",
        accent="#ff8a1f",
        accent_dark="#7a2c07",
        accent_ink="#1b0b02",
        bg="#140b07",
        surface="#21130c",
        surface_2="#331f13",
        ink="#fff1e3",
        muted="#c9a385",
        line="#4c2f1d",
        pressed="#0f0805",
        outgoing_ink="#ffffff",
        outgoing_meta="#ffd7ac",
        sender="#ffb37a",
        good="#4ade80",
        warn="#fbbf24",
        bad="#ef4444",
    ),
}

DEFAULT_THEME = "cyborg_98"


class _ThemeBus(QObject):
    changed = Signal(str)


theme_bus = _ThemeBus()
theme_changed = theme_bus.changed
_current = THEMES[DEFAULT_THEME]


# Module-level aliases kept for delegates that read the palette while painting.
# ``apply_theme`` republishes these when the active theme changes.
ACCENT = ""
ACCENT_DARK = ""
ACCENT_INK = ""
BG = ""
SURFACE = ""
SURFACE_2 = ""
INK = ""
MUTED = ""
LINE = ""
PRESSED = ""
OUTGOING_INK = ""
OUTGOING_META = ""
SENDER = ""
GOOD = ""
WARN = ""
BAD = ""


def theme_for(key: str | None) -> Theme:
    if key and key in THEMES:
        return THEMES[key]
    return THEMES[DEFAULT_THEME]


def current() -> Theme:
    return _current


def _publish(theme: Theme) -> None:
    global ACCENT, ACCENT_DARK, ACCENT_INK, BG, SURFACE, SURFACE_2
    global INK, MUTED, LINE, PRESSED, OUTGOING_INK, OUTGOING_META, SENDER
    global GOOD, WARN, BAD, _current
    _current = theme
    ACCENT = theme.accent
    ACCENT_DARK = theme.accent_dark
    ACCENT_INK = theme.accent_ink
    BG = theme.bg
    SURFACE = theme.surface
    SURFACE_2 = theme.surface_2
    INK = theme.ink
    MUTED = theme.muted
    LINE = theme.line
    PRESSED = theme.pressed
    OUTGOING_INK = theme.outgoing_ink
    OUTGOING_META = theme.outgoing_meta
    SENDER = theme.sender
    GOOD = theme.good
    WARN = theme.warn
    BAD = theme.bad


def build_qss(theme: Theme) -> str:
    return f"""
QMainWindow, QDialog {{
    background: {theme.bg};
    color: {theme.ink};
}}
QWidget {{
    color: {theme.ink};
    font-family: "Segoe UI", "Noto Sans", sans-serif;
    font-size: 13px;
}}
QLabel#title {{
    font-size: 22px;
    font-weight: 700;
    color: {theme.ink};
}}
QLabel#subtitle {{
    color: {theme.muted};
    font-size: 12px;
}}
QLabel#section {{
    color: {theme.muted};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#identity {{
    color: {theme.muted};
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 11px;
}}
QLabel#warning {{
    color: {theme.warn};
    background: {theme.surface_2};
    border: 1px solid {theme.line};
    border-radius: 3px;
    padding: 6px 8px;
    font-weight: 700;
}}
QLabel#logo {{
    background: transparent;
    border: 1px solid {theme.line};
    border-radius: 6px;
}}
QLineEdit, QPlainTextEdit, QComboBox {{
    background: {theme.surface};
    color: {theme.ink};
    border: 1px solid {theme.line};
    border-radius: 3px;
    padding: 7px 9px;
    selection-background-color: {theme.accent_dark};
    selection-color: {theme.outgoing_ink};
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border-color: {theme.accent};
}}
QComboBox QAbstractItemView {{
    background: {theme.surface};
    color: {theme.ink};
    selection-background-color: {theme.accent_dark};
    selection-color: {theme.outgoing_ink};
}}
QPushButton {{
    background: {theme.surface_2};
    color: {theme.ink};
    border: 1px solid {theme.line};
    border-radius: 3px;
    padding: 7px 12px;
    min-height: 18px;
}}
QPushButton:hover {{
    border-color: {theme.accent};
}}
QPushButton:pressed {{
    background: {theme.pressed};
}}
QPushButton#primary {{
    background: {theme.accent};
    border-color: {theme.accent_dark};
    color: {theme.accent_ink};
    font-weight: 700;
}}
QPushButton#danger {{
    color: {theme.bad};
    border-color: {theme.bad};
}}
QListView, QListWidget {{
    background: {theme.surface};
    border: 1px solid {theme.line};
    border-radius: 3px;
    outline: none;
}}
QListView::item, QListWidget::item {{
    border: none;
}}
QListWidget::item:selected {{
    background: {theme.accent_dark};
    color: {theme.outgoing_ink};
}}
QFrame#header {{
    background: {theme.surface};
    border-bottom: 1px solid {theme.line};
}}
QFrame#composer {{
    background: {theme.surface};
    border-top: 1px solid {theme.line};
}}
QStatusBar {{
    background: {theme.surface};
    color: {theme.muted};
    border-top: 1px solid {theme.line};
}}
QToolTip {{
    background: {theme.surface_2};
    color: {theme.ink};
    border: 1px solid {theme.line};
}}
QDialogButtonBox QPushButton {{
    min-width: 78px;
}}
"""


def _asset_dirs() -> tuple[Path, ...]:
    candidates: list[Path] = []
    override = os.environ.get("NCC_ASSETS")
    if override:
        candidates.append(Path(override))
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        candidates.append(Path(frozen_root) / "res")
    # Source checkout: client-py/ncc/style.py -> <repo>/res
    candidates.append(Path(__file__).resolve().parent.parent.parent / "res")
    # Optional in-package assets directory.
    candidates.append(Path(__file__).resolve().parent / "assets")
    return tuple(dict.fromkeys(candidates))


def asset_path(name: str) -> Path | None:
    for directory in _asset_dirs():
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def logo_pixmap(key: str | None = None, size: int = 88, ratio: float = 1.0) -> QPixmap:
    path = asset_path(theme_for(key).logo)
    if path is None:
        return QPixmap()
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return pixmap
    target = max(1, int(round(size * ratio)))
    scaled = pixmap.scaled(
        target,
        target,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    scaled.setDevicePixelRatio(ratio)
    return scaled


def window_icon(key: str | None = None) -> QIcon:
    path = asset_path(theme_for(key).logo)
    return QIcon(str(path)) if path is not None else QIcon()


def apply_theme(app: QApplication | None = None, key: str | None = None) -> str:
    """Activate ``key`` (or the saved/default theme) for the whole application."""
    theme = theme_for(key)
    _publish(theme)
    application = app if app is not None else QApplication.instance()
    if application is not None:
        application.setStyle("Fusion")
        application.setStyleSheet(build_qss(theme))
        font = QFont()
        font.setPointSize(10)
        application.setFont(font)
        icon = window_icon(theme.key)
        if not icon.isNull():
            application.setWindowIcon(icon)
    theme_changed.emit(theme.key)
    return theme.key


def load_saved_theme(data_dir: str | Path | None) -> str:
    """Read the saved theme name from ``settings.json``; never raises."""
    if not data_dir:
        return DEFAULT_THEME
    path = Path(data_dir) / SETTINGS_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DEFAULT_THEME
    if isinstance(data, dict):
        candidate = data.get("theme")
        if isinstance(candidate, str) and candidate in THEMES:
            return candidate
    return DEFAULT_THEME


def save_theme(data_dir: str | Path | None, key: str) -> bool:
    """Persist a non-secret UI preference; returns ``False`` if it cannot write."""
    if not data_dir or key not in THEMES:
        return False
    path = Path(data_dir) / SETTINGS_FILE
    data: dict = {}
    temp = path.with_name(f"{path.name}.tmp")
    try:
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        data["theme"] = key
        temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, path)
    except (OSError, ValueError):
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    return True


_publish(_current)
