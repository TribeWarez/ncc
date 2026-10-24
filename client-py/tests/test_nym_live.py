"""Opt-in live mainnet test: two native daemons exchange sealed DMs.

Run with a feature-built daemon:
    $env:NCC_LIVE_NYM = "1"
    .\\.venv\\Scripts\\python -m pytest tests/test_nym_live.py -q
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

from ncc.daemon import find_daemon
from ncc.rpc import RpcClient, RpcError

pytestmark = pytest.mark.skipif(
    os.environ.get("NCC_LIVE_NYM") != "1",
    reason="set NCC_LIVE_NYM=1 to run the live Nym mainnet test",
)


def _wait_for_message(client: RpcClient, timeout: float = 120.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for event in client.pop_events():
            if event.get("event") == "message" and isinstance(event.get("data"), dict):
                message = event["data"].get("message")
                if isinstance(message, dict):
                    return message
        time.sleep(1.0)
    raise AssertionError("timed out waiting for a Nym message")


def test_two_daemons_exchange_room_messages(tmp_path: Path) -> None:
    try:
        daemon = find_daemon()
    except FileNotFoundError:
        pytest.skip("ncc-daemon is not built")

    base = Path(tempfile.mkdtemp(prefix="ncc-nym-room-pytest-", dir=tmp_path))
    env = os.environ.copy()
    env.pop("NCC_DEMO", None)
    a = RpcClient([str(daemon), "--transport", "nym", "--data-dir", str(base / "a")], env=env)
    b = RpcClient([str(daemon), "--transport", "nym", "--data-dir", str(base / "b")], env=env)
    a.start()
    b.start()
    try:
        try:
            a_hello = a.call("core.hello", timeout=240)
            b_hello = b.call("core.hello", timeout=240)
        except RpcError as exc:
            if "compiled without the nym feature" in exc.message:
                pytest.skip("ncc-daemon was built without --features nym")
            raise

        a_pub = a.call("identity.status")["pubkey"]
        b_pub = b.call("identity.status")["pubkey"]
        a_addr = a_hello["nym_address"]
        b_addr = b_hello["nym_address"]

        a.call("contact.add", {"petname": "B", "pubkey": b_pub, "nym_address": b_addr})
        b.call("contact.add", {"petname": "A", "pubkey": a_pub, "nym_address": a_addr})

        created = a.call(
            "group.create",
            {"name": "Live Room", "member_pubkeys": [b_pub]},
        )
        gid = created["group"]["id"]
        b.call("group.join", {"invite": created["invite"]})
        assert b.call("group.list")["groups"][0]["id"] == gid

        a.call("group.send", {"group_id": gid, "text": "live room A to B"})
        received = _wait_for_message(b)
        assert received["body"] == "live room A to B"
        assert received["conversation_id"] == f"group:{gid}"
        assert received["from"] == a_pub

        b.call("group.send", {"group_id": gid, "text": "live room B to A"})
        reply = _wait_for_message(a)
        assert reply["body"] == "live room B to A"
        assert reply["conversation_id"] == f"group:{gid}"
        assert reply["from"] == b_pub

        assert a.call("group.history", {"group_id": gid})["messages"]
        assert b.call("group.history", {"group_id": gid})["messages"]
    finally:
        a.close()
        b.close()
        shutil.rmtree(base, ignore_errors=True)


def test_two_daemons_exchange_dms(tmp_path: Path) -> None:
    try:
        daemon = find_daemon()
    except FileNotFoundError:
        pytest.skip("ncc-daemon is not built")

    base = Path(tempfile.mkdtemp(prefix="ncc-nym-pytest-", dir=tmp_path))
    env = os.environ.copy()
    env.pop("NCC_DEMO", None)
    a = RpcClient([str(daemon), "--transport", "nym", "--data-dir", str(base / "a")], env=env)
    b = RpcClient([str(daemon), "--transport", "nym", "--data-dir", str(base / "b")], env=env)
    a.start()
    b.start()
    try:
        try:
            a_hello = a.call("core.hello", timeout=240)
            b_hello = b.call("core.hello", timeout=240)
        except RpcError as exc:
            if "compiled without the nym feature" in exc.message:
                pytest.skip("ncc-daemon was built without --features nym")
            raise

        a_pub = a.call("identity.status")["pubkey"]
        b_pub = b.call("identity.status")["pubkey"]
        a_addr = a_hello["nym_address"]
        b_addr = b_hello["nym_address"]

        a.call("contact.add", {"petname": "B", "pubkey": b_pub, "nym_address": b_addr})
        b.call("contact.add", {"petname": "A", "pubkey": a_pub, "nym_address": a_addr})

        a.call("chat.send", {"peer_pub": b_pub, "text": "live A to B"})
        received = _wait_for_message(b)
        assert received["body"] == "live A to B"
        assert received["from"] == a_pub

        b.call("chat.send", {"peer_pub": a_pub, "text": "live B to A"})
        reply = _wait_for_message(a)
        assert reply["body"] == "live B to A"
        assert reply["from"] == b_pub
    finally:
        a.close()
        b.close()
        shutil.rmtree(base, ignore_errors=True)
