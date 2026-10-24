# Nym transport

NCC talks to peers through `nym-sdk`, not the browser WASM client. The adapter
lives in `Nysiris-Core/crates/nysiris-transport-nym` and is behind the `nym`
feature so the default Core build stays fast.

## Build

```powershell
cd ..\Nysiris-Core
cargo check -p nysiris-transport-nym --features nym

cd ..\Nysiris-Chat-Commander\ncc-daemon
cargo build --features nym --release
```

Without the feature, `NymTransport::connect` fails explicitly:

```text
nysiris-transport-nym was compiled without the nym feature; rebuild with --features nym
```

## Runtime shape

```text
UI thread
  └─ RpcClient (stdin/stdout)
        └─ ncc-daemon
              └─ ChatEngine ── Arc<dyn Transport>
                    └─ NymTransport
                          ├─ Tokio runtime thread
                          ├─ MixnetClient (persistent storage)
                          ├─ send task (MixnetClientSender)
                          └─ receive loop (wait_for_messages)
```

- `send()` enqueues a job and waits for the actual `send_message` result.
- Each outbound DM includes reply SURBs (`IncludedSurbs::new(3)`).
- Received payloads are pushed into a channel; the daemon verifies/decrypts and
  emits `{"event":"message", ...}` to the UI.
- The Nym identity lives under `<data-dir>/nym`.
- `NCC_NYM_GATEWAY` optionally pins the entry gateway.

## Dependency pin

Nym's current 1.22.x patch line is internally inconsistent when freshly
resolved. `Nysiris-Core/Cargo.lock` and `ncc-daemon/Cargo.lock` pin the
known-good 1.22.0 set used by the Nysiris services. Do not regenerate either
lockfile without re-running `cargo check --features nym`.

## Live proof

Two native daemons were connected to mainnet, each added the other as a contact,
and exchanged sealed DMs in both directions. The same pair also created a
capability-key room, joined via the signed invite, and exchanged room messages
in both directions. The scenarios are available as:

```powershell
cd client-py
$env:NCC_LIVE_NYM = "1"
.\.venv\Scripts\python -m pytest tests/test_nym_live.py -q
```

The test is opt-in because it needs mainnet connectivity and a feature-built
daemon.

## Not implemented

- Attachments
- Typing/read receipts
- Multi-device sync
- OS keychain-backed history keys
