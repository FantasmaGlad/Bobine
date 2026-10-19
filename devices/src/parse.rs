//! Analyseurs PURS des sorties d'outils Windows et macOS — compilés et testés sur toutes les
//! plateformes (les exemples des tests sont des sorties représentatives, pas des captures de machines).

use serde_json::{json, Value};

// ---------------------------------------------------------------------------
// Communs
// ---------------------------------------------------------------------------

/// dBm → pourcentage de qualité (0-100) : -50 dBm et mieux = 100, -100 dBm et pire = 0.
pub fn dbm_to_percent(dbm: f64) -> u8 {
    (2.0 * (dbm + 100.0)).clamp(0.0, 100.0).round() as u8
}

/// Sous-réseau CIDR depuis une adresse IPv4 et un masque pointé (`255.255.255.0`) ou hexadécimal (`0xffffff00`).
pub fn subnet_cidr(ip: &str, mask: &str) -> Option<String> {
    let ip: Vec<u8> = ip
        .split('.')
        .map(|p| p.parse().ok())
        .collect::<Option<Vec<u8>>>()?;
    if ip.len() != 4 {
        return None;
    }
    let mask_bits: u32 = if let Some(hex) = mask.strip_prefix("0x") {
        u32::from_str_radix(hex, 16).ok()?
    } else {
        let parts: Vec<u8> = mask
            .split('.')
            .map(|p| p.parse().ok())
            .collect::<Option<Vec<u8>>>()?;
        if parts.len() != 4 {
            return None;
        }
        u32::from_be_bytes([parts[0], parts[1], parts[2], parts[3]])
    };
    let prefix = mask_bits.count_ones();
    if mask_bits.leading_ones() != prefix {
        return None; // masque non contigu
    }
    let ip_bits = u32::from_be_bytes([ip[0], ip[1], ip[2], ip[3]]);
    let net = ip_bits & mask_bits;
    let b = net.to_be_bytes();
    Some(format!("{}.{}.{}.{}/{}", b[0], b[1], b[2], b[3], prefix))
}

// ---------------------------------------------------------------------------
// macOS
// ---------------------------------------------------------------------------

/// `networksetup -listallhardwareports` → périphérique du port Wi-Fi (`en0`).
pub fn macos_wifi_device(text: &str) -> Option<String> {
    let mut is_wifi = false;
    for line in text.lines() {
        if let Some(port) = line.strip_prefix("Hardware Port:") {
            let port = port.trim();
            is_wifi = port.eq_ignore_ascii_case("Wi-Fi") || port.eq_ignore_ascii_case("AirPort");
        } else if is_wifi {
            if let Some(device) = line.strip_prefix("Device:") {
                return Some(device.trim().to_string());
            }
        }
    }
    None
}

/// `Wi-Fi Power (en0): On` → Some(true).
pub fn macos_wifi_power(text: &str) -> Option<bool> {
    let value = text.rsplit(':').next()?.trim().to_ascii_lowercase();
    match value.as_str() {
        "on" => Some(true),
        "off" => Some(false),
        _ => None,
    }
}

/// `Current Wi-Fi Network: X` → Some("X") ; « not associated » → None.
pub fn macos_current_network(text: &str) -> Option<String> {
    let line = text.lines().next()?;
    let (_, name) = line.split_once("Current Wi-Fi Network:")?;
    let name = name.trim();
    if name.is_empty() {
        None
    } else {
        Some(name.to_string())
    }
}

/// `networksetup -listpreferredwirelessnetworks en0` → noms (lignes indentées).
pub fn macos_preferred_networks(text: &str) -> Vec<String> {
    text.lines()
        .filter(|l| l.starts_with('\t') || l.starts_with("    "))
        .map(|l| l.trim().to_string())
        .filter(|l| !l.is_empty())
        .collect()
}

fn macos_security(mode: &str) -> String {
    let m = mode
        .strip_prefix("spairport_security_mode_")
        .unwrap_or(mode);
    match m {
        "none" | "open" => String::new(),
        "wep" => "WEP".into(),
        "wpa_personal" | "wpa_enterprise" => "WPA".into(),
        "wpa2_personal" | "wpa2_enterprise" => "WPA2".into(),
        "wpa3_personal" | "wpa3_enterprise" | "wpa3_transition" => "WPA3".into(),
        other => other.replace('_', " ").to_uppercase(),
    }
}

