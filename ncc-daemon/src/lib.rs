//! NCC daemon: a line-delimited JSON-RPC sidecar.
//!
//! The daemon owns the chat identity, contacts, sealed DM crypto, encrypted
//! history, and transport. The PySide6 UI must not implement crypto or open
//! the history files.

use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

use nysiris_chat_core::ChatEngine;
use nysiris_chat_history::History;
use nysiris_core::contact::Contact;
use nysiris_core::error::CoreError;
use nysiris_core::group::Group;
use nysiris_core::identity::ChatIdentity;
use nysiris_core::sealed_file::{read_sealed, write_sealed};
use nysiris_core::transport::Transport;
use nysiris_testkit::MemoryTransport;
use nysiris_transport_nym::NymTransport;
use rand::RngCore;
use serde::Deserialize;
use serde_json::{json, Value};

const IDENTITY_FILE: &str = "chat-identity.enc";
const CONTACTS_FILE: &str = "contacts.enc";
const GROUPS_FILE: &str = "groups.enc";
const IDENTITY_AAD: &[u8] = b"ncc/chat-identity/v1";
const CONTACTS_AAD: &[u8] = b"ncc/contacts/v1";
const GROUPS_AAD: &[u8] = b"ncc/groups/v1";
const DEMO_SEED: [u8; 32] = [7u8; 32];

pub type EventSink = Arc<dyn Fn(String) + Send + Sync>;

#[derive(Debug, Deserialize)]
pub struct RpcRequest {
    #[serde(default)]
    pub id: Value,
    pub method: String,
    #[serde(default)]
    pub params: Value,
}

#[derive(Debug, thiserror::Error)]
pub enum RpcError {
    #[error("{0}")]
    BadRequest(String),
    #[error("{0}")]
    NotFound(String),
    #[error("{0}")]
    Transport(String),
    #[error("{0}")]
    Crypto(String),
    #[error("{0}")]
    Internal(String),
}

impl RpcError {
    fn code(&self) -> &'static str {
        match self {
            Self::BadRequest(_) => "bad_request",
            Self::NotFound(_) => "not_found",
            Self::Transport(_) => "transport",
            Self::Crypto(_) => "crypto",
            Self::Internal(_) => "internal",
        }
    }
}

impl From<CoreError> for RpcError {
    fn from(value: CoreError) -> Self {
        match value {
            CoreError::InvalidInput(_) | CoreError::InvalidKey(_) => {
                Self::BadRequest(value.to_string())
            }
            CoreError::NotFound(_) => Self::NotFound(value.to_string()),
            CoreError::Transport(_) => Self::Transport(value.to_string()),
            CoreError::Crypto(_) => Self::Crypto(value.to_string()),
            _ => Self::Internal(value.to_string()),
        }
    }
}

pub struct Daemon {
    data_dir: PathBuf,
    key: [u8; 32],
    engine: Arc<Mutex<ChatEngine>>,
    nym: Option<Arc<NymTransport>>,
    demo: bool,
    should_exit: bool,
}

impl Daemon {
    pub fn new(
        data_dir: impl AsRef<Path>,
        key: [u8; 32],
        transport_kind: &str,
        demo: bool,
        event_sink: EventSink,
    ) -> Result<Self, RpcError> {
        let data_dir = data_dir.as_ref().to_path_buf();
        std::fs::create_dir_all(&data_dir)
            .map_err(|e| RpcError::Internal(format!("cannot create data dir: {e}")))?;

        let identity = load_or_create_identity(&data_dir, &key)?;
        let contacts = load_contacts(&data_dir, &key)?;
        let groups = load_groups(&data_dir, &key)?;
        let history = History::open(data_dir.join("history"), key)
            .map_err(|e| RpcError::Internal(format!("cannot open history: {e}")))?;

        let (transport, nym): (Arc<dyn Transport>, Option<Arc<NymTransport>>) = match transport_kind
        {
            "nym" => {
                let gateway = std::env::var("NCC_NYM_GATEWAY").ok();
                let nym = Arc::new(
                    NymTransport::connect(data_dir.join("nym"), gateway)
                        .map_err(|e| RpcError::Transport(e.to_string()))?,
                );
                let transport: Arc<dyn Transport> = nym.clone();
                (transport, Some(nym))
            }
            "mock" | "memory" => (Arc::new(MemoryTransport::new()), None),
            other => {
                return Err(RpcError::BadRequest(format!(
                    "unknown transport {other:?}; use mock or nym"
                )))
            }
        };

        let own_nym_address = nym
            .as_ref()
            .map(|n| n.address().to_string())
            .unwrap_or_else(|| format!("mock:{}", identity.public_hex()));
        let mut engine = ChatEngine::new(
            identity,
            contacts,
            groups,
            history,
            transport,
            own_nym_address,
        );
        if demo {
            seed_demo(&mut engine, &data_dir, &key)?;
        }
        let engine = Arc::new(Mutex::new(engine));

        if let Some(nym) = &nym {
            spawn_nym_reader(Arc::clone(nym), Arc::clone(&engine), event_sink);
        }

        Ok(Self {
            data_dir,
            key,
            engine,
            nym,
            demo,
            should_exit: false,
        })
    }

