"""Contact and settings dialogs."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import style
from ..rpc import RpcClient, RpcError

HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


class AddContactDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add contact")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        note = QLabel(
            "Paste the contact's Nym address and chat public key. "
            "There is no directory; both values must come from them out of band."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {style.MUTED};")
        layout.addWidget(note)

        form = QFormLayout()
        self.petname = QLineEdit()
        self.petname.setPlaceholderText("A name only you see")
        self.pubkey = QLineEdit()
        self.pubkey.setPlaceholderText("64 hex characters")
        self.pubkey.setFont(self._mono())
        self.nym_address = QLineEdit()
        self.nym_address.setPlaceholderText("<identity>.<encryption>@<gateway>")
        self.nym_address.setFont(self._mono())
        form.addRow("Petname", self.petname)
        form.addRow("Chat public key", self.pubkey)
        form.addRow("Nym address", self.nym_address)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _mono() -> QFont:
        font = QFont("Cascadia Mono")
        font.setStyleHint(QFont.StyleHint.Monospace)
        return font

    def _validate(self) -> None:
        if not self.petname.text().strip():
            QMessageBox.warning(self, "Missing petname", "Give the contact a local name.")
            return
        if not HEX64.match(self.pubkey.text().strip()):
            QMessageBox.warning(
                self, "Bad public key", "The chat public key must be 64 hex characters."
            )
            return
        if not self.nym_address.text().strip():
            QMessageBox.warning(self, "Missing address", "A Nym address is required.")
            return
        self.accept()

    def contact(self) -> dict:
        return {
            "petname": self.petname.text().strip(),
            "pubkey": self.pubkey.text().strip().lower(),
            "nym_address": self.nym_address.text().strip(),
        }


class SettingsDialog(QDialog):
    def __init__(
        self,
        rpc: RpcClient,
        hello: dict,
        identity: dict,
        parent: QWidget | None = None,
        *,
        data_dir: str = "",
    ) -> None:
        super().__init__(parent)
        self.rpc = rpc
        self.data_dir = data_dir or str(hello.get("data_dir") or "")
        self.setWindowTitle("NCC settings")
        self.setMinimumWidth(620)
        layout = QVBoxLayout(self)

        appearance = QLabel("Appearance")
        appearance_font = appearance.font()
        appearance_font.setPointSize(14)
        appearance_font.setBold(True)
        appearance.setFont(appearance_font)
        layout.addWidget(appearance)

        theme_form = QFormLayout()
        self.theme_combo = QComboBox()
        for key, theme in style.THEMES.items():
            self.theme_combo.addItem(theme.label, key)
        current_index = self.theme_combo.findData(style.current().key)
        if current_index >= 0:
            self.theme_combo.setCurrentIndex(current_index)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_form.addRow("Theme colors", self.theme_combo)
        layout.addLayout(theme_form)

        self.swatch = QLabel()
        self.swatch.setFixedHeight(10)
        layout.addWidget(self.swatch)
        self._refresh_swatch()

        theme_note = QLabel(
            "Themes apply immediately and also change the window icon and roster logo. "
            "Only the theme name is saved to settings.json; no message content is stored there."
        )
        theme_note.setWordWrap(True)
        theme_note.setStyleSheet(f"color: {style.MUTED};")
        layout.addWidget(theme_note)

        heading = QLabel("Identity and storage")
        font = heading.font()
        font.setPointSize(14)
        font.setBold(True)
        heading.setFont(font)
        layout.addWidget(heading)

        form = QFormLayout()
        form.addRow("Transport", self._value(str(hello.get("transport", "?"))))
        form.addRow("Data directory", self._value(self.data_dir or "?"))
        form.addRow("Chat public key", self._value(str(identity.get("pubkey", "?"))))
        form.addRow("Nym address", self._value(str(identity.get("nym_address", "?"))))
        layout.addLayout(form)

        privacy = QLabel(
            "No chat service. No server mailbox. Messages are stored only in the "
            "encrypted local history journal; there is no SQLite database and no "
            "multi-device sync."
        )
        privacy.setWordWrap(True)
        privacy.setStyleSheet(f"color: {style.MUTED};")
        layout.addWidget(privacy)

        clear = QPushButton("Clear all local history")
        clear.setObjectName("danger")
        clear.clicked.connect(self._clear_history)
        layout.addWidget(clear, 0, Qt.AlignmentFlag.AlignLeft)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    @staticmethod
    def _value(text: str) -> QLabel:
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setWordWrap(True)
        label.setStyleSheet("font-family: 'Cascadia Mono', Consolas, monospace; font-size: 11px;")
        return label

    def _on_theme_changed(self, _index: int) -> None:
        key = str(self.theme_combo.currentData() or style.DEFAULT_THEME)
        style.apply_theme(QApplication.instance(), key)
        style.save_theme(self.data_dir, key)
        self._refresh_swatch()

    def _refresh_swatch(self) -> None:
        theme = style.current()
        self.swatch.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 {theme.accent}, stop:0.5 {theme.accent_dark}, "
            f"stop:1 {theme.surface_2}); "
            f"border: 1px solid {theme.line}; border-radius: 3px;"
        )

    def _clear_history(self) -> None:
        answer = QMessageBox.question(
            self,
            "Clear local history",
            "Delete all encrypted local message journals? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.rpc.call("chat.clear")
            QMessageBox.information(self, "History cleared", "Local message journals were removed.")
        except RpcError as exc:
            QMessageBox.warning(self, "Could not clear history", exc.message)
