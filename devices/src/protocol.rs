//! Protocole JSON-RPC 2.0 sur stdin/stdout, versionné.
//!
//! * une requête = une réponse, une ligne JSON chacune (`\n` final) ;
//! * `protocol_version` est annoncé par `hello` : le backend refuse un sidecar d'une autre version ;
//! * **liste blanche** de méthodes : toute autre méthode reçoit « méthode introuvable » avant
//!   même d'atteindre une plateforme ;
//! * paramètres validés ici (types, longueurs, formats) — les plateformes ne reçoivent jamais de
//!   valeur non contrôlée ;
//! * aucune donnée n'est jamais écrite sur stdout hors réponses (les journaux vont sur stderr).

use serde::Serialize;
use serde_json::{json, Map, Value};

pub const PROTOCOL_VERSION: u64 = 1;
pub const MAX_LINE_BYTES: usize = 64 * 1024;

pub const ERR_PARSE: i64 = -32700;
pub const ERR_INVALID_REQUEST: i64 = -32600;
pub const ERR_METHOD_NOT_FOUND: i64 = -32601;
pub const ERR_INVALID_PARAMS: i64 = -32602;
/// Erreur applicative : `data.code` porte un code stable (`unsupported`, `tool_missing`, `timeout`...).
pub const ERR_APPLICATION: i64 = -32000;

/// Méthodes acceptées — rien d'autre n'est jamais exécuté.
pub const METHODS: &[&str] = &[
    "hello",
    "audio.list",
    "audio.set_default",
    "audio.set_volume",
    "bluetooth.status",
    "bluetooth.set_power",
    "bluetooth.scan",
    "bluetooth.pair",
    "bluetooth.connect",
    "bluetooth.disconnect",
    "bluetooth.forget",
    "wifi.status",
    "wifi.scan",
    "wifi.set_power",
    "wifi.current_connection",
    "wifi.connect",
    "wifi.activate",
    "wifi.forget",
    "wifi.subnet",
];

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct RpcError {
    pub code: i64,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<Value>,
}

impl RpcError {
    pub fn app(code: &str, message: impl Into<String>) -> Self {
        RpcError {
            code: ERR_APPLICATION,
            message: message.into(),
            data: Some(json!({ "code": code })),
        }
    }
    pub fn unsupported(message: impl Into<String>) -> Self {
        Self::app("unsupported", message)
    }
    pub fn invalid_params(message: impl Into<String>) -> Self {
        RpcError {
            code: ERR_INVALID_PARAMS,
            message: message.into(),
            data: None,
        }
    }
}

pub type RpcResult = Result<Value, RpcError>;

/// Plateforme : un backend par système d'exploitation.
pub trait Platform {
    fn name(&self) -> &'static str;
    /// `{clé: {"supported": bool, "reason"?: str}}`
    fn capabilities(&self) -> Value;
    fn call(&self, method: &str, params: &Map<String, Value>) -> RpcResult;
}

/// Traite UNE ligne de requête et renvoie la ligne de réponse (sans `\n`).
pub fn handle_line(platform: &dyn Platform, line: &str) -> String {
    let response = match serde_json::from_str::<Value>(line) {
        Err(_) => error_response(
            Value::Null,
            RpcError {
                code: ERR_PARSE,
                message: "JSON invalide".into(),
                data: None,
            },
        ),
        Ok(value) => handle_value(platform, value),
    };
    response.to_string()
}

fn handle_value(platform: &dyn Platform, value: Value) -> Value {
    let obj = match value.as_object() {
        Some(obj) => obj,
        None => {
            return error_response(
                Value::Null,
                RpcError {
                    code: ERR_INVALID_REQUEST,
                    message: "Requête invalide".into(),
                    data: None,
                },
            )
        }
    };
    let id = obj.get("id").cloned().unwrap_or(Value::Null);
    if !(id.is_null() || id.is_u64() || id.is_i64() || id.is_string()) {
        return error_response(
            Value::Null,
            RpcError {
                code: ERR_INVALID_REQUEST,
                message: "Identifiant invalide".into(),
                data: None,
            },
        );
    }
    if obj.get("jsonrpc").and_then(Value::as_str) != Some("2.0") {
        return error_response(
            id,
            RpcError {
                code: ERR_INVALID_REQUEST,
                message: "jsonrpc doit valoir 2.0".into(),
                data: None,
            },
        );
    }
    let method = match obj.get("method").and_then(Value::as_str) {
        Some(m) => m,
        None => {
            return error_response(
                id,
                RpcError {
                    code: ERR_INVALID_REQUEST,
                    message: "Méthode manquante".into(),
                    data: None,
                },
            )
        }
    };
    if !METHODS.contains(&method) {
        return error_response(
            id,
            RpcError {
                code: ERR_METHOD_NOT_FOUND,
                message: format!("Méthode introuvable : {method}"),
                data: None,
            },
        );
    }
    let empty = Map::new();
    let params = match obj.get("params") {
        None | Some(Value::Null) => &empty,
        Some(Value::Object(map)) => map,
        Some(_) => {
            return error_response(id, RpcError::invalid_params("params doit être un objet"))
        }
    };
    if let Err(e) = validate_params(method, params) {
        return error_response(id, e);
    }
    let result = if method == "hello" {
        Ok(json!({
            "protocol_version": PROTOCOL_VERSION,
            "version": env!("CARGO_PKG_VERSION"),
            "platform": platform.name(),
            "capabilities": platform.capabilities(),
        }))
    } else {
        platform.call(method, params)
    };
    match result {
        Ok(value) => json!({ "jsonrpc": "2.0", "id": id, "result": value }),
        Err(err) => error_response(id, err),
    }
}

