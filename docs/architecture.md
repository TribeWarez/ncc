# NCC architecture

```text
Nysiris PWA (TypeScript)
        │ wire protocol
        ▼
Nysiris services (Rust) ──────► Nysiris-Core
                                       ▲
                                       │
NCC (PySide6 + ncc-daemon) ────────────┘
```

## Boundaries

- **Nysiris-Core** is the shared Rust layer. It must not depend on Nysiris or
  NCC. It owns chat identity, DM framing/crypto, encrypted history, and the
  transport trait.
- **Nysiris services** depend on Core's service/social crates. The PWA remains
  a TypeScript wire-compatible client.
- **NCC** depends on Core's chat/transport/history crates. It does not depend on
  the Nysiris app.
- **ncc-daemon** is NCC-owned. It owns identity, contacts, crypto, history, and
  network; the Python UI only speaks JSON-RPC. An encrypted outbox is planned,
  not implemented.

## Runtime

```text
PySide6 UI (one QApplication, many QMainWindow windows)
        │ line-delimited JSON-RPC on stdio
        ▼
ncc-daemon (one process)
  ├─ ChatIdentity (ed25519)
  ├─ contacts.enc
  ├─ message history (encrypted flat-file journals)
  ├─ DM seal/open + signed inner envelope
  └─ Transport trait
        ├─ MemoryTransport (demo/tests)
        └─ NymTransport (nym-sdk; real behind the nym feature)
```

There is no chat service and no server mailbox. The Nym gateway queue is the
only network-side buffer.

## Message path

1. UI calls `chat.send` with a peer public key and text.
2. Daemon builds a signed inner envelope, seals it to the peer's ed25519 key,
   and hands the payload to the transport.
3. The daemon appends the outgoing message to the encrypted local journal.
4. On receive, the daemon opens/verifies the sealed envelope, dedupes by
   `msgId`, and appends the incoming message.
5. The UI reloads `chat.history`; it never touches crypto or files.

Room path:

1. A room is a random 128-bit id plus a random 256-bit capability key.
2. `group.create` includes the selected saved contacts and this identity; the
   returned signed invite carries the key and roster out of band.
3. `group.join` verifies the invite signature and requires this identity to be
   in the roster.
4. `group.send` signs the inner envelope, seals it once with the room key, and
   fans out one copy to every member except the sender.
5. Every member writes the message to its own encrypted history. There is no
   relay, no server roster, and no late-join history.

## Privacy decisions

- No chat service, no server-side message database, no SQLite.
- Local history is encrypted with XChaCha20-Poly1305 and bound to the hashed
  conversation filename. Identity/contact/group files are replaced atomically
  with a previous-generation backup.
- Contacts and chat identity are sealed local files.
- Inbound DMs require a saved contact; room messages require a key in the local
  room roster.
- Presence is local by default; no broadcast and no central presence service.
- Groups are client-side fan-out; no relay and no late-join history.
- No telemetry, no message content in logs, no multi-device sync.
- One UI instance per user; a second launch activates the existing roster.
- A torn history tail is quarantined as `*.corrupt` and the valid prefix is kept.

## Phase 0 scope

Implemented: 1:1 DMs, capability-key rooms with client-side fan-out, local
contacts, encrypted history, roster/chat/room windows, local status, mock
transport, JSON-RPC daemon, and a real `nym-sdk` transport behind the `nym`
feature. The Nym path was verified on mainnet with two native daemons exchanging
sealed DMs and room messages.

Pending: attachments, OS keychain, tray/notifications, signed releases, Android
via FFI.
