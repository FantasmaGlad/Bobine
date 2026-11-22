use serde_json::{json, Value};

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