fn error_response(id: Value, err: RpcError) -> Value {
    json!({ "jsonrpc": "2.0", "id": id, "error": err })
}

// ---------------------------------------------------------------------------
// Validation des paramètres
// ---------------------------------------------------------------------------

fn get_str<'a>(params: &'a Map<String, Value>, key: &str) -> Result<&'a str, RpcError> {
    params
        .get(key)
        .and_then(Value::as_str)
        .ok_or_else(|| RpcError::invalid_params(format!("paramètre texte manquant : {key}")))
}

fn get_bool(params: &Map<String, Value>, key: &str) -> Result<bool, RpcError> {
    params
        .get(key)
        .and_then(Value::as_bool)
        .ok_or_else(|| RpcError::invalid_params(format!("paramètre booléen manquant : {key}")))
}

/// Pas de caractère de contrôle, longueur bornée (un SSID fait au plus 32 octets ; marge pour les identifiants).
pub fn is_safe_text(text: &str, max_bytes: usize) -> bool {
    !text.is_empty() && text.len() <= max_bytes && !text.chars().any(|c| c.is_control())
}

pub fn is_valid_mac(text: &str) -> bool {
    let parts: Vec<&str> = text.split(':').collect();
    parts.len() == 6
        && parts
            .iter()
            .all(|p| p.len() == 2 && p.chars().all(|c| c.is_ascii_hexdigit()))
}

fn validate_params(method: &str, params: &Map<String, Value>) -> Result<(), RpcError> {
    match method {
        "audio.set_default" => check_text(params, "id", 256),
        "audio.set_volume" => {
            check_text(params, "id", 256)?;
            if let Some(v) = params.get("volume") {
                if !v.is_null() {
                    let n = v
                        .as_f64()
                        .ok_or_else(|| RpcError::invalid_params("volume doit être un nombre"))?;
                    if !(0.0..=1.5).contains(&n) {
                        return Err(RpcError::invalid_params("volume hors de [0, 1,5]"));
                    }
                }
            }
            if let Some(m) = params.get("muted") {
                if !m.is_null() && !m.is_boolean() {
                    return Err(RpcError::invalid_params("muted doit être un booléen"));
                }
            }
            Ok(())
        }
        "bluetooth.set_power" | "bluetooth.scan" | "wifi.set_power" => {
            get_bool(params, "on").map(|_| ())
        }
        "bluetooth.pair" | "bluetooth.connect" | "bluetooth.disconnect" | "bluetooth.forget" => {
            let address = get_str(params, "address")?;
            if is_valid_mac(address) {
                Ok(())
            } else {
                Err(RpcError::invalid_params("adresse Bluetooth invalide"))
            }
        }
        "wifi.connect" => {
            check_text(params, "ssid", 64)?;
            if let Some(p) = params.get("password") {
                if !p.is_null() {
                    let text = p
                        .as_str()
                        .ok_or_else(|| RpcError::invalid_params("password doit être un texte"))?;
                    if text.len() > 128 || text.chars().any(|c| c == '\n' || c == '\r' || c == '\0')
                    {
                        return Err(RpcError::invalid_params("mot de passe invalide"));
                    }
                }
            }
            Ok(())
        }
        "wifi.activate" | "wifi.forget" => check_text(
            params,
            if method == "wifi.forget" {
                "ssid"
            } else {
                "connection"
            },
            64,
        ),
        _ => Ok(()),
    }
}

fn check_text(params: &Map<String, Value>, key: &str, max: usize) -> Result<(), RpcError> {
    let text = get_str(params, key)?;
    if is_safe_text(text, max) {
        Ok(())
    } else {
        Err(RpcError::invalid_params(format!("{key} invalide")))
    }
}

/// Réponse de capacités uniforme : tout à faux avec la même raison.
pub fn capabilities_all(supported: bool, reason: &str) -> Value {
    let keys = [
        "audio_list",
        "audio_set_default",
        "audio_set_volume",
        "bluetooth_status",
        "bluetooth_power",
        "bluetooth_scan",
        "bluetooth_pair",
        "bluetooth_connect",
        "bluetooth_forget",
        "wifi_status",
        "wifi_power",
        "wifi_scan",
        "wifi_connect",
        "wifi_forget",
    ];
    let mut map = Map::new();
    for key in keys {
        let mut entry = Map::new();
        entry.insert("supported".into(), Value::Bool(supported));
        if !supported {
            entry.insert("reason".into(), Value::String(reason.to_string()));
        }
        map.insert(key.into(), Value::Object(entry));
    }
    Value::Object(map)
}

