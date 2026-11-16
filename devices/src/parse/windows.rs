use serde_json::{json, Value};

fn key_matches(key: &str, aliases: &[&str]) -> bool {
    let k = key.trim().to_lowercase();
    aliases.iter().any(|a| k == *a)
}

fn split_kv(line: &str) -> Option<(&str, &str)> {
    let (k, v) = line.split_once(':')?;
    Some((k.trim(), v.trim()))
}

pub struct NetshInterface {
    pub name: String,
    pub connected: bool,
    pub ssid: Option<String>,
    pub signal: u8,
    pub band: String,
}

pub fn interface(text: &str) -> Option<NetshInterface> {
    let mut name = None;
    let mut ssid = None;
    let mut bssid = false;
    let mut signal = 0u8;
    let mut band = String::new();
    let mut state_connected = None;
    for line in text.lines() {
        let Some((key, value)) = split_kv(line) else {
            continue;
        };
        if key_matches(key, &["name", "nom"]) && name.is_none() {
            name = Some(value.to_string());
        } else if key_matches(key, &["state", "état", "etat"]) {
            let v = value.to_lowercase();
            state_connected = Some(v == "connected" || v == "connecté" || v == "connecte");
        } else if key_matches(key, &["ssid"]) {
            ssid = if value.is_empty() {
                None
            } else {
                Some(value.to_string())
            };
        } else if key_matches(key, &["bssid", "ap bssid"]) {
            bssid = !value.is_empty();
        } else if key_matches(key, &["signal"]) {
            signal = value.trim_end_matches('%').trim().parse().unwrap_or(0);
        } else if key_matches(key, &["band", "bande"]) {
            band = value.to_string();
        }
    }
    let name = name?;
    let connected = state_connected.unwrap_or(ssid.is_some() && bssid) && ssid.is_some();
    Some(NetshInterface {
        name,
        connected,
        ssid,
        signal,
        band,
    })
}

fn security(value: &str) -> Option<String> {
    let v = value.to_lowercase();
    if v.contains("wpa3") {
        Some("WPA3".into())
    } else if v.contains("wpa2") {
        Some("WPA2".into())
    } else if v.contains("wpa") {
        Some("WPA".into())
    } else if v.contains("wep") {
        Some("WEP".into())
    } else if v == "open" || v == "ouvert" || v == "ouverte" {
        Some(String::new())
    } else {
        None
    }
}

pub fn networks(text: &str, current: Option<&str>, known: &[String]) -> Vec<Value> {
    struct Net {
        ssid: String,
        security: Option<String>,
        signal: u8,
        band: String,
    }
    let mut nets: Vec<Net> = Vec::new();
    for line in text.lines() {
        let trimmed = line.trim();
        if let Some(rest) = trimmed.strip_prefix("SSID ") {
            if let Some((idx, name)) = rest.split_once(':') {
                if idx.trim().chars().all(|c| c.is_ascii_digit()) && !idx.trim().is_empty() {
                    nets.push(Net {
                        ssid: name.trim().to_string(),
                        security: None,
                        signal: 0,
                        band: String::new(),
                    });
                    continue;
                }
            }
        }
        let Some(net) = nets.last_mut() else { continue };
        let Some((key, value)) = split_kv(trimmed) else {
            continue;
        };
        if net.security.is_none() {
            if let Some(sec) = security(value) {
                net.security = Some(sec);
                continue;
            }
        }
        if key_matches(key, &["signal"]) {
            let s: u8 = value.trim_end_matches('%').trim().parse().unwrap_or(0);
            net.signal = net.signal.max(s);
        } else if key_matches(key, &["band", "bande"]) && net.band.is_empty() {
            net.band = value.to_string();
        }
    }
    let mut best: Vec<Value> = Vec::new();
    for n in nets.into_iter().filter(|n| !n.ssid.is_empty()) {
        if best.iter().any(|b| b["ssid"] == n.ssid.as_str()) {
            continue;
        }
        best.push(json!({
            "ssid": n.ssid,
            "signal": n.signal,
            "security": n.security.unwrap_or_default(),
            "band": n.band,
            "known": known.contains(&n.ssid),
            "in_use": current == Some(n.ssid.as_str()),
        }));
    }
    best
}

pub fn profiles(text: &str) -> Vec<String> {
    text.lines()
        .filter(|l| l.starts_with(' ') || l.starts_with('\t'))
        .filter_map(|l| l.split_once(" : ").map(|(_, v)| v.trim().to_string()))
        .filter(|v| !v.is_empty())
        .collect()
}

pub fn xml_escape(text: &str) -> String {
    text.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}

pub fn profile_xml(ssid: &str, password: Option<&str>) -> String {
    let ssid = xml_escape(ssid);
    let security = match password {
        Some(pw) => format!(
            "<security><authEncryption><authentication>WPA2PSK</authentication><encryption>AES</encryption><useOneX>false</useOneX></authEncryption><sharedKey><keyType>passPhrase</keyType><protected>false</protected><keyMaterial>{}</keyMaterial></sharedKey></security>",
            xml_escape(pw)
        ),
        None => "<security><authEncryption><authentication>open</authentication><encryption>none</encryption><useOneX>false</useOneX></authEncryption></security>".to_string(),
    };
    format!(
        "<?xml version=\"1.0\"?><WLANProfile xmlns=\"http://www.microsoft.com/networking/WLAN/profile/v1\"><name>{ssid}</name><SSIDConfig><SSID><name>{ssid}</name></SSID></SSIDConfig><connectionType>ESS</connectionType><connectionMode>auto</connectionMode><MSM>{security}</MSM></WLANProfile>"
    )
}

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
