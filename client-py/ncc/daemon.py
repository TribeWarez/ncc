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


def default_data_dir() -> str:
    """Mirror the daemon's default data directory without asking it over RPC."""
    override = os.environ.get("NCC_DATA_DIR")
    if override:
        return override
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return str(Path(appdata) / "NCC")
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return str(Path(xdg) / "ncc")
    home = os.environ.get("HOME")
    if home:
        return str(Path(home) / ".local" / "share" / "ncc")
    return str(Path("ncc-data"))


def start_daemon(
    *,
    explicit: str | None = None,
    data_dir: str | None = None,
    transport: str = "mock",
    demo: bool = True,
) -> RpcClient:
    daemon = find_daemon(explicit)
    effective_data_dir = data_dir or default_data_dir()
    command = [str(daemon)]
    command.extend(["--data-dir", effective_data_dir])
    command.extend(["--transport", transport])
    if demo:
        command.append("--demo")
    env = os.environ.copy()
    env["NCC_DATA_DIR"] = effective_data_dir
    env["NCC_TRANSPORT"] = transport
    if demo:
        env["NCC_DEMO"] = "1"
    client = RpcClient(command, env=env)
    client.data_dir = effective_data_dir
    return client
