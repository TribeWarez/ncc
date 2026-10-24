# AGENTS.md — Nysiris Chat Commander (NCC)

NCC is a native, privacy-clean desktop chat client for Windows and Linux:
an ICQ/Jabber-style roster, multi-window 1:1 chats, group rooms, and
encrypted local history. It has **no central chat service**. Android is a
later target.

NCC is not Nysiris. Nysiris remains the PWA/Electron/Tauri product for
portals, social/timeline, and service hosting. Do not move NCC chat into
Nysiris, and do not add the Nysiris app as an NCC dependency.

## Final dependency graph

```text
Nysiris PWA (TypeScript)
        │ wire protocol
        ▼
Nysiris services (Rust) ──────► Nysiris-Core
                                       ▲
                                       │
NCC (PySide6 + ncc-daemon) ────────────┘
```

- `Nysiris-Core` depends on neither Nysiris nor NCC.
- NCC pins the Core repository as the `core/` submodule.
- Nysiris and NCC are siblings that depend on different Core crates.
- Nysiris depends on Core's service/social crates; it must **not** depend on
  `nysiris-chat-core`.
- NCC depends on Core's chat/transport/history crates; it must **not** depend
  on the Nysiris app.
- The Nysiris PWA is a TypeScript wire-compatible client. It does not link the
  Rust crates.

## Repository boundaries

### Nysiris-Core (separate GitHub repo; crates.io publication target)

| Crate | Responsibility |
|---|---|
| `nysiris-core` | Shared primitives, traits, identities, protocol helpers; keep Nym-free where possible |
| `nysiris-transport-nym` | Real `nym-sdk` adapter behind the `nym` feature; default builds use an explicit unavailable stub |
| `nysiris-service` | Service framework for social/portal/third-party services |
| `nysiris-social-protocol` | Social wire format/client |
| `nysiris-chat-core` | P2P chat engine: DMs, groups, fan-out, sync, outbox |
| `nysiris-chat-history` | Encrypted flat-file history |
| `nysiris-testkit` | Fake transport, fixtures, conformance helpers |

Phase 0 implements `nysiris-core`, `nysiris-transport-nym` (real behind the
`nym` feature, stub by default), `nysiris-chat-core`, `nysiris-chat-history`,
and `nysiris-testkit`.
`nysiris-service` and `nysiris-social-protocol` are planned extractions for the
Nysiris service side, not part of the NCC Phase 0 build.

Do not put Qt/Python/React code, Nysiris service binaries, or the NCC daemon
in Nysiris-Core.

### Nysiris (existing product)

- `web/` PWA for portal/social/timeline.
- Electron/Tauri desktop packaging.
- `services/social`, portal, and other provider modules.
- Chat is no longer a social-provider feature: `/dm` is kept only for a bounded
  legacy read-only migration window, then removed.
- Nysiris PWA's DM tab is removed when that window closes. There is no chat
  service to point it at; NCC is the chat client.
- Leave Nysiris's existing social/portal SQLite storage alone. The no-SQLite
  rule applies to NCC/chat, not to a Nysiris rewrite.

### NCC (this repo)

```text
NCC/
  ncc-daemon/        Rust JSON-RPC sidecar (publish = false)
  client-py/         PySide6 UI
  packaging/         Windows/Linux packaging
  scripts/           cross-platform build/check wrappers
  docs/
  core/              Nysiris-Core git submodule (required)
```

`ncc-daemon` is NCC-owned. It defines the JSON-RPC contract for the Python UI
and is not published to crates.io.

NCC pins `core/` as a git submodule and `ncc-daemon/Cargo.toml` uses path
dependencies because the Core crates are `publish = false`:

```toml
# ncc-daemon/Cargo.toml
nysiris-core = { path = "../core/crates/nysiris-core" }
nysiris-chat-core = { path = "../core/crates/nysiris-chat-core" }
nysiris-chat-history = { path = "../core/crates/nysiris-chat-history" }
nysiris-transport-nym = { path = "../core/crates/nysiris-transport-nym" }
```

Clone with `git clone --recurse-submodules` or run
`git submodule update --init --recursive`. Switch these to crates.io versions
when the first Core release is published.

