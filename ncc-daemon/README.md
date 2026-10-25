# ncc-daemon

Line-delimited JSON-RPC sidecar for the NCC PySide6 client. It owns the chat
identity, contacts, sealed DM crypto, encrypted history, and transport.

`ncc-daemon` is **not published to crates.io** (`publish = false`): it is the
NCC binary sidecar, not a reusable library. The reusable protocol lives in
[Nysiris-Core](https://github.com/TribeWarez/nysiris-core), published as
`nysiris-core`, `nysiris-chat-core`, `nysiris-chat-history`,
`nysiris-transport-nym`, and `nysiris-testkit`. Every public item there carries
rustdoc (`#![warn(missing_docs)]`, docs built with `-D warnings`).

## Run

Mock transport (default, no network):

```powershell
cargo run -- --transport mock --demo
```

Real Nym transport (feature-gated, compiles the `nym-sdk` stack):

```powershell
cargo build --features nym --release
.\target\release\ncc-daemon.exe --transport nym
```

Optional gateway pin:

```powershell
$env:NCC_NYM_GATEWAY = "<gateway identity key>"
```

The Nym identity is stored under `<data-dir>/nym`; keep it to keep a stable
Nym address. The UI reads the address from `core.hello` / `identity.status`.

## Protocol

One JSON object per stdin line; one JSON response per stdout line. Logs go to
stderr. See `../docs/rpc.md`.

When a Nym message arrives, the daemon emits an unsolicited event on stdout:

```json
{"event":"message","data":{"message":{...}}}
```

The UI drains these through `RpcClient.pop_events()` and refreshes the roster,
open chat window, or open room window. Room messages use
`conversation_id = "group:<gid>"`.

Rooms are capability-key groups: `group.create` returns a signed invite,
`group.join` imports it, and `group.send` fans out one sealed copy per member.
There is no relay and no server room state.

Errors use the codes `bad_request`, `not_found`, `transport`, `crypto`, and
`internal`.

## Environment

| Variable | Meaning |
|---|---|
| `NCC_DATA_DIR` | app data directory |
| `NCC_MASTER_KEY` | 32-byte hex master key; otherwise `dev-master.key` |
| `NCC_TRANSPORT` | `mock` or `nym` |
| `NCC_DEMO` | `1` seeds the demo contact and enables `debug.inject` |
| `NCC_NYM_GATEWAY` | optional gateway identity key |

## Nym dependency pin

The workspace `Cargo.lock` intentionally pins the known-good Nym 1.22.0 set
used by the Nysiris services. The current 1.22.x patch line has internally
inconsistent transitive requirements. Do not run `cargo update` without
building and testing `--features nym` again.

## Test

```powershell
cargo test --locked
cargo clippy --all-targets --locked -- -D warnings
cargo check --features nym --locked
```

Live mainnet test from `client-py`:

```powershell
$env:NCC_LIVE_NYM = "1"
.\.venv\Scripts\python -m pytest tests/test_nym_live.py -q
```
