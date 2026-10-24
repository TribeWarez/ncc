# ncc-daemon JSON-RPC

`ncc-daemon` reads one JSON object per line on stdin and writes one JSON object
per line on stdout. Logs and warnings go to stderr only.

Request:

```json
{ "id": 1, "method": "core.hello", "params": {} }
```

Success:

```json
{ "id": 1, "result": { ... } }
```

Error:

```json
{ "id": 1, "error": { "code": "bad_request", "message": "..." } }
```

`id` is echoed exactly. The daemon also emits unsolicited events:

```json
{"event":"message","data":{"message":{...}}}
{"event":"error","data":{"message":"..."}}
```

The Qt client drains them through `RpcClient.pop_events()`.

## Methods

| Method | Params | Result |
|---|---|---|
| `core.hello` | `{}` | `{name, version, protocol, transport, nym_address, data_dir, demo}` |
| `identity.status` | `{}` | `{pubkey, nym_address, transport, status}` |
| `contact.list` | `{}` | `{contacts: Contact[]}` |
| `contact.add` | `{petname, pubkey, nym_address}` | `{contact}` |
| `contact.remove` | `{pubkey}` | `{removed: bool}` |
| `chat.conversations` | `{}` | `{conversations: ConversationSummary[]}` |
| `chat.history` | `{peer_pub, limit?}` | `{messages: ChatMessage[]}` |
| `chat.send` | `{peer_pub, text}` | `{message: ChatMessage}` |
| `chat.clear` | `{}` | `{cleared: true}` |
| `group.list` | `{}` | `{groups: GroupSummary[]}` |
| `group.create` | `{name, member_pubkeys}` | `{group, invite}` |
| `group.join` | `{invite}` | `{group}` |
| `group.invite` | `{group_id}` | `{invite}` |
| `group.history` | `{group_id, limit?}` | `{messages: ChatMessage[]}` |
| `group.send` | `{group_id, text}` | `{message, delivered, failed}` |
| `group.leave` | `{group_id}` | `{removed: bool}` |
| `presence.set` | `{status}` | `{status}` |
| `debug.inject` | `{text}` | `{message}` (demo only) |
| `shutdown` | `{}` | `{ok: true}` |

## Contact

```json
{
  "petname": "Alice",
  "pubkey": "<64 hex>",
  "nym_address": "<identity>.<encryption>@<gateway>",
  "created_at": 1790000000000
}
```

## ChatMessage

```json
{
  "msg_id": "<32 hex>",
  "conversation_id": "dm:<peer pubkey>",
  "from": "<64 hex>",
  "to": "<64 hex>",
  "body": "hello",
  "at": 1790000000000,
  "direction": "incoming|outgoing",
  "state": "sent|queued|failed"
}
```

`group.create` selects saved contacts by public key. The returned `invite` is a
signed JSON capability containing the room key and roster; share it out of band.
`group.join` verifies the invite signature and requires this chat identity to be
in the member list. Messages use `conversation_id = "group:<gid>"`, and inbound
room events arrive through the same `message` event.

## Error codes

| Code | Meaning |
|---|---|
| `bad_request` | malformed params, unknown method, invalid key |
| `not_found` | missing contact/conversation |
| `transport` | transport failure, including a daemon built without `--features nym` |
| `crypto` | seal/open/signature failure |
| `internal` | local storage or unexpected failure |
| `daemon_down` | UI-side RPC client lost the process |
| `timeout` | UI-side request timeout |

## Environment

| Variable | Meaning |
|---|---|
| `NCC_DATA_DIR` | app data directory |
| `NCC_MASTER_KEY` | 32-byte hex master key; otherwise `dev-master.key` |
| `NCC_TRANSPORT` | `mock` or `nym` |
| `NCC_DEMO` | `1` seeds the demo contact and enables `debug.inject` |
| `NCC_NYM_GATEWAY` | optional Nym entry-gateway identity key |

`dev-master.key` is a development fallback. Replace it with the OS keychain
before shipping.

`--transport nym` requires an `ncc-daemon` built with `--features nym`; without
it the daemon fails explicitly at startup.
