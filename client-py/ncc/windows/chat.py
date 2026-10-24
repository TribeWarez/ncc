"""Native chat window with a custom message delegate."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QAbstractListModel, QModelIndex, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QKeyEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListView,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from ..models import Contact, Message, short_address, short_hex
from ..rpc import RpcClient, RpcError
from ..style import ACCENT_DARK, BAD, INK, LINE, MUTED, SURFACE_2


class MessageListModel(QAbstractListModel):
    MessageRole = Qt.ItemDataRole.UserRole + 2

    def __init__(self) -> None:
        super().__init__()
        self._messages: list[Message] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return 0 if parent is not None and parent.isValid() else len(self._messages)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._messages)):
            return None
        message = self._messages[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return message.body
        if role == self.MessageRole:
            return message
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{message.time_label} · {message.state}"
        return None

    def set_messages(self, messages: list[Message]) -> None:
        self.beginResetModel()
        self._messages = messages
        self.endResetModel()

    def append(self, message: Message) -> None:
        row = len(self._messages)
        self.beginInsertRows(QModelIndex(), row, row)
        self._messages.append(message)
        self.endInsertRows()

    def messages(self) -> list[Message]:
        return list(self._messages)


class MessageDelegate(QStyledItemDelegate):
    def __init__(
        self,
        parent=None,
        name_for: Callable[[str], str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.name_for = name_for

    def _layout(self, option: QStyleOptionViewItem, message: Message) -> tuple[QRect, QRect]:
        rect = option.rect.adjusted(8, 3, -8, -3)
        max_width = max(220, int(rect.width() * 0.72))
        metrics = QFontMetrics(option.font)
        text_rect = metrics.boundingRect(
            QRect(0, 0, max_width - 26, 20_000),
            int(Qt.TextFlag.TextWordWrap),
            message.body,
        )
        is_group_sender = message.conversation_id.startswith("group:") and not message.outgoing
        sender_height = 14 if is_group_sender else 0
        bubble_width = min(max_width, max(120, text_rect.width() + 26))
        bubble_height = max(38, text_rect.height() + 30 + sender_height)
        if message.outgoing:
            left = rect.right() - bubble_width
        else:
            left = rect.left()
        return QRect(left, rect.top(), bubble_width, bubble_height), QRect(
            left + 13,
            rect.top() + 8 + sender_height,
            bubble_width - 26,
            bubble_height - 24 - sender_height,
        )

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        message: Message | None = index.data(MessageListModel.MessageRole)
        if message is None:
            return QSize(0, 44)
        if option.rect.width() <= 0:
            option.rect.setWidth(640)
        bubble, _ = self._layout(option, message)
        return QSize(0, bubble.height() + 8)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        message: Message | None = index.data(MessageListModel.MessageRole)
        if message is None:
            return
        bubble, text_rect = self._layout(option, message)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        background = QColor(ACCENT_DARK) if message.outgoing else QColor(SURFACE_2)
        border = QColor(ACCENT_DARK if message.outgoing else LINE)
        painter.setBrush(background)
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(bubble, 9, 9)

        if message.conversation_id.startswith("group:") and not message.outgoing:
            label = (
                self.name_for(message.sender)
                if self.name_for is not None
                else short_hex(message.sender, 6, 4)
            )
            sender_font = QFont(option.font)
            sender_font.setPointSize(8)
            sender_font.setBold(True)
            painter.setFont(sender_font)
            painter.setPen(QColor("#ffb37a"))
            painter.drawText(
                QRect(bubble.left() + 13, bubble.top() + 5, bubble.width() - 26, 12),
                int(Qt.AlignmentFlag.AlignLeft) | int(Qt.AlignmentFlag.AlignVCenter),
                label,
            )

        painter.setFont(option.font)
        painter.setPen(QColor("#ffffff" if message.outgoing else INK))
        painter.drawText(
            text_rect,
            int(Qt.TextFlag.TextWordWrap) | int(Qt.AlignmentFlag.AlignLeft)
            | int(Qt.AlignmentFlag.AlignTop),
            message.body,
        )

        small = QFont(option.font)
        small.setPointSize(8)
        painter.setFont(small)
        painter.setPen(QColor("#ffd7bd" if message.outgoing else MUTED))
        timestamp = message.time_label
        if message.state == "failed":
            timestamp = f"{timestamp} · failed"
            painter.setPen(QColor(BAD))
        painter.drawText(
            QRect(bubble.left() + 10, bubble.bottom() - 17, bubble.width() - 20, 14),
            int(Qt.AlignmentFlag.AlignRight) | int(Qt.AlignmentFlag.AlignVCenter),
            timestamp,
        )
        painter.restore()


class Composer(QPlainTextEdit):
    send_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setPlaceholderText("Write a message…  Enter sends, Shift+Enter adds a line")
        self.setFixedHeight(78)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.send_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class ChatWindow(QMainWindow):
    changed = Signal()
    closed = Signal(str)

    def __init__(self, rpc: RpcClient, contact: Contact, *, demo: bool = False) -> None:
        super().__init__()
        self.rpc = rpc
        self.contact = contact
        self.demo = demo
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle(f"{contact.petname} — NCC")
        self.resize(680, 720)
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(self._scroll_to_bottom)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("header")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)
        header_layout.setSpacing(2)
        name = QLabel(contact.petname)
        name_font = name.font()
        name_font.setPointSize(15)
        name_font.setBold(True)
        name.setFont(name_font)
        address = QLabel(f"{short_address(contact.nym_address)} · encrypted local history")
        address.setObjectName("identity")
        header_layout.addWidget(name)
        header_layout.addWidget(address)
        layout.addWidget(header)

        self.empty = QLabel(
            "No messages in this conversation yet.\n"
            "Messages are stored only in the encrypted local journal — no chat service."
        )
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.setStyleSheet(f"color: {MUTED}; padding: 28px;")
        layout.addWidget(self.empty)

        self.model = MessageListModel()
        self.view = QListView()
        self.view.setModel(self.model)
        self.view.setItemDelegate(MessageDelegate(self.view))
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setUniformItemSizes(False)
        self.view.setSpacing(0)
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
        self.statusBar().showMessage("Local-only history · no server mailbox")
        self.refresh()

    def _scroll_to_bottom(self) -> None:
        try:
            self.view.scrollToBottom()
        except RuntimeError:
            # The window can be closing while the zero-delay timer fires.
            pass

    def refresh(self) -> None:
        try:
            result = self.rpc.call(
                "chat.history", {"peer_pub": self.contact.pubkey, "limit": 500}
            )
            messages = [Message.from_dict(item) for item in result.get("messages", [])]
            self.model.set_messages(messages)
            self.empty.setVisible(not messages)
            self.view.setVisible(bool(messages))
            self._scroll_timer.start(0)
        except RpcError as exc:
            self.empty.setText(f"Cannot load history: {exc.message}")
            self.empty.setVisible(True)
            self.view.setVisible(False)

    def send(self) -> None:
        text = self.composer.toPlainText().strip()
        if not text:
            return
        self.send_button.setEnabled(False)
        try:
            result = self.rpc.call(
                "chat.send", {"peer_pub": self.contact.pubkey, "text": text}
            )
            message = Message.from_dict(result["message"])
            self.model.append(message)
            self.empty.setVisible(False)
            self.view.setVisible(True)
            self.composer.clear()
            self.changed.emit()
            self._scroll_timer.start(0)
        except RpcError as exc:
            QMessageBox.warning(self, "Send failed", exc.message)
        finally:
            self.send_button.setEnabled(True)
            self.composer.setFocus()

    def simulate_incoming(self) -> None:
        if not self.demo:
            return
        text, ok = QInputDialog.getText(self, "Simulate incoming", "Message text:")
        if not ok or not text.strip():
            return
        try:
            self.rpc.call("debug.inject", {"text": text.strip()})
            self.refresh()
            self.changed.emit()
        except RpcError as exc:
            QMessageBox.warning(self, "Demo injection failed", exc.message)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.closed.emit(self.contact.pubkey)
        super().closeEvent(event)
