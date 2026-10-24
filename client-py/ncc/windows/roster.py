"""ICQ/Jabber-style roster window."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import Contact, ContactRow, Conversation, GroupSummary, Message, short_hex
from ..rpc import RpcClient, RpcError
from .chat import ChatWindow
from .contacts import ContactDelegate, ContactListModel
from .dialogs import AddContactDialog, SettingsDialog
from .rooms import (
    CreateRoomDialog,
    GroupDelegate,
    GroupListModel,
    JoinRoomDialog,
    RoomWindow,
)

STATUSES = [
    ("Online", "online"),
    ("Away", "away"),
    ("Do not disturb", "dnd"),
    ("Invisible", "invisible"),
]


class RosterWindow(QMainWindow):
    def __init__(self, rpc: RpcClient, hello: dict, *, demo: bool = False) -> None:
        super().__init__()
        self.rpc = rpc
        self.hello = hello
        self.demo = demo or bool(hello.get("demo"))
        self.contacts: list[Contact] = []
        self.conversations: dict[str, Conversation] = {}
        self.groups: list[GroupSummary] = []
        self.chats: dict[str, ChatWindow] = {}
        self.rooms: dict[str, RoomWindow] = {}
        self.identity: dict = {}
        self.setWindowTitle("NCC — Nysiris Chat Commander")
        self.resize(400, 760)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QFrame()
        header.setObjectName("header")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(10, 8, 10, 8)
        header_layout.setSpacing(1)
        title = QLabel("NCC")
        title.setObjectName("title")
        subtitle = QLabel("Nysiris Chat Commander")
        subtitle.setObjectName("subtitle")
        self.identity_label = QLabel("starting…")
        self.identity_label.setObjectName("identity")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addWidget(self.identity_label)
        layout.addWidget(header)

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        status_row.addWidget(QLabel("Local status"))
        self.status_combo = QComboBox()
        for label, value in STATUSES:
            self.status_combo.addItem(label, value)
        self.status_combo.currentIndexChanged.connect(self._on_status_changed)
        status_row.addWidget(self.status_combo, 1)
        layout.addLayout(status_row)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search contacts")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search)

        section = QLabel("PEOPLE")
        section.setObjectName("section")
        layout.addWidget(section)

        self.model = ContactListModel()
        self.view = QListView()
        self.view.setModel(self.model)
        self.view.setItemDelegate(ContactDelegate(self.view))
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setMouseTracking(True)
        self.view.setSpacing(0)
        self.view.doubleClicked.connect(self._open_index)
        layout.addWidget(self.view, 2)

        rooms_section = QLabel("ROOMS")
        rooms_section.setObjectName("section")
        layout.addWidget(rooms_section)

        self.group_model = GroupListModel()
        self.group_view = QListView()
        self.group_view.setModel(self.group_model)
        self.group_view.setItemDelegate(GroupDelegate(self.group_view))
        self.group_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.group_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.group_view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.group_view.setMouseTracking(True)
        self.group_view.setSpacing(0)
        self.group_view.doubleClicked.connect(self._open_group_index)
        layout.addWidget(self.group_view, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        add_button = QPushButton("+ Contact")
        add_button.setObjectName("primary")
        add_button.clicked.connect(self.add_contact)
        settings_button = QPushButton("Settings")
        settings_button.clicked.connect(self.open_settings)
        bottom.addWidget(add_button)
        bottom.addWidget(settings_button)
        if self.demo:
            demo_button = QPushButton("Demo reply")
            demo_button.clicked.connect(self.simulate_incoming)
            bottom.addWidget(demo_button)
        layout.addLayout(bottom)

        room_actions = QHBoxLayout()
        room_actions.setSpacing(8)
        create_room = QPushButton("+ Room")
        create_room.clicked.connect(self.create_room)
        join_room = QPushButton("Join")
        join_room.clicked.connect(self.join_room)
        room_actions.addWidget(create_room)
        room_actions.addWidget(join_room)
        layout.addLayout(room_actions)

        self.setCentralWidget(root)
        self.statusBar().showMessage("No server mailbox · encrypted local history")
        self._event_timer = QTimer(self)
        self._event_timer.setInterval(250)
        self._event_timer.timeout.connect(self._drain_events)
        self._event_timer.start()
        self.refresh()

    def refresh(self) -> None:
        try:
            identity = self.rpc.call("identity.status")
            contacts = self.rpc.call("contact.list").get("contacts", [])
            conversations = self.rpc.call("chat.conversations").get("conversations", [])
            groups = self.rpc.call("group.list").get("groups", [])
        except RpcError as exc:
            self.statusBar().showMessage(f"daemon error: {exc.message}")
            return

        self.identity = identity
        self.contacts = [Contact.from_dict(item) for item in contacts]
        self.conversations = {
            str(item.get("peer_pub", "")).lower(): Conversation.from_dict(item)
            for item in conversations
        }
        self.groups = [GroupSummary.from_dict(item) for item in groups]
        transport = identity.get("transport", "?")
        pubkey = short_hex(str(identity.get("pubkey", "")), 10, 8)
        nym_address = str(identity.get("nym_address", ""))
        label = f"{pubkey} · {transport} transport"
        if nym_address and not nym_address.startswith("mock:"):
            label += f" · {short_hex(nym_address, 8, 6)}"
        self.identity_label.setText(label)
        desired = self.status_combo.findData(identity.get("status", "online"))
        if desired >= 0:
            self.status_combo.blockSignals(True)
            self.status_combo.setCurrentIndex(desired)
            self.status_combo.blockSignals(False)
        self._apply_filter()
        self.statusBar().showMessage(
            f"{len(self.contacts)} contacts · {len(self.groups)} rooms · no server mailbox"
        )

    def _apply_filter(self, *_args) -> None:
        query = self.search.text() if hasattr(self, "search") else ""
        rows: list[ContactRow] = []
        for contact in self.contacts:
            if not contact.matches(query):
                continue
            conversation = self.conversations.get(contact.pubkey)
            preview = ""
            last_at = 0
            if conversation and conversation.last_message:
                preview = conversation.last_message.body
                last_at = conversation.last_message.at
            rows.append(ContactRow(contact=contact, preview=preview, last_at=last_at))
        rows.sort(key=lambda row: (-row.last_at, row.contact.petname.lower()))
        self.model.set_rows(rows)

        q = query.strip().lower()
        groups = [g for g in self.groups if not q or q in g.name.lower()]
        self.group_model.set_rows(groups)

    def _open_index(self, index: QModelIndex) -> None:
        row = self.model.row_at(index)
        if row is not None:
            self.open_chat(row.contact)

    def _open_group_index(self, index: QModelIndex) -> None:
        group = self.group_model.row_at(index)
        if group is not None:
            self.open_room(group)

    def open_room(self, group: GroupSummary) -> None:
        existing = self.rooms.get(group.id)
        if existing is not None:
            existing.show()
            existing.raise_()
            existing.activateWindow()
            return
        room = RoomWindow(self.rpc, group)
        room.changed.connect(self.refresh)
        room.closed.connect(self._on_room_closed)
        self.rooms[group.id] = room
        room.show()
        room.raise_()
        room.activateWindow()

    def _on_room_closed(self, group_id: str) -> None:
        self.rooms.pop(group_id, None)

    def create_room(self) -> None:
        dialog = CreateRoomDialog(self.contacts, self)
        if dialog.exec() != CreateRoomDialog.DialogCode.Accepted:
            return
        try:
            result = self.rpc.call("group.create", dialog.payload())
            group_id = str(result.get("group", {}).get("id", "")).lower()
            self.refresh()
            summary = next((g for g in self.groups if g.id == group_id), None)
            if summary is not None:
                self.open_room(summary)
        except RpcError as exc:
            QMessageBox.warning(self, "Cannot create room", exc.message)

    def join_room(self) -> None:
        dialog = JoinRoomDialog(self)
        if dialog.exec() != JoinRoomDialog.DialogCode.Accepted:
            return
        try:
            result = self.rpc.call("group.join", {"invite": dialog.invite_text()})
            self.refresh()
            group_id = str(result.get("group", {}).get("id", "")).lower()
            summary = next((g for g in self.groups if g.id == group_id), None)
            if summary is not None:
                self.open_room(summary)
        except RpcError as exc:
            QMessageBox.warning(self, "Cannot join room", exc.message)

    def open_chat(self, contact: Contact) -> None:
        existing = self.chats.get(contact.pubkey)
        if existing is not None:
            existing.show()
            existing.raise_()
            existing.activateWindow()
            return
        chat = ChatWindow(self.rpc, contact, demo=self.demo)
        chat.changed.connect(self.refresh)
        chat.closed.connect(self._on_chat_closed)
        self.chats[contact.pubkey] = chat
        chat.show()
        chat.raise_()
        chat.activateWindow()

    def _on_chat_closed(self, pubkey: str) -> None:
        self.chats.pop(pubkey, None)

    def add_contact(self) -> None:
        dialog = AddContactDialog(self)
        if dialog.exec() != AddContactDialog.DialogCode.Accepted:
            return
        try:
            result = self.rpc.call("contact.add", dialog.contact())
            contact = Contact.from_dict(result["contact"])
            self.refresh()
            self.open_chat(contact)
        except RpcError as exc:
            QMessageBox.warning(self, "Cannot save contact", exc.message)

    def open_settings(self) -> None:
        SettingsDialog(self.rpc, self.hello, self.identity, self).exec()
        self.refresh()
        for chat in self.chats.values():
            chat.refresh()
        for room in self.rooms.values():
            room.refresh()

    def simulate_incoming(self) -> None:
        if not self.demo:
            return
        text, ok = QInputDialog.getText(self, "Simulate incoming", "Message text:")
        if not ok or not text.strip():
            return
        try:
            result = self.rpc.call("debug.inject", {"text": text.strip()})
            self.refresh()
            for chat in self.chats.values():
                chat.refresh()
            message = result.get("message")
            if message:
                peer = str(message.get("from", "")).lower()
                contact = next((c for c in self.contacts if c.pubkey == peer), None)
                if contact is not None:
                    self.open_chat(contact)
        except RpcError as exc:
            QMessageBox.warning(self, "Demo injection failed", exc.message)

    def _drain_events(self) -> None:
        for event in self.rpc.pop_events():
            kind = event.get("event")
            data = event.get("data") or {}
            if kind == "message" and isinstance(data.get("message"), dict):
                message = Message.from_dict(data["message"])
                if message.conversation_id.startswith("group:"):
                    group_id = message.conversation_id.split(":", 1)[1]
                    self.refresh()
                    room = self.rooms.get(group_id)
                    if room is not None:
                        room.refresh()
                    group = next((g for g in self.groups if g.id == group_id), None)
                    name = group.name if group is not None else short_hex(group_id)
                    self.statusBar().showMessage(f"New room message in {name}")
                    continue
                peer = message.sender if not message.outgoing else message.recipient
                self.refresh()
                chat = self.chats.get(peer)
                if chat is not None:
                    chat.refresh()
                contact = next((c for c in self.contacts if c.pubkey == peer), None)
                if contact is not None:
                    self.statusBar().showMessage(f"New message from {contact.petname}")
                else:
                    self.statusBar().showMessage(f"New message from unknown {short_hex(peer)}")
            elif kind == "error":
                self.statusBar().showMessage(f"Nym: {data.get('message', 'transport error')}")

    def _on_status_changed(self, _index: int) -> None:
        status = self.status_combo.currentData()
        try:
            self.rpc.call("presence.set", {"status": status})
            self.statusBar().showMessage(f"Local status: {status} (not broadcast)")
        except RpcError as exc:
            self.statusBar().showMessage(f"status error: {exc.message}")

    def closeEvent(self, event) -> None:  # noqa: N802
        self._event_timer.stop()
        for chat in list(self.chats.values()):
            chat.close()
        for room in list(self.rooms.values()):
            room.close()
        QApplication.quit()
        super().closeEvent(event)
