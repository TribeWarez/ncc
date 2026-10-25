import pytest

pytest.importorskip("PySide6")

from ncc import style  # noqa: E402
from ncc.windows.dialogs import SettingsDialog  # noqa: E402
from ncc.windows.roster import RosterWindow  # noqa: E402


@pytest.fixture(autouse=True)
def _default_theme(qapp):
    style.apply_theme(qapp, style.DEFAULT_THEME)
    yield
    style.apply_theme(qapp, style.DEFAULT_THEME)


CONTACT = {
    "petname": "Alice",
    "pubkey": "ab" * 32,
    "nym_address": "alice.enc@gw",
    "created_at": 1,
}

GROUP = {
    "id": "cd" * 16,
    "name": "Test Room",
    "member_count": 2,
    "members": [
        {"petname": "You", "pubkey": "cd" * 32, "nym_address": "you.enc@gw"},
        {"petname": "Alice", "pubkey": CONTACT["pubkey"], "nym_address": CONTACT["nym_address"]},
    ],
    "message_count": 1,
    "last_message": {
        "msg_id": "ee" * 16,
        "conversation_id": "group:" + "cd" * 16,
        "from": CONTACT["pubkey"],
        "to": "cd" * 16,
        "body": "hello room",
        "at": 3,
        "direction": "incoming",
        "state": "sent",
    },
}


class FakeRpc:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict | None]] = []
        self.events: list[dict] = []

    def pop_events(self):
        events = self.events
        self.events = []
        return events

    def call(self, method: str, params: dict | None = None, timeout: float = 30.0):
        self.calls.append((method, params))
        if method == "identity.status":
            return {
                "pubkey": "cd" * 32,
                "nym_address": "mock:" + "cd" * 32,
                "transport": "memory",
                "status": "online",
            }
        if method == "contact.list":
            return {"contacts": [CONTACT]}
        if method == "chat.conversations":
            return {
                "conversations": [
                    {
                        "id": "dm:" + CONTACT["pubkey"],
                        "peer_pub": CONTACT["pubkey"],
                        "petname": "Alice",
                        "message_count": 1,
                        "last_message": {
                            "msg_id": "aa" * 16,
                            "conversation_id": "dm:" + CONTACT["pubkey"],
                            "from": CONTACT["pubkey"],
                            "to": "cd" * 32,
                            "body": "last message",
                            "at": 1,
                            "direction": "incoming",
                            "state": "sent",
                        },
                    }
                ]
            }
        if method == "chat.history":
            return {"messages": []}
        if method == "group.list":
            return {"groups": [GROUP]}
        if method == "group.history":
            return {"messages": [GROUP["last_message"]]}
        if method == "group.invite":
            return {"invite": "{}"}
        if method == "presence.set":
            return {"status": "online"}
        raise AssertionError(f"unexpected call {method}")


def test_roster_lists_and_filters_contacts(qtbot):
    rpc = FakeRpc()
    window = RosterWindow(rpc, {"transport": "memory", "data_dir": "C:/tmp"}, demo=False)
    qtbot.addWidget(window)
    window.show()
    assert window.model.rowCount() == 1
    assert window.model.row_at(window.model.index(0, 0)).contact.petname == "Alice"

    window.search.setText("zzz")
    assert window.model.rowCount() == 0
    window.search.clear()
    assert window.model.rowCount() == 1


def test_incoming_event_updates_the_roster(qtbot):
    rpc = FakeRpc()
    window = RosterWindow(rpc, {"transport": "memory", "data_dir": "C:/tmp"}, demo=False)
    qtbot.addWidget(window)
    window.show()
    rpc.events.append(
        {
            "event": "message",
            "data": {
                "message": {
                    "msg_id": "bb" * 16,
                    "conversation_id": "dm:" + CONTACT["pubkey"],
                    "from": CONTACT["pubkey"],
                    "to": "cd" * 32,
                    "body": "live event",
                    "at": 2,
                    "direction": "incoming",
                    "state": "sent",
                }
            },
        }
    )
    window._drain_events()
    assert "Alice" in window.statusBar().currentMessage()