fn macos_band(channel: &str) -> String {
    if channel.contains("6GHz") {
        "6 GHz".into()
    } else if channel.contains("5GHz") {
        "5 GHz".into()
    } else if channel.contains("2GHz") {
        "2.4 GHz".into()
    } else {
        String::new()
    }
}

fn macos_signal(text: &str) -> u8 {
    // "-55 dBm / -90 dBm" : le premier nombre est le signal.
    text.split_whitespace()
        .next()
        .and_then(|n| n.parse::<f64>().ok())
        .map(dbm_to_percent)
        .unwrap_or(0)
}

/// `system_profiler SPAirPortDataType -json` → (réseau courant, autres réseaux) pour l'interface donnée.
pub fn macos_airport(json_text: &str, device: &str, known: &[String]) -> Option<Vec<Value>> {
    let root: Value = serde_json::from_str(json_text).ok()?;
    let interfaces =
        root["SPAirPortDataType"].get(0)?["spairport_airport_interfaces"].as_array()?;
    let iface = interfaces
        .iter()
        .find(|i| i["_name"] == device)
        .or_else(|| interfaces.first())?;
    let mut networks: Vec<Value> = Vec::new();
    let mut push = |item: &Value, in_use: bool| {
        let ssid = item["_name"].as_str().unwrap_or("");
        if ssid.is_empty() || ssid == "<redacted>" {
            return;
        }
        networks.push(json!({
            "ssid": ssid,
            "signal": macos_signal(item["spairport_signal_noise"].as_str().unwrap_or("")),
            "security": macos_security(item["spairport_security_mode"].as_str().unwrap_or("none")),
            "band": macos_band(item["spairport_network_channel"].as_str().unwrap_or("")),
            "known": known.iter().any(|k| k == ssid),
            "in_use": in_use,
        }));
    };
    if iface["spairport_current_network_information"].is_object() {
        push(&iface["spairport_current_network_information"], true);
    }
    for key in [
        "spairport_airport_other_local_wireless_networks",
        "spairport_airport_local_wireless_networks",
    ] {
        if let Some(list) = iface[key].as_array() {
            for item in list {
                push(item, false);
            }
        }
    }
    Some(networks)
}

fn macos_audio_kind(transport: &str, name: &str) -> &'static str {
    let t = transport.to_ascii_lowercase();
    let n = name.to_ascii_lowercase();
    if t.contains("bluetooth") {
        "bluetooth"
    } else if t.contains("usb") {
        "usb"
    } else if t.contains("hdmi")
        || t.contains("displayport")
        || n.contains("hdmi")
        || n.contains("display")
    {
        "hdmi"
    } else if t.contains("builtin") || t.contains("built_in") {
        "internal"
    } else if t.contains("virtual") || t.contains("aggregate") {
        "virtual"
    } else {
        "other"
    }
}

/// `system_profiler SPAudioDataType -json` → (sorties, id de la sortie par défaut).
pub fn macos_audio(json_text: &str) -> Option<(Vec<Value>, Option<String>)> {
    let root: Value = serde_json::from_str(json_text).ok()?;
    let mut devices = Vec::new();
    let mut default_id = None;
    for group in root["SPAudioDataType"].as_array()? {
        for item in group["_items"].as_array().into_iter().flatten() {
            if item.get("coreaudio_device_output").is_none() {
                continue;
            }
            let name = item["_name"].as_str().unwrap_or("").to_string();
            if name.is_empty() {
                continue;
            }
            let is_default = item["coreaudio_default_audio_output_device"] == "spaudio_yes";
            if is_default {
                default_id = Some(name.clone());
            }
            devices.push(json!({
                "id": name,
                "name": name,
                "description": "",
                "manufacturer": item["coreaudio_device_manufacturer"].as_str().unwrap_or(""),
                "kind": macos_audio_kind(item["coreaudio_device_transport"].as_str().unwrap_or(""), &name),
                "is_default": is_default,
                "available": true,
                "volume": null,
                "muted": null,
            }));
        }
    }
    Some((devices, default_id))
}

fn bluetooth_kind(minor: &str) -> &'static str {
    match minor.to_ascii_lowercase().as_str() {
        "headset" => "headset",
        "headphones" => "headphones",
        "speaker" | "loudspeaker" => "speaker",
        "keyboard" => "keyboard",
        "mouse" | "trackpad" => "mouse",
        "gamepad" | "game controller" => "gamepad",
        "phone" | "cellphone" => "phone",
        _ => "other",
    }
}

