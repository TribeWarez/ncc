# Contributing

## Setup

```powershell
git clone --recurse-submodules https://github.com/TribeWarez/ncc.git
cd ncc
cd ncc-daemon
cargo build
cd ..\client-py
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

## Gate

```powershell
python scripts/check.py        # fast gate
python scripts/check.py --nym  # also compile the real Nym transport
```

The live mainnet suite is opt-in:

```powershell
$env:NCC_LIVE_NYM = "1"
cd client-py
.\.venv\Scripts\python -m pytest tests/test_nym_live.py -q
```

## Ground rules

- Keep the Core boundary: `core/` is a pinned submodule. Shared protocol/crypto
  changes belong in `TribeWarez/nysiris-core`, followed by a gitlink bump.
- Keep Nysiris and NCC independent. Do not add Nysiris as an NCC dependency.
- Chat is P2P. Do not add a chat service, server message store, or chat SQLite.
- Privacy defaults are product requirements: no presence broadcast, no typing
  or read receipts by default, no telemetry, no message content in logs.
- Add a test with every behavior change. Core tests use the in-memory
  transport; live Nym tests are opt-in.
- Do not commit `dev-master.key`, `*.enc`, history journals, `target/`,
  `.venv/`, or tokens.
- PySide6 only. Do not introduce PyQt6 or a browser engine.

## Pull requests

Small and focused. State what changed, why, and the exact verification output.
CI runs the default gate plus the Nym feature compile.
