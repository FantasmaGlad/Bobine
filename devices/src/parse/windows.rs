use serde_json::{json, Value};

pub fn powershell_json_array(text: &str) -> Vec<Value> {
    let text = text.trim();
    if text.is_empty() {
        return Vec::new();
    }
    match serde_json::from_str::<Value>(text) {
        Ok(Value::Array(items)) => items,
        Ok(obj @ Value::Object(_)) => vec![obj],
        _ => Vec::new(),
    }
}

pub fn bluetooth(items: &[Value]) -> Vec<Value> {
    let mut devices = Vec::new();
    for item in items {
        let id = item["InstanceId"].as_str().unwrap_or("");
        let Some(pos) = id.to_uppercase().find("DEV_") else {
            continue;
        };
        let hex: String = id[pos + 4..].chars().take(12).collect();
        if hex.len() != 12 || !hex.chars().all(|c| c.is_ascii_hexdigit()) {
            continue;
        }
        let address = hex
            .as_bytes()
            .chunks(2)
            .map(|c| String::from_utf8_lossy(c).to_uppercase())
            .collect::<Vec<_>>()
            .join(":");
        if devices
            .iter()
            .any(|d: &Value| d["address"] == address.as_str())
        {
            continue;
        }
        devices.push(json!({
            "address": address,
            "name": item["FriendlyName"].as_str().unwrap_or(&address),
            "paired": true,
            "connected": item["Status"] == "OK",
            "trusted": true,
            "rssi": null,
            "kind": "other",
            "profiles": [],
            "battery": null,
        }));
    }
    devices
}