    pub fn data_dir(&self) -> &Path {
        &self.data_dir
    }

    pub fn should_exit(&self) -> bool {
        self.should_exit
    }

    pub fn shutdown(&self) {
        if let Some(nym) = &self.nym {
            nym.shutdown();
        }
    }

    /// Handle one JSON-RPC line. Returns the response line, if any.
    pub fn handle_line(&mut self, line: &str) -> Option<String> {
        let request: RpcRequest = match serde_json::from_str(line) {
            Ok(value) => value,
            Err(err) => {
                return Some(
                    json!({
                        "id": null,
                        "error": {"code": "bad_request", "message": format!("invalid JSON-RPC line: {err}")}
                    })
                    .to_string(),
                )
            }
        };

        let id = request.id.clone();
        let result = self.dispatch(&request.method, &request.params);
        Some(match result {
            Ok(value) => json!({"id": id, "result": value}).to_string(),
            Err(err) => json!({
                "id": id,
                "error": {"code": err.code(), "message": err.to_string()}
            })
            .to_string(),
        })
    }

    fn dispatch(&mut self, method: &str, params: &Value) -> Result<Value, RpcError> {
        let mut engine = self
            .engine
            .lock()
            .map_err(|_| RpcError::Internal("chat engine lock poisoned".into()))?;

        match method {
            "core.hello" => Ok(json!({
                "name": "ncc-daemon",
                "version": env!("CARGO_PKG_VERSION"),
                "protocol": 1,
                "transport": engine.transport_name(),
                "nym_address": self.nym.as_ref().map(|n| n.address().to_string()),
                "data_dir": self.data_dir.display().to_string(),
                "demo": self.demo,
            })),
            "identity.status" => {
                let pubkey = engine.identity().public_hex();
                let nym_address = self
                    .nym
                    .as_ref()
                    .map(|n| n.address().to_string())
                    .unwrap_or_else(|| format!("mock:{}", &pubkey[..12]));
                Ok(json!({
                    "pubkey": pubkey,
                    "nym_address": nym_address,
                    "transport": engine.transport_name(),
                    "status": engine.status(),
                }))
            }
            "contact.list" => Ok(json!({"contacts": engine.contacts()})),
            "contact.add" => {
                let petname = required_str(params, "petname")?;
                let pubkey = required_str(params, "pubkey")?;
                let nym_address = required_str(params, "nym_address")?;
                let contact = Contact::new(&petname, &pubkey, &nym_address)?;
                let saved = engine.add_contact(contact);
                save_contacts(&self.data_dir, &self.key, engine.contacts())?;
                Ok(json!({"contact": saved}))
            }
            "contact.remove" => {
                let pubkey = required_str(params, "pubkey")?;
                let removed = engine.remove_contact(&pubkey);
                save_contacts(&self.data_dir, &self.key, engine.contacts())?;
                Ok(json!({"removed": removed}))
            }
            "chat.conversations" => Ok(json!({"conversations": engine.conversations()})),
            "chat.history" => {
                let peer_pub = required_str(params, "peer_pub")?;
                let limit = params.get("limit").and_then(Value::as_u64).unwrap_or(200) as usize;
                Ok(json!({"messages": engine.history_for(&peer_pub, limit)}))
            }
            "chat.send" => {
                let peer_pub = required_str(params, "peer_pub")?;
                let text = required_str(params, "text")?;
                let message = engine.send_dm(&peer_pub, &text)?;
                Ok(json!({"message": message}))
            }
            "chat.clear" => {
                engine
                    .clear_history()
                    .map_err(|e| RpcError::Internal(e.to_string()))?;
                Ok(json!({"cleared": true}))
            }
            "group.list" => Ok(json!({"groups": engine.group_summaries()})),
            "group.create" => {
                let name = required_str(params, "name")?;
                let member_pubkeys: Vec<String> = params
                    .get("member_pubkeys")
                    .and_then(Value::as_array)
                    .map(|rows| {
                        rows.iter()
                            .filter_map(Value::as_str)
                            .map(str::to_string)
                            .collect()
                    })
                    .unwrap_or_default();
                let (group, invite) = engine.create_group(&name, &member_pubkeys)?;
                save_groups(&self.data_dir, &self.key, engine.groups())?;
                Ok(json!({"group": group, "invite": invite}))
            }
            "group.join" => {
                let invite = required_str(params, "invite")?;
                let group = engine.join_group(&invite)?;
                save_groups(&self.data_dir, &self.key, engine.groups())?;
                Ok(json!({"group": group}))
            }
            "group.invite" => {
                let group_id = required_str(params, "group_id")?;
                Ok(json!({"invite": engine.group_invite(&group_id)?}))
            }
            "group.history" => {
                let group_id = required_str(params, "group_id")?;
                let limit = params.get("limit").and_then(Value::as_u64).unwrap_or(200) as usize;
                Ok(json!({"messages": engine.group_history(&group_id, limit)}))
            }
            "group.send" => {
                let group_id = required_str(params, "group_id")?;
                let text = required_str(params, "text")?;
                let report = engine.send_group(&group_id, &text)?;
                Ok(json!({
                    "message": report.message,
                    "delivered": report.delivered,
                    "failed": report.failed,
                }))
            }
            "group.leave" => {
                let group_id = required_str(params, "group_id")?;
                let removed = engine.remove_group(&group_id);
                save_groups(&self.data_dir, &self.key, engine.groups())?;
                Ok(json!({"removed": removed}))
            }
            "presence.set" => {
                let status = required_str(params, "status")?;
                engine.set_status(&status)?;
                Ok(json!({"status": engine.status()}))
            }
            "debug.inject" => {
                if !self.demo {
                    return Err(RpcError::BadRequest(
                        "debug.inject is only available with --demo".into(),
                    ));
                }
                let text = required_str(params, "text")?;
                let demo_identity = ChatIdentity::from_secret_bytes(DEMO_SEED);
                let contact = Contact::new(
                    "Demo Contact",
                    &demo_identity.public_hex(),
                    "demo.contact@mock",
                )?;
                engine.add_contact(contact);
                save_contacts(&self.data_dir, &self.key, engine.contacts())?;
                let message = engine
                    .deliver_demo(&demo_identity, &text)
                    .map_err(|e| RpcError::Internal(e.to_string()))?;
                Ok(json!({"message": message}))
            }
            "shutdown" => {
                drop(engine);
                self.should_exit = true;
                self.shutdown();
                Ok(json!({"ok": true}))
            }
            _ => Err(RpcError::BadRequest(format!("unknown method {method:?}"))),
        }
    }
}

