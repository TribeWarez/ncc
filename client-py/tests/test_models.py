from ncc.models import Contact, Conversation, Message, short_address, short_hex


def test_contact_parsing_and_search():
    contact = Contact.from_dict(
        {"petname": "Alice", "pubkey": "AB" * 32, "nym_address": "id.enc@gw"}
    )
    assert contact.pubkey == "ab" * 32
    assert contact.matches("ali")
    assert contact.matches("id.enc")
    assert not contact.matches("bob")


def test_message_direction_and_time():
    message = Message.from_dict(
        {
            "msg_id": "aa" * 16,
            "conversation_id": "dm:" + "bb" * 32,
            "from": "bb" * 32,
            "to": "cc" * 32,
            "body": "hello",
            "at": 0,
            "direction": "outgoing",
            "state": "sent",
        }
    )
    assert message.outgoing is True
    assert message.body == "hello"
    assert message.time_label == ""


def test_conversation_parsing():
    conversation = Conversation.from_dict(
        {
            "id": "dm:" + "bb" * 32,
            "peer_pub": "BB" * 32,
            "petname": "Bob",
            "message_count": 2,
            "last_message": {
                "msg_id": "aa" * 16,
                "conversation_id": "dm:" + "bb" * 32,
                "from": "bb" * 32,
                "to": "cc" * 32,
                "body": "last",
                "at": 1,
                "direction": "incoming",
                "state": "sent",
            },
        }
    )
    assert conversation.peer_pub == "bb" * 32
    assert conversation.last_message is not None
    assert conversation.last_message.body == "last"


def test_short_helpers():
    assert short_hex("a" * 64).startswith("aaaaaaaa")
    assert "…" in short_hex("a" * 64)
    assert "@" in short_address("a" * 52 + "@" + "b" * 52)
