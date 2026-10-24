# Nysiris Chat Commander (NCC)

Native, privacy-clean desktop chat for Windows and Linux: an ICQ/Jabber-style
roster, multi-window 1:1 chats, encrypted local history, and no central chat
service.

NCC is a client. Nysiris remains the PWA/Electron/Tauri product for portals,
social/timeline, and service hosting. The shared Rust layer is
[`Nysiris-Core`](https://github.com/TribeWarez/nysiris-core), pinned here as
the `core/` submodule.

```text
Nysiris PWA ──wire──► Nysiris services ──► Nysiris-Core
                                              ▲
NCC (PySide6 + ncc-daemon) ───────────────────┘
```

## What works now (Phase 0)

- Rust `Nysiris-Core` crates:
  - ed25519 chat identity
  - sealed 1:1 DM crypto (ed25519 → X25519, BLAKE2b KDF, XChaCha20-Poly1305)
  - signed inner DM envelope bound to sender, recipient, timestamp, id, body
  - encrypted append-only local history, no SQLite
  - chat engine over a transport trait
  - in-memory transport for tests/demo
  - real `nym-sdk` transport behind the `nym` feature
- `ncc-daemon`: line-delimited JSON-RPC sidecar owning identity, contacts,
  crypto, history, and transport.
- `client-py`: PySide6 roster, native chat windows, rooms, contact dialog,
  settings, encrypted-history note, local-only status selector, demo incoming
  messages.
- **Rooms** with signed capability-key invites, local rosters, client-side
  fan-out, room history, and a native room window. No relay and no server
  room state.
- **Native Nym transport** behind `--features nym`: real mainnet connect,
  sealed DM/room send/receive, SURB replies, and inbound event push to the UI.
  Verified with two native daemons exchanging DMs and room messages in both
  directions.

There is **no chat service**, **no server-side message store**, and **no
SQLite**. Attachments, OS keychain integration, tray notifications, and
packaging are next.

## Quick start (Windows)

Prerequisites: Rust stable, Node not required, Python 3.12 or 3.13.

Clone with the Core submodule:

```powershell
git clone --recurse-submodules https://github.com/TribeWarez/ncc.git
cd ncc
```

```powershell
# 1. Build the Rust core and daemon
cd core
cargo test --workspace

cd ..\ncc-daemon
cargo build

# 2. Install the UI
cd ..\client-py
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"

# 3. Run the demo (in-memory transport, one seeded contact + room)
.\.venv\Scripts\python -m ncc --demo
```

The demo still uses the real encrypted local history journal. The seeding only
adds a local contact and a welcome message; it does not create a server.

## Real Nym transport

Build the daemon with the Nym feature:

```powershell
cd ncc-daemon
cargo build --features nym --release

cd ..\client-py
.\.venv\Scripts\python -m ncc --transport nym
```

The first connect may take a few seconds while the Nym client fetches topology
and connects to a gateway. The Nym identity lives in
`%APPDATA%\NCC\nym`; keep it to keep a stable address. `NCC_NYM_GATEWAY` can pin
an entry gateway.

Nym's 1.22.x patch line is currently internally inconsistent when freshly
resolved; both lockfiles pin the known-good 1.22.0 set. Do not run
`cargo update` without testing `--features nym` again.

## Verify

```powershell
# Rust core
cd core
cargo fmt --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace

# Daemon
cd ..\ncc-daemon
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test

# UI
cd ..\client-py
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m pytest
```

Or run `python scripts/check.py` from the repo root (cross-platform), or
`.\scripts\check.ps1` on Windows. Add `--nym` / `-Nym` to compile the heavy real
Nym transport as part of the gate.

## Why no chat service?

Chat is application-layer P2P over Nym:

- DMs go directly to the peer's Nym address.
- Groups are client-side fan-out to each member.
- The Nym gateway queue is the only network-side buffer.
- History is local, encrypted, and never uploaded.
- No contact directory; invites are out of band.

This makes the privacy boundary explicit: there is no chat database to seize
and no provider that learns the contact graph. Nym still exposes network
metadata to gateways; NCC does not claim otherwise.

## Docs

- `docs/architecture.md` — boundaries, runtime, message path, privacy decisions.
- `docs/nym-transport.md` — feature build, runtime shape, live test, lock pin.
- `docs/rpc.md` — ncc-daemon JSON-RPC methods, groups, events, error codes.
- `AGENTS.md` — repo rules for coding agents.

## Status and limitations

- Native Nym transport works behind `--features nym`, including live mainnet
  delivery, SURB replies, and room fan-out. The default build stays on the mock
  transport.
- Attachments, tray notifications, OS keychain, packaging, and multi-device
  sync are not implemented yet.
- `dev-master.key` is a development fallback for encrypting local identity,
  contacts, and history. Replace it with the OS keychain before shipping.
- No multi-device sync. No server history. No read receipts or typing
  indicators by default.
- PySide6 is LGPLv3; PyQt6 is not used because it is GPLv3/commercial.

## Contributing and security

- `CONTRIBUTING.md` — setup, gate, live tests, and ground rules.
- `SECURITY.md` — private vulnerability reporting and scope reminders.

## License

Apache-2.0. Nysiris-Core is also Apache-2.0.
