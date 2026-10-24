"""Contact and settings dialogs."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
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

from ..rpc import RpcClient, RpcError
from ..style import MUTED

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
        note.setStyleSheet(f"color: {MUTED};")
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
    ) -> None:
        super().__init__(parent)
        self.rpc = rpc
        self.setWindowTitle("NCC settings")
        self.setMinimumWidth(620)
        layout = QVBoxLayout(self)

        heading = QLabel("Identity and storage")
        font = heading.font()
        font.setPointSize(14)
        font.setBold(True)
        heading.setFont(font)
        layout.addWidget(heading)

        form = QFormLayout()
        form.addRow("Transport", self._value(str(hello.get("transport", "?"))))
        form.addRow("Data directory", self._value(str(hello.get("data_dir", "?"))))
        form.addRow("Chat public key", self._value(str(identity.get("pubkey", "?"))))
        form.addRow("Nym address", self._value(str(identity.get("nym_address", "?"))))
        layout.addLayout(form)

        privacy = QLabel(
            "No chat service. No server mailbox. Messages are stored only in the "
            "encrypted local history journal; there is no SQLite database and no "
            "multi-device sync."
        )
        privacy.setWordWrap(True)
        privacy.setStyleSheet(f"color: {MUTED};")
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
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setWordWrap(True)
        label.setStyleSheet("font-family: 'Cascadia Mono', Consolas, monospace; font-size: 11px;")
        return label

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
