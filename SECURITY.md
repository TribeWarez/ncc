# Security

NCC is experimental and has not had an independent security audit. The DM and
room cryptography in `core/` is protocol code, not audited production crypto.

## Reporting

Do not open a public issue for a vulnerability. Use GitHub's private security
advisory flow for `TribeWarez/ncc`:

<https://github.com/TribeWarez/ncc/security/advisories/new>

Include the affected component, a reproduction, the impact, and whether the
issue affects the mock transport, the Nym transport, or both.

## Scope reminders

- NCC has no chat service and no server-side message store.
- History is local and encrypted at rest; `dev-master.key` is a development
  fallback and must not ship.
- The Nym gateway queue is the only network-side message buffer.
- Nym hides who-talks-to-whom from network observers, not all metadata from
  gateways.
- Room invites are capability keys: anyone with an invite can read and post.
- Do not report the lack of server-side history, multi-device sync, or presence
  as vulnerabilities; they are deliberate product constraints.

## Supported versions

Only the current `main` branch is supported during pre-release development.