## Non-negotiable design decisions

- **No chat service.** No `services/chat`, no server-side mailbox, room log, or
  message database. Nym's gateway queue is the only network-side buffer.
- **Chat is separate from social.** Use `nysiris-chat-v1/*` domains for new chat
  protocols. Do not reuse `fly-social-v1/*` social domains or copy social
  provider routes into chat.
- **Encrypted local history is allowed and expected.** Messages are written to
  an encrypted append-only journal, not SQLite. There is no server history.
- **No SQLite in NCC/chat.** Identity, contacts, groups, and history use
  encrypted flat files plus the OS keychain; non-secret UI settings may use
  plain JSON.
- **One UI process, many native windows.** PySide6/Qt Widgets; no Chromium,
  Electron, Tauri, QWebEngine, IndexedDB, BroadcastChannel, or leader election.
- **One Rust core process** owns network, crypto, history, contacts, sync, and
  outbox. The Python UI talks to it over JSON-RPC on stdio.
- **Separate identities.** The Nym transport identity and the ed25519 chat
  identity are different. Invites carry both the Nym address and the ed25519
  public key. Do not conflate or rotate them casually.
- **No directory or resolver.** Nym addresses are
  `<identity>.<encryption>@<gateway>` and are shared out of band. There is no
  global contact/service directory; invites are the discovery mechanism.
- **DMs are application-layer P2P over Nym.** Contact invite contains the
  peer's Nym address and ed25519 pubkey. Replies use SURBs or the known Nym
  address; verify SDK behavior in the native spike.
- **Groups are client-side fan-out.** A random group key is shared in the
  invite; the sender encrypts once and sends one copy per member. No relay, no
  authoritative member list, no server history.
- **Group limits are explicit.** Late joiners see only future messages unless
  a bounded history bundle is deliberately sent. Removing a member requires a
  new group key. Cap group size (roughly 8–16) because every message costs N
  sends.
- **Presence is private by default.** Self status is local. Contact presence is
  opt-in, probe-based, encrypted, and TTL-limited; no broadcast, no central
  presence service, no group presence.
- **Typing indicators and read receipts are off by default.** If added, they are
  ephemeral and per-conversation opt-in.
- **No multi-device sync.** Each device has its own Nym address and local
  history. Encrypted manual export/import only.
- **No telemetry and no message content in logs.** Crash dumps and diagnostics
  must not contain plaintext messages, contact lists, or keys.

## Storage rules

Expected app-data layout (Windows `%APPDATA%\NCC`, Linux
`$XDG_DATA_HOME/ncc`):

```text
identity/                 Nym SDK identity and state
chat-identity.enc         ed25519 chat identity
contacts.enc              contacts and petnames
groups.enc                group keys and local rosters
outbox.enc                encrypted pending sends
settings.json             non-secret UI settings
history/<opaque-id>.log   encrypted append-only message journal
```

- Phase 0 uses a local `dev-master.key` fallback so the demo can persist.
  Replace it with the OS keychain before shipping; never commit that key.
- Production history key comes from the OS keychain, or an Argon2id-derived
  passphrase. Losing the key loses the history.
- Encrypt records with XChaCha20-Poly1305; bind conversation id, record type,
  and version as AAD.
- Use opaque conversation ids as filenames; map them to contacts only in the
  encrypted contacts file.
- Retention and panic-wipe are local policies. Secure deletion is best-effort
  on SSDs.
- Audit the Nym SDK's own storage. If it embeds SQLite internally, treat that
  as a dependency to review, not as permission to add an app-level SQLite store.

## Nysiris-side work

Read `G:\projects\Nysiris\.agents\AGENTS.md` before editing Nysiris. Its rules
still apply:

- `crates/sphinx-core` is reference/test-vector crypto, never production.
  Production transport uses Nym's audited packages (`nym-sdk`, `mix-fetch`).
- `fly.*` localStorage keys and `fly-social-v1/*` signature domains are frozen;
  renaming them breaks existing identities, history, and signed content.
- Service crates under `services/` are standalone and excluded from the root
  workspace. Use `./build.sh services`, not `workspace.members`.