/// `system_profiler SPBluetoothDataType -json` → (allumé, appareils appairés).
pub fn macos_bluetooth(json_text: &str) -> Option<(bool, Vec<Value>)> {
    let root: Value = serde_json::from_str(json_text).ok()?;
    let block = root["SPBluetoothDataType"].get(0)?;
    let powered = block["controller_properties"]["controller_state"] == "attrib_on";
    let mut devices = Vec::new();
    for (key, connected) in [("device_connected", true), ("device_not_connected", false)] {
        for entry in block[key].as_array().into_iter().flatten() {
            for (name, props) in entry.as_object().into_iter().flatten() {
                let address = props["device_address"]
                    .as_str()
                    .unwrap_or("")
                    .replace('-', ":")
                    .to_uppercase();
                devices.push(json!({
                    "address": address,
                    "name": name,
                    "paired": true,
                    "connected": connected,
                    "trusted": true,
                    "rssi": null,
                    "kind": bluetooth_kind(props["device_minorType"].as_str().unwrap_or("")),
                    "profiles": [],
                    "battery": props["device_batteryLevelMain"].as_str().and_then(|b| b.trim_end_matches('%').parse::<u64>().ok()),
                }));
            }
        }
    }
    Some((powered, devices))
}

// ---------------------------------------------------------------------------
// Windows
// ---------------------------------------------------------------------------

fn key_matches(key: &str, aliases: &[&str]) -> bool {
    let k = key.trim().to_lowercase();
    aliases.iter().any(|a| k == *a)
}

/// Valeur après le premier « : » d'une ligne `Clé : Valeur` (les clés de `netsh` sont localisées).
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

