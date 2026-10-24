#!/usr/bin/env python3
"""Cross-platform NCC check runner: Rust core, daemon, and PySide6 client."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core"
if not CORE.is_dir():
    CORE = ROOT.parent / "Nysiris-Core"
DAEMON = ROOT / "ncc-daemon"
CLIENT = ROOT / "client-py"


def venv_python() -> Path:
    if os.name == "nt":
        candidate = CLIENT / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = CLIENT / ".venv" / "bin" / "python"
    return candidate if candidate.is_file() else Path(sys.executable)


def run(cwd: Path, *args: str) -> None:
    print(f"\n== {cwd.name}: {' '.join(args)} ==", flush=True)
    completed = subprocess.run(args, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the NCC check gate.")
    parser.add_argument(
        "--nym",
        action="store_true",
        help="also compile the heavy real Nym transport",
    )
    args = parser.parse_args()

    if not CORE.is_dir():
        print(f"Nysiris-Core not found at {CORE}", file=sys.stderr)
        return 2

    run(CORE, "cargo", "fmt", "--check")
    run(CORE, "cargo", "clippy", "--workspace", "--all-targets", "--", "-D", "warnings")
    run(CORE, "cargo", "test", "--workspace")

    run(DAEMON, "cargo", "fmt", "--check")
    run(DAEMON, "cargo", "clippy", "--all-targets", "--", "-D", "warnings")
    run(DAEMON, "cargo", "test")
    if args.nym:
        run(DAEMON, "cargo", "check", "--features", "nym")

    python = venv_python()
    run(CLIENT, str(python), "-m", "ruff", "check", ".")
    run(CLIENT, str(python), "-m", "pytest")
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
