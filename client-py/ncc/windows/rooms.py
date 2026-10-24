"""Room list, create/join dialogs, and native room windows."""

from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from ..models import Contact, GroupSummary, Message
from ..rpc import RpcClient, RpcError
from ..style import ACCENT_DARK, LINE, MUTED, SURFACE_2
from .chat import Composer, MessageDelegate, MessageListModel


class GroupListModel(QAbstractListModel):
    GroupRole = Qt.ItemDataRole.UserRole + 4

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[GroupSummary] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return 0 if parent is not None and parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        group = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return group.name
        if role == self.GroupRole:
            return group
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{group.name} · {group.member_count} members\nRoom id: {group.id}"
        return None

    def set_rows(self, rows: list[GroupSummary]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def row_at(self, index: QModelIndex) -> GroupSummary | None:
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        return self._rows[index.row()]


class GroupDelegate(QStyledItemDelegate):
    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        return QSize(0, 58)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        group: GroupSummary | None = index.data(GroupListModel.GroupRole)
        if group is None:
            return
        painter.save()
        rect = option.rect.adjusted(4, 2, -4, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected or hovered:
            painter.setPen(QPen(QColor(LINE), 1))
            painter.setBrush(QColor(SURFACE_2))
            painter.drawRoundedRect(rect, 4, 4)
        if selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(ACCENT_DARK))
            painter.drawRect(QRect(rect.left(), rect.top() + 6, 3, rect.height() - 12))

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ff7300"))
        painter.drawEllipse(rect.left() + 12, rect.top() + 15, 7, 7)

        name_font = QFont(option.font)
        name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(QColor("#f2f3f5"))
        painter.drawText(
            QRect(rect.left() + 28, rect.top() + 7, rect.width() - 80, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            QFontMetrics(name_font).elidedText(
                group.name, Qt.TextElideMode.ElideRight, rect.width() - 80
            ),
        )

        time_font = QFont(option.font)
        time_font.setPointSize(8)
        painter.setFont(time_font)
        painter.setPen(QColor(MUTED))
        painter.drawText(
            QRect(rect.right() - 66, rect.top() + 8, 60, 18),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            group.time_label,
        )

        preview_font = QFont(option.font)
        preview_font.setPointSize(8)
        painter.setFont(preview_font)
        painter.setPen(QColor(MUTED))
        text = f"{group.member_count} members · {group.preview}"
        painter.drawText(
            QRect(rect.left() + 28, rect.top() + 29, rect.width() - 40, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            QFontMetrics(preview_font).elidedText(
                text, Qt.TextElideMode.ElideRight, rect.width() - 40
            ),
        )
        painter.restore()


class CreateRoomDialog(QDialog):
    def __init__(self, contacts: list[Contact], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create room")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        note = QLabel(
            "A room is a capability-key group. Every member receives the room key "
            "in the invite; messages are fanned out directly, never through a server."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {MUTED};")
        layout.addWidget(note)

        self.name = QLineEdit()
        self.name.setPlaceholderText("Room name")
        layout.addWidget(self.name)

        layout.addWidget(QLabel("Invite contacts"))
        self.members = QListWidget()
        self.members.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for contact in contacts:
            item = QListWidgetItem(contact.petname)
            item.setData(Qt.ItemDataRole.UserRole, contact.pubkey)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.members.addItem(item)
        layout.addWidget(self.members, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Missing name", "Give the room a local name.")
            return
        if not self.member_pubkeys():
            QMessageBox.warning(self, "No members", "Select at least one contact.")
            return
        if len(self.member_pubkeys()) > 15:
            QMessageBox.warning(self, "Too many members", "Rooms are limited to 16 people.")
            return
        self.accept()

    def member_pubkeys(self) -> list[str]:
        out = []
        for i in range(self.members.count()):
            item = self.members.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                out.append(str(item.data(Qt.ItemDataRole.UserRole)))
        return out

    def payload(self) -> dict:
        return {"name": self.name.text().strip(), "member_pubkeys": self.member_pubkeys()}


class JoinRoomDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Join room")
        self.setMinimumWidth(620)
        layout = QVBoxLayout(self)
        note = QLabel(
            "Paste the room invite JSON shared by a member. The invite includes "
            "the room key and roster; verify the inviter out of band."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {MUTED};")
        layout.addWidget(note)
        self.invite = QPlainTextEdit()
        self.invite.setPlaceholderText('{"v":1,"group_id":"…","name":"…",…}')
        self.invite.setMinimumHeight(180)
        layout.addWidget(self.invite, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self) -> None:
        if not self.invite.toPlainText().strip():
            QMessageBox.warning(self, "Missing invite", "Paste the room invite JSON.")
            return
        self.accept()

    def invite_text(self) -> str:
        return self.invite.toPlainText().strip()


class RoomWindow(QMainWindow):
    changed = Signal()
    closed = Signal(str)

    def __init__(self, rpc: RpcClient, group: GroupSummary) -> None:
        super().__init__()
        self.rpc = rpc
        self.group = group
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle(f"{group.name} — NCC room")
        self.resize(720, 740)
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(self._scroll_to_bottom)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel(group.name)
        title_font = title.font()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        subtitle = QLabel(f"{group.member_count} members · capability-key room")
        subtitle.setObjectName("identity")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box, 1)
        invite = QPushButton("Copy invite")
        invite.clicked.connect(self.copy_invite)
        header_layout.addWidget(invite)
        layout.addWidget(header)

        self.empty = QLabel(
            "No room messages yet.\n"
            "Messages are sealed with the room key and stored only in encrypted local history."
        )
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.setStyleSheet(f"color: {MUTED}; padding: 28px;")
        layout.addWidget(self.empty)

        self.model = MessageListModel()
        self.view = QListView()
        self.view.setModel(self.model)
        self.view.setItemDelegate(MessageDelegate(self.view, name_for=group.member_name))
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setUniformItemSizes(False)
        layout.addWidget(self.view, 1)

        composer_frame = QFrame()
        composer_frame.setObjectName("composer")
        composer_layout = QHBoxLayout(composer_frame)
        composer_layout.setContentsMargins(12, 10, 12, 10)
        composer_layout.setSpacing(8)
        self.composer = Composer()
        self.composer.send_requested.connect(self.send)
        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("primary")
        self.send_button.clicked.connect(self.send)
        composer_layout.addWidget(self.composer, 1)
        composer_layout.addWidget(self.send_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(composer_frame)

        self.setCentralWidget(root)
        self.statusBar().showMessage(
            "Room key lives in your encrypted store · no relay · local history only"
        )
        self.refresh()

    def _scroll_to_bottom(self) -> None:
        try:
            self.view.scrollToBottom()
        except RuntimeError:
            pass

    def refresh(self) -> None:
        try:
            result = self.rpc.call(
                "group.history", {"group_id": self.group.id, "limit": 500}
            )
            messages = [Message.from_dict(item) for item in result.get("messages", [])]
            self.model.set_messages(messages)
            self.empty.setVisible(not messages)
            self.view.setVisible(bool(messages))
            self._scroll_timer.start(0)
        except RpcError as exc:
            self.empty.setText(f"Cannot load room history: {exc.message}")
            self.empty.setVisible(True)
            self.view.setVisible(False)

    def send(self) -> None:
        text = self.composer.toPlainText().strip()
        if not text:
            return
        self.send_button.setEnabled(False)
        try:
            result = self.rpc.call(
                "group.send", {"group_id": self.group.id, "text": text}
            )
            message = Message.from_dict(result["message"])
            self.model.append(message)
            self.empty.setVisible(False)
            self.view.setVisible(True)
            self.composer.clear()
            delivered = int(result.get("delivered", 0))
            failed = result.get("failed") or []
            if failed:
                self.statusBar().showMessage(
                    f"Delivered to {delivered}; failed: {'; '.join(failed)}"
                )
            else:
                self.statusBar().showMessage(f"Delivered to {delivered} members")
            self.changed.emit()
            self._scroll_timer.start(0)
        except RpcError as exc:
            QMessageBox.warning(self, "Room send failed", exc.message)
        finally:
            self.send_button.setEnabled(True)
            self.composer.setFocus()

    def copy_invite(self) -> None:
        try:
            invite = self.rpc.call("group.invite", {"group_id": self.group.id})["invite"]
            QApplication.clipboard().setText(invite)
            QMessageBox.information(
                self,
                "Room invite copied",
                "Share this invite out of band. Anyone with it can read and post to the room.",
            )
        except RpcError as exc:
            QMessageBox.warning(self, "Cannot create invite", exc.message)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.closed.emit(self.group.id)
        super().closeEvent(event)