impl Drop for Daemon {
    fn drop(&mut self) {
        self.shutdown();
    }
}

fn spawn_nym_reader(nym: Arc<NymTransport>, engine: Arc<Mutex<ChatEngine>>, sink: EventSink) {
    let _ = thread::Builder::new()
        .name("ncc-nym-inbound".into())
        .spawn(move || loop {
            match nym.recv_timeout(Duration::from_secs(1)) {
                Ok(Some(inbound)) => {
                    let result = {
                        let mut engine = match engine.lock() {
                            Ok(guard) => guard,
                            Err(_) => break,
                        };
                        engine.receive_any(&inbound.payload)
                    };
                    match result {
                        Ok(Some(message)) => {
                            sink(
                                json!({"event": "message", "data": {"message": message}})
                                    .to_string(),
                            );
                        }
                        Ok(None) => {}
                        Err(err) => {
                            sink(
                                json!({"event": "error", "data": {"message": err.to_string()}})
                                    .to_string(),
                            );
                        }
                    }
                }
                Ok(None) => {}
                Err(_) => break,
            }
        });
}

fn seed_demo(engine: &mut ChatEngine, data_dir: &Path, key: &[u8; 32]) -> Result<(), RpcError> {
    let demo_identity = ChatIdentity::from_secret_bytes(DEMO_SEED);
    let demo_contact = Contact::new(
        "Demo Contact",
        &demo_identity.public_hex(),
        "demo.contact@mock",
    )?;
    engine.add_contact(demo_contact);
    save_contacts(data_dir, key, engine.contacts())?;
    if engine
        .history_for(&demo_identity.public_hex(), 1)
        .is_empty()
    {
        engine
            .deliver_demo(
                &demo_identity,
                "Welcome to NCC. This is a local demo message; there is no chat service and no server history.",
            )
            .map_err(|e| RpcError::Internal(format!("demo seed failed: {e}")))?;
    }
    if engine.groups().is_empty() {
        let (group, _invite) = engine
            .create_group("Demo Room", &[demo_identity.public_hex()])
            .map_err(|e| RpcError::Internal(format!("demo room seed failed: {e}")))?;
        save_groups(data_dir, key, engine.groups())?;
        engine
            .deliver_demo_group(
                &demo_identity,
                &group.id,
                "Welcome to the demo room. Everyone gets the room key from the invite; messages are fanned out directly.",
            )
            .map_err(|e| RpcError::Internal(format!("demo room message failed: {e}")))?;
    }
    Ok(())
}

