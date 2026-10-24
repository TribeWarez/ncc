# NCC desktop client

PySide6 native frontend for Nysiris Chat Commander. It talks to the
`ncc-daemon` Rust sidecar over line-delimited JSON-RPC; the UI never touches
crypto, network, or history files directly.

## Run the Phase 0 demo

Build the daemon first:

```powershell
cd ..\ncc-daemon
cargo build
```

Then install and run the UI:

```powershell
cd ..\client-py
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m ncc --demo
```

The demo uses the in-memory transport and seeds one local contact and one room.
Messages are still written to the encrypted local history journal; there is no
server and no SQLite.

Rooms are created from contacts (`+ Room`) and joined by pasting a signed invite
JSON (`Join`). A room window can copy its invite for another client.

## Real Nym transport

```powershell
cd ..\ncc-daemon
cargo build --features nym --release

cd ..\client-py
.\.venv\Scripts\python -m ncc --transport nym
```

Nym connection takes a few seconds on first launch. The Nym identity is stored
under `%APPDATA%\NCC\nym`; keep it to keep a stable address. The daemon pushes
incoming messages as `{"event":"message",...}` lines and the UI drains them into
the roster and open chat windows.

## Test

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
```

Live mainnet tests (need a feature-built daemon and network):

```powershell
$env:NCC_LIVE_NYM = "1"
.\.venv\Scripts\python -m pytest tests/test_nym_live.py -q
```

They cover both direct DMs and room fan-out between two native daemons.