#[cfg(test)]
mod tests {
    use super::*;

    struct Fake;
    impl Platform for Fake {
        fn name(&self) -> &'static str {
            "fake"
        }
        fn capabilities(&self) -> Value {
            capabilities_all(true, "")
        }
        fn call(&self, method: &str, params: &Map<String, Value>) -> RpcResult {
            match method {
                "audio.list" => Ok(json!({"supported": true, "devices": [], "default_id": null})),
                "wifi.connect" => Ok(json!({"ssid": params["ssid"]})),
                _ => Err(RpcError::unsupported("non géré")),
            }
        }
    }

    fn call(line: &str) -> Value {
        serde_json::from_str(&handle_line(&Fake, line)).unwrap()
    }

    #[test]
    fn hello_announces_the_protocol_version_and_capabilities() {
        let r = call(r#"{"jsonrpc":"2.0","id":1,"method":"hello"}"#);
        assert_eq!(r["id"], 1);
        assert_eq!(r["result"]["protocol_version"], PROTOCOL_VERSION);
        assert_eq!(r["result"]["platform"], "fake");
        assert_eq!(
            r["result"]["capabilities"]["wifi_connect"]["supported"],
            true
        );
    }

    #[test]
    fn unknown_methods_never_reach_the_platform() {
        for method in ["system.exec", "shell", "wifi.delete_all", "../hello", ""] {
            let r = call(&format!(
                r#"{{"jsonrpc":"2.0","id":2,"method":"{method}"}}"#
            ));
            assert_eq!(r["error"]["code"], ERR_METHOD_NOT_FOUND, "méthode {method}");
        }
    }

    #[test]
    fn malformed_requests_get_structured_errors() {
        assert_eq!(call("pas du json")["error"]["code"], ERR_PARSE);
        assert_eq!(call("[1,2]")["error"]["code"], ERR_INVALID_REQUEST);
        assert_eq!(
            call(r#"{"jsonrpc":"1.0","id":1,"method":"hello"}"#)["error"]["code"],
            ERR_INVALID_REQUEST
        );
        assert_eq!(
            call(r#"{"jsonrpc":"2.0","id":{"a":1},"method":"hello"}"#)["error"]["code"],
            ERR_INVALID_REQUEST
        );
        assert_eq!(
            call(r#"{"jsonrpc":"2.0","id":1,"method":"hello","params":[1]}"#)["error"]["code"],
            ERR_INVALID_PARAMS
        );
    }

    #[test]
    fn params_are_validated_before_the_platform() {
        let bad = [
            r#"{"jsonrpc":"2.0","id":1,"method":"wifi.connect","params":{}}"#,
            r#"{"jsonrpc":"2.0","id":1,"method":"wifi.connect","params":{"ssid":"a\nb"}}"#,
            r#"{"jsonrpc":"2.0","id":1,"method":"wifi.connect","params":{"ssid":"ok","password":"x\ny"}}"#,
            r#"{"jsonrpc":"2.0","id":1,"method":"bluetooth.pair","params":{"address":"nop"}}"#,
            r#"{"jsonrpc":"2.0","id":1,"method":"bluetooth.pair","params":{"address":"AA:BB:CC:DD:EE:GG"}}"#,
            r#"{"jsonrpc":"2.0","id":1,"method":"audio.set_volume","params":{"id":"x","volume":9}}"#,
            r#"{"jsonrpc":"2.0","id":1,"method":"wifi.set_power","params":{"on":"oui"}}"#,
        ];
        for line in bad {
            assert_eq!(call(line)["error"]["code"], ERR_INVALID_PARAMS, "{line}");
        }
        let ok = call(
            r#"{"jsonrpc":"2.0","id":"abc","method":"wifi.connect","params":{"ssid":"Maison"}}"#,
        );
        assert_eq!(ok["id"], "abc");
        assert_eq!(ok["result"]["ssid"], "Maison");
    }

    #[test]
    fn application_errors_carry_a_stable_code() {
        let r =
            call(r#"{"jsonrpc":"2.0","id":7,"method":"audio.set_default","params":{"id":"x"}}"#);
        assert_eq!(r["error"]["code"], ERR_APPLICATION);
        assert_eq!(r["error"]["data"]["code"], "unsupported");
    }

    #[test]
    fn helpers() {
        assert!(
            is_valid_mac("aa:BB:00:11:22:ff")
                && !is_valid_mac("aa:bb:00:11:22")
                && !is_valid_mac("aabbccddeeff")
        );
        assert!(is_safe_text("Café", 64) && !is_safe_text("", 64) && !is_safe_text("a\u{7}b", 64));
        assert!(!is_safe_text(&"x".repeat(65), 64));
    }
}
