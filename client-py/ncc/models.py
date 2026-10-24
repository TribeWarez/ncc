"""Plain data models shared by the Qt widgets and tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


def short_hex(value: str, head: int = 8, tail: int = 6) -> str:
    value = (value or "").strip()
    if len(value) <= head + tail + 1:
        return value
    return f"{value[:head]}…{value[-tail:]}"


def short_address(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if "@" in value:
        identity, gateway = value.split("@", 1)
        return f"{short_hex(identity, 6, 4)}@{short_hex(gateway, 4, 4)}"
    return short_hex(value)


def format_ms(value: int | float | None) -> str:
    if not value:
        return ""
    try:
        return datetime.fromtimestamp(float(value) / 1000.0).strftime("%H:%M")
    except (OverflowError, OSError, ValueError):
        return ""


@dataclass(frozen=True)
class Contact:
    petname: str
    pubkey: str
    nym_address: str
    created_at: int = 0

    @classmethod
    def from_dict(cls, raw: dict) -> Contact:
        return cls(
            petname=str(raw.get("petname", "")),
            pubkey=str(raw.get("pubkey", "")).lower(),
            nym_address=str(raw.get("nym_address", "")),
            created_at=int(raw.get("created_at", 0) or 0),
        )

    def matches(self, query: str) -> bool:
        q = query.strip().lower()
        if not q:
            return True
        return q in self.petname.lower() or q in self.pubkey.lower() or q in self.nym_address.lower()


@dataclass(frozen=True)
class Message:
    msg_id: str
    conversation_id: str
    sender: str
    recipient: str
    body: str
    at: int
    direction: str
    state: str

    @classmethod
    def from_dict(cls, raw: dict) -> Message:
        return cls(
            msg_id=str(raw.get("msg_id", "")),
            conversation_id=str(raw.get("conversation_id", "")),
            sender=str(raw.get("from", "")).lower(),
            recipient=str(raw.get("to", "")).lower(),
            body=str(raw.get("body", "")),
            at=int(raw.get("at", 0) or 0),
            direction=str(raw.get("direction", "incoming")),
            state=str(raw.get("state", "sent")),
        )

    @property
    def outgoing(self) -> bool:
        return self.direction == "outgoing"

    @property
    def time_label(self) -> str:
        return format_ms(self.at)


@dataclass
class Conversation:
    id: str
    peer_pub: str
    petname: str | None
    last_message: Message | None
    message_count: int = 0

    @classmethod
    def from_dict(cls, raw: dict) -> Conversation:
        last = raw.get("last_message")
        return cls(
            id=str(raw.get("id", "")),
            peer_pub=str(raw.get("peer_pub", "")).lower(),
            petname=raw.get("petname"),
            last_message=Message.from_dict(last) if isinstance(last, dict) else None,
            message_count=int(raw.get("message_count", 0) or 0),
        )


@dataclass
class GroupMember:
    petname: str
    pubkey: str
    nym_address: str

    @classmethod
    def from_dict(cls, raw: dict) -> GroupMember:
        return cls(
            petname=str(raw.get("petname", "")),
            pubkey=str(raw.get("pubkey", "")).lower(),
            nym_address=str(raw.get("nym_address", "")),
        )


@dataclass
class Group:
    id: str
    name: str
    members: list[GroupMember] = field(default_factory=list)
    created_at: int = 0

    @classmethod
    def from_dict(cls, raw: dict) -> Group:
        return cls(
            id=str(raw.get("id", "")).lower(),
            name=str(raw.get("name", "")),
            members=[GroupMember.from_dict(m) for m in raw.get("members", [])],
            created_at=int(raw.get("created_at", 0) or 0),
        )

    def member_name(self, pubkey: str) -> str:
        key = (pubkey or "").lower()
        for member in self.members:
            if member.pubkey == key:
                return member.petname or short_hex(key)
        return short_hex(key)


@dataclass
class GroupSummary:
    id: str
    name: str
    member_count: int
    members: list[GroupMember]
    last_message: Message | None
    message_count: int = 0

    @classmethod
    def from_dict(cls, raw: dict) -> GroupSummary:
        last = raw.get("last_message")
        return cls(
            id=str(raw.get("id", "")).lower(),
            name=str(raw.get("name", "")),
            member_count=int(raw.get("member_count", 0) or 0),
            members=[GroupMember.from_dict(m) for m in raw.get("members", [])],
            last_message=Message.from_dict(last) if isinstance(last, dict) else None,
            message_count=int(raw.get("message_count", 0) or 0),
        )

    @property
    def time_label(self) -> str:
        return self.last_message.time_label if self.last_message else ""

    @property
    def preview(self) -> str:
        return self.last_message.body if self.last_message else f"{self.member_count} members"

    def member_name(self, pubkey: str) -> str:
        key = (pubkey or "").lower()
        for member in self.members:
            if member.pubkey == key:
                return member.petname or short_hex(key)
        return short_hex(key)


@dataclass
class ContactRow:
    contact: Contact
    preview: str = ""
    last_at: int = 0
    extra: dict = field(default_factory=dict)

    @property
    def time_label(self) -> str:
        return format_ms(self.last_at)
