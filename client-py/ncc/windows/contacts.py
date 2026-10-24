"""Roster list model and two-line contact delegate."""

from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from ..models import ContactRow, short_address
from ..style import ACCENT, INK, LINE, MUTED, SURFACE_2


class ContactListModel(QAbstractListModel):
    RowRole = Qt.ItemDataRole.UserRole + 1

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[ContactRow] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return 0 if parent is not None and parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        row = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return row.contact.petname
        if role == self.RowRole:
            return row
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{row.contact.pubkey}\n{row.contact.nym_address}"
        return None

    def set_rows(self, rows: list[ContactRow]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def row_at(self, index: QModelIndex) -> ContactRow | None:
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        return self._rows[index.row()]


class ContactDelegate(QStyledItemDelegate):
    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        return QSize(0, 60)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        row: ContactRow | None = index.data(ContactListModel.RowRole)
        if row is None:
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
            painter.setBrush(QColor(ACCENT))
            painter.drawRect(QRect(rect.left(), rect.top() + 6, 3, rect.height() - 12))

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Presence is not available from Nym. The dot is intentionally muted.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(MUTED))
        painter.drawEllipse(rect.left() + 12, rect.top() + 15, 7, 7)

        name_rect = QRect(rect.left() + 28, rect.top() + 7, rect.width() - 80, 20)
        name_font = QFont(option.font)
        name_font.setBold(True)
        name_font.setPointSize(max(9, name_font.pointSize()))
        painter.setFont(name_font)
        painter.setPen(QColor(INK))
        painter.drawText(
            name_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            QFontMetrics(name_font).elidedText(
                row.contact.petname, Qt.TextElideMode.ElideRight, name_rect.width()
            ),
        )

        time_font = QFont(option.font)
        time_font.setPointSize(8)
        painter.setFont(time_font)
        painter.setPen(QColor(MUTED))
        painter.drawText(
            QRect(rect.right() - 66, rect.top() + 8, 60, 18),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            row.time_label,
        )

        preview = row.preview or short_address(row.contact.nym_address)
        preview_font = QFont(option.font)
        preview_font.setPointSize(8)
        painter.setFont(preview_font)
        painter.setPen(QColor(MUTED))
        painter.drawText(
            QRect(rect.left() + 28, rect.top() + 30, rect.width() - 40, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            QFontMetrics(preview_font).elidedText(
                preview, Qt.TextElideMode.ElideRight, rect.width() - 40
            ),
        )
        painter.restore()
