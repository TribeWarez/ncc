"""NCC application entry point."""

from __future__ import annotations

import argparse
import os
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from .daemon import start_daemon
from .rpc import RpcError
from .style import apply_theme
from .windows.roster import RosterWindow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ncc",
        description="Nysiris Chat Commander — native privacy-clean desktop chat",
    )
    parser.add_argument("--daemon", help="path to ncc-daemon (or set NCC_DAEMON)")
    parser.add_argument("--data-dir", help="override NCC data directory")
    parser.add_argument(
        "--transport",
        choices=("mock", "nym"),
        default=os.environ.get("NCC_TRANSPORT", "mock"),
        help="transport adapter (default: mock)",
    )
    parser.add_argument(
        "--demo",
        action=argparse.BooleanOptionalAction,
        default=os.environ.get("NCC_DEMO") == "1",
        help="seed a local demo contact and enable debug.inject",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("NCC")
    app.setOrganizationName("Nysiris")
    apply_theme(app)

    rpc = None
    try:
        rpc = start_daemon(
            explicit=args.daemon,
            data_dir=args.data_dir,
            transport=args.transport,
            demo=args.demo,
        )
        rpc.start()
        hello = rpc.call("core.hello", timeout=200)
        window = RosterWindow(rpc, hello, demo=args.demo)
        window.show()
        app.aboutToQuit.connect(rpc.close)
        return app.exec()
    except FileNotFoundError as exc:
        QMessageBox.critical(None, "ncc-daemon not found", str(exc))
        return 2
    except RpcError as exc:
        QMessageBox.critical(None, "NCC could not start", f"{exc.code}: {exc.message}")
        if rpc is not None:
            rpc.close()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
