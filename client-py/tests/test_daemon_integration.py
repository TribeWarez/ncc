import pytest

from ncc.daemon import find_daemon, start_daemon
from ncc.rpc import RpcError


def test_real_daemon_round_trip(tmp_path):
    try:
        find_daemon()
    except FileNotFoundError:
        pytest.skip("ncc-daemon is not built")

    rpc = start_daemon(data_dir=str(tmp_path), transport="mock", demo=True)
    rpc.start()
    try:
        hello = rpc.call("core.hello")
        assert hello["protocol"] == 1
        assert hello["transport"] == "memory"

        contacts = rpc.call("contact.list")["contacts"]
        assert contacts[0]["petname"] == "Demo Contact"

        groups = rpc.call("group.list")["groups"]
        assert groups[0]["name"] == "Demo Room"
        group_history = rpc.call("group.history", {"group_id": groups[0]["id"]})
        assert group_history["messages"]

        injected = rpc.call("debug.inject", {"text": "integration ping"})
        assert injected["message"]["body"] == "integration ping"

        history = rpc.call(
            "chat.history", {"peer_pub": injected["message"]["from"], "limit": 10}
        )
        assert any(item["body"] == "integration ping" for item in history["messages"])
    finally:
        rpc.close()


def test_real_daemon_reports_bad_method(tmp_path):
    try:
        find_daemon()
    except FileNotFoundError:
        pytest.skip("ncc-daemon is not built")

    rpc = start_daemon(data_dir=str(tmp_path), transport="mock", demo=False)
    rpc.start()
    try:
        with pytest.raises(RpcError) as info:
            rpc.call("does.not.exist")
        assert info.value.code == "bad_request"
    finally:
        rpc.close()