fn required_str(params: &Value, field: &str) -> Result<String, RpcError> {
    params
        .get(field)
        .and_then(Value::as_str)
        .map(str::to_string)
        .ok_or_else(|| RpcError::BadRequest(format!("missing string field {field:?}")))
}

fn load_or_create_identity(data_dir: &Path, key: &[u8; 32]) -> Result<ChatIdentity, RpcError> {
    let path = data_dir.join(IDENTITY_FILE);
    match read_sealed(&path, key, IDENTITY_AAD) {
        Ok(bytes) => {
            let value: Value = serde_json::from_slice(&bytes)
                .map_err(|e| RpcError::Internal(format!("bad identity file: {e}")))?;
            let secret = value
                .get("secret_hex")
                .and_then(Value::as_str)
                .ok_or_else(|| RpcError::Internal("identity file has no secret_hex".into()))?;
            ChatIdentity::from_secret_hex(secret).map_err(Into::into)
        }
        Err(CoreError::Io(err)) if err.kind() == std::io::ErrorKind::NotFound => {
            let identity = ChatIdentity::generate();
            let raw = serde_json::to_vec(&json!({"secret_hex": identity.secret_hex()}))
                .map_err(|e| RpcError::Internal(e.to_string()))?;
            write_sealed(&path, key, IDENTITY_AAD, &raw)
                .map_err(|e| RpcError::Internal(format!("cannot write identity: {e}")))?;
            Ok(identity)
        }
        Err(err) => Err(RpcError::Internal(format!("cannot read identity: {err}"))),
    }
}

fn load_contacts(data_dir: &Path, key: &[u8; 32]) -> Result<Vec<Contact>, RpcError> {
    let path = data_dir.join(CONTACTS_FILE);
    match read_sealed(&path, key, CONTACTS_AAD) {
        Ok(bytes) => serde_json::from_slice(&bytes)
            .map_err(|e| RpcError::Internal(format!("bad contacts file: {e}"))),
        Err(CoreError::Io(err)) if err.kind() == std::io::ErrorKind::NotFound => Ok(Vec::new()),
        Err(err) => Err(RpcError::Internal(format!("cannot read contacts: {err}"))),
    }
}