- Nysiris web still uses `sdk-full-fat` 1.x without a sender-tag/reply API. Do
  not assume NCC's native `nym-sdk` behavior applies to the PWA.
- Nysiris has its own gates: `./build.sh check` and
  `./build.sh services <name>`. Do not run them from the NCC repo.

## Build and verification

Phase 0 scaffold exists: Nysiris-Core crates, `ncc-daemon`, and a PySide6
roster/chat/room UI. The real Nym transport is implemented behind the `nym`
feature and was verified with two live mainnet daemons exchanging DMs and room
messages. Attachments, OS keychain, tray, and packaging are still pending. If a
part is absent, create it to this shape rather than reviving the old
Chromium/submodule/chat-service plan.

One command runs the whole gate:

```bash
python scripts/check.py        # fast default gate
python scripts/check.py --nym  # also compile the heavy real Nym transport
```

Individual gates:

```bash
# Nysiris-Core
cargo fmt --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
cargo semver-checks
# After removing publish = false:
cargo publish --dry-run -p nysiris-core   # repeat per published crate, in dependency order

# NCC daemon
cd ncc-daemon
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test

# Real Nym adapter (heavy first build; feature-gated)
cargo check --features nym

# Python UI
cd client-py
python -m pytest
ruff check .
# run the adopted typechecker (mypy or pyright)
```

- Core tests must use the fake transport and stay offline.
- Live Nym tests are manual/opt-in: two native clients, direct DMs, room
  fan-out, and gateway-queued delivery. Use `NCC_LIVE_NYM=1` with
  `client-py/tests/test_nym_live.py`.
- Nym 1.22.x patch releases are internally inconsistent. Both lockfiles pin
  the known-good 1.22.0 set; do not run `cargo update` without re-testing the
  `nym` feature.
- UI tests use a fake daemon and `QT_QPA_PLATFORM=offscreen`.
- History tests use temp directories and assert no SQLite file and no plaintext
  message content.
- On this Windows host, `bash` resolves to a broken WSL install. Use PowerShell
  or Git Bash (`C:\Program Files\Git\bin\bash.exe`); do not assume `./build.sh`
  runs as-is.

## Crates.io and GitHub

- crates.io is the canonical Rust dependency; GitHub is source/releases.
- Publish in dependency order: `nysiris-core` → transport → history →
  `nysiris-chat-core`/social protocol → `nysiris-service` → testkit.
- `ncc-daemon` and service binaries are not crates.io packages.
- Published versions are immutable; tag Core releases and pin consumers.
- A GitHub submodule is optional for source/integration, not a replacement for
  crates.io dependency resolution.
- CI should include a consumer smoke job that builds Nysiris and NCC against the
  new Core release without making Core depend on either app.

## Python/Qt specifics

- Use **PySide6**, not PyQt6, unless a commercial PyQt license exists. PyQt6 is
  GPLv3/commercial; PySide6 is LGPLv3.
- Target Python 3.12/3.13; PySide6 support often lags the newest Python.
- Use Qt Widgets, `QAbstractListModel`, and `QListView` for dense roster and
  message lists; never create one `QWidget` per message.
- Use `QSystemTrayIcon`, `QSettings`, and `QLocalServer` for tray, window state,
  and single-instance activation.
- Package with PyInstaller or Briefcase, bundling the `ncc-daemon` binary and Qt
  plugins. Do not bundle a browser engine.

## Do not

- Add a chat service, server-side message store, or chat SQLite schema.
- Add Nysiris as an NCC submodule or dependency.
- Make Nysiris depend on `nysiris-chat-core`.
- Make Nysiris-Core depend on Nysiris or NCC.
- Reuse social `/dm` routes/domains for chat.
- Add Chromium/Electron/Tauri/QWebEngine to NCC.
- Store message content in logs, telemetry, crash reports, or QSettings.
- Commit Nym `sp-storage`, identity keys, history journals, SQLite files,
  crates.io tokens, `target/`, `.venv/`, `__pycache__/`, or `dist/`.
- Claim live presence, server-side history, multi-device sync, or zero network
  metadata. Nym hides who-talks-to-whom from network observers, not all
  metadata from gateways.