/// `netsh wlan show interfaces` (anglais et français) → première interface Wi-Fi.
pub fn windows_interface(text: &str) -> Option<NetshInterface> {
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

fn windows_security(value: &str) -> Option<String> {
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

/// `netsh wlan show networks mode=bssid` → réseaux dédoublonnés (signal maximal), `known` rempli par l'appelant.
pub fn windows_networks(text: &str, current: Option<&str>, known: &[String]) -> Vec<Value> {
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
            // « SSID 3 : Nom » (et non « SSID : » de l'interface)
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
            if let Some(sec) = windows_security(value) {
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

/// `netsh wlan show profiles` → noms des profils (lignes « … : Nom » sous l'en-tête de l'interface).
pub fn windows_profiles(text: &str) -> Vec<String> {
    text.lines()
        .filter(|l| l.starts_with(' ') || l.starts_with('\t'))
        .filter_map(|l| l.split_once(" : ").map(|(_, v)| v.trim().to_string()))
        .filter(|v| !v.is_empty())
        .collect()
}

/// Échappement XML minimal pour les profils Wi-Fi générés.
pub fn xml_escape(text: &str) -> String {
    text.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}

/// Profil WLAN minimal (WPA2-Personal/AES, ou ouvert) pour `netsh wlan add profile`.
pub fn windows_profile_xml(ssid: &str, password: Option<&str>) -> String {
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

/// Sortie JSON de PowerShell : un objet seul ou un tableau → toujours un tableau.
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

/// `Get-PnpDevice -Class Bluetooth` : appareils (adresse extraite de `BTHENUM\DEV_AABBCCDDEEFF\...`).
pub fn windows_bluetooth(items: &[Value]) -> Vec<Value> {
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dbm_and_subnet() {
        assert_eq!(dbm_to_percent(-50.0), 100);
        assert_eq!(dbm_to_percent(-75.0), 50);
        assert_eq!(dbm_to_percent(-120.0), 0);
        assert_eq!(
            subnet_cidr("192.168.1.17", "255.255.255.0").as_deref(),
            Some("192.168.1.0/24")
        );
        assert_eq!(
            subnet_cidr("10.1.2.3", "0xffff0000").as_deref(),
            Some("10.1.0.0/16")
        );
        assert_eq!(subnet_cidr("10.1.2.3", "255.0.255.0"), None);
        assert_eq!(subnet_cidr("x", "255.0.0.0"), None);
    }

    #[test]
    fn macos_networksetup() {
        let ports = "Hardware Port: Ethernet\nDevice: en5\nEthernet Address: aa\n\nHardware Port: Wi-Fi\nDevice: en0\nEthernet Address: bb\n";
        assert_eq!(macos_wifi_device(ports).as_deref(), Some("en0"));
        assert_eq!(
            macos_wifi_device("Hardware Port: Ethernet\nDevice: en5\n"),
            None
        );
        assert_eq!(macos_wifi_power("Wi-Fi Power (en0): On"), Some(true));
        assert_eq!(macos_wifi_power("Wi-Fi Power (en0): Off"), Some(false));
        assert_eq!(
            macos_current_network("Current Wi-Fi Network: Livebox\n").as_deref(),
            Some("Livebox")
        );
        assert_eq!(
            macos_current_network("You are not associated with an AirPort network.\n"),
            None
        );
        assert_eq!(
            macos_preferred_networks("Preferred networks on en0:\n\tLivebox\n\tFanta\n"),
            vec!["Livebox", "Fanta"]
        );
    }

    const AIRPORT: &str = r#"{"SPAirPortDataType":[{"spairport_airport_interfaces":[{"_name":"en0",
      "spairport_current_network_information":{"_name":"Livebox","spairport_network_channel":"36 (5GHz, 80MHz)","spairport_security_mode":"spairport_security_mode_wpa2_personal","spairport_signal_noise":"-55 dBm / -90 dBm"},
      "spairport_airport_other_local_wireless_networks":[
        {"_name":"Voisin","spairport_network_channel":"1 (2GHz, 20MHz)","spairport_security_mode":"spairport_security_mode_wpa3_personal","spairport_signal_noise":"-80 dBm / -92 dBm"},
        {"_name":"Cafe","spairport_network_channel":"6 (2GHz, 20MHz)","spairport_security_mode":"spairport_security_mode_none","spairport_signal_noise":"-90 dBm / -92 dBm"}]}]}]}"#;

    #[test]
    fn macos_airport_lists_current_and_others() {
        let nets = macos_airport(AIRPORT, "en0", &["Livebox".to_string()]).unwrap();
        assert_eq!(nets.len(), 3);
        assert_eq!(nets[0]["ssid"], "Livebox");
        assert_eq!(nets[0]["in_use"], true);
        assert_eq!(nets[0]["known"], true);
        assert_eq!(nets[0]["band"], "5 GHz");
        assert_eq!(nets[0]["security"], "WPA2");
        assert_eq!(nets[1]["security"], "WPA3");
        assert_eq!(nets[2]["security"], "");
        assert_eq!(nets[1]["signal"], 40);
        assert!(macos_airport("pas du json", "en0", &[]).is_none());
    }

    #[test]
    fn macos_audio_and_bluetooth() {
        let audio = r#"{"SPAudioDataType":[{"_items":[
          {"_name":"MacBook Pro Speakers","coreaudio_default_audio_output_device":"spaudio_yes","coreaudio_device_output":2,"coreaudio_device_transport":"coreaudio_device_type_builtin"},
          {"_name":"AirPods","coreaudio_device_output":2,"coreaudio_device_transport":"coreaudio_device_type_bluetooth"},
          {"_name":"Micro","coreaudio_device_input":1}]}]}"#;
        let (devices, default_id) = macos_audio(audio).unwrap();
        assert_eq!(devices.len(), 2);
        assert_eq!(default_id.as_deref(), Some("MacBook Pro Speakers"));
        assert_eq!(devices[0]["kind"], "internal");
        assert_eq!(devices[1]["kind"], "bluetooth");

        let bt = r#"{"SPBluetoothDataType":[{"controller_properties":{"controller_state":"attrib_on"},
          "device_connected":[{"AirPods":{"device_address":"AA-BB-CC-DD-EE-FF","device_minorType":"Headphones","device_batteryLevelMain":"80%"}}],
          "device_not_connected":[{"Souris":{"device_address":"11:22:33:44:55:66","device_minorType":"Mouse"}}]}]}"#;
        let (powered, devices) = macos_bluetooth(bt).unwrap();
        assert!(powered);
        assert_eq!(devices[0]["address"], "AA:BB:CC:DD:EE:FF");
        assert_eq!(devices[0]["connected"], true);
        assert_eq!(devices[0]["kind"], "headphones");
        assert_eq!(devices[0]["battery"], 80);
        assert_eq!(devices[1]["kind"], "mouse");
    }

    const NETSH_IF_EN: &str = "There is 1 interface on the system:\n\n    Name                   : Wi-Fi\n    Description            : Intel(R) Wi-Fi 6\n    State                  : connected\n    SSID                   : Livebox\n    BSSID                  : aa:bb:cc:dd:ee:ff\n    Network type           : Infrastructure\n    Band                   : 5 GHz\n    Signal                 : 84%\n";
    const NETSH_IF_FR: &str = "Il existe 1 interface sur le système :\n\n    Nom                    : Wi-Fi\n    État                   : connecté\n    SSID                   : Livebox\n    BSSID                  : aa:bb:cc:dd:ee:ff\n    Bande                  : 5 GHz\n    Signal                 : 71%\n";

    #[test]
    fn windows_interface_en_and_fr() {
        let en = windows_interface(NETSH_IF_EN).unwrap();
        assert!(
            en.connected
                && en.ssid.as_deref() == Some("Livebox")
                && en.signal == 84
                && en.band == "5 GHz"
        );
        let fr = windows_interface(NETSH_IF_FR).unwrap();
        assert!(fr.connected && fr.signal == 71 && fr.name == "Wi-Fi");
        let off = windows_interface("    Name : Wi-Fi\n    State : disconnected\n").unwrap();
        assert!(!off.connected && off.ssid.is_none());
        assert!(windows_interface("rien").is_none());
    }

    #[test]
    fn windows_networks_dedupes_and_flags() {
        let text = "Interface name : Wi-Fi\nThere are 3 networks currently visible.\n\nSSID 1 : Livebox\n    Network type            : Infrastructure\n    Authentication          : WPA2-Personal\n    Encryption              : CCMP\n    BSSID 1                 : aa:bb\n         Signal             : 80%\n         Band               : 5 GHz\n    BSSID 2                 : cc:dd\n         Signal             : 55%\n         Band               : 2.4 GHz\n\nSSID 2 : Cafe\n    Authentication          : Open\n    BSSID 1                 : ee:ff\n         Signal             : 30%\n\nSSID 3 : \n    Authentication          : WPA2-Personal\n    BSSID 1                 : 11:22\n         Signal             : 20%\n";
        let nets = windows_networks(text, Some("Livebox"), &["Livebox".to_string()]);
        assert_eq!(nets.len(), 2);
        assert_eq!(nets[0]["signal"], 80);
        assert_eq!(nets[0]["security"], "WPA2");
        assert_eq!(nets[0]["in_use"], true);
        assert_eq!(nets[0]["known"], true);
        assert_eq!(nets[0]["band"], "5 GHz");
        assert_eq!(nets[1]["security"], "");
    }

    #[test]
    fn windows_profiles_and_xml() {
        let text = "Profiles on interface Wi-Fi:\n\nGroup policy profiles (read only)\n---------------------------------\n    <None>\n\nUser profiles\n-------------\n    All User Profile     : Livebox\n    All User Profile     : Café & Co\n";
        assert_eq!(windows_profiles(text), vec!["Livebox", "Café & Co"]);
        let xml = windows_profile_xml("A&B", Some("p<w>\"'"));
        assert!(
            xml.contains("<name>A&amp;B</name>")
                && xml.contains("p&lt;w&gt;&quot;&apos;")
                && xml.contains("WPA2PSK")
        );
        assert!(
            windows_profile_xml("Libre", None).contains("<authentication>open</authentication>")
        );
    }

    #[test]
    fn powershell_json_and_bluetooth() {
        assert_eq!(powershell_json_array("").len(), 0);
        assert_eq!(powershell_json_array(r#"{"a":1}"#).len(), 1);
        assert_eq!(powershell_json_array(r#"[{"a":1},{"a":2}]"#).len(), 2);
        let items = powershell_json_array(
            r#"[{"FriendlyName":"JBL","Status":"OK","InstanceId":"BTHENUM\\DEV_88B2CC9C410E\\7&1&0&BLUETOOTHDEVICE_88B2CC9C410E"},{"FriendlyName":"Radio","Status":"OK","InstanceId":"USB\\VID_8087"}]"#,
        );
        let devices = windows_bluetooth(&items);
        assert_eq!(devices.len(), 1);
        assert_eq!(devices[0]["address"], "88:B2:CC:9C:41:0E");
        assert_eq!(devices[0]["connected"], true);
    }
}