fn save_contacts(data_dir: &Path, key: &[u8; 32], contacts: &[Contact]) -> Result<(), RpcError> {
    let raw = serde_json::to_vec(contacts).map_err(|e| RpcError::Internal(e.to_string()))?;
    write_sealed(&data_dir.join(CONTACTS_FILE), key, CONTACTS_AAD, &raw)
        .map_err(|e| RpcError::Internal(format!("cannot write contacts: {e}")))
}

fn load_groups(data_dir: &Path, key: &[u8; 32]) -> Result<Vec<Group>, RpcError> {
    let path = data_dir.join(GROUPS_FILE);
    match read_sealed(&path, key, GROUPS_AAD) {
        Ok(bytes) => serde_json::from_slice(&bytes)
            .map_err(|e| RpcError::Internal(format!("bad groups file: {e}"))),
        Err(CoreError::Io(err)) if err.kind() == std::io::ErrorKind::NotFound => Ok(Vec::new()),
        Err(err) => Err(RpcError::Internal(format!("cannot read groups: {err}"))),
    }
}

fn save_groups(data_dir: &Path, key: &[u8; 32], groups: &[Group]) -> Result<(), RpcError> {
    let raw = serde_json::to_vec(groups).map_err(|e| RpcError::Internal(e.to_string()))?;
    write_sealed(&data_dir.join(GROUPS_FILE), key, GROUPS_AAD, &raw)
        .map_err(|e| RpcError::Internal(format!("cannot write groups: {e}")))
}

/// Resolve the development master key. Phase 0 uses an explicit env key or a
/// local `dev-master.key`; the OS keychain adapter is the next hardening step.
pub fn resolve_master_key(data_dir: &Path) -> Result<[u8; 32], RpcError> {
    if let Ok(value) = std::env::var("NCC_MASTER_KEY") {
        let raw = hex::decode(value.trim())
            .map_err(|_| RpcError::BadRequest("NCC_MASTER_KEY is not hex".into()))?;
        if raw.len() != 32 {
            return Err(RpcError::BadRequest(
                "NCC_MASTER_KEY must be 32 bytes of hex".into(),
            ));
        }
        let mut key = [0u8; 32];
        key.copy_from_slice(&raw);
        return Ok(key);
    }

    let path = data_dir.join("dev-master.key");
    if let Ok(value) = std::fs::read_to_string(&path) {
        let raw = hex::decode(value.trim())
            .map_err(|_| RpcError::Internal("dev-master.key is not hex".into()))?;
        if raw.len() != 32 {
            return Err(RpcError::Internal(
                "dev-master.key must be 32 bytes of hex".into(),
            ));
        }
        let mut key = [0u8; 32];
        key.copy_from_slice(&raw);
        return Ok(key);
    }

    let mut key = [0u8; 32];
    rand::rngs::OsRng.fill_bytes(&mut key);
    std::fs::create_dir_all(data_dir)
        .map_err(|e| RpcError::Internal(format!("cannot create data dir: {e}")))?;
    std::fs::write(&path, hex::encode(key))
        .map_err(|e| RpcError::Internal(format!("cannot write dev-master.key: {e}")))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o600));
    }
    eprintln!(
        "warning: using a development master key at {}; replace with the OS keychain",
        path.display()
    );
    Ok(key)
}

