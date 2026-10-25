"""Locate and start the ncc-daemon sidecar."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from .rpc import RpcClient


def repo_root() -> Path:
    # Packaged builds (PyInstaller) place ncc-daemon.exe next to ncc.exe.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # client-py/ncc/daemon.py -> client-py -> NCC
    return Path(__file__).resolve().parents[2]


def find_daemon(explicit: str | None = None) -> Path:
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return path
        raise FileNotFoundError(f"NCC_DAEMON does not exist: {path}")

    candidates: list[Path] = []
    env_path = os.environ.get("NCC_DAEMON")
    if env_path:
        candidates.append(Path(env_path))
    root = repo_root()
    for name in ("ncc-daemon.exe", "ncc-daemon"):
        candidates.append(root / name)
    # PyInstaller onedir keeps bundled binaries in `_internal` (sys._MEIPASS).
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        for name in ("ncc-daemon.exe", "ncc-daemon"):
            candidates.append(Path(meipass) / name)
    for profile in ("debug", "release"):
        for name in ("ncc-daemon.exe", "ncc-daemon"):
            candidates.append(root / "ncc-daemon" / "target" / profile / name)
    found = shutil.which("ncc-daemon")
    if found:
        candidates.append(Path(found))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "ncc-daemon was not found. Build it with:\n"
        "  cd ncc-daemon && cargo build\n"
        "or set NCC_DAEMON to the binary path."
    )


def start_daemon(
    *,
    explicit: str | None = None,
    data_dir: str | None = None,
    transport: str = "mock",
    demo: bool = True,
) -> RpcClient:
    daemon = find_daemon(explicit)
    command = [str(daemon)]
    if data_dir:
        command.extend(["--data-dir", data_dir])
    command.extend(["--transport", transport])
    if demo:
        command.append("--demo")
    env = os.environ.copy()
    if data_dir:
        env["NCC_DATA_DIR"] = data_dir
    env["NCC_TRANSPORT"] = transport
    if demo:
        env["NCC_DEMO"] = "1"
    return RpcClient(command, env=env)
