import sys

from ncc.rpc import RpcClient, RpcError

FAKE_DAEMON = r"""
import json
import sys

for line in sys.stdin:
    request = json.loads(line)
    method = request["method"]
    if method == "ping":
        print(json.dumps({"id": request["id"], "result": {"pong": True}}), flush=True)
    elif method == "echo":
        print(json.dumps({"id": request["id"], "result": request.get("params")}), flush=True)
    elif method == "boom":
        print(json.dumps({"id": request["id"], "error": {"code": "bad", "message": "nope"}}), flush=True)
    elif method == "event":
        print(json.dumps({"event": "tick", "data": {"n": 1}}), flush=True)
        print(json.dumps({"id": request["id"], "result": {"ok": True}}), flush=True)
    elif method == "shutdown":
        print(json.dumps({"id": request["id"], "result": {"ok": True}}), flush=True)
        break
"""


def test_rpc_round_trip_and_error():
    events: list[dict] = []
    client = RpcClient(
        [sys.executable, "-u", "-c", FAKE_DAEMON],
        on_event=events.append,
        on_stderr=lambda _line: None,
    )
    client.start()
    try:
        assert client.call("ping") == {"pong": True}
        assert client.call("echo", {"x": 1}) == {"x": 1}
        try:
            client.call("boom")
        except RpcError as exc:
            assert exc.code == "bad"
            assert exc.message == "nope"
        else:
            raise AssertionError("expected RpcError")
        assert client.call("event") == {"ok": True}
        assert events == [{"event": "tick", "data": {"n": 1}}]
        assert client.pop_events() == [{"event": "tick", "data": {"n": 1}}]
        assert client.pop_events() == []
    finally:
        client.close()
    assert not client.alive