pub fn default_data_dir() -> PathBuf {
    if let Ok(value) = std::env::var("NCC_DATA_DIR") {
        return PathBuf::from(value);
    }
    if cfg!(windows) {
        if let Ok(appdata) = std::env::var("APPDATA") {
            return PathBuf::from(appdata).join("NCC");
        }
    }
    if let Ok(xdg) = std::env::var("XDG_DATA_HOME") {
        return PathBuf::from(xdg).join("ncc");
    }
    if let Ok(home) = std::env::var("HOME") {
        return PathBuf::from(home).join(".local/share/ncc");
    }
    PathBuf::from("ncc-data")
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn daemon() -> (Daemon, TempDir) {
        let dir = TempDir::new().unwrap();
        let daemon = Daemon::new(dir.path(), [11u8; 32], "mock", true, Arc::new(|_| {})).unwrap();
        (daemon, dir)
    }

    #[test]
    fn hello_reports_protocol_and_demo() {
        let (mut daemon, _dir) = daemon();
        let line = daemon
            .handle_line(r#"{"id":1,"method":"core.hello","params":{}}"#)
            .unwrap();
        let value: Value = serde_json::from_str(&line).unwrap();
        assert_eq!(value["result"]["protocol"], 1);
        assert_eq!(value["result"]["transport"], "memory");
        assert_eq!(value["result"]["demo"], true);
    }

    #[test]
    fn demo_contact_and_welcome_message_are_seeded() {
        let (mut daemon, _dir) = daemon();
        let line = daemon
            .handle_line(r#"{"id":1,"method":"contact.list","params":{}}"#)
            .unwrap();
        let value: Value = serde_json::from_str(&line).unwrap();
        assert_eq!(value["result"]["contacts"][0]["petname"], "Demo Contact");

        let line = daemon
            .handle_line(&format!(
                r#"{{"id":2,"method":"chat.history","params":{{"peer_pub":"{}"}}}}"#,
                ChatIdentity::from_secret_bytes(DEMO_SEED).public_hex()
            ))
            .unwrap();
        let value: Value = serde_json::from_str(&line).unwrap();
        assert_eq!(value["result"]["messages"].as_array().unwrap().len(), 1);
    }

    #[test]
    fn debug_inject_creates_an_incoming_message() {
        let (mut daemon, _dir) = daemon();
        let line = daemon
            .handle_line(r#"{"id":1,"method":"debug.inject","params":{"text":"ping"}}"#)
            .unwrap();
        let value: Value = serde_json::from_str(&line).unwrap();
        assert_eq!(value["result"]["message"]["body"], "ping");
        assert_eq!(value["result"]["message"]["direction"], "incoming");
    }

    #[test]
    fn demo_room_and_group_fanout_are_seeded() {
        let (mut daemon, _dir) = daemon();
        let line = daemon
            .handle_line(r#"{"id":1,"method":"group.list","params":{}}"#)
            .unwrap();
        let value: Value = serde_json::from_str(&line).unwrap();
        let groups = value["result"]["groups"].as_array().unwrap();
        assert_eq!(groups.len(), 1);
        assert_eq!(groups[0]["name"], "Demo Room");
        let demo_gid = groups[0]["id"].as_str().unwrap().to_string();

        let line = daemon
            .handle_line(&format!(
                r#"{{"id":2,"method":"group.history","params":{{"group_id":"{demo_gid}"}}}}"#
            ))
            .unwrap();
        let value: Value = serde_json::from_str(&line).unwrap();
        assert_eq!(value["result"]["messages"].as_array().unwrap().len(), 1);

        let demo_pub = ChatIdentity::from_secret_bytes(DEMO_SEED).public_hex();
        let line = daemon
            .handle_line(&format!(
                r#"{{"id":3,"method":"group.create","params":{{"name":"Test Room","member_pubkeys":["{demo_pub}"]}}}}"#
            ))
            .unwrap();
        let value: Value = serde_json::from_str(&line).unwrap();
        let gid = value["result"]["group"]["id"].as_str().unwrap().to_string();
        assert!(value["result"]["invite"]
            .as_str()
            .unwrap()
            .contains("Test Room"));

        let line = daemon
            .handle_line(&format!(
                r#"{{"id":4,"method":"group.send","params":{{"group_id":"{gid}","text":"hello room"}}}}"#
            ))
            .unwrap();
        let value: Value = serde_json::from_str(&line).unwrap();
        assert_eq!(value["result"]["delivered"], 1);
        assert_eq!(value["result"]["message"]["body"], "hello room");

        let line = daemon
            .handle_line(&format!(
                r#"{{"id":5,"method":"group.history","params":{{"group_id":"{gid}"}}}}"#
            ))
            .unwrap();
        let value: Value = serde_json::from_str(&line).unwrap();
        assert_eq!(value["result"]["messages"].as_array().unwrap().len(), 1);
    }

    #[test]
    fn bad_method_returns_an_error() {
        let (mut daemon, _dir) = daemon();
        let line = daemon
            .handle_line(r#"{"id":1,"method":"nope","params":{}}"#)
            .unwrap();
        let value: Value = serde_json::from_str(&line).unwrap();
        assert_eq!(value["error"]["code"], "bad_request");
    }
}
