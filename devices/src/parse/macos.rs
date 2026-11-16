use super::dbm_to_percent;
use serde_json::{json, Value};

pub fn wifi_device(text: &str) -> Option<String> {
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

pub fn wifi_power(text: &str) -> Option<bool> {
    let value = text.rsplit(':').next()?.trim().to_ascii_lowercase();
    match value.as_str() {
        "on" => Some(true),
        "off" => Some(false),
        _ => None,
    }
}

pub fn current_network(text: &str) -> Option<String> {
    let line = text.lines().next()?;
    let (_, name) = line.split_once("Current Wi-Fi Network:")?;
    let name = name.trim();
    if name.is_empty() {
        None
    } else {
        Some(name.to_string())
    }
}

pub fn preferred_networks(text: &str) -> Vec<String> {
    text.lines()
        .filter(|l| l.starts_with('\t') || l.starts_with("    "))
        .map(|l| l.trim().to_string())
        .filter(|l| !l.is_empty())
        .collect()
}

fn security(mode: &str) -> String {
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

fn band(channel: &str) -> String {
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

fn signal(text: &str) -> u8 {
    text.split_whitespace()
        .next()
        .and_then(|n| n.parse::<f64>().ok())
        .map(dbm_to_percent)
        .unwrap_or(0)
}

pub fn airport(json_text: &str, device: &str, known: &[String]) -> Option<Vec<Value>> {
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
            "signal": signal(item["spairport_signal_noise"].as_str().unwrap_or("")),
            "security": security(item["spairport_security_mode"].as_str().unwrap_or("none")),
            "band": band(item["spairport_network_channel"].as_str().unwrap_or("")),
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

fn audio_kind(transport: &str, name: &str) -> &'static str {
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

pub fn audio(json_text: &str) -> Option<(Vec<Value>, Option<String>)> {
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
                "kind": audio_kind(item["coreaudio_device_transport"].as_str().unwrap_or(""), &name),
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

pub fn bluetooth(json_text: &str) -> Option<(bool, Vec<Value>)> {
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
