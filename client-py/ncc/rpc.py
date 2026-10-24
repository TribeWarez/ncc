"""Line-delimited JSON-RPC client for the Rust ncc-daemon sidecar."""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


class RpcError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass
class _Pending:
    event: threading.Event = field(default_factory=threading.Event)
    response: dict[str, Any] | None = None


class RpcClient:
    """Spawns the daemon and multiplexes requests by JSON-RPC id.

    The UI thread may call :meth:`call`; responses are matched on a reader
    thread. Keep calls short in the UI thread for Phase 0; long network calls
    will move to a worker in the Nym transport phase.
    """

    def __init__(
        self,
        command: list[str],
        *,
        env: dict[str, str] | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
        on_stderr: Callable[[str], None] | None = None,
    ) -> None:
        self.command = command
        self.env = env
        self.on_event = on_event
        self.on_stderr = on_stderr
        self._proc: subprocess.Popen[str] | None = None
        self._pending: dict[int, _Pending] = {}
        self._pending_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._next_id = 0
        self._alive = False
        self._stderr_lines: list[str] = []
        self._events: queue.Queue[dict[str, Any]] = queue.Queue()

    @property
    def stderr_lines(self) -> list[str]:
        return list(self._stderr_lines)

    @property
    def alive(self) -> bool:
        return self._alive

    def start(self) -> None:
        if self._proc is not None:
            return
        self._proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=self.env,
        )
        self._alive = True
        threading.Thread(target=self._read_stdout, name="ncc-rpc-out", daemon=True).start()
        threading.Thread(target=self._read_stderr, name="ncc-rpc-err", daemon=True).start()

    def _read_stdout(self) -> None:
        assert self._proc is not None
        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                self._emit_stderr(f"malformed daemon output: {line[:200]}")
                continue
            if not isinstance(payload, dict):
                continue
            if "event" in payload:
                self._events.put(payload)
                if self.on_event:
                    self.on_event(payload)
                continue
            request_id = payload.get("id")
            if not isinstance(request_id, int):
                continue
            with self._pending_lock:
                pending = self._pending.pop(request_id, None)
            if pending is None:
                continue
            pending.response = payload
            pending.event.set()
        self._mark_dead("daemon stdout closed")

    def _read_stderr(self) -> None:
        assert self._proc is not None
        assert self._proc.stderr is not None
        for line in self._proc.stderr:
            self._emit_stderr(line.rstrip())

    def _emit_stderr(self, line: str) -> None:
        self._stderr_lines.append(line)
        if self.on_stderr:
            self.on_stderr(line)
        else:
            print(f"[ncc-daemon] {line}", file=sys.stderr)

    def _mark_dead(self, reason: str) -> None:
        self._alive = False
        with self._pending_lock:
            pending = list(self._pending.values())
            self._pending.clear()
        for waiter in pending:
            waiter.response = {"error": {"code": "daemon_down", "message": reason}}
            waiter.event.set()

    def pop_events(self) -> list[dict[str, Any]]:
        """Drain queued unsolicited events. Safe from the Qt thread."""
        events: list[dict[str, Any]] = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                return events

    def call(self, method: str, params: dict[str, Any] | None = None, timeout: float = 30.0) -> Any:
        if not self._alive or self._proc is None or self._proc.stdin is None:
            raise RpcError("daemon_down", "ncc-daemon is not running")
        with self._pending_lock:
            self._next_id += 1
            request_id = self._next_id
            waiter = _Pending()
            self._pending[request_id] = waiter
        request = json.dumps(
            {"id": request_id, "method": method, "params": params or {}},
            separators=(",", ":"),
        )
        try:
            with self._write_lock:
                self._proc.stdin.write(request + "\n")
                self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise RpcError("daemon_down", f"cannot write to daemon: {exc}") from exc

        if not waiter.event.wait(timeout):
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise RpcError("timeout", f"{method} timed out after {timeout:.1f}s")
        response = waiter.response or {}
        error = response.get("error")
        if isinstance(error, dict):
            raise RpcError(
                str(error.get("code", "rpc_error")),
                str(error.get("message", "unknown daemon error")),
            )
        return response.get("result")

    def close(self) -> None:
        if self._proc is None:
            return
        if self._alive:
            try:
                self.call("shutdown", timeout=1.0)
            except RpcError:
                pass
        try:
            self._proc.terminate()
            self._proc.wait(timeout=2.0)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass
        self._alive = False
        self._proc = None

    def __enter__(self) -> RpcClient:
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
