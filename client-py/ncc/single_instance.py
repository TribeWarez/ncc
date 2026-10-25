"""Single-instance guard for the NCC desktop UI.

A second launch activates the existing roster window instead of starting a
second daemon against the same encrypted store.
"""

from __future__ import annotations

import hashlib
import os

from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QWidget


def instance_name() -> str:
    user = os.environ.get("USERNAME") or os.environ.get("USER") or "user"
    uid = str(os.getuid()) if hasattr(os, "getuid") else ""
    digest = hashlib.sha256(f"{user}:{uid}".encode()).hexdigest()[:12]
    return f"ncc-single-instance-{digest}"


class SingleInstance:
    def __init__(self, name: str | None = None) -> None:
        self.name = name or instance_name()
        self._server: QLocalServer | None = None
        self._window: QWidget | None = None

    def try_acquire(self) -> bool:
        """Return ``False`` when another instance was asked to activate."""
        probe = QLocalSocket()
        probe.connectToServer(self.name)
        if probe.waitForConnected(250):
            probe.write(b"activate\n")
            probe.flush()
            probe.waitForBytesWritten(250)
            probe.disconnectFromServer()
            return False

        # Remove a stale socket left by a crashed instance, then listen.
        QLocalServer.removeServer(self.name)
        server = QLocalServer()
        if not server.listen(self.name):
            # Local sockets can be unavailable in restricted environments; do
            # not prevent the app from starting in that case.
            self._server = None
            return True
        self._server = server
        return True

    def attach(self, window: QWidget) -> None:
        self._window = window
        if self._server is not None:
            self._server.newConnection.connect(self._activate)
            if self._server.hasPendingConnections():
                self._activate()

    def _activate(self) -> None:
        if self._server is not None:
            while self._server.hasPendingConnections():
                connection = self._server.nextPendingConnection()
                if connection is not None:
                    connection.readAll()
                    connection.disconnectFromServer()
                    connection.deleteLater()
        window = self._window
        if window is not None:
            window.showNormal()
            window.raise_()
            window.activateWindow()

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
        QLocalServer.removeServer(self.name)