def test_rooms_are_listed_and_open_native_room_window(qtbot):
    rpc = FakeRpc()
    window = RosterWindow(rpc, {"transport": "memory", "data_dir": "C:/tmp"}, demo=False)
    qtbot.addWidget(window)
    window.show()
    assert window.group_model.rowCount() == 1
    group = window.group_model.row_at(window.group_model.index(0, 0))
    assert group.name == "Test Room"
    window.open_room(group)
    qtbot.waitUntil(lambda: group.id in window.rooms)
    room = window.rooms[group.id]
    assert room.windowTitle().startswith("Test Room")
    room.close()


def test_opening_a_chat_creates_a_native_window(qtbot):
    rpc = FakeRpc()
    window = RosterWindow(rpc, {"transport": "memory", "data_dir": "C:/tmp"}, demo=False)
    qtbot.addWidget(window)
    window.show()
    contact = window.model.row_at(window.model.index(0, 0)).contact
    window.open_chat(contact)
    qtbot.waitUntil(lambda: contact.pubkey in window.chats)
    chat = window.chats[contact.pubkey]
    assert chat.windowTitle().startswith("Alice")
    chat.close()


def test_default_theme_is_cyborg_98_with_themed_logo(qapp):
    assert style.DEFAULT_THEME == "cyborg_98"
    assert style.current().key == "cyborg_98"
    for key in style.THEMES:
        pixmap = style.logo_pixmap(key, 88)
        assert not pixmap.isNull(), f"missing logo for {key}"


def test_roster_shows_the_themed_logo(qtbot):
    rpc = FakeRpc()
    window = RosterWindow(rpc, {"transport": "memory", "data_dir": "C:/tmp"}, demo=False)
    qtbot.addWidget(window)
    window.show()
    pixmap = window.logo.pixmap()
    assert pixmap is not None
    assert not pixmap.isNull()
    assert window.logo.toolTip().startswith("Cyborg 98")


def test_theme_setting_applies_and_persists(qtbot, tmp_path):
    rpc = FakeRpc()
    dialog = SettingsDialog(
        rpc,
        {"transport": "memory", "data_dir": str(tmp_path)},
        {},
        data_dir=str(tmp_path),
    )
    qtbot.addWidget(dialog)
    index = dialog.theme_combo.findData("flame_fury_2003")
    assert index >= 0
    dialog.theme_combo.setCurrentIndex(index)

    assert style.current().key == "flame_fury_2003"
    assert style.load_saved_theme(tmp_path) == "flame_fury_2003"
    assert "theme" in (tmp_path / style.SETTINGS_FILE).read_text(encoding="utf-8")


def test_theme_preference_round_trips(tmp_path):
    assert style.load_saved_theme(tmp_path) == style.DEFAULT_THEME
    assert style.save_theme(tmp_path, "aero_2007") is True
    assert style.load_saved_theme(tmp_path) == "aero_2007"
    assert style.save_theme(tmp_path, "not-a-theme") is False
    assert style.load_saved_theme(tmp_path) == "aero_2007"
    assert not (tmp_path / f"{style.SETTINGS_FILE}.tmp").exists()


def test_demo_transport_is_visibly_flagged(qtbot):
    rpc = FakeRpc()
    window = RosterWindow(rpc, {"transport": "memory", "data_dir": "C:/tmp"}, demo=False)
    qtbot.addWidget(window)
    window.show()
    assert window.demo_transport is True
    assert window.demo_banner.isVisible()

    contact = window.model.row_at(window.model.index(0, 0)).contact
    window.open_chat(contact)
    qtbot.waitUntil(lambda: contact.pubkey in window.chats)
    assert "Demo transport" in window.chats[contact.pubkey].statusBar().currentMessage()
    window.chats[contact.pubkey].close()


def test_nym_transport_does_not_show_the_demo_banner(qtbot):
    rpc = FakeRpc()
    window = RosterWindow(rpc, {"transport": "nym", "data_dir": "C:/tmp"}, demo=False)
    qtbot.addWidget(window)
    window.show()
    assert window.demo_transport is False
    assert window.demo_banner.isHidden()
